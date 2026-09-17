import logging
import time
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.orm import LoanApplication, Applicant, UnderwritingReport
from app.observability.logger import LLMLogger

from app.pipeline.stage1_validation import run_stage1
from app.pipeline.stage2_kyc_profiling import run_stage2
from app.pipeline.stage3_cashflow import run_stage3
from app.pipeline.stage4_health_scoring import run_stage4
from app.pipeline.stage5_fraud_detection import run_stage5
from app.pipeline.stage6_policy_matching import run_stage6
from app.pipeline.stage7_affordability import run_stage7
from app.pipeline.stage8_decision import run_stage8

logger = logging.getLogger(__name__)


async def run_underwriting_pipeline(application_id: int, db: Session) -> dict:
    """
    Main 8-stage underwriting pipeline orchestrator.
    Updates application status and progress in DB at each stage.
    Creates UnderwritingReport upon completion.
    """
    all_stage_results: dict = {}
    application = None

    try:
        # 1. Load application + applicant from DB
        application = db.query(LoanApplication).filter(LoanApplication.id == application_id).first()
        if not application:
            raise ValueError(f"Application {application_id} not found")

        applicant = db.query(Applicant).filter(Applicant.id == application.applicant_id).first()
        if not applicant:
            raise ValueError(f"Applicant {application.applicant_id} not found")

        # Instantiate LLMLogger with db session + application id
        llm_logger = LLMLogger(db=db, application_id=application_id)

        # 2. Build application_data dict from DB records
        application_data = {
            "application_id": application.id,
            "loan_amount": application.loan_amount,
            "loan_purpose": application.loan_purpose,
            "tenure_months": application.tenure_months,
            "monthly_income": application.monthly_income,
            "monthly_expenses": application.monthly_expenses,
            "existing_emi": application.existing_emi or 0.0,
            "credit_score": application.credit_score or 650,
            "applicant_id": applicant.id,
            "full_name": applicant.full_name,
            "email": applicant.email,
            "pan_number": applicant.pan_number or "",
            "aadhaar_number": applicant.aadhaar_number or "",
            "employment_type": applicant.employment_type or "SALARIED",
            "employer_name": applicant.employer_name or "",
            "industry": applicant.industry or "OTHER",
            "years_employed": applicant.years_employed or 0.0,
            "phone": applicant.phone or "",
            "address": applicant.address or "",
        }

        # 3. Set status=PROCESSING, progress=0
        application.status = "PROCESSING"
        application.pipeline_progress = 0
        db.commit()

        # ── STAGE 1: Data Validation & Cleaning ──────────────────────────────
        logger.info(f"[App {application_id}] Running Stage 1: Validation")
        stage1_res = await run_stage1(application_data)
        all_stage_results["stage1"] = stage1_res
        if stage1_res.get("status") == "FAILED":
            raise ValueError(f"Stage 1 validation failed: {stage1_res.get('validation_issues', [])}")
        # Use cleaned data for subsequent stages
        application_data.update(stage1_res.get("cleaned_data", {}))
        application.pipeline_progress = 1
        db.commit()

        # ── STAGE 2: Identity & KYC Profiling ────────────────────────────────
        logger.info(f"[App {application_id}] Running Stage 2: KYC Profiling")
        stage2_res = await run_stage2(application_data, db)
        all_stage_results["stage2"] = stage2_res
        application.pipeline_progress = 2
        db.commit()

        # ── STAGE 3: Cash Flow Analysis (Nemotron Small) ──────────────────────
        logger.info(f"[App {application_id}] Running Stage 3: Cash Flow Analysis")
        stage3_res = await run_stage3(application_data, db, llm_logger)
        all_stage_results["stage3"] = stage3_res
        application.pipeline_progress = 3
        db.commit()

        # ── STAGE 4: Financial Health Scoring ────────────────────────────────
        logger.info(f"[App {application_id}] Running Stage 4: Health Scoring")
        stage4_res = await run_stage4(application_data, stage3_res)
        all_stage_results["stage4"] = stage4_res
        application.pipeline_progress = 4
        db.commit()

        # ── STAGE 5: Fraud Detection (Nemotron Large) ─────────────────────────
        logger.info(f"[App {application_id}] Running Stage 5: Fraud Detection")
        stage5_res = await run_stage5(application_data, stage2_res, stage3_res, llm_logger)
        all_stage_results["stage5"] = stage5_res
        application.pipeline_progress = 5
        db.commit()

        # ── STAGE 6: Policy Matching & Business Rules ─────────────────────────
        logger.info(f"[App {application_id}] Running Stage 6: Policy Matching")
        stage6_res = await run_stage6(application_data, stage4_res)
        all_stage_results["stage6"] = stage6_res
        application.pipeline_progress = 6
        db.commit()

        # ── STAGE 7: Affordability Check ──────────────────────────────────────
        logger.info(f"[App {application_id}] Running Stage 7: Affordability")
        stage7_res = await run_stage7(application_data, stage3_res, stage4_res)
        all_stage_results["stage7"] = stage7_res
        application.pipeline_progress = 7
        db.commit()

        # ── STAGE 8: AI Decision Engine (Nemotron Large) ──────────────────────
        logger.info(f"[App {application_id}] Running Stage 8: Decision Engine")
        stage8_res = await run_stage8(application_data, all_stage_results, llm_logger)
        all_stage_results["stage8"] = stage8_res
        application.pipeline_progress = 8

        # ── Create/update UnderwritingReport ──────────────────────────────────
        report = db.query(UnderwritingReport).filter(
            UnderwritingReport.application_id == application_id
        ).first()
        if not report:
            report = UnderwritingReport(application_id=application_id)
            db.add(report)

        report.stage_results = all_stage_results
        report.decision = stage8_res.get("decision", "REVIEW")
        report.health_score = float(stage4_res.get("health_score", 0.0))
        report.fraud_score = float(stage5_res.get("fraud_score", 0.0))
        report.risk_score = 100.0 - float(stage4_res.get("health_score", 50.0))
        report.affordability_score = float(stage7_res.get("affordability_score", 0.0))
        report.max_emi = float(stage7_res.get("max_emi", 0.0))
        report.policy_violations = stage6_res.get("violations", [])
        report.cash_flow_analysis = stage3_res.get("cashflow_analysis", {})
        report.kyc_status = stage2_res.get("kyc_status", "PENDING")
        report.recommended_rate = float(stage8_res.get("recommended_rate", 0.0))
        report.recommended_tenure = int(stage8_res.get("recommended_tenure", application_data.get("tenure_months", 24)))
        report.confidence_score = float(stage8_res.get("confidence_score", 0.0))
        report.reasoning = str(stage8_res.get("reasoning", ""))
        # Radar chart sub-scores
        report.income_stability_score = float(stage4_res.get("income_stability_score", 50.0))
        report.expense_management_score = float(stage4_res.get("expense_management_score", 50.0))
        report.debt_management_score = float(stage4_res.get("debt_management_score", 50.0))
        report.credit_history_score = float(stage4_res.get("credit_history_score", 50.0))
        report.fraud_risk_score = max(0.0, 100.0 - float(stage5_res.get("fraud_score", 0.0)))

        # Set final application status
        final_decision = stage8_res.get("decision", "REVIEW")
        # Validate decision value
        if final_decision not in ("APPROVED", "REVIEW", "REJECTED"):
            final_decision = "REVIEW"
        application.status = final_decision
        db.commit()
        db.refresh(report)

        logger.info(f"[App {application_id}] Pipeline complete. Decision: {final_decision}")
        return all_stage_results

    except Exception as e:
        logger.error(f"Pipeline failed for application {application_id}: {e}", exc_info=True)
        if application is not None:
            try:
                application.status = "REVIEW"
                application.error_message = str(e)[:500]
                # Save partial results if any
                if all_stage_results:
                    report = db.query(UnderwritingReport).filter(
                        UnderwritingReport.application_id == application_id
                    ).first()
                    if not report:
                        report = UnderwritingReport(application_id=application_id)
                        db.add(report)
                    report.stage_results = all_stage_results
                    report.decision = "REVIEW"
                db.commit()
            except Exception as commit_err:
                logger.error(f"Failed to save error state: {commit_err}")
                db.rollback()

        return {"error": str(e), "partial_results": all_stage_results}
