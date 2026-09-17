import json
import logging
import re
import time
from app.config import settings
from app.observability.logger import LLMLogger
from openai import OpenAI

logger = logging.getLogger(__name__)
client = OpenAI(api_key=settings.NVIDIA_API_KEY, base_url=settings.NVIDIA_BASE_URL)


def _parse_json(text: str, fallback: dict) -> dict:
    """Extract JSON from LLM response with multiple fallback strategies."""
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r'```json\s*([\s\S]*?)```', text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    s, e = text.find('{'), text.rfind('}')
    if s != -1 and e != -1:
        try:
            return json.loads(text[s:e + 1])
        except Exception:
            pass
    return fallback


async def run_stage5(
    application_data: dict,
    stage2_result: dict,
    stage3_result: dict,
    llm_logger: LLMLogger,
) -> dict:
    """
    Stage 5: Fraud Detection & Anomaly Analysis
    - Use Nemotron Large to detect unusual patterns
    - Check for synthetic identity signals
    Returns: {fraud_score, anomalies_detected, risk_flags, synthetic_identity_probability,
              income_consistency_flag, document_authenticity_score, recommendation}
    """
    fallback = {
        "fraud_score": 10.0,
        "synthetic_identity_probability": 5.0,
        "anomalies_detected": [],
        "income_consistency_flag": "CONSISTENT",
        "document_authenticity_score": 90.0,
        "risk_flags": [],
        "recommendation": "PROCEED",
        "explanation": "Rule-based fallback applied.",
    }

    system_prompt = (
        "You are a senior fraud detection analyst at a financial institution. "
        "Analyze the applicant's KYC and cash-flow data for fraud indicators including: "
        "income inflation, address inconsistency, transaction velocity anomalies, "
        "round-number declared salaries with no corresponding bank credits, PEP flags, "
        "and synthetic identity signals. Return ONLY valid JSON with no additional text."
    )

    user_prompt = f"""Applicant Profile:
- Name: {application_data.get('full_name')}
- PAN: {application_data.get('pan_number')}
- Employment: {application_data.get('employment_type')} at {application_data.get('employer_name')}
- Declared Income: ₹{application_data.get('monthly_income', 0):,.0f}/month
- Declared Expenses: ₹{application_data.get('monthly_expenses', 0):,.0f}/month
- Credit Score: {application_data.get('credit_score')}

KYC Results:
- KYC Status: {stage2_result.get('kyc_status')}
- Name Match Score: {stage2_result.get('kyc_result', {}).get('name_match_score', 'N/A')}
- PEP Flag: {stage2_result.get('kyc_result', {}).get('politically_exposed_person', False)}
- Risk Category: {stage2_result.get('kyc_result', {}).get('risk_category', 'N/A')}
- Identity Risk Flags: {stage2_result.get('risk_flags', [])}
- Income Match Score: {stage2_result.get('income_verification', {}).get('income_match_score', 'N/A')}

Cash Flow Analysis:
- Avg Monthly Income (bank): ₹{stage3_result.get('avg_monthly_income', 0):,.0f}
- Avg Monthly Expenses (bank): ₹{stage3_result.get('avg_monthly_expenses', 0):,.0f}
- Income Stability Score: {stage3_result.get('income_stability_score', 50)}/100
- Risk Indicators: {stage3_result.get('risk_indicators', [])}

Return ONLY this JSON:
{{
  "fraud_score": <float 0-100>,
  "synthetic_identity_probability": <float 0-100>,
  "anomalies_detected": [{{"type": "<string>", "severity": "HIGH|MEDIUM|LOW", "description": "<string>"}}],
  "income_consistency_flag": "CONSISTENT|INCONSISTENT|SUSPICIOUS",
  "document_authenticity_score": <float 0-100>,
  "risk_flags": ["<string>"],
  "recommendation": "PROCEED|REVIEW|REJECT_FRAUD",
  "explanation": "<paragraph>"
}}"""

    model = settings.NVIDIA_LARGE_MODEL
    start_time = time.time()
    validation_status = "SUCCESS"
    text = ""
    in_tok = 0
    out_tok = 0
    result = fallback.copy()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        text = response.choices[0].message.content or ""
        in_tok = response.usage.prompt_tokens if response.usage else 0
        out_tok = response.usage.completion_tokens if response.usage else 0

        parsed = _parse_json(text, fallback)
        if "fraud_score" in parsed:
            result = parsed
        else:
            result = fallback.copy()
            validation_status = "RECOVERED"

    except Exception as e:
        logger.warning(f"Stage 5 LLM call failed: {e}. Using rule-based fallback.")
        validation_status = "FAILED"
        # Rule-based fallback: check KYC flags
        kyc_flags = stage2_result.get("risk_flags", [])
        inc_match = stage2_result.get("income_verification", {}).get("income_match_score", 80)
        if len(kyc_flags) >= 3 or inc_match < 50:
            result["fraud_score"] = 55.0
            result["recommendation"] = "REVIEW"
            result["risk_flags"] = kyc_flags

    latency_ms = (time.time() - start_time) * 1000

    # Enforce recommendation based on fraud_score
    fraud_score = float(result.get("fraud_score", 0.0))
    if fraud_score > 70:
        result["recommendation"] = "REJECT_FRAUD"
    elif fraud_score >= 40:
        result["recommendation"] = "REVIEW"
    else:
        result["recommendation"] = "PROCEED"

    # Observability logging
    try:
        await llm_logger.log_simple(
            stage_name="stage5_fraud_detection",
            model_id=model,
            latency_ms=latency_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            validation_status=validation_status,
            prompt_template="fraud_detection_v1",
            prompt_version="1.0",
            prompt_preview=user_prompt[:500],
            response_preview=text[:500],
        )
    except Exception as log_err:
        logger.warning(f"Failed to log stage5 observability: {log_err}")

    return result
