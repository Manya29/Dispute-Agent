
from tools import get_transaction, check_reversal


MAX_AUTO_REFUND = 5000


def validate_refund(txn_id: str, user_msisdn: str) -> dict:
    """
    Check whether a transaction is eligible for an automatic refund.

    This function validates the request; it does not issue a refund.
    """

    # 1. Fetch the transaction
    transaction = get_transaction(txn_id)

    if "error" in transaction:
        return {
            "allowed": False,
            "decision": "NEED_INFO",
            "reason": transaction["error"],
        }

    # 2. Verify customer ownership
    if transaction["msisdn"] != user_msisdn:
        return {
            "allowed": False,
            "decision": "REJECTED",
            "reason": "This transaction does not belong to the customer.",
        }

    # 3. Only failed transactions are eligible
    if transaction["status"] != "FAILED":
        if transaction["status"] == "PENDING":
            return {
                "allowed": False,
                "decision": "WAIT",
                "reason": "The transaction is pending. Check its age before advising the customer to wait.",
            }

        return {
            "allowed": False,
            "decision": "REJECTED",
            "reason": "Only failed transactions can be considered for a refund.",
        }

    # 4. Verify money was debited
    if not transaction["debited"]:
        return {
            "allowed": False,
            "decision": "REJECTED",
            "reason": "No debit was recorded for this transaction.",
        }

    # 5. Verify the receiver was not credited
    if transaction["credited_to_receiver"]:
        return {
            "allowed": False,
            "decision": "REJECTED",
            "reason": "The receiver was credited, so the refund criteria are not met.",
        }

    # 6. Check for an existing reversal
    reversal = check_reversal(txn_id)

    if "error" in reversal:
        return {
            "allowed": False,
            "decision": "NEED_INFO",
            "reason": "Could not verify whether a reversal already exists. No refund is allowed until this is checked.",
        }

    if reversal.get("reversal_exists"):
        return {
            "allowed": False,
            "decision": "REJECTED",
            "reason": "A reversal already exists for this transaction.",
        }

    # 7. High-value refunds require human approval
    if transaction["amount"] > MAX_AUTO_REFUND:
        return {
            "allowed": False,
            "decision": "ESCALATED",
            "reason": "Refunds above ₹5000 require human approval.",
        }

    # All automatic-refund conditions passed
    return {
        "allowed": True,
        "decision": "REFUND_CANDIDATE",
        "reason": "Transaction passed the automatic-refund eligibility checks.",
        "txn_id": txn_id,
        "amount": transaction["amount"],
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
