import zoneinfo
from datetime import datetime, date, timedelta
import logging
from database.connection import query_one, query_all, execute_statement
from auth.security import generate_uuid
from services.auth_service import get_gym_settings

logger = logging.getLogger(__name__)

def get_gym_local_date():
    """Get the current calendar date in the gym's configured timezone."""
    settings = get_gym_settings()
    tz_name = settings.get("timezone", "Asia/Karachi")
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("Asia/Karachi")
    return datetime.now(tz).date(), datetime.now(tz)

def record_attendance_by_qr(qr_token, recorded_by_id):
    """
    Process QR code check-in from receptionist scanner.
    Enforces status checks, duplicate check, and absence alert resolution.
    """
    # 1. Look up member by token
    member = query_one("""
        SELECT m.id, m.user_id, m.member_code, m.full_name, m.membership_status,
               m.membership_end_date, u.is_active AS user_is_active
        FROM members m
        JOIN users u ON u.id = m.user_id
        WHERE m.qr_token = %s;
    """, (qr_token.strip(),))

    if not member:
        return {
            "success": False,
            "status": "not_found",
            "message": "Invalid QR Code. No matching gym member found."
        }

    return _process_attendance_record(member, recorded_by_id, method="QR")

def record_attendance_manual(member_id, recorded_by_id, notes=None):
    """
    Process manual attendance check-in (front desk manual lookup).
    """
    member = query_one("""
        SELECT m.id, m.user_id, m.member_code, m.full_name, m.membership_status,
               m.membership_end_date, u.is_active AS user_is_active
        FROM members m
        JOIN users u ON u.id = m.user_id
        WHERE m.id = %s;
    """, (member_id,))

    if not member:
        return {
            "success": False,
            "status": "not_found",
            "message": "Member not found."
        }

    return _process_attendance_record(member, recorded_by_id, method="MANUAL", notes=notes)

def _process_attendance_record(member, recorded_by_id, method="QR", notes=None):
    """Internal helper to validate membership, check duplicates, and record attendance."""
    today, now_local = get_gym_local_date()

    # 1. Check membership status
    if not member["user_is_active"] or member["membership_status"] in ("inactive", "suspended"):
        return {
            "success": False,
            "status": "inactive",
            "message": f"Membership for {member['full_name']} ({member['member_code']}) is {member['membership_status'].upper()}. Check-in denied."
        }

    # 2. Check membership expiry date
    mem_end = member["membership_end_date"]
    if isinstance(mem_end, str):
        try:
            mem_end = datetime.strptime(mem_end[:10], "%Y-%m-%d").date()
        except Exception:
            pass

    if mem_end and mem_end < today:
        return {
            "success": False,
            "status": "expired",
            "message": f"Membership for {member['full_name']} expired on {member['membership_end_date']}. Renewal required."
        }

    # 3. Check duplicate attendance for today
    existing = query_one("""
        SELECT id, check_in_time, method
        FROM attendance
        WHERE member_id = %s AND attendance_date = %s;
    """, (member["id"], today))

    if existing:
        formatted_time = existing["check_in_time"].strftime("%I:%M %p") if hasattr(existing["check_in_time"], "strftime") else str(existing["check_in_time"])
        return {
            "success": False,
            "status": "already_marked",
            "message": f"Duplicate scan: {member['full_name']} is already checked in for today at {formatted_time}."
        }

    # 4. Insert attendance record
    att_id = generate_uuid()
    # Ensure recorded_by_id is a valid user ID or None
    valid_recorder_id = None
    if recorded_by_id:
        user_check = query_one("SELECT id FROM users WHERE id = %s;", (recorded_by_id,))
        if user_check:
            valid_recorder_id = user_check["id"]

    try:
        execute_statement("""
            INSERT INTO attendance (id, member_id, attendance_date, check_in_time, recorded_by_id, method, status, notes)
            VALUES (%s, %s, %s, %s, %s, %s, 'present', %s);
        """, (att_id, member["id"], today, now_local, valid_recorder_id, method, notes))
    except Exception as e:
        logger.error(f"Error inserting attendance: {e}")
        return {
            "success": False,
            "status": "error",
            "message": "Failed to record attendance due to database constraint."
        }

    # 5. Resolve active absence alert if present
    execute_statement("""
        UPDATE absence_alerts
        SET is_resolved = TRUE, resolved_date = %s
        WHERE member_id = %s AND is_resolved = FALSE;
    """, (today, member["id"]))

    # 6. Audit log
    execute_statement("""
        INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
        VALUES (%s, %s, 'ATTENDANCE_CHECKIN', 'ATTENDANCE', %s, %s);
    """, (generate_uuid(), recorded_by_id, att_id, f"Checked in {member['full_name']} via {method}"))

    return {
        "success": True,
        "status": "success",
        "message": f"Welcome, {member['full_name']}! Attendance verified.",
        "member_name": member["full_name"],
        "member_code": member["member_code"],
        "check_in_time": now_local.strftime("%I:%M %p"),
        "method": method
    }

