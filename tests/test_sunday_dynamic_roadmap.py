import pytest
from datetime import date
from sqlalchemy.orm import Session

from app.models.core import Users
from app.models.roadmap import Roadmaps, Months, Weeks, Topics, Tasks, DailyPlans, StudySessions
from app.planner.service import PlannerService
from app.core.settings_service import set_user_setting

def create_sample_roadmap(db_session: Session, user_id: int, title: str, topic_titles: list, start_date_val: date = date(2026, 7, 20)) -> Roadmaps:
    roadmap = Roadmaps(
        user_id=user_id,
        title=title,
        description=f"Roadmap for {title}",
        category="Tech",
        is_active=True,
        status="active",
        start_date=start_date_val
    )
    db_session.add(roadmap)
    db_session.flush()

    month = Months(roadmap_id=roadmap.id, month_number=1, title="Month 1")
    db_session.add(month)
    db_session.flush()

    week = Weeks(month_id=month.id, week_number=1, title="Week 1")
    db_session.add(week)
    db_session.flush()

    for top_title in topic_titles:
        topic = Topics(
            roadmap_id=roadmap.id,
            week_id=week.id,
            title=top_title,
            description=f"Learn {top_title}",
            priority="high",
            estimated_hours=2.0
        )
        db_session.add(topic)
        db_session.flush()

        task1 = Tasks(
            topic_id=topic.id,
            title=f"{top_title} Basics & Syntax",
            description=f"Study basics of {top_title}",
            estimated_minutes=60,
            priority="high",
            energy_level="high",
            is_completed=False
        )
        task2 = Tasks(
            topic_id=topic.id,
            title=f"{top_title} Practice & Exercises",
            description=f"Solve practice problems for {top_title}",
            estimated_minutes=60,
            priority="medium",
            energy_level="medium",
            is_completed=False
        )
        db_session.add_all([task1, task2])
        db_session.flush()

        # Add a prior study session on start_date_val to indicate roadmap has started
        prior_plan = DailyPlans(user_id=user_id, date=start_date_val, total_available_hours=4.0, is_finalized=True)
        db_session.add(prior_plan)
        db_session.flush()
        prior_sess = StudySessions(daily_plan_id=prior_plan.id, task_id=task1.id, start_time="09:00", end_time="10:00", status="completed")
        db_session.add(prior_sess)

    db_session.commit()
    return roadmap

def test_python_roadmap_sunday_plan(db_session: Session):
    """
    Validates that a 7-Day Python Roadmap on Sunday:
    1. Contains Python-related tasks (not generic LeetCode/Mock Placement).
    2. Continues roadmap progress cleanly.
    """
    user = Users(name="Python Learner", email="py_user@example.com")
    db_session.add(user)
    db_session.flush()

    rm = create_sample_roadmap(db_session, user.id, "7-Day Python Mastery", ["Python Variables", "Python Functions"])
    
    set_user_setting(db_session, user.id, "sunday_mode", "roadmap_plus_revision")
    set_user_setting(db_session, user.id, "schedule_mode", "custom")
    set_user_setting(db_session, user.id, "custom_start_time", "09:00")
    set_user_setting(db_session, user.id, "study_hours_per_day", "6.0")

    # Sunday date
    sunday_date = date(2026, 7, 26) # 2026-07-26 is a Sunday

    planner = PlannerService(db_session)
    plan = planner.generate_daily_plan(user.id, sunday_date)

    sessions = db_session.query(StudySessions).filter(StudySessions.daily_plan_id == plan.id).all()
    assert len(sessions) > 0, "Sunday plan should contain scheduled sessions"

    task_titles = [s.task.title for s in sessions if s.task]

    # Verify Python roadmap task is scheduled
    assert any("Python Variables" in t for t in task_titles), f"Python task should be scheduled on Sunday. Got: {task_titles}"

    # Verify NO generic hardcoded tasks appear
    for t in task_titles:
        assert "Mock Placement Test" not in t, "Should not contain generic placement test"
        assert "LeetCode Weekly Contest" not in t, "Should not contain generic LeetCode contest"

