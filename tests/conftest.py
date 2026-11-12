import os
import pytest

# Keep tests isolated from any local or production database.
os.environ.setdefault("DATABASE_URL", "sqlite:///test_gym_portal.db")
from app import create_app
from config import TestingConfig
from database.connection import execute_statement, query_one
from services.auth_service import setup_initial_owner

@pytest.fixture(scope="session")
def app():
    app = create_app(TestingConfig)
    return app

@pytest.fixture(autouse=True)
def ensure_clean_environment(app):
    """Ensure database has basic gym settings and an owner account before tests run."""
    with app.app_context():
        # Check if owner exists
        owner = query_one("SELECT * FROM users WHERE role = 'owner' LIMIT 1;")
        if not owner:
            try:
                setup_initial_owner(
                    gym_name="Vanguard Fitness Club",
                    currency="PKR",
                    timezone="Asia/Karachi",
                    username="admin",
                    password="AdminPassword123!",
                    full_name="Gym Owner Malik",
                    phone="+923001234567",
                    email="owner@vanguardfitness.com"
                )
            except Exception:
                pass
