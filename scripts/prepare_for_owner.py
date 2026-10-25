#!/usr/bin/env python3
"""Prepare a fresh database for owner handover. Destructive action is guarded."""
import os
import sys
import getpass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database.connection import init_db, execute_statement
from services.auth_service import setup_initial_owner, has_owner_account

TABLES_TO_CLEAR = (
    "audit_logs", "notifications", "absence_alerts", "payments", "attendance",
    "trainer_notes", "members", "trainers", "receptionists", "profiles", "users", "gym_settings",
)

def prepare():
    print("VANGUARD GYM OS - OWNER HANDOVER SETUP")
    print("WARNING: This operation deletes ALL existing gym records in the configured database.")
    confirmation = input("Type WIPE ALL DATA to continue: ").strip()
    if confirmation != "WIPE ALL DATA":
        print("Cancelled. No data was changed.")
        return 1

    gym_name = input("Gym name: ").strip()
    owner_name = input("Owner full name: ").strip()
    owner_phone = input("Owner phone: ").strip()
    owner_user = input("Owner username: ").strip()
    owner_pass = getpass.getpass("Set a strong owner password (minimum 12 characters): ")
    confirm_pass = getpass.getpass("Confirm owner password: ")
    if not all((gym_name, owner_name, owner_phone, owner_user)):
        print("All fields are required. No data was changed.")
        return 1
    if len(owner_pass) < 12 or owner_pass != confirm_pass:
        print("Password must be at least 12 characters and both entries must match. No data was changed.")
        return 1

    init_db()
    # The explicit confirmation above is required before any deletion.
    for table in TABLES_TO_CLEAR:
        execute_statement(f"DELETE FROM {table};")
    setup_initial_owner(
        gym_name=gym_name, currency="PKR", timezone="Asia/Karachi",
        username=owner_user, password=owner_pass, full_name=owner_name,
        phone=owner_phone, email=""
    )
    print("Owner account created. Password was not printed; provide it to the owner securely.")
    print("Open your configured live HTTPS URL and sign in with the username you entered.")
    return 0

if __name__ == "__main__":
    raise SystemExit(prepare())
