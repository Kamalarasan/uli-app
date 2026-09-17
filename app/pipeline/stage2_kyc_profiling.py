import logging
from sqlalchemy.orm import Session
from app.connectors.kyc import verify_kyc
from app.connectors.gst_income import verify_gst_income

logger = logging.getLogger(__name__)


async def run_stage2(application_data: dict, db: Session) -> dict:
    """
    Stage 2: Identity Summary & KYC Profiling
    - Call KYC connector (PAN/Aadhaar verification mock)
    - Call GST/Income connector
    - Reconcile applicant identity
    Returns: {kyc_status, kyc_result, income_verification, identity_profile, risk_flags}
    """
    pan_number = application_data.get("pan_number", "")
    aadhaar_number = application_data.get("aadhaar_number", "")
    full_name = application_data.get("full_name", "")
    monthly_income = application_data.get("monthly_income", 0.0)
    employment_type = application_data.get("employment_type", "SALARIED")

    risk_flags: list[str] = []

    # ── KYC Verification ─────────────────────────────────────────
    try:
        kyc_result = await verify_kyc(
            pan_number=pan_number,
            aadhaar_number=aadhaar_number,
            full_name=full_name,
        )
    except Exception as e:
        logger.warning(f"KYC connector failed: {e}. Using defaults.")
        kyc_result = {
            "is_valid": True,
            "name_match_score": 75,
            "pan_status": "ACTIVE",
            "aadhaar_linked": True,
            "address_verified": True,
            "photo_match_score": 80,
            "politically_exposed_person": False,
            "risk_category": "LOW",
        }

    # ── GST / Income Verification ─────────────────────────────────
    try:
        income_verification = await verify_gst_income(
            pan_number=pan_number,
            monthly_income=monthly_income,
            employment_type=employment_type,
        )
    except Exception as e:
        logger.warning(f"GST connector failed: {e}. Using defaults.")
        income_verification = {
            "gst_registered": False,
            "itr_filed": True,
            "declared_income": monthly_income * 12,
            "income_verified": True,
            "income_match_score": 80,
            "tax_compliance_score": 70,
            "red_flags": [],
        }

    # ── Risk flag analysis ────────────────────────────────────────
    # Flag income mismatch
    income_match_score = float(income_verification.get("income_match_score", 100))
    if income_match_score < 60:
        risk_flags.append(f"Significant income mismatch: verified match score {income_match_score:.0f}%")
    elif income_match_score < 80:
        risk_flags.append(f"Moderate income discrepancy: match score {income_match_score:.0f}%")

    # Flag KYC issues
    name_match = float(kyc_result.get("name_match_score", 100))
    if name_match < 70:
        risk_flags.append(f"Low KYC name match score: {name_match:.0f}%")

    # Flag PEP
    if kyc_result.get("politically_exposed_person", False):
        risk_flags.append("Applicant is a Politically Exposed Person (PEP) — enhanced due diligence required")

    # Flag PAN inactive
    if kyc_result.get("pan_status") == "INACTIVE":
        risk_flags.append("PAN number is INACTIVE")

    # Flag Aadhaar not linked
    if not kyc_result.get("aadhaar_linked", True):
        risk_flags.append("Aadhaar not linked to PAN")

    # Flag red flags from income verification
    for flag in income_verification.get("red_flags", []):
        risk_flags.append(flag)

    # Flag high industry risk
    if kyc_result.get("risk_category") == "HIGH":
        risk_flags.append(f"High-risk category applicant")

    # ── Build identity profile ────────────────────────────────────
    identity_profile = {
        "verified_name": full_name,
        "pan_number": pan_number,
        "pan_status": kyc_result.get("pan_status", "UNKNOWN"),
        "kyc_match_score": name_match,
        "photo_match_score": float(kyc_result.get("photo_match_score", 0)),
        "aadhaar_linked": kyc_result.get("aadhaar_linked", False),
        "address_verified": kyc_result.get("address_verified", False),
        "income_verified": income_verification.get("income_verified", False),
        "income_match_score": income_match_score,
        "tax_compliance_score": float(income_verification.get("tax_compliance_score", 0)),
        "pep_flag": kyc_result.get("politically_exposed_person", False),
        "risk_category": kyc_result.get("risk_category", "MEDIUM"),
    }

    # ── Determine overall KYC status ──────────────────────────────
    critical_flags = [
        kyc_result.get("pan_status") == "INACTIVE",
        kyc_result.get("politically_exposed_person", False),
        income_match_score < 50,
    ]
    if any(critical_flags):
        kyc_status = "FAILED"
    elif len(risk_flags) > 0 or name_match < 80 or income_match_score < 80:
        kyc_status = "PARTIAL"
    else:
        kyc_status = "VERIFIED"

    return {
        "kyc_status": kyc_status,
        "kyc_result": kyc_result,
        "income_verification": income_verification,
        "identity_profile": identity_profile,
        "risk_flags": risk_flags,
    }
