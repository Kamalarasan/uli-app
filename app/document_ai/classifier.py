import re

async def classify_and_extract(text: str, filename: str) -> dict:
    text_lower = text.lower()
    
    keywords = {
        "PAYSLIP": ["salary", "gross", "net pay", "basic", "deduction", "pf", "esi", "tds", "payslip"],
        "BANK_STATEMENT": ["statement", "account no", "ifsc", "balance", "credit", "debit", "transaction"],
        "TAX_FORM": ["form 16", "itr", "assessment year", "income tax", "pan"],
        "ID_PROOF": ["pan card", "aadhaar", "passport", "driving license", "election commission"]
    }
    
    scores = {doc_type: 0 for doc_type in keywords}
    for doc_type, kw_list in keywords.items():
        for kw in kw_list:
            if kw in text_lower or kw in filename.lower():
                scores[doc_type] += 1
                
    best_match = max(scores.items(), key=lambda x: x[1])
    doc_type = best_match[0] if best_match[1] > 0 else "OTHER"
    confidence = min(best_match[1] / 3.0, 1.0) if best_match[1] > 0 else 0.0
    
    extracted = {}
    if doc_type == "PAYSLIP":
        gross_match = re.search(r'(?:gross salary|gross pay)[\s:]*([\d,]+\.?\d*)', text_lower)
        if gross_match: extracted["gross_salary"] = gross_match.group(1)
    elif doc_type == "BANK_STATEMENT":
        acc_match = re.search(r'(?:account no|a/c no)[\s:]*([\dx]+)', text_lower)
        if acc_match: extracted["account_number"] = f"XXXXXX{acc_match.group(1)[-4:]}"
    elif doc_type == "TAX_FORM":
        pan_match = re.search(r'[a-z]{5}[0-9]{4}[a-z]', text_lower)
        if pan_match: extracted["pan_number"] = pan_match.group(0).upper()
    elif doc_type == "ID_PROOF":
        pan_match = re.search(r'[a-z]{5}[0-9]{4}[a-z]', text_lower)
        if pan_match:
            extracted["id_type"] = "PAN"
            extracted["id_number"] = pan_match.group(0).upper()
            
    return {
        "doc_type": doc_type,
        "confidence": confidence,
        "extracted_fields": extracted
    }
