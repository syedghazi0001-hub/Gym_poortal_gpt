#!/usr/bin/env python3
"""
scripts/seed_demo_data.py

Seeds realistic sample data into the database for demonstration and testing.
Creates owner, trainers, receptionists, members, attendance, and payment records.
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import init_db, execute_statement, query_one
from services.auth_service import setup_initial_owner, get_gym_settings
from services.staff_service import create_trainer, create_receptionist
from services.member_service import create_member
from services.attendance_service import record_attendance_by_qr, record_attendance_manual, get_gym_local_date
from services.payment_service import record_monthly_payment, get_current_billing_month
from services.absence_service import run_ten_day_absence_check

def seed():
    print("Initializing schema...")
    init_db()

    # Clear previous seed data
    print("Clearing previous records...")
    execute_statement("DELETE FROM audit_logs;")
    execute_statement("DELETE FROM notifications;")
    execute_statement("DELETE FROM absence_alerts;")
    execute_statement("DELETE FROM payments;")
    execute_statement("DELETE FROM attendance;")
    execute_statement("DELETE FROM trainer_notes;")
    execute_statement("DELETE FROM members;")
    execute_statement("DELETE FROM trainers;")
    execute_statement("DELETE FROM receptionists;")
    execute_statement("DELETE FROM profiles;")
    execute_statement("DELETE FROM users;")
    execute_statement("DELETE FROM gym_settings;")

    today, _ = get_gym_local_date()
    current_month = get_current_billing_month()

    # 1. Setup Gym Owner
    print("1. Creating Primary Gym Owner...")
    owner = setup_initial_owner(
        gym_name="Vanguard Fitness Club",
        currency="PKR",
        timezone="Asia/Karachi",
        username="owner",
        password="OwnerPassword123!",
        full_name="Malik Tariq (Gym Owner)",
        phone="+92 300 1234567",
        email="owner@vanguardfitness.com"
    )
    owner_id = owner["user_id"]

    # 2. Create Trainers
    print("2. Creating Trainers...")
    t1 = create_trainer(
        full_name="Coach Hamza",
        phone="+92 301 5551234",
        email="hamza@vanguard.com",
        specialization="Strength & Powerlifting",
        bio="Certified strength coach, 6+ years experience in Olympic lifting.",
        hire_date="2025-06-01",
        username="coach.hamza",
        password="CoachPassword123!",
        created_by_id=owner_id
    )

    t2 = create_trainer(
        full_name="Coach Bilal",
        phone="+92 302 7774321",
        email="bilal@vanguard.com",
        specialization="High Intensity & Conditioning",
        bio="Crossfit Level 2 Trainer with athletic conditioning background.",
        hire_date="2025-08-15",
        username="coach.bilal",
        password="CoachPassword123!",
        created_by_id=owner_id
    )

    # 3. Create Receptionists
    print("3. Creating Receptionists...")
    r1 = create_receptionist(
        full_name="Ayesha Khan",
        phone="+92 312 9998877",
        email="ayesha@vanguard.com",
        shift="Morning",
        username="receptionist",
        password="ReceptionPassword123!",
        created_by_id=owner_id
    )

    # 4. Create Members
    print("4. Creating Members...")
    # Member 1: Active, regular attendee, paid
    m1 = create_member(
        full_name="Zubair Ahmed",
        phone="+92 300 4441111",
        email="zubair@gmail.com",
        dob="1996-04-14",
        emergency_contact="Brother: 0300-1111111",
        membership_plan="VIP Unlimited",
        start_date=(today - timedelta(days=60)).strftime("%Y-%m-%d"),
        end_date=(today + timedelta(days=30)).strftime("%Y-%m-%d"),
        monthly_fee=7500,
        membership_status="active",
        assigned_trainer_id=t1["id"],
        notes="Goal: Hypertrophy & core stability",
        username="zubair",
        password="MemberPassword123!",
        created_by_id=owner_id
    )

    # Member 2: Active, attended today, fee pending
    m2 = create_member(
        full_name="Usman Farooq",
        phone="+92 301 2223333",
        email="usman@gmail.com",
        dob="1999-08-22",
        emergency_contact="Father: 0301-0000000",
        membership_plan="Standard Monthly",
        start_date=(today - timedelta(days=20)).strftime("%Y-%m-%d"),
        end_date=(today + timedelta(days=40)).strftime("%Y-%m-%d"),
        monthly_fee=5000,
        membership_status="active",
        assigned_trainer_id=t2["id"],
        notes="General cardio and strength",
        username="usman",
        password="MemberPassword123!",
        created_by_id=owner_id
    )

    # Member 3: Absent for 14 days (will trigger 10-day absence alert!)
    m3 = create_member(
        full_name="Kamran Shah",
        phone="+92 333 9991122",
        email="kamran@gmail.com",
        dob="1994-11-05",
        emergency_contact="Spouse: 0333-8888888",
        membership_plan="Standard Monthly",
        start_date=(today - timedelta(days=45)).strftime("%Y-%m-%d"),
        end_date=(today + timedelta(days=15)).strftime("%Y-%m-%d"),
        monthly_fee=5000,
        membership_status="active",
        assigned_trainer_id=t1["id"],
        notes="Knee strain in early October",
        username="kamran",
        password="MemberPassword123!",
        created_by_id=owner_id
    )

    # 5. Seed Attendance
    print("5. Recording historical attendance...")
    # Zubair attended multiple days including today
    for i in [6, 4, 3, 2, 1, 0]:
        past_date = today - timedelta(days=i)
        execute_statement("""
            INSERT INTO attendance (id, member_id, attendance_date, check_in_time, recorded_by_id, method, status)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s, 'QR', 'present')
            ON CONFLICT (member_id, attendance_date) DO NOTHING;
        """, (f"seed-att-zubair-{i}", m1["id"], past_date, owner_id))

    # Usman checked in today via receptionist
    execute_statement("""
        INSERT INTO attendance (id, member_id, attendance_date, check_in_time, recorded_by_id, method, status)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s, 'QR', 'present')
        ON CONFLICT (member_id, attendance_date) DO NOTHING;
    """, ("seed-att-usman-today", m2["id"], today, r1["user_id"]))

    # Kamran last attended 14 days ago
    fourteen_days_ago = today - timedelta(days=14)
    execute_statement("""
        INSERT INTO attendance (id, member_id, attendance_date, check_in_time, recorded_by_id, method, status)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s, 'QR', 'present')
        ON CONFLICT (member_id, attendance_date) DO NOTHING;
    """, ("seed-att-kamran-old", m3["id"], fourteen_days_ago, owner_id))

    # 6. Seed Monthly Payments
    print("6. Recording payments...")
    # Zubair paid for current month
    record_monthly_payment(
        member_id=m1["id"],
        billing_month=current_month,
        amount=7500,
        payment_method="bank_transfer",
        recorded_by_id=owner_id,
        notes="Online bank transfer ref #90812"
    )

    # 7. Run Absence Check to trigger 10-day alert for Kamran Shah
    print("7. Running 10-day absence check engine...")
    run_ten_day_absence_check(force=True)

    print("\n" + "=" * 60)
    print("Demo Data Seeded Successfully!")
    print("=" * 60)
    print("Accounts created:")
    print("  • Owner:        username='owner'         password='OwnerPassword123!'")
    print("  • Receptionist: username='receptionist'  password='ReceptionPassword123!'")
    print("  • Trainer 1:    username='coach.hamza'   password='CoachPassword123!'")
    print("  • Trainer 2:    username='coach.bilal'   password='CoachPassword123!'")
    print("  • Member 1:     username='zubair'        password='MemberPassword123!' (Paid, Regular)")
    print("  • Member 2:     username='usman'         password='MemberPassword123!' (Fee Pending)")
    print("  • Member 3:     username='kamran'        password='MemberPassword123!' (14-Day Absent Alert)")
    print("=" * 60)

if __name__ == "__main__":
    seed()
