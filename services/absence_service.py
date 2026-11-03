import zoneinfo
from datetime import datetime, date, timedelta
import logging
from database.connection import query_one, query_all, execute_statement
from auth.security import generate_uuid
from services.auth_service import get_gym_settings, invalidate_gym_settings_cache

logger = logging.getLogger(__name__)

def run_ten_day_absence_check(force=False):
    """
    Evaluates all active gym members for 10+ consecutive calendar days of absence.
    Generates alerts and notifications without spamming duplicates.
    """
    settings = get_gym_settings()
    tz_name = settings.get("timezone", "Asia/Karachi")
    threshold_days = settings.get("absence_threshold_days", 10)
    
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("Asia/Karachi")
        
    today = datetime.now(tz).date()

    # Throttling check: avoid running if checked within last 1 hour unless force=True
    if not force and settings.get("last_absence_check_at"):
        last_check = settings["last_absence_check_at"]
        if hasattr(last_check, "tzinfo") and last_check.tzinfo is None:
            last_check = last_check.replace(tzinfo=tz)
        if (datetime.now(tz) - last_check).total_seconds() < 3600:
            return {"status": "skipped", "reason": "throttled_within_1_hour", "new_alerts_count": 0}

    # Fetch all active members
    active_members = query_all("""
        SELECT m.id, m.user_id, m.member_code, m.full_name, m.phone, m.membership_start_date,
               m.membership_status
        FROM members m
        WHERE m.membership_status = 'active';
    """)

    # Fetch owner user ID for notifications
    owners = query_all("SELECT id FROM users WHERE role = 'owner' AND is_active = TRUE;")
    owner_ids = [o["id"] for o in owners]

    # Batch-fetch latest attendance dates for all members in a single query (prevents N+1)
    latest_att_rows = query_all("""
        SELECT member_id, MAX(attendance_date) AS last_date
        FROM attendance
        GROUP BY member_id;
    """)
    latest_attendance_map = {r["member_id"]: r["last_date"] for r in latest_att_rows}

    # Batch-fetch existing unresolved alerts in a single query (prevents N+1)
    existing_alerts_rows = query_all("""
        SELECT id, member_id, consecutive_days_absent
        FROM absence_alerts
        WHERE is_resolved = FALSE;
    """)
    existing_alerts_map = {r["member_id"]: r for r in existing_alerts_rows}

    new_alerts_count = 0

    for m in active_members:
        member_id = m["id"]
        start_date = m["membership_start_date"]

        last_date = latest_attendance_map.get(member_id) or start_date

        if not last_date:
            continue

        if isinstance(last_date, str):
            try:
                last_date = datetime.strptime(last_date[:10], "%Y-%m-%d").date()
            except Exception:
                continue

        days_absent = (today - last_date).days

        if days_absent >= threshold_days:
            existing_alert = existing_alerts_map.get(member_id)

            if not existing_alert:
                alert_id = generate_uuid()
                execute_statement("""
                    INSERT INTO absence_alerts (
                        id, member_id, last_attendance_date, consecutive_days_absent,
                        alert_date, is_resolved, acknowledged_by_owner
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, FALSE, FALSE
                    );
                """, (alert_id, member_id, last_date, days_absent, today))

                # 1. Notify Gym Owners
                owner_msg = (
                    f"Member {m['full_name']} (ID: {m['member_code']}, Phone: {m['phone']}) "
                    f"ne pichlay {days_absent} din se attendance mark nahi karwai."
                )
                for o_id in owner_ids:
                    execute_statement("""
                        INSERT INTO notifications (id, user_id, title, message, category, link_url)
                        VALUES (%s, %s, 'Ten-Day Absence Alert', %s, 'absence', '/owner/alerts');
                    """, (generate_uuid(), o_id, owner_msg))

                # 2. Notify the Member (warning inside their personal portal)
                member_msg = (
                    f"Aap ne pichlay {days_absent} din se gym attendance mark nahi karwai. "
                    "Apni attendance routine dobara shuru karne ke liye gym se rabta karein."
                )
                execute_statement("""
                    INSERT INTO notifications (id, user_id, title, message, category, link_url)
                    VALUES (%s, %s, 'Absence Warning', %s, 'absence', '/member/dashboard');
                """, (generate_uuid(), m["user_id"], member_msg))

                new_alerts_count += 1
                existing_alerts_map[member_id] = {
                    "id": alert_id,
                    "member_id": member_id,
                    "consecutive_days_absent": days_absent
                }
            elif existing_alert.get("consecutive_days_absent") != days_absent:
                # Update days_absent counter on the existing open alert only if changed
                execute_statement("""
                    UPDATE absence_alerts
                    SET consecutive_days_absent = %s
                    WHERE id = %s;
                """, (days_absent, existing_alert["id"]))
                existing_alert["consecutive_days_absent"] = days_absent

    # Update last check timestamp
    execute_statement("UPDATE gym_settings SET last_absence_check_at = CURRENT_TIMESTAMP WHERE id = 1;")
    invalidate_gym_settings_cache()

    return {
        "status": "completed",
        "checked_members": len(active_members),
        "new_alerts_count": new_alerts_count,
        "run_at": datetime.now(tz).isoformat()
    }

def get_active_absence_alerts():
    """Retrieve all open (unresolved) absence alerts."""
    sql = """
        SELECT a.*, m.full_name, m.member_code, m.phone, m.membership_status,
               m.membership_end_date, t.full_name AS trainer_name
        FROM absence_alerts a
        JOIN members m ON m.id = a.member_id
        LEFT JOIN trainers t ON t.id = m.assigned_trainer_id
        WHERE a.is_resolved = FALSE
        ORDER BY a.consecutive_days_absent DESC, a.alert_date DESC;
    """
    return query_all(sql)

def get_all_absence_alerts_history(limit=50):
    """Retrieve both active and resolved alerts."""
    sql = """
        SELECT a.*, m.full_name, m.member_code, m.phone
        FROM absence_alerts a
        JOIN members m ON m.id = a.member_id
        ORDER BY a.created_at DESC
        LIMIT %s;
    """
    return query_all(sql, (limit,))

def acknowledge_alert(alert_id, owner_id):
    """Mark an absence alert as acknowledged by the gym owner."""
    execute_statement("""
        UPDATE absence_alerts
        SET acknowledged_by_owner = TRUE, acknowledged_at = CURRENT_TIMESTAMP
        WHERE id = %s;
    """, (alert_id,))
    
    execute_statement("""
        INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
        VALUES (%s, %s, 'ACKNOWLEDGE_ABSENCE_ALERT', 'ABSENCE_ALERT', %s, 'Owner acknowledged absence alert');
    """, (generate_uuid(), owner_id, alert_id))
    return True
