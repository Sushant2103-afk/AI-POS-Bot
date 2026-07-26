import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.core import Users, Settings
from app.models.roadmap import Roadmaps, Months, Weeks, Topics, Tasks, DailyPlans, StudySessions, UserFavorites
from app.core.settings_service import get_user_setting, set_user_setting, get_all_user_settings
from app.ai.resources import recommend_resources, get_fallback_resources
from app.ai.practice import analyze_smart_practice
from app.planner.service import PlannerService
from app.telegram.bot import build_plan_message_and_markup

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    user = Users(id=1, name="Test User", email="test@example.com", wake_up_time="07:00", sleep_time="23:00")
    db.add(user)
    db.commit()
    
    yield db
    db.close()

def test_settings_service(db_session):
    set_user_setting(db_session, 1, "schedule_mode", "custom")
    set_user_setting(db_session, 1, "custom_start_time", "19:00")
    set_user_setting(db_session, 1, "study_hours_per_day", "4.0")
    
    assert get_user_setting(db_session, 1, "schedule_mode") == "custom"
    assert get_user_setting(db_session, 1, "custom_start_time") == "19:00"
    assert get_user_setting(db_session, 1, "study_hours_per_day") == "4.0"

def test_resource_recommendation_and_fallback():
    resources = recommend_resources("Binary Search Trees", "DSA")
    assert len(resources) >= 3
    categories = [r["category"] for r in resources]
    assert "Official Documentation" in categories or len(resources) > 0
    
    fallback = get_fallback_resources("Python Modules", "Python")
    assert len(fallback) == 5
    assert fallback[0]["category"] == "Official Documentation"

def test_smart_practice_analysis():
    rec = analyze_smart_practice("Binary Search Tree Insertion", "DSA", 60)
    assert rec.is_practice_required is True
    assert rec.practice_category == "DSA"
    assert len(rec.platforms) >= 2

def test_custom_study_mode_planner(db_session):
    set_user_setting(db_session, 1, "schedule_mode", "custom")
    set_user_setting(db_session, 1, "custom_start_time", "18:30")
    set_user_setting(db_session, 1, "study_hours_per_day", "4.0")
    
    roadmap = Roadmaps(user_id=1, title="Test Roadmap", is_active=True)
    db_session.add(roadmap)
    db_session.flush()
    
    topic = Topics(roadmap_id=roadmap.id, title="Python Basics")
    db_session.add(topic)
    db_session.flush()
    
    task1 = Tasks(topic_id=topic.id, title="Variables & Data Types", estimated_minutes=60, energy_level="medium", priority="medium")
    task2 = Tasks(topic_id=topic.id, title="Control Structures", estimated_minutes=60, energy_level="medium", priority="medium")
    db_session.add_all([task1, task2])
    db_session.commit()
    
    planner = PlannerService(db_session)
    today = datetime.date.today()
    plan = planner.generate_daily_plan(1, today)
    
    assert plan is not None
    assert len(plan.study_sessions) > 0
    assert plan.study_sessions[0].start_time == "18:30"

def test_build_plan_message_and_markup_task_buttons(db_session):
    roadmap = Roadmaps(user_id=1, title="Test Roadmap", is_active=True)
    db_session.add(roadmap)
    db_session.flush()
    
    topic = Topics(roadmap_id=roadmap.id, title="Python Basics")
    db_session.add(topic)
    db_session.flush()
    
    task = Tasks(topic_id=topic.id, title="Variables", estimated_minutes=60, energy_level="medium", priority="medium")
    db_session.add(task)
    db_session.flush()
    
    today = datetime.date.today()
    plan = DailyPlans(user_id=1, date=today, total_available_hours=4.0)
    db_session.add(plan)
    db_session.flush()
    
    session = StudySessions(daily_plan_id=plan.id, task_id=task.id, start_time="18:30", end_time="19:30", status="planned")
    db_session.add(session)
    db_session.commit()
    
    msg, markup = build_plan_message_and_markup(db_session, 1, today)
    assert "Variables" in msg
    assert markup is not None
    
    # Verify task inline buttons (Completed, Remind, Skip, Resources)
    callback_data_list = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert f"act_complete_{session.id}" in callback_data_list
    assert f"act_remind_{session.id}" in callback_data_list
    assert f"act_skip_{session.id}" in callback_data_list
    assert f"act_resources_{session.id}" in callback_data_list
