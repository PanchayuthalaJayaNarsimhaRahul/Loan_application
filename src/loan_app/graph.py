# pyrefly: ignore [missing-import]
from langgraph.graph import StateGraph, END
from .state import State
from .nodes import (
    collect_application,
    verify_documents,
    risk_assessment,
    eligibility_check,
    manager_approval,
    pending_review,
    final_decision,
    rejected
)
from .conditions import (
    route_collect_application,
    route_verify_documents,
    route_risk_assessment,
    route_eligibility_check,
    route_manager_approval,
    route_pending_review
)

def create_graph(checkpointer=None):
    """
    Constructs, configures, and compiles the LangGraph loan application workflow.
    Configures an interrupt BEFORE the 'pending_review' node for manual review.
    """
    workflow = StateGraph(State)
    
    # Register workflow nodes
    workflow.add_node("collect_application", collect_application)
    workflow.add_node("verify_documents", verify_documents)
    workflow.add_node("risk_assessment", risk_assessment)
    workflow.add_node("eligibility_check", eligibility_check)
    workflow.add_node("manager_approval", manager_approval)
    workflow.add_node("pending_review", pending_review)
    workflow.add_node("final_decision", final_decision)
    workflow.add_node("rejected", rejected)
    
    # Set the workflow start point
    workflow.set_entry_point("collect_application")
    
    # Register conditional routing edges
    workflow.add_conditional_edges(
        "collect_application",
        route_collect_application,
        {
            "verify_documents": "verify_documents",
            "rejected": "rejected"
        }
    )
    workflow.add_conditional_edges(
        "verify_documents",
        route_verify_documents,
        {
            "risk_assessment": "risk_assessment",
            "rejected": "rejected"
        }
    )
    workflow.add_conditional_edges(
        "risk_assessment",
        route_risk_assessment,
        {
            "eligibility_check": "eligibility_check",
            "rejected": "rejected"
        }
    )
    workflow.add_conditional_edges(
        "eligibility_check",
        route_eligibility_check,
        {
            "manager_approval": "manager_approval",
            "rejected": "rejected"
        }
    )
    workflow.add_conditional_edges(
        "manager_approval",
        route_manager_approval,
        {
            "final_decision": "final_decision",
            "rejected": "rejected",
            "pending_review": "pending_review"
        }
    )
    workflow.add_conditional_edges(
        "pending_review",
        route_pending_review,
        {
            "final_decision": "final_decision",
            "rejected": "rejected",
            "pending_review": "pending_review"
        }
    )
    
    # Standard edges from terminal nodes to END
    workflow.add_edge("final_decision", END)
    workflow.add_edge("rejected", END)
    
    # Compile with persistence checkpointer and pause step
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["pending_review"]
    )
