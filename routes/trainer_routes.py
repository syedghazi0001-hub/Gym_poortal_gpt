from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from auth.decorators import role_required, get_current_user
from services.staff_service import (
    get_trainer_by_user_id, get_trainer_assigned_members,
    add_trainer_note, get_trainer_notes_for_member
)
from services.member_service import get_member_by_id
from services.attendance_service import (
    get_member_attendance_history, calculate_member_attendance_stats
)
from services.auth_service import get_gym_settings

trainer_bp = Blueprint("trainer", __name__, url_prefix="/trainer")

@trainer_bp.route("/dashboard")
@role_required("trainer")
def dashboard():
    """Trainer overview: Assigned members list and attendance status."""
    trainer = get_trainer_by_user_id(session["user_id"])
    if not trainer:
        flash("Trainer profile not found.", "danger")
        return redirect(url_for("auth.login"))

    assigned_members = get_trainer_assigned_members(trainer["id"])
    settings = get_gym_settings()

    return render_template(
        "trainer/dashboard.html",
        trainer=trainer,
        assigned_members=assigned_members,
        settings=settings
    )

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
