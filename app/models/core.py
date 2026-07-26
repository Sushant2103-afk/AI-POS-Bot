from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database.base_class import Base

class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    wake_up_time = Column(String, default="07:00", nullable=False)
    sleep_time = Column(String, default="23:00", nullable=False)
    preferred_study_hours = Column(Float, default=6.0, nullable=False)
    timezone = Column(String, default="UTC", nullable=False)

    # Relationships
    settings = relationship("Settings", back_populates="user", cascade="all, delete-orphan")
    timetable = relationship("Timetable", back_populates="user", cascade="all, delete-orphan")
    holidays = relationship("Holidays", back_populates="user", cascade="all, delete-orphan")
    events = relationship("Events", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notifications", back_populates="user", cascade="all, delete-orphan")
    analytics = relationship("Analytics", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("Reports", back_populates="user", cascade="all, delete-orphan")
    roadmaps = relationship("Roadmaps", back_populates="user", cascade="all, delete-orphan")
    daily_plans = relationship("DailyPlans", back_populates="user", cascade="all, delete-orphan")
    user_overrides = relationship("UserOverrides", back_populates="user", cascade="all, delete-orphan")
    user_notes = relationship("UserTaskNotes", back_populates="user", cascade="all, delete-orphan")
    favorites = relationship("UserFavorites", back_populates="user", cascade="all, delete-orphan")

class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key = Column(String, index=True, nullable=False)
    value = Column(Text, nullable=False)

    # Relationships
    user = relationship("Users", back_populates="settings")

class Timetable(Base):
    __tablename__ = "timetable"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(Integer, nullable=False) # 0 = Monday, 6 = Sunday
    activity_name = Column(String, nullable=False)
    start_time = Column(String, nullable=False) # e.g. "09:00"
    end_time = Column(String, nullable=False) # e.g. "10:30"

    # Relationships
    user = relationship("Users", back_populates="timetable")

class Holidays(Base):
    __tablename__ = "holidays"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    description = Column(String, nullable=True)

    # Relationships
    user = relationship("Users", back_populates="holidays")

class Events(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    is_blocked_time = Column(Boolean, default=True, nullable=False)

    # Relationships
    user = relationship("Users", back_populates="events")

class Notifications(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    provider = Column(String, default="telegram", nullable=False)
    status = Column(String, default="pending", nullable=False) # pending, sent, failed

    # Relationships
    user = relationship("Users", back_populates="notifications")

class Analytics(Base):
    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    metric_date = Column(Date, nullable=False)
    study_hours_completed = Column(Float, default=0.0, nullable=False)
    tasks_completed_count = Column(Integer, default=0, nullable=False)
    tasks_total_count = Column(Integer, default=0, nullable=False)
    streak_count = Column(Integer, default=0, nullable=False)
    readiness_score = Column(Float, default=0.0, nullable=False)

    # Relationships
    user = relationship("Users", back_populates="analytics")

class Reports(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    report_type = Column(String, nullable=False) # e.g. weekly, monthly
    generated_at = Column(DateTime(timezone=True), nullable=False)
    content = Column(Text, nullable=False) # Markdown structure
    file_path = Column(String, nullable=True)

    # Relationships
    user = relationship("Users", back_populates="reports")
