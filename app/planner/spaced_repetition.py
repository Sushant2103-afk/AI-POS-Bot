from datetime import date, timedelta
from typing import List
from sqlalchemy.orm import Session
from app.models.roadmap import Tasks, Topics, Roadmaps, RevisionHistory
from app.core.logging import logger

class SpacedRepetitionEngine:
    """
    Spaced Repetition scheduling engine.
    Calculates revision dates (1, 3, 7, 15, 30 days) upon task completion 
    and queries pending revisions for active timetables.
    """

    def __init__(self, db: Session):
        self.db = db

    def schedule_revisions(self, task_id: int, completed_date: date) -> List[RevisionHistory]:
        """
        Schedules revision sessions at 1, 3, 7, 15, and 30 days intervals
        after a task has been completed.
        """
        intervals = [1, 3, 7, 15, 30]
        revisions = []
        
        logger.info(f"Scheduling spaced repetitions for task ID {task_id} relative to date {completed_date}")
        
        for interval in intervals:
            scheduled_date = completed_date + timedelta(days=interval)
            
            # Check if this specific revision interval already exists to prevent duplicates
            existing = self.db.query(RevisionHistory).filter(
                RevisionHistory.task_id == task_id,
                RevisionHistory.revision_interval_days == interval
            ).first()
            
            if existing:
                existing.scheduled_date = scheduled_date
                existing.status = "pending"
                existing.completed_at = None
                revisions.append(existing)
            else:
                rev = RevisionHistory(
                    task_id=task_id,
                    scheduled_date=scheduled_date,
                    revision_interval_days=interval,
                    status="pending"
                )
                self.db.add(rev)
                revisions.append(rev)
                
        self.db.commit()
        return revisions

    def get_pending_revisions(self, user_id: int, target_date: date) -> List[Tasks]:
        """
        Queries all tasks with pending revision sessions scheduled for target_date.
        """
        # Join RevisionHistory -> Tasks -> Topics -> Roadmaps
        revisions = self.db.query(Tasks).join(
            RevisionHistory, RevisionHistory.task_id == Tasks.id
        ).join(
            Topics, Topics.id == Tasks.topic_id
        ).join(
            Roadmaps, Roadmaps.id == Topics.roadmap_id
        ).filter(
            Roadmaps.user_id == user_id,
            (Roadmaps.status == "active") | (Roadmaps.status == None) & (Roadmaps.is_active == True),
            RevisionHistory.scheduled_date == target_date,
            RevisionHistory.status == "pending"
        ).all()
        
        return revisions
