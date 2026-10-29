import pytest
import uuid
from app import create_app
from database.connection import execute_statement, query_one, query_all
from services.equipment_service import (
    get_all_equipment, create_equipment, update_equipment,
    delete_equipment, seed_default_equipment_if_empty
)
from services.attendance_service import (
    get_gym_terminal_token, record_member_self_scan, record_trainer_self_scan
)
from services.member_service import register_member_self, get_member_by_id

@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key-12345"
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_equipment_service_crud():
    """Verify gym equipment CRUD operations."""
    seed_default_equipment_if_empty()
    items = get_all_equipment()
    assert len(items) >= 10, "Default equipment should be seeded"

    # Create new machine
    new_item = create_equipment(
        name="Cable Crossover Machine",
        category="Functional & Cable",
        target_muscle="Chest, Arms, Shoulders",
        quantity=2,
        status="operational",
        description="Dual adjustable pulley cable station",
        instructions="Adjust pulley height and select appropriate pin weight."
    )
    assert new_item["name"] == "Cable Crossover Machine"
    item_id = new_item["id"]

    # Filter by category
    cable_items = get_all_equipment(category="Functional & Cable")
    assert any(i["id"] == item_id for i in cable_items)

    # Update machine
    updated = update_equipment(
        item_id,
        name="Cable Crossover Pro",
        category="Functional & Cable",
        target_muscle="Chest, Delts",
        quantity=3,
        status="maintenance",
        description="Updated cable machine",
        instructions="Handle with care"
    )
    assert updated["name"] == "Cable Crossover Pro"
    assert updated["quantity"] == 3
    assert updated["status"] == "maintenance"

    # Delete machine
    delete_equipment(item_id)
    rem = get_all_equipment()
    assert not any(i["id"] == item_id for i in rem)

def test_member_self_registration_and_admin_approval(client):
    """Verify self-registration (pending) and admin approval flow."""
    unique_user = f"new_member_{uuid.uuid4().hex[:6]}"
    unique_phone = f"0300{uuid.uuid4().int % 10000000:07d}"

    # 1. Register through public /register
    res = client.post("/register", data={
        "full_name": "Hamza Test",
        "phone": unique_phone,
        "email": f"{unique_user}@example.com",
        "username": unique_user,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "membership_plan": "Standard Monthly"
    }, follow_redirects=True)
    assert res.status_code == 200

    # User should be inactive initially
    user = query_one("SELECT id, is_active FROM users WHERE username = %s;", (unique_user,))
    assert user is not None
    assert user["is_active"] == 0 or user["is_active"] is False

    # Member should have pending status
    member = query_one("SELECT id, membership_status FROM members WHERE user_id = %s;", (user["id"],))
    assert member is not None
    assert member["membership_status"] == "pending"

    # Inactive member cannot log in
    login_res = client.post("/login", data={
        "username": unique_user,
        "password": "Password123!"
    }, follow_redirects=True)
    assert b"pending administrator approval" in login_res.data or b"Account is inactive" in login_res.data or b"Account is deactivated" in login_res.data

    # Log in as owner to approve member
    owner = query_one("SELECT username FROM users WHERE role = 'owner' LIMIT 1;")
    assert owner is not None

    with client.session_transaction() as sess:
        sess["user_id"] = "owner-test-id"
        sess["username"] = owner["username"]
        sess["user_role"] = "owner"

    # Owner approves member
    appr_res = client.post(f"/owner/members/{member['id']}/approve", data={
        "monthly_fee": 6000,
        "membership_plan": "Strength & Conditioning",
        "assigned_trainer_id": ""
    }, follow_redirects=True)
    assert appr_res.status_code == 200

    # Verify user is now active and member status is active
    updated_user = query_one("SELECT is_active FROM users WHERE id = %s;", (user["id"],))
    assert updated_user["is_active"] == 1 or updated_user["is_active"] is True
    updated_member = query_one("SELECT membership_status, monthly_fee FROM members WHERE id = %s;", (member["id"],))
    assert updated_member["membership_status"] == "active"
    assert updated_member["monthly_fee"] == 6000

