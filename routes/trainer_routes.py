from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from auth.decorators import role_required, get_current_user
from services.staff_service import (
    get_trainer_by_user_id, get_trainer_assigned_members,
    add_trainer_note, get_trainer_notes_for_member
)
from services.member_service import get_member_by_id
from services.attendance_service import (
    get_member_attendance_history, calculate_member_attendance_stats,
    record_trainer_checkin, record_trainer_checkout,
    get_trainer_attendance_history, get_gym_local_date
)
from services.auth_service import get_gym_settings
from database.connection import query_one

trainer_bp = Blueprint("trainer", __name__, url_prefix="/trainer")

@trainer_bp.route("/dashboard")
@role_required("trainer")
def dashboard():
    """Trainer overview: Assigned members list and attendance status."""
    trainer = get_trainer_by_user_id(session["user_id"])
    if not trainer:
        flash("Trainer profile not found.", "danger")
        return redirect(url_for("auth.login"))

    today, _ = get_gym_local_date()
    try:
        today_attendance = query_one(
            "SELECT * FROM trainer_attendance WHERE trainer_id = %s AND attendance_date = %s;",
            (trainer["id"], today)
        )
    except Exception:
        today_attendance = None

    try:
        attendance_history = get_trainer_attendance_history(trainer["id"], limit=15)
    except Exception:
        attendance_history = []

    try:
        assigned_members = get_trainer_assigned_members(trainer["id"])
    except Exception:
        assigned_members = []

    try:
        settings = get_gym_settings()
    except Exception:
        settings = {"gym_name": "Vanguard Fitness Club", "currency": "PKR"}

    return render_template(
        "trainer/dashboard.html",
        trainer=trainer,
        today_attendance=today_attendance,
        attendance_history=attendance_history,
        assigned_members=assigned_members,
        settings=settings
    )

@trainer_bp.route("/punch-in", methods=["POST"])
@role_required("trainer")
def punch_in():
    """Trainer punches in for their shift."""
    trainer = get_trainer_by_user_id(session["user_id"])
    try:
        res = record_trainer_checkin(
            trainer_id=trainer["id"],
            recorded_by_id=session["user_id"],
            method="self",
            notes="Self punch-in"
        )
        flash(res["message"], "success")
    except Exception as e:
        flash(f"Check-in failed: {str(e)}", "danger")
    return redirect(url_for("trainer.dashboard"))

@trainer_bp.route("/punch-out", methods=["POST"])
@role_required("trainer")
def punch_out():
    """Trainer punches out from their shift."""
    trainer = get_trainer_by_user_id(session["user_id"])
    try:
        res = record_trainer_checkout(trainer["id"])
        flash(res["message"], "success")
    except Exception as e:
        flash(f"Check-out failed: {str(e)}", "danger")
    return redirect(url_for("trainer.dashboard"))

@trainer_bp.route("/members/<member_id>")
@role_required("trainer")
def member_detail(member_id):
    """View permitted member info & attendance history (trainer isolation enforced)."""
    trainer = get_trainer_by_user_id(session["user_id"])
    member = get_member_by_id(member_id)

    if not member:
        flash("Member not found.", "danger")
        return redirect(url_for("trainer.dashboard"))

    # Strict isolation check: Trainer can only view members assigned to them!
    if member["assigned_trainer_id"] != trainer["id"]:
        flash("Access Denied: You are not assigned to this member.", "danger")
        return redirect(url_for("trainer.dashboard"))

    stats = calculate_member_attendance_stats(member_id, start_date=member.get("membership_start_date"))
    attendance_history = get_member_attendance_history(member_id, limit=30)
    notes = get_trainer_notes_for_member(member_id)
    settings = get_gym_settings()

    return render_template(
        "trainer/member_detail.html",
        trainer=trainer,
        member=member,
        stats=stats,
        attendance_history=attendance_history,
        notes=notes,
        settings=settings
    )

@trainer_bp.route("/members/<member_id>/notes", methods=["POST"])
@role_required("trainer")
def add_note(member_id):
    """Add a workout or progress note for an assigned member."""
    trainer = get_trainer_by_user_id(session["user_id"])
    member = get_member_by_id(member_id)

    if not member or member["assigned_trainer_id"] != trainer["id"]:
        flash("Access Denied.", "danger")
        return redirect(url_for("trainer.dashboard"))

    note_text = request.form.get("note", "").strip()
    try:
        add_trainer_note(trainer["id"], member_id, note_text)
        flash("Training note saved.", "success")
    except Exception as e:
        flash(f"Failed to add note: {str(e)}", "danger")

    return redirect(url_for("trainer.member_detail", member_id=member_id))
