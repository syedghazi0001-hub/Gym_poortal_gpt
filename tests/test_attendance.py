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

    # 5. Trainer Attendance Tests
    from services.staff_service import create_trainer
    trainer = create_trainer(
        full_name="Trainer Bilal Coach",
        phone="+923004441111",
        email="bilal_coach@gym.com",
        specialization="HIIT & Strength",
        bio="Certified HIIT and strength coach",
        hire_date="2026-01-01",
        username="trainer_bilal_test",
        password="Password123!"
    )

    # Receptionist checks in trainer
    t_checkin_res = client.post("/receptionist/trainers/checkin", data={"trainer_id": trainer["id"]}, follow_redirects=True)
    assert t_checkin_res.status_code == 200

    t_att = query_one("SELECT * FROM trainer_attendance WHERE trainer_id = %s AND attendance_date = %s;", (trainer["id"], today))
    assert t_att is not None
    assert t_att["status"] == "present"

    # Duplicate trainer checkin on same day fails
    t_dup_res = client.post("/receptionist/trainers/checkin", data={"trainer_id": trainer["id"]}, follow_redirects=True)
    assert b"already checked in" in t_dup_res.data or b"Trainer check-in failed" in t_dup_res.data

    # Receptionist checks out trainer
    t_checkout_res = client.post("/receptionist/trainers/checkout", data={"trainer_id": trainer["id"]}, follow_redirects=True)
    assert t_checkout_res.status_code == 200

    t_att_updated = query_one("SELECT * FROM trainer_attendance WHERE trainer_id = %s AND attendance_date = %s;", (trainer["id"], today))
    assert t_att_updated["check_out_time"] is not None


def test_trainer_attendance_db_fallback(app):
    """Verify that if trainer_attendance table is dropped, pages degrade gracefully without 500 errors."""
    client = app.test_client()
    # Log in as receptionist created in previous step or fresh
    import secrets
    r_user = f"rec_fb_{secrets.token_hex(4)}"
    create_receptionist(
        full_name="Fallback Receptionist",
        phone=f"+9230{secrets.randbelow(90000000)+10000000}",
        email="fallback_rec@gym.com",
        shift="Morning",
        username=r_user,
        password="Password123!"
    )
    login_res = client.post("/login", data={"username": r_user, "password": "Password123!"}, follow_redirects=True)
    assert login_res.status_code == 200

    # Drop table to simulate unmigrated Supabase database
    execute_statement("DROP TABLE IF EXISTS trainer_attendance;")

    # Desk page must render 200 OK without crashing (not 500)
    resp_desk = client.get("/receptionist/desk")
    assert resp_desk.status_code == 200
    assert b"Front Desk Attendance &amp; Roster" in resp_desk.data or b"Front Desk" in resp_desk.data


def test_receptionist_desk_full_workflow(app):
    """Test full receptionist desk features: search, 1-click checkin, member code checkin."""
    client = app.test_client()
    import secrets
    r_user = f"desk_wf_{secrets.token_hex(4)}"
    create_receptionist(
        full_name="Workflow Desk", phone=f"+9230{secrets.randbelow(90000000)+10000000}",
        email="wf_desk@gym.com", shift="Evening", username=r_user, password="Password123!"
    )
    client.post("/login", data={"username": r_user, "password": "Password123!"}, follow_redirects=True)

    today, _ = get_gym_local_date()
    m = create_member(
        full_name="Desk Test Member",
        phone=f"+9230{secrets.randbelow(90000000)+10000000}",
        start_date=today.strftime("%Y-%m-%d"),
        end_date="2026-12-01",
        monthly_fee=5000,
        username=f"desk_m_{secrets.token_hex(4)}",
        password="Password123!",
        membership_status="active"
    )

    # 1. Desk renders with member in list
    res_desk = client.get("/receptionist/desk")
    assert res_desk.status_code == 200
    assert m["member_code"].encode() in res_desk.data

    # 2. Search API returns both full_name and member_code
    res_search = client.get(f"/api/members/search?q={m['member_code']}")
    assert res_search.status_code == 200
    data_search = res_search.get_json()
    assert len(data_search) > 0
    assert data_search[0]["id"] == m["id"]
    assert data_search[0]["code"] == m["member_code"]
    assert data_search[0]["name"] == m["full_name"]

    # 3. Check in via member code string
    res_scan = client.post("/api/attendance/scan", json={"qr_token": m["member_code"]})
    assert res_scan.status_code == 200
    assert res_scan.get_json()["success"] is True

    # 4. Duplicate scan rejected
    res_scan_dup = client.post("/api/attendance/scan", json={"qr_token": m["member_code"]})
    assert res_scan_dup.status_code == 409
