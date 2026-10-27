from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from auth.decorators import role_required, get_current_user
from services.auth_service import get_gym_settings, update_gym_settings
from services.member_service import (
    create_member, update_member, get_all_members, get_member_by_id,
    generate_qr_code_image_data, regenerate_member_qr_token, delete_member
)
from services.staff_service import (
    create_trainer, get_all_trainers, get_trainer_by_id, update_trainer_status,
    create_receptionist, get_all_receptionists, get_receptionist_by_id, update_receptionist_status,
    get_trainer_notes_for_member, delete_trainer, delete_receptionist
)
from services.attendance_service import (
    get_today_attendance, get_attendance_logs, get_gym_local_date,
    get_member_attendance_history, calculate_member_attendance_stats,
    get_daily_attendance_trend, get_all_trainers_with_today_status,
    get_today_trainer_attendance, record_trainer_checkin, record_trainer_checkout
)
from services.payment_service import (
    get_current_billing_month, get_monthly_payment_status,
    record_monthly_payment, get_recent_payments, reverse_payment,
    get_member_payment_history, get_monthly_revenue_trend
)
from services.absence_service import (
    run_ten_day_absence_check, get_active_absence_alerts,
    get_all_absence_alerts_history, acknowledge_alert
)
from database.connection import query_one

owner_bp = Blueprint("owner", __name__, url_prefix="/owner")

@owner_bp.route("/dashboard")
@role_required("owner")
def dashboard():
    """Owner primary command center with real database statistics and analytics."""
    # Run throttled absence check in background
    try:
        run_ten_day_absence_check(force=False)
    except Exception:
        pass

    today, _ = get_gym_local_date()
    current_month = get_current_billing_month()

    # Core Metric Calculations (Consolidated into 1 multi-aggregate query to reduce remote DB roundtrips)
    counts = query_one("""
        SELECT 
            (SELECT COUNT(*) FROM members WHERE membership_status = 'active') AS active_members,
            (SELECT COUNT(*) FROM trainers WHERE is_active = TRUE) AS total_trainers,
            (SELECT COUNT(*) FROM receptionists WHERE is_active = TRUE) AS total_receptionists,
            (SELECT COUNT(*) FROM attendance WHERE attendance_date = %s) AS today_attendance;
    """, (today,))
    active_members_count = counts["active_members"] if counts else 0
    total_trainers_count = counts["total_trainers"] if counts else 0
    total_receptionists_count = counts["total_receptionists"] if counts else 0
    today_attendance_count = counts["today_attendance"] if counts else 0
    today_absent_count = max(0, active_members_count - today_attendance_count)

    # Monthly payment metrics
    payment_status = get_monthly_payment_status(current_month)
    paid_members_count = payment_status["metrics"]["paid_count"]
    pending_members_count = payment_status["metrics"]["pending_count"]
    total_collected_month = payment_status["metrics"]["total_collected"]

    # Alerts
    absence_alerts = get_active_absence_alerts()
    active_alerts_count = len(absence_alerts)

    # Recent activity
    recent_payments = get_recent_payments(limit=6)
    today_attendance = get_today_attendance()[:6]

    settings = get_gym_settings()

    return render_template(
        "owner/dashboard.html",
        active_members_count=active_members_count,
        total_trainers_count=total_trainers_count,
        total_receptionists_count=total_receptionists_count,
        today_attendance_count=today_attendance_count,
        today_absent_count=today_absent_count,
        paid_members_count=paid_members_count,
        pending_members_count=pending_members_count,
        total_collected_month=total_collected_month,
        active_alerts_count=active_alerts_count,
        absence_alerts=absence_alerts[:5],
        recent_payments=recent_payments,
        today_attendance=today_attendance,
        settings=settings,
        current_month=current_month
    )

# ============================================================================
# MEMBER MANAGEMENT
# ============================================================================

