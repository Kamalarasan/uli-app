import time
import logging
import json
from datetime import datetime
from typing import Optional, Callable, Any
from sqlalchemy.orm import Session
from app.models.orm import ObservabilityLog

logger = logging.getLogger(__name__)

class LLMLogger:
    def __init__(self, db: Session, application_id: Optional[int] = None):
        self.db = db
        self.application_id = application_id
    
    async def log_llm_call(
        self,
        stage_name: str,
        prompt_template: str,
        prompt_version: str,
        model_id: str,
        call_fn: Callable,
        prompt_text: str = "",
        *args,
        **kwargs
    ) -> tuple[Any, ObservabilityLog]:
        """Wrap an LLM call with full observability logging.
        Returns (result, log_entry)."""
        start_time = time.time()
        validation_status = "SUCCESS"
        error_message = None
        result = None
        input_tokens = 0
        output_tokens = 0
        confidence_score = None
        decision = None
        response_preview = ""
        
        try:
            result = await call_fn(*args, **kwargs)
            # Extract token counts if result has usage attribute
            if hasattr(result, 'usage') and result.usage:
                input_tokens = result.usage.prompt_tokens or 0
                output_tokens = result.usage.completion_tokens or 0
            # Extract confidence/decision from result if it's a dict
            if isinstance(result, dict):
                confidence_score = result.get('confidence_score')
                decision = result.get('decision')
                response_preview = json.dumps(result)[:500]
        except Exception as e:
            validation_status = "FAILED"
            error_message = str(e)
            logger.error(f"LLM call failed in {stage_name}: {e}")
        finally:
            latency_ms = (time.time() - start_time) * 1000
        
        log_entry = ObservabilityLog(
            application_id=self.application_id,
            stage_name=stage_name,
            prompt_template=prompt_template,
            prompt_version=prompt_version,
            model_id=model_id,
            latency_ms=round(latency_ms, 2),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            validation_status=validation_status,
            confidence_score=confidence_score,
            decision=decision,
            error_message=error_message,
            prompt_preview=prompt_text[:500] if prompt_text else "",
            response_preview=response_preview,
        )
        
        try:
            self.db.add(log_entry)
            self.db.commit()
            self.db.refresh(log_entry)
        except Exception as db_err:
            logger.error(f"Failed to save observability log: {db_err}")
            self.db.rollback()
        
        if validation_status == "FAILED":
            raise RuntimeError(f"LLM call failed: {error_message}")
        
        return result, log_entry
    
    async def log_simple(
        self,
        stage_name: str,
        model_id: str,
        latency_ms: float,
        input_tokens: int,
        output_tokens: int,
        validation_status: str = "SUCCESS",
        confidence_score: Optional[float] = None,
        decision: Optional[str] = None,
        prompt_template: str = "",
        prompt_version: str = "1.0",
        error_message: Optional[str] = None,
        prompt_preview: str = "",
        response_preview: str = "",
    ) -> ObservabilityLog:
        """Log a pre-computed LLM call result."""
        log_entry = ObservabilityLog(
            application_id=self.application_id,
            stage_name=stage_name,
            prompt_template=prompt_template,
            prompt_version=prompt_version,
            model_id=model_id,
            latency_ms=round(latency_ms, 2),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            validation_status=validation_status,
            confidence_score=confidence_score,
            decision=decision,
            error_message=error_message,
            prompt_preview=prompt_preview[:500] if prompt_preview else "",
            response_preview=response_preview[:500] if response_preview else "",
        )
        try:
            self.db.add(log_entry)
            self.db.commit()
            self.db.refresh(log_entry)
        except Exception as db_err:
            logger.error(f"Failed to save observability log: {db_err}")
            self.db.rollback()
        return log_entry
