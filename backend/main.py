from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.db import get_connection, init_db


app = FastAPI(
    title="Mobile Money Dispute Backend",
    description="Mock backend for the dispute resolution agent",
)


@app.on_event("startup")
def startup():
    init_db()


# ============================================================
# 1. GET ONE TRANSACTION
# ============================================================

@app.get("/transactions/{txn_id}")
def get_transaction(txn_id: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            txn_id,
            msisdn,
            amount,
            status,
            debited,
            credited_to_receiver,
            timestamp
        FROM transactions
        WHERE txn_id = ?
        """,
        (txn_id,),
    )

    transaction = cursor.fetchone()
    connection.close()

    if transaction is None:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found",
        )

    return dict(transaction)


# ============================================================
# 2. GET CUSTOMER TRANSACTIONS
# ============================================================

@app.get("/transactions")
def get_customer_transactions(msisdn: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            txn_id,
            msisdn,
            amount,
            status,
            debited,
            credited_to_receiver,
            timestamp
        FROM transactions
        WHERE msisdn = ?
        ORDER BY timestamp DESC
        """,
        (msisdn,),
    )

    transactions = cursor.fetchall()
    connection.close()

    return [dict(transaction) for transaction in transactions]


# ============================================================
# 3. GET WALLET BALANCE
# ============================================================

@app.get("/wallet/{msisdn}")
def get_wallet(msisdn: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            msisdn,
            balance
        FROM wallets
        WHERE msisdn = ?
        """,
        (msisdn,),
    )

    wallet = cursor.fetchone()
    connection.close()

    if wallet is None:
        raise HTTPException(
            status_code=404,
            detail="Wallet not found",
        )

    return dict(wallet)


# ============================================================
# 4. CHECK EXISTING REVERSAL
# ============================================================

@app.get("/reversals/{txn_id}")
def check_reversal(txn_id: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            txn_id,
            amount,
            reason,
            created_at
        FROM reversals
        WHERE txn_id = ?
        """,
        (txn_id,),
    )

    reversal = cursor.fetchone()
    connection.close()

    return {
        "txn_id": txn_id,
        "reversal_exists": reversal is not None,
        "reversal": dict(reversal) if reversal else None,
    }


# ============================================================
# 5. CREATE REVERSAL
# ============================================================

class ReversalRequest(BaseModel):
    txn_id: str
    amount: float
    reason: str


@app.post("/reversals")
def create_reversal(request: ReversalRequest):
    connection = get_connection()
    cursor = connection.cursor()

    # Check whether transaction exists
    cursor.execute(
        """
        SELECT *
        FROM transactions
        WHERE txn_id = ?
        """,
        (request.txn_id,),
    )

    transaction = cursor.fetchone()

    if transaction is None:
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="Transaction not found",
        )

    # Check whether reversal already exists
    cursor.execute(
        """
        SELECT *
        FROM reversals
        WHERE txn_id = ?
        """,
        (request.txn_id,),
    )

    existing_reversal = cursor.fetchone()

    if existing_reversal is not None:
        connection.close()

        raise HTTPException(
            status_code=409,
            detail="Reversal already exists for this transaction",
        )

    # Create reversal
    cursor.execute(
        """
        INSERT INTO reversals (
            txn_id,
            amount,
            reason,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            request.txn_id,
            request.amount,
            request.reason,
            datetime.now().isoformat(),
        ),
    )

    connection.commit()

    reversal_id = cursor.lastrowid

    connection.close()

    return {
        "success": True,
        "message": "Reversal created successfully",
        "reversal_id": reversal_id,
        "txn_id": request.txn_id,
        "amount": request.amount,
    }


# ============================================================
# 6. CREATE ESCALATION
# ============================================================

class EscalationRequest(BaseModel):
    txn_id: str | None = None
    msisdn: str
    reason: str


@app.post("/escalations")
def create_escalation(request: EscalationRequest):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO escalations (
            txn_id,
            msisdn,
            reason,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            request.txn_id,
            request.msisdn,
            request.reason,
            "OPEN",
            datetime.now().isoformat(),
        ),
    )

    connection.commit()

    escalation_id = cursor.lastrowid

    connection.close()

    return {
        "success": True,
        "message": "Case escalated to human agent",
        "escalation_id": escalation_id,
        "status": "OPEN",
    }