import time
import pytest
from app import create_app
from config import TestingConfig
from database.connection import is_db_initialized, init_db, query_one
from services.auth_service import (
    get_gym_settings, update_gym_settings, invalidate_gym_settings_cache
)
from services.absence_service import run_ten_day_absence_check

def test_db_initialized_check(app):
    """Verify that is_db_initialized returns True for an initialized DB and init_db skips DDL safely."""
    with app.app_context():
        assert is_db_initialized() is True
        # Calling init_db without force should be a safe no-op
        init_db(force=False)
        assert is_db_initialized() is True

def test_gym_settings_caching(app):
    """Verify request-scoped and process caching for get_gym_settings."""
    with app.app_context():
        # Force refresh first
        settings_1 = get_gym_settings(force_refresh=True)
        assert settings_1 is not None
        assert "gym_name" in settings_1

        # Second call should return cached object
        settings_2 = get_gym_settings()
        assert settings_2["gym_name"] == settings_1["gym_name"]

        # Cache invalidation check
        invalidate_gym_settings_cache()
        settings_3 = get_gym_settings()
        assert settings_3["gym_name"] == settings_1["gym_name"]

def test_gym_settings_update_invalidates_cache(app):
    """Verify that updating gym settings invalidates and updates the cache immediately."""
    with app.app_context():
        orig_settings = get_gym_settings()
        orig_name = orig_settings["gym_name"]
        
        test_name = "Vanguard High Performance Hub"
        updated = update_gym_settings(
            gym_name=test_name,
            gym_tagline=orig_settings.get("gym_tagline", ""),
            currency=orig_settings.get("currency", "PKR"),
            timezone=orig_settings.get("timezone", "Asia/Karachi"),
            accent_color=orig_settings.get("accent_color", "#10B981"),
            contact_phone=orig_settings.get("contact_phone", ""),
            contact_email=orig_settings.get("contact_email", ""),
            address=orig_settings.get("address", ""),
            absence_threshold_days=orig_settings.get("absence_threshold_days", 10)
        )
        assert updated["gym_name"] == test_name
        cached = get_gym_settings()
        assert cached["gym_name"] == test_name

        # Restore original
        update_gym_settings(
            gym_name=orig_name,
            gym_tagline=orig_settings.get("gym_tagline", ""),
            currency=orig_settings.get("currency", "PKR"),
            timezone=orig_settings.get("timezone", "Asia/Karachi"),
            accent_color=orig_settings.get("accent_color", "#10B981"),
            contact_phone=orig_settings.get("contact_phone", ""),
            contact_email=orig_settings.get("contact_email", ""),
            address=orig_settings.get("address", ""),
            absence_threshold_days=orig_settings.get("absence_threshold_days", 10)
        )

def test_absence_check_batch_execution(app):
    """Verify absence check engine runs in batch mode without error."""
    with app.app_context():
        res = run_ten_day_absence_check(force=True)
        assert res["status"] == "completed"
        assert "checked_members" in res
