from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date


# Base Models for Applicant
class ApplicantBase(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    pan_number: Optional[str] = None
    aadhaar_number: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    employment_type: str = "SALARIED"
    employer_name: Optional[str] = None
    industry: Optional[str] = None
    years_employed: float = 0.0

class ApplicantCreate(ApplicantBase):
    pass

class ApplicantResponse(ApplicantBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Base Models for Loan Application
class LoanApplicationBase(BaseModel):
    loan_amount: float
    loan_purpose: str = "PERSONAL"
    tenure_months: int
    monthly_income: float
    monthly_expenses: float
    existing_emi: float = 0.0
    credit_score: int = 650

class LoanApplicationCreate(LoanApplicationBase):
    applicant_id: int

class LoanApplicationResponse(LoanApplicationBase):
    id: int
    applicant_id: int
    status: str
    pipeline_progress: int
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Models for Document
class DocumentResponse(BaseModel):
    id: int
    application_id: int
    doc_type: str
    filename: str
    file_path: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    classification_result: Optional[Dict[str, Any]] = None
    processing_status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Models for Underwriting Report
class UnderwritingReportBase(BaseModel):
    kyc_status: str
    cash_flow_analysis: Optional[Dict[str, Any]] = None
    health_score: float
    fraud_score: float
    risk_score: float
    policy_violations: Optional[List[Dict[str, Any]]] = None
    affordability_score: float
    max_emi: float
    decision: Optional[str] = None
    recommended_rate: Optional[float] = None
    recommended_tenure: Optional[int] = None
    confidence_score: float
    reasoning: Optional[str] = None
    income_stability_score: float
    expense_management_score: float
    debt_management_score: float
    credit_history_score: float
    fraud_risk_score: float

class UnderwritingReportResponse(UnderwritingReportBase):
    id: int
    application_id: int
    stage_results: Optional[Dict[str, Any]] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Models for Digital Twin Scenario
class DigitalTwinScenarioBase(BaseModel):
    scenario_name: str = "Custom Scenario"
    salary_change_pct: float
    expense_inflation_pct: float
    rate_shift_bps: float
    tenure_change_months: int
    economic_condition: str

class DigitalTwinScenarioCreate(DigitalTwinScenarioBase):
    base_application_id: int

class DigitalTwinScenarioResponse(BaseModel):
    id: int
    base_application_id: int
    scenario_name: str
    scenario_params: Dict[str, Any]
    simulation_results: Optional[Dict[str, Any]] = None
    approval_probability: float
    avg_risk_score: float
    estimated_default_rate: float
    fairness_metrics: Optional[Dict[str, Any]] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Models for Observability
class ObservabilityLogBase(BaseModel):
    application_id: Optional[int] = None
    stage_name: str
    prompt_template: Optional[str] = None
    prompt_version: str = "1.0"
    model_id: Optional[str] = None
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    validation_status: str = "SUCCESS"
    confidence_score: Optional[float] = None
    decision: Optional[str] = None
    error_message: Optional[str] = None
    prompt_preview: Optional[str] = None
    response_preview: Optional[str] = None

class ObservabilityLogResponse(ObservabilityLogBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ObservabilityMetrics(BaseModel):
    total_calls: int
    avg_latency_ms: float
    total_tokens: int
    by_model: Dict[str, Any]
    by_stage: Dict[str, Any]
    by_validation_status: Dict[str, Any]
    success_rate: float
    model_config = ConfigDict(from_attributes=True)


# Composite and Utility Models
class PipelineStatus(BaseModel):
    application_id: int
    status: str
    current_stage: int
    total_stages: int
    message: str
    model_config = ConfigDict(from_attributes=True)

class LoanApplicationFull(BaseModel):
    application: LoanApplicationResponse
    applicant: ApplicantResponse
    report: Optional[UnderwritingReportResponse] = None
    model_config = ConfigDict(from_attributes=True)

class CashFlowAnalysis(BaseModel):
    net_income: float
    dti_ratio: float
    savings_rate: float
    disposable_income: float
    model_config = ConfigDict(from_attributes=True)

class FraudAnalysis(BaseModel):
    fraud_score: float
    risk_factors: List[str]
    is_suspicious: bool
    model_config = ConfigDict(from_attributes=True)

class PolicyViolation(BaseModel):
    rule: str
    severity: str
    message: str
    model_config = ConfigDict(from_attributes=True)

class UnderwritingDecision(BaseModel):
    decision: str
    recommended_rate: float
    recommended_tenure: int
    reasoning: str
    confidence_score: float
    max_emi: float
    model_config = ConfigDict(from_attributes=True)

class SeedResponse(BaseModel):
    message: str
    records_created: int
    model_config = ConfigDict(from_attributes=True)
