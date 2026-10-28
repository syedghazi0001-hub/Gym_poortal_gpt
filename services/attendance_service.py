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
    Process QR code or member code check-in from receptionist terminal.
    Enforces status checks, duplicate check, and absence alert resolution.
    Supports raw qr_token, member_code (e.g. MBR-...), or phone number.
    """
    clean_val = qr_token.strip()
    member = query_one("""
        SELECT m.id, m.user_id, m.member_code, m.full_name, m.membership_status,
               m.membership_end_date, u.is_active AS user_is_active
        FROM members m
        JOIN users u ON u.id = m.user_id
        WHERE m.qr_token = %s OR m.member_code = %s OR m.phone = %s;
    """, (clean_val, clean_val, clean_val))

    if not member:
        return {
            "success": False,
            "status": "not_found",
            "message": "Invalid QR badge or code. No active gym member found."
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

def calculate_member_attendance_stats(member_id, start_date=None):
    """
    Calculate comprehensive attendance stats:
    - total attended days
    - total days since membership start
    - total absent days
    - current streak (consecutive attendance days)
    """
    if not start_date:
        member = query_one("SELECT membership_start_date FROM members WHERE id = %s;", (member_id,))
        if not member:
            return {"total_attended": 0, "total_absent": 0, "streak": 0}
        start_date = member["membership_start_date"]

    today, _ = get_gym_local_date()
    if isinstance(start_date, str):
        try:
            start_date = datetime.strptime(start_date[:10], "%Y-%m-%d").date()
        except Exception:
            start_date = today

    # Current streak & attended records calculation
    # Fetch dates attended in descending order (len(dates_rows) gives total_attended without a separate query)
    dates_rows = query_all("""
        SELECT attendance_date
        FROM attendance
        WHERE member_id = %s
        ORDER BY attendance_date DESC;
    """, (member_id,))

    total_attended = len(dates_rows)

    # Total calendar days active
    days_since_start = max(1, (today - start_date).days + 1)
    total_absent = max(0, days_since_start - total_attended)
    
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

# ============================================================================
# TRAINER ATTENDANCE ENGINE
# ============================================================================

def _ensure_trainer_attendance_table():
    """Ensure the trainer_attendance table exists in the active database engine."""
    from database.connection import get_db_backend
    backend = get_db_backend()
    try:
        if backend == "postgres":
            execute_statement("""
                CREATE TABLE IF NOT EXISTS trainer_attendance (
                    id VARCHAR(36) PRIMARY KEY,
                    trainer_id VARCHAR(36) NOT NULL REFERENCES trainers(id) ON DELETE CASCADE,
                    attendance_date DATE NOT NULL,
                    check_in_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    check_out_time TIMESTAMPTZ,
                    status VARCHAR(20) NOT NULL DEFAULT 'present',
                    method VARCHAR(30) NOT NULL DEFAULT 'desk_terminal',
                    recorded_by_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
                    notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_trainer_attendance_per_day UNIQUE (trainer_id, attendance_date)
                );
            """)
        else:
            execute_statement("""
                CREATE TABLE IF NOT EXISTS trainer_attendance (
                    id TEXT PRIMARY KEY,
                    trainer_id TEXT NOT NULL REFERENCES trainers(id) ON DELETE CASCADE,
                    attendance_date DATE NOT NULL,
                    check_in_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    check_out_time TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'present',
                    method TEXT NOT NULL DEFAULT 'desk_terminal',
                    recorded_by_id TEXT REFERENCES users(id) ON DELETE SET NULL,
                    notes TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_trainer_attendance_per_day UNIQUE (trainer_id, attendance_date)
                );
            """)
    except Exception as e:
        logger.debug("Table check for trainer_attendance: %s", e)

def record_trainer_checkin(trainer_id, recorded_by_id=None, method="desk_terminal", notes=None):
    """Record daily check-in for a gym trainer."""
    _ensure_trainer_attendance_table()
    trainer = query_one("SELECT * FROM trainers WHERE id = %s;", (trainer_id,))
    if not trainer:
        raise ValueError("Trainer not found.")
    if not trainer["is_active"]:
        raise ValueError("Trainer account is deactivated.")

    today, now_local = get_gym_local_date()

    existing = query_one(
        "SELECT id, check_in_time FROM trainer_attendance WHERE trainer_id = %s AND attendance_date = %s;",
        (trainer_id, today)
    )
    if existing:
        raise ValueError(f"Trainer '{trainer['full_name']}' has already checked in today at {existing['check_in_time']}.")

    att_id = generate_uuid()
    execute_statement("""
        INSERT INTO trainer_attendance (id, trainer_id, attendance_date, check_in_time, status, method, recorded_by_id, notes)
        VALUES (%s, %s, %s, %s, 'present', %s, %s, %s);
    """, (att_id, trainer_id, today, now_local, method, recorded_by_id, notes))

    execute_statement("""
        INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
        VALUES (%s, %s, 'TRAINER_CHECKIN', 'TRAINER_ATTENDANCE', %s, %s);
    """, (generate_uuid(), recorded_by_id, att_id, f"Trainer {trainer['full_name']} checked in via {method}"))

    return {
        "success": True,
        "trainer_id": trainer_id,
        "trainer_name": trainer["full_name"],
        "check_in_time": now_local.strftime("%I:%M %p"),
        "message": f"Trainer {trainer['full_name']} checked in successfully at {now_local.strftime('%I:%M %p')}."
    }

def record_trainer_checkout(trainer_id):
    """Record daily check-out time for a trainer."""
    _ensure_trainer_attendance_table()
    today, now_local = get_gym_local_date()

    att = query_one(
        "SELECT * FROM trainer_attendance WHERE trainer_id = %s AND attendance_date = %s;",
        (trainer_id, today)
    )
    if not att:
        raise ValueError("Trainer has not checked in today.")

    execute_statement(
        "UPDATE trainer_attendance SET check_out_time = %s WHERE id = %s;",
        (now_local, att["id"])
    )

    return {
        "success": True,
        "check_out_time": now_local.strftime("%I:%M %p"),
        "message": f"Checked out at {now_local.strftime('%I:%M %p')}."
    }

def get_today_trainer_attendance():
    """Get all trainer check-in records for today with error resilience."""
    today, _ = get_gym_local_date()
    _ensure_trainer_attendance_table()
    sql = """
        SELECT ta.*, t.full_name AS trainer_name, t.phone AS trainer_phone,
               t.specialization, u_rec.username AS recorded_by_name
        FROM trainer_attendance ta
        JOIN trainers t ON t.id = ta.trainer_id
        LEFT JOIN users u_rec ON u_rec.id = ta.recorded_by_id
        WHERE ta.attendance_date = %s
        ORDER BY ta.check_in_time DESC;
    """
    try:
        return query_all(sql, (today,))
    except Exception as e:
        logger.warning("Could not query today trainer attendance: %s", e)
        return []

def get_all_trainers_with_today_status():
    """Retrieve all active trainers along with their check-in status for today with zero-crash fallback."""
    today, _ = get_gym_local_date()
    _ensure_trainer_attendance_table()
    sql = """
        SELECT t.*, u.username,
               ta.id AS attendance_id,
               ta.check_in_time,
               ta.check_out_time,
               ta.status AS attendance_status,
               ta.method AS attendance_method,
               (SELECT COUNT(*) FROM members WHERE assigned_trainer_id = t.id) AS assigned_count
        FROM trainers t
        JOIN users u ON u.id = t.user_id
        LEFT JOIN trainer_attendance ta ON ta.trainer_id = t.id AND ta.attendance_date = %s
        WHERE t.is_active = 1
        ORDER BY t.full_name ASC;
    """
    try:
        return query_all(sql, (today,))
    except Exception as e:
        logger.error("Primary trainer attendance query failed: %s; using safe fallback", e)
        # Safe fallback: retrieve trainers without joining trainer_attendance so page never 500s!
        try:
            fallback_sql = """
                SELECT t.*, u.username,
                       NULL AS attendance_id,
                       NULL AS check_in_time,
                       NULL AS check_out_time,
                       'not_checked_in' AS attendance_status,
                       NULL AS attendance_method,
                       (SELECT COUNT(*) FROM members WHERE assigned_trainer_id = t.id) AS assigned_count
                FROM trainers t
                JOIN users u ON u.id = t.user_id
                WHERE t.is_active = 1
                ORDER BY t.full_name ASC;
            """
            return query_all(fallback_sql)
        except Exception as e2:
            logger.error("Fallback trainer query also failed: %s", e2)
            return []

def get_trainer_attendance_history(trainer_id, limit=30):
    """Retrieve attendance history for a single trainer with error resilience."""
    _ensure_trainer_attendance_table()
    sql = """
        SELECT ta.*, u_rec.username AS recorded_by_name
        FROM trainer_attendance ta
        LEFT JOIN users u_rec ON u_rec.id = ta.recorded_by_id
        WHERE ta.trainer_id = %s
        ORDER BY ta.attendance_date DESC, ta.check_in_time DESC
        LIMIT %s;
    """
    try:
        return query_all(sql, (trainer_id, limit))
    except Exception as e:
        logger.warning("Could not query trainer attendance history: %s", e)
        return []
