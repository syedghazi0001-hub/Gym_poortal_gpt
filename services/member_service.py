import io
import base64
import logging
from datetime import datetime, date
import qrcode
from database.connection import query_one, query_all, execute_statement
from auth.security import hash_password, generate_uuid, generate_qr_token, generate_member_code

logger = logging.getLogger(__name__)

def generate_next_member_code():
    """Determine the next sequential member code for the current year."""
    year = datetime.now().year
    res = query_one("""
        SELECT COUNT(*) AS total
        FROM members
        WHERE member_code LIKE %s;
    """, (f"MEM-{year}-%",))
    next_num = (res["total"] if res else 0) + 1
    return generate_member_code(next_num)

def create_member(
    full_name, phone, start_date, end_date, monthly_fee,
    username, password, email=None, dob=None, emergency_contact=None,
    membership_plan="Monthly Standard", membership_status="active",
    assigned_trainer_id=None, notes=None, created_by_id=None
):
    """
    Create a new gym member along with their secure portal login account.
    Auto-generates Member ID and secure QR token.
    """
    # 1. Validate username uniqueness
    existing_user = query_one("SELECT id FROM users WHERE LOWER(username) = LOWER(%s);", (username.strip(),))
    if existing_user:
        raise ValueError(f"Username '{username}' is already in use.")

    # 2. Check phone duplicates if needed (soft check)
    existing_member_phone = query_one("SELECT id, full_name FROM members WHERE phone = %s;", (phone.strip(),))
    if existing_member_phone:
        raise ValueError(f"Phone number '{phone}' is already registered to {existing_member_phone['full_name']}.")

    # 3. Generate IDs
    user_id = generate_uuid()
    member_id = generate_uuid()
    member_code = generate_next_member_code()
    qr_token = generate_qr_token()
    p_hash = hash_password(password)

    # 4. Create User
    execute_statement("""
        INSERT INTO users (id, username, password_hash, role, is_active)
        VALUES (%s, %s, %s, 'member', TRUE);
    """, (user_id, username.strip(), p_hash))

    # 5. Create Profile
    profile_id = generate_uuid()
    execute_statement("""
        INSERT INTO profiles (id, user_id, full_name, phone, email, avatar_color)
        VALUES (%s, %s, %s, %s, %s, '#10B981');
    """, (profile_id, user_id, full_name.strip(), phone.strip(), (email or "").strip()))

    # 6. Insert Member
    execute_statement("""
        INSERT INTO members (
            id, user_id, member_code, full_name, phone, email, dob,
            emergency_contact, membership_plan, membership_start_date,
            membership_end_date, monthly_fee, membership_status,
            assigned_trainer_id, qr_token, notes
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s
        );
    """, (
        member_id, user_id, member_code, full_name.strip(), phone.strip(),
        (email or "").strip() or None, dob or None,
        (emergency_contact or "").strip() or None,
        (membership_plan or "Monthly Standard").strip(),
        start_date, end_date, float(monthly_fee),
        membership_status, (assigned_trainer_id or None),
        qr_token, (notes or "").strip() or None
    ))

    # 7. Audit log
    execute_statement("""
        INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
        VALUES (%s, %s, 'CREATE_MEMBER', 'MEMBER', %s, %s);
    """, (generate_uuid(), created_by_id, member_id, f"Created member {full_name} ({member_code})"))

    return get_member_by_id(member_id)

