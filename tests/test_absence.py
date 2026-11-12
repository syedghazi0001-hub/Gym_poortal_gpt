import pytest
from datetime import timedelta
from app import create_app
from config import TestingConfig
from database.connection import query_one, execute_statement
from services.auth_service import setup_initial_owner
from services.member_service import create_member
from services.absence_service import run_ten_day_absence_check, get_active_absence_alerts
from services.attendance_service import record_attendance_by_qr, get_gym_local_date

def test_ten_day_absence_logic(app):
    with app.app_context():
        # Ensure owner exists
        owner = query_one("SELECT * FROM users WHERE role = 'owner' LIMIT 1;")
        if not owner:
            try:
                setup_initial_owner(
                    gym_name="Vanguard Fitness Club",
                    currency="PKR",
                    timezone="Asia/Karachi",
                    username="admin",
                    password="AdminPassword123!",
                    full_name="Gym Owner Malik",
                    phone="+923001234567"
                )
            except Exception:
                pass

        execute_statement("DELETE FROM absence_alerts;")
        execute_statement("DELETE FROM notifications WHERE category = 'absence';")
        today, _ = get_gym_local_date()

        # 1. Create a member who joined 5 days ago (should NOT trigger alert)
        recent_date = (today - timedelta(days=5)).strftime("%Y-%m-%d")
        recent_member = create_member(
            full_name="Recent Member 5d",
            phone="+923005555555",
            start_date=recent_date,
            end_date="2026-11-20",
            monthly_fee=5000,
            username="recent_user_5d",
            password="Password123!"
        )

        # 2. Create a member who joined 15 days ago and never attended (SHOULD trigger alert)
        absent_date = (today - timedelta(days=15)).strftime("%Y-%m-%d")
        absent_member = create_member(
            full_name="Absent Member 15d",
            phone="+923007777777",
            start_date=absent_date,
            end_date="2026-11-20",
            monthly_fee=5000,
            username="absent_user_15d",
            password="Password123!"
        )

        # 3. Run absence check
        res = run_ten_day_absence_check(force=True)
        assert res["status"] == "completed"

        # 4. Verify alerts in database
        alerts = get_active_absence_alerts()
        alert_member_ids = [a["member_id"] for a in alerts]

        assert absent_member["id"] in alert_member_ids
        assert recent_member["id"] not in alert_member_ids

        # Verify member warning notification text in Urdu as requested
        m_notif = query_one("""
            SELECT * FROM notifications
            WHERE user_id = %s AND category = 'absence';
        """, (absent_member["user_id"],))
        assert m_notif is not None
        assert "Aap ne pichlay 15 din se gym attendance mark nahi karwai" in m_notif["message"]

        # Verify owner notification text
        owner_notif = query_one("""
            SELECT * FROM notifications
            WHERE category = 'absence' AND message LIKE %s;
        """, (f"%{absent_member['full_name']}%",))
        assert owner_notif is not None
        assert "ne pichlay 15 din se attendance mark nahi karwai" in owner_notif["message"]

        # 5. Run check again: DUPLICATE ALERT MUST NOT BE CREATED!
        res_repeat = run_ten_day_absence_check(force=True)
        assert res_repeat["new_alerts_count"] == 0

        # 6. Now member attends gym! Alert must be automatically resolved
        att_res = record_attendance_by_qr(absent_member["qr_token"], owner["id"])
        assert att_res["success"] is True

        # Check alert status in DB
        resolved_alert = query_one("""
            SELECT * FROM absence_alerts WHERE member_id = %s;
        """, (absent_member["id"],))
        assert bool(resolved_alert["is_resolved"]) is True
        assert str(resolved_alert["resolved_date"])[:10] == str(today)[:10]
