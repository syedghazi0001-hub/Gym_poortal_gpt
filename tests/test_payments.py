import pytest
from app import create_app
from config import TestingConfig
from database.connection import query_one, query_all, execute_statement
from services.payment_service import (
    record_monthly_payment, get_monthly_payment_status,
    reverse_payment, get_current_billing_month
)

@pytest.fixture
def app():
    app = create_app(TestingConfig)
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

def test_payment_operations(client):
    execute_statement("DELETE FROM payments;")
    current_month = get_current_billing_month()

    member = query_one("SELECT * FROM members WHERE membership_status = 'active' LIMIT 1;")
    owner = query_one("SELECT * FROM users WHERE role = 'owner' LIMIT 1;")

    # 1. Initially member payment status for current_month should be pending
    status_before = get_monthly_payment_status(current_month)
    member_record_before = next(m for m in status_before["members"] if m["member_id"] == member["id"])
    assert member_record_before["payment_status"] == "pending"

    # 2. Record payment
    payment = record_monthly_payment(
        member_id=member["id"],
        billing_month=current_month,
        amount=member["monthly_fee"],
        payment_method="cash",
        recorded_by_id=owner["id"],
        notes="First month paid in cash"
    )
    assert payment is not None
    assert payment["receipt_number"].startswith(f"REC-{current_month.replace('-', '')}-")
    assert payment["status"] == "paid"

    # 3. After payment, status for current_month is paid
    status_after = get_monthly_payment_status(current_month)
    member_record_after = next(m for m in status_after["members"] if m["member_id"] == member["id"])
    assert member_record_after["payment_status"] == "paid"
    assert member_record_after["receipt_number"] == payment["receipt_number"]

    # 4. Duplicate payment for the same billing period MUST be blocked!
    with pytest.raises(ValueError) as excinfo:
        record_monthly_payment(
            member_id=member["id"],
            billing_month=current_month,
            amount=member["monthly_fee"],
            payment_method="cash",
            recorded_by_id=owner["id"]
        )
    assert "already been recorded" in str(excinfo.value)
    assert "Duplicate payments are blocked" in str(excinfo.value)

    # 5. Member notification created
    notif = query_one("SELECT * FROM notifications WHERE user_id = %s AND category = 'payment';", (member["user_id"],))
    assert notif is not None
    assert "Payment Confirmed" in notif["title"]

    # 6. Payment reversal
    reverse_payment(payment["id"], owner["id"], reason="Test reversal")
    reversed_p = query_one("SELECT * FROM payments WHERE id = %s;", (payment["id"],))
    assert reversed_p["status"] == "reversed"
    assert "Test reversal" in reversed_p["notes"]
