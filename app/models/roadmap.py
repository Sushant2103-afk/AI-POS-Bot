import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database.base_class import Base


class Roadmaps(Base):
    __tablename__ = "roadmaps"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    file_path = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    status = Column(String, default="active", nullable=False) # active, paused, archived
    priority = Column(Integer, default=1, nullable=False) # 1 (Highest), 2, 3, etc.
    category = Column(String, default="General", nullable=False) # e.g. Placement, AI/ML, Cybersecurity, GATE, Custom
    schedule_type = Column(String, default="daily", nullable=False) # daily, weekdays, weekends, custom_days
    schedule_days = Column(String, default="[0,1,2,3,4,5,6]", nullable=False) # JSON array of day numbers (0=Mon, 6=Sun)
    start_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=True)

    # Relationships
    user = relationship("Users", back_populates="roadmaps")
    months = relationship("Months", back_populates="roadmap", cascade="all, delete-orphan")
    topics = relationship("Topics", back_populates="roadmap", cascade="all, delete-orphan")
    settings = relationship("RoadmapSettings", back_populates="roadmap", cascade="all, delete-orphan", uselist=False)
    schedules = relationship("RoadmapSchedule", back_populates="roadmap", cascade="all, delete-orphan")
    progress_metrics = relationship("RoadmapProgress", back_populates="roadmap", cascade="all, delete-orphan")
    analytics = relationship("RoadmapAnalytics", back_populates="roadmap", cascade="all, delete-orphan")

class RoadmapSettings(Base):
    __tablename__ = "roadmap_settings"

    id = Column(Integer, primary_key=True, index=True)
    roadmap_id = Column(Integer, ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False, unique=True)
    target_hours_per_week = Column(Float, default=15.0, nullable=False)
    buffer_ratio = Column(Float, default=0.15, nullable=False)
    allow_weekend_overtime = Column(Boolean, default=True, nullable=False)

    # Relationships
    roadmap = relationship("Roadmaps", back_populates="settings")

