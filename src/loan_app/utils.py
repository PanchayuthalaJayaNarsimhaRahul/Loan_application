import sqlite3
import datetime
from typing import List, Dict, Any, Optional

def init_db(db_path: str) -> None:
    """Initialize the metadata database and ensure the required table exists."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS loan_applications (
            thread_id TEXT PRIMARY KEY,
            applicant_name TEXT NOT NULL,
            loan_amount REAL NOT NULL,
            status TEXT NOT NULL,
            current_stage TEXT NOT NULL,
            risk_score REAL,
            rejection_reason TEXT,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_application(db_path: str, thread_id: str, state: Dict[str, Any]) -> None:
    """
    Extract critical fields from the LangGraph State dictionary and persist 
    them to the queryable loan_applications SQLite metadata table.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    applicant_name = state.get("applicant_name", "Unknown")
    loan_amount = state.get("loan_amount", 0.0)
    status = state.get("status", "Unknown")
    current_stage = state.get("current_stage", "Unknown")
    risk_score = state.get("risk_score")
    rejection_reason = state.get("rejection_reason")
    updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    cursor.execute("""
        INSERT OR REPLACE INTO loan_applications 
        (thread_id, applicant_name, loan_amount, status, current_stage, risk_score, rejection_reason, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (thread_id, applicant_name, loan_amount, status, current_stage, risk_score, rejection_reason, updated_at))
    conn.commit()
    conn.close()

def list_applications(db_path: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """List metadata for all submitted loan applications, optionally filtered by status."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if status:
        cursor.execute("SELECT * FROM loan_applications WHERE status = ? ORDER BY updated_at DESC", (status,))
    else:
        cursor.execute("SELECT * FROM loan_applications ORDER BY updated_at DESC")
        
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_application(db_path: str, thread_id: str) -> Optional[Dict[str, Any]]:
    """Fetch application metadata by thread ID."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM loan_applications WHERE thread_id = ?", (thread_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
