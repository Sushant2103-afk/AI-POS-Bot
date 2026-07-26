import pytest
from datetime import date, datetime
from sqlalchemy.orm import Session

from app.models.core import Users
from app.models.roadmap import Roadmaps, Months, Weeks, Topics, Tasks, DailyPlans, StudySessions
from app.planner.service import PlannerService
from app.core.settings_service import set_user_setting

def create_test_roadmap(db_session: Session, user_id: int, title: str, start_date_val: date) -> Roadmaps:
    roadmap = Roadmaps(
        user_id=user_id,
        title=title,
        description=f"Roadmap {title}",
        category="Tech",
        is_active=True,
        status="active",
        start_date=start_date_val,
        created_at=datetime.combine(start_date_val, datetime.min.time())
    )
    db_session.add(roadmap)
    db_session.flush()

    month = Months(roadmap_id=roadmap.id, month_number=1, title="Month 1")
    db_session.add(month)
    db_session.flush()

    week = Weeks(month_id=month.id, week_number=1, title="Week 1")
    db_session.add(week)
    db_session.flush()

    # Day 1 Topic & Tasks
    topic1 = Topics(
        roadmap_id=roadmap.id,
        week_id=week.id,
        title="Day 1: Introduction & Environment Setup",
        description="Day 1 core study",
        priority="high",
        estimated_hours=2.0
    )
    db_session.add(topic1)
    db_session.flush()

    task1 = Tasks(
        topic_id=topic1.id,
        title="Day 1 Task A: Environment Setup",
        description="Install dependencies and setup IDE",
        estimated_minutes=60,
        priority="high",
        energy_level="high",
        is_completed=False
    )
    task2 = Tasks(
        topic_id=topic1.id,
        title="Day 1 Task B: First Program",
        description="Write first program",
        estimated_minutes=60,
        priority="high",
        energy_level="high",
        is_completed=False
    )
    db_session.add_all([task1, task2])

    # Day 2 Topic & Tasks
    topic2 = Topics(
        roadmap_id=roadmap.id,
        week_id=week.id,
        title="Day 2: Basic Concepts",
        description="Day 2 study",
        priority="medium",
        estimated_hours=2.0
    )
    db_session.add(topic2)
    db_session.flush()

    task3 = Tasks(
        topic_id=topic2.id,
        title="Day 2 Task: Core Syntax",
        description="Learn core syntax",
        estimated_minutes=60,
        priority="medium",
        energy_level="medium",
        is_completed=False
    )
    db_session.add(task3)
    db_session.commit()
    return roadmap

def test_scenario_1_roadmap_starts_on_sunday(db_session: Session):
    """
    Scenario 1: Roadmap starts on Sunday (2026-07-26).
    Expected: Roadmap Day 1 tasks execute normally without applying Sunday mode.
    """
    user = Users(name="Sunday Starter", email="sunday_starter@example.com")
    db_session.add(user)
    db_session.flush()

    sunday_date = date(2026, 7, 26) # 2026-07-26 is Sunday
    roadmap = create_test_roadmap(db_session, user.id, "Python Bootcamp", sunday_date)

    set_user_setting(db_session, user.id, "sunday_mode", "roadmap_plus_revision")

    planner = PlannerService(db_session)
    plan = planner.generate_daily_plan(user.id, sunday_date)

    sessions = db_session.query(StudySessions).filter(StudySessions.daily_plan_id == plan.id).all()
    task_titles = [s.task.title for s in sessions if s.task]

    # Verify Day 1 tasks are scheduled
    assert "Day 1 Task A: Environment Setup" in task_titles
    assert "Day 1 Task B: First Program" in task_titles

    # Verify NO Sunday revision activities are added on Day 1
    for t in task_titles:
        assert "Weekly Concept Revision" not in t
        assert "Weekly Progress Review" not in t

def test_scenario_2_roadmap_starts_on_wednesday(db_session: Session):
    """
    Scenario 2: Roadmap starts on Wednesday (2026-07-22).
    Expected: Wednesday becomes Roadmap Day 1.
    The following Sunday (2026-07-26) includes roadmap-aware Sunday planning.
    """
    user = Users(name="Wed Starter", email="wed_starter@example.com")
    db_session.add(user)
    db_session.flush()

    wed_date = date(2026, 7, 22) # Wednesday
    roadmap = create_test_roadmap(db_session, user.id, "Data Science Track", wed_date)

    planner = PlannerService(db_session)

    # 1. Execute Day 1 on Wednesday
    plan_wed = planner.generate_daily_plan(user.id, wed_date)
    sessions_wed = db_session.query(StudySessions).filter(StudySessions.daily_plan_id == plan_wed.id).all()
    task_titles_wed = [s.task.title for s in sessions_wed if s.task]
    assert "Day 1 Task A: Environment Setup" in task_titles_wed

    # 2. Execute on following Sunday (2026-07-26)
    sunday_date = date(2026, 7, 26)
    set_user_setting(db_session, user.id, "sunday_mode", "roadmap_plus_revision")

    plan_sun = planner.generate_daily_plan(user.id, sunday_date)
    sessions_sun = db_session.query(StudySessions).filter(StudySessions.daily_plan_id == plan_sun.id).all()
    task_titles_sun = [s.task.title for s in sessions_sun if s.task]

    # Dynamic Sunday review tasks should appear on the second Sunday
    assert any("Weekly Concept Revision" in t or "Weekly Progress Review" in t for t in task_titles_sun)

def test_scenario_3_roadmap_starts_on_monday(db_session: Session):
    """
    Scenario 3: Roadmap starts on Monday (2026-07-20).
    Expected: Monday executes Day 1.
    The first Sunday after Monday (2026-07-26) uses dynamic Sunday planning.
    """
    user = Users(name="Mon Starter", email="mon_starter@example.com")
    db_session.add(user)
    db_session.flush()

    mon_date = date(2026, 7, 20) # Monday
    roadmap = create_test_roadmap(db_session, user.id, "DevOps Track", mon_date)

    planner = PlannerService(db_session)

    # 1. Execute Day 1 on Monday
    plan_mon = planner.generate_daily_plan(user.id, mon_date)
    sessions_mon = db_session.query(StudySessions).filter(StudySessions.daily_plan_id == plan_mon.id).all()
    task_titles_mon = [s.task.title for s in sessions_mon if s.task]
    assert "Day 1 Task A: Environment Setup" in task_titles_mon

    # 2. Execute on Sunday (2026-07-26)
    sunday_date = date(2026, 7, 26)
    set_user_setting(db_session, user.id, "sunday_mode", "roadmap_plus_revision")

    plan_sun = planner.generate_daily_plan(user.id, sunday_date)
    sessions_sun = db_session.query(StudySessions).filter(StudySessions.daily_plan_id == plan_sun.id).all()
    task_titles_sun = [s.task.title for s in sessions_sun if s.task]

    # Sunday dynamic planning applies on the Sunday following Monday start
    assert any("Weekly Concept Revision" in t or "Weekly Progress Review" in t for t in task_titles_sun)
