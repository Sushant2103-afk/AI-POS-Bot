import os
from app.core.config import load_settings, Settings

def test_load_settings_defaults():
    """
    Test that default settings are loaded correctly and configurations parse properly.
    """
    settings = load_settings()
    assert isinstance(settings, Settings)
    assert settings.user_profile.name == "Placement Candidate"
    assert settings.scheduler.buffer_ratio == 0.15
    assert len(settings.revision.strategy) == 5
    assert settings.ai.provider == "groq"
    assert settings.ui.theme == "dark"

def test_env_overrides(monkeypatch):
    """
    Test that environment variables override configurations loaded from files.
    """
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("GROQ_API_KEY", "env-secret-api-key")
    
    settings = load_settings()
    assert settings.ENV == "production"
    assert settings.GROQ_API_KEY == "env-secret-api-key"
