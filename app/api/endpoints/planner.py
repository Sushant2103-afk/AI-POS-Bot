from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import Optional
from app.api.deps import get_db, get_current_user_id
from app.api.schemas import GeneratePlanRequest, DailyPlanResponse, RescheduleResponse, StudySessionResponse
from app.planner.service import PlannerService
from app.planner.spaced_repetition import SpacedRepetitionEngine
from app.models.roadmap import StudySessions, Tasks, DailyPlans, Progress
from app.core.logging import logger

router = APIRouter()

@router.post("/generate", response_model=DailyPlanResponse, status_code=status.HTTP_201_CREATED)
def generate_daily_plan_endpoint(
    req: GeneratePlanRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Generate or regenerate a daily study plan for the given target date.
    Calculates time allocation, runs energy scheduler, and logs planned study sessions.
    """
    try:
        service = PlannerService(db)
        db_plan = service.generate_daily_plan(user_id, req.target_date)
        return db_plan
    except Exception as e:
        logger.error(f"Error generating daily plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to generate plan: {str(e)}"
        )

@router.get("/daily-plan", response_model=DailyPlanResponse)
def get_daily_plan(
    target_date: Optional[date] = None,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Retrieve the study plan for a given date. Defaults to today's date.
    """
    query_date = target_date or date.today()
    plan = db.query(DailyPlans).filter(
        DailyPlans.user_id == user_id,
        DailyPlans.date == query_date
    ).first()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No daily plan found for date {query_date}"
        )
    return plan

@router.post("/sessions/{session_id}/complete", response_model=StudySessionResponse)
def complete_study_session(
    session_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Mark a planned study session as completed.
    Triggers completion of the parent task, logs progress minutes, and schedules 
    the 1, 3, 7, 15, and 30 days spaced repetition reviews.
    """
    # Verify study session exists and belongs to user
    session = db.query(StudySessions).join(
        DailyPlans, DailyPlans.id == StudySessions.daily_plan_id
    ).filter(
        DailyPlans.user_id == user_id,
        StudySessions.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Study session with ID {session_id} not found."
        )
        
    if session.status == "completed":
        return session

    # 1. Update session status
    session.status = "completed"
    
    # 2. Mark task complete
    task = db.query(Tasks).filter(Tasks.id == session.task_id).first()
    if task:
        task.is_completed = True
        
        # 3. Log progress
        progress = Progress(
            task_id=task.id,
            completed_at=datetime.utcnow(),
            actual_minutes_spent=task.estimated_minutes,
            notes="Session marked complete via REST API."
        )
        db.add(progress)
        
        # 4. Trigger Spaced Repetition reviews
        repetition_engine = SpacedRepetitionEngine(db)
        repetition_engine.schedule_revisions(task.id, session.daily_plan.date)
        
    db.commit()
    db.refresh(session)
    return session

@router.post("/reschedule", response_model=RescheduleResponse)
def reschedule_past_due_sessions(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Scan for unfinished study sessions from dates strictly before today.
    Marks them as 'postponed' and logs user overrides to allow future scheduling.
    """
    service = PlannerService(db)
    today = date.today()
    count = service.reschedule_unfinished_tasks(user_id, today)
    
    return RescheduleResponse(
        rescheduled_count=count,
        message=f"Successfully rescheduled {count} past-due planned tasks."
    )
