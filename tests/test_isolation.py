import pytest
from app import create_app
from config import TestingConfig
from database.connection import query_one
from services.staff_service import create_trainer
from services.member_service import create_member

@pytest.fixture
def app():
    app = create_app(TestingConfig)
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

def test_data_isolation_and_role_security(client):
    # Setup two trainers: Coach A and Coach B
    trainer_a = create_trainer("Coach A", "+923001110001", "a@gym.com", "Yoga", "Bio", "2026-01-01", "trainer_a_test", "Pass123!")
    trainer_b = create_trainer("Coach B", "+923001110002", "b@gym.com", "Crossfit", "Bio", "2026-01-01", "trainer_b_test", "Pass123!")

    # Member assigned to Coach A
    member_a = create_member(
        "Trainee of A", "+923002220001", "2026-10-01", "2026-11-01", 5000,
        "trainee_a_user", "Pass123!", assigned_trainer_id=trainer_a["id"]
    )

    # Member assigned to Coach B
    member_b = create_member(
        "Trainee of B", "+923002220002", "2026-10-01", "2026-11-01", 5000,
        "trainee_b_user", "Pass123!", assigned_trainer_id=trainer_b["id"]
    )

    # 1. TRAINER ISOLATION:
    # Log in as Coach B
    client.post("/login", data={"username": "trainer_b_test", "password": "Pass123!"})

    # Coach B accessing Member A (assigned to Coach A) MUST BE DENIED!
    resp_cross_trainer = client.get(f"/trainer/members/{member_a['id']}", follow_redirects=True)
    assert b"Access Denied" in resp_cross_trainer.data

    # Coach B accessing Member B (assigned to Coach B) MUST SUCCEED
    resp_own_trainer = client.get(f"/trainer/members/{member_b['id']}")
    assert resp_own_trainer.status_code == 200
    assert b"Trainee Progress &amp; Log" in resp_own_trainer.data or b"Trainee of B" in resp_own_trainer.data

    # 2. MEMBER ISOLATION:
    client.get("/logout")
    client.post("/login", data={"username": "trainee_a_user", "password": "Pass123!"})

    # Member trying to access owner dashboard or settings MUST BE DENIED!
    resp_member_to_owner = client.get("/owner/dashboard", follow_redirects=True)
    assert resp_member_to_owner.status_code in (403, 302, 200)
    assert b"Owner Command Center" not in resp_member_to_owner.data

    # Member trying to access receptionist scanner terminal MUST BE DENIED!
    resp_member_to_desk = client.get("/receptionist/desk", follow_redirects=True)
    assert b"Front Desk Attendance Terminal" not in resp_member_to_desk.data

    # 3. RECEPTIONIST RESTRICTION:
    client.get("/logout")
    import secrets
    r_user = f"rec_{secrets.token_hex(4)}"
    from services.staff_service import create_receptionist
    create_receptionist("Rec Isolation", f"+9230{secrets.randbelow(90000000)+10000000}", "rec@test.com", "Morning", r_user, "RecPass123!")
    client.post("/login", data={"username": r_user, "password": "RecPass123!"})

    # Receptionist trying to access owner gym settings MUST BE DENIED!
    resp_rec_settings = client.get("/owner/settings", follow_redirects=True)
    assert b"Gym Branding &amp; Configurations" not in resp_rec_settings.data
