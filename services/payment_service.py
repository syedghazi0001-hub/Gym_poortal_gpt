import logging
from datetime import datetime, date
from database.connection import query_one, query_all, execute_statement
from auth.security import generate_uuid, generate_receipt_number
from services.auth_service import get_gym_settings

logger = logging.getLogger(__name__)

def get_current_billing_month():
    """Returns 'YYYY-MM', e.g. '2026-10'."""
    settings = get_gym_settings()
    return datetime.now().strftime("%Y-%m")

def record_monthly_payment(
    member_id, billing_month, amount, payment_method="cash",
    recorded_by_id=None, notes=None
):
    """
    Record a manual monthly membership payment.
    Enforces duplicate prevention per member per billing month.
    """
    member = query_one("""
        SELECT m.id, m.user_id, m.member_code, m.full_name, m.monthly_fee
        FROM members m
        WHERE m.id = %s;
    """, (member_id,))

    if not member:
        raise ValueError("Member not found.")

    # Validate billing month format (YYYY-MM)
    if not billing_month or len(billing_month) != 7 or "-" not in billing_month:
        raise ValueError("Invalid billing month format. Expected 'YYYY-MM' (e.g., '2026-10').")

    # Check for duplicate payment record for this member in this billing period
    existing = query_one("""
        SELECT id, receipt_number, amount, payment_date, status
        FROM payments
        WHERE member_id = %s AND billing_month = %s;
    """, (member_id, billing_month))

    if existing and existing["status"] == "paid":
        raise ValueError(
            f"Payment for {billing_month} has already been recorded for {member['full_name']} "
            f"(Receipt: {existing['receipt_number']} on {existing['payment_date']}). Duplicate payments are blocked."
        )

    settings = get_gym_settings()
    currency = settings.get("currency", "PKR")
    receipt_number = generate_receipt_number(billing_month)
    payment_id = generate_uuid()

    if existing and existing["status"] != "paid":
        # If previously reversed or refunded, re-record
        execute_statement("""
            UPDATE payments
            SET amount = %s, currency = %s, payment_date = CURRENT_DATE,
                payment_method = %s, status = 'paid', receipt_number = %s,
                recorded_by_id = %s, notes = %s
            WHERE id = %s;
        """, (float(amount), currency, payment_method, receipt_number, recorded_by_id, notes, existing["id"]))
        payment_id = existing["id"]
    else:
        execute_statement("""
            INSERT INTO payments (
                id, member_id, billing_month, amount, currency,
                payment_date, payment_method, status, receipt_number,
                recorded_by_id, notes
            ) VALUES (
                %s, %s, %s, %s, %s,
                CURRENT_DATE, %s, 'paid', %s,
                %s, %s
            );
        """, (
            payment_id, member_id, billing_month, float(amount),
            currency, payment_method, receipt_number, recorded_by_id, notes
        ))

    # Send notification to member
    notif_id = generate_uuid()
    execute_statement("""
        INSERT INTO notifications (id, user_id, title, message, category, link_url)
        VALUES (%s, %s, 'Payment Confirmed', %s, 'payment', '/member/payments');
    """, (
        notif_id, member["user_id"],
        f"Payment of {currency} {float(amount):,.2f} for billing period {billing_month} recorded successfully (Receipt: {receipt_number})."
    ))

    # Audit log
    execute_statement("""
        INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
        VALUES (%s, %s, 'RECORD_PAYMENT', 'PAYMENT', %s, %s);
    """, (generate_uuid(), recorded_by_id, payment_id, f"Recorded {currency} {amount} for {member['full_name']} ({billing_month})"))

    return get_payment_by_id(payment_id)

def get_payment_by_id(payment_id):
    """Retrieve single payment details."""
    sql = """
        SELECT p.*, m.full_name, m.member_code, m.phone,
               u_rec.username AS recorded_by_name
        FROM payments p
        JOIN members m ON m.id = p.member_id
        LEFT JOIN users u_rec ON u_rec.id = p.recorded_by_id
        WHERE p.id = %s;
    """
    return query_one(sql, (payment_id,))