def register_member_self(full_name, phone=None, email=None, username=None, password=None, membership_plan="Standard Monthly", payment_preference="pay_later"):
    """
    Self-registration for new gym members (pending admin approval).
    Creates inactive user record and pending member record until admin approval.
    Username, password, and full name are required; phone and email are optional.
    """
    if not full_name or not (full_name.strip()):
        raise ValueError("Full name is required.")
    if not username or not (username.strip()):
        raise ValueError("Username is required.")
    if not password:
        raise ValueError("Password is required.")

    clean_username = username.strip()
    clean_full_name = full_name.strip()
    clean_phone = (phone or "").strip()
    clean_email = (email or "").strip()

    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")

    existing_user = query_one("SELECT id FROM users WHERE LOWER(username) = LOWER(%s);", (clean_username,))
    if existing_user:
        raise ValueError(f"Username '{clean_username}' is already in use.")

    if clean_phone:
        existing_member_phone = query_one("SELECT id, full_name FROM members WHERE phone = %s;", (clean_phone,))
        if existing_member_phone:
            raise ValueError(f"Phone number '{clean_phone}' is already registered to {existing_member_phone['full_name']}.")

    from datetime import timedelta
    from services.attendance_service import get_gym_local_date
    today, _ = get_gym_local_date()

    user_id = generate_uuid()
    member_id = generate_uuid()
    member_code = generate_next_member_code()
    qr_token = generate_qr_token()
    p_hash = hash_password(password)

    fee_pref_label = "Pay Now (Online/Cash ready)" if payment_preference == "pay_now" else "Pay Later (At Front Desk)"
    notes = f"Self-registered online — Pending Approval | Fee Preference: {fee_pref_label} | Reg Date: {today.isoformat()}"

    # 1. Create inactive user
    execute_statement("""
        INSERT INTO users (id, username, password_hash, role, is_active)
        VALUES (%s, %s, %s, 'member', 0);
    """, (user_id, clean_username, p_hash))

    # 2. Create Profile
    profile_id = generate_uuid()
    execute_statement("""
        INSERT INTO profiles (id, user_id, full_name, phone, email, avatar_color)
        VALUES (%s, %s, %s, %s, %s, '#10B981');
    """, (profile_id, user_id, clean_full_name, clean_phone, clean_email))

    # 3. Create Pending Member
    execute_statement("""
        INSERT INTO members (
            id, user_id, member_code, full_name, phone, email,
            membership_plan, membership_start_date, membership_end_date,
            monthly_fee, membership_status, qr_token, notes
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s,
            5000.0, 'pending', %s, %s
        );
    """, (
        member_id, user_id, member_code, clean_full_name, clean_phone or "None",
        clean_email or None, (membership_plan or "Standard Monthly").strip(),
        today, today + timedelta(days=30), qr_token, notes
    ))

    execute_statement("""
        INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
        VALUES (%s, %s, 'SELF_REGISTER', 'MEMBER', %s, %s);
    """, (generate_uuid(), user_id, member_id, f"Self-registered {clean_full_name} ({member_code})"))

    return get_member_by_id(member_id)

def update_member(
    member_id, full_name, phone, email, dob, emergency_contact,
    membership_plan, start_date, end_date, monthly_fee,
    membership_status, assigned_trainer_id, notes, updated_by_id=None
):
    """Update member profile details, trainer assignment, and status."""
    member = get_member_by_id(member_id)
    if not member:
        raise ValueError("Member not found.")

    execute_statement("""
        UPDATE members
        SET full_name = %s,
            phone = %s,
            email = %s,
            dob = %s,
            emergency_contact = %s,
            membership_plan = %s,
            membership_start_date = %s,
            membership_end_date = %s,
            monthly_fee = %s,
            membership_status = %s,
            assigned_trainer_id = %s,
            notes = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s;
    """, (
        full_name.strip(), phone.strip(), (email or "").strip() or None,
        dob or None, (emergency_contact or "").strip() or None,
        membership_plan.strip(), start_date, end_date,
        float(monthly_fee), membership_status,
        (assigned_trainer_id or None), (notes or "").strip() or None,
        member_id
    ))

    # Also update profile full_name, phone, email
    execute_statement("""
        UPDATE profiles
        SET full_name = %s, phone = %s, email = %s
        WHERE user_id = %s;
    """, (full_name.strip(), phone.strip(), (email or "").strip() or None, member["user_id"]))

    # Update user active status if membership is inactive/suspended
    is_active = (membership_status == "active")
    execute_statement("UPDATE users SET is_active = %s WHERE id = %s;", (is_active, member["user_id"]))

    # Audit log
    execute_statement("""
        INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
        VALUES (%s, %s, 'UPDATE_MEMBER', 'MEMBER', %s, %s);
    """, (generate_uuid(), updated_by_id, member_id, f"Updated member {full_name} ({member['member_code']})"))

    return get_member_by_id(member_id)

def regenerate_member_qr_token(member_id, requested_by_id=None):
    """Revoke old QR token and generate a fresh one."""
    member = get_member_by_id(member_id)
    if not member:
        raise ValueError("Member not found.")
    
    new_token = generate_qr_token()
    execute_statement("UPDATE members SET qr_token = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s;", (new_token, member_id))
    
    execute_statement("""
        INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
        VALUES (%s, %s, 'REGENERATE_QR', 'MEMBER', %s, %s);
    """, (generate_uuid(), requested_by_id, member_id, f"Regenerated QR token for {member['member_code']}"))
    
    return new_token

