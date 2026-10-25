from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from services.auth_service import (
    has_owner_account, setup_initial_owner, authenticate_user,
    change_user_password, get_gym_settings
)
from services.notification_service import (
    get_user_notifications, get_unread_notification_count,
    mark_notification_as_read, mark_all_notifications_as_read
)
from auth.decorators import login_required, get_current_user
from auth.security import validate_csrf_token

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """Initial one-time setup wizard for gym owner."""
    if has_owner_account():
        flash("System is already configured. Please sign in.", "info")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        gym_name = request.form.get("gym_name", "Vanguard Fitness Club").strip()
        currency = request.form.get("currency", "PKR").strip().upper()
        timezone = request.form.get("timezone", "Asia/Karachi").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()

        # Validation
        if not username or not password or not full_name or not phone:
            flash("All required fields must be filled.", "danger")
            return render_template("setup.html")

        if len(password) < 12:
            flash("Password must be at least 12 characters long.", "danger")
            return render_template("setup.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("setup.html")

        try:
            res = setup_initial_owner(
                gym_name=gym_name,
                currency=currency,
                timezone=timezone,
                username=username,
                password=password,
                full_name=full_name,
                phone=phone,
                email=email
            )
            # Log in automatically
            session["user_id"] = res["user_id"]
            session["username"] = res["username"]
            session["user_role"] = res["role"]
            flash(f"Welcome to {gym_name}! Initial setup completed.", "success")
            return redirect(url_for("owner.dashboard"))
        except Exception as e:
            flash(f"Setup failed: {str(e)}", "danger")

    return render_template("setup.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Sign-in page for all user roles."""
    if not has_owner_account():
        return redirect(url_for("auth.setup"))

    if "user_id" in session:
        role = session.get("user_role")
        if role == "owner":
            return redirect(url_for("owner.dashboard"))
        elif role == "receptionist":
            return redirect(url_for("receptionist.desk"))
        elif role == "trainer":
            return redirect(url_for("trainer.dashboard"))
        elif role == "member":
            return redirect(url_for("member.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Please enter both username and password.", "danger")
            return render_template("auth/login.html")

        user = authenticate_user(username, password)
        if not user:
            flash("Invalid username or password.", "danger")
            return render_template("auth/login.html")

        if isinstance(user, dict) and "error" in user:
            flash(user["error"], "danger")
            return render_template("auth/login.html")

        # Session setup
        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["user_role"] = user["role"]
        session["full_name"] = user["full_name"]
        session.permanent = True

        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)

        # Route by role
        if user["role"] == "owner":
            return redirect(url_for("owner.dashboard"))
        elif user["role"] == "receptionist":
            return redirect(url_for("receptionist.desk"))
        elif user["role"] == "trainer":
            return redirect(url_for("trainer.dashboard"))
        elif user["role"] == "member":
            return redirect(url_for("member.dashboard"))

    return render_template("auth/login.html")

@auth_bp.route("/logout")
def logout():
    """Sign out the current user."""
    session.clear()
    flash("You have been signed out safely.", "info")
    return redirect(url_for("auth.login"))

@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Allow logged in user to change their password."""
    if request.method == "POST":
        current_password = request.form.get("current_password", "").strip()
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if new_password != confirm_password:
            flash("New passwords do not match.", "danger")
            return render_template("auth/change_password.html")

        ok, msg = change_user_password(session["user_id"], current_password, new_password)
        if ok:
            flash("Password updated successfully.", "success")
            role = session.get("user_role")
            if role == "owner":
                return redirect(url_for("owner.dashboard"))
            elif role == "receptionist":
                return redirect(url_for("receptionist.desk"))
            elif role == "trainer":
                return redirect(url_for("trainer.dashboard"))
            elif role == "member":
                return redirect(url_for("member.dashboard"))
        else:
            flash(msg, "danger")

    return render_template("auth/change_password.html")

@auth_bp.route("/notifications")
@login_required
def notifications():
    """User notification inbox."""
    user_id = session["user_id"]
    notifs = get_user_notifications(user_id, limit=50)
    return render_template("notifications.html", notifications=notifs)

@auth_bp.route("/notifications/read/<notif_id>", methods=["POST"])
@login_required
def read_notification(notif_id):
    """Mark a specific notification as read."""
    user_id = session["user_id"]
    mark_notification_as_read(notif_id, user_id)
    return jsonify({"success": True})

@auth_bp.route("/notifications/read-all", methods=["POST"])
@login_required
def read_all_notifications():
    """Mark all user notifications as read."""
    user_id = session["user_id"]
    mark_all_notifications_as_read(user_id)
    flash("All notifications marked as read.", "success")
    return redirect(url_for("auth.notifications"))
