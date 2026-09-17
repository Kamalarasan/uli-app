import logging
from sqlalchemy.orm import Session
from app.models.orm import LoanApplication, Applicant, UnderwritingReport, DigitalTwinScenario
from app.pipeline.stage4_health_scoring import run_stage4
from app.pipeline.stage7_affordability import run_stage7

logger = logging.getLogger(__name__)


async def run_simulation(
    base_application_id: int,
    scenario_name: str,
    salary_change_pct: float,       # e.g. -20.0 means 20% salary cut
    expense_inflation_pct: float,   # e.g. 15.0 means 15% expense increase
    rate_shift_bps: float,          # e.g. 200 means +2% interest rate
    tenure_change_months: int,      # e.g. -12 means 12 months shorter
    economic_condition: str,        # NORMAL, DOWNTURN, BOOM
    db: Session,
) -> dict:
    """
    Run a what-if simulation on a base loan application.
    Returns comparison metrics between base and simulated scenarios.
    """
    # ── Load base application & report ───────────────────────────
    base_app = db.query(LoanApplication).filter(
        LoanApplication.id == base_application_id
    ).first()
    if not base_app:
        raise ValueError(f"Base application {base_application_id} not found")

    base_report = db.query(UnderwritingReport).filter(
        UnderwritingReport.application_id == base_application_id
    ).first()
    if not base_report:
        raise ValueError(f"No underwriting report found for application {base_application_id}. Run the pipeline first.")

    # ── Apply scenario parameter adjustments ─────────────────────
    mod_income = float(base_app.monthly_income or 0) * (1 + salary_change_pct / 100.0)
    mod_expenses = float(base_app.monthly_expenses or 0) * (1 + expense_inflation_pct / 100.0)
    base_rate_pct = float(base_report.recommended_rate or 12.0)
    mod_rate = base_rate_pct + (rate_shift_bps / 100.0)
    mod_tenure = int(base_app.tenure_months or 24) + tenure_change_months

    # Apply macro-economic condition multipliers
    if economic_condition == "DOWNTURN":
        mod_income *= 0.90
        mod_expenses *= 1.20
        mod_rate += 1.50
    elif economic_condition == "BOOM":
        mod_income *= 1.05
        mod_expenses *= 0.95
        mod_rate -= 0.50

    # Enforce bounds
    mod_tenure = max(12, min(360, mod_tenure))
    mod_rate = max(5.0, min(30.0, mod_rate))
    mod_income = max(1.0, mod_income)
    mod_expenses = max(0.0, mod_expenses)

    # ── Build simulated application data dict ────────────────────
    app_data = {
        "application_id": base_application_id,
        "loan_amount": float(base_app.loan_amount or 0),
        "monthly_income": mod_income,
        "monthly_expenses": mod_expenses,
        "existing_emi": float(base_app.existing_emi or 0),
        "tenure_months": mod_tenure,
        "credit_score": base_app.credit_score or 650,
        "base_interest_rate": mod_rate / 100.0,  # as decimal for EMI calc
        "loan_purpose": base_app.loan_purpose or "PERSONAL",
        "employment_type": base_app.applicant.employment_type if base_app.applicant else "SALARIED",
        "full_name": base_app.applicant.full_name if base_app.applicant else "Applicant",
    }

    # Minimal stage3-like result for stage4 scoring
    net_disposable = mod_income - mod_expenses
    savings_rate = max(0.0, net_disposable / mod_income) if mod_income > 0 else 0.0
    mock_stage3 = {
        "cashflow_analysis": {
            "savings_rate": savings_rate,
            "avg_monthly_income": mod_income,
            "avg_monthly_expenses": mod_expenses,
        },
        "income_stability_score": 65.0,  # conservative assumption
        "volatility_score": 35.0,
        "savings_rate": savings_rate,
        "net_disposable_income": net_disposable,
    }

    # ── Run stage 4 & 7 on simulated data ────────────────────────
    try:
        stage4_res = await run_stage4(app_data, mock_stage3)
    except Exception as e:
        logger.warning(f"Stage 4 simulation failed: {e}")
        stage4_res = {"health_score": 50.0, "dti_ratio": 40.0, "risk_tier": "FAIR", "proposed_emi": 0.0}

    try:
        stage7_res = await run_stage7(app_data, mock_stage3, stage4_res)
    except Exception as e:
        logger.warning(f"Stage 7 simulation failed: {e}")
        stage7_res = {"affordability_score": 50.0, "max_emi": mod_income * 0.4, "dti_ratio": 40.0}

    # ── Compute simulation metrics ────────────────────────────────
    sim_health = float(stage4_res.get("health_score", 50.0))
    sim_affordability = float(stage7_res.get("affordability_score", 50.0))
    sim_dti = float(stage4_res.get("dti_ratio", stage7_res.get("dti_ratio", 40.0)))
    sim_max_emi = float(stage7_res.get("max_emi", mod_income * 0.4))
    sim_approval_prob = min(100.0, max(0.0, (sim_health * 0.6 + sim_affordability * 0.4)))
    sim_risk = max(0.0, 100.0 - sim_health)
    sim_default_rate = max(0.0, min(100.0, (sim_dti / 40.0) * (100.0 - sim_health) / 50.0))

    simulated_metrics = {
        "health_score": round(sim_health, 2),
        "affordability_score": round(sim_affordability, 2),
        "max_emi": round(sim_max_emi, 2),
        "dti_ratio": round(sim_dti, 2),
        "approval_probability": round(sim_approval_prob, 2),
        "risk_score": round(sim_risk, 2),
        "estimated_default_rate": round(sim_default_rate, 2),
        "modified_income": round(mod_income, 2),
        "modified_expenses": round(mod_expenses, 2),
        "modified_rate": round(mod_rate, 2),
        "modified_tenure": mod_tenure,
    }

    # ── Build base metrics from existing report ───────────────────
    base_health = float(base_report.health_score or 50.0)
    base_affordability = float(base_report.affordability_score or 50.0)
    base_max_emi = float(base_report.max_emi or 0.0)
    base_risk = float(base_report.risk_score or 50.0)
    base_approval_prob = min(100.0, max(0.0, base_health * 0.6 + base_affordability * 0.4))

    base_metrics = {
        "health_score": round(base_health, 2),
        "affordability_score": round(base_affordability, 2),
        "max_emi": round(base_max_emi, 2),
        "dti_ratio": round(
            (base_report.cash_flow_analysis or {}).get("dti_ratio", 40.0), 2
        ) if base_report.cash_flow_analysis else 40.0,
        "approval_probability": round(base_approval_prob, 2),
        "risk_score": round(base_risk, 2),
        "estimated_default_rate": round(base_risk / 100.0 * 15.0, 2),
    }

    # ── Comparison deltas ─────────────────────────────────────────
    delta_health = simulated_metrics["health_score"] - base_metrics["health_score"]
    delta_approval = simulated_metrics["approval_probability"] - base_metrics["approval_probability"]
    comparison = {
        "delta_health_score": round(delta_health, 2),
        "delta_affordability": round(simulated_metrics["affordability_score"] - base_metrics["affordability_score"], 2),
        "delta_max_emi": round(simulated_metrics["max_emi"] - base_metrics["max_emi"], 2),
        "delta_approval_probability": round(delta_approval, 2),
        "recommendation": (
            "Positive Impact — scenario improves approval likelihood." if delta_approval > 0
            else "Negative Impact — scenario reduces approval likelihood." if delta_approval < -5
            else "Neutral Impact — minimal change in approval likelihood."
        ),
    }

    # ── Fairness metrics (income group proxy) ────────────────────
    income = mod_income
    if income < 30000:
        income_group = "Low Income"
    elif income < 80000:
        income_group = "Middle Income"
    else:
        income_group = "High Income"

    fairness_metrics = {
        "income_group": income_group,
        "risk_percentile": round(sim_risk, 1),
        "income_band": f"₹{income/1000:.0f}k/month",
        "relative_default_risk": "HIGH" if sim_default_rate > 10 else "MEDIUM" if sim_default_rate > 5 else "LOW",
    }

    # ── Persist scenario to DB ────────────────────────────────────
    scenario_params = {
        "salary_change_pct": salary_change_pct,
        "expense_inflation_pct": expense_inflation_pct,
        "rate_shift_bps": rate_shift_bps,
        "tenure_change_months": tenure_change_months,
        "economic_condition": economic_condition,
    }
    simulation_results = {
        "simulated_metrics": simulated_metrics,
        "comparison": comparison,
        "fairness_metrics": fairness_metrics,
    }

    scenario = DigitalTwinScenario(
        base_application_id=base_application_id,
        scenario_name=scenario_name,
        scenario_params=scenario_params,
        simulation_results=simulation_results,
        approval_probability=simulated_metrics["approval_probability"],
        avg_risk_score=simulated_metrics["risk_score"],
        estimated_default_rate=simulated_metrics["estimated_default_rate"],
        fairness_metrics=fairness_metrics,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)

    return {
        "scenario_id": scenario.id,
        "scenario_name": scenario_name,
        "scenario_params": scenario_params,
        "base_metrics": base_metrics,
        "simulated_metrics": simulated_metrics,
        "comparison": comparison,
        "fairness_metrics": fairness_metrics,
    }
