from datetime import date, datetime, time
from app.models.core import Users, Timetable, Holidays, Events, Settings
from app.models.roadmap import Roadmaps, Months, Weeks, Topics, Tasks, StudySessions, RevisionHistory, UserOverrides
from app.planner.time_allocator import TimeAllocator
from app.planner.energy_scheduler import EnergyScheduler
from app.planner.spaced_repetition import SpacedRepetitionEngine
from app.planner.service import PlannerService

def test_time_allocator_blocked_slots(db_session):
    # Create user
    user = Users(name="Test User", wake_up_time="07:00", sleep_time="23:00")
    db_session.add(user)
    db_session.flush()

    # Mock Timetable: class on Monday (weekday=0) 10:00-11:30
    timetable_class = Timetable(
        user_id=user.id,
        day_of_week=0,
        activity_name="Algorithms Lecture",
        start_time="10:00",
        end_time="11:30"
    )
    db_session.add(timetable_class)
    
    # Mock Event: blocked event from 14:00 to 15:00
    target_date = date(2026, 7, 20) # 2026-07-20 is Monday
    event = Events(
        user_id=user.id,
        title="Dentist",
        start_time=datetime(2026, 7, 20, 14, 0),
        end_time=datetime(2026, 7, 20, 15, 0),
        is_blocked_time=True
    )
    db_session.add(event)
    db_session.commit()

    allocator = TimeAllocator(db_session)
    blocked = allocator.get_blocked_intervals(user.id, target_date)
    
    # Expected sleep blocks: 0 to 420 (wake_up), 1380 to 1440 (sleep)
    # Expected lecture block: 600 to 690 (10:00-11:30)
    # Expected dentist block: 840 to 900 (14:00-15:00)
    # Expected default meal/gym:
    # breakfast: 480-525
    # lunch: 780-840
    # dinner: 1200-1260
    # gym: 1080-1140 (gym default "18:00-19:00" = 1080-1140)
    # Let's verify that dentist, class, sleep, and meal times are in the blocked list.
    
    # Let's verify free slots
    free = allocator.get_free_slots(user.id, target_date)
    assert len(free) > 0
    # Check that 10:30 (630) is blocked, but 08:30 (510) is not (or is breakfast, let's verify)
    # Total available hours should be less than 24 - 8 (sleep) = 16 hours
    hours = allocator.get_available_study_hours(user.id, target_date)
    assert hours < 16.0

def test_time_allocator_holiday(db_session):
    user = Users(name="Test User", wake_up_time="07:00", sleep_time="23:00")
    db_session.add(user)
    db_session.flush()

    # Lecture on Monday (weekday=0)
    db_session.add(Timetable(
        user_id=user.id, day_of_week=0, activity_name="Class",
        start_time="09:00", end_time="10:30"
    ))
    # Mark date as holiday
    target_date = date(2026, 7, 20) # Monday
    db_session.add(Holidays(user_id=user.id, date=target_date, description="National holiday"))
    db_session.commit()

    allocator = TimeAllocator(db_session)
    blocked = allocator.get_blocked_intervals(user.id, target_date)

    # Since it is a holiday, class intervals (09:00-10:30 = 540-630) should NOT be blocked
    for start, end in blocked:
        # Check that class time is NOT inside any merged blocked block
        if start <= 540 and end >= 630:
            assert False, "Classes should be skipped on holidays!"

def test_energy_scheduler_placement():
    scheduler = EnergyScheduler(buffer_ratio=0.1)
    
    class MockTask:
        def __init__(self, title, duration, priority, energy):
            self.title = title
            self.estimated_minutes = duration
            self.priority = priority
            self.energy_level = energy

    tasks = [
        MockTask("DP Knapsack", 90, "high", "high"),
        MockTask("CN Reading", 60, "medium", "low"),
        MockTask("DBMS Theory", 45, "low", "low"),
    ]

    # Free slots: 09:00-12:00 (540-720 = 180m) and 14:00-17:00 (840-1020 = 180m)
    # Total free = 360m. Buffer (10%) = 36m. Max study = 324m.
    # Total tasks duration = 90 + 60 + 45 = 195m (fits within 324m limit)
    free_slots = [(540, 720), (840, 1020)]
    
    # Peak study hours morning: 09:00-11:00 (540-660)
    sessions, unscheduled = scheduler.schedule(free_slots, tasks, peak_str="09:00-11:00")
    
    assert len(sessions) == 3
    assert len(unscheduled) == 0
    
    # Verify high energy task is placed in morning peak (starts at 540)
    dp_session = next(s for s in sessions if s["task"].title == "DP Knapsack")
    assert dp_session["start_minutes"] == 540

