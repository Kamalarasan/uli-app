import re

async def run_stage1(application_data: dict) -> dict:
    """
    Stage 1: Data Validation & Cleaning
    - Sanitize and validate all input fields
    - Check required fields present
    - Normalize data types
    - Flag data quality issues
    Returns: {status, cleaned_data, validation_issues, data_quality_score}
    """
    cleaned_data = application_data.copy()
    validation_issues = []
    
    # Check required fields
    required_fields = ['loan_amount', 'tenure_months', 'monthly_income', 'pan_number', 'email', 'phone', 'employment_type']
    for field in required_fields:
        if field not in cleaned_data or cleaned_data[field] is None or cleaned_data[field] == "":
            validation_issues.append({"field": field, "severity": "ERROR", "message": f"Missing required field: {field}"})

    # Validate numbers
    if cleaned_data.get('loan_amount', 0) <= 0:
        validation_issues.append({"field": "loan_amount", "severity": "ERROR", "message": "Loan amount must be > 0"})
    
    tenure = cleaned_data.get('tenure_months', 0)
    if not (1 <= tenure <= 360):
        validation_issues.append({"field": "tenure_months", "severity": "ERROR", "message": "Tenure must be between 1 and 360 months"})
        
    if cleaned_data.get('monthly_income', 0) <= 0:
        validation_issues.append({"field": "monthly_income", "severity": "ERROR", "message": "Monthly income must be > 0"})

    # Validate PAN format (Regex: 5 letters, 4 numbers, 1 letter)
    pan = cleaned_data.get('pan_number', '')
    if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', str(pan)):
        validation_issues.append({"field": "pan_number", "severity": "ERROR", "message": "Invalid PAN format"})
        cleaned_data['pan_number'] = str(pan).upper()
        
    # Validate Email format
    email = cleaned_data.get('email', '')
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', str(email)):
        validation_issues.append({"field": "email", "severity": "ERROR", "message": "Invalid email format"})
        
    # Validate Phone format
    phone = cleaned_data.get('phone', '')
    if not re.match(r'^\+?[1-9]\d{1,14}$', str(phone)):
        validation_issues.append({"field": "phone", "severity": "WARNING", "message": "Invalid phone format"})
        
    # Cap credit_score between 300-900
    credit_score = cleaned_data.get('credit_score', 0)
    if credit_score < 300:
        cleaned_data['credit_score'] = 300
        validation_issues.append({"field": "credit_score", "severity": "WARNING", "message": "Credit score capped to minimum 300"})
    elif credit_score > 900:
        cleaned_data['credit_score'] = 900
        validation_issues.append({"field": "credit_score", "severity": "WARNING", "message": "Credit score capped to maximum 900"})
        
    # Normalize employment_type to uppercase
    emp_type = cleaned_data.get('employment_type', '')
    if isinstance(emp_type, str):
        cleaned_data['employment_type'] = emp_type.upper()
        
    # Calculate data_quality_score (0-100) based on completeness
    total_fields = len(application_data)
    missing_or_invalid = len(validation_issues)
    data_quality_score = max(0, 100 - (missing_or_invalid * 10))
    
    # Determine status
    status = "SUCCESS"
    for issue in validation_issues:
        if issue['severity'] == "ERROR":
            status = "FAILED"
            break
            
    return {
        "status": status,
        "cleaned_data": cleaned_data,
        "validation_issues": validation_issues,
        "data_quality_score": data_quality_score
    }
