import pytest
import datetime
from fastapi.testclient import TestClient
from app.main import app
from app.api.deps import get_db, get_current_user_id
from app.models.core import Users
from app.models.roadmap import Roadmaps, Topics, Tasks
from app.imports.engine import ImportEngine
from app.planner.service import PlannerService

client = TestClient(app)

@pytest.fixture
def test_user(db_session):
    user = Users(name="Test Multi User", email="multiuser@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

def test_import_multiple_independent_roadmaps(db_session, test_user):
    """Verify that multiple imported roadmaps coexist independently without overwriting."""
    engine = ImportEngine(db_session)

    text1 = """
    Month 1: Placement Prep
    Week 1: Core Algorithms
    - Topic: Data Structures
      - Task: Solve Arrays Problem (30 mins)
    """
    rm1 = engine.import_roadmap_text(
        user_id=test_user.id,
        raw_text=text1,
        title="Placement Prep",
        category="Placement",
        priority=1
    )

    text2 = """
    Month 1: AI/ML Engineering
    Week 1: Neural Networks
    - Topic: Deep Learning
      - Task: Train PyTorch Model (60 mins)
    """
    rm2 = engine.import_roadmap_text(
        user_id=test_user.id,
        raw_text=text2,
        title="AI/ML Engineering",
        category="AI/ML",
        priority=2
    )

    # rm2 was imported second, so rm1 (previous active) is auto-paused to focus on rm2 (new active focus)
    all_roadmaps = db_session.query(Roadmaps).filter(Roadmaps.user_id == test_user.id).order_by(Roadmaps.id.asc()).all()
    assert len(all_roadmaps) == 2
    titles = [r.title for r in all_roadmaps]
    assert "Placement Prep" in titles
    assert "AI/ML Engineering" in titles
    assert all_roadmaps[0].status == "paused"
    assert all_roadmaps[0].is_active is False
    assert all_roadmaps[1].status == "active"
    assert all_roadmaps[1].is_active is True

def test_multi_roadmap_planner_priority(db_session, test_user):
    """Verify that PlannerService schedules tasks from multiple active roadmaps sorted by priority."""
    engine = ImportEngine(db_session)

    rm1 = engine.import_roadmap_text(
        user_id=test_user.id,
        raw_text="Month 1: A\nWeek 1: B\n- Topic: C\n  - Task: Placement Task (45 mins)",
        title="Placement Prep",
        category="Placement",
        priority=1
    )

    rm2 = engine.import_roadmap_text(
        user_id=test_user.id,
        raw_text="Month 1: X\nWeek 1: Y\n- Topic: Z\n  - Task: AI/ML Task (45 mins)",
        title="AI/ML Roadmap",
        category="AI/ML",
        priority=2
    )

    # Explicitly activate both roadmaps with priorities 1 and 2 to test multi-roadmap priority ordering
    rm1.status = "active"
    rm1.is_active = True
    rm1.priority = 1
    rm2.status = "active"
    rm2.is_active = True
    rm2.priority = 2
    db_session.commit()

    planner = PlannerService(db_session)
    monday_date = datetime.date(2026, 7, 27) # Monday
    plan = planner.generate_daily_plan(test_user.id, monday_date)

    assert plan is not None
    assert len(plan.study_sessions) >= 2
    # Verify higher priority roadmap task (Priority 1) is scheduled before Priority 2
    first_task = plan.study_sessions[0].task
    second_task = plan.study_sessions[1].task
    assert first_task.topic.roadmap_id == rm1.id
    assert second_task.topic.roadmap_id == rm2.id

def test_paused_roadmap_exclusion(db_session, test_user):
    """Verify that tasks from paused roadmaps are excluded from daily study plans."""
    engine = ImportEngine(db_session)

    rm1 = engine.import_roadmap_text(
        user_id=test_user.id,
        raw_text="Month 1: A\nWeek 1: B\n- Topic: C\n  - Task: Active Task (30 mins)",
        title="Active Roadmap",
        priority=1
    )

    rm2 = engine.import_roadmap_text(
        user_id=test_user.id,
        raw_text="Month 1: X\nWeek 1: Y\n- Topic: Z\n  - Task: Paused Task (30 mins)",
        title="Paused Roadmap",
        priority=2
    )

    # Ensure rm1 is active and rm2 is paused
    rm1.status = "active"
    rm1.is_active = True
    rm2.status = "paused"
    rm2.is_active = False
    db_session.commit()

    planner = PlannerService(db_session)
    monday_date = datetime.date(2026, 7, 27) # Monday
    plan = planner.generate_daily_plan(test_user.id, monday_date)

    roadmap_ids = [s.task.topic.roadmap_id for s in plan.study_sessions if s.task and s.task.topic]
    assert rm1.id in roadmap_ids
    assert rm2.id not in roadmap_ids

def test_roadmap_rest_api_crud(db_session, test_user):
    """Verify REST API endpoint functions for listing, creating, updating, and pausing roadmaps."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user_id] = lambda: test_user.id

    try:
        # 1. Create roadmap via REST API
        resp = client.post("/api/roadmaps", json={
            "title": "Cybersecurity Roadmap",
            "category": "Cybersecurity",
            "priority": 3,
            "schedule_type": "weekends"
        })
        assert resp.status_code == 201
        data = resp.json()
        rm_id = data["id"]
        assert data["title"] == "Cybersecurity Roadmap"
        assert data["priority"] == 3

        # 2. List roadmaps
        list_resp = client.get("/api/roadmaps")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) >= 1

        # 3. Pause roadmap
        pause_resp = client.post(f"/api/roadmaps/{rm_id}/pause")
        assert pause_resp.status_code == 200
        assert pause_resp.json()["status"] == "paused"

        # 4. Resume roadmap
        resume_resp = client.post(f"/api/roadmaps/{rm_id}/resume")
        assert resume_resp.status_code == 200
        assert resume_resp.json()["status"] == "active"

        # 5. Analytics summary
        analytics_resp = client.get("/api/roadmaps/analytics/summary")
        assert analytics_resp.status_code == 200
        summary = analytics_resp.json()
        assert summary["active_roadmaps_count"] >= 1
    finally:
        app.dependency_overrides.clear()
