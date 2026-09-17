import json
import logging
import re
import time
from pydantic import BaseModel, ValidationError
from app.config import settings
from app.observability.logger import LLMLogger
from openai import OpenAI

logger = logging.getLogger(__name__)
client = OpenAI(api_key=settings.NVIDIA_API_KEY, base_url=settings.NVIDIA_BASE_URL)


def parse_json_response(text: str, fallback: dict) -> dict:
    """Extract JSON from LLM response with multiple fallback strategies."""
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r'```json\s*([\s\S]*?)```', text)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    if start_idx != -1 and end_idx != -1:
        try:
            return json.loads(text[start_idx:end_idx + 1])
        except Exception:
            pass
    return fallback


class DecisionOutput(BaseModel):
    decision: str  # APPROVED, REVIEW, or REJECTED
    recommended_rate: float  # annual interest rate %
    recommended_tenure: int  # months
    confidence_score: float  # 0-100
    reasoning: str
    conditions: list[str]
    risk_summary: str
    terms_offered: dict


def _get_rule_based_decision(
    stage4: dict, stage5: dict, stage6: dict, application_data: dict
) -> DecisionOutput:
    """Deterministic fallback decision when LLM is unavailable."""
    health_score = float(stage4.get("health_score", 50.0))
    fraud_score = float(stage5.get("fraud_score", 0.0))
    compliance_score = float(stage6.get("compliance_score", 50.0))
    risk_tier = str(stage4.get("risk_tier", "FAIR"))
    tenure = int(application_data.get("tenure_months", 24))

    # Determine interest rate from risk tier
    rate_map = {
        "EXCELLENT": 9.0,
        "GOOD": 11.5,
        "FAIR": 14.5,
        "POOR": 19.0,
        "CRITICAL": 0.0,
    }
    rate = rate_map.get(risk_tier, 14.5)

    # Rule-based decision
    critical_violations = [
        v for v in stage6.get("violations", [])
        if v.get("severity") == "CRITICAL"
    ]

    if fraud_score > 70 or risk_tier == "CRITICAL" or len(critical_violations) > 0:
        decision = "REJECTED"
        rate = 0.0
        conditions = ["Application rejected due to high risk indicators."]
        reasoning = (
            f"Application rejected based on rule-based analysis. "
            f"Fraud Score: {fraud_score:.0f}/100. "
            f"Risk Tier: {risk_tier}. "
            f"Critical Policy Violations: {len(critical_violations)}."
        )
    elif health_score > 70 and fraud_score < 30 and compliance_score > 70:
        decision = "APPROVED"
        conditions = [
            "Maintain existing income level throughout loan tenure.",
            "Report any change in employment status within 30 days.",
        ]
        reasoning = (
            f"Application approved based on strong financial profile. "
            f"Health Score: {health_score:.0f}/100. "
            f"Fraud Risk: Low ({fraud_score:.0f}/100). "
            f"Policy Compliance: {compliance_score:.0f}/100."
        )
    else:
        decision = "REVIEW"
        conditions = ["Manual review required for final approval."]
        reasoning = (
            f"Application requires manual review. "
            f"Health Score: {health_score:.0f}/100. "
            f"Fraud Score: {fraud_score:.0f}/100. "
            f"Compliance Score: {compliance_score:.0f}/100."
        )

    loan_amount = float(application_data.get("loan_amount", 0))
    return DecisionOutput(
        decision=decision,
        recommended_rate=rate,
        recommended_tenure=tenure,
        confidence_score=75.0,
        reasoning=reasoning,
        conditions=conditions,
        risk_summary=f"Risk Tier: {risk_tier} | Health: {health_score:.0f} | Fraud: {fraud_score:.0f}",
        terms_offered={
            "max_loan_amount": loan_amount,
            "annual_interest_rate_pct": rate,
            "processing_fee_pct": 1.5,
            "tenure_months": tenure,
            "prepayment_penalty_pct": 2.0,
        },
    )


