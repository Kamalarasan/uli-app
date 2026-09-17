import hashlib
import re

async def verify_kyc(pan_number: str, aadhaar_number: str, full_name: str) -> dict:
    pan_valid = bool(re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', pan_number))
    
    # Simple Luhn-like check for Aadhaar (just length 12 for mock)
    aadhaar_valid = len(aadhaar_number) == 12 and aadhaar_number.isdigit()
    
    # Deterministic mock based on PAN
    hash_val = int(hashlib.md5(pan_number.encode()).hexdigest(), 16)
    
    name_match = 85 + (hash_val % 15)
    pan_status = "ACTIVE" if hash_val % 100 > 5 else "INACTIVE"
    aadhaar_linked = hash_val % 100 > 10
    address_verified = hash_val % 100 > 15
    photo_match = 75 + (hash_val % 25)
    pep = hash_val % 100 < 5
    
    risk_score = hash_val % 100
    if risk_score > 80:
        risk_category = "HIGH"
    elif risk_score > 40:
        risk_category = "MEDIUM"
    else:
        risk_category = "LOW"
        
    return {
        "is_valid": pan_valid and aadhaar_valid and pan_status == "ACTIVE",
        "name_match_score": name_match,
        "pan_status": pan_status,
        "aadhaar_linked": aadhaar_linked,
        "address_verified": address_verified,
        "photo_match_score": photo_match,
        "politically_exposed_person": pep,
        "risk_category": risk_category
    }
