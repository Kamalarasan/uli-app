from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Date,
    ForeignKey, JSON, Boolean, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


class Applicant(Base):
    __tablename__ = "applicants"
    
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(20))
    pan_number = Column(String(10), unique=True, index=True)
    aadhaar_number = Column(String(12))
    date_of_birth = Column(Date)
    address = Column(Text)
    city = Column(String(100))
    state = Column(String(100))
    employment_type = Column(String(50), default="SALARIED")  # SALARIED, SELF_EMPLOYED, BUSINESS
    employer_name = Column(String(255))
    industry = Column(String(100))
    years_employed = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    applications = relationship("LoanApplication", back_populates="applicant", cascade="all, delete-orphan")


class LoanApplication(Base):
    __tablename__ = "loan_applications"
    
    id = Column(Integer, primary_key=True, index=True)
    applicant_id = Column(Integer, ForeignKey("applicants.id"), nullable=False)
    loan_amount = Column(Float, nullable=False)
    loan_purpose = Column(String(100), default="PERSONAL")  # HOME, PERSONAL, BUSINESS, AUTO, EDUCATION
    tenure_months = Column(Integer, nullable=False)
    monthly_income = Column(Float, nullable=False)
    monthly_expenses = Column(Float, nullable=False)
    existing_emi = Column(Float, default=0.0)
    credit_score = Column(Integer, default=650)
    status = Column(String(20), default="PENDING")  # PENDING, PROCESSING, APPROVED, REVIEW, REJECTED
    pipeline_progress = Column(Integer, default=0)  # 0-8 stages completed
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    applicant = relationship("Applicant", back_populates="applications")
    documents = relationship("Document", back_populates="application", cascade="all, delete-orphan")
    report = relationship("UnderwritingReport", back_populates="application", uselist=False, cascade="all, delete-orphan")
    scenarios = relationship("DigitalTwinScenario", back_populates="application", cascade="all, delete-orphan")
    observability_logs = relationship("ObservabilityLog", back_populates="application", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("loan_applications.id"), nullable=False)
    doc_type = Column(String(50), default="OTHER")  # PAYSLIP, BANK_STATEMENT, TAX_FORM, ID_PROOF, OTHER
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    extracted_text = Column(Text)
    classification_result = Column(JSON)  # {doc_type, confidence, fields: {employer, salary, ...}}
    processing_status = Column(String(20), default="PENDING")  # PENDING, PROCESSED, FAILED
    created_at = Column(DateTime, default=datetime.utcnow)
    
    application = relationship("LoanApplication", back_populates="documents")


class UnderwritingReport(Base):
    __tablename__ = "underwriting_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("loan_applications.id"), unique=True, nullable=False)
    
    # Stage results
    stage_results = Column(JSON)  # {"stage1": {...}, "stage2": {...}, ...}
    
    # Key metrics
    kyc_status = Column(String(20), default="PENDING")  # VERIFIED, PENDING, FAILED
    cash_flow_analysis = Column(JSON)  # {net_income, dti_ratio, savings_rate, ...}
    health_score = Column(Float, default=0.0)  # 0-100
    fraud_score = Column(Float, default=0.0)  # 0-100 (higher = more suspicious)
    risk_score = Column(Float, default=0.0)  # 0-100 (higher = more risky)
    policy_violations = Column(JSON)  # list of {rule, severity, message}
    affordability_score = Column(Float, default=0.0)  # 0-100
    max_emi = Column(Float, default=0.0)
    
    # Decision
    decision = Column(String(20))  # APPROVED, REVIEW, REJECTED
    recommended_rate = Column(Float)  # Annual interest rate %
    recommended_tenure = Column(Integer)  # months
    confidence_score = Column(Float, default=0.0)  # 0-100
    reasoning = Column(Text)
    
    # Radar chart data
    income_stability_score = Column(Float, default=0.0)
    expense_management_score = Column(Float, default=0.0)
    debt_management_score = Column(Float, default=0.0)
    credit_history_score = Column(Float, default=0.0)
    fraud_risk_score = Column(Float, default=0.0)  # inverted for display
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    application = relationship("LoanApplication", back_populates="report")


class DigitalTwinScenario(Base):
    __tablename__ = "digital_twin_scenarios"
    
    id = Column(Integer, primary_key=True, index=True)
    base_application_id = Column(Integer, ForeignKey("loan_applications.id"), nullable=False)
    scenario_name = Column(String(100), default="Custom Scenario")
    
    # Scenario parameters
    scenario_params = Column(JSON)  # {salary_change_pct, expense_inflation_pct, rate_shift_bps, tenure_change_months, economic_condition}
    
    # Results
    simulation_results = Column(JSON)  # {decision, health_score, fraud_score, affordability_score, max_emi, recommended_rate, ...}
    
    # Comparison metrics
    approval_probability = Column(Float, default=0.0)  # 0-100
    avg_risk_score = Column(Float, default=0.0)
    estimated_default_rate = Column(Float, default=0.0)
    fairness_metrics = Column(JSON)  # {gender_bias, income_bias, ...}
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    application = relationship("LoanApplication", back_populates="scenarios")


class ObservabilityLog(Base):
    __tablename__ = "observability_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("loan_applications.id"), nullable=True)
    stage_name = Column(String(100), nullable=False)
    prompt_template = Column(String(100))
    prompt_version = Column(String(20), default="1.0")
    model_id = Column(String(100))
    
    # Performance
    latency_ms = Column(Float, default=0.0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # Quality
    validation_status = Column(String(20), default="SUCCESS")  # SUCCESS, FAILED, RECOVERED
    confidence_score = Column(Float)
    decision = Column(String(20))
    error_message = Column(Text)
    
    # Full prompt/response for audit (truncated)
    prompt_preview = Column(String(500))
    response_preview = Column(String(500))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    application = relationship("LoanApplication", back_populates="observability_logs")