async def run_stage8(
    application_data: dict, all_stage_results: dict, llm_logger: LLMLogger
) -> dict:
    """
    Stage 8: AI Recommendation & Decision Engine
    - Use Nemotron Large to synthesize all stage results
    - Generate final decision with terms
    Returns: {decision, recommended_rate, recommended_tenure, confidence_score,
              reasoning, conditions, risk_summary, terms_offered}
    """
    stage4 = all_stage_results.get("stage4", {})
    stage5 = all_stage_results.get("stage5", {})
    stage6 = all_stage_results.get("stage6", {})
    stage7 = all_stage_results.get("stage7", {})

    # Build comprehensive summary for LLM
    summary = {
        "loan_request": {
            "amount": application_data.get("loan_amount"),
            "purpose": application_data.get("loan_purpose"),
            "tenure_months": application_data.get("tenure_months"),
        },
        "applicant": {
            "name": application_data.get("full_name"),
            "employment": application_data.get("employment_type"),
            "income_monthly": application_data.get("monthly_income"),
            "expenses_monthly": application_data.get("monthly_expenses"),
            "credit_score": application_data.get("credit_score"),
        },
        "health_score": stage4.get("health_score"),
        "risk_tier": stage4.get("risk_tier"),
        "dti_ratio": stage4.get("dti_ratio"),
        "fraud_score": stage5.get("fraud_score"),
        "fraud_recommendation": stage5.get("recommendation"),
        "fraud_anomalies": stage5.get("anomalies_detected", []),
        "compliance_score": stage6.get("compliance_score"),
        "critical_violations": [
            v for v in stage6.get("violations", []) if v.get("severity") == "CRITICAL"
        ],
        "affordability_score": stage7.get("affordability_score"),
        "max_emi": stage7.get("max_emi"),
        "requested_emi": stage7.get("requested_emi"),
        "repayment_capacity_ratio": stage7.get("repayment_capacity_ratio"),
        "kyc_status": all_stage_results.get("stage2", {}).get("kyc_status"),
    }

    system_prompt = (
        "You are the final AI Loan Decision Engine for a regulated financial institution. "
        "Review the complete underwriting analysis and issue a final decision. "
        "You MUST return ONLY a valid JSON object. The decision field MUST be exactly one of: "
        "APPROVED, REVIEW, or REJECTED (uppercase). "
        "Interest rates should be between 8.0 and 24.0%. Never recommend approval for high-fraud applications."
    )

    user_prompt = f"""Complete Underwriting Analysis Summary:
{json.dumps(summary, indent=2, default=str)}

Based on this analysis, provide your final underwriting decision as a JSON object:
{{
  "decision": "APPROVED" | "REVIEW" | "REJECTED",
  "recommended_rate": <annual_interest_rate_float_8_to_24>,
  "recommended_tenure": <months_integer>,
  "confidence_score": <float_0_to_100>,
  "reasoning": "<2-3 paragraph detailed reasoning>",
  "conditions": ["<condition1>", "<condition2>"],
  "risk_summary": "<one paragraph risk summary>",
  "terms_offered": {{
    "max_loan_amount": <float>,
    "annual_interest_rate_pct": <float>,
    "processing_fee_pct": <float>,
    "tenure_months": <int>,
    "prepayment_penalty_pct": <float>
  }}
}}"""

    model = settings.NVIDIA_LARGE_MODEL
    start_time = time.time()
    validation_status = "SUCCESS"
    text = ""
    in_tok = 0
    out_tok = 0
    decision_obj: DecisionOutput | None = None

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=2048,
        )
        text = response.choices[0].message.content or ""
        in_tok = response.usage.prompt_tokens if response.usage else 0
        out_tok = response.usage.completion_tokens if response.usage else 0

        raw = parse_json_response(text, {})
        if not raw:
            raise ValueError("Empty JSON from LLM")

        # Enforce valid decision
        if raw.get("decision") not in ("APPROVED", "REVIEW", "REJECTED"):
            raw["decision"] = "REVIEW"
            validation_status = "RECOVERED"

        # Clamp rate
        rate = float(raw.get("recommended_rate", 12.0))
        raw["recommended_rate"] = max(8.0, min(24.0, rate))

        decision_obj = DecisionOutput(**raw)

    except (ValidationError, Exception) as e:
        logger.warning(f"Stage 8 LLM failed: {e}. Using rule-based fallback.")
        decision_obj = _get_rule_based_decision(stage4, stage5, stage6, application_data)
        validation_status = "FAILED" if not text else "RECOVERED"

    latency_ms = (time.time() - start_time) * 1000

    # Log to observability
    try:
        await llm_logger.log_simple(
            stage_name="stage8_decision",
            model_id=model,
            latency_ms=latency_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            validation_status=validation_status,
            confidence_score=decision_obj.confidence_score,
            decision=decision_obj.decision,
            prompt_template="final_decision_v1",
            prompt_version="1.0",
            prompt_preview=user_prompt[:500],
            response_preview=text[:500],
        )
    except Exception as log_err:
        logger.warning(f"Failed to log stage8 observability: {log_err}")

    return decision_obj.model_dump()