def get_member_by_id(member_id):
    """Retrieve full member details including assigned trainer name."""
    sql = """
        SELECT m.*, u.username, u.is_active AS user_is_active,
               t.full_name AS trainer_name, t.specialization AS trainer_specialization
        FROM members m
        JOIN users u ON u.id = m.user_id
        LEFT JOIN trainers t ON t.id = m.assigned_trainer_id
        WHERE m.id = %s;
    """
    return query_one(sql, (member_id,))

def get_member_by_user_id(user_id):
    """Retrieve member details given user_id."""
    sql = """
        SELECT m.*, u.username,
               t.full_name AS trainer_name, t.phone AS trainer_phone
        FROM members m
        JOIN users u ON u.id = m.user_id
        LEFT JOIN trainers t ON t.id = m.assigned_trainer_id
        WHERE m.user_id = %s;
    """
    return query_one(sql, (user_id,))

def get_member_by_qr_token(qr_token):
    """Retrieve member matching the scanned QR token."""
    sql = """
        SELECT m.*, u.username, u.is_active AS user_is_active,
               t.full_name AS trainer_name
        FROM members m
        JOIN users u ON u.id = m.user_id
        LEFT JOIN trainers t ON t.id = m.assigned_trainer_id
        WHERE m.qr_token = %s;
    """
    return query_one(sql, (qr_token,))

def get_all_members(search=None, status=None, trainer_id=None, limit=100, offset=0):
    """Filter and search members with pagination."""
    params = []
    where_clauses = ["1=1"]

    if search and search.strip():
        term = f"%{search.strip()}%"
        where_clauses.append("(m.full_name ILIKE %s OR m.member_code ILIKE %s OR m.phone ILIKE %s OR u.username ILIKE %s)")
        params.extend([term, term, term, term])

    if status and status.strip() and status != "all":
        where_clauses.append("m.membership_status = %s")
        params.append(status.strip())

    if trainer_id and trainer_id.strip() and trainer_id != "all":
        where_clauses.append("m.assigned_trainer_id = %s")
        params.append(trainer_id.strip())

    where_sql = " AND ".join(where_clauses)
    
    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM members m
        JOIN users u ON u.id = m.user_id
        WHERE {where_sql};
    """
    count_res = query_one(count_sql, tuple(params))
    total_count = count_res["total"] if count_res else 0

    sql = f"""
        SELECT m.*, u.username,
               t.full_name AS trainer_name,
               (SELECT MAX(attendance_date) FROM attendance WHERE member_id = m.id) AS last_attendance_date,
               (SELECT COUNT(*) FROM attendance WHERE member_id = m.id) AS total_attendance_count
        FROM members m
        JOIN users u ON u.id = m.user_id
        LEFT JOIN trainers t ON t.id = m.assigned_trainer_id
        WHERE {where_sql}
        ORDER BY m.created_at DESC
        LIMIT %s OFFSET %s;
    """
    params.extend([limit, offset])
    members = query_all(sql, tuple(params))
    return members, total_count

def delete_member(member_id, owner_id=None):
    """
    Permanently delete a gym member, associated user account, and all records.
    """
    member = query_one("SELECT id, user_id, full_name, member_code FROM members WHERE id = %s;", (member_id,))
    if not member:
        return False, "Member not found."

    user_id = member["user_id"]

    # Delete related dependent records
    execute_statement("DELETE FROM absence_alerts WHERE member_id = %s;", (member_id,))
    execute_statement("DELETE FROM trainer_notes WHERE member_id = %s;", (member_id,))
    execute_statement("DELETE FROM attendance WHERE member_id = %s;", (member_id,))
    execute_statement("DELETE FROM payments WHERE member_id = %s;", (member_id,))
    execute_statement("DELETE FROM notifications WHERE user_id = %s;", (user_id,))
    execute_statement("DELETE FROM members WHERE id = %s;", (member_id,))
    execute_statement("DELETE FROM users WHERE id = %s;", (user_id,))

    if owner_id:
        execute_statement("""
            INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
            VALUES (%s, %s, 'DELETE_MEMBER', 'MEMBER', %s, %s);
        """, (generate_uuid(), owner_id, member_id, f"Deleted member {member['full_name']} ({member['member_code']})"))

    logger.info("Member %s (%s) deleted by owner %s", member["full_name"], member_id, owner_id)
    return True, f"Member '{member['full_name']}' has been permanently removed."

def generate_qr_code_image_data(qr_token):
    """
    Generate high-resolution PNG QR Code for a member token,
    encoded as base64 data URI string.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(qr_token)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"
