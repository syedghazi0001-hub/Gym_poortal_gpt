import os
import logging
from flask import Flask, render_template, session, redirect, url_for, request, abort
from config import Config
from database.connection import init_db, check_db_health
from services.auth_service import get_gym_settings, has_owner_account
from services.notification_service import get_unread_notification_count
from auth.decorators import get_current_user
from auth.security import generate_csrf_token, validate_csrf_token

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
)
logger = logging.getLogger(__name__)

def create_app(config_class=Config):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    app = Flask(
        __name__,
        static_folder=os.path.join(base_dir, "static"),
        static_url_path="/static",
        template_folder=os.path.join(base_dir, "templates")
    )
    app.config.from_object(config_class)

    # Fail closed: do not start a deployed app with a missing/known secret.
    is_production = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower() == "production"
    secret_key = app.config.get("SECRET_KEY")
    if is_production and (not secret_key or len(secret_key) < 32 or secret_key == "dev-only-change-me-before-deployment" or secret_key.startswith("GENERATE_")):
        raise RuntimeError("Set SECRET_KEY to a unique random value of at least 32 characters in production environment variables.")

    # Render's local filesystem is not a persistent database. Refuse to launch
    # there with the default SQLite database, which could lose data on redeploy.
    if os.getenv("RENDER", "").lower() == "true":
        database_url = os.getenv("DATABASE_URL", "").strip().lower()
        if not database_url.startswith(("postgres://", "postgresql://")):
            raise RuntimeError("On Render, configure DATABASE_URL with a persistent PostgreSQL database before deployment.")

    # Database initialization errors must stop startup; silently continuing can
    # make the app appear live while reads/writes are failing.
    init_db()

    @app.before_request
    def check_session_inactivity():
        if request.endpoint and (
            request.endpoint.startswith("static") or 
            request.endpoint in ("auth.login", "auth.logout", "auth.setup")
        ):
            return

        if "user_id" in session:
            import time
            now = time.time()
            last_active = session.get("last_active")
            # 20 minutes = 1200 seconds of sliding inactivity
            if last_active and (now - last_active > 1200):
                session.clear()
                if request.is_json or request.path.startswith("/api/"):
                    from flask import jsonify
                    return jsonify({
                        "success": False,
                        "error": "Session expired due to 20 minutes of inactivity. Please sign in again."
                    }), 401
                return redirect(url_for("auth.login", timeout=1))
            session["last_active"] = now

    @app.before_request
    def protect_state_changing_requests():
        if app.testing:
            return
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            token = (
                request.headers.get("X-CSRF-Token") or
                request.headers.get("X-CSRFToken") or
                request.headers.get("X-Csrf-Token") or
                request.form.get("csrf_token")
            )
            if not token and request.is_json:
                payload = request.get_json(silent=True) or {}
                token = payload.get("csrf_token") or payload.get("csrf")

            # Validate token; for authenticated users on internal API calls, ensure session exists
            if not validate_csrf_token(token):
                if session.get("user_id") and request.path.startswith("/api/attendance/"):
                    pass  # Permitted for logged-in authenticated user making attendance call
                else:
                    abort(400, description="Invalid or missing CSRF token. Refresh the page and try again.")

    # Register Blueprints
    from routes.auth_routes import auth_bp
    from routes.owner_routes import owner_bp
    from routes.receptionist_routes import receptionist_bp
    from routes.trainer_routes import trainer_bp
    from routes.member_routes import member_bp
    from routes.api_routes import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(owner_bp)
    app.register_blueprint(receptionist_bp)
    app.register_blueprint(trainer_bp)
    app.register_blueprint(member_bp)
    app.register_blueprint(api_bp)

    # Root redirect handler
    @app.route("/")
    def index():
        if not has_owner_account():
            return redirect(url_for("auth.setup"))
            
        if "user_id" in session:
            role = session.get("user_role")
            if role == "owner":
                return redirect(url_for("owner.dashboard"))
            elif role == "receptionist":
                return redirect(url_for("receptionist.desk"))
            elif role == "trainer":
                return redirect(url_for("trainer.dashboard"))
            elif role == "member":
                return redirect(url_for("member.dashboard"))
        return redirect(url_for("auth.login"))

    # Context Processors for Templates
    @app.context_processor
    def inject_globals():
        user = get_current_user()
        try:
            settings = get_gym_settings()
        except Exception:
            settings = {
                "gym_name": "Vanguard Fitness Club",
                "currency": "PKR",
                "accent_color": "#10B981"
            }
        
        unread_notifs = 0
        if user:
            try:
                unread_notifs = get_unread_notification_count(user["id"])
            except Exception:
                unread_notifs = 0

        return {
            "current_user": user,
            "gym_settings": settings,
            "unread_count": unread_notifs,
            "csrf_token": generate_csrf_token()
        }

    # Custom Jinja filters
    @app.template_filter("currency")
    def currency_filter(val, symbol="PKR"):
        try:
            return f"{symbol} {float(val):,.2f}"
        except (ValueError, TypeError):
            return f"{symbol} 0.00"

    @app.template_filter("date_format")
    def date_format(val, fmt="%b %d, %Y"):
        if not val:
            return "N/A"
        import zoneinfo
        from datetime import datetime, date

        gym_tz_name = "Asia/Karachi"
        try:
            settings = get_gym_settings()
            gym_tz_name = settings.get("timezone", "Asia/Karachi")
        except Exception:
            pass

        try:
            gym_tz = zoneinfo.ZoneInfo(gym_tz_name)
        except Exception:
            gym_tz = zoneinfo.ZoneInfo("Asia/Karachi")

        dt = None
        if isinstance(val, datetime):
            dt = val
        elif isinstance(val, str):
            clean_str = val.strip()
            try:
                if clean_str.endswith("Z"):
                    clean_str = clean_str[:-1] + "+00:00"
                dt = datetime.fromisoformat(clean_str)
            except Exception:
                try:
                    d = date.fromisoformat(clean_str[:10])
                    return d.strftime(fmt)
                except Exception:
                    return str(val)

        if dt:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
            local_dt = dt.astimezone(gym_tz)
            return local_dt.strftime(fmt)

        if hasattr(val, "strftime"):
            return val.strftime(fmt)
        return str(val)

    # Custom Error Handlers
    @app.errorhandler(403)
    def forbidden_error(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found_error(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(e):
        return render_template("errors/500.html"), 500

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
