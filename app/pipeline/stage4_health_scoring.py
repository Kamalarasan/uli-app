import logging

logger = logging.getLogger(__name__)


def _dti_ratio_score(dti: float) -> float:
    """Map DTI ratio to score: 0-30% → 100, ≥60% → 0."""
    if dti <= 30:
        return 100.0
    elif dti >= 60:
        return 0.0
    else:
        return 100.0 - ((dti - 30.0) * (100.0 / 30.0))


async def run_stage4(application_data: dict, stage3_result: dict) -> dict:
    """
    Stage 4: Financial Health Scoring
    - Calculate Debt-to-Income ratio
    - Assess savings consistency
    - Calculate stability scores
    Returns: {health_score, dti_ratio, savings_consistency_score, stability_score,
              income_stability_score, expense_management_score, debt_management_score,
              credit_history_score, risk_tier, score_breakdown, proposed_emi}
    """
    loan_amount = float(application_data.get("loan_amount", 0))
    monthly_income = max(float(application_data.get("monthly_income", 1)), 1.0)  # avoid div/0
    existing_emi = float(application_data.get("existing_emi", 0.0))
    tenure_months = max(int(application_data.get("tenure_months", 12)), 1)
    credit_score = max(300.0, min(900.0, float(application_data.get("credit_score", 650))))

    # ── Proposed EMI (Reducing Balance at 12% base rate) ─────────
    annual_base_rate = float(application_data.get("base_interest_rate", 0.12))
    monthly_rate = annual_base_rate / 12.0

    if monthly_rate > 0 and tenure_months > 0 and loan_amount > 0:
        proposed_emi = (
            loan_amount
            * monthly_rate
            * ((1 + monthly_rate) ** tenure_months)
            / (((1 + monthly_rate) ** tenure_months) - 1)
        )
    else:
        proposed_emi = loan_amount / tenure_months if tenure_months > 0 else 0.0

    # ── DTI Ratio ─────────────────────────────────────────────────
    total_emi = existing_emi + proposed_emi
    dti_ratio = (total_emi / monthly_income) * 100.0

    # ── Savings Consistency ───────────────────────────────────────
    cf_analysis = stage3_result.get("cashflow_analysis", {})
    savings_rate = float(cf_analysis.get("savings_rate", stage3_result.get("savings_rate", 0.1)))
    # 20% savings rate → 100 score; 0% → 0
    savings_consistency_score = min(100.0, max(0.0, savings_rate * 500.0))

    # ── Income Stability (from stage3) ────────────────────────────
    income_stability_score = float(stage3_result.get("income_stability_score", 50.0))

    # ── Expense Management Score ──────────────────────────────────
    volatility = float(stage3_result.get("volatility_score", 50.0))
    expense_management_score = max(0.0, min(100.0, 100.0 - volatility * 0.5 - dti_ratio * 0.5))

    # ── Debt Management Score ─────────────────────────────────────
    existing_emi_ratio = (existing_emi / monthly_income) * 100.0  # pct
    credit_penalty = max(0.0, (750.0 - credit_score) / 4.5)
    debt_management_score = max(0.0, min(100.0, 100.0 - existing_emi_ratio - credit_penalty))

    # ── Credit History Score (map 300-900 → 0-100) ────────────────
    credit_history_score = max(0.0, min(100.0, (credit_score - 300.0) / 6.0))

    # ── Stability Score ───────────────────────────────────────────
    stability_score = (income_stability_score + savings_consistency_score + expense_management_score) / 3.0

    # ── Composite Health Score (weighted) ────────────────────────
    dti_score = _dti_ratio_score(dti_ratio)
    health_score = (
        0.30 * dti_score
        + 0.20 * savings_consistency_score
        + 0.20 * income_stability_score
        + 0.15 * credit_history_score
        + 0.15 * debt_management_score
    )
    health_score = max(0.0, min(100.0, health_score))

    # ── Risk Tier ─────────────────────────────────────────────────
    if health_score >= 85:
        risk_tier = "EXCELLENT"
    elif health_score >= 70:
        risk_tier = "GOOD"
    elif health_score >= 50:
        risk_tier = "FAIR"
    elif health_score >= 30:
        risk_tier = "POOR"
    else:
        risk_tier = "CRITICAL"

    return {
        "health_score": round(health_score, 2),
        "dti_ratio": round(dti_ratio, 2),
        "proposed_emi": round(proposed_emi, 2),
        "savings_consistency_score": round(savings_consistency_score, 2),
        "stability_score": round(stability_score, 2),
        "income_stability_score": round(income_stability_score, 2),
        "expense_management_score": round(expense_management_score, 2),
        "debt_management_score": round(debt_management_score, 2),
        "credit_history_score": round(credit_history_score, 2),
        "risk_tier": risk_tier,
        "score_breakdown": {
            "dti_score": round(dti_score, 2),
            "savings_score": round(savings_consistency_score, 2),
            "income_stability": round(income_stability_score, 2),
            "credit_history": round(credit_history_score, 2),
            "debt_management": round(debt_management_score, 2),
        },
    }
