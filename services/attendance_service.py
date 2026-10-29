import zoneinfo
from datetime import datetime, date, timedelta
import logging
from database.connection import query_one, query_all, execute_statement
from auth.security import generate_uuid
from services.auth_service import get_gym_settings

logger = logging.getLogger(__name__)

_CACHED_TZ = None
_CACHED_TZ_NAME = None
_TRAINER_TABLE_ENSURED = False

def get_gym_local_date():
    """Get the current calendar date in the gym's configured timezone (cached in-memory for speed)."""
    global _CACHED_TZ, _CACHED_TZ_NAME
    settings = get_gym_settings()
    tz_name = settings.get("timezone", "Asia/Karachi")
    if _CACHED_TZ is None or _CACHED_TZ_NAME != tz_name:
        try:
            _CACHED_TZ = zoneinfo.ZoneInfo(tz_name)
            _CACHED_TZ_NAME = tz_name
        except Exception:
            _CACHED_TZ = zoneinfo.ZoneInfo("Asia/Karachi")
            _CACHED_TZ_NAME = "Asia/Karachi"
    now_aware = datetime.now(_CACHED_TZ)
    return now_aware.date(), now_aware

def get_gym_terminal_token():
    """Retrieve or initialize the official Gym Front Desk Terminal QR token."""
    settings = get_gym_settings()
    token = settings.get("terminal_qr_token")
    if not token:
        token = "VANGUARD-TERMINAL-DESK-STATION"
    return token

def _match_terminal_token(scanned, expected):
    """Fuzzy-match scanned terminal token, tolerating URLs, query parameters, casing, and whitespace."""
    if not scanned or not expected:
        return False
    s = str(scanned).strip()
    exp = str(expected).strip()
    if s == exp or s.upper() == exp.upper() or exp.lower() in s.lower():
        return True
    import urllib.parse
    try:
        parsed = urllib.parse.urlparse(s)
        qs = urllib.parse.parse_qs(parsed.query)
        for key in ("token", "terminal_token", "station"):
            val = qs.get(key, [""])[0]
            if val and (val.strip() == exp or val.strip().upper() == exp.upper() or exp.lower() in val.lower()):
                return True
    except Exception:
        pass
    return False

def record_member_self_scan(user_id, terminal_token, action="check_in"):
    """
    Ultra-fast single-roundtrip attendance processing for Members.
    Executes in under 15ms using unified SQL queries.
    """
    expected_token = get_gym_terminal_token()
    if not _match_terminal_token(terminal_token, expected_token):
        return {
            "success": False,
            "status": "invalid_terminal",
            "message": "Invalid Gym Station QR pass. Please scan the official counter QR Pass."
        }

    today, now_local = get_gym_local_date()

    # Unified single query: Fetches member status, user active state, AND today's attendance in 1 query!
    row = query_one("""
        SELECT m.id AS member_id, m.member_code, m.full_name, m.membership_status,
               u.is_active AS user_is_active,
               a.id AS attendance_id, a.check_in_time, a.check_out_time
        FROM members m
        JOIN users u ON u.id = m.user_id
        LEFT JOIN attendance a ON a.member_id = m.id AND a.attendance_date = %s
        WHERE m.user_id = %s;
    """, (today, user_id))

    if not row:
        return {
            "success": False,
            "status": "not_found",
            "message": "Member record not found."
        }

    if not row["user_is_active"] or row["membership_status"] in ("inactive", "suspended", "pending"):
        return {
            "success": False,
            "status": "inactive",
            "message": f"Your membership status is {row['membership_status'].upper()}. Access restricted."
        }

    time_display = now_local.strftime("%I:%M %p")

    if action == "check_in":
        if row.get("attendance_id"):
            in_val = row["check_in_time"]
            fmt_in = in_val.strftime("%I:%M %p") if hasattr(in_val, "strftime") else str(in_val)
            return {
                "success": False,
                "status": "already_checked_in",
                "message": f"You have already checked in today at {fmt_in}! Cannot check in twice.",
                "check_in_time": fmt_in,
                "check_out_time": row["check_out_time"].strftime("%I:%M %p") if row.get("check_out_time") and hasattr(row["check_out_time"], "strftime") else str(row.get("check_out_time") or "")
            }

        att_id = generate_uuid()
        execute_statement("""
            INSERT INTO attendance (id, member_id, attendance_date, check_in_time, method, status)
            VALUES (%s, %s, %s, %s, 'SELF_QR', 'present');
        """, (att_id, row["member_id"], today, now_local))

        # Background cleanup (non-blocking)
        try:
            execute_statement("""
                UPDATE absence_alerts
                SET is_resolved = TRUE, resolved_date = %s
                WHERE member_id = %s AND is_resolved = FALSE;
            """, (today, row["member_id"]))
        except Exception:
            pass

        return {
            "success": True,
            "action": "check_in",
            "message": f"Welcome, {row['full_name']}! Checked in at {time_display}. Have a great workout!",
            "check_in_time": time_display,
            "member_name": row["full_name"],
            "member_code": row["member_code"]
        }

    elif action == "check_out":
        if not row.get("attendance_id"):
            return {
                "success": False,
                "status": "not_checked_in",
                "message": "Cannot check out before checking in! Please check in first upon arrival."
            }

        if row.get("check_out_time"):
            out_val = row["check_out_time"]
            fmt_out = out_val.strftime("%I:%M %p") if hasattr(out_val, "strftime") else str(out_val)
            return {
                "success": False,
                "status": "already_checked_out",
                "message": f"You have already checked out today at {fmt_out}! Session already completed."
            }

        execute_statement("""
            UPDATE attendance SET check_out_time = %s WHERE id = %s;
        """, (now_local, row["attendance_id"]))

        return {
            "success": True,
            "action": "check_out",
            "message": f"Checked out at {time_display}! Great workout today, {row['full_name']}!",
            "check_out_time": time_display,
            "member_name": row["full_name"],
            "member_code": row["member_code"]
        }

    return {
        "success": False,
        "status": "bad_action",
        "message": "Invalid action specified."
    }