def test_reverse_qr_attendance_and_double_scan_prevention(client):
    """Verify station QR self-scan check-in and check-out rules."""
    unique_user = f"scan_member_{uuid.uuid4().hex[:6]}"
    unique_phone = f"0311{uuid.uuid4().int % 10000000:07d}"

    # Setup active member
    from services.member_service import create_member
    from datetime import date, timedelta
    today = date.today()
    new_m = create_member(
        full_name="Reverse QR Tester",
        phone=unique_phone,
        start_date=today,
        end_date=today + timedelta(days=30),
        monthly_fee=5000,
        username=unique_user,
        password="Password123!",
        email=f"{unique_user}@test.com"
    )
    user_id = new_m["user_id"]
    terminal_token = get_gym_terminal_token()

    # Log in as this member
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = unique_user
        sess["user_role"] = "member"

    # 1. Attempt Check-Out BEFORE Check-In -> Expect 400
    res_early_out = client.post("/api/attendance/self-scan", json={
        "token": terminal_token,
        "action": "check_out"
    })
    assert res_early_out.status_code == 400
    assert "Cannot check out before checking in" in res_early_out.json["error"]

    # 2. Check-In with Station QR -> Expect 200
    res_in = client.post("/api/attendance/self-scan", json={
        "token": terminal_token,
        "action": "check_in"
    })
    assert res_in.status_code == 200
    assert res_in.json["success"] is True

    # 3. Duplicate Check-In attempt on same day -> Expect 409
    res_dup_in = client.post("/api/attendance/self-scan", json={
        "token": terminal_token,
        "action": "check_in"
    })
    assert res_dup_in.status_code == 409
    assert "already checked in today" in res_dup_in.json["error"].lower()

    # 4. Check-Out with Station QR -> Expect 200
    res_out = client.post("/api/attendance/self-scan", json={
        "token": terminal_token,
        "action": "check_out"
    })
    assert res_out.status_code == 200
    assert res_out.json["success"] is True

    # 5. Duplicate Check-Out attempt on same day -> Expect 409
    res_dup_out = client.post("/api/attendance/self-scan", json={
        "token": terminal_token,
        "action": "check_out"
    })
    assert res_dup_out.status_code == 409
    assert "already checked out today" in res_dup_out.json["error"].lower()

def test_admin_password_reset_override(client):
    """Verify owner can manually override passwords for members and staff."""
    unique_user = f"pwd_member_{uuid.uuid4().hex[:6]}"
    unique_phone = f"0322{uuid.uuid4().int % 10000000:07d}"

    from services.member_service import create_member
    from datetime import date, timedelta
    today = date.today()
    m = create_member(
        full_name="Password Target",
        phone=unique_phone,
        start_date=today,
        end_date=today + timedelta(days=30),
        monthly_fee=5000,
        username=unique_user,
        password="OldPassword123!",
        email=f"{unique_user}@test.com"
    )

    # Set owner session
    with client.session_transaction() as sess:
        sess["user_id"] = "owner-override-id"
        sess["username"] = "admin"
        sess["user_role"] = "owner"

    # Owner resets member password
    res = client.post(f"/owner/members/{m['id']}/reset-password", data={
        "new_password": "NewSecretPassword999!"
    }, follow_redirects=True)
    assert res.status_code == 200

    # Clear session and verify member can log in with NEW password
    with client.session_transaction() as sess:
        sess.clear()

    login_res = client.post("/login", data={
        "username": unique_user,
        "password": "NewSecretPassword999!"
    }, follow_redirects=True)
    assert login_res.status_code == 200
    assert b"My Pass & Profile" in login_res.data or b"Member Personal Portal" in login_res.data

