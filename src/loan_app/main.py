import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import uuid
import argparse
from dotenv import load_dotenv
from tabulate import tabulate

from src.loan_app.state import create_initial_state
from src.loan_app.utils import init_db, save_application, list_applications, get_application
from src.loan_app.graph import create_graph
from src.loan_app.checkpoint import get_checkpointer

def get_app_context():
    """Initializes environment, database, and compiles the LangGraph workflow."""
    load_dotenv()
    db_path = os.getenv("CHECKPOINT_DB_PATH", os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/loan_workflow.db')))
    init_db(db_path)
    
    # Get checkpointer and connection from the checkpoint module
    checkpointer, conn = get_checkpointer(db_path)
    app = create_graph(checkpointer)
    return app, conn, db_path


def format_audit_trail(audit_trail):
    """Formats the audit trail for display."""
    if not audit_trail:
        return "No audit logs recorded."
    
    table_data = []
    for entry in audit_trail:
        table_data.append([
            entry.get("node", ""),
            entry.get("timestamp", ""),
            entry.get("action", ""),
            entry.get("message", "")
        ])
    return tabulate(table_data, headers=["Node/Stage", "Timestamp", "Action", "Detail/Reason"], tablefmt="grid")


def cmd_submit(args):
    """Submits a new loan application and starts the workflow."""
    app, conn, db_path = get_app_context()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"==================================================")
    print(f"Submitting Loan Application (Thread ID: {thread_id})")
    print(f"Applicant: {args.name}, Age: {args.age}, Amount: ${args.amount:,}")
    print(f"==================================================")
    
    initial_state = create_initial_state(
        applicant_name=args.name,
        applicant_age=args.age,
        employment_tenure_months=args.tenure,
        credit_score=args.credit,
        monthly_income=args.income,
        monthly_debt=args.debt,
        loan_amount=args.amount,
        loan_purpose=args.purpose,
        has_id=args.has_id,
        has_proof_of_income=args.has_income,
        has_bank_statement=args.has_bank
    )
    
    try:
        # Run workflow nodes sequentially (streaming execution events)
        for event in app.stream(initial_state, config):
            for node_name, node_state in event.items():
                print(f"\n>>> Executing Node: [{node_name}]")
                if "audit_trail" in node_state and node_state["audit_trail"]:
                    latest = node_state["audit_trail"][-1]
                    print(f"    Action: {latest['action']}")
                    print(f"    Message: {latest['message']}")
                    
        # Retrieve final state after this run segment completes (or pauses)
        final_state = app.get_state(config)
        state_values = final_state.values
        
        # Save current state summary to metadata table
        save_application(db_path, thread_id, state_values)
        
        print(f"\n==================================================")
        print(f"Application Status: {state_values.get('status').upper()}")
        print(f"Current Stage: {state_values.get('current_stage')}")
        if state_values.get("status") == "REJECTED":
            print(f"Reason for Rejection: {state_values.get('rejection_reason')}")
        elif state_values.get("status") == "pending_review":
            print(f"ACTION REQUIRED: Application is paused. A manager must review it.")
            print(f"Run CLI command to review: python main.py review --thread-id {thread_id} --decision APPROVED/REJECTED --notes '...'")
        print(f"==================================================")
        
    finally:
        conn.close()


def cmd_list(args):
    """Lists applications, optionally filtered by status."""
    app, conn, db_path = get_app_context()
    try:
        apps = list_applications(db_path, status=args.status)
        if not apps:
            filter_msg = f" with status '{args.status}'" if args.status else ""
            print(f"No applications found{filter_msg}.")
            return
        
        table_data = []
        for a in apps:
            table_data.append([
                a["thread_id"],
                a["applicant_name"],
                f"${a['loan_amount']:,.2f}",
                a["status"].upper(),
                a["current_stage"],
                f"{a['risk_score']:.1f}" if a["risk_score"] is not None else "N/A",
                a["updated_at"]
            ])
            
        print(tabulate(table_data, headers=["Thread ID", "Applicant", "Amount", "Status", "Current Stage", "Risk Score", "Last Updated"], tablefmt="simple"))
    finally:
        conn.close()


def cmd_review(args):
    """Resumes a paused loan application with a manager's decision."""
    app, conn, db_path = get_app_context()
    thread_id = args.thread_id
    config = {"configurable": {"thread_id": thread_id}}
    
    meta = get_application(db_path, thread_id)
    if not meta:
        print(f"Error: Application with Thread ID {thread_id} not found in metadata database.")
        conn.close()
        sys.exit(1)
        
    if meta["status"] != "pending_review":
        print(f"Warning: Application status is currently '{meta['status']}', not 'pending_review'.")
        print("Resuming execution might use current values or fail if already completed.")
        
    print(f"==================================================")
    print(f"Reviewing Loan Application (Thread ID: {thread_id})")
    print(f"Applicant: {meta['applicant_name']}, Amount: ${meta['loan_amount']:,}")
    print(f"Manager Decision: {args.decision}")
    print(f"Manager Notes: {args.notes}")
    print(f"==================================================")
    
    try:
        # Update state with manager review details
        app.update_state(
            config,
            {
                "manager_decision": args.decision,
                "manager_notes": args.notes
            }
        )
        
        # Resume the workflow stream from the pause checkpoint (None input signals resumption)
        for event in app.stream(None, config):
            for node_name, node_state in event.items():
                print(f"\n>>> Resuming & Executing Node: [{node_name}]")
                if "audit_trail" in node_state and node_state["audit_trail"]:
                    latest = node_state["audit_trail"][-1]
                    print(f"    Action: {latest['action']}")
                    print(f"    Message: {latest['message']}")
                    
        # Update metadata table with the new finalized state
        final_state = app.get_state(config)
        state_values = final_state.values
        save_application(db_path, thread_id, state_values)
        
        print(f"\n==================================================")
        print(f"Final Application Status: {state_values.get('status').upper()}")
        print(f"Current Stage: {state_values.get('current_stage')}")
        if state_values.get("status") == "REJECTED":
            print(f"Reason for Rejection: {state_values.get('rejection_reason')}")
        print(f"==================================================")
        
    finally:
        conn.close()


