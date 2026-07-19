from .state import State

def route_collect_application(state: State) -> str:
    """Route after collect_application stage."""
    if state.get("status") == "REJECTED":
        return "rejected"
    return "verify_documents"

def route_verify_documents(state: State) -> str:
    """Route after verify_documents stage."""
    if state.get("status") == "REJECTED":
        return "rejected"
    return "risk_assessment"

def route_risk_assessment(state: State) -> str:
    """Route after risk_assessment stage."""
    if state.get("status") == "REJECTED":
        return "rejected"
    return "eligibility_check"

def route_eligibility_check(state: State) -> str:
    """Route after eligibility_check stage."""
    if state.get("status") == "REJECTED":
        return "rejected"
    return "manager_approval"

def route_manager_approval(state: State) -> str:
    """Route after manager_approval stage."""
    decision = state.get("manager_decision")
    if decision == "AUTO_APPROVED":
        return "final_decision"
    elif decision == "AUTO_REJECTED":
        return "rejected"
    return "pending_review"  # Matches PENDING status for manual review

def route_pending_review(state: State) -> str:
    """Route after pending_review stage (when manual review resumes)."""
    status = state.get("status")
    if status == "APPROVED":
        return "final_decision"
    elif status == "REJECTED":
        return "rejected"
    return "pending_review"  # Fallback to keep in review if no valid decision is present
