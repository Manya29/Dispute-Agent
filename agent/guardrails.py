
from datetime import datetime, timezone

from tools import get_transaction, check_reversal

MAX_AUTO_REFUND = 5000
PENDING_WAIT_HOURS = 24


def parse_timestamp(value: str):
    """Parse an ISO timestamp and normalize it to UTC."""
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        return timestamp.astimezone(timezone.utc)
    except (ValueError, AttributeError, TypeError):
        return None


def validate_refund(txn_id: str, user_msisdn: str) -> dict:
    """Check refund eligibility without issuing a refund."""
    transaction = get_transaction(txn_id)

    if "error" in transaction:
        return {
            "allowed": False,
            "decision": "NEED_INFO",
            "reason": transaction["error"],
        }

    if transaction.get("msisdn") != user_msisdn:
        return {
            "allowed": False,
            "decision": "REJECTED",
            "reason": "This transaction does not belong to the customer.",
        }

    status = transaction.get("status")

    if status == "PENDING":
        timestamp = parse_timestamp(transaction.get("timestamp"))

        if timestamp is None:
            return {
                "allowed": False,
                "decision": "NEED_INFO",
                "reason": "Could not verify the transaction timestamp.",
            }

        age = datetime.now(timezone.utc) - timestamp

        if age.total_seconds() < 0:
            return {
                "allowed": False,
                "decision": "NEED_INFO",
                "reason": "The transaction timestamp is in the future.",
            }

        if age.total_seconds() < PENDING_WAIT_HOURS * 3600:
            return {
                "allowed": False,
                "decision": "WAIT",
                "reason": (
                    "The transaction has been pending for less than "
                    "24 hours. Ask the customer to wait."
                ),
            }

        return {
            "allowed": False,
            "decision": "ESCALATED",
            "reason": (
                "The transaction has been pending for 24 hours or more "
                "and requires human investigation."
            ),
        }

    if status != "FAILED":
        return {
            "allowed": False,
            "decision": "REJECTED",
            "reason": "Only failed transactions can be considered for a refund.",
        }

    if not transaction.get("debited"):
        return {
            "allowed": False,
            "decision": "REJECTED",
            "reason": "No debit was recorded for this transaction.",
        }

    if transaction.get("credited_to_receiver"):
        return {
            "allowed": False,
            "decision": "REJECTED",
            "reason": "The receiver was credited, so the refund criteria are not met.",
        }

    reversal = check_reversal(txn_id)

    if "error" in reversal:
        return {
            "allowed": False,
            "decision": "NEED_INFO",
            "reason": (
                "Could not verify whether a reversal already exists. "
                "No refund is allowed until this is checked."
            ),
        }

    if reversal.get("reversal_exists"):
        return {
            "allowed": False,
            "decision": "REJECTED",
            "reason": "A reversal already exists for this transaction.",
        }

    amount = transaction.get("amount")

    if not isinstance(amount, (int, float)) or amount <= 0:
        return {
            "allowed": False,
            "decision": "NEED_INFO",
            "reason": "The transaction amount is missing or invalid.",
        }

    if amount > MAX_AUTO_REFUND:
        return {
            "allowed": False,
            "decision": "ESCALATED",
            "reason": "Refunds above ₹5000 require human approval.",
        }

    return {
        "allowed": True,
        "decision": "REFUND_CANDIDATE",
        "reason": "Transaction passed the automatic-refund eligibility checks.",
        "txn_id": txn_id,
        "amount": amount,
    }


if __name__ == "__main__":
    tests = [
        ("Valid refund", "TXN001", "9876543210"),
        ("Successful transaction", "TXN002", "9876543210"),
        ("Pending transaction", "TXN003", "9876543210"),
        ("Already reversed", "TXN004", "9123456780"),
        ("High-value refund", "TXN005", "9123456780"),
        ("Wrong customer", "TXN001", "9123456780"),
        ("Missing transaction", "TXN999", "9876543210"),
    ]

    for name, txn_id, msisdn in tests:
        print(f"\n--- {name} ---")
        print(validate_refund(txn_id, msisdn))
