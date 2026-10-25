import pytest
from app import create_app
from config import TestingConfig
from database.connection import execute_statement, query_one
from services.auth_service import setup_initial_owner, authenticate_user

def test_initial_setup_and_login(app):
    client = app.test_client()

    # Clear users & gym_settings to test cold start setup
    execute_statement("DELETE FROM audit_logs;")
    execute_statement("DELETE FROM notifications;")
    execute_statement("DELETE FROM absence_alerts;")
    execute_statement("DELETE FROM payments;")
    execute_statement("DELETE FROM attendance;")
    execute_statement("DELETE FROM members;")
    execute_statement("DELETE FROM trainers;")
    execute_statement("DELETE FROM receptionists;")
    execute_statement("DELETE FROM profiles;")
    execute_statement("DELETE FROM users;")
    execute_statement("DELETE FROM gym_settings;")

    # 1. Accessing root redirects to /setup when no owner
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/setup" in resp.headers.get("Location")

    # 2. Perform initial setup
    setup_data = {
        "gym_name": "Apex Strength Club",
        "currency": "PKR",
        "timezone": "Asia/Karachi",
        "full_name": "Hamza Malik",
        "phone": "+923001112233",
        "email": "hamza@apexstrength.com",
        "username": "owner_hamza",
        "password": "SecretPassword123!",
        "confirm_password": "SecretPassword123!"
    }
    resp = client.post("/setup", data=setup_data, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Apex Strength Club" in resp.data

    # Verify user exists in database with owner role
    user = query_one("SELECT * FROM users WHERE username = 'owner_hamza';")
    assert user is not None
    assert user["role"] == "owner"

    # 3. Subsequent /setup attempt must be blocked
    resp2 = client.get("/setup", follow_redirects=False)
    assert resp2.status_code == 302
    assert "/login" in resp2.headers.get("Location")

    # 4. Logout
    client.get("/logout")

    # 5. Invalid login fails
    resp_invalid = client.post("/login", data={
        "username": "owner_hamza",
        "password": "WrongPassword!"
    }, follow_redirects=True)
    assert b"Invalid username or password" in resp_invalid.data

    # 6. Valid login succeeds
    resp_valid = client.post("/login", data={
        "username": "owner_hamza",
        "password": "SecretPassword123!"
    }, follow_redirects=True)
    assert resp_valid.status_code == 200
    assert b"Owner Command Center" in resp_valid.data
