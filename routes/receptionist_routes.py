from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from auth.decorators import role_required, get_current_user
from services.auth_service import get_gym_settings
from services.member_service import get_all_members, get_member_by_id, generate_qr_code_image_data
from services.attendance_service import (
    record_attendance_by_qr, record_attendance_manual,
    get_today_attendance, get_gym_local_date,
    record_trainer_checkin, record_trainer_checkout,
    get_today_trainer_attendance, get_all_trainers_with_today_status,
    delete_attendance_record, get_gym_terminal_token
)
from services.payment_service import (
    get_current_billing_month, get_monthly_payment_status,
    record_monthly_payment
)

receptionist_bp = Blueprint("receptionist", __name__, url_prefix="/receptionist")

@receptionist_bp.route("/desk")
@role_required("receptionist", "owner")
def desk():
    """Receptionist Front Desk Terminal with Live QR Camera Scanner & Trainer Attendance."""
    today, _ = get_gym_local_date()
    try:
        today_records = get_today_attendance()
    except Exception:
        today_records = []

    try:
        trainers_status = get_all_trainers_with_today_status()
    except Exception:
        trainers_status = []

    try:
        today_trainer_records = get_today_trainer_attendance()
    except Exception:
        today_trainer_records = []

    try:
        members_res, _ = get_all_members(status="active", limit=30)
    except Exception:
        members_res = []

    try:
        settings = get_gym_settings()
    except Exception:
        settings = {"gym_name": "Vanguard Fitness Club", "currency": "PKR", "timezone": "Asia/Karachi"}

    terminal_token = get_gym_terminal_token()
    try:
        terminal_qr_data_uri = generate_qr_code_image_data(terminal_token)
    except Exception:
        terminal_qr_data_uri = ""

    current_month = get_current_billing_month()

    return render_template(
        "receptionist/desk.html",
        today_records=today_records,
        trainers_status=trainers_status,
        today_trainer_records=today_trainer_records,
        members_list=members_res,
        today_date=today.strftime("%A, %B %d, %Y"),
        settings=settings,
        terminal_token=terminal_token,
        terminal_qr_data_uri=terminal_qr_data_uri,
        current_month=current_month
    )

@receptionist_bp.route("/trainers/checkin", methods=["POST"])
@role_required("receptionist", "owner")
def trainer_checkin():
    """Record trainer attendance from front desk."""
    trainer_id = request.form.get("trainer_id")
    notes = request.form.get("notes", "").strip()
    try:
        res = record_trainer_checkin(
            trainer_id=trainer_id,
            recorded_by_id=session.get("user_id"),
            method="desk_terminal",
            notes=notes
        )
        flash(res["message"], "success")
    except Exception as e:
        flash(f"Trainer check-in failed: {str(e)}", "danger")
    return redirect(url_for("receptionist.desk"))

@receptionist_bp.route("/trainers/checkout", methods=["POST"])
@role_required("receptionist", "owner")
def trainer_checkout():
    """Record trainer checkout from front desk."""
    trainer_id = request.form.get("trainer_id")
    try:
        res = record_trainer_checkout(trainer_id=trainer_id)
        flash(res["message"], "success")
    except Exception as e:
        flash(f"Trainer check-out failed: {str(e)}", "danger")
    return redirect(url_for("receptionist.desk"))

@receptionist_bp.route("/attendance/<attendance_id>/delete", methods=["POST"])
@role_required("receptionist", "owner")
def delete_attendance(attendance_id):
    """Delete a check-in record for today (allows re-scan or correction)."""
    try:
        res = delete_attendance_record(attendance_id, requested_by_id=session.get("user_id"))
        flash(res["message"], "success")
    except Exception as e:
        flash(f"Could not remove check-in: {str(e)}", "danger")
    return redirect(url_for("receptionist.desk"))

@receptionist_bp.route("/attendance")
@role_required("receptionist", "owner")
def attendance():
    """Daily attendance log & manual check-in search."""
    today, _ = get_gym_local_date()
    today_records = get_today_attendance()
    settings = get_gym_settings()

    return render_template(
        "receptionist/attendance.html",
        today_records=today_records,
        today_date=today.strftime("%A, %B %d, %Y"),
        settings=settings
    )

@receptionist_bp.route("/payments")
@role_required("receptionist", "owner")
def payments():
    """Receptionist monthly fee collection & lookup."""
    month = request.args.get("month") or get_current_billing_month()
    status_filter = request.args.get("status", "all")
    search = request.args.get("q", "")

    overview = get_monthly_payment_status(
        billing_month=month, search=search, status_filter=status_filter
    )
    settings = get_gym_settings()

    return render_template(
        "receptionist/payments.html",
        overview=overview,
        selected_month=month,
        status_filter=status_filter,
        search=search,
        settings=settings
    )

@receptionist_bp.route("/payments/record", methods=["POST"])
@role_required("receptionist", "owner")
def record_payment():
    """Receptionist records a manual payment."""
    member_id = request.form.get("member_id")
    billing_month = request.form.get("billing_month") or get_current_billing_month()
    amount = request.form.get("amount")
    payment_method = request.form.get("payment_method", "cash")
    notes = request.form.get("notes", "").strip()

    try:
        payment = record_monthly_payment(
            member_id=member_id,
            billing_month=billing_month,
            amount=amount,
            payment_method=payment_method,
            recorded_by_id=session.get("user_id"),
            notes=notes
        )
        flash(f"Payment recorded! Receipt: {payment['receipt_number']}", "success")
    except Exception as e:
        flash(f"Payment recording failed: {str(e)}", "danger")

    return redirect(url_for("receptionist.payments", month=billing_month))