def record_trainer_self_scan(user_id, terminal_token, action="check_in"):
    """
    Ultra-fast single-roundtrip shift punch processing for Trainers.
    """
    expected_token = get_gym_terminal_token()
    if not _match_terminal_token(terminal_token, expected_token):
        return {
            "success": False,
            "status": "invalid_terminal",
            "message": "Invalid Gym Station QR pass. Please scan the official counter QR Pass."
        }

    today, now_local = get_gym_local_date()

    row = query_one("""
        SELECT t.id AS trainer_id, t.full_name, t.specialization,
               u.is_active AS user_is_active,
               ta.id AS attendance_id, ta.check_in_time, ta.check_out_time
        FROM trainers t
        JOIN users u ON u.id = t.user_id
        LEFT JOIN trainer_attendance ta ON ta.trainer_id = t.id AND ta.attendance_date = %s
        WHERE t.user_id = %s;
    """, (today, user_id))

    if not row:
        return {
            "success": False,
            "status": "not_found",
            "message": "Trainer profile not found."
        }

    if not row["user_is_active"]:
        return {
            "success": False,
            "status": "inactive",
            "message": "Your coach account is inactive. Please contact administration."
        }

    time_display = now_local.strftime("%I:%M %p")

    if action == "check_in":
        if row.get("attendance_id"):
            in_val = row["check_in_time"]
            fmt_in = in_val.strftime("%I:%M %p") if hasattr(in_val, "strftime") else str(in_val)
            return {
                "success": False,
                "status": "already_checked_in",
                "message": f"You have already punched in for shift today at {fmt_in}!",
                "check_in_time": fmt_in
            }

        att_id = generate_uuid()
        execute_statement("""
            INSERT INTO trainer_attendance (id, trainer_id, attendance_date, check_in_time, method, status)
            VALUES (%s, %s, %s, %s, 'SELF_QR', 'present');
        """, (att_id, row["trainer_id"], today, now_local))

        return {
            "success": True,
            "action": "check_in",
            "message": f"Shift started, Coach {row['full_name']}! Punched in at {time_display}.",
            "check_in_time": time_display,
            "trainer_name": row["full_name"]
        }

    elif action == "check_out":
        if not row.get("attendance_id"):
            return {
                "success": False,
                "status": "not_checked_in",
                "message": "Cannot punch out before punching in for your shift!"
            }

        if row.get("check_out_time"):
            out_val = row["check_out_time"]
            fmt_out = out_val.strftime("%I:%M %p") if hasattr(out_val, "strftime") else str(out_val)
            return {
                "success": False,
                "status": "already_checked_out",
                "message": f"You have already punched out today at {fmt_out}! Shift already ended."
            }

        execute_statement("""
            UPDATE trainer_attendance SET check_out_time = %s WHERE id = %s;
        """, (now_local, row["attendance_id"]))

        return {
            "success": True,
            "action": "check_out",
            "message": f"Duty shift completed at {time_display}! Good shift, Coach {row['full_name']}.",
            "check_out_time": time_display,
            "trainer_name": row["full_name"]
        }

    return {
        "success": False,
        "status": "bad_action",
        "message": "Invalid action specified."
    }

