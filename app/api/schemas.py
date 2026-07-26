from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import date, datetime
from typing import List, Optional

# --- User Schemas ---
class UserBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    wake_up_time: str = Field("07:00", description="HH:MM format")
    sleep_time: str = Field("23:00", description="HH:MM format")
    preferred_study_hours: float = 6.0

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- Settings Schemas ---
class SettingUpdate(BaseModel):
    key: str
    value: str

class SettingResponse(BaseModel):
    id: int
    key: str
    value: str
    model_config = ConfigDict(from_attributes=True)

# --- Timetable Schemas ---
class TimetableBase(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6, description="0 = Monday, 6 = Sunday")
    activity_name: str
    start_time: str = Field(..., description="HH:MM")
    end_time: str = Field(..., description="HH:MM")

class TimetableCreate(TimetableBase):
    pass

class TimetableResponse(TimetableBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- Ingestion Schemas ---
class ImportTextRequest(BaseModel):
    title: str
    content: str
    category: Optional[str] = "General"
    priority: Optional[int] = 1
    schedule_type: Optional[str] = "daily"
    schedule_days: Optional[str] = "[0,1,2,3,4,5,6]"

class RoadmapCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: str = "General"
    priority: int = 1
    schedule_type: str = "daily"
    schedule_days: str = "[0,1,2,3,4,5,6]"

class RoadmapUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None # active, paused, archived
    priority: Optional[int] = None
    category: Optional[str] = None
    schedule_type: Optional[str] = None
    schedule_days: Optional[str] = None

class RoadmapResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    is_active: bool
    status: str = "active"
    priority: int = 1
    category: str = "General"
    schedule_type: str = "daily"
    schedule_days: str = "[0,1,2,3,4,5,6]"
    completion_percentage: Optional[float] = 0.0
    total_tasks_count: Optional[int] = 0
    completed_tasks_count: Optional[int] = 0
    model_config = ConfigDict(from_attributes=True)

# --- Planner Schemas ---
class GeneratePlanRequest(BaseModel):
    target_date: date

class TaskBrief(BaseModel):
    id: int
    title: str
    estimated_minutes: int
    priority: str
    energy_level: str
    is_completed: bool
    model_config = ConfigDict(from_attributes=True)

class StudySessionResponse(BaseModel):
    id: int
    start_time: str
    end_time: str
    session_type: str
    status: str
    task: TaskBrief
    model_config = ConfigDict(from_attributes=True)

class DailyPlanResponse(BaseModel):
    id: int
    date: date
    total_available_hours: float
    is_finalized: bool
    study_sessions: List[StudySessionResponse] = []
    model_config = ConfigDict(from_attributes=True)

class RescheduleResponse(BaseModel):
    rescheduled_count: int
    message: str
