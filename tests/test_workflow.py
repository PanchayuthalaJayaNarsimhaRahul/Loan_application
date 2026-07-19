import sqlite3
# pyrefly: ignore [missing-import]
import pytest
# pyrefly: ignore [missing-import]
from langgraph.checkpoint.sqlite import SqliteSaver

from src.loan_app.state import create_initial_state
from src.loan_app.graph import create_graph

@pytest.fixture
def test_app():
    """Provides a fresh compiled graph with a clean in-memory SQLite checkpointer for each test."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()
    app = create_graph(checkpointer)
    yield app, conn
    conn.close()


def test_auto_approval_path(test_app):
    """Test full auto-approval path for a low-risk, small-amount loan."""
    app, conn = test_app
    config = {"configurable": {"thread_id": "test-thread-1"}}
    
    # Alice: Low risk, small amount, all docs
    state = create_initial_state(
        applicant_name="Alice Smith",
        applicant_age=30,
        employment_tenure_months=36,
        credit_score=800,
        monthly_income=10000.0,
        monthly_debt=500.0,
        loan_amount=15000.0,
        loan_purpose="Car Purchase",
        has_id=True,
        has_proof_of_income=True,
        has_bank_statement=True
    )
    
    # Execute graph fully
    events = list(app.stream(state, config))
    
    # Check final state
    final_state = app.get_state(config)
    values = final_state.values
    
    assert values["status"] == "APPROVED"
    assert values["manager_decision"] == "AUTO_APPROVED"
    assert values["current_stage"] == "final_decision"
    assert values["risk_score"] is not None
    assert values["risk_score"] < 30
    assert not values["rejection_reason"]
    
    # Verify nodes ran
    nodes_run = [event_key for event in events for event_key in event.keys()]
    assert "collect_application" in nodes_run
    assert "verify_documents" in nodes_run
    assert "risk_assessment" in nodes_run
    assert "eligibility_check" in nodes_run
    assert "manager_approval" in nodes_run
    assert "final_decision" in nodes_run


def test_rejection_at_verify_documents(test_app):
    """Test rejection when required verification documents are missing."""
    app, conn = test_app
    config = {"configurable": {"thread_id": "test-thread-2"}}
    
    # Bob: Missing bank statement
    state = create_initial_state(
        applicant_name="Bob Jones",
        applicant_age=25,
        employment_tenure_months=12,
        credit_score=700,
        monthly_income=5000.0,
        monthly_debt=1000.0,
        loan_amount=5000.0,
        loan_purpose="Debt Consolidation",
        has_id=True,
        has_proof_of_income=True,
        has_bank_statement=False  # Missing document
    )
    
    list(app.stream(state, config))
    
    final_state = app.get_state(config)
    values = final_state.values
    
    assert values["status"] == "REJECTED"
    assert values["current_stage"] == "rejected"
    assert "Missing documents" in values["rejection_reason"]
    assert "Bank Statement" in values["rejection_reason"]


def test_rejection_at_risk_assessment(test_app):
    """Test rejection when computed risk score exceeds the threshold of 85."""
    app, conn = test_app
    config = {"configurable": {"thread_id": "test-thread-3"}}
    
    # Charlie: High debt, low credit, low tenure -> High risk
    state = create_initial_state(
        applicant_name="Charlie Brown",
        applicant_age=22,
        employment_tenure_months=3,  # Low tenure (+15 risk)
        credit_score=520,            # Low credit (+35 risk)
        monthly_income=3000.0,
        monthly_debt=2100.0,         # High DTI 70% (+35 risk)
        loan_amount=10000.0,
        loan_purpose="Personal",
        has_id=True,
        has_proof_of_income=True,
        has_bank_statement=True
    )
    # Total risk score should clamp to 100, which is > 85
    
    list(app.stream(state, config))
    
    final_state = app.get_state(config)
    values = final_state.values
    
    assert values["status"] == "REJECTED"
    assert values["current_stage"] == "rejected"
    assert values["risk_score"] == 100.0
    assert "risk score" in values["rejection_reason"].lower()


def test_rejection_at_eligibility_credit_score(test_app):
    """Test rejection when credit score is below the minimum requirement of 600, but passes risk assessment."""
    app, conn = test_app
    config = {"configurable": {"thread_id": "test-thread-4"}}
    
    # Dave: Credit score 590 (below 600 limit)
    # Let's ensure risk score passes by having low debt and high tenure
    state = create_initial_state(
        applicant_name="Dave Miller",
        applicant_age=45,
        employment_tenure_months=48,  # Tenure >= 24 (-10 risk)
        credit_score=590,            # Credit < 600 (+20 risk)
        monthly_income=8000.0,
        monthly_debt=400.0,          # DTI 5% < 20% (-10 risk)
        loan_amount=10000.0,
        loan_purpose="Home Repair",
        has_id=True,
        has_proof_of_income=True,
        has_bank_statement=True
    )
    # Risk calculation: 50 + 20 (credit) - 10 (DTI) - 10 (tenure) = 50. Passes risk check.
    
    list(app.stream(state, config))
    
    final_state = app.get_state(config)
    values = final_state.values
    
    assert values["status"] == "REJECTED"
    assert values["current_stage"] == "rejected"
    assert values["risk_score"] == 50.0
    assert "Credit score 590 is below minimum requirement of 600" in values["rejection_reason"]


def test_rejection_at_eligibility_loan_to_income(test_app):
    """Test rejection when loan-to-income (LTI) ratio exceeds 4.5."""
    app, conn = test_app
    config = {"configurable": {"thread_id": "test-thread-5"}}
    
    # Eve: High income, but requesting a massive loan (LTI > 4.5)
    # Income: $2,000/mo ($24,000/yr). Loan amount: $120,000. LTI = 5.0
    state = create_initial_state(
        applicant_name="Eve Adams",
        applicant_age=35,
        employment_tenure_months=36,
        credit_score=750,
        monthly_income=2000.0,
        monthly_debt=100.0,
        loan_amount=120000.0,
        loan_purpose="Business Start",
        has_id=True,
        has_proof_of_income=True,
        has_bank_statement=True
    )
    
    list(app.stream(state, config))
    
    final_state = app.get_state(config)
    values = final_state.values
    
    assert values["status"] == "REJECTED"
    assert values["current_stage"] == "rejected"
    assert "exceeds maximum limit of 4.5" in values["rejection_reason"]


def test_manual_review_routing_and_approval(test_app):
    """Test routing to manual review, pausing, and resuming after manager approval."""
    app, conn = test_app
    config = {"configurable": {"thread_id": "test-thread-6"}}
    
    # Frank: Large loan amount ($40,000 >= $25,000) so cannot auto-approve.
    # Risk score will be 40 (passes risk and eligibility)
    state = create_initial_state(
        applicant_name="Frank Wright",
        applicant_age=28,
        employment_tenure_months=18,
        credit_score=700,             # Credit < 750 (-10 risk)
        monthly_income=6000.0,
        monthly_debt=1800.0,          # DTI 30% (no risk modification)
        loan_amount=40000.0,          # Large amount, triggers manual review
        loan_purpose="Medical Bills",
        has_id=True,
        has_proof_of_income=True,
        has_bank_statement=True
    )
    
    # Run the graph. It should pause because of the interrupt before 'pending_review'
    events = list(app.stream(state, config))
    
    # Verify it paused and is waiting at pending_review
    state_after_pause = app.get_state(config)
    assert state_after_pause.values["status"] == "pending_review"
    assert state_after_pause.values["manager_decision"] == "PENDING"
    assert state_after_pause.next == ("pending_review",)
    
    # Verify 'pending_review' has not executed yet
    nodes_run = [event_key for event in events for event_key in event.keys()]
    assert "manager_approval" in nodes_run
    assert "pending_review" not in nodes_run
    
    # Simulate a manager updating state and approving the loan
    app.update_state(
        config,
        {
            "manager_decision": "APPROVED",
            "manager_notes": "Frank has stable employment and good collateral."
        }
    )
    
    # Resume the graph from checkpoint (None input signals resumption)
    resume_events = list(app.stream(None, config))
    
    # Verify the remaining nodes run and final state is approved
    resume_nodes = [event_key for event in resume_events for event_key in event.keys()]
    assert "pending_review" in resume_nodes
    assert "final_decision" in resume_nodes
    
    final_state = app.get_state(config)
    assert final_state.values["status"] == "APPROVED"
    assert final_state.values["current_stage"] == "final_decision"
    
    # Verify audit trail contains manager's notes
    audit = final_state.values["audit_trail"]
    manager_review_log = next(log for log in audit if log["node"] == "pending_review")
    assert manager_review_log["action"] == "MANUALLY_APPROVED"
    assert "stable employment" in manager_review_log["message"]


def test_manual_review_routing_and_rejection(test_app):
    """Test routing to manual review, pausing, and resuming after manager rejection."""
    app, conn = test_app
    config = {"configurable": {"thread_id": "test-thread-7"}}
    
    state = create_initial_state(
        applicant_name="Grace Hopper",
        applicant_age=31,
        employment_tenure_months=20,
        credit_score=710,
        monthly_income=8000.0,
        monthly_debt=2400.0,
        loan_amount=50000.0,
        loan_purpose="Business Launch",
        has_id=True,
        has_proof_of_income=True,
        has_bank_statement=True
    )
    
    # Run to pause
    list(app.stream(state, config))
    
    # Simulate manager rejection
    app.update_state(
        config,
        {
            "manager_decision": "REJECTED",
            "manager_notes": "Business plan lacks detail."
        }
    )
    
    # Resume graph
    list(app.stream(None, config))
    
    final_state = app.get_state(config)
    assert final_state.values["status"] == "REJECTED"
    assert final_state.values["current_stage"] == "rejected"
    assert "Rejected by manager: Business plan lacks detail." in final_state.values["rejection_reason"]
    
    audit = final_state.values["audit_trail"]
    manager_review_log = next(log for log in audit if log["node"] == "pending_review")
    assert manager_review_log["action"] == "MANUALLY_REJECTED"


def test_audit_trail_sequencing(test_app):
    """Test audit trail correctness, ensuring the right entries are created in the right sequential order."""
    app, conn = test_app
    config = {"configurable": {"thread_id": "test-thread-8"}}
    
    state = create_initial_state(
        applicant_name="Audit Tester",
        applicant_age=25,
        employment_tenure_months=24,
        credit_score=780,
        monthly_income=7000.0,
        monthly_debt=500.0,
        loan_amount=10000.0,
        loan_purpose="Furniture",
        has_id=True,
        has_proof_of_income=True,
        has_bank_statement=True
    )
    
    list(app.stream(state, config))
    
    final_state = app.get_state(config)
    audit = final_state.values["audit_trail"]
    
    # Expecting: collect_application -> verify_documents -> risk_assessment -> eligibility_check -> manager_approval -> final_decision
    assert len(audit) == 6
    assert audit[0]["node"] == "collect_application"
    assert audit[0]["action"] == "PASSED_VALIDATION"
    
    assert audit[1]["node"] == "verify_documents"
    assert audit[1]["action"] == "PASSED_VERIFICATION"
    
    assert audit[2]["node"] == "risk_assessment"
    assert audit[2]["action"] == "PASSED_RISK_ASSESSMENT"
    
    assert audit[3]["node"] == "eligibility_check"
    assert audit[3]["action"] == "PASSED_ELIGIBILITY"
    
    assert audit[4]["node"] == "manager_approval"
    assert audit[4]["action"] == "AUTO_APPROVED"
    
    assert audit[5]["node"] == "final_decision"
    assert audit[5]["action"] == "LOAN_APPROVED"
    
    # Verify timestamps are in chronological order
    for i in range(len(audit) - 1):
        assert audit[i]["timestamp"] <= audit[i+1]["timestamp"]
