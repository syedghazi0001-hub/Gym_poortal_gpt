from functools import wraps
from flask import session, redirect, url_for, flash, request, abort, jsonify, g, has_request_context
from database.connection import query_one

def clear_current_user_cache():
    """Clear request-scoped current user cache."""
    if has_request_context() and hasattr(g, "_current_user"):
        try:
            delattr(g, "_current_user")
        except Exception:
            pass

def get_current_user():
    """Retrieve the currently logged-in user details from session and database, cached per-request."""
    if has_request_context() and hasattr(g, "_current_user"):
        return g._current_user

    user_id = session.get("user_id")
    if not user_id:
        return None
    
    # Query user and profile
    sql = """
        SELECT u.id, u.username, u.role, u.is_active,
               COALESCE(p.full_name, t.full_name, r.full_name, m.full_name, u.username) AS full_name,
               COALESCE(p.avatar_color, '#10B981') AS avatar_color
        FROM users u
        LEFT JOIN profiles p ON p.user_id = u.id
        LEFT JOIN trainers t ON t.user_id = u.id
        LEFT JOIN receptionists r ON r.user_id = u.id
        LEFT JOIN members m ON m.user_id = u.id
        WHERE u.id = %s
    """
    user = query_one(sql, (user_id,))
    if not user or not user["is_active"]:
        session.clear()
        if has_request_context():
            g._current_user = None
        return None

    if has_request_context():
        g._current_user = user
    return user

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Authentication required"}), 401
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                if request.is_json or request.path.startswith("/api/"):
                    return jsonify({"success": False, "error": "Authentication required"}), 401
                flash("Please sign in to access this page.", "warning")
                return redirect(url_for("auth.login", next=request.path))
            
            user_role = session.get("user_role")
            if user_role not in allowed_roles:
                if request.is_json or request.path.startswith("/api/"):
                    return jsonify({"success": False, "error": "Access denied: insufficient permissions"}), 403
                flash("Access denied: You do not have permission to view that resource.", "danger")
                # Redirect to appropriate home page for the role
                if user_role == "owner":
                    return redirect(url_for("owner.dashboard"))
                elif user_role == "receptionist":
                    return redirect(url_for("receptionist.desk"))
                elif user_role == "trainer":
                    return redirect(url_for("trainer.dashboard"))
                elif user_role == "member":
                    return redirect(url_for("member.dashboard"))
                return redirect(url_for("auth.login"))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