def get_today_attendance():
    """Retrieve all attendance records for today."""
    today, _ = get_gym_local_date()
    sql = """
        SELECT a.*, m.full_name, m.member_code, m.phone,
               u_rec.username AS recorded_by_name
        FROM attendance a
        JOIN members m ON m.id = a.member_id
        LEFT JOIN users u_rec ON u_rec.id = a.recorded_by_id
        WHERE a.attendance_date = %s
        ORDER BY a.check_in_time DESC;
    """
    return query_all(sql, (today,))

def get_attendance_logs(date_filter=None, limit=100, offset=0):
    """Retrieve attendance logs with optional date filter."""
    params = []
    where_sql = "1=1"
    if date_filter:
        where_sql += " AND a.attendance_date = %s"
        params.append(date_filter)
        
    sql = f"""
        SELECT a.*, m.full_name, m.member_code, m.phone,
               u_rec.username AS recorded_by_name
        FROM attendance a
        JOIN members m ON m.id = a.member_id
        LEFT JOIN users u_rec ON u_rec.id = a.recorded_by_id
        WHERE {where_sql}
        ORDER BY a.check_in_time DESC
        LIMIT %s OFFSET %s;
    """
    params.extend([limit, offset])
    return query_all(sql, tuple(params))

def get_member_attendance_history(member_id, limit=60):
    """Retrieve full attendance history for a specific member."""
    sql = """
        SELECT a.*, u_rec.username AS recorded_by_name
        FROM attendance a
        LEFT JOIN users u_rec ON u_rec.id = a.recorded_by_id
        WHERE a.member_id = %s
        ORDER BY a.attendance_date DESC
        LIMIT %s;
    """
    return query_all(sql, (member_id, limit))

def calculate_member_attendance_stats(member_id):
    """
    Calculate comprehensive attendance stats:
    - total attended days
    - total days since membership start
    - total absent days
    - current streak (consecutive attendance days)
    """
    member = query_one("SELECT membership_start_date FROM members WHERE id = %s;", (member_id,))
    if not member:
        return {"total_attended": 0, "total_absent": 0, "streak": 0}

    today, _ = get_gym_local_date()
    start_date = member["membership_start_date"]
    if isinstance(start_date, str):
        try:
            start_date = datetime.strptime(start_date[:10], "%Y-%m-%d").date()
        except Exception:
            start_date = today

    # Total attended count
    att_count_row = query_one("SELECT COUNT(*) AS total FROM attendance WHERE member_id = %s;", (member_id,))
    total_attended = att_count_row["total"] if att_count_row else 0

    # Total calendar days active
    days_since_start = max(1, (today - start_date).days + 1)
    total_absent = max(0, days_since_start - total_attended)

    # Current streak calculation
    # Fetch dates attended in descending order
    dates_rows = query_all("""
        SELECT attendance_date
        FROM attendance
        WHERE member_id = %s
        ORDER BY attendance_date DESC;
    """, (member_id,))
    
    attended_dates = {r["attendance_date"] for r in dates_rows}
    streak = 0
    check_day = today
    # If not attended today, check if attended yesterday to continue streak
    if check_day not in attended_dates:
        check_day = today - timedelta(days=1)

    while check_day in attended_dates:
        streak += 1
        check_day -= timedelta(days=1)

    return {
        "total_attended": total_attended,
        "total_absent": total_absent,
        "streak": streak,
        "days_since_start": days_since_start
    }

def get_daily_attendance_trend(days=14):
    """Get count of attendance for the past N days for dashboard charts."""
    today, _ = get_gym_local_date()
    start_day = today - timedelta(days=days - 1)
    
    sql = """
        SELECT attendance_date, COUNT(*) AS count
        FROM attendance
        WHERE attendance_date >= %s
        GROUP BY attendance_date
        ORDER BY attendance_date ASC;
    """
    rows = query_all(sql, (start_day,))
    counts_map = {r["attendance_date"]: r["count"] for r in rows}

    trend = []
    curr = start_day
    while curr <= today:
        trend.append({
            "date": curr.strftime("%b %d"),
            "full_date": curr.strftime("%Y-%m-%d"),
            "count": counts_map.get(curr, 0)
        })
        curr += timedelta(days=1)
    return trend
