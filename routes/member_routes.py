from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from auth.decorators import role_required, get_current_user
from services.member_service import (
    get_member_by_user_id, generate_qr_code_image_data
)
from services.attendance_service import (
    get_member_attendance_history, calculate_member_attendance_stats,
    get_gym_local_date
)
from services.payment_service import (
    get_current_billing_month, get_member_payment_history
)
from services.staff_service import get_trainer_notes_for_member, get_all_trainers
from services.equipment_service import get_all_equipment, STANDARD_CATEGORIES
from services.auth_service import get_gym_settings
from auth.security import hash_password, verify_password
from database.connection import query_one, execute_statement

member_bp = Blueprint("member", __name__, url_prefix="/member")

@member_bp.route("/dashboard")
@role_required("member")
def dashboard():
    """Member personal portal dashboard."""
    user_id = session["user_id"]
    member = get_member_by_user_id(user_id)
    if not member:
        flash("Member record not found. Please contact administration.", "danger")
        return redirect(url_for("auth.login"))

    # Generate QR badge data URI
    qr_data_uri = generate_qr_code_image_data(member["qr_token"])

    # Attendance stats
    stats = calculate_member_attendance_stats(member["id"], start_date=member.get("membership_start_date"))
    recent_attendance = get_member_attendance_history(member["id"], limit=10)

    # Payments
    current_month = get_current_billing_month()
    payments = get_member_payment_history(member["id"])
    
    # Check current month payment status
    current_payment = next((p for p in payments if p["billing_month"] == current_month and p["status"] == "paid"), None)
    is_current_paid = bool(current_payment)

    # Check for active 10-day absence alert for this member
    absence_alert = query_one("""
        SELECT * FROM absence_alerts
        WHERE member_id = %s AND is_resolved = FALSE;
    """, (member["id"],))

    notes = get_trainer_notes_for_member(member["id"])
    settings = get_gym_settings()
    today, _ = get_gym_local_date()
    today_attendance = query_one(
        "SELECT * FROM attendance WHERE member_id = %s AND attendance_date = %s;",
        (member["id"], today)
    )

    return render_template(
        "member/dashboard.html",
        member=member,
        qr_data_uri=qr_data_uri,
        stats=stats,
        recent_attendance=recent_attendance,
        today_attendance=today_attendance,
        payments=payments,
        is_current_paid=is_current_paid,
        current_payment=current_payment,
        current_month=current_month,
        absence_alert=absence_alert,
        notes=notes,
        settings=settings,
        gym_settings=settings
    )

@member_bp.route("/attendance")
@role_required("member")
def attendance():
    """Member full attendance history."""
    user_id = session["user_id"]
    member = get_member_by_user_id(user_id)
    if not member:
        flash("Member record not found.", "danger")
        return redirect(url_for("auth.login"))

    history = get_member_attendance_history(member["id"], limit=100)
    stats = calculate_member_attendance_stats(member["id"], start_date=member.get("membership_start_date"))
    settings = get_gym_settings()

    return render_template(
        "member/attendance.html",
        member=member,
        history=history,
        stats=stats,
        settings=settings
    )

@member_bp.route("/payments")
@role_required("member")
def payments():
    """Member payment receipts & history."""
    user_id = session["user_id"]
    member = get_member_by_user_id(user_id)
    if not member:
        flash("Member record not found.", "danger")
        return redirect(url_for("auth.login"))

    history = get_member_payment_history(member["id"])
    current_month = get_current_billing_month()
    settings = get_gym_settings()

    return render_template(
        "member/payments.html",
        member=member,
        history=history,
        current_month=current_month,
        settings=settings
    )

@member_bp.route("/equipment")
@role_required("member")
def equipment():
    """Member gym equipment & machines directory."""
    user_id = session["user_id"]
    member = get_member_by_user_id(user_id)
    category = request.args.get("category", "all")
    items = get_all_equipment(category=category, status="all")
    settings = get_gym_settings()
    return render_template(
        "member/equipment.html",
        member=member,
        equipment=items,
        categories=STANDARD_CATEGORIES,
        current_category=category,
        settings=settings
    )

@member_bp.route("/trainers")
@role_required("member")
def trainers():
    """Member view of certified gym trainers."""
    user_id = session["user_id"]
    member = get_member_by_user_id(user_id)
    all_trainers = get_all_trainers()
    settings = get_gym_settings()
    return render_template(
        "member/trainers.html",
        member=member,
        trainers=all_trainers,
        settings=settings
    )

@member_bp.route("/change-password", methods=["GET", "POST"])
@role_required("member")
def change_password():
    """Member password update."""
    user_id = session["user_id"]
    member = get_member_by_user_id(user_id)
    settings = get_gym_settings()

    if request.method == "POST":
        current_pwd = request.form.get("current_password", "")
        new_pwd = request.form.get("new_password", "").strip()
        confirm_pwd = request.form.get("confirm_password", "").strip()

        user = query_one("SELECT password_hash FROM users WHERE id = %s;", (user_id,))
        if not user or not verify_password(current_pwd, user["password_hash"]):
            flash("Current password is incorrect.", "danger")
            return render_template("member/change_password.html", member=member, settings=settings)

        if len(new_pwd) < 6:
            flash("New password must be at least 6 characters.", "danger")
            return render_template("member/change_password.html", member=member, settings=settings)

        if new_pwd != confirm_pwd:
            flash("New passwords do not match.", "danger")
            return render_template("member/change_password.html", member=member, settings=settings)

        execute_statement("UPDATE users SET password_hash = %s WHERE id = %s;", (hash_password(new_pwd), user_id))
        flash("Password updated successfully!", "success")
        return redirect(url_for("member.dashboard"))

    return render_template("member/change_password.html", member=member, settings=settings)
