import pytest
from app import create_app
from config import TestingConfig
from database.connection import query_one, execute_statement
from services.member_service import create_member
from services.staff_service import create_receptionist
from services.attendance_service import record_attendance_by_qr, record_attendance_manual, get_gym_local_date

def test_attendance_operations(app):
    client = app.test_client()
    today, _ = get_gym_local_date()

    # Clear existing attendance
    execute_statement("DELETE FROM attendance;")

    # Create a fresh receptionist for this test
    import secrets
    rec_username = f"desk_{secrets.token_hex(4)}"
    create_receptionist(
        full_name="Desk Staff", phone=f"+9230{secrets.randbelow(90000000)+10000000}", email="desk@test.com",
        shift="Morning", username=rec_username, password="DeskPass123!"
    )

    # Ensure an active member exists
    member = create_member(
        full_name="Attendance Test Member",
        phone=f"+9230{secrets.randbelow(90000000)+10000000}",
        start_date=today.strftime("%Y-%m-%d"),
        end_date="2026-11-25",
        monthly_fee=5000,
        username=f"att_test_{secrets.token_hex(4)}",
        password="Pass123!",
        membership_status="active"
    )

    # 1. Valid QR Scan via API
    # Log in as receptionist
    client.post("/login", data={"username": rec_username, "password": "DeskPass123!"})
    
    resp = client.post("/api/attendance/scan", json={"qr_token": member["qr_token"]})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "Welcome" in data["message"]
    assert data["member_name"] == member["full_name"]

    # Verify persisted in database
    att_row = query_one("SELECT * FROM attendance WHERE member_id = %s AND attendance_date = %s;", (member["id"], today))
    assert att_row is not None
    assert att_row["method"] == "QR"

    # 2. Duplicate same-day QR scan MUST be rejected!
    resp_dup = client.post("/api/attendance/scan", json={"qr_token": member["qr_token"]})
    assert resp_dup.status_code == 409
    data_dup = resp_dup.get_json()
    assert data_dup["success"] is False
    assert data_dup["status"] == "already_marked"
    assert "already checked in" in data_dup["message"].lower()

    # 3. Create an inactive member and verify QR scan is rejected
    inactive_m = create_member(
        full_name="Inactive Member Att",
        phone="+923008882222",
        start_date=today.strftime("%Y-%m-%d"),
        end_date="2026-11-01",
        monthly_fee=5000,
        username="inactive_att_user",
        password="Password123!",
        membership_status="inactive"
    )
    resp_inactive = client.post("/api/attendance/scan", json={"qr_token": inactive_m["qr_token"]})
    assert resp_inactive.status_code == 400
    data_inact = resp_inactive.get_json()
    assert data_inact["success"] is False
    assert "INACTIVE" in data_inact["message"]

    # 4. Manual attendance check-in for a different active member
    active_m2 = create_member(
        full_name="Manual Checkin Member 2",
        phone="+923008883333",
        start_date=today.strftime("%Y-%m-%d"),
        end_date="2026-11-01",
        monthly_fee=5000,
        username="manual_user_test_2",
        password="Password123!",
        membership_status="active"
    )
    resp_manual = client.post("/api/attendance/manual", json={"member_id": active_m2["id"]})
    assert resp_manual.status_code == 200
    assert resp_manual.get_json()["success"] is True

    # Duplicate manual check-in rejected
    resp_manual_dup = client.post("/api/attendance/manual", json={"member_id": active_m2["id"]})
    assert resp_manual_dup.status_code == 400
    assert "already checked in" in resp_manual_dup.get_json()["message"].lower()
