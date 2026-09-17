import random
from datetime import datetime, timedelta

async def fetch_bank_statement(applicant_id: int, monthly_income: float, monthly_expenses: float) -> dict:
    random.seed(applicant_id)
    account_number = f"XXXXXX{random.randint(1000,9999)}"
    bank_name = random.choice(["HDFC Bank", "ICICI Bank", "SBI", "Axis Bank"])
    account_type = "SAVINGS"
    ifsc = f"{bank_name[:4].upper()}000{random.randint(1000,9999)}"
    
    transactions = []
    current_date = datetime.now()
    
    categories = ["FREELANCE", "RENT", "UTILITIES", "FOOD", "TRANSPORT", "EMI", "INSURANCE", "INVESTMENT", "OTHER"]
    
    opening_bal = monthly_income * random.uniform(1.0, 3.0)
    
    min_bal = opening_bal
    max_bal = opening_bal
    bounce_count = 0
    total_inc = 0
    total_exp = 0
    
    for i in range(12):
        month_date = current_date - timedelta(days=30 * (11 - i))
        month_name = month_date.strftime("%B %Y")
        
        credits = []
        debits = []
        
        # Salary around 1st-5th
        sal_date = month_date.replace(day=random.randint(1, 5))
        sal_amount = monthly_income * random.uniform(0.95, 1.05)
        credits.append({"date": sal_date.strftime("%Y-%m-%d"), "description": "SALARY CREDIT", "amount": sal_amount, "category": "SALARY"})
        
        # Expenses
        num_expenses = random.randint(10, 20)
        exp_amount = monthly_expenses * random.uniform(0.9, 1.1)
        avg_exp = exp_amount / num_expenses
        
        for _ in range(num_expenses):
            exp_d = month_date.replace(day=random.randint(1, 28))
            debits.append({"date": exp_d.strftime("%Y-%m-%d"), "description": f"POS/UPI {random.randint(1000,9999)}", "amount": avg_exp * random.uniform(0.5, 1.5), "category": random.choice(categories)})
        
        tot_c = sum(c["amount"] for c in credits)
        tot_d = sum(d["amount"] for d in debits)
        
        closing_bal = opening_bal + tot_c - tot_d
        
        if closing_bal < 0:
            bounce_count += 1
            closing_bal = 0 # reset for next month simulation
            
        if closing_bal < min_bal: min_bal = closing_bal
        if closing_bal > max_bal: max_bal = closing_bal
        
        transactions.append({
            "month_name": month_name,
            "credits": credits,
            "debits": debits,
            "opening_balance": opening_bal,
            "closing_balance": closing_bal,
            "total_credits": tot_c,
            "total_debits": tot_d
        })
        
        total_inc += tot_c
        total_exp += tot_d
        opening_bal = closing_bal
        
    avg_inc = total_inc / 12
    avg_exp = total_exp / 12
    
    return {
        "account_number": account_number,
        "bank_name": bank_name,
        "account_type": account_type,
        "ifsc": ifsc,
        "transactions": transactions,
        "summary": {
            "avg_monthly_income": avg_inc,
            "avg_monthly_expenses": avg_exp,
            "income_consistency_score": random.randint(75, 98),
            "avg_savings_rate": max(0, (avg_inc - avg_exp) / avg_inc) if avg_inc > 0 else 0,
            "min_balance": min_bal,
            "max_balance": max_bal,
            "bounce_count": bounce_count
        }
    }
