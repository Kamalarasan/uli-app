import asyncio
import logging
import random
import string
from datetime import date, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models.orm import Applicant, LoanApplication, UnderwritingReport
from app.pipeline.orchestrator import run_underwriting_pipeline

router = APIRouter(prefix="/api", tags=["applications"])
logger = logging.getLogger(__name__)


class ApplicationCreate(BaseModel):
    full_name: str
    email: str
    phone: str
    pan_number: str
    aadhaar_number: str
    date_of_birth: str  # YYYY-MM-DD string from form
    address: str
    city: str
    state: str
    employment_type: str
    employer_name: str
    industry: str
    years_employed: float = 0.0
    loan_amount: float
    loan_purpose: str = "PERSONAL"
    tenure_months: int
    monthly_income: float
    monthly_expenses: float
    existing_emi: float = 0.0
    credit_score: int = 650


@router.post("/applications")
def create_application(app_in: ApplicationCreate, db: Session = Depends(get_db)):
    """Create or retrieve applicant and create a new loan application."""
    # Parse date_of_birth
    dob: date | None = None
    try:
        dob = datetime.strptime(app_in.date_of_birth, "%Y-%m-%d").date()
    except ValueError:
        dob = None

    # Upsert applicant by email
    applicant = db.query(Applicant).filter(Applicant.email == app_in.email).first()
    if not applicant:
        applicant = Applicant(
            full_name=app_in.full_name,
            email=app_in.email,
            phone=app_in.phone,
            pan_number=app_in.pan_number,
            aadhaar_number=app_in.aadhaar_number,
            date_of_birth=dob,
            address=app_in.address,
            city=app_in.city,
            state=app_in.state,
            employment_type=app_in.employment_type.upper(),
            employer_name=app_in.employer_name,
            industry=app_in.industry,
            years_employed=app_in.years_employed,
        )
        db.add(applicant)
        db.commit()
        db.refresh(applicant)

    application = LoanApplication(
        applicant_id=applicant.id,
        loan_amount=app_in.loan_amount,
        loan_purpose=app_in.loan_purpose.upper(),
        tenure_months=app_in.tenure_months,
        monthly_income=app_in.monthly_income,
        monthly_expenses=app_in.monthly_expenses,
        existing_emi=app_in.existing_emi,
        credit_score=app_in.credit_score,
        status="PENDING",
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    return {
        "id": application.id,
        "applicant_id": applicant.id,
        "status": application.status,
        "message": "Application created successfully.",
    }


def _run_pipeline_sync(app_id: int) -> None:
    """Run pipeline in a new DB session (for BackgroundTasks)."""
    db = SessionLocal()
    try:
        asyncio.run(run_underwriting_pipeline(app_id, db))
    except Exception as e:
        logger.error(f"Background pipeline error for app {app_id}: {e}")
    finally:
        db.close()


@router.post("/applications/{app_id}/process")
def process_application(
    app_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Trigger the 8-stage underwriting pipeline as a background task."""
    application = db.query(LoanApplication).filter(LoanApplication.id == app_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.status in ("PROCESSING",):
        return {"message": "Pipeline already running.", "application_id": app_id}

    application.status = "PROCESSING"
    db.commit()

    background_tasks.add_task(_run_pipeline_sync, app_id)
    return {"message": "Pipeline started successfully.", "application_id": app_id}


@router.get("/applications")
def list_applications(
    page: int = 1, limit: int = 10, db: Session = Depends(get_db)
):
    """List all loan applications with pagination."""
    skip = (page - 1) * limit
    apps = (
        db.query(LoanApplication)
        .order_by(LoanApplication.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    total = db.query(LoanApplication).count()
    result = []
    for a in apps:
        result.append({
            "id": a.id,
            "applicant_name": a.applicant.full_name if a.applicant else "Unknown",
            "applicant_email": a.applicant.email if a.applicant else "",
            "status": a.status,
            "loan_amount": a.loan_amount,
            "loan_purpose": a.loan_purpose,
            "credit_score": a.credit_score,
            "pipeline_progress": a.pipeline_progress,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "has_report": a.report is not None,
        })
    return {"total": total, "page": page, "limit": limit, "items": result}


@router.get("/applications/{app_id}")
def get_application(app_id: int, db: Session = Depends(get_db)):
    """Get a single application with applicant details and report summary."""
    a = db.query(LoanApplication).filter(LoanApplication.id == app_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Application not found")

    report = a.report
    return {
        "id": a.id,
        "status": a.status,
        "pipeline_progress": a.pipeline_progress,
        "loan_amount": a.loan_amount,
        "loan_purpose": a.loan_purpose,
        "tenure_months": a.tenure_months,
        "monthly_income": a.monthly_income,
        "monthly_expenses": a.monthly_expenses,
        "existing_emi": a.existing_emi,
        "credit_score": a.credit_score,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "applicant": {
            "id": a.applicant.id,
            "full_name": a.applicant.full_name,
            "email": a.applicant.email,
            "phone": a.applicant.phone,
            "pan_number": a.applicant.pan_number,
            "employment_type": a.applicant.employment_type,
            "employer_name": a.applicant.employer_name,
            "industry": a.applicant.industry,
            "years_employed": a.applicant.years_employed,
        } if a.applicant else None,
        "report_summary": {
            "decision": report.decision if report else None,
            "health_score": report.health_score if report else None,
            "fraud_score": report.fraud_score if report else None,
            "recommended_rate": report.recommended_rate if report else None,
            "confidence_score": report.confidence_score if report else None,
        } if report else None,
    }


def _random_pan() -> str:
    """Generate a random valid-format PAN number."""
    letters = string.ascii_uppercase
    return (
        random.choice(letters)
        + random.choice(letters)
        + random.choice(letters)
        + random.choice(letters)
        + random.choice(letters)
        + str(random.randint(1000, 9999))
        + random.choice(letters)
    )


def _random_aadhaar() -> str:
    return "".join([str(random.randint(0, 9)) for _ in range(12)])


@router.post("/seed")
def seed_applications(db: Session = Depends(get_db)):
    """Seed the database with realistic demo loan applications."""
    demo_profiles = [
        {
            "name": "Ravi Kumar Sharma",
            "email": "ravi.kumar@techcorp.in",
            "phone": "9876543210",
            "city": "Bengaluru",
            "state": "Karnataka",
            "employer": "Infosys Technologies Ltd",
            "industry": "IT",
            "income": 95000,
            "expenses": 38000,
            "emi": 8000,
            "loan_amount": 1500000,
            "purpose": "HOME",
            "tenure": 180,
            "credit_score": 760,
            "years_employed": 6.5,
            "employment_type": "SALARIED",
            "status": "PENDING",
        },
        {
            "name": "Priya Anand Nair",
            "email": "priya.nair@outlook.in",
            "phone": "9845678901",
            "city": "Mumbai",
            "state": "Maharashtra",
            "employer": "HDFC Bank",
            "industry": "BANKING",
            "income": 120000,
            "expenses": 45000,
            "emi": 12000,
            "loan_amount": 3000000,
            "purpose": "HOME",
            "tenure": 240,
            "credit_score": 790,
            "years_employed": 9.0,
            "employment_type": "SALARIED",
            "status": "PENDING",
        },
        {
            "name": "Amit Patel",
            "email": "amit.patel@gmail.com",
            "phone": "9723456789",
            "city": "Ahmedabad",
            "state": "Gujarat",
            "employer": "Self Employed",
            "industry": "RETAIL",
            "income": 55000,
            "expenses": 42000,
            "emi": 6000,
            "loan_amount": 500000,
            "purpose": "BUSINESS",
            "tenure": 36,
            "credit_score": 620,
            "years_employed": 3.0,
            "employment_type": "SELF_EMPLOYED",
            "status": "PENDING",
        },
        {
            "name": "Sneha Mehra Gupta",
            "email": "sneha.mehra@wipro.com",
            "phone": "9654321098",
            "city": "Pune",
            "state": "Maharashtra",
            "employer": "Wipro Limited",
            "industry": "IT",
            "income": 200000,
            "expenses": 65000,
            "emi": 25000,
            "loan_amount": 8000000,
            "purpose": "HOME",
            "tenure": 300,
            "credit_score": 820,
            "years_employed": 12.0,
            "employment_type": "SALARIED",
            "status": "PENDING",
        },
        {
            "name": "Vikram Singh Rajput",
            "email": "vikram.rajput@tata.com",
            "phone": "9512345678",
            "city": "Chennai",
            "state": "Tamil Nadu",
            "employer": "Tata Motors",
            "industry": "MANUFACTURING",
            "income": 78000,
            "expenses": 32000,
            "emi": 5000,
            "loan_amount": 900000,
            "purpose": "AUTO",
            "tenure": 60,
            "credit_score": 700,
            "years_employed": 4.5,
            "employment_type": "SALARIED",
            "status": "PENDING",
        },
    ]

    created_count = 0
    for d in demo_profiles:
        # Skip if applicant already exists
        existing = db.query(Applicant).filter(Applicant.email == d["email"]).first()
        if existing:
            continue

        applicant = Applicant(
            full_name=d["name"],
            email=d["email"],
            phone=d["phone"],
            pan_number=_random_pan(),
            aadhaar_number=_random_aadhaar(),
            date_of_birth=date(1988, 6, 15),
            address=f"123 Main Street, {d['city']}",
            city=d["city"],
            state=d["state"],
            employment_type=d["employment_type"],
            employer_name=d["employer"],
            industry=d["industry"],
            years_employed=d["years_employed"],
        )
        db.add(applicant)
        db.commit()
        db.refresh(applicant)

        application = LoanApplication(
            applicant_id=applicant.id,
            loan_amount=d["loan_amount"],
            loan_purpose=d["purpose"],
            tenure_months=d["tenure"],
            monthly_income=d["income"],
            monthly_expenses=d["expenses"],
            existing_emi=d["emi"],
            credit_score=d["credit_score"],
            status=d["status"],
        )
        db.add(application)
        db.commit()
        created_count += 1

    return {
        "message": f"Demo data seeded successfully.",
        "applications_created": created_count,
        "note": "Use POST /api/applications/{id}/process to run the AI pipeline.",
    }
