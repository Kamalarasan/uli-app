from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.orm import LoanApplication, UnderwritingReport, Document

router = APIRouter(prefix="/api/reports", tags=["reports"])

@router.get("/{application_id}")
def get_report(application_id: int, db: Session = Depends(get_db)):
    report = db.query(UnderwritingReport).filter(UnderwritingReport.application_id == application_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    return {
        "id": report.id,
        "application_id": report.application_id,
        "decision": report.decision,
        "health_score": report.health_score,
        "risk_score": report.risk_score,
        "confidence_score": report.confidence_score,
        "approval_probability": report.approval_probability,
        "estimated_default_rate": report.estimated_default_rate,
        "max_emi": report.max_emi,
        "dti_ratio": report.dti_ratio,
        "stage_results": report.stage_results,
        "summary": report.summary,
        "created_at": report.created_at
    }

@router.get("/{application_id}/summary")
def get_report_summary(application_id: int, db: Session = Depends(get_db)):
    report = db.query(UnderwritingReport).filter(UnderwritingReport.application_id == application_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    # Mocking radar chart data based on report scores or defaults
    radar_data = [
        report.health_score or 70, # income_stability
        80, # expense_management
        75, # debt_management
        85, # credit_history
        100 - (report.risk_score or 30) # fraud_risk (inverted)
    ]
    
    return {
        "radar_data": radar_data,
        "gauge_data": {
            "risk_score": report.risk_score or 0,
            "health_score": report.health_score or 0,
            "confidence_score": report.confidence_score or 0
        }
    }
