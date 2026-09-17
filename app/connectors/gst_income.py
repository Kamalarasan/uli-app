import hashlib
import random

async def verify_gst_income(pan_number: str, monthly_income: float, employment_type: str) -> dict:
    hash_val = int(hashlib.md5(pan_number.encode()).hexdigest(), 16)
    random.seed(hash_val)
    
    if employment_type == "SALARIED":
        return {
            "gst_registered": False,
            "gstin": None,
            "annual_turnover": None,
            "itr_filed": random.choice([True, True, True, False]),
            "declared_income": monthly_income * 12 * random.uniform(0.9, 1.1),
            "income_verified": True,
            "income_match_score": random.randint(85, 100),
            "tax_compliance_score": random.randint(70, 100),
            "business_vintage_years": None,
            "red_flags": []
        }
    else:
        gst_registered = random.choice([True, True, False])
        return {
            "gst_registered": gst_registered,
            "gstin": f"{random.randint(10,99)}{pan_number}{random.randint(1,9)}Z{random.choice('A B C D E F'.split())}" if gst_registered else None,
            "annual_turnover": monthly_income * 12 * random.uniform(1.2, 3.5) if gst_registered else None,
            "itr_filed": random.choice([True, True, False]),
            "declared_income": monthly_income * 12 * random.uniform(0.8, 1.2),
            "income_verified": gst_registered,
            "income_match_score": random.randint(60, 95),
            "tax_compliance_score": random.randint(50, 95),
            "business_vintage_years": round(random.uniform(1.0, 10.0), 1),
            "red_flags": ["Late GST filing"] if random.random() < 0.2 else []
        }
