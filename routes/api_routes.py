from flask import Blueprint, request, jsonify, session
from auth.decorators import login_required, role_required
from services.attendance_service import (
    record_attendance_by_qr, record_attendance_manual,
    get_daily_attendance_trend, delete_attendance_record,
    reset_member_today_attendance
)
from services.payment_service import (
    record_monthly_payment, get_monthly_revenue_trend,
    get_monthly_payment_status, get_current_billing_month
)
from services.member_service import get_all_members

api_bp = Blueprint("api", __name__, url_prefix="/api")

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
