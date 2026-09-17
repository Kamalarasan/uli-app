import logging
from app.rag.retriever import retrieve_and_rerank

logger = logging.getLogger(__name__)


async def run_stage6(application_data: dict, stage4_result: dict) -> dict:
    """
    Stage 6: Policy Matching & Business Rules
    - Retrieve relevant credit policies via RAG
    - Evaluate policies against applicant financials
    Returns: {matched_policies, violations, compliance_score, policy_recommendations}
    """
    loan_type = application_data.get('loan_purpose', 'PERSONAL').upper()
    monthly_income = float(application_data.get('monthly_income', 0))
    dti_ratio = float(stage4_result.get('dti_ratio', 0))
    credit_score = float(application_data.get('credit_score', 0))
    employment_years = float(application_data.get('years_employed', 0))
    existing_emi = float(application_data.get('existing_emi', 0))
    kyc_status = application_data.get('kyc_status', 'PENDING')
    employment_type = application_data.get('employment_type', 'SALARIED')
    industry = application_data.get('industry', 'OTHER')

    query = (
        f"Credit policy for {loan_type} loan with monthly income {monthly_income:.0f}, "
        f"DTI ratio {dti_ratio:.1f}%, credit score {credit_score:.0f}, "
        f"employment type {employment_type}, industry {industry}"
    )
    try:
        matched_policies = await retrieve_and_rerank(query, k=5, rerank_top_n=3)
    except Exception as e:
        logger.warning(f"RAG retrieval failed in stage6: {e}. Using empty policy list.")
        matched_policies = []

    violations = []
    critical_violations = 0
    high_violations = 0
    medium_violations = 0
    warning_violations = 0
    
    if loan_type.lower() == 'personal' and dti_ratio > 40:
        violations.append({"rule": "DTI Limit", "severity": "CRITICAL", "message": f"DTI > 40% ({dti_ratio:.2f}%) for personal loan"})
        critical_violations += 1
        
    if credit_score < 650:
        violations.append({"rule": "Credit Score Minimum", "severity": "CRITICAL", "message": f"Credit score {credit_score} < 650"})
        critical_violations += 1
        
    if monthly_income < 20000:
        violations.append({"rule": "Minimum Income", "severity": "HIGH", "message": f"Monthly income {monthly_income} < 20000"})
        high_violations += 1
        
    if monthly_income > 0 and (existing_emi / monthly_income) > 0.30:
        violations.append({"rule": "Existing EMI Limit", "severity": "MEDIUM", "message": "Existing EMI > 30% of income"})
        medium_violations += 1
        
    if employment_years < 1:
        violations.append({"rule": "Employment Tenure", "severity": "WARNING", "message": "Employment < 1 year"})
        warning_violations += 1
        
    compliance_score = max(0, 100 - (critical_violations * 30 + high_violations * 15 + medium_violations * 5 + warning_violations * 2))
    
    policy_recommendations = []
    if critical_violations > 0:
        policy_recommendations.append("Application violates critical credit policies.")
    elif compliance_score < 80:
        policy_recommendations.append("Application requires manual review due to policy deviations.")
    else:
        policy_recommendations.append("Application meets standard credit policies.")
        
    return {
        "matched_policies": matched_policies,
        "violations": violations,
        "compliance_score": compliance_score,
        "policy_recommendations": policy_recommendations
    }