class RoadmapSchedule(Base):
    __tablename__ = "roadmap_schedules"

    id = Column(Integer, primary_key=True, index=True)
    roadmap_id = Column(Integer, ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(Integer, nullable=False) # 0 = Monday, 6 = Sunday
    is_enabled = Column(Boolean, default=True, nullable=False)
    custom_start_time = Column(String, nullable=True) # e.g. "18:00"
    custom_end_time = Column(String, nullable=True) # e.g. "21:00"

    # Relationships
    roadmap = relationship("Roadmaps", back_populates="schedules")

class RoadmapProgress(Base):
    __tablename__ = "roadmap_progress"

    id = Column(Integer, primary_key=True, index=True)
    roadmap_id = Column(Integer, ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False)
    metric_date = Column(Date, nullable=False)
    completed_topics_count = Column(Integer, default=0, nullable=False)
    total_topics_count = Column(Integer, default=0, nullable=False)
    completed_tasks_count = Column(Integer, default=0, nullable=False)
    total_tasks_count = Column(Integer, default=0, nullable=False)
    completion_percentage = Column(Float, default=0.0, nullable=False)

    # Relationships
    roadmap = relationship("Roadmaps", back_populates="progress_metrics")

class RoadmapAnalytics(Base):
    __tablename__ = "roadmap_analytics"

    id = Column(Integer, primary_key=True, index=True)
    roadmap_id = Column(Integer, ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False)
    total_hours_spent = Column(Float, default=0.0, nullable=False)
    revision_count = Column(Integer, default=0, nullable=False)
    consistency_score = Column(Float, default=100.0, nullable=False)
    last_updated_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    roadmap = relationship("Roadmaps", back_populates="analytics")

class Months(Base):
    __tablename__ = "months"

    id = Column(Integer, primary_key=True, index=True)
    roadmap_id = Column(Integer, ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False)
    month_number = Column(Integer, nullable=False) # e.g. 1, 2, 3
    title = Column(String, nullable=False)
    target_hours = Column(Float, default=0.0, nullable=False)

    # Relationships
    roadmap = relationship("Roadmaps", back_populates="months")
    weeks = relationship("Weeks", back_populates="month", cascade="all, delete-orphan")

class Weeks(Base):
    __tablename__ = "weeks"

    id = Column(Integer, primary_key=True, index=True)
    month_id = Column(Integer, ForeignKey("months.id", ondelete="CASCADE"), nullable=False)
    week_number = Column(Integer, nullable=False) # e.g. 1, 2, 3, 4
    title = Column(String, nullable=False)
    target_hours = Column(Float, default=0.0, nullable=False)

    # Relationships
    month = relationship("Months", back_populates="weeks")
    topics = relationship("Topics", back_populates="week", cascade="all, delete-orphan")

class Topics(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    roadmap_id = Column(Integer, ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False)
    week_id = Column(Integer, ForeignKey("weeks.id", ondelete="SET NULL"), nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String, default="medium", nullable=False) # high, medium, low
    estimated_hours = Column(Float, default=0.0, nullable=False)
    energy_level = Column(String, default="medium", nullable=False) # high, medium, low
    parent_topic_id = Column(Integer, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    roadmap = relationship("Roadmaps", back_populates="topics")
    week = relationship("Weeks", back_populates="topics")
    tasks = relationship("Tasks", back_populates="topic", cascade="all, delete-orphan")
    resources = relationship("Resources", back_populates="topic", cascade="all, delete-orphan")
    
    # Self-referential relationship for nested hierarchy
    subtopics = relationship("Topics", back_populates="parent_topic", remote_side=[id])
    parent_topic = relationship("Topics", back_populates="subtopics", remote_side=[parent_topic_id])

class Tasks(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    estimated_minutes = Column(Integer, default=60, nullable=False)
    priority = Column(String, default="medium", nullable=False) # high, medium, low
    energy_level = Column(String, default="medium", nullable=False) # high, medium, low
    is_completed = Column(Boolean, default=False, nullable=False)

    # Relationships
    topic = relationship("Topics", back_populates="tasks")
    study_sessions = relationship("StudySessions", back_populates="task", cascade="all, delete-orphan")
    progress = relationship("Progress", back_populates="task", cascade="all, delete-orphan")
    revision_history = relationship("RevisionHistory", back_populates="task", cascade="all, delete-orphan")
    user_overrides = relationship("UserOverrides", back_populates="task", cascade="all, delete-orphan")
    user_notes = relationship("UserTaskNotes", back_populates="task", cascade="all, delete-orphan")
    favorites = relationship("UserFavorites", back_populates="task", cascade="all, delete-orphan")

class DailyPlans(Base):
    __tablename__ = "daily_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    total_available_hours = Column(Float, default=0.0, nullable=False)
    is_finalized = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("Users", back_populates="daily_plans")
    study_sessions = relationship("StudySessions", back_populates="daily_plan", cascade="all, delete-orphan")

class StudySessions(Base):
    __tablename__ = "study_sessions"

    id = Column(Integer, primary_key=True, index=True)
    daily_plan_id = Column(Integer, ForeignKey("daily_plans.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    start_time = Column(String, nullable=False) # e.g. "09:00"
    end_time = Column(String, nullable=False) # e.g. "10:30"
    session_type = Column(String, default="study", nullable=False) # study, revision
    status = Column(String, default="planned", nullable=False) # planned, completed, skipped, postponed

    # Relationships
    daily_plan = relationship("DailyPlans", back_populates="study_sessions")
    task = relationship("Tasks", back_populates="study_sessions")

class Progress(Base):
    __tablename__ = "progress"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=False)
    actual_minutes_spent = Column(Integer, default=0, nullable=False)
    notes = Column(Text, nullable=True)

    # Relationships
    task = relationship("Tasks", back_populates="progress")

class Resources(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    resource_type = Column(String, default="youtube", nullable=False) # youtube, documentation, article, leetcode, github, practice_sheet
    is_cached = Column(Boolean, default=True, nullable=False)

    # Relationships
    topic = relationship("Topics", back_populates="resources")

class RevisionHistory(Base):
    __tablename__ = "revision_history"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    scheduled_date = Column(Date, nullable=False)
    revision_interval_days = Column(Integer, nullable=False) # e.g. 1, 3, 7, 15, 30
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="pending", nullable=False) # pending, completed, skipped

    # Relationships
    task = relationship("Tasks", back_populates="revision_history")

class UserOverrides(Base):
    __tablename__ = "user_overrides"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    override_date = Column(Date, nullable=False)
    action = Column(String, nullable=False) # skip, postpone, reorder
    reason = Column(Text, nullable=True)

    # Relationships
    user = relationship("Users", back_populates="user_overrides")
    task = relationship("Tasks", back_populates="user_overrides")

class UserTaskNotes(Base):
    __tablename__ = "user_task_notes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("Users", back_populates="user_notes")
    task = relationship("Tasks", back_populates="user_notes")

class UserFavorites(Base):
    __tablename__ = "user_favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    user = relationship("Users", back_populates="favorites")
    task = relationship("Tasks", back_populates="favorites")

