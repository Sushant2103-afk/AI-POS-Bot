import pytest
from fastapi.testclient import TestClient
from datetime import date, datetime
from app.main import app
from app.api.deps import get_db
from app.models.core import Users
from app.models.roadmap import Roadmaps, Months, Weeks, Topics, Tasks, StudySessions, DailyPlans

@pytest.fixture
def client(db_session):
    # Override get_db dependency to use the test database session
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    # Clear overrides after the test is complete
    app.dependency_overrides.clear()

def test_health_check(client):
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "online"

def test_users_endpoints(client):
    # 1. Fetch default user (header X-User-ID defaults to 1, which will trigger auto-creation)
    res = client.get("/api/users/me", headers={"X-User-ID": "1"})
    assert res.status_code == 200
    assert res.json()["name"] == "Default User"

    # 2. Create another user
    new_user = {
        "name": "Alex",
        "email": "alex@example.com",
        "wake_up_time": "06:30",
        "sleep_time": "22:30",
        "preferred_study_hours": 8.0
    }
    res = client.post("/api/users/", json=new_user)
    assert res.status_code == 201
    user_id = res.json()["id"]

    # 3. Put Setting
    setting_payload = {"key": "gym_time", "value": "17:00-18:00"}
    res = client.put("/api/users/settings", json=setting_payload, headers={"X-User-ID": str(user_id)})
    assert res.status_code == 200
    assert res.json()["value"] == "17:00-18:00"

    # 4. Get Settings
    res = client.get("/api/users/settings", headers={"X-User-ID": str(user_id)})
    assert res.status_code == 200
    assert len(res.json()) == 1

    # 5. Add Timetable
    timetable_payload = {
        "day_of_week": 1,
        "activity_name": "Database Systems",
        "start_time": "11:00",
        "end_time": "12:30"
    }
    res = client.post("/api/users/timetable", json=timetable_payload, headers={"X-User-ID": str(user_id)})
    assert res.status_code == 201
    assert res.json()["activity_name"] == "Database Systems"

def test_imports_and_planner_endpoints(client, db_session):
    # 1. Create a user
    user = Users(name="Bob", email="bob@example.com")
    db_session.add(user)
    db_session.flush()
    user_id = str(user.id)

    # 2. Paste text import
    roadmap_data = {
        "title": "Unstructured Curriculum",
        "content": """
        Month 1: DSA Foundation
        Week 1: Array Basics
        - Priority: high
        - Topic: Array insertions and deletions (Estimated Hours: 4.0, Energy Level: medium)
        - Tasks:
          * Solve Two Sum (30 mins, Priority: high, Energy Level: high)
          * Solve Container With Most Water (45 mins, Priority: high, Energy Level: high)
        """
    }
    res = client.post("/api/imports/text", json=roadmap_data, headers={"X-User-ID": user_id})
    assert res.status_code == 201
    assert res.json()["title"] == "Mock SDE Prep Roadmap" # MockAIProvider returns standard title

    # 3. Generate plan
    plan_date = "2026-07-20" # Monday
    res = client.post("/api/planner/generate", json={"target_date": plan_date}, headers={"X-User-ID": user_id})
    assert res.status_code == 201
    assert len(res.json()["study_sessions"]) == 2

    # 4. Fetch plan
    res = client.get(f"/api/planner/daily-plan?target_date={plan_date}", headers={"X-User-ID": user_id})
    assert res.status_code == 200
    plan_id = res.json()["id"]
    sessions = res.json()["study_sessions"]
    assert len(sessions) == 2
    session_id = sessions[0]["id"]

    # 5. Complete session
    res = client.post(f"/api/planner/sessions/{session_id}/complete", headers={"X-User-ID": user_id})
    assert res.status_code == 200
    assert res.json()["status"] == "completed"

    # 6. Trigger Reschedule
    res = client.post("/api/planner/reschedule", headers={"X-User-ID": user_id})
    assert res.status_code == 200
    # There is 1 past uncompleted session (Container Water), so count should be 1
    assert res.json()["rescheduled_count"] == 1

def test_exports_endpoint(client, db_session):
    user = Users(name="ExportTester", email="export@example.com")
    db_session.add(user)
    db_session.flush()
    user_id = str(user.id)

    # Export plan in markdown, csv, and json
    res_md = client.get("/api/exports/plan?format=markdown", headers={"X-User-ID": user_id})
    assert res_md.status_code == 200
    assert "Daily Study Schedule" in res_md.text

    res_csv = client.get("/api/exports/plan?format=csv", headers={"X-User-ID": user_id})
    assert res_csv.status_code == 200
    assert "Start Time,End Time" in res_csv.text

    res_json = client.get("/api/exports/plan?format=json", headers={"X-User-ID": user_id})
    assert res_json.status_code == 200
    assert "study_sessions" in res_json.json()
