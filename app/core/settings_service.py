from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.core import Settings, Users

DEFAULT_SETTINGS = {
    "schedule_mode": "auto",            # "auto" or "custom"
    "custom_start_time": "18:30",       # e.g. "18:30"
    "study_hours_per_day": "6.0",       # e.g. "6.0"
    "max_session_duration": "60",       # minutes
    "break_duration": "15",             # minutes
    "ai_provider": "groq",              # groq, gemini, openai, etc.
    "timezone": "Asia/Kolkata",
    "notif_morning": "true",
    "notif_morning_time": "07:00",
    "notif_morning_ai_tip": "true",
    "notif_morning_resources": "true",
    "notif_study_reminders": "true",
    "notif_revision_reminders": "true",
    "notif_evening_review": "true",
    "notif_weekly_report": "true",
    "sunday_mode": "roadmap_plus_revision"   # options: roadmap_plus_revision, roadmap_normal, revision_focus, practice_focus, project_focus, custom
}

def get_user_setting(db: Session, user_id: int, key: str, default: Optional[str] = None) -> str:
    """Retrieves a setting value for a given user from the database, returning default if not found."""
    setting = db.query(Settings).filter(
        Settings.user_id == user_id,
        Settings.key == key
    ).first()
    if setting and setting.value is not None:
        return setting.value
    if default is not None:
        return default
    return DEFAULT_SETTINGS.get(key, "")

def set_user_setting(db: Session, user_id: int, key: str, value: str) -> None:
    """Creates or updates a key-value setting for a given user in the database."""
    setting = db.query(Settings).filter(
        Settings.user_id == user_id,
        Settings.key == key
    ).first()
    if setting:
        setting.value = str(value)
    else:
        setting = Settings(user_id=user_id, key=key, value=str(value))
        db.add(setting)
    db.commit()

def get_all_user_settings(db: Session, user_id: int) -> Dict[str, str]:
    """Returns a merged dictionary of user settings with fallback defaults."""
    user_settings = db.query(Settings).filter(Settings.user_id == user_id).all()
    res = dict(DEFAULT_SETTINGS)
    for s in user_settings:
        res[s.key] = s.value
    return res
