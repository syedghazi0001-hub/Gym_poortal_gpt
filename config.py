import os
from datetime import timedelta
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

_IS_PRODUCTION = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower() == "production"

class Config:
    # Never use a known default secret in a deployed application.
    SECRET_KEY = os.getenv("SECRET_KEY") or (None if _IS_PRODUCTION else "dev-only-change-me-before-deployment")

    # Local development may use SQLite. Set DATABASE_URL explicitly in hosting.
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///gym_portal.db")
    
    # Supabase REST API credentials (Optional)
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", os.getenv("SUPABASE_SECRET_KEY", ""))
    
    # Gym Local Timezone
    TIMEZONE = os.getenv("GYM_TIMEZONE", "Asia/Karachi")
    
    # Session Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _IS_PRODUCTION
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    
    # Application settings
    APP_NAME = "Vanguard Gym OS"
    VERSION = "2.4.0"
    DEFAULT_CURRENCY = "PKR"
    ABSENCE_THRESHOLD_DAYS = 10

class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True

class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///test_gym_portal.db")
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False
