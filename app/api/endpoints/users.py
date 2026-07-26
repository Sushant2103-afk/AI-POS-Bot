from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.api.deps import get_db, get_current_user_id
from app.api.schemas import UserCreate, UserResponse, SettingUpdate, SettingResponse, TimetableCreate, TimetableResponse
from app.models.core import Users, Settings, Timetable

router = APIRouter()

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    """Create a new user."""
    existing = db.query(Users).filter(Users.email == user_in.email).first() if user_in.email else None
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists."
        )
    
    db_user = Users(**user_in.model_dump())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.get("/me", response_model=UserResponse)
def get_user_me(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Retrieve details of the current active user."""
    user = db.query(Users).filter(Users.id == user_id).first()
    return user

@router.get("/settings", response_model=List[SettingResponse])
def get_user_settings(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """List all custom settings configurations for the user."""
    return db.query(Settings).filter(Settings.user_id == user_id).all()

@router.put("/settings", response_model=SettingResponse)
def update_user_setting(
    setting_in: SettingUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Create or update a custom user configuration setting (e.g. gym_time)."""
    setting = db.query(Settings).filter(
        Settings.user_id == user_id,
        Settings.key == setting_in.key
    ).first()
    
    if setting:
        setting.value = setting_in.value
    else:
        setting = Settings(
            user_id=user_id,
            key=setting_in.key,
            value=setting_in.value
        )
        db.add(setting)
        
    db.commit()
    db.refresh(setting)
    return setting

@router.post("/timetable", response_model=TimetableResponse, status_code=status.HTTP_201_CREATED)
def add_timetable_entry(
    entry_in: TimetableCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Add a weekly lecture or recurring activity to the college timetable."""
    entry = Timetable(
        user_id=user_id,
        **entry_in.model_dump()
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

@router.get("/timetable", response_model=List[TimetableResponse])
def get_timetable(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """List the entire weekly college class timetable."""
    return db.query(Timetable).filter(Timetable.user_id == user_id).all()
