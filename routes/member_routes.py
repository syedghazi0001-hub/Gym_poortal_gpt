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
from services.staff_service import get_trainer_notes_for_member
from services.auth_service import get_gym_settings
from database.connection import query_one

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

    return render_template(
        "member/dashboard.html",
        member=member,
        qr_data_uri=qr_data_uri,
        stats=stats,
        recent_attendance=recent_attendance,
        payments=payments,
        is_current_paid=is_current_paid,
        current_payment=current_payment,
        current_month=current_month,
        absence_alert=absence_alert,
        notes=notes,
        settings=settings,
        today=today
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
