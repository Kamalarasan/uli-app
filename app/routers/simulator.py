from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.digital_twin.simulator import run_simulation
from app.models.orm import DigitalTwinScenario, LoanApplication, UnderwritingReport

router = APIRouter(prefix="/api/simulator", tags=["simulator"])


class SimulationRequest(BaseModel):
    base_application_id: int
    scenario_name: str = "Custom Scenario"
    salary_change_pct: float = Field(0.0, ge=-50.0, le=100.0)
    expense_inflation_pct: float = Field(0.0, ge=-50.0, le=100.0)
    rate_shift_bps: float = Field(0.0, ge=-500.0, le=500.0)
    tenure_change_months: int = Field(0, ge=-120, le=120)
    economic_condition: str = Field("NORMAL", pattern="^(NORMAL|DOWNTURN|BOOM)$")


@router.post("/run")
async def execute_simulation(req: SimulationRequest, db: Session = Depends(get_db)):
    """Run a what-if simulation on a completed loan application."""
    app_obj = db.query(LoanApplication).filter(
        LoanApplication.id == req.base_application_id
    ).first()
    if not app_obj:
        raise HTTPException(status_code=404, detail="Application not found")

    report = db.query(UnderwritingReport).filter(
        UnderwritingReport.application_id == req.base_application_id
    ).first()
    if not report:
        raise HTTPException(
            status_code=400,
            detail="Application must have a completed underwriting report before simulation.",
        )

    result = await run_simulation(
        base_application_id=req.base_application_id,
        scenario_name=req.scenario_name,
        salary_change_pct=req.salary_change_pct,
        expense_inflation_pct=req.expense_inflation_pct,
        rate_shift_bps=req.rate_shift_bps,
        tenure_change_months=req.tenure_change_months,
        economic_condition=req.economic_condition,
        db=db,
    )
    return result


@router.get("/scenarios/{application_id}")
def list_scenarios(application_id: int, db: Session = Depends(get_db)):
    """List all simulation scenarios for a given application."""
    scenarios = (
        db.query(DigitalTwinScenario)
        .filter(DigitalTwinScenario.base_application_id == application_id)
        .order_by(DigitalTwinScenario.created_at.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "scenario_name": s.scenario_name,
            "scenario_params": s.scenario_params,
            "simulation_results": s.simulation_results,
            "approval_probability": s.approval_probability,
            "avg_risk_score": s.avg_risk_score,
            "estimated_default_rate": s.estimated_default_rate,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in scenarios
    ]


@router.get("/applications")
def list_simulatable_applications(db: Session = Depends(get_db)):
    """List applications with completed reports (eligible for simulation)."""
    apps = (
        db.query(LoanApplication)
        .filter(LoanApplication.status.in_(["APPROVED", "REVIEW", "REJECTED"]))
        .order_by(LoanApplication.created_at.desc())
        .all()
    )
    return [
        {
            "id": a.id,
            "applicant_name": a.applicant.full_name if a.applicant else "Unknown",
            "loan_amount": a.loan_amount,
            "loan_purpose": a.loan_purpose,
            "status": a.status,
            "has_report": a.report is not None,
            "decision": a.report.decision if a.report else None,
        }
        for a in apps
    ]