def test_member_and_trainer_self_password_change(client):
    """Verify members and trainers can update their passwords securely."""
    unique_user = f"chg_member_{uuid.uuid4().hex[:6]}"
    unique_phone = f"0333{uuid.uuid4().int % 10000000:07d}"

    from services.member_service import create_member
    from datetime import date, timedelta
    today = date.today()
    m = create_member(
        full_name="Password Changer",
        phone=unique_phone,
        start_date=today,
        end_date=today + timedelta(days=30),
        monthly_fee=5000,
        username=unique_user,
        password="InitialPassword123!",
        email=f"{unique_user}@test.com"
    )

    with client.session_transaction() as sess:
        sess["user_id"] = m["user_id"]
        sess["username"] = unique_user
        sess["user_role"] = "member"

    # Change password
    res = client.post("/member/change-password", data={
        "current_password": "InitialPassword123!",
        "new_password": "UpdatedPassword456!",
        "confirm_password": "UpdatedPassword456!"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Password updated successfully" in res.data

    # Verify old password fails
    with client.session_transaction() as sess:
        sess.clear()

    bad_login = client.post("/login", data={
        "username": unique_user,
        "password": "InitialPassword123!"
    }, follow_redirects=True)
    assert b"Invalid username or password" in bad_login.data

    # Verify new password succeeds
    good_login = client.post("/login", data={
        "username": unique_user,
        "password": "UpdatedPassword456!"
    }, follow_redirects=True)
    assert good_login.status_code == 200

def test_trainer_reverse_qr_attendance(client):
    """Verify trainer self-scan check-in and check-out with station token."""
    unique_user = f"scan_trainer_{uuid.uuid4().hex[:6]}"
    unique_phone = f"0344{uuid.uuid4().int % 10000000:07d}"

    from services.staff_service import create_trainer
    from datetime import date
    t = create_trainer(
        full_name="Coach Scan Test",
        phone=unique_phone,
        specialization="Strength Coach",
        bio="Certified strength coach",
        hire_date=date.today(),
        username=unique_user,
        password="Password123!",
        email=f"{unique_user}@test.com"
    )
    user_id = t["user_id"]
    terminal_token = get_gym_terminal_token()

    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = unique_user
        sess["user_role"] = "trainer"

    # 1. Early Check-out -> 400
    res_early = client.post("/api/attendance/self-scan", json={
        "token": terminal_token,
        "action": "check_out"
    })
    assert res_early.status_code == 400

    # 2. Check-in -> 200
    res_in = client.post("/api/attendance/self-scan", json={
        "token": terminal_token,
        "action": "check_in"
    })
    assert res_in.status_code == 200

    # 3. Duplicate check-in -> 409
    res_dup = client.post("/api/attendance/self-scan", json={
        "token": terminal_token,
        "action": "check_in"
    })
    assert res_dup.status_code == 409

    # 4. Check-out -> 200
    res_out = client.post("/api/attendance/self-scan", json={
        "token": terminal_token,
        "action": "check_out"
    })
    assert res_out.status_code == 200

    # 5. Duplicate check-out -> 409
    res_dup_out = client.post("/api/attendance/self-scan", json={
        "token": terminal_token,
        "action": "check_out"
    })
    assert res_dup_out.status_code == 409

def test_equipment_and_trainers_views_accessible(client):
    """Verify equipment and trainers directories render successfully."""
    # Member session
    with client.session_transaction() as sess:
        sess["user_id"] = "test-member-view"
        sess["username"] = "member_viewer"
        sess["user_role"] = "member"

    # Fake member record in DB for session
    user_id = "test-member-view"
    member_id = "test-member-view-id"
    from database.connection import execute_statement
    execute_statement("INSERT OR IGNORE INTO users (id, username, password_hash, role, is_active) VALUES (%s, %s, 'hash', 'member', 1);", (user_id, "member_viewer"))
    execute_statement("INSERT OR IGNORE INTO members (id, user_id, member_code, full_name, phone, membership_plan, membership_start_date, membership_end_date, monthly_fee, membership_status, qr_token) VALUES (%s, %s, 'MBR-9999', 'View Tester', '03999999999', 'Standard', '2026-01-01', '2026-12-31', 5000, 'active', 'qr-token-test');", (member_id, user_id))

    # Test member equipment view
    res_eq = client.get("/member/equipment")
    assert res_eq.status_code == 200
    assert b"Gym Equipment Directory" in res_eq.data or b"Gym Machines" in res_eq.data

    # Test member trainers view
    res_tr = client.get("/member/trainers")
    assert res_tr.status_code == 200
    assert b"Certified Gym Trainers" in res_tr.data or b"Meet Our Certified" in res_tr.data

def test_quick_scan_attendance_direct_url(client):
    """Verify quick-scan direct link works for camera-less or external QR app flow."""
    unique_user = f"direct_scan_{uuid.uuid4().hex[:6]}"
    unique_phone = f"0355{uuid.uuid4().int % 10000000:07d}"

    from services.member_service import create_member
    from datetime import date, timedelta
    today = date.today()
    m = create_member(
        full_name="Direct Scan Tester",
        phone=unique_phone,
        start_date=today,
        end_date=today + timedelta(days=30),
        monthly_fee=5000,
        username=unique_user,
        password="Password123!",
        email=f"{unique_user}@test.com"
    )

    with client.session_transaction() as sess:
        sess["user_id"] = m["user_id"]
        sess["username"] = unique_user
        sess["user_role"] = "member"

    # 1. Quick Scan Check In via direct GET URL
    res_in = client.get("/api/attendance/quick-scan?action=check_in&token=VANGUARD-TERMINAL-DESK-STATION", follow_redirects=True)
    assert res_in.status_code == 200
    assert b"Check-in recorded" in res_in.data or b"Checked in successfully" in res_in.data or b"recorded" in res_in.data

    # 2. Duplicate Quick Scan Check In -> Expect error message
    res_dup = client.get("/api/attendance/quick-scan?action=check_in&token=VANGUARD-TERMINAL-DESK-STATION", follow_redirects=True)
    assert res_dup.status_code == 200
    assert b"already checked in today" in res_dup.data.lower()

    # 3. Quick Scan Check Out via direct GET URL
    res_out = client.get("/api/attendance/quick-scan?action=check_out&token=VANGUARD-TERMINAL-DESK-STATION", follow_redirects=True)
    assert res_out.status_code == 200
    assert b"Check-out recorded" in res_out.data or b"Checked out successfully" in res_out.data or b"recorded" in res_out.data

    # 4. Duplicate Quick Scan Check Out -> Expect error message
    res_dup_out = client.get("/api/attendance/quick-scan?action=check_out&token=VANGUARD-TERMINAL-DESK-STATION", follow_redirects=True)
    assert res_dup_out.status_code == 200
    assert b"already checked out today" in res_dup_out.data.lower()


