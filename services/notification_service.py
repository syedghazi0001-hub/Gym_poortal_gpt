import logging
from database.connection import query_one, query_all, execute_statement
from auth.security import generate_uuid

logger = logging.getLogger(__name__)

def get_user_notifications(user_id, unread_only=False, limit=30):
    """Retrieve notifications strictly for the given user (isolation guaranteed)."""
    where_sql = "user_id = %s"
    params = [user_id]
    
    if unread_only:
        where_sql += " AND is_read = FALSE"
        
    sql = f"""
        SELECT *
        FROM notifications
        WHERE {where_sql}
        ORDER BY created_at DESC
        LIMIT %s;
    """
    params.append(limit)
    return query_all(sql, tuple(params))

def get_unread_notification_count(user_id):
    """Get count of unread notifications for navbar badge."""
    res = query_one("""
        SELECT COUNT(*) AS unread_count
        FROM notifications
        WHERE user_id = %s AND is_read = FALSE;
    """, (user_id,))
    return res["unread_count"] if res else 0

def mark_notification_as_read(notification_id, user_id):
    """Mark a notification as read, ensuring it belongs to the user."""
    execute_statement("""
        UPDATE notifications
        SET is_read = TRUE, read_at = CURRENT_TIMESTAMP
        WHERE id = %s AND user_id = %s;
    """, (notification_id, user_id))
    return True

def mark_all_notifications_as_read(user_id):
    """Mark all unread notifications for user as read."""
    execute_statement("""
        UPDATE notifications
        SET is_read = TRUE, read_at = CURRENT_TIMESTAMP
        WHERE user_id = %s AND is_read = FALSE;
    """, (user_id,))
    return True

def send_notification(user_id, title, message, category="system", link_url=None):
    """Send a notification to a specific user."""
    notif_id = generate_uuid()
    execute_statement("""
        INSERT INTO notifications (id, user_id, title, message, category, link_url)
        VALUES (%s, %s, %s, %s, %s, %s);
    """, (notif_id, user_id, title, message, category, link_url))
    return notif_id
