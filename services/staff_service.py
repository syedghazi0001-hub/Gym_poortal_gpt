import logging
from database.connection import query_one, query_all, execute_statement
from auth.security import hash_password, generate_uuid

logger = logging.getLogger(__name__)

# ============================================================================
# TRAINERS
# ============================================================================

def create_trainer(full_name, phone, email, specialization, bio, hire_date, username, password, created_by_id=None):
    """Create a new trainer account with login credentials."""
    # Check duplicate username
    existing_user = query_one("SELECT id FROM users WHERE LOWER(username) = LOWER(%s);", (username.strip(),))
    if existing_user:
        raise ValueError(f"Username '{username}' is already taken.")

    user_id = generate_uuid()
    trainer_id = generate_uuid()
    p_hash = hash_password(password)

    # 1. Create user
    execute_statement("""
        INSERT INTO users (id, username, password_hash, role, is_active)
        VALUES (%s, %s, %s, 'trainer', TRUE);
    """, (user_id, username.strip(), p_hash))

    # 2. Create trainer profile
    execute_statement("""
        INSERT INTO trainers (id, user_id, full_name, phone, email, specialization, bio, hire_date, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE);
    """, (trainer_id, user_id, full_name.strip(), phone.strip(), (email or "").strip(),
          (specialization or "General Fitness").strip(), (bio or "").strip(), hire_date))

    # 3. Audit log
    execute_statement("""
        INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
        VALUES (%s, %s, 'CREATE_TRAINER', 'TRAINER', %s, %s);
    """, (generate_uuid(), created_by_id, trainer_id, f"Created trainer {full_name} ({username})"))

    return get_trainer_by_id(trainer_id)

def get_all_trainers(active_only=False):
    """Retrieve list of trainers with count of assigned members."""
    sql = """
        SELECT t.*, u.username,
               COUNT(m.id) AS assigned_members_count
        FROM trainers t
        JOIN users u ON u.id = t.user_id
        LEFT JOIN members m ON m.assigned_trainer_id = t.id AND m.membership_status = 'active'
        WHERE (%s = FALSE OR t.is_active = TRUE)
        GROUP BY t.id, u.username
        ORDER BY t.full_name ASC;
    """
    return query_all(sql, (active_only,))

def get_trainer_by_id(trainer_id):
    """Retrieve single trainer by id."""
    sql = """
        SELECT t.*, u.username
        FROM trainers t
        JOIN users u ON u.id = t.user_id
        WHERE t.id = %s;
    """
    return query_one(sql, (trainer_id,))

def get_trainer_by_user_id(user_id):
    """Retrieve single trainer by user_id."""
    sql = """
        SELECT t.*, u.username
        FROM trainers t
        JOIN users u ON u.id = t.user_id
        WHERE t.user_id = %s;
    """
    return query_one(sql, (user_id,))

def update_trainer_status(trainer_id, is_active, updated_by_id=None):
    """Activate or deactivate a trainer and their login access."""
    trainer = get_trainer_by_id(trainer_id)
    if not trainer:
        raise ValueError("Trainer not found.")
    
    execute_statement("UPDATE trainers SET is_active = %s WHERE id = %s;", (is_active, trainer_id))
    execute_statement("UPDATE users SET is_active = %s WHERE id = %s;", (is_active, trainer["user_id"]))
    
    execute_statement("""
        INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
        VALUES (%s, %s, 'UPDATE_TRAINER_STATUS', 'TRAINER', %s, %s);
    """, (generate_uuid(), updated_by_id, trainer_id, f"Trainer {trainer['full_name']} active status set to {is_active}"))

# ============================================================================
# RECEPTIONISTS
# ============================================================================

def create_receptionist(full_name, phone, email, shift, username, password, created_by_id=None):
    """Create a new front desk receptionist account."""
    existing_user = query_one("SELECT id FROM users WHERE LOWER(username) = LOWER(%s);", (username.strip(),))
    if existing_user:
        raise ValueError(f"Username '{username}' is already taken.")

    user_id = generate_uuid()
    receptionist_id = generate_uuid()
    p_hash = hash_password(password)

    # 1. Create user
    execute_statement("""
        INSERT INTO users (id, username, password_hash, role, is_active)
        VALUES (%s, %s, %s, 'receptionist', TRUE);
    """, (user_id, username.strip(), p_hash))

    # 2. Create receptionist profile
    execute_statement("""
        INSERT INTO receptionists (id, user_id, full_name, phone, email, shift, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, TRUE);
    """, (receptionist_id, user_id, full_name.strip(), phone.strip(), (email or "").strip(), (shift or "Morning").strip()))

    # 3. Audit log
    execute_statement("""
        INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
        VALUES (%s, %s, 'CREATE_RECEPTIONIST', 'RECEPTIONIST', %s, %s);
    """, (generate_uuid(), created_by_id, receptionist_id, f"Created receptionist {full_name} ({username})"))

    return get_receptionist_by_id(receptionist_id)