@owner_bp.route("/members")
@role_required("owner")
def members():
    """Member directory with search, filtering, and pagination."""
    search = request.args.get("q", "")
    status = request.args.get("status", "all")
    trainer_id = request.args.get("trainer", "all")
    page = int(request.args.get("page", 1))
    per_page = 20
    offset = (page - 1) * per_page

    member_list, total_count = get_all_members(
        search=search, status=status, trainer_id=trainer_id,
        limit=per_page, offset=offset
    )
    trainers = get_all_trainers(active_only=True)
    total_pages = max(1, (total_count + per_page - 1) // per_page)

    return render_template(
        "owner/members.html",
        members=member_list,
        trainers=trainers,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        search=search,
        status=status,
        trainer_id=trainer_id
    )

@owner_bp.route("/members/new", methods=["GET", "POST"])
@role_required("owner")
def new_member():
    """Register a new gym member."""
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        dob = request.form.get("dob") or None
        emergency_contact = request.form.get("emergency_contact", "").strip()
        membership_plan = request.form.get("membership_plan", "Monthly Standard")
        start_date = request.form.get("membership_start_date")
        end_date = request.form.get("membership_end_date")
        monthly_fee = request.form.get("monthly_fee", 5000)
        membership_status = request.form.get("membership_status", "active")
        assigned_trainer_id = request.form.get("assigned_trainer_id") or None
        notes = request.form.get("notes", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not full_name or not phone or not start_date or not end_date or not username or not password:
            flash("Please fill in all required fields.", "danger")
            trainers = get_all_trainers(active_only=True)
            return render_template("owner/member_form.html", trainers=trainers, member=None)

        try:
            member = create_member(
                full_name=full_name,
                phone=phone,
                email=email,
                dob=dob,
                emergency_contact=emergency_contact,
                membership_plan=membership_plan,
                start_date=start_date,
                end_date=end_date,
                monthly_fee=monthly_fee,
                membership_status=membership_status,
                assigned_trainer_id=assigned_trainer_id,
                notes=notes,
                username=username,
                password=password,
                created_by_id=session.get("user_id")
            )
            flash(f"Member {member['full_name']} ({member['member_code']}) created successfully!", "success")
            return redirect(url_for("owner.member_detail", member_id=member["id"]))
        except Exception as e:
            flash(f"Error creating member: {str(e)}", "danger")

    trainers = get_all_trainers(active_only=True)
    return render_template("owner/member_form.html", trainers=trainers, member=None)

@owner_bp.route("/members/<member_id>")
@role_required("owner")
def member_detail(member_id):
    """Member 360 profile view: identity, QR badge, stats, attendance, payments."""
    member = get_member_by_id(member_id)
    if not member:
        flash("Member not found.", "danger")
        return redirect(url_for("owner.members"))

    # Generate QR badge data URI
    qr_data_uri = generate_qr_code_image_data(member["qr_token"])
    
    # Attendance stats & history
    stats = calculate_member_attendance_stats(member_id, start_date=member.get("membership_start_date"))
    attendance_history = get_member_attendance_history(member_id, limit=30)
    
    # Payment history
    payments = get_member_payment_history(member_id)
    
    # Trainer notes
    notes = get_trainer_notes_for_member(member_id)
    
    settings = get_gym_settings()
    current_month = get_current_billing_month()

    return render_template(
        "owner/member_detail.html",
        member=member,
        qr_data_uri=qr_data_uri,
        stats=stats,
        attendance_history=attendance_history,
        payments=payments,
        notes=notes,
        settings=settings,
        current_month=current_month
    )

@owner_bp.route("/members/<member_id>/edit", methods=["GET", "POST"])
@role_required("owner")
def edit_member(member_id):
    """Edit member profile and trainer assignment."""
    member = get_member_by_id(member_id)
    if not member:
        flash("Member not found.", "danger")
        return redirect(url_for("owner.members"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        dob = request.form.get("dob") or None
        emergency_contact = request.form.get("emergency_contact", "").strip()
        membership_plan = request.form.get("membership_plan", "Monthly Standard")
        start_date = request.form.get("membership_start_date")
        end_date = request.form.get("membership_end_date")
        monthly_fee = request.form.get("monthly_fee", 5000)
        membership_status = request.form.get("membership_status", "active")
        assigned_trainer_id = request.form.get("assigned_trainer_id") or None
        notes = request.form.get("notes", "").strip()

        try:
            update_member(
                member_id=member_id,
                full_name=full_name,
                phone=phone,
                email=email,
                dob=dob,
                emergency_contact=emergency_contact,
                membership_plan=membership_plan,
                start_date=start_date,
                end_date=end_date,
                monthly_fee=monthly_fee,
                membership_status=membership_status,
                assigned_trainer_id=assigned_trainer_id,
                notes=notes,
                updated_by_id=session.get("user_id")
            )
            flash(f"Member {full_name} updated successfully.", "success")
            return redirect(url_for("owner.member_detail", member_id=member_id))
        except Exception as e:
            flash(f"Update failed: {str(e)}", "danger")

    trainers = get_all_trainers(active_only=True)
    return render_template("owner/member_form.html", trainers=trainers, member=member)

@owner_bp.route("/members/<member_id>/regenerate-qr", methods=["POST"])
@role_required("owner")
def regenerate_qr(member_id):
    """Revoke old QR token and issue a fresh one."""
    try:
        regenerate_member_qr_token(member_id, requested_by_id=session.get("user_id"))
        flash("QR Code has been revoked and regenerated successfully.", "success")
    except Exception as e:
        flash(f"Failed to regenerate QR: {str(e)}", "danger")
    return redirect(url_for("owner.member_detail", member_id=member_id))

# ============================================================================
# STAFF MANAGEMENT (TRAINERS & RECEPTIONISTS)
# ============================================================================

@owner_bp.route("/staff")
@role_required("owner")
def staff():
    """Staff directory (Trainers and Front Desk Receptionists) & Trainer Attendance."""
    try:
        trainers = get_all_trainers()
    except Exception:
        trainers = []

    try:
        receptionists = get_all_receptionists()
    except Exception:
        receptionists = []

    try:
        trainers_status = get_all_trainers_with_today_status()
    except Exception:
        trainers_status = []

    try:
        today_trainer_records = get_today_trainer_attendance()
    except Exception:
        today_trainer_records = []

    today, _ = get_gym_local_date()
    return render_template(
        "owner/staff.html",
        trainers=trainers,
        receptionists=receptionists,
        trainers_status=trainers_status,
        today_trainer_records=today_trainer_records,
        today_date=today.strftime("%A, %B %d, %Y")
    )

@owner_bp.route("/staff/trainers/<trainer_id>/checkin", methods=["POST"])
@role_required("owner")
def owner_trainer_checkin(trainer_id):
    """Owner logs checkin for a trainer."""
    try:
        res = record_trainer_checkin(trainer_id, recorded_by_id=session.get("user_id"), method="owner")
        flash(res["message"], "success")
    except Exception as e:
        flash(f"Check-in failed: {str(e)}", "danger")
    return redirect(url_for("owner.staff"))

@owner_bp.route("/staff/trainers/<trainer_id>/checkout", methods=["POST"])
@role_required("owner")
def owner_trainer_checkout(trainer_id):
    """Owner logs checkout for a trainer."""
    try:
        res = record_trainer_checkout(trainer_id)
        flash(res["message"], "success")
    except Exception as e:
        flash(f"Checkout failed: {str(e)}", "danger")
    return redirect(url_for("owner.staff"))

@owner_bp.route("/staff/trainer/new", methods=["POST"])
@role_required("owner")
def new_trainer():
    """Create a new trainer."""
    full_name = request.form.get("full_name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    specialization = request.form.get("specialization", "General Fitness").strip()
    bio = request.form.get("bio", "").strip()
    hire_date = request.form.get("hire_date") or None
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    try:
        create_trainer(
            full_name=full_name, phone=phone, email=email,
            specialization=specialization, bio=bio, hire_date=hire_date,
            username=username, password=password,
            created_by_id=session.get("user_id")
        )
        flash(f"Trainer {full_name} created successfully.", "success")
    except Exception as e:
        flash(f"Error creating trainer: {str(e)}", "danger")
    return redirect(url_for("owner.staff"))

@owner_bp.route("/staff/receptionist/new", methods=["POST"])
@role_required("owner")
def new_receptionist():
    """Create a new receptionist."""
    full_name = request.form.get("full_name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    shift = request.form.get("shift", "Morning").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    try:
        create_receptionist(
            full_name=full_name, phone=phone, email=email,
            shift=shift, username=username, password=password,
            created_by_id=session.get("user_id")
        )
        flash(f"Receptionist {full_name} created successfully.", "success")
    except Exception as e:
        flash(f"Error creating receptionist: {str(e)}", "danger")
    return redirect(url_for("owner.staff"))

@owner_bp.route("/staff/trainer/<trainer_id>/toggle", methods=["POST"])
@role_required("owner")
def toggle_trainer(trainer_id):
    """Toggle trainer active/inactive state."""
    trainer = get_trainer_by_id(trainer_id)
    if trainer:
        new_status = not trainer["is_active"]
        update_trainer_status(trainer_id, new_status, updated_by_id=session.get("user_id"))
        status_word = "activated" if new_status else "deactivated"
        flash(f"Trainer {trainer['full_name']} has been {status_word}.", "info")
    return redirect(url_for("owner.staff"))

@owner_bp.route("/staff/receptionist/<rec_id>/toggle", methods=["POST"])
@role_required("owner")
def toggle_receptionist(rec_id):
    """Toggle receptionist active/inactive state."""
    rec = get_receptionist_by_id(rec_id)
    if rec:
        new_status = not rec["is_active"]
        update_receptionist_status(rec_id, new_status, updated_by_id=session.get("user_id"))
        status_word = "activated" if new_status else "deactivated"
        flash(f"Receptionist {rec['full_name']} has been {status_word}.", "info")
    return redirect(url_for("owner.staff"))

# ============================================================================
# ATTENDANCE MANAGEMENT
# ============================================================================

@owner_bp.route("/attendance")
@role_required("owner")
def attendance():
    """Owner attendance records view with date filtering."""
    date_filter = request.args.get("date")
    today, _ = get_gym_local_date()
    if not date_filter:
        date_filter = today.strftime("%Y-%m-%d")

    logs = get_attendance_logs(date_filter=date_filter, limit=100)
    settings = get_gym_settings()

    return render_template(
        "owner/attendance.html",
        logs=logs,
        date_filter=date_filter,
        today=today.strftime("%Y-%m-%d"),
        settings=settings
    )

# ============================================================================
# MONTHLY PAYMENTS MANAGEMENT
# ============================================================================

@owner_bp.route("/payments")
@role_required("owner")
def payments():
    """Monthly payment collections, paid vs pending tracker."""
    month = request.args.get("month") or get_current_billing_month()
    status_filter = request.args.get("status", "all")
    search = request.args.get("q", "")

    overview = get_monthly_payment_status(
        billing_month=month, search=search, status_filter=status_filter
    )
    settings = get_gym_settings()

    return render_template(
        "owner/payments.html",
        overview=overview,
        selected_month=month,
        status_filter=status_filter,
        search=search,
        settings=settings
    )

@owner_bp.route("/payments/record", methods=["POST"])
@role_required("owner")
def record_payment():
    """Record manual payment from modal."""
    member_id = request.form.get("member_id")
    billing_month = request.form.get("billing_month")
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
        flash(f"Payment recorded successfully! Receipt: {payment['receipt_number']}", "success")
    except Exception as e:
        flash(f"Payment record failed: {str(e)}", "danger")

    return redirect(url_for("owner.payments", month=billing_month))

@owner_bp.route("/payments/<payment_id>/reverse", methods=["POST"])
@role_required("owner")
def reverse_pay(payment_id):
    """Reverse a payment record (preserves audit trail)."""
    reason = request.form.get("reason", "Owner manual reversal").strip()
    try:
        reverse_payment(payment_id, session.get("user_id"), reason=reason)
        flash("Payment reversed successfully. Audit record updated.", "info")
    except Exception as e:
        flash(f"Reversal failed: {str(e)}", "danger")
    return redirect(url_for("owner.payments"))

# ============================================================================
# 10-DAY ABSENCE ALERT CENTER
# ============================================================================

@owner_bp.route("/alerts")
@role_required("owner")
def alerts():
    """Ten-day consecutive absence alert dashboard."""
    active_alerts = get_active_absence_alerts()
    history_alerts = get_all_absence_alerts_history(limit=30)
    settings = get_gym_settings()

    return render_template(
        "owner/alerts.html",
        active_alerts=active_alerts,
        history_alerts=history_alerts,
        settings=settings
    )

@owner_bp.route("/alerts/trigger-check", methods=["POST"])
@role_required("owner")
def trigger_check():
    """Manually invoke the 10-day absence check engine."""
    try:
        res = run_ten_day_absence_check(force=True)
        flash(
            f"Absence check finished: {res['checked_members']} active members evaluated. "
            f"{res['new_alerts_count']} new alerts generated.",
            "success"
        )
    except Exception as e:
        flash(f"Absence check failed: {str(e)}", "danger")
    return redirect(url_for("owner.alerts"))

@owner_bp.route("/alerts/<alert_id>/acknowledge", methods=["POST"])
@role_required("owner")
def acknowledge(alert_id):
    """Acknowledge an absence alert."""
    try:
        acknowledge_alert(alert_id, session.get("user_id"))
        flash("Alert marked as acknowledged.", "success")
    except Exception as e:
        flash(f"Failed to acknowledge alert: {str(e)}", "danger")
    return redirect(url_for("owner.alerts"))

# ============================================================================
# GYM SETTINGS
# ============================================================================

@owner_bp.route("/settings", methods=["GET", "POST"])
@role_required("owner")
def settings():
    """Manage gym branding, currency, timezone, and thresholds."""
    if request.method == "POST":
        gym_name = request.form.get("gym_name", "Vanguard Fitness Club").strip()
        gym_tagline = request.form.get("gym_tagline", "").strip()
        currency = request.form.get("currency", "PKR").strip().upper()
        timezone = request.form.get("timezone", "Asia/Karachi").strip()
        accent_color = request.form.get("accent_color", "#10B981").strip()
        contact_phone = request.form.get("contact_phone", "").strip()
        contact_email = request.form.get("contact_email", "").strip()
        address = request.form.get("address", "").strip()
        threshold_days = int(request.form.get("absence_threshold_days", 10))

        try:
            update_gym_settings(
                gym_name=gym_name,
                gym_tagline=gym_tagline,
                currency=currency,
                timezone=timezone,
                accent_color=accent_color,
                contact_phone=contact_phone,
                contact_email=contact_email,
                address=address,
                absence_threshold_days=threshold_days
            )
            flash("Gym settings updated successfully.", "success")
        except Exception as e:
            flash(f"Failed to update settings: {str(e)}", "danger")

    current_settings = get_gym_settings()
    return render_template("owner/settings.html", settings=current_settings)

@owner_bp.route("/members/<member_id>/delete", methods=["POST"])
@role_required("owner")
def remove_member(member_id):
    """Permanently remove a member from the gym system."""
    success, msg = delete_member(member_id, owner_id=session.get("user_id"))
    flash(msg, "success" if success else "danger")
    return redirect(url_for("owner.members"))

@owner_bp.route("/staff/trainers/<trainer_id>/delete", methods=["POST"])
@role_required("owner")
def remove_trainer(trainer_id):
    """Permanently remove a trainer."""
    success, msg = delete_trainer(trainer_id, owner_id=session.get("user_id"))
    flash(msg, "success" if success else "danger")
    return redirect(url_for("owner.staff"))

@owner_bp.route("/staff/receptionists/<receptionist_id>/delete", methods=["POST"])
@role_required("owner")
def remove_receptionist(receptionist_id):
    """Permanently remove a receptionist."""
    success, msg = delete_receptionist(receptionist_id, owner_id=session.get("user_id"))
    flash(msg, "success" if success else "danger")
    return redirect(url_for("owner.staff"))
