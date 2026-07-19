from typing import TypedDict, List, Dict, Any, Optional

class State(TypedDict):
    """
    Represents the full schema of the Loan Application Workflow graph state.
    Must remain fully JSON-serializable for LangGraph checkpointing.
    """
    # Applicant details
    applicant_name: str
    applicant_age: int
    employment_tenure_months: int
    credit_score: int
    monthly_income: float
    monthly_debt: float
    
    # Loan details
    loan_amount: float
    loan_purpose: str
    
    # Verification documents
    has_id: bool
    has_proof_of_income: bool
    has_bank_statement: bool
    
    # Stage & Decisions
    current_stage: str  # Tracks name of the currently active stage/node
    status: str         # "collecting", "verifying", "assessing_risk", "checking_eligibility", "pending_review", "APPROVED", "REJECTED"
    risk_score: Optional[float]
    rejection_reason: Optional[str]
    
    # Manager review details
    manager_decision: Optional[str]  # None, "PENDING", "APPROVED", "REJECTED", "AUTO_APPROVED", "AUTO_REJECTED"
    manager_notes: Optional[str]
    
    # Audit trail (list of historical entries per node execution)
    audit_trail: List[Dict[str, Any]]


def create_initial_state(
    applicant_name: str,
    applicant_age: int,
    employment_tenure_months: int,
    credit_score: int,
    monthly_income: float,
    monthly_debt: float,
    loan_amount: float,
    loan_purpose: str,
    has_id: bool = False,
    has_proof_of_income: bool = False,
    has_bank_statement: bool = False,
) -> State:
    """Helper function to create a clean initial state for a new application."""
    return {
        "applicant_name": applicant_name,
        "applicant_age": applicant_age,
        "employment_tenure_months": employment_tenure_months,
        "credit_score": credit_score,
        "monthly_income": monthly_income,
        "monthly_debt": monthly_debt,
        "loan_amount": loan_amount,
        "loan_purpose": loan_purpose,
        "has_id": has_id,
        "has_proof_of_income": has_proof_of_income,
        "has_bank_statement": has_bank_statement,
        "current_stage": "collect_application",
        "status": "collecting",
        "risk_score": None,
        "rejection_reason": None,
        "manager_decision": None,
        "manager_notes": None,
        "audit_trail": [],
    }