def get_all_receptionists(active_only=False):
    """Retrieve list of receptionists."""
    sql = """
        SELECT r.*, u.username
        FROM receptionists r
        JOIN users u ON u.id = r.user_id
        WHERE (%s = FALSE OR r.is_active = TRUE)
        ORDER BY r.full_name ASC;
    """
    return query_all(sql, (active_only,))

def get_receptionist_by_id(receptionist_id):
    """Retrieve single receptionist by id."""
    sql = """
        SELECT r.*, u.username
        FROM receptionists r
        JOIN users u ON u.id = r.user_id
        WHERE r.id = %s;
    """
    return query_one(sql, (receptionist_id,))

def update_receptionist_status(receptionist_id, is_active, updated_by_id=None):
    """Activate or deactivate a receptionist."""
    receptionist = get_receptionist_by_id(receptionist_id)
    if not receptionist:
        raise ValueError("Receptionist not found.")
    
    execute_statement("UPDATE receptionists SET is_active = %s WHERE id = %s;", (is_active, receptionist_id))
    execute_statement("UPDATE users SET is_active = %s WHERE id = %s;", (is_active, receptionist["user_id"]))
    
    execute_statement("""
        INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
        VALUES (%s, %s, 'UPDATE_RECEPTIONIST_STATUS', 'RECEPTIONIST', %s, %s);
    """, (generate_uuid(), updated_by_id, receptionist_id, f"Receptionist {receptionist['full_name']} status set to {is_active}"))

def delete_trainer(trainer_id, owner_id=None):
    """Permanently delete a trainer and their user account."""
    trainer = query_one("SELECT id, user_id, full_name FROM trainers WHERE id = %s;", (trainer_id,))
    if not trainer:
        return False, "Trainer not found."

    user_id = trainer["user_id"]
    execute_statement("UPDATE members SET assigned_trainer_id = NULL WHERE assigned_trainer_id = %s;", (trainer_id,))
    execute_statement("DELETE FROM trainer_notes WHERE trainer_id = %s;", (trainer_id,))
    execute_statement("DELETE FROM notifications WHERE user_id = %s;", (user_id,))
    execute_statement("DELETE FROM trainers WHERE id = %s;", (trainer_id,))
    execute_statement("DELETE FROM users WHERE id = %s;", (user_id,))

    if owner_id:
        execute_statement("""
            INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
            VALUES (%s, %s, 'DELETE_TRAINER', 'TRAINER', %s, %s);
        """, (generate_uuid(), owner_id, trainer_id, f"Deleted trainer {trainer['full_name']}"))

    return True, f"Trainer '{trainer['full_name']}' has been permanently removed."

def delete_receptionist(receptionist_id, owner_id=None):
    """Permanently delete a receptionist and their user account."""
    receptionist = query_one("SELECT id, user_id, full_name FROM receptionists WHERE id = %s;", (receptionist_id,))
    if not receptionist:
        return False, "Receptionist not found."

    user_id = receptionist["user_id"]
    execute_statement("DELETE FROM notifications WHERE user_id = %s;", (user_id,))
    execute_statement("DELETE FROM receptionists WHERE id = %s;", (receptionist_id,))
    execute_statement("DELETE FROM users WHERE id = %s;", (user_id,))

    if owner_id:
        execute_statement("""
            INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
            VALUES (%s, %s, 'DELETE_RECEPTIONIST', 'RECEPTIONIST', %s, %s);
        """, (generate_uuid(), owner_id, receptionist_id, f"Deleted receptionist {receptionist['full_name']}"))

    return True, f"Receptionist '{receptionist['full_name']}' has been permanently removed."

# ============================================================================
# TRAINER ASSIGNED MEMBERS & NOTES
# ============================================================================

def get_trainer_assigned_members(trainer_id):
    """Retrieve active members assigned to a specific trainer."""
    sql = """
        SELECT m.*, u.username,
               (SELECT MAX(attendance_date) FROM attendance WHERE member_id = m.id) AS last_attended_date
        FROM members m
        JOIN users u ON u.id = m.user_id
        WHERE m.assigned_trainer_id = %s
        ORDER BY m.full_name ASC;
    """
    return query_all(sql, (trainer_id,))

def add_trainer_note(trainer_id, member_id, note_text):
    """Add a training progress note for an assigned member."""
    if not note_text or not note_text.strip():
        raise ValueError("Note content cannot be empty.")
        
    note_id = generate_uuid()
    execute_statement("""
        INSERT INTO trainer_notes (id, trainer_id, member_id, note)
        VALUES (%s, %s, %s, %s);
    """, (note_id, trainer_id, member_id, note_text.strip()))
    return note_id

def get_trainer_notes_for_member(member_id):
    """Retrieve all trainer notes for a member."""
    sql = """
        SELECT tn.*, t.full_name AS trainer_name
        FROM trainer_notes tn
        JOIN trainers t ON t.id = tn.trainer_id
        WHERE tn.member_id = %s
        ORDER BY tn.created_at DESC;
    """
    return query_all(sql, (member_id,))
