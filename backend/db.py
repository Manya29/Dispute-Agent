import sqlite3
from pathlib import Path


# Path of our SQLite database file
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "dispute_agent.db"


def get_connection():
    """
    Create and return a connection to the SQLite database.
    """
    connection = sqlite3.connect(DB_PATH)

    # Allows us to access database rows like dictionaries
    connection.row_factory = sqlite3.Row

    return connection


def init_db():
    """
    Create all required database tables if they don't already exist.
    """

    connection = get_connection()
    cursor = connection.cursor()

    # Transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            txn_id TEXT PRIMARY KEY,
            msisdn TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            debited INTEGER NOT NULL,
            credited_to_receiver INTEGER NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    # Reversals table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reversals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_id TEXT NOT NULL UNIQUE,
            amount REAL NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Escalations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_id TEXT,
            msisdn TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Wallets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wallets (
            msisdn TEXT PRIMARY KEY,
            balance REAL NOT NULL
        )
    """)

    connection.commit()
    connection.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized successfully at: {DB_PATH}")