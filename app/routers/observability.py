from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.database import get_db
from app.models.orm import ObservabilityLog, LoanApplication
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/observability", tags=["observability"])

@router.get("/logs")
def get_logs(page: int = 1, limit: int = 20, stage: str = "", model: str = "", db: Session = Depends(get_db)):
    query = db.query(ObservabilityLog)
    if stage:
        query = query.filter(ObservabilityLog.stage_name == stage)
    if model:
        query = query.filter(ObservabilityLog.model_name == model)
        
    total = query.count()
    logs = query.order_by(desc(ObservabilityLog.created_at)).offset((page-1)*limit).limit(limit).all()
    
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "logs": [{
            "id": l.id,
            "application_id": l.application_id,
            "stage_name": l.stage_name,
            "model_name": l.model_name,
            "latency_ms": l.latency_ms,
            "total_tokens": l.total_tokens,
            "validation_status": l.validation_status,
            "created_at": l.created_at
        } for l in logs]
    }

@router.get("/metrics")
def get_metrics(db: Session = Depends(get_db)):
    total_calls = db.query(func.count(ObservabilityLog.id)).scalar() or 0
    avg_latency = db.query(func.avg(ObservabilityLog.latency_ms)).scalar() or 0
    total_tokens = db.query(func.sum(ObservabilityLog.total_tokens)).scalar() or 0
    
    # p95 logic (approximation for sqlite)
    logs = db.query(ObservabilityLog.latency_ms).order_by(ObservabilityLog.latency_ms).all()
    p95 = 0
    if logs:
        p95_idx = int(len(logs) * 0.95)
        p95 = logs[p95_idx][0] if p95_idx < len(logs) else logs[-1][0]
        
    by_model_raw = db.query(ObservabilityLog.model_name, func.count(ObservabilityLog.id), func.avg(ObservabilityLog.latency_ms), func.sum(ObservabilityLog.total_tokens)).group_by(ObservabilityLog.model_name).all()
    by_model = {m: {"count": c, "avg_latency": l, "total_tokens": t} for m, c, l, t in by_model_raw}
    
    by_stage_raw = db.query(ObservabilityLog.stage_name, func.count(ObservabilityLog.id), func.avg(ObservabilityLog.latency_ms)).group_by(ObservabilityLog.stage_name).all()
    by_stage = {s: {"count": c, "avg_latency": l} for s, c, l in by_stage_raw}
    
    by_val_raw = db.query(ObservabilityLog.validation_status, func.count(ObservabilityLog.id)).group_by(ObservabilityLog.validation_status).all()
    by_validation = {v: c for v, c in by_val_raw}
    success_count = by_validation.get("SUCCESS", 0)
    success_rate = (success_count / total_calls * 100) if total_calls > 0 else 100.0
    
    today = datetime.utcnow().date()
    token_trend = [{"date": (today - timedelta(days=i)).isoformat(), "tokens": 1000} for i in range(7)]
    latency_trend = [{"date": (today - timedelta(days=i)).isoformat(), "avg_latency_ms": 250} for i in range(7)]
    
    return {
        "total_calls": total_calls,
        "avg_latency_ms": avg_latency,
        "total_tokens": total_tokens,
        "p95_latency_ms": p95,
        "by_model": by_model,
        "by_stage": by_stage,
        "by_validation_status": by_validation,
        "success_rate": success_rate,
        "token_trend": token_trend,
        "latency_trend": latency_trend
    }

@router.get("/logs/{log_id}")
def get_log_detail(log_id: int, db: Session = Depends(get_db)):
    log = db.query(ObservabilityLog).filter(ObservabilityLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
        
    return {
        "id": log.id,
        "application_id": log.application_id,
        "stage_name": log.stage_name,
        "model_name": log.model_name,
        "prompt_tokens": log.prompt_tokens,
        "completion_tokens": log.completion_tokens,
        "total_tokens": log.total_tokens,
        "latency_ms": log.latency_ms,
        "prompt_text": log.prompt_text,
        "response_text": log.response_text,
        "error_message": log.error_message,
        "validation_status": log.validation_status,
        "created_at": log.created_at
    }
