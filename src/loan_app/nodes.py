import datetime
from typing import Dict, Any
from .state import State

def get_timestamp() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def calculate_risk(credit_score: int, monthly_income: float, monthly_debt: float, tenure: int) -> float:
    """Computes a numeric risk score between 0 and 100."""
    risk = 50.0
    
    # Credit score impact
    if credit_score >= 750:
        risk -= 20
    elif credit_score >= 650:
        risk -= 10
    elif credit_score < 600:
        risk += 20
    if credit_score < 550:
        risk += 15
        
    # Debt-to-Income (DTI) impact
    dti = monthly_debt / monthly_income if monthly_income > 0 else 1.0
    if dti < 0.2:
        risk -= 10
    elif dti > 0.45:
        risk += 20
    if dti > 0.6:
        risk += 15
        
    # Employment tenure impact
    if tenure >= 24:
        risk -= 10
    elif tenure < 12:
        risk += 15
        
    return max(0.0, min(100.0, risk))


def collect_application(state: State) -> Dict[str, Any]:
    """
    Node 1: Capture applicant and loan details; validate required fields.
    """
    errors = []
    if not state.get("applicant_name") or not state["applicant_name"].strip():
        errors.append("Applicant name cannot be empty.")
    if state.get("applicant_age", 0) < 18:
        errors.append("Applicant must be 18 years or older.")
    if state.get("loan_amount", 0) <= 0:
        errors.append("Loan amount must be greater than zero.")
        
    audit_trail = list(state.get("audit_trail", []))
    
    if errors:
        reason = "; ".join(errors)
        audit_trail.append({
            "node": "collect_application",
            "timestamp": get_timestamp(),
            "action": "FAILED_VALIDATION",
            "message": f"Application validation failed: {reason}"
        })
        return {
            "current_stage": "collect_application",
            "status": "REJECTED",
            "rejection_reason": f"Validation errors: {reason}",
            "audit_trail": audit_trail
        }
    
    audit_trail.append({
        "node": "collect_application",
        "timestamp": get_timestamp(),
        "action": "PASSED_VALIDATION",
        "message": "Applicant and loan details validated successfully."
    })
    return {
        "current_stage": "collect_application",
        "status": "verifying",
        "audit_trail": audit_trail
    }


def verify_documents(state: State) -> Dict[str, Any]:
    """
    Node 2: Verify that all required documents are submitted.
    """
    missing = []
    if not state.get("has_id"):
        missing.append("Government ID")
    if not state.get("has_proof_of_income"):
        missing.append("Proof of Income")
    if not state.get("has_bank_statement"):
        missing.append("Bank Statement")
        
    audit_trail = list(state.get("audit_trail", []))
    
    if missing:
        reason = f"Missing documents: {', '.join(missing)}"
        audit_trail.append({
            "node": "verify_documents",
            "timestamp": get_timestamp(),
            "action": "FAILED_VERIFICATION",
            "message": reason
        })
        return {
            "current_stage": "verify_documents",
            "status": "REJECTED",
            "rejection_reason": reason,
            "audit_trail": audit_trail
        }
        
    audit_trail.append({
        "node": "verify_documents",
        "timestamp": get_timestamp(),
        "action": "PASSED_VERIFICATION",
        "message": "All required documents verified successfully."
    })
    return {
        "current_stage": "verify_documents",
        "status": "assessing_risk",
        "audit_trail": audit_trail
    }


def risk_assessment(state: State) -> Dict[str, Any]:
    """
    Node 3: Compute risk score.
    """
    risk_score = calculate_risk(
        credit_score=state.get("credit_score", 0),
        monthly_income=state.get("monthly_income", 0.0),
        monthly_debt=state.get("monthly_debt", 0.0),
        tenure=state.get("employment_tenure_months", 0)
    )
    
    audit_trail = list(state.get("audit_trail", []))
    
    if risk_score > 85:
        reason = f"Calculated risk score {risk_score:.1f} exceeds threshold of 85."
        audit_trail.append({
            "node": "risk_assessment",
            "timestamp": get_timestamp(),
            "action": "FAILED_RISK_ASSESSMENT",
            "message": reason
        })
        return {
            "current_stage": "risk_assessment",
            "status": "REJECTED",
            "risk_score": risk_score,
            "rejection_reason": reason,
            "audit_trail": audit_trail
        }
        
    audit_trail.append({
        "node": "risk_assessment",
        "timestamp": get_timestamp(),
        "action": "PASSED_RISK_ASSESSMENT",
        "message": f"Risk assessment passed with score: {risk_score:.1f}/100."
    })
    return {
        "current_stage": "risk_assessment",
        "status": "checking_eligibility",
        "risk_score": risk_score,
        "audit_trail": audit_trail
    }


