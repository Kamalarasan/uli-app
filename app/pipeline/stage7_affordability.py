async def run_stage7(application_data: dict, stage3_result: dict, stage4_result: dict) -> dict:
    """
    Stage 7: Affordability Check
    - Calculate max affordable EMI
    - Check repayment capacity
    Returns: {max_emi, requested_emi, affordability_score, repayment_capacity_ratio,
              recommended_tenure_adjustment, loan_to_income_ratio, stress_test_result}
    """
    net_disposable_income = stage3_result.get('net_disposable_income', 0)
    loan_amount = float(application_data.get('loan_amount', 0))
    monthly_income = float(application_data.get('monthly_income', 1))
    tenure_months = int(application_data.get('tenure_months', 12))
    
    max_emi = 0.40 * net_disposable_income
    
    annual_rate = 0.12
    monthly_rate = annual_rate / 12.0
    
    if monthly_rate > 0 and tenure_months > 0:
        requested_emi = loan_amount * monthly_rate * ((1 + monthly_rate) ** tenure_months) / (((1 + monthly_rate) ** tenure_months) - 1)
    else:
        requested_emi = loan_amount / (tenure_months if tenure_months > 0 else 12)
        
    affordability_score = min(100.0, (max_emi / requested_emi) * 100.0) if requested_emi > 0 else 100.0
    repayment_capacity_ratio = max_emi / requested_emi if requested_emi > 0 else float('inf')
    
    loan_to_income_ratio = loan_amount / (monthly_income * 12.0)
    
    # Stress test
    stressed_income = net_disposable_income * 0.80  # 20% drop
    stressed_expenses = (monthly_income - net_disposable_income) * 1.15  # 15% rise
    stressed_net_disposable = (monthly_income * 0.80) - stressed_expenses
    
    income_stress = (stressed_income * 0.40) >= requested_emi
    expense_stress = ( (monthly_income - stressed_expenses) * 0.40) >= requested_emi
    combined_stress = (stressed_net_disposable * 0.40) >= requested_emi
    
    stress_test_result = {
        "income_stress": income_stress,
        "expense_stress": expense_stress,
        "combined_stress": combined_stress
    }
    
    recommended_tenure_adjustment = 0
    if requested_emi > max_emi and max_emi > 0:
        # Calculate required tenure for max_emi
        # EMI = P * r * (1+r)^n / ((1+r)^n - 1)
        # We can approximate or just suggest +12 months
        recommended_tenure_adjustment = 12
        
    return {
        "max_emi": round(max_emi, 2),
        "requested_emi": round(requested_emi, 2),
        "affordability_score": round(affordability_score, 2),
        "repayment_capacity_ratio": round(repayment_capacity_ratio, 2),
        "recommended_tenure_adjustment": recommended_tenure_adjustment,
        "loan_to_income_ratio": round(loan_to_income_ratio, 2),
        "stress_test_result": stress_test_result
    }
