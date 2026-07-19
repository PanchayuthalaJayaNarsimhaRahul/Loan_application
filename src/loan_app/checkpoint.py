import sqlite3
# pyrefly: ignore [missing-import]
from langgraph.checkpoint.sqlite import SqliteSaver

def get_checkpointer(db_path: str):
    """
    Creates and sets up the SQLite checkpointer for LangGraph state persistence.
    Returns both the SqliteSaver checkpointer and the connection object.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()
    return checkpointer, conn
