from flask import Blueprint, request, jsonify, session, flash, redirect, url_for
from auth.decorators import login_required, role_required
from services.attendance_service import (
    record_attendance_by_qr, record_attendance_manual,
    get_daily_attendance_trend, delete_attendance_record,
    reset_member_today_attendance, record_member_self_scan,
    record_trainer_self_scan, get_gym_terminal_token
)
from services.payment_service import (
    record_monthly_payment, get_monthly_revenue_trend,
    get_monthly_payment_status, get_current_billing_month
)
from services.member_service import get_all_members

api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.route("/attendance/self-scan", methods=["POST"])
@login_required
def self_scan_attendance():
    """
    Endpoint for members and trainers self-scanning the Front Desk Terminal Station QR pass.
    Distinguishes between 'check_in' (arrival) and 'check_out' (departure).
    """
    data = request.get_json(silent=True) or request.form
    terminal_token = (data.get("terminal_token") or data.get("token") or "").strip()
    action = (data.get("action") or "check_in").strip().lower()

    if not terminal_token:
        return jsonify({
            "success": False,
            "message": "Gym Station QR pass code is required.",
            "error": "Gym Station QR pass code is required."
        }), 400

    user_id = session.get("user_id")
    role = session.get("user_role") or session.get("role")

    try:
        if role == "member":
            res = record_member_self_scan(user_id, terminal_token, action=action)
        elif role == "trainer":
            res = record_trainer_self_scan(user_id, terminal_token, action=action)
        else:
            return jsonify({
                "success": False,
                "message": "Only members and trainers can self-scan attendance.",
                "error": "Only members and trainers can self-scan attendance."
            }), 403

        if not res.get("error"):
            res["error"] = res.get("message")
        status_code = 200 if res.get("success") else (409 if res.get("status") in ("already_checked_in", "already_checked_out") else 400)
        return jsonify(res), status_code
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Attendance self-scan exception: %s", e)
        return jsonify({
            "success": False,
            "message": f"Attendance processing error: {str(e)}",
            "error": str(e)
        }), 500

@api_bp.route("/attendance/quick-scan", methods=["GET"])
@login_required
def quick_scan_attendance():
    """
    Direct link endpoint when member/trainer phone camera opens the QR code directly in browser.
    Immediately processes check-in or check-out and redirects to dashboard with visual alert.
    """
    terminal_token = (request.args.get("token") or request.args.get("terminal_token") or "VANGUARD-TERMINAL-DESK-STATION").strip()
    action = (request.args.get("action") or "check_in").strip().lower()
    user_id = session.get("user_id")
    role = session.get("user_role") or session.get("role")

    if role == "member":
        res = record_member_self_scan(user_id, terminal_token, action=action)
        flash(res.get("message", "Attendance recorded!"), "success" if res.get("success") else "danger")
        return redirect(url_for("member.dashboard"))
    elif role == "trainer":
        res = record_trainer_self_scan(user_id, terminal_token, action=action)
        flash(res.get("message", "Duty attendance recorded!"), "success" if res.get("success") else "danger")
        return redirect(url_for("trainer.dashboard"))
    else:
        flash("Only members and trainers can self-scan attendance.", "danger")
        return redirect(url_for("auth.login"))

@api_bp.route("/attendance/scan", methods=["POST"])
@role_required("receptionist", "owner")
def scan_attendance():
    """Endpoint for camera QR code scanner."""
    data = request.get_json(silent=True) or request.form
    qr_token = data.get("qr_token", "").strip()
    override = bool(data.get("override", False))

    if not qr_token:
        return jsonify({
            "success": False,
            "status": "bad_request",
            "message": "QR token is required."
        }), 400

    result = record_attendance_by_qr(qr_token, session.get("user_id"), allow_override=override)
    status_code = 200 if result["success"] else (409 if result.get("status") == "already_marked" else 400)
    return jsonify(result), status_code

@api_bp.route("/attendance/manual", methods=["POST"])
@role_required("receptionist", "owner")
def manual_attendance():
    """Endpoint for manual front-desk check-in."""
    data = request.get_json(silent=True) or request.form
    member_id = data.get("member_id", "").strip()
    notes = data.get("notes", "").strip()
    override = bool(data.get("override", False))

    if not member_id:
        return jsonify({"success": False, "message": "Member ID is required."}), 400

    result = record_attendance_manual(member_id, session.get("user_id"), notes=notes, allow_override=override)
    status_code = 200 if result["success"] else (409 if result.get("status") == "already_marked" else 400)
    return jsonify(result), status_code

@api_bp.route("/attendance/<attendance_id>/delete", methods=["POST"])
@role_required("receptionist", "owner")
def api_delete_attendance(attendance_id):
    """API endpoint to delete a check-in record."""
    try:
        res = delete_attendance_record(attendance_id, requested_by_id=session.get("user_id"))
        return jsonify(res), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@api_bp.route("/attendance/reset-today", methods=["POST"])
@role_required("receptionist", "owner")
def api_reset_today_attendance():
    """API endpoint to reset a member's today attendance so they can be re-scanned."""
    data = request.get_json(silent=True) or request.form
    member_id = data.get("member_id", "").strip()
    if not member_id:
        return jsonify({"success": False, "message": "Member ID is required."}), 400
    try:
        res = reset_member_today_attendance(member_id, requested_by_id=session.get("user_id"))
        return jsonify(res), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400
    return jsonify(result), status_code

@api_bp.route("/members/search")
@role_required("receptionist", "owner")
def search_members():
    """Live search autocomplete for members."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    try:
        members, _ = get_all_members(search=q, limit=15)
        results = [{
            "id": m["id"],
            "name": m["full_name"],
            "full_name": m["full_name"],
            "code": m["member_code"],
            "member_code": m["member_code"],
            "phone": m.get("phone") or "",
            "status": m.get("membership_status") or "active",
            "fee": float(m["monthly_fee"]) if m.get("monthly_fee") else 0.0
        } for m in members]
        return jsonify(results)
    except Exception:
        return jsonify([]), 200

@api_bp.route("/charts/dashboard")
@role_required("owner")
def dashboard_charts():
    """Data endpoint for owner dashboard attendance & revenue charts."""
    attendance_trend = get_daily_attendance_trend(days=14)
    revenue_trend = get_monthly_revenue_trend(months=6)

    return jsonify({
        "attendance": attendance_trend,
        "revenue": revenue_trend
    })
