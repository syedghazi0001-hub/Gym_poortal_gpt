import uuid
import secrets
import hmac
import hashlib
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session, request, abort

def hash_password(password: str) -> str:
    """Hash password securely using Werkzeug's default modern algorithm (pbkdf2/scrypt)."""
    return generate_password_hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against stored hash."""
    if not hashed_password or not plain_password:
        return False
    return check_password_hash(hashed_password, plain_password)

def generate_uuid() -> str:
    """Generate a clean 36-character UUID string."""
    return str(uuid.uuid4())

def generate_qr_token() -> str:
    """Generate a high-entropy URL-safe QR token for member badge verification."""
    return f"GYM-{secrets.token_hex(16).upper()}"

def generate_csrf_token() -> str:
    """Generate or retrieve the session CSRF token."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]

def validate_csrf_token(token: str) -> bool:
    """Validate submitted CSRF token against session."""
    expected = session.get("_csrf_token")
    if not expected or not token:
        return False
    return hmac.compare_digest(expected, token)

def generate_receipt_number(billing_month: str) -> str:
    """Generate a unique human-friendly receipt number, e.g. REC-202610-A9B2."""
    clean_month = billing_month.replace("-", "")
    suffix = secrets.token_hex(2).upper()
    return f"REC-{clean_month}-{suffix}"

def generate_member_code(sequence_num: int) -> str:
    """Generate consistent formatted member ID, e.g. MEM-2026-0042."""
    year = datetime.now().year
    return f"MEM-{year}-{sequence_num:04d}"