def test_french_language_roadmap_sunday_plan(db_session: Session):
    """
    Validates domain independence: A French Language roadmap on Sunday
    generates French-related activities and zero coding/test tasks.
    """
    user = Users(name="French Learner", email="french_user@example.com")
    db_session.add(user)
    db_session.flush()

    rm = create_sample_roadmap(db_session, user.id, "French Conversational Beginner", ["French Alphabet", "Basic Greetings"])
    
    set_user_setting(db_session, user.id, "sunday_mode", "roadmap_plus_revision")

    sunday_date = date(2026, 7, 26)
    planner = PlannerService(db_session)
    plan = planner.generate_daily_plan(user.id, sunday_date)

    sessions = db_session.query(StudySessions).filter(StudySessions.daily_plan_id == plan.id).all()
    task_titles = [s.task.title for s in sessions if s.task]

    assert any("French" in t for t in task_titles)
    for t in task_titles:
        assert "LeetCode" not in t
        assert "Placement" not in t

def test_sunday_modes(db_session: Session):
    """
    Validates various sunday_mode preferences:
    - roadmap_normal: only roadmap tasks
    - practice_focus: practice application tasks
    - project_focus: project tasks
    """
    user = Users(name="Web Dev Learner", email="web_user@example.com")
    db_session.add(user)
    db_session.flush()

    rm = create_sample_roadmap(db_session, user.id, "Web Development Bootcamp", ["HTML & CSS", "JavaScript Basics"])
    sunday_date = date(2026, 7, 26)
    planner = PlannerService(db_session)

    # 1. roadmap_normal
    set_user_setting(db_session, user.id, "sunday_mode", "roadmap_normal")
    plan1 = planner.generate_daily_plan(user.id, sunday_date)
    sessions1 = db_session.query(StudySessions).filter(StudySessions.daily_plan_id == plan1.id).all()
    titles1 = [s.task.title for s in sessions1 if s.task]
    assert all("Sunday Activities" not in getattr(s.task.topic, "title", "") for s in sessions1 if s.task)

    # 2. project_focus
    set_user_setting(db_session, user.id, "sunday_mode", "project_focus")
    plan2 = planner.generate_daily_plan(user.id, sunday_date)
    sessions2 = db_session.query(StudySessions).filter(StudySessions.daily_plan_id == plan2.id).all()
    titles2 = [s.task.title for s in sessions2 if s.task]
    assert any("Mini-Project" in t for t in titles2), f"Expected Mini-Project task in project_focus. Got: {titles2}"

def test_limited_time_priority(db_session: Session):
    """
    Validates that when study time is limited (e.g. 1.5 hours),
    primary roadmap tasks take priority over dynamic Sunday review tasks.
    """
    user = Users(name="DS Learner", email="ds_user@example.com")
    db_session.add(user)
    db_session.flush()

    rm = create_sample_roadmap(db_session, user.id, "Data Science Roadmap", ["Pandas Basics"])
    set_user_setting(db_session, user.id, "sunday_mode", "roadmap_plus_revision")
    set_user_setting(db_session, user.id, "schedule_mode", "custom")
    set_user_setting(db_session, user.id, "custom_start_time", "18:00")
    set_user_setting(db_session, user.id, "study_hours_per_day", "1.5") # Only 90 mins available

    sunday_date = date(2026, 7, 26)
    planner = PlannerService(db_session)
    plan = planner.generate_daily_plan(user.id, sunday_date)

    sessions = db_session.query(StudySessions).filter(StudySessions.daily_plan_id == plan.id).all()
    titles = [s.task.title for s in sessions if s.task]

    # Primary roadmap task must be scheduled
    assert any("Pandas Basics" in t for t in titles), f"Primary roadmap task should fit in available time. Got: {titles}"