def eligibility_check(state: State) -> Dict[str, Any]:
    """
    Node 4: Enforce minimum credit score and maximum loan-to-income ratio.
    """
    credit = state.get("credit_score", 0)
    monthly_income = state.get("monthly_income", 0.0)
    annual_income = monthly_income * 12
    loan_amount = state.get("loan_amount", 0.0)
    
    audit_trail = list(state.get("audit_trail", []))
    errors = []
    
    if credit < 600:
        errors.append(f"Credit score {credit} is below minimum requirement of 600")
        
    if annual_income <= 0:
        errors.append("Annual income must be greater than 0 to evaluate eligibility")
    else:
        lti = loan_amount / annual_income
        if lti > 4.5:
            errors.append(f"Loan-to-Income ratio {lti:.2f} exceeds maximum limit of 4.5")
            
    if errors:
        reason = "; ".join(errors)
        audit_trail.append({
            "node": "eligibility_check",
            "timestamp": get_timestamp(),
            "action": "FAILED_ELIGIBILITY",
            "message": reason
        })
        return {
            "current_stage": "eligibility_check",
            "status": "REJECTED",
            "rejection_reason": reason,
            "audit_trail": audit_trail
        }
        
    audit_trail.append({
        "node": "eligibility_check",
        "timestamp": get_timestamp(),
        "action": "PASSED_ELIGIBILITY",
        "message": f"Eligibility requirements met. LTI: {loan_amount / annual_income:.2f}."
    })
    return {
        "current_stage": "eligibility_check",
        "status": "pending_approval",
        "audit_trail": audit_trail
    }


def manager_approval(state: State) -> Dict[str, Any]:
    """
    Node 5: Auto-approve, auto-reject, or route to pending manual review.
    """
    risk_score = state.get("risk_score", 50.0)
    loan_amount = state.get("loan_amount", 0.0)
    
    audit_trail = list(state.get("audit_trail", []))
    
    if risk_score < 30 and loan_amount < 25000:
        audit_trail.append({
            "node": "manager_approval",
            "timestamp": get_timestamp(),
            "action": "AUTO_APPROVED",
            "message": f"Auto-approved: risk score {risk_score:.1f} < 30 and amount ${loan_amount:,} < $25,000."
        })
        return {
            "current_stage": "manager_approval",
            "status": "APPROVED",
            "manager_decision": "AUTO_APPROVED",
            "audit_trail": audit_trail
        }
        
    if risk_score > 75:
        reason = f"Auto-rejected by manager rules: risk score {risk_score:.1f} exceeds auto-rejection threshold of 75."
        audit_trail.append({
            "node": "manager_approval",
            "timestamp": get_timestamp(),
            "action": "AUTO_REJECTED",
            "message": reason
        })
        return {
            "current_stage": "manager_approval",
            "status": "REJECTED",
            "rejection_reason": reason,
            "manager_decision": "AUTO_REJECTED",
            "audit_trail": audit_trail
        }
        
    audit_trail.append({
        "node": "manager_approval",
        "timestamp": get_timestamp(),
        "action": "PENDING_REVIEW",
        "message": f"Application requires manual manager review. Risk score: {risk_score:.1f}, Amount: ${loan_amount:,}."
    })
    return {
        "current_stage": "manager_approval",
        "status": "pending_review",
        "manager_decision": "PENDING",
        "audit_trail": audit_trail
    }


def pending_review(state: State) -> Dict[str, Any]:
    """
    Node 6: Pause and resume human review.
    """
    decision = state.get("manager_decision")
    notes = state.get("manager_notes", "No notes provided.")
    audit_trail = list(state.get("audit_trail", []))
    
    if decision == "APPROVED":
        audit_trail.append({
            "node": "pending_review",
            "timestamp": get_timestamp(),
            "action": "MANUALLY_APPROVED",
            "message": f"Manager approved. Notes: {notes}"
        })
        return {
            "current_stage": "pending_review",
            "status": "APPROVED",
            "audit_trail": audit_trail
        }
    elif decision == "REJECTED":
        audit_trail.append({
            "node": "pending_review",
            "timestamp": get_timestamp(),
            "action": "MANUALLY_REJECTED",
            "message": f"Manager rejected. Notes: {notes}"
        })
        return {
            "current_stage": "pending_review",
            "status": "REJECTED",
            "rejection_reason": f"Rejected by manager: {notes}",
            "audit_trail": audit_trail
        }
    
    return {
        "current_stage": "pending_review",
        "status": "pending_review",
    }


def final_decision(state: State) -> Dict[str, Any]:
    """Terminal node for successful approvals."""
    audit_trail = list(state.get("audit_trail", []))
    audit_trail.append({
        "node": "final_decision",
        "timestamp": get_timestamp(),
        "action": "LOAN_APPROVED",
        "message": "Loan application workflow finalized. Status: APPROVED."
    })
    return {
        "current_stage": "final_decision",
        "status": "APPROVED",
        "audit_trail": audit_trail
    }


def rejected(state: State) -> Dict[str, Any]:
    """Terminal node for failures or rejections."""
    audit_trail = list(state.get("audit_trail", []))
    reason = state.get("rejection_reason", "No reason specified.")
    audit_trail.append({
        "node": "rejected",
        "timestamp": get_timestamp(),
        "action": "LOAN_REJECTED",
        "message": f"Loan application workflow finalized. Status: REJECTED. Reason: {reason}"
    })
    return {
        "current_stage": "rejected",
        "status": "REJECTED",
        "audit_trail": audit_trail
    }
