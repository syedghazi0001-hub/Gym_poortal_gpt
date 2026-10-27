import os
import re
import logging
import sqlite3
from contextlib import contextmanager
from config import Config

logger = logging.getLogger(__name__)

# Check if psycopg2 is available
try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

_connection_pool = None
_backend = None  # 'postgres' or 'sqlite'
_sqlite_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gym_portal.db")

def get_db_backend():
    """Determine whether to use PostgreSQL or SQLite."""
    global _backend, _sqlite_path, _connection_pool
    if _backend is not None:
        return _backend

    db_url = Config.DATABASE_URL or ""
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    if db_url.startswith("sqlite"):
        _backend = "sqlite"
        path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
        if path and path != ":memory:":
            _sqlite_path = path
        logger.info(f"Using SQLite database engine at {_sqlite_path}")
        return _backend

    # PostgreSQL was requested. Never silently switch to SQLite if its driver
    # is missing; production data could otherwise go to a different database.
    if not PSYCOPG2_AVAILABLE:
        raise RuntimeError("DATABASE_URL points to PostgreSQL but psycopg2-binary is not installed.")

    # Try connecting to PostgreSQL
    try:
        db_url = Config.DATABASE_URL
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        conn_params = {"dsn": db_url}
        if "localhost" not in db_url and "127.0.0.1" not in db_url:
            if "sslmode" not in db_url:
                conn_params["sslmode"] = "require"

        _connection_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            **conn_params
        )
        _backend = "postgres"
        logger.info("Connected to PostgreSQL database pool.")
        return _backend
    except Exception as e:
        is_production = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower() == "production"
        if is_production:
            # Never silently switch a live deployment to ephemeral SQLite.
            # That can make data appear to disappear after restarts/redeploys.
            logger.exception("Configured PostgreSQL database is unavailable; refusing SQLite fallback in production.")
            raise RuntimeError("Production database connection failed. Check DATABASE_URL and database availability.") from e
        logger.warning("PostgreSQL unavailable (%s); using SQLite for local development only.", e)
        _backend = "sqlite"
        return _backend

def _convert_sql_for_sqlite(sql):
    """Convert PostgreSQL-style %s placeholders and syntax to SQLite."""
    s = re.sub(r'%s', '?', sql)
    s = re.sub(r'\bILIKE\b', 'LIKE', s, flags=re.IGNORECASE)
    # Convert ANY(array) to IN (list)
    if "= ANY(?)" in s:
        s = s.replace("= ANY(?)", "= ?")
    return s

@contextmanager
def get_db_connection():
    """Context manager yielding a database connection."""
    backend = get_db_backend()
    if backend == "postgres":
        global _connection_pool
        conn = _connection_pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            _connection_pool.putconn(conn)
    else:
        conn = sqlite3.connect(_sqlite_path, timeout=20.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

def query_all(sql, params=None):
    """Execute a query and fetch all rows as a list of dicts."""
    backend = get_db_backend()
    if backend == "postgres":
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params or ())
                return [dict(row) for row in cur.fetchall()]
    else:
        with get_db_connection() as conn:
            cur = conn.cursor()
            formatted_sql = _convert_sql_for_sqlite(sql)
            # Handle tuple/list param expansion if needed
            flat_params = []
            if params:
                for p in params:
                    if isinstance(p, (list, tuple)) and "= ?" in formatted_sql:
                        # expand first element or single string
                        flat_params.append(p[0] if len(p) > 0 else "")
                    else:
                        flat_params.append(p)
            cur.execute(formatted_sql, flat_params)
            return [dict(row) for row in cur.fetchall()]

def query_one(sql, params=None):
    """Execute a query and fetch a single row as a dict, or None."""
    backend = get_db_backend()
    if backend == "postgres":
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params or ())
                row = cur.fetchone()
                return dict(row) if row else None
    else:
        with get_db_connection() as conn:
            cur = conn.cursor()
            formatted_sql = _convert_sql_for_sqlite(sql)
            cur.execute(formatted_sql, params or ())
            row = cur.fetchone()
            return dict(row) if row else None

def execute_insert(sql, params=None, returning_id_col=None):
    """Execute INSERT and return affected rows."""
    return execute_statement(sql, params)

def execute_statement(sql, params=None):
    """Execute UPDATE, DELETE, or DDL statement and return affected rows."""
    backend = get_db_backend()
    if backend == "postgres":
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                return cur.rowcount
    else:
        with get_db_connection() as conn:
            cur = conn.cursor()
            formatted_sql = _convert_sql_for_sqlite(sql)
            cur.execute(formatted_sql, params or ())
            return cur.rowcount

def init_db(schema_file=None):
    """Execute appropriate schema file to ensure tables exist."""
    backend = get_db_backend()
    if backend == "postgres":
        if schema_file is None:
            schema_file = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_file, "r", encoding="utf-8") as f:
            sql = f.read()
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
    else:
        if schema_file is None:
            schema_file = os.path.join(os.path.dirname(__file__), "schema_sqlite.sql")
        with open(schema_file, "r", encoding="utf-8") as f:
            sql = f.read()
        with get_db_connection() as conn:
            conn.executescript(sql)
    logger.info("Database schema applied successfully.")

def check_db_health():
    """Verify database health."""
    try:
        row = query_one("SELECT 1 AS alive;")
        return bool(row and row.get("alive") == 1)
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
