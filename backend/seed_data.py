from datetime import datetime, timedelta

from db import get_connection, init_db


transactions = [
    # 1. Failed + debited + not credited = valid refund
    {
        "txn_id": "TXN001",
        "msisdn": "9876543210",
        "amount": 500,
        "status": "FAILED",
        "debited": 1,
        "credited_to_receiver": 0,
        "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
    },

    # 2. Successful transaction = reject
    {
        "txn_id": "TXN002",
        "msisdn": "9876543210",
        "amount": 800,
        "status": "SUCCESS",
        "debited": 1,
        "credited_to_receiver": 1,
        "timestamp": (datetime.now() - timedelta(hours=3)).isoformat(),
    },

    # 3. Pending transaction less than 24 hours = wait
    {
        "txn_id": "TXN003",
        "msisdn": "9876543210",
        "amount": 300,
        "status": "PENDING",
        "debited": 1,
        "credited_to_receiver": 0,
        "timestamp": (datetime.now() - timedelta(hours=5)).isoformat(),
    },

    # 4. Already reversed
    {
        "txn_id": "TXN004",
        "msisdn": "9123456780",
        "amount": 700,
        "status": "FAILED",
        "debited": 1,
        "credited_to_receiver": 0,
        "timestamp": (datetime.now() - timedelta(hours=4)).isoformat(),
    },

    # 5. High amount = human approval required
    {
        "txn_id": "TXN005",
        "msisdn": "9123456780",
        "amount": 8000,
        "status": "FAILED",
        "debited": 1,
        "credited_to_receiver": 0,
        "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
    },

    # 6. Another valid refund
    {
        "txn_id": "TXN006",
        "msisdn": "9123456780",
        "amount": 1200,
        "status": "FAILED",
        "debited": 1,
        "credited_to_receiver": 0,
        "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
    },

    # 7. Successful transaction
    {
        "txn_id": "TXN007",
        "msisdn": "9000011111",
        "amount": 1500,
        "status": "SUCCESS",
        "debited": 1,
        "credited_to_receiver": 1,
        "timestamp": (datetime.now() - timedelta(hours=6)).isoformat(),
    },

    # 8. Valid refund
    {
        "txn_id": "TXN008",
        "msisdn": "9000011111",
        "amount": 250,
        "status": "FAILED",
        "debited": 1,
        "credited_to_receiver": 0,
        "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
    },

    # 9. Pending
    {
        "txn_id": "TXN009",
        "msisdn": "9000011111",
        "amount": 450,
        "status": "PENDING",
        "debited": 1,
        "credited_to_receiver": 0,
        "timestamp": (datetime.now() - timedelta(hours=10)).isoformat(),
    },

    # 10. High amount
    {
        "txn_id": "TXN010",
        "msisdn": "9000011111",
        "amount": 12000,
        "status": "FAILED",
        "debited": 1,
        "credited_to_receiver": 0,
        "timestamp": (datetime.now() - timedelta(hours=3)).isoformat(),
    },
]


def seed_transactions():
    connection = get_connection()
    cursor = connection.cursor()

    for txn in transactions:
        cursor.execute(
            """
            INSERT OR IGNORE INTO transactions (
                txn_id,
                msisdn,
                amount,
                status,
                debited,
                credited_to_receiver,
                timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                txn["txn_id"],
                txn["msisdn"],
                txn["amount"],
                txn["status"],
                txn["debited"],
                txn["credited_to_receiver"],
                txn["timestamp"],
            ),
        )

    connection.commit()
    connection.close()

    print(f"Inserted {len(transactions)} transactions.")


def seed_wallets():
    wallets = [
        ("9876543210", 5000),
        ("9123456780", 10000),
        ("9000011111", 7500),
    ]

    connection = get_connection()
    cursor = connection.cursor()

    for msisdn, balance in wallets:
        cursor.execute(
            """
            INSERT OR IGNORE INTO wallets (msisdn, balance)
            VALUES (?, ?)
            """,
            (msisdn, balance),
        )

    connection.commit()
    connection.close()

    print(f"Inserted {len(wallets)} wallets.")


def seed_reversal():
    """
    Create an existing reversal for TXN004.
    This lets us test duplicate-refund protection later.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO reversals (
            txn_id,
            amount,
            reason,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            "TXN004",
            700,
            "Original transaction failed",
            datetime.now().isoformat(),
        ),
    )

    connection.commit()
    connection.close()

    print("Created existing reversal for TXN004.")


if __name__ == "__main__":
    init_db()
    seed_transactions()
    seed_wallets()
    seed_reversal()

    print("Seed data created successfully.")