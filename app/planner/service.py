from datetime import date, datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.core import Users, Settings
from app.models.roadmap import Roadmaps, Months, Weeks, Topics, Tasks, StudySessions, RevisionHistory, DailyPlans, UserOverrides
from app.planner.time_allocator import TimeAllocator
from app.planner.energy_scheduler import EnergyScheduler
from app.planner.spaced_repetition import SpacedRepetitionEngine
from app.core.logging import logger

class PlannerService:
    """
    Main orchestrator for SDE placement planning and daily study scheduling.
    Integrates available free slots, task priority, energy mapping, 
    spaced repetition schedules, and Sunday Mode custom items.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.time_allocator = TimeAllocator(db)
        self.spaced_repetition = SpacedRepetitionEngine(db)
        
        # Read buffer ratio from settings if available
        self.energy_scheduler = EnergyScheduler(buffer_ratio=0.15)

    def _is_roadmap_first_day(self, active_roadmap: Roadmaps, target_date: date) -> bool:
        """
        Determines whether target_date is the first day of execution for the active roadmap.
        If active_roadmap.start_date is set, returns True if start_date == target_date.
        Otherwise falls back to checking for prior study sessions before target_date.
        """
        if hasattr(active_roadmap, "start_date") and active_roadmap.start_date is not None:
            return active_roadmap.start_date == target_date

        # Fallback if start_date is not explicitly set: check for prior sessions before target_date
        prior_session = self.db.query(StudySessions).join(
            DailyPlans, DailyPlans.id == StudySessions.daily_plan_id
        ).join(
            Tasks, Tasks.id == StudySessions.task_id
        ).join(
            Topics, Topics.id == Tasks.topic_id
        ).filter(
            Topics.roadmap_id == active_roadmap.id,
            DailyPlans.user_id == active_roadmap.user_id,
            DailyPlans.date < target_date
        ).first()

        return prior_session is None

    def _generate_dynamic_sunday_tasks(self, active_roadmap: Roadmaps, sunday_mode: str = "roadmap_plus_revision") -> List[Tasks]:
        """
        Dynamically generates Sunday activities derived strictly from the active roadmap's title,
        topics, and current progress—without any hardcoded domain assumptions or generic tests.
        """
        if sunday_mode == "roadmap_normal":
            return []

        # 1. Determine active topic context from uncompleted tasks of this roadmap
        active_task = self.db.query(Tasks).join(
            Topics, Topics.id == Tasks.topic_id
        ).filter(
            Topics.roadmap_id == active_roadmap.id,
            Tasks.is_completed == False,
            Topics.title != "Sunday Activities"
        ).order_by(Tasks.id.asc()).first()

        active_topic_title = active_task.topic.title if (active_task and active_task.topic and active_task.topic.title) else active_roadmap.title

        # 2. Get or create a Sunday Activities topic under this roadmap
        first_week = self.db.query(Weeks).join(
            Months, Months.id == Weeks.month_id
        ).filter(
            Months.roadmap_id == active_roadmap.id
        ).order_by(
            Months.month_number.asc(),
            Weeks.week_number.asc()
        ).first()

        topic = self.db.query(Topics).filter(
            Topics.roadmap_id == active_roadmap.id,
            Topics.title == "Sunday Activities"
        ).first()

        if not topic:
            topic = Topics(
                roadmap_id=active_roadmap.id,
                week_id=first_week.id if first_week else None,
                title="Sunday Activities",
                description=f"Dynamic Sunday activities derived from {active_roadmap.title}",
                priority="medium",
                estimated_hours=4.0,
                energy_level="medium"
            )
            self.db.add(topic)
            self.db.flush()

        # 3. Formulate dynamic activity definitions based on sunday_mode
        candidates = []
        if sunday_mode in ("roadmap_plus_revision", "revision_focus", "custom"):
            candidates.append((
                f"Weekly Concept Revision: {active_topic_title}",
                60, "medium", "medium",
                f"Review notes, key concepts, and past exercises for {active_topic_title}."
            ))

        if sunday_mode in ("practice_focus", "custom"):
            candidates.append((
                f"Practical Application & Exercises: {active_topic_title}",
                60, "high", "medium",
                f"Complete hands-on practice problems for {active_topic_title}."
            ))

        if sunday_mode in ("project_focus", "custom"):
            candidates.append((
                f"Mini-Project & Deep Dive: {active_topic_title}",
                90, "high", "medium",
                f"Build a small practical application or project feature applying {active_topic_title}."
            ))

        if sunday_mode in ("roadmap_plus_revision", "revision_focus", "practice_focus", "project_focus", "custom"):
            candidates.append((
                f"Weekly Progress Review & Next Week Setup: {active_roadmap.title}",
                30, "low", "low",
                f"Review weekly progress on {active_roadmap.title} and set up upcoming learning goals."
            ))

        tasks = []
        for title, minutes, energy, priority, desc in candidates:
            task = self.db.query(Tasks).filter(
                Tasks.topic_id == topic.id,
                Tasks.title == title
            ).first()

            if not task:
                task = Tasks(
                    topic_id=topic.id,
                    title=title,
                    description=desc,
                    estimated_minutes=minutes,
                    priority=priority,
                    energy_level=energy,
                    is_completed=False
                )
                self.db.add(task)
                self.db.flush()
            setattr(task, "is_sunday_activity", True)
            tasks.append(task)

        self.db.commit()
        return tasks

    def generate_daily_plan(self, user_id: int, target_date: date) -> DailyPlans:
        """
        Generates a chronological daily study plan containing allocated sessions.
        """
        logger.info(f"Generating daily plan for User {user_id} on {target_date}")
        
        # 1. Clean existing daily plan to prevent duplicates during regeneration
        old_plan = self.db.query(DailyPlans).filter(
            DailyPlans.user_id == user_id,
            DailyPlans.date == target_date
        ).first()
        if old_plan:
            self.db.delete(old_plan)
            self.db.commit()

        # 2. Compute study time available (Custom vs Auto)
        from app.core.settings_service import get_user_setting
        sched_mode = get_user_setting(self.db, user_id, "schedule_mode", "auto")
        sunday_mode = get_user_setting(self.db, user_id, "sunday_mode", "roadmap_plus_revision")
        
        if sched_mode == "custom":
            start_str = get_user_setting(self.db, user_id, "custom_start_time", "18:30")
            hours_str = get_user_setting(self.db, user_id, "study_hours_per_day", "6.0")
            try:
                tot_hrs = float(hours_str)
            except Exception:
                tot_hrs = 6.0
                
            total_hours = tot_hrs
            parts = start_str.split(":")
            start_mins = int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 1110
            end_mins = min(1440, start_mins + int(tot_hrs * 60))
            
            free_slots = [(start_mins, end_mins)]

        else:
            free_slots = self.time_allocator.get_free_slots(user_id, target_date)
            total_hours = self.time_allocator.get_available_study_hours(user_id, target_date)

        db_plan = DailyPlans(
            user_id=user_id,
            date=target_date,
            total_available_hours=total_hours,
            is_finalized=False
        )
        self.db.add(db_plan)
        self.db.flush()

        # 3. Gather candidate tasks across ALL ACTIVE roadmaps
        tasks_to_schedule = []

        # A. Revision tasks take top priority
        revisions = self.spaced_repetition.get_pending_revisions(user_id, target_date)
        tasks_to_schedule.extend(revisions)

        # B. Load active roadmaps
        active_roadmaps = self.db.query(Roadmaps).filter(
            Roadmaps.user_id == user_id,
            (Roadmaps.status == "active") | (Roadmaps.status == None) & (Roadmaps.is_active == True)
        ).order_by(Roadmaps.priority.asc(), Roadmaps.id.asc()).all()

        day_num = target_date.weekday() # 0 = Monday, 6 = Sunday
        is_sunday = day_num == 6

        import json
        eligible_roadmaps = []
        for rm in active_roadmaps:
            sched_type = (rm.schedule_type or "daily").lower()
            if sched_type == "weekdays" and day_num >= 5:
                continue
            if sched_type == "weekends" and day_num < 5:
                continue
            if sched_type == "custom_days" and rm.schedule_days:
                try:
                    allowed_days = json.loads(rm.schedule_days)
                    if day_num not in allowed_days:
                        continue
                except Exception:
                    pass
            eligible_roadmaps.append(rm)

        # C. Schedule tasks from eligible active roadmaps
        for active_roadmap in eligible_roadmaps:
            is_first_day = self._is_roadmap_first_day(active_roadmap, target_date)

            roadmap_tasks = self.db.query(Tasks).join(
                Topics, Topics.id == Tasks.topic_id
            ).join(
                Roadmaps, Roadmaps.id == Topics.roadmap_id
            ).outerjoin(
                Weeks, Weeks.id == Topics.week_id
            ).outerjoin(
                Months, Months.id == Weeks.month_id
            ).filter(
                Roadmaps.id == active_roadmap.id,
                Tasks.is_completed == False,
                Topics.title != "Sunday Activities"
            ).order_by(
                Months.month_number.asc(),
                Weeks.week_number.asc(),
                Topics.id.asc(),
                Tasks.id.asc()
            ).all()

            # First Day Rule: If roadmap starts today (even on Sunday), execute Roadmap Day 1 without Sunday mode
            if is_sunday and not is_first_day:
                dynamic_sunday_tasks = self._generate_dynamic_sunday_tasks(active_roadmap, sunday_mode)
                uncompleted_sunday = [t for t in dynamic_sunday_tasks if not t.is_completed]

                if sunday_mode == "revision_focus":
                    tasks_to_schedule.extend(uncompleted_sunday)
                    tasks_to_schedule.extend(roadmap_tasks)
                else:
                    tasks_to_schedule.extend(roadmap_tasks)
                    tasks_to_schedule.extend(uncompleted_sunday)
            else:
                tasks_to_schedule.extend(roadmap_tasks)

        # Remove duplicates preserving order
        seen = set()
        unique_tasks = []
        for t in tasks_to_schedule:
            if t.id not in seen:
                seen.add(t.id)
                unique_tasks.append(t)

        # 4. Schedule Tasks
        user_settings = self.db.query(Settings).filter(
            Settings.user_id == user_id,
            Settings.key == "peak_study_hours"
        ).first()
        peak_str = user_settings.value if user_settings else None

        sessions, unscheduled = self.energy_scheduler.schedule(free_slots, unique_tasks, peak_str)

        # 5. Save StudySessions to database
        revision_task_ids = {r.id for r in revisions}
        
        for sess in sessions:
            task = sess["task"]
            sess_type = "revision" if task.id in revision_task_ids else "study"
            
            db_session = StudySessions(
                daily_plan_id=db_plan.id,
                task_id=task.id,
                start_time=sess["start_time"],
                end_time=sess["end_time"],
                session_type=sess_type,
                status="planned"
            )
            self.db.add(db_session)

        self.db.commit()
        logger.info(f"Daily plan generated successfully with {len(sessions)} study sessions.")
        return db_plan

    def reschedule_unfinished_tasks(self, user_id: int, date_limit: date) -> int:
        """
        Identifies incomplete planned study sessions from dates strictly before date_limit.
        Marks them as 'postponed' and logs a reschedule override record.
        Returns the number of rescheduled tasks.
        """
        logger.info(f"Rescheduling unfinished study sessions before {date_limit} for User {user_id}")
        
        unfinished_sessions = self.db.query(StudySessions).join(
            DailyPlans, DailyPlans.id == StudySessions.daily_plan_id
        ).join(
            Tasks, Tasks.id == StudySessions.task_id
        ).filter(
            DailyPlans.user_id == user_id,
            DailyPlans.date < date_limit,
            StudySessions.status == "planned",
            Tasks.is_completed == False
        ).all()

        count = 0
        for sess in unfinished_sessions:
            # 1. Update session status
            sess.status = "postponed"
            
            # 2. Log override reason
            override = UserOverrides(
                user_id=user_id,
                task_id=sess.task_id,
                override_date=date_limit,
                action="postpone",
                reason=f"Rescheduled unfinished session from {sess.daily_plan.date}"
            )
            self.db.add(override)
            count += 1
            
        if count > 0:
            self.db.commit()
            logger.info(f"Successfully rescheduled {count} tasks.")
            
        return count