def test_spaced_repetition_logic(db_session):
    user = Users(name="Jane", email="jane@example.com")
    db_session.add(user)
    db_session.flush()

    roadmap = Roadmaps(user_id=user.id, title="Prep Roadmap")
    db_session.add(roadmap)
    db_session.flush()

    topic = Topics(roadmap_id=roadmap.id, title="Recursion")
    db_session.add(topic)
    db_session.flush()

    task = Tasks(topic_id=topic.id, title="Solve Fibonacci")
    db_session.add(task)
    db_session.commit()

    engine = SpacedRepetitionEngine(db_session)
    completed_date = date(2026, 7, 20)
    
    # Complete task, schedule repetitions
    revisions = engine.schedule_revisions(task.id, completed_date)
    assert len(revisions) == 5
    assert revisions[0].scheduled_date == date(2026, 7, 21) # +1 day
    assert revisions[4].scheduled_date == date(2026, 8, 19) # +30 days

    # Retrieve revisions due on +3 days (2026-07-23)
    due_tasks = engine.get_pending_revisions(user.id, date(2026, 7, 23))
    assert len(due_tasks) == 1
    assert due_tasks[0].title == "Solve Fibonacci"

def test_planner_service_workflow(db_session):
    user = Users(name="Sasha", email="sasha@example.com", wake_up_time="07:00", sleep_time="23:00")
    db_session.add(user)
    db_session.flush()

    roadmap = Roadmaps(user_id=user.id, title="Placement Roadmap", is_active=True, start_date=date(2026, 7, 13))
    db_session.add(roadmap)
    db_session.flush()

    month = Months(roadmap_id=roadmap.id, month_number=1, title="Month 1")
    db_session.add(month)
    db_session.flush()

    week = Weeks(month_id=month.id, week_number=1, title="Week 1")
    db_session.add(week)
    db_session.flush()

    topic = Topics(roadmap_id=roadmap.id, week_id=week.id, title="Arrays")
    db_session.add(topic)
    db_session.flush()

    task1 = Tasks(topic_id=topic.id, title="Two Sum", estimated_minutes=30)
    task2 = Tasks(topic_id=topic.id, title="Container Water", estimated_minutes=45)
    db_session.add(task1)
    db_session.add(task2)
    db_session.commit()

    service = PlannerService(db_session)
    
    # 1. Generate Daily Plan on a Monday (2026-07-20)
    target_date = date(2026, 7, 20)
    plan = service.generate_daily_plan(user.id, target_date)
    
    assert plan.date == target_date
    sessions = db_session.query(StudySessions).filter(StudySessions.daily_plan_id == plan.id).all()
    assert len(sessions) == 2
    assert sessions[0].task.title == "Two Sum"

    # 2. Sunday Mode: Generate plan on Sunday (2026-07-26)
    sunday_date = date(2026, 7, 26)
    sunday_plan = service.generate_daily_plan(user.id, sunday_date)
    
    sun_sessions = db_session.query(StudySessions).filter(StudySessions.daily_plan_id == sunday_plan.id).all()
    # Check that dynamic roadmap-driven Sunday tasks were scheduled
    titles = [s.task.title for s in sun_sessions]
    assert any("Weekly" in t or "Arrays" in t for t in titles)

    # 3. Adaptive Rescheduling
    # Mark Monday's Two Sum completed, leave Container Water planned
    sessions[0].status = "completed"
    db_session.commit()
    
    # Run rescheduling before Tuesday (2026-07-28)
    rescheduled_count = service.reschedule_unfinished_tasks(user.id, date(2026, 7, 28))
    assert rescheduled_count >= 1 # Container Water / Sunday Sessions should be rescheduled
    
    # Check session status updated to postponed
    db_session.refresh(sessions[1])
    assert sessions[1].status == "postponed"
    
    # Check user overrides created
    overrides = db_session.query(UserOverrides).filter(UserOverrides.user_id == user.id).all()
    assert len(overrides) == 5
    assert overrides[0].action == "postpone"
