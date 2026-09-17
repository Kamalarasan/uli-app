import json
import logging
import re
import time
from sqlalchemy.orm import Session
from app.config import settings
from app.observability.logger import LLMLogger
from app.connectors.account_aggregator import fetch_bank_statement
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


async def run_stage3(application_data: dict, db: Session, llm_logger: LLMLogger) -> dict:
    """
    Stage 3: Cash Flow Analysis
    - Fetch 12-month bank statement via Account Aggregator connector
    - Use Nemotron Small to analyze income vs expenses
    - Calculate net disposable income
    Returns: {bank_statement_summary, cashflow_analysis, net_disposable_income,
              income_stability_score, expense_categories, volatility_score}
    """
    monthly_income = application_data.get("monthly_income", 0.0)
    monthly_expenses = application_data.get("monthly_expenses", 0.0)
    applicant_id = application_data.get("applicant_id", 0)

    # Fetch 12-month bank statement from Account Aggregator connector
    try:
        bank_data = await fetch_bank_statement(
            applicant_id=applicant_id,
            monthly_income=monthly_income,
            monthly_expenses=monthly_expenses,
        )
        summary = bank_data.get("summary", {})
        bank_statement_text = (
            f"Bank: {bank_data.get('bank_name', 'N/A')} | Account: {bank_data.get('account_number', 'N/A')}\n"
            f"12-Month Summary:\n"
            f"  Avg Monthly Income: ₹{summary.get('avg_monthly_income', monthly_income):,.0f}\n"
            f"  Avg Monthly Expenses: ₹{summary.get('avg_monthly_expenses', monthly_expenses):,.0f}\n"
            f"  Avg Savings Rate: {summary.get('avg_savings_rate', 0):.1%}\n"
            f"  Income Consistency Score: {summary.get('income_consistency_score', 50)}/100\n"
            f"  Min Balance: ₹{summary.get('min_balance', 0):,.0f}\n"
            f"  Max Balance: ₹{summary.get('max_balance', 0):,.0f}\n"
            f"  Bounce Count (12m): {summary.get('bounce_count', 0)}\n"
        )
        # Add monthly breakdown
        transactions = bank_data.get("transactions", [])
        if transactions:
            bank_statement_text += "\nMonthly Breakdown:\n"
            for month in transactions[:6]:  # limit to 6 months for prompt length
                bank_statement_text += (
                    f"  {month.get('month_name', '')}: "
                    f"Credits ₹{month.get('total_credits', 0):,.0f} | "
                    f"Debits ₹{month.get('total_debits', 0):,.0f} | "
                    f"Closing ₹{month.get('closing_balance', 0):,.0f}\n"
                )
    except Exception as e:
        logger.warning(f"Failed to fetch bank statement: {e}. Using declared income/expenses.")
        bank_statement_text = (
            f"Declared Monthly Income: ₹{monthly_income:,.0f}\n"
            f"Declared Monthly Expenses: ₹{monthly_expenses:,.0f}\n"
            f"Net Disposable: ₹{monthly_income - monthly_expenses:,.0f}\n"
            f"Note: Bank statement unavailable - using applicant-declared figures."
        )
        summary = {}

    # Build LLM prompts
    system_prompt = (
        "You are a financial analyst specializing in loan underwriting. "
        "Analyze the provided 12-month bank statement data and provide structured cash flow insights. "
        "Always respond in valid JSON only with no additional commentary."
    )
    user_prompt = f"""Applicant Financial Profile:
- Declared Monthly Income: ₹{monthly_income:,.0f}
- Declared Monthly Expenses: ₹{monthly_expenses:,.0f}
- Employment Type: {application_data.get('employment_type', 'SALARIED')}
- Employer: {application_data.get('employer_name', 'N/A')}

Bank Statement Data (12 months):
{bank_statement_text}

Analyze the cash flow and return ONLY a JSON object with this exact schema:
{{
  "avg_monthly_income": <float>,
  "avg_monthly_expenses": <float>,
  "net_disposable_income": <float>,
  "income_stability_score": <integer 0-100>,
  "expense_volatility_score": <integer 0-100>,
  "top_expense_categories": [
    {{"category": "<string>", "monthly_avg": <float>, "pct_of_expenses": <float>}}
  ],
  "income_sources": [
    {{"source": "<string>", "monthly_avg": <float>}}
  ],
  "savings_rate": <float 0-1>,
  "key_observations": ["<string>"],
  "risk_indicators": ["<string>"]
}}"""

    fallback_income = summary.get("avg_monthly_income", monthly_income)
    fallback_expenses = summary.get("avg_monthly_expenses", monthly_expenses)
    fallback = {
        "avg_monthly_income": fallback_income,
        "avg_monthly_expenses": fallback_expenses,
        "net_disposable_income": fallback_income - fallback_expenses,
        "income_stability_score": int(summary.get("income_consistency_score", 50)),
        "expense_volatility_score": 40,
        "top_expense_categories": [
            {"category": "RENT", "monthly_avg": fallback_expenses * 0.35, "pct_of_expenses": 35.0},
            {"category": "FOOD", "monthly_avg": fallback_expenses * 0.20, "pct_of_expenses": 20.0},
            {"category": "UTILITIES", "monthly_avg": fallback_expenses * 0.10, "pct_of_expenses": 10.0},
        ],
        "income_sources": [{"source": "SALARY", "monthly_avg": fallback_income}],
        "savings_rate": max(0.0, (fallback_income - fallback_expenses) / fallback_income) if fallback_income > 0 else 0.0,
        "key_observations": ["Analysis based on declared figures due to LLM unavailability."],
        "risk_indicators": [],
    }

    model = settings.NVIDIA_SMALL_MODEL
    start_time = time.time()
    validation_status = "SUCCESS"
    text = ""
    in_tok = 0
    out_tok = 0

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
        cashflow_analysis = parse_json_response(text, fallback)
        # Validate required keys
        if "avg_monthly_income" not in cashflow_analysis:
            cashflow_analysis = fallback
            validation_status = "RECOVERED"
    except Exception as e:
        logger.warning(f"Stage 3 LLM call failed: {e}. Using fallback.")
        cashflow_analysis = fallback
        validation_status = "FAILED"

    latency_ms = (time.time() - start_time) * 1000

    # Log to observability
    try:
        await llm_logger.log_simple(
            stage_name="stage3_cashflow",
            model_id=model,
            latency_ms=latency_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            validation_status=validation_status,
            prompt_template="cashflow_analysis_v1",
            prompt_version="1.0",
            prompt_preview=user_prompt[:500],
            response_preview=text[:500],
        )
    except Exception as log_err:
        logger.warning(f"Failed to log stage3 observability: {log_err}")

    net_disposable_income = cashflow_analysis.get("net_disposable_income", fallback["net_disposable_income"])

    return {
        "bank_statement_summary": bank_statement_text,
        "cashflow_analysis": cashflow_analysis,
        "net_disposable_income": net_disposable_income,
        "income_stability_score": cashflow_analysis.get("income_stability_score", 50),
        "expense_categories": cashflow_analysis.get("top_expense_categories", []),
        "volatility_score": cashflow_analysis.get("expense_volatility_score", 50),
        "avg_monthly_income": cashflow_analysis.get("avg_monthly_income", monthly_income),
        "avg_monthly_expenses": cashflow_analysis.get("avg_monthly_expenses", monthly_expenses),
        "savings_rate": cashflow_analysis.get("savings_rate", 0.1),
        "key_observations": cashflow_analysis.get("key_observations", []),
        "risk_indicators": cashflow_analysis.get("risk_indicators", []),
    }
