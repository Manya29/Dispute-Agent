
import requests

BACKEND_URL = "http://127.0.0.1:8000"
TIMEOUT = 10


def handle_response(response):
    """Convert an HTTP response into JSON or a readable error."""
    try:
        response.raise_for_status()
        return response.json()
    except requests.HTTPError:
        try:
            return {
                "error": response.json().get("detail", response.text),
                "status_code": response.status_code,
            }
        except ValueError:
            return {
                "error": response.text,
                "status_code": response.status_code,
            }
    except requests.RequestException as error:
        return {"error": str(error)}


def get_transaction(txn_id: str):
    """Fetch one transaction by its ID."""
    try:
        response = requests.get(
            f"{BACKEND_URL}/transactions/{txn_id}",
            timeout=TIMEOUT,
        )
        return handle_response(response)
    except requests.RequestException as error:
        return {"error": str(error)}


def get_customer_transactions(msisdn: str):
    """Fetch transactions belonging to a customer."""
    try:
        response = requests.get(
            f"{BACKEND_URL}/transactions",
            params={"msisdn": msisdn},
            timeout=TIMEOUT,
        )
        return handle_response(response)
    except requests.RequestException as error:
        return {"error": str(error)}


def get_wallet(msisdn: str):
    """Fetch a customer's wallet balance."""
    try:
        response = requests.get(
            f"{BACKEND_URL}/wallet/{msisdn}",
            timeout=TIMEOUT,
        )
        return handle_response(response)
    except requests.RequestException as error:
        return {"error": str(error)}


def check_reversal(txn_id: str):
    """Check whether a transaction already has a reversal."""
    try:
        response = requests.get(
            f"{BACKEND_URL}/reversals/{txn_id}",
            timeout=TIMEOUT,
        )
        return handle_response(response)
    except requests.RequestException as error:
        return {"error": str(error)}


def create_reversal(txn_id: str, amount: float, reason: str):
    """Request a reversal from the backend.

    Business-rule guardrails will be added separately before
    this function is exposed to the AI agent.
    """
    try:
        response = requests.post(
            f"{BACKEND_URL}/reversals",
            json={
                "txn_id": txn_id,
                "amount": amount,
                "reason": reason,
            },
            timeout=TIMEOUT,
        )
        return handle_response(response)
    except requests.RequestException as error:
        return {"error": str(error)}


def create_escalation(
    msisdn: str,
    reason: str,
    txn_id: str | None = None,
):
    """Create a human-review ticket."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/escalations",
            json={
                "txn_id": txn_id,
                "msisdn": msisdn,
                "reason": reason,
            },
            timeout=TIMEOUT,
        )
        return handle_response(response)
    except requests.RequestException as error:
        return {"error": str(error)}


if __name__ == "__main__":
    # Basic smoke tests for the read-only tools.
    tests = [
        ("Transaction", lambda: get_transaction("TXN001")),
        (
            "Customer transactions",
            lambda: get_customer_transactions("9876543210"),
        ),
        ("Wallet", lambda: get_wallet("9876543210")),
        ("Existing reversal", lambda: check_reversal("TXN004")),
        ("Missing transaction", lambda: get_transaction("TXN999")),
    ]

    for name, test in tests:
        print(f"\n--- {name} ---")
        print(test())
