
from datetime import datetime, timezone
import hmac
import json
import math
import os
import sqlite3

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from backend.db import get_connection, init_db


MAX_AUTO_REFUND = 5000.0


def authenticate_customer(authorization: str | None = Header(default=None)) -> str:
    """Resolve the authenticated customer from a configured bearer token.

    CUSTOMER_API_TOKENS must be a JSON object mapping customer MSISDNs to
    high-entropy bearer tokens. Tokens are never accepted from query params.
    """
    raw_tokens = os.environ.get("CUSTOMER_API_TOKENS", "")
    try:
        tokens = json.loads(raw_tokens)
    except (TypeError, ValueError):
        tokens = None

    if not isinstance(tokens, dict) or not tokens:
        raise HTTPException(status_code=503, detail="Customer authentication is not configured")

    scheme, _, supplied = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not supplied:
        raise HTTPException(status_code=401, detail="A bearer token is required")

    for msisdn, expected in tokens.items():
        if isinstance(msisdn, str) and isinstance(expected, str) and hmac.compare_digest(supplied, expected):
            return msisdn

    raise HTTPException(status_code=401, detail="Invalid bearer token")

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
def get_transaction(txn_id: str, customer_msisdn: str = Depends(authenticate_customer)):
    connection = get_connection()

    try:
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

        if transaction is None:
            raise HTTPException(
                status_code=404,
                detail="Transaction not found",
            )

        if transaction["msisdn"] != customer_msisdn:
            raise HTTPException(status_code=404, detail="Transaction not found")

        return dict(transaction)
    finally:
        connection.close()


# ============================================================
# 2. GET CUSTOMER TRANSACTIONS
# ============================================================

@app.get("/transactions")
def get_customer_transactions(customer_msisdn: str = Depends(authenticate_customer)):
    connection = get_connection()

    try:
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
            (customer_msisdn,),
        )

        transactions = cursor.fetchall()
        return [dict(transaction) for transaction in transactions]
    finally:
        connection.close()


# ============================================================
# 3. GET WALLET BALANCE
# ============================================================

@app.get("/wallet/{msisdn}")
def get_wallet(msisdn: str, customer_msisdn: str = Depends(authenticate_customer)):
    if msisdn != customer_msisdn:
        raise HTTPException(status_code=404, detail="Wallet not found")
    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT msisdn, balance
            FROM wallets
            WHERE msisdn = ?
            """,
            (msisdn,),
        )

        wallet = cursor.fetchone()

        if wallet is None:
            raise HTTPException(
                status_code=404,
                detail="Wallet not found",
            )

        return dict(wallet)
    finally:
        connection.close()


# ============================================================
# 4. CHECK EXISTING REVERSAL
# ============================================================

@app.get("/reversals/{txn_id}")
def check_reversal(txn_id: str, customer_msisdn: str = Depends(authenticate_customer)):
    connection = get_connection()

    try:
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

        cursor.execute("SELECT msisdn FROM transactions WHERE txn_id = ?", (txn_id,))
        transaction = cursor.fetchone()
        if transaction is None or transaction["msisdn"] != customer_msisdn:
            raise HTTPException(status_code=404, detail="Transaction not found")

        return {
            "txn_id": txn_id,
            "reversal_exists": reversal is not None,
            "reversal": dict(reversal) if reversal else None,
        }
    finally:
        connection.close()


# ============================================================
# 5. CREATE REVERSAL — SERVER-SIDE SAFETY CHECKS
# ============================================================

class ReversalRequest(BaseModel):
    txn_id: str = Field(min_length=1)
    amount: float = Field(gt=0, allow_inf_nan=False)
    reason: str = Field(min_length=1)


@app.post("/reversals")
def create_reversal(request: ReversalRequest, customer_msisdn: str = Depends(authenticate_customer)):
    connection = get_connection()

    try:
        # Acquire a write lock before checking eligibility and duplicates.
        # This helps prevent two concurrent requests creating two reversals.
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.cursor()

        # Rule 1: Transaction must exist.
        cursor.execute(
            """
            SELECT
                txn_id,
                msisdn,
                amount,
                status,
                debited,
                credited_to_receiver
            FROM transactions
            WHERE txn_id = ?
            """,
            (request.txn_id,),
        )

        transaction = cursor.fetchone()

        if transaction is None:
            raise HTTPException(
                status_code=404,
                detail="Transaction not found",
            )

        transaction = dict(transaction)

        if transaction["msisdn"] != customer_msisdn:
            raise HTTPException(status_code=404, detail="Transaction not found")

        # Rule 2: Only failed transactions qualify.
        if transaction["status"] != "FAILED":
            raise HTTPException(
                status_code=409,
                detail="Only failed transactions can be reversed",
            )

        # Rule 3: Money must have been debited.
        if not transaction["debited"]:
            raise HTTPException(
                status_code=409,
                detail="No debit was recorded for this transaction",
            )

        # Rule 4: Receiver must not have been credited.
        if transaction["credited_to_receiver"]:
            raise HTTPException(
                status_code=409,
                detail="Receiver was credited; reversal is not permitted",
            )

        # Rule 5: Requested amount must match the database amount.
        actual_amount = float(transaction["amount"])

        if not math.isclose(
            request.amount,
            actual_amount,
            rel_tol=0.0,
            abs_tol=0.000001,
        ):
            raise HTTPException(
                status_code=400,
                detail="Requested amount does not match the transaction amount",
            )

        # Rule 6: Amounts above ₹5,000 need human approval.
        if actual_amount > MAX_AUTO_REFUND:
            raise HTTPException(
                status_code=403,
                detail="Refunds above ₹5000 require human approval",
            )

        # Rule 7: Never create a duplicate reversal.
        cursor.execute(
            """
            SELECT id
            FROM reversals
            WHERE txn_id = ?
            """,
            (request.txn_id,),
        )

        if cursor.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail="Reversal already exists for this transaction",
            )

        # All eligibility checks passed. Record the reversal request.
        # This mock operation does not update wallet balances or connect
        # to a real payment network.
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
                actual_amount,
                request.reason.strip(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        reversal_id = cursor.lastrowid
        connection.commit()

        return {
            "success": True,
            "message": "Reversal record created successfully",
            "reversal_id": reversal_id,
            "txn_id": request.txn_id,
            "amount": actual_amount,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# ============================================================
# 6. CREATE ESCALATION
# ============================================================

class EscalationRequest(BaseModel):
    txn_id: str | None = None
    msisdn: str = Field(min_length=1)
    reason: str = Field(min_length=1)


@app.post("/escalations")
def create_escalation(request: EscalationRequest, customer_msisdn: str = Depends(authenticate_customer)):
    if request.msisdn != customer_msisdn:
        raise HTTPException(status_code=403, detail="Customer does not match authenticated account")
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # If a transaction is supplied, verify that it belongs to the
        # MSISDN included in the escalation request.
        if request.txn_id:
            cursor.execute(
                """
                SELECT msisdn
                FROM transactions
                WHERE txn_id = ?
                """,
                (request.txn_id,),
            )

            transaction = cursor.fetchone()

            if transaction is None:
                raise HTTPException(
                    status_code=404,
                    detail="Transaction not found",
                )

            if transaction["msisdn"] != request.msisdn:
                raise HTTPException(
                    status_code=403,
                    detail="Transaction does not belong to this customer",
                )

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
                request.reason.strip(),
                "OPEN",
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        escalation_id = cursor.lastrowid
        connection.commit()

        return {
            "success": True,
            "message": "Case escalated to human agent",
            "escalation_id": escalation_id,
            "status": "OPEN",
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
