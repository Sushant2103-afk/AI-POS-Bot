from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from datetime import date
from app.api.deps import get_db, get_current_user_id
from app.planner.service import PlannerService
from app.exports.engine import ExportEngine

router = APIRouter()

@router.get("/plan")
def export_daily_plan(
    target_date: date = Query(default_factory=date.today),
    format: str = Query("markdown", pattern="^(markdown|csv|json)$"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    Export the user's daily study plan for a given target date in markdown, csv, or json format.
    """
    planner_service = PlannerService(db)
    daily_plan = planner_service.generate_daily_plan(user_id=user_id, target_date=target_date)
    
    # Format plan dictionary
    plan_dict = {
        "id": daily_plan.id,
        "date": daily_plan.date,
        "total_available_hours": daily_plan.total_available_hours,
        "is_finalized": daily_plan.is_finalized,
        "study_sessions": [
            {
                "id": s.id,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "session_type": s.session_type,
                "status": s.status,
                "task": {
                    "id": s.task.id,
                    "title": s.task.title,
                    "estimated_minutes": s.task.estimated_minutes,
                    "priority": s.task.priority,
                    "energy_level": s.task.energy_level,
                    "is_completed": s.task.is_completed
                } if s.task else {}
            }
            for s in daily_plan.study_sessions
        ]
    }

    if format == "csv":
        content = ExportEngine.export_plan_csv(plan_dict)
        return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=plan_{target_date}.csv"})
    elif format == "json":
        content = ExportEngine.export_plan_json(plan_dict)
        return Response(content=content, media_type="application/json")
    else:
        content = ExportEngine.export_plan_markdown(plan_dict)
        return Response(content=content, media_type="text/markdown", headers={"Content-Disposition": f"attachment; filename=plan_{target_date}.md"})
