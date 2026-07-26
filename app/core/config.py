import os
import yaml
from typing import Dict, Any, List
from pydantic import Field, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

class UserProfileConfig(BaseModel):
    name: str = "Placement Candidate"
    wake_up_time: str = "07:00"
    sleep_time: str = "23:00"
    preferred_study_hours: float = 6.0
    break_duration_minutes: int = 15
    lunch_time: str = "13:00"
    dinner_time: str = "20:00"
    exercise_time: str = "18:00"

class SundayModeConfig(BaseModel):
    prioritize_mock_test: bool = True
    prioritize_revision: bool = True
    prioritize_mock_interview: bool = True
    prioritize_leetcode_contest: bool = True
    prioritize_resume_update: bool = True
    prioritize_linkedin_update: bool = True
    prioritize_project_work: bool = True

class SchedulerConfig(BaseModel):
    buffer_ratio: float = 0.15
    sunday_mode: SundayModeConfig = Field(default_factory=SundayModeConfig)

class RevisionConfig(BaseModel):
    strategy: List[int] = [1, 3, 7, 15, 30]

class NotificationsConfig(BaseModel):
    provider: str = "telegram"
    morning_plan_time: str = "08:00"
    evening_review_time: str = "22:00"
    study_session_reminder_minutes: int = 10

class AIConfig(BaseModel):
    provider: str = "groq"
    model: str = "llama3-8b-8192"
    temperature: float = 0.2

class UIConfig(BaseModel):
    theme: str = "dark"
    dashboard_preferences: Dict[str, bool] = Field(
        default_factory=lambda: {
            "show_readiness_score": True,
            "show_countdown": True,
            "show_daily_streak": True,
        }
    )

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    ENV: str = "development"
    SECRET_KEY: str = "supersecretkeyplaceholder"
    DATABASE_URL: str = "sqlite:///./ai_pos.db"

    DEFAULT_AI_PROVIDER: str = "groq"

    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    CLAUDE_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # configurations loaded from configs/settings.yaml
    user_profile: UserProfileConfig = Field(default_factory=UserProfileConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    revision: RevisionConfig = Field(default_factory=RevisionConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    ui: UIConfig = Field(default_factory=UIConfig)

def load_settings(yaml_path: str = None) -> Settings:
    # Resolve default path relative to workspace root if not specified
    if yaml_path is None:
        # Check standard location relative to project root
        yaml_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "configs", "settings.yaml")

    settings = Settings()

    if os.path.exists(yaml_path):
        with open(yaml_path, "r") as f:
            try:
                yaml_data = yaml.safe_load(f)
                if yaml_data:
                    if "user_profile" in yaml_data:
                        settings.user_profile = UserProfileConfig(**yaml_data["user_profile"])
                    if "scheduler" in yaml_data:
                        sched_data = yaml_data["scheduler"]
                        sun_data = sched_data.get("sunday_mode", {})
                        settings.scheduler = SchedulerConfig(
                            buffer_ratio=sched_data.get("buffer_ratio", 0.15),
                            sunday_mode=SundayModeConfig(**sun_data)
                        )
                    if "revision" in yaml_data:
                        settings.revision = RevisionConfig(**yaml_data["revision"])
                    if "notifications" in yaml_data:
                        settings.notifications = NotificationsConfig(**yaml_data["notifications"])
                    if "ai" in yaml_data:
                        settings.ai = AIConfig(**yaml_data["ai"])
                    if "ui" in yaml_data:
                        settings.ui = UIConfig(**yaml_data["ui"])
            except Exception as e:
                # Fallback to defaults if parsing fails
                pass

    return settings

settings = load_settings()