def cmd_view(args):
    """Displays full application details and audit trail."""
    app, conn, db_path = get_app_context()
    thread_id = args.thread_id
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # Fetch current graph state values
        state_data = app.get_state(config)
        if not state_data or not state_data.values:
            # Fallback to metadata db if not in checkpoint saver
            meta = get_application(db_path, thread_id)
            if not meta:
                print(f"Error: Application with Thread ID {thread_id} not found.")
                return
            print(f"Application metadata found, but no checkpoints exist in the state saver.")
            print(f"Name: {meta['applicant_name']}, Amount: ${meta['loan_amount']:,}, Status: {meta['status']}")
            return
            
        values = state_data.values
        print(f"==================================================")
        print(f"Loan Application Detail")
        print(f"==================================================")
        print(f"Thread ID:        {thread_id}")
        print(f"Applicant Name:   {values.get('applicant_name')}")
        print(f"Applicant Age:    {values.get('applicant_age')}")
        print(f"Employment:       {values.get('employment_tenure_months')} months tenure")
        print(f"Credit Score:     {values.get('credit_score')}")
        print(f"Monthly Income:   ${values.get('monthly_income'):,.2f}")
        print(f"Monthly Debt:     ${values.get('monthly_debt'):,.2f}")
        print(f"Loan Amount:      ${values.get('loan_amount'):,.2f}")
        print(f"Loan Purpose:     {values.get('loan_purpose')}")
        print(f"--------------------------------------------------")
        print(f"Documents Submitted:")
        print(f"  - Government ID:      {'YES' if values.get('has_id') else 'NO'}")
        print(f"  - Proof of Income:    {'YES' if values.get('has_proof_of_income') else 'NO'}")
        print(f"  - Bank Statement:     {'YES' if values.get('has_bank_statement') else 'NO'}")
        print(f"--------------------------------------------------")
        print(f"Analysis & Decisions:")
        risk_score = values.get('risk_score')
        risk_score_str = f"{risk_score:.1f}/100" if risk_score is not None else "N/A"
        print(f"  - Calculated Risk Score: {risk_score_str}")
        print(f"  - Manager Decision:      {values.get('manager_decision') or 'None'}")
        print(f"  - Manager Notes:         {values.get('manager_notes') or 'N/A'}")
        print(f"  - Rejection Reason:      {values.get('rejection_reason') or 'N/A'}")
        print(f"  - Current Workflow Node: {values.get('current_stage')}")
        print(f"  - Final Decision Status: {values.get('status').upper()}")
        print(f"==================================================")
        print(f"Audit Trail:")
        print(format_audit_trail(values.get("audit_trail", [])))
        print(f"==================================================")
        
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Loan Application Processing Workflow (LangGraph)")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Subcommands")
    
    # Submit Subcommand
    p_submit = subparsers.add_parser("submit", help="Submit a new loan application")
    p_submit.add_argument("--name", required=True, help="Applicant name")
    p_submit.add_argument("--age", type=int, required=True, help="Applicant age")
    p_submit.add_argument("--tenure", type=int, required=True, help="Employment tenure in months")
    p_submit.add_argument("--credit", type=int, required=True, help="Credit score (300-850)")
    p_submit.add_argument("--income", type=float, required=True, help="Monthly income in USD")
    p_submit.add_argument("--debt", type=float, required=True, help="Monthly debt in USD")
    p_submit.add_argument("--amount", type=float, required=True, help="Requested loan amount")
    p_submit.add_argument("--purpose", required=True, help="Purpose of the loan")
    p_submit.add_argument("--has-id", action="store_true", help="Applicant submitted government ID")
    p_submit.add_argument("--has-income", action="store_true", help="Applicant submitted proof of income")
    p_submit.add_argument("--has-bank", action="store_true", help="Applicant submitted bank statement")
    
    # List Subcommand
    p_list = subparsers.add_parser("list", help="List all applications in the database")
    p_list.add_argument("--status", choices=["collecting", "verifying", "assessing_risk", "checking_eligibility", "pending_review", "APPROVED", "REJECTED"], help="Filter applications by status")
    
    # Review Subcommand
    p_review = subparsers.add_parser("review", help="Submit manager review and resume paused application")
    p_review.add_argument("--thread-id", required=True, help="Application thread ID to resume")
    p_review.add_argument("--decision", required=True, choices=["APPROVED", "REJECTED"], help="Manager's decision")
    p_review.add_argument("--notes", required=True, help="Manager's assessment notes")
    
    # View Subcommand
    p_view = subparsers.add_parser("view", help="View full details and audit logs for an application")
    p_view.add_argument("--thread-id", required=True, help="Application thread ID to view")
    
    args = parser.parse_args()
    
    if args.command == "submit":
        cmd_submit(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "review":
        cmd_review(args)
    elif args.command == "view":
        cmd_view(args)


if __name__ == "__main__":
    main()
