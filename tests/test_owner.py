import pytest
from app import create_app
from config import TestingConfig
from database.connection import query_one, execute_statement
from services.member_service import get_member_by_id

@pytest.fixture
def app():
    app = create_app(TestingConfig)
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

def login_as(client, username, password):
    return client.post("/login", data={"username": username, "password": password}, follow_redirects=True)

def test_owner_operations(client):
    # Ensure owner is logged in
    login_as(client, "owner_hamza", "SecretPassword123!")

    # 1. Create a Trainer
    trainer_data = {
        "full_name": "Coach Asad",
        "phone": "+923009998877",
        "email": "asad@gym.com",
        "specialization": "Bodybuilding & Hypertrophy",
        "bio": "Certified strength coach with 8 years experience.",
        "hire_date": "2026-01-15",
        "username": "coach_asad",
        "password": "CoachPassword123!"
    }
    resp = client.post("/owner/staff/trainer/new", data=trainer_data, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Trainer Coach Asad created successfully" in resp.data

    trainer = query_one("SELECT * FROM trainers WHERE full_name = 'Coach Asad';")
    assert trainer is not None
    assert trainer["specialization"] == "Bodybuilding & Hypertrophy"

    # 2. Create a Receptionist
    rec_data = {
        "full_name": "Sana Receptionist",
        "phone": "+923005554433",
        "email": "sana@gym.com",
        "shift": "Morning",
        "username": "sana_desk",
        "password": "SanaPassword123!"
    }
    resp2 = client.post("/owner/staff/receptionist/new", data=rec_data, follow_redirects=True)
    assert resp2.status_code == 200
    assert b"Receptionist Sana Receptionist created successfully" in resp2.data

    # 3. Create a Member with Assigned Trainer
    member_data = {
        "full_name": "Zaid Khan",
        "phone": "+923121234567",
        "email": "zaid@example.com",
        "dob": "1998-05-12",
        "emergency_contact": "Father: 0312-0000000",
        "membership_plan": "Monthly Standard",
        "membership_start_date": "2026-10-01",
        "membership_end_date": "2026-11-01",
        "monthly_fee": "6000",
        "membership_status": "active",
        "assigned_trainer_id": trainer["id"],
        "notes": "Prefers evening workouts",
        "username": "zaid_member",
        "password": "ZaidPassword123!"
    }
    resp3 = client.post("/owner/members/new", data=member_data, follow_redirects=True)
    assert resp3.status_code == 200
    assert b"Zaid Khan" in resp3.data

    member = query_one("SELECT * FROM members WHERE phone = '+923121234567';")
    assert member is not None
    assert member["member_code"].startswith("MEM-2026-")
    assert member["qr_token"].startswith("GYM-")
    assert member["assigned_trainer_id"] == trainer["id"]

    # 4. Edit member
    edit_data = {
        "full_name": "Zaid Khan Senior",
        "phone": "+923121234567",
        "email": "zaid.sr@example.com",
        "dob": "1998-05-12",
        "emergency_contact": "Father: 0312-0000000",
        "membership_plan": "VIP Unlimited",
        "membership_start_date": "2026-10-01",
        "membership_end_date": "2026-11-01",
        "monthly_fee": "8500",
        "membership_status": "active",
        "assigned_trainer_id": trainer["id"],
        "notes": "Upgraded to VIP tier"
    }
    resp4 = client.post(f"/owner/members/{member['id']}/edit", data=edit_data, follow_redirects=True)
    assert resp4.status_code == 200
    assert b"Zaid Khan Senior" in resp4.data

    updated = get_member_by_id(member["id"])
    assert updated["full_name"] == "Zaid Khan Senior"
    assert updated["membership_plan"] == "VIP Unlimited"
    assert float(updated["monthly_fee"]) == 8500.0

    # 5. Non-owner cannot create members or staff
    client.get("/logout")
    login_as(client, "sana_desk", "SanaPassword123!")
    blocked_resp = client.get("/owner/members/new", follow_redirects=True)
    # Should redirect with access denied or 403
    assert b"Access denied" in blocked_resp.data or blocked_resp.status_code in (403, 302)
