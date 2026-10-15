# Mobile Money Dispute Assistant

A local learning prototype for investigating mobile money transaction disputes. It combines a FastAPI backend, SQLite sample data, a Python agent, and a local Ollama model.

## What it does

- Looks up a customer's transactions and wallet balance.
- Applies code-based refund eligibility checks.
- Waits on recent pending transactions and escalates older or high-value cases for human review.
- Creates an escalation record when a case needs review.
- Requires a customer-specific bearer token for backend requests and checks transaction ownership.

The agent does **not** issue refunds or move money. A reversal endpoint exists for backend demonstrations, but the agent cannot call it. The project is for local learning with sample data, not production financial use.

## Requirements

- Python 3.10 or newer.
- Ollama running locally with the `qwen2.5:3b` model available for non-refund questions. The explicit refund-check flow uses Python guardrails and does not need an LLM response.

## Setup on Windows PowerShell

Run these commands from the project root (`dispute-agent`):

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If `.venv` already exists, skip the first command. The checked-in SQLite database contains demo records. To initialize or add missing demo records, run:

```powershell
Push-Location backend
..\.venv\Scripts\python.exe seed_data.py
Pop-Location
```

## Start the backend

Open a PowerShell terminal at the project root, configure demo tokens, and start the API:

```powershell
$env:CUSTOMER_API_TOKENS='{"9876543210":"demo-token-1","9123456780":"demo-token-2","9000011111":"demo-token-3"}'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Keep this terminal open. The JSON object maps each customer MSISDN to its bearer token. Set this variable in the same terminal that starts the backend.

## Check authentication and ownership

In a second PowerShell terminal at the project root, run:

```powershell
curl.exe -i http://127.0.0.1:8000/transactions/TXN001
curl.exe -i -H "Authorization: Bearer demo-token-1" http://127.0.0.1:8000/transactions/TXN001
curl.exe -i -H "Authorization: Bearer demo-token-1" http://127.0.0.1:8000/transactions/TXN004
```

Expected status codes are `401` (missing token), `200` (customer's transaction), and `404` (another customer's transaction).

## Run the agent

Keep the backend running. From another terminal at the project root:

```powershell
.\.venv\Scripts\python.exe agent\agent.py
```

Enter a demo customer's MSISDN and matching token when prompted. For example, use `9876543210`, `demo-token-1`, and ask: `Please check the refund for TXN001.` Eligible cases are escalated for manual review; no refund is issued.

## Demo transaction scenarios

| Transaction | Scenario | Expected result |
| --- | --- | --- |
| `TXN001` | Failed, debited, receiver not credited | Escalated for manual review |
| `TXN002` | Successful transaction | Rejected for refund |
| `TXN003` | Recent pending transaction | Wait |
| `TXN004` | Reversal already exists (customer `9123456780`) | Rejected as already reversed |
| `TXN005` | Failed transaction above ₹5,000 (customer `9123456780`) | Escalated for human approval |

The sample database is kept between runs, so transaction ages can become stale. `TXN003` returns `WAIT` only while its stored timestamp is less than 24 hours old; an older pending transaction is escalated. Seed timestamps created by the current script use UTC. Older timezone-free sample timestamps are interpreted as local time for compatibility.

## Project layout

- `backend/main.py` — FastAPI routes, authentication, and reversal/escalation rules.
- `backend/db.py` — SQLite connection and schema initialization.
- `backend/seed_data.py` — repeatable sample data for the demo.
- `agent/agent.py` — local conversational agent and deterministic refund workflow.
- `agent/guardrails.py` — ownership, status, amount, duplicate, and pending-time checks.
- `agent/tools.py` — authenticated HTTP client used by the agent.

## Prototype limits

- The bearer tokens above are demo credentials. Use a real identity provider and secure secret storage before handling real customer data.
- The backend is intended for local use; it has no production deployment, TLS, rate limiting, or staff escalation dashboard.
- A successful reversal response records a mock database row only. It does not credit a wallet or contact a payment network.
- Transactions and escalations are stored in the local SQLite file `backend/dispute_agent.db`.
