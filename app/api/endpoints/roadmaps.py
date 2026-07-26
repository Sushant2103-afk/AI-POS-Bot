from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.api.deps import get_db, get_current_user_id
from app.api.schemas import RoadmapCreate, RoadmapUpdate, RoadmapResponse
from app.models.roadmap import Roadmaps, Topics, Tasks
from app.imports.engine import ImportEngine
from app.core.logging import logger

router = APIRouter()

def compute_roadmap_metrics(db: Session, roadmap: Roadmaps) -> Dict[str, Any]:
    all_tasks = db.query(Tasks).join(Topics, Tasks.topic_id == Topics.id).filter(Topics.roadmap_id == roadmap.id).all()
    total_count = len(all_tasks)
    completed_count = len([t for t in all_tasks if t.is_completed])
    percentage = (completed_count / total_count * 100.0) if total_count > 0 else 0.0
    return {
        "id": roadmap.id,
        "title": roadmap.title,
        "description": roadmap.description,
        "is_active": roadmap.status == "active" or (roadmap.status is None and roadmap.is_active),
        "status": roadmap.status or "active",
        "priority": roadmap.priority or 1,
        "category": roadmap.category or "General",
        "schedule_type": roadmap.schedule_type or "daily",
        "schedule_days": roadmap.schedule_days or "[0,1,2,3,4,5,6]",
        "total_tasks_count": total_count,
        "completed_tasks_count": completed_count,
        "completion_percentage": round(percentage, 1)
    }

@router.get("", response_model=List[RoadmapResponse])
def list_roadmaps(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """List all roadmaps owned by current user with stats."""
    roadmaps = db.query(Roadmaps).filter(Roadmaps.user_id == user_id).order_by(Roadmaps.priority.asc(), Roadmaps.id.asc()).all()
    res = []
    for rm in roadmaps:
        res.append(compute_roadmap_metrics(db, rm))
    return res

@router.post("", response_model=RoadmapResponse, status_code=status.HTTP_201_CREATED)
def create_manual_roadmap(
    rm_in: RoadmapCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Create a new manual roadmap shell."""
    roadmap = Roadmaps(
        user_id=user_id,
        title=rm_in.title,
        description=rm_in.description,
        is_active=True,
        status="active",
        priority=rm_in.priority,
        category=rm_in.category,
        schedule_type=rm_in.schedule_type,
        schedule_days=rm_in.schedule_days
    )
    db.add(roadmap)
    db.commit()
    db.refresh(roadmap)
    return compute_roadmap_metrics(db, roadmap)

@router.get("/{roadmap_id}", response_model=RoadmapResponse)
def get_roadmap_detail(
    roadmap_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Retrieve detailed metadata and progress metrics for a single roadmap."""
    roadmap = db.query(Roadmaps).filter(Roadmaps.id == roadmap_id, Roadmaps.user_id == user_id).first()
    if not roadmap:
        raise HTTPException(status_code=404, detail=f"Roadmap ID {roadmap_id} not found.")
    return compute_roadmap_metrics(db, roadmap)

@router.patch("/{roadmap_id}", response_model=RoadmapResponse)
def update_roadmap(
    roadmap_id: int,
    rm_update: RoadmapUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Update roadmap status, priority, title, category, or schedule configuration."""
    roadmap = db.query(Roadmaps).filter(Roadmaps.id == roadmap_id, Roadmaps.user_id == user_id).first()
    if not roadmap:
        raise HTTPException(status_code=404, detail=f"Roadmap ID {roadmap_id} not found.")

    if rm_update.title is not None:
        roadmap.title = rm_update.title
    if rm_update.description is not None:
        roadmap.description = rm_update.description
    if rm_update.status is not None:
        roadmap.status = rm_update.status
        roadmap.is_active = (rm_update.status == "active")
    if rm_update.priority is not None:
        roadmap.priority = rm_update.priority
    if rm_update.category is not None:
        roadmap.category = rm_update.category
    if rm_update.schedule_type is not None:
        roadmap.schedule_type = rm_update.schedule_type
    if rm_update.schedule_days is not None:
        roadmap.schedule_days = rm_update.schedule_days

    db.commit()
    db.refresh(roadmap)
    return compute_roadmap_metrics(db, roadmap)

@router.post("/{roadmap_id}/duplicate", response_model=RoadmapResponse, status_code=status.HTTP_201_CREATED)
def duplicate_roadmap_endpoint(
    roadmap_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Duplicate an existing roadmap into a independent new active copy."""
    try:
        engine = ImportEngine(db)
        new_roadmap = engine.duplicate_roadmap(user_id, roadmap_id)
        return compute_roadmap_metrics(db, new_roadmap)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))

@router.post("/{roadmap_id}/pause", response_model=RoadmapResponse)
def pause_roadmap(
    roadmap_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Pause roadmap execution (excludes tasks from daily planner)."""
    return update_roadmap(roadmap_id, RoadmapUpdate(status="paused"), user_id, db)

@router.post("/{roadmap_id}/resume", response_model=RoadmapResponse)
def resume_roadmap(
    roadmap_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Resume a paused roadmap (includes tasks in daily planner)."""
    return update_roadmap(roadmap_id, RoadmapUpdate(status="active"), user_id, db)

@router.post("/{roadmap_id}/archive", response_model=RoadmapResponse)
def archive_roadmap(
    roadmap_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Archive a roadmap."""
    return update_roadmap(roadmap_id, RoadmapUpdate(status="archived"), user_id, db)

@router.delete("/{roadmap_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_roadmap(
    roadmap_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Permanently delete a roadmap and all associated topics/tasks."""
    roadmap = db.query(Roadmaps).filter(Roadmaps.id == roadmap_id, Roadmaps.user_id == user_id).first()
    if not roadmap:
        raise HTTPException(status_code=404, detail=f"Roadmap ID {roadmap_id} not found.")
    db.delete(roadmap)
    db.commit()
    return None

@router.get("/analytics/summary")
def get_roadmap_analytics_summary(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Per-roadmap metrics and overall aggregate completion analytics."""
    roadmaps = db.query(Roadmaps).filter(Roadmaps.user_id == user_id).all()
    metrics = [compute_roadmap_metrics(db, rm) for rm in roadmaps]
    
    total_tasks = sum(m["total_tasks_count"] for m in metrics)
    total_completed = sum(m["completed_tasks_count"] for m in metrics)
    overall_percentage = (total_completed / total_tasks * 100.0) if total_tasks > 0 else 0.0

    return {
        "overall_tasks_total": total_tasks,
        "overall_tasks_completed": total_completed,
        "overall_completion_percentage": round(overall_percentage, 1),
        "active_roadmaps_count": len([m for m in metrics if m["status"] == "active"]),
        "paused_roadmaps_count": len([m for m in metrics if m["status"] == "paused"]),
        "archived_roadmaps_count": len([m for m in metrics if m["status"] == "archived"]),
        "roadmaps": metrics
    }