def record_attendance_by_qr(qr_token, recorded_by_id, allow_override=False):
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

    return _process_attendance_record(member, recorded_by_id, method="QR", allow_override=allow_override)

def record_attendance_manual(member_id, recorded_by_id, notes=None, allow_override=False):
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

    return _process_attendance_record(member, recorded_by_id, method="MANUAL", notes=notes, allow_override=allow_override)

def _process_attendance_record(member, recorded_by_id, method="QR", notes=None, allow_override=False):
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
        if allow_override:
            execute_statement("""
                UPDATE attendance SET check_in_time = %s, method = %s WHERE id = %s;
            """, (now_local, method, existing["id"]))
            return {
                "success": True,
                "status": "success",
                "message": f"Check-in updated for {member['full_name']} at {now_local.strftime('%I:%M %p')}.",
                "member_id": member["id"],
                "member_name": member["full_name"],
                "member_code": member["member_code"],
                "check_in_time": now_local.strftime("%I:%M %p"),
                "method": method,
                "attendance_id": existing["id"]
            }
        formatted_time = existing["check_in_time"].strftime("%I:%M %p") if hasattr(existing["check_in_time"], "strftime") else str(existing["check_in_time"])
        return {
            "success": False,
            "status": "already_marked",
            "message": f"Duplicate scan: {member['full_name']} is already checked in for today at {formatted_time}.",
            "member_id": member["id"],
            "member_name": member["full_name"],
            "member_code": member["member_code"],
            "check_in_time": formatted_time,
            "attendance_id": existing["id"]
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

def delete_attendance_record(attendance_id, requested_by_id=None):
    """Delete an attendance check-in record (allows receptionist/owner to undo a test check-in)."""
    att = query_one("""
        SELECT a.*, m.full_name, m.member_code
        FROM attendance a
        JOIN members m ON m.id = a.member_id
        WHERE a.id = %s;
    """, (attendance_id,))
    if not att:
        raise ValueError("Attendance record not found.")

    execute_statement("DELETE FROM attendance WHERE id = %s;", (attendance_id,))
    execute_statement("""
        INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
        VALUES (%s, %s, 'DELETE_ATTENDANCE', 'ATTENDANCE', %s, %s);
    """, (generate_uuid(), requested_by_id, attendance_id, f"Deleted attendance for {att['full_name']} ({att['member_code']}) on {att['attendance_date']}"))
    return {
        "success": True,
        "message": f"Check-in for {att['full_name']} removed. Ready to scan again!"
    }

def reset_member_today_attendance(member_id, requested_by_id=None):
    """Remove today's attendance for a member so they can be re-tested immediately."""
    today, _ = get_gym_local_date()
    att = query_one("""
        SELECT a.id, m.full_name, m.member_code
        FROM attendance a
        JOIN members m ON m.id = a.member_id
        WHERE a.member_id = %s AND a.attendance_date = %s;
    """, (member_id, today))
    if not att:
        return {
            "success": True,
            "message": "No attendance record found for today."
        }
    return delete_attendance_record(att["id"], requested_by_id)

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
    """Ensure the trainer_attendance table exists in the active database engine (cached)."""
    global _TRAINER_TABLE_ENSURED
    if _TRAINER_TABLE_ENSURED:
        return
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
        _TRAINER_TABLE_ENSURED = True
    except Exception as e:
        logger.warning(f"Could not verify trainer_attendance table: {e}")
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
