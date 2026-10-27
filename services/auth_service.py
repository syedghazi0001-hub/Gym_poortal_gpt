import zoneinfo
from datetime import datetime
from database.connection import query_one, query_all, execute_insert, execute_statement
from auth.security import hash_password, verify_password, generate_uuid
from config import Config

def get_gym_settings():
    """Retrieve the singleton gym settings record, or create default if missing."""
    settings = query_one("SELECT * FROM gym_settings WHERE id = 1;")
    if not settings:
        execute_statement("""
            INSERT INTO gym_settings (id, gym_name, gym_tagline, currency, timezone, accent_color)
            VALUES (1, 'Vanguard Fitness Club', 'Premium Strength & Performance Gym', 'PKR', 'Asia/Karachi', '#10B981')
            ON CONFLICT (id) DO NOTHING;
        """)
        settings = query_one("SELECT * FROM gym_settings WHERE id = 1;")
    return settings

def update_gym_settings(gym_name, gym_tagline, currency, timezone, accent_color, contact_phone, contact_email, address, absence_threshold_days):
    """Update gym settings configuration."""
    sql = """
        UPDATE gym_settings
        SET gym_name = %s,
            gym_tagline = %s,
            currency = %s,
            timezone = %s,
            accent_color = %s,
            contact_phone = %s,
            contact_email = %s,
            address = %s,
            absence_threshold_days = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1;
    """
    execute_statement(sql, (
        gym_name, gym_tagline, currency, timezone, accent_color,
        contact_phone, contact_email, address, absence_threshold_days
    ))
    return get_gym_settings()

def has_owner_account() -> bool:
    """Check if at least one active owner account exists in the database."""
    res = query_one("SELECT COUNT(*) AS count FROM users WHERE role = 'owner' AND is_active = TRUE;")
    return res["count"] > 0 if res else False

def setup_initial_owner(gym_name, currency, timezone, username, password, full_name, phone, email=None):
    """
    Initial one-time setup: Configure gym settings and create the primary owner account.
    Fails if an owner already exists to prevent tampering.
    """
    if has_owner_account():
        raise ValueError("An owner account already exists. Setup is locked.")
    
    # 1. Update or initialize gym_settings
    execute_statement("""
        INSERT INTO gym_settings (id, gym_name, currency, timezone, updated_at)
        VALUES (1, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (id) DO UPDATE SET
            gym_name = EXCLUDED.gym_name,
            currency = EXCLUDED.currency,
            timezone = EXCLUDED.timezone,
            updated_at = CURRENT_TIMESTAMP;
    """, (gym_name, currency, timezone))
    
    # 2. Create Owner User
    user_id = generate_uuid()
    p_hash = hash_password(password)
    
    execute_statement("""
        INSERT INTO users (id, username, password_hash, role, is_active)
        VALUES (%s, %s, %s, 'owner', TRUE);
    """, (user_id, username.strip(), p_hash))
    
    # 3. Create Owner Profile
    profile_id = generate_uuid()
    execute_statement("""
        INSERT INTO profiles (id, user_id, full_name, phone, email, avatar_color)
        VALUES (%s, %s, %s, %s, %s, '#10B981');
    """, (profile_id, user_id, full_name.strip(), phone.strip(), (email or "").strip()))
    
    # 4. Audit Log
    execute_statement("""
        INSERT INTO audit_logs (id, user_id, username, action, resource_type, resource_id, details)
        VALUES (%s, %s, %s, 'INITIAL_SETUP', 'SYSTEM', %s, 'Initial gym setup completed successfully.');
    """, (generate_uuid(), user_id, username, user_id))
    
    return {"user_id": user_id, "username": username, "role": "owner"}

def authenticate_user(username, password):
    """
    Authenticate a user by username and password.
    Returns user dict on success, None on failure.
    """
    user = query_one("""
        SELECT u.id, u.username, u.password_hash, u.role, u.is_active,
               COALESCE(p.full_name, t.full_name, r.full_name, m.full_name, u.username) AS full_name
        FROM users u
        LEFT JOIN profiles p ON p.user_id = u.id
        LEFT JOIN trainers t ON t.user_id = u.id
        LEFT JOIN receptionists r ON r.user_id = u.id
        LEFT JOIN members m ON m.user_id = u.id
        WHERE LOWER(u.username) = LOWER(%s);
    """, (username.strip(),))
    
    if not user:
        return None
        
    if not user["is_active"]:
        return {"error": "Account is deactivated. Please contact the gym owner."}
        
    if not verify_password(password, user["password_hash"]):
        return None
        
    # Update last login timestamp
    execute_statement("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s;", (user["id"],))
    return user

def change_user_password(user_id, current_password, new_password):
    """Safely verify old password and update to new password."""
    user = query_one("SELECT id, password_hash FROM users WHERE id = %s;", (user_id,))
    if not user:
        return False, "User not found."
    
    if not verify_password(current_password, user["password_hash"]):
        return False, "Current password is incorrect."
        
    if len(new_password) < 12:
        return False, "New password must be at least 12 characters long."
        
    new_hash = hash_password(new_password)
    execute_statement("UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s;", (new_hash, user_id))
    return True, "Password updated successfully."