def get_monthly_payment_status(billing_month=None, search=None, status_filter=None):
    """
    Get all active members and their payment status for a given month.
    status_filter: 'all', 'paid', or 'pending'
    """
    if not billing_month:
        billing_month = get_current_billing_month()

    params = [billing_month]
    where_sql = "m.membership_status = 'active'"

    if search and search.strip():
        term = f"%{search.strip()}%"
        where_sql += " AND (m.full_name ILIKE %s OR m.member_code ILIKE %s OR m.phone ILIKE %s)"
        params.extend([term, term, term])

    sql = f"""
        SELECT m.id AS member_id, m.member_code, m.full_name, m.phone, m.monthly_fee,
               p.id AS payment_id, p.billing_month, p.amount AS paid_amount,
               p.currency, p.payment_date, p.payment_method, p.receipt_number,
               COALESCE(p.status, 'pending') AS payment_status,
               u_rec.username AS recorded_by_name
        FROM members m
        LEFT JOIN payments p ON p.member_id = m.id AND p.billing_month = %s AND p.status = 'paid'
        LEFT JOIN users u_rec ON u_rec.id = p.recorded_by_id
        WHERE {where_sql}
        ORDER BY m.full_name ASC;
    """
    rows = query_all(sql, tuple(params))

    # Apply in-memory status filter if requested
    if status_filter and status_filter in ("paid", "pending"):
        rows = [r for r in rows if r["payment_status"] == status_filter]

    # Calculate summary metrics
    total_active_members = len(rows)
    paid_count = sum(1 for r in rows if r["payment_status"] == "paid")
    pending_count = sum(1 for r in rows if r["payment_status"] == "pending")
    total_collected = sum(float(r["paid_amount"] or 0) for r in rows if r["payment_status"] == "paid")
    total_pending_amount = sum(float(r["monthly_fee"] or 0) for r in rows if r["payment_status"] == "pending")

    return {
        "billing_month": billing_month,
        "members": rows,
        "metrics": {
            "total_members": total_active_members,
            "paid_count": paid_count,
            "pending_count": pending_count,
            "total_collected": total_collected,
            "total_pending_amount": total_pending_amount
        }
    }

def get_member_payment_history(member_id):
    """Retrieve full payment ledger for a specific member."""
    sql = """
        SELECT p.*, u_rec.username AS recorded_by_name
        FROM payments p
        LEFT JOIN users u_rec ON u_rec.id = p.recorded_by_id
        WHERE p.member_id = %s
        ORDER BY p.billing_month DESC;
    """
    return query_all(sql, (member_id,))

def get_recent_payments(limit=10):
    """Retrieve most recent payment receipts for dashboard."""
    sql = """
        SELECT p.*, m.full_name, m.member_code,
               u_rec.username AS recorded_by_name
        FROM payments p
        JOIN members m ON m.id = p.member_id
        LEFT JOIN users u_rec ON u_rec.id = p.recorded_by_id
        ORDER BY p.created_at DESC
        LIMIT %s;
    """
    return query_all(sql, (limit,))

def reverse_payment(payment_id, owner_id, reason="Owner reversal"):
    """
    Owner-only payment reversal (audit compliant).
    Marks status as 'reversed' rather than deleting, preserving ledger integrity.
    """
    payment = get_payment_by_id(payment_id)
    if not payment:
        raise ValueError("Payment record not found.")

    execute_statement("""
        UPDATE payments
        SET status = 'reversed', notes = COALESCE(notes, '') || ' [Reversed: ' || %s || ']'
        WHERE id = %s;
    """, (reason, payment_id))

    execute_statement("""
        INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, details)
        VALUES (%s, %s, 'REVERSE_PAYMENT', 'PAYMENT', %s, %s);
    """, (generate_uuid(), owner_id, payment_id, f"Reversed payment {payment['receipt_number']}: {reason}"))

    return True

def get_monthly_revenue_trend(months=6):
    """Retrieve total collection amounts for the past N billing months."""
    current_date = datetime.now()
    month_list = []
    
    # Generate list of past N months: 'YYYY-MM'
    year = current_date.year
    month = current_date.month
    for _ in range(months):
        month_list.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    month_list.reverse()

    sql = """
        SELECT billing_month, SUM(amount) AS total_collected
        FROM payments
        WHERE billing_month = ANY(%s) AND status = 'paid'
        GROUP BY billing_month;
    """
    rows = query_all(sql, (month_list,))
    data_map = {r["billing_month"]: float(r["total_collected"]) for r in rows}

    trend = []
    for m in month_list:
        try:
            dt = datetime.strptime(m, "%Y-%m")
            label = dt.strftime("%b %Y")
        except Exception:
            label = m
        trend.append({
            "billing_month": m,
            "label": label,
            "amount": data_map.get(m, 0.0)
        })
    return trend
