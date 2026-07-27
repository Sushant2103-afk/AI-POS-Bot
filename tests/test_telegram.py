import pytest
from unittest.mock import AsyncMock, MagicMock
import datetime
from app.models.core import Users, Settings
from app.models.roadmap import Roadmaps, Months, Weeks, Topics, Tasks, StudySessions, DailyPlans
from app.telegram.bot import start, plan, today, complete
from app.telegram.scheduler import send_morning_schedule_job, send_evening_review_job

# --- Mock Classes for python-telegram-bot ---

class MockChat:
    def __init__(self, chat_id: int):
        self.id = chat_id

class MockMessage:
    def __init__(self):
        self.reply_text = AsyncMock()

class MockUpdate:
    def __init__(self, chat_id: int):
        self.effective_chat = MockChat(chat_id)
        self.message = MockMessage()
        self.effective_message = self.message

class MockContext:
    def __init__(self, args=None):
        self.args = args or []

# --- Test Implementations ---

@pytest.mark.anyio
async def test_telegram_start_command(db_session):
    # 1. Create mock user in database
    user = Users(name="TelegramTester", email="tg@example.com")
    db_session.add(user)
    db_session.commit()

    # 2. Invoke start command linking chat ID 99999 to user.id
    update = MockUpdate(chat_id=99999)
    context = MockContext(args=[str(user.id)])
    
    # Override get_db in the module for session consistency
    import app.telegram.bot
    original_get_db = app.telegram.bot.get_db
    app.telegram.bot.get_db = lambda: iter([db_session])
    
    try:
        await start(update, context)
        
        # Verify reply was sent
        update.message.reply_text.assert_called_once()
        reply_args = update.message.reply_text.call_args[0][0]
        assert "linked to AI-POS User ID" in reply_args
        assert "TelegramTester" in reply_args
        
        # Verify settings updated in DB
        setting = db_session.query(Settings).filter(
            Settings.user_id == user.id,
            Settings.key == "telegram_chat_id"
        ).first()
        assert setting is not None
        assert setting.value == "99999"
    finally:
        app.telegram.bot.get_db = original_get_db

@pytest.mark.anyio
async def test_telegram_plan_and_today_commands(db_session):
    # 1. Set up linked user and study plan
    user = Users(name="ScheduleTester", email="st@example.com")
    db_session.add(user)
    db_session.flush()
    
    setting = Settings(user_id=user.id, key="telegram_chat_id", value="88888")
    db_session.add(setting)
    
    roadmap = Roadmaps(user_id=user.id, title="Test Roadmap", is_active=True)
    db_session.add(roadmap)
    db_session.flush()
    
    month = Months(roadmap_id=roadmap.id, month_number=1, title="M1")
    db_session.add(month)
    db_session.flush()
    
    week = Weeks(month_id=month.id, week_number=1, title="W1")
    db_session.add(week)
    db_session.flush()
    
    topic = Topics(roadmap_id=roadmap.id, week_id=week.id, title="Dynamic Programming")
    db_session.add(topic)
    db_session.flush()
    
    task = Tasks(topic_id=topic.id, title="Solve Fibonacci", estimated_minutes=30)
    db_session.add(task)
    db_session.flush()
    
    today_date = datetime.date.today()
    plan_record = DailyPlans(user_id=user.id, date=today_date, total_available_hours=4.0)
    db_session.add(plan_record)
    db_session.flush()
    
    session = StudySessions(
        daily_plan_id=plan_record.id,
        task_id=task.id,
        start_time="09:00",
        end_time="09:30",
        session_type="roadmap",
        status="planned"
    )
    db_session.add(session)
    db_session.commit()

    # 2. Invoke commands
    update = MockUpdate(chat_id=88888)
    context = MockContext()
    
    import app.telegram.bot
    original_get_db = app.telegram.bot.get_db
    app.telegram.bot.get_db = lambda: iter([db_session])
    
    try:
        # Test /plan
        await plan(update, context)
        assert update.message.reply_text.call_count == 1
        plan_reply = update.message.reply_text.call_args[0][0]
        assert "Daily Plan" in plan_reply
        assert "Solve Fibonacci" in plan_reply
        
        # Test /today (pending checklist)
        update.message.reply_text.reset_mock()
        await today(update, context)
        assert update.message.reply_text.call_count == 1
        today_reply = update.message.reply_text.call_args[0][0]
        assert "Pending Tasks" in today_reply
        assert "Fibonacci" in today_reply
    finally:
        app.telegram.bot.get_db = original_get_db

@pytest.mark.anyio
async def test_telegram_complete_command(db_session):
    # 1. Create a planned session
    user = Users(name="CompleterTester", email="ct@example.com")
    db_session.add(user)
    db_session.flush()
    
    setting = Settings(user_id=user.id, key="telegram_chat_id", value="77777")
    db_session.add(setting)
    
    roadmap = Roadmaps(user_id=user.id, title="Test Roadmap", is_active=True)
    db_session.add(roadmap)
    db_session.flush()
    
    month = Months(roadmap_id=roadmap.id, month_number=1, title="M1")
    db_session.add(month)
    db_session.flush()
    
    week = Weeks(month_id=month.id, week_number=1, title="W1")
    db_session.add(week)
    db_session.flush()
    
    topic = Topics(roadmap_id=roadmap.id, week_id=week.id, title="Arrays")
    db_session.add(topic)
    db_session.flush()
    
    task = Tasks(topic_id=topic.id, title="Three Sum", estimated_minutes=30)
    db_session.add(task)
    db_session.flush()
    
    today_date = datetime.date.today()
    plan_record = DailyPlans(user_id=user.id, date=today_date, total_available_hours=4.0)
    db_session.add(plan_record)
    db_session.flush()
    
    session = StudySessions(
        daily_plan_id=plan_record.id,
        task_id=task.id,
        start_time="10:00",
        end_time="10:30",
        session_type="roadmap",
        status="planned"
    )
    db_session.add(session)
    db_session.commit()

    # 2. Invoke /complete <session.id>
    update = MockUpdate(chat_id=77777)
    context = MockContext(args=[str(session.id)])
    
    import app.telegram.bot
    original_get_db = app.telegram.bot.get_db
    app.telegram.bot.get_db = lambda: iter([db_session])
    
    try:
        await complete(update, context)
        assert update.message.reply_text.call_count == 1
        reply = update.message.reply_text.call_args[0][0]
        assert "marked completed" in reply
        
        # Verify changes committed to database
        db_session.refresh(session)
        assert session.status == "completed"
        assert session.task.is_completed is True
    finally:
        app.telegram.bot.get_db = original_get_db

@pytest.mark.anyio
async def test_telegram_scheduler_jobs(db_session, monkeypatch):
    # 1. Setup mock user with chat mapping
    user = Users(name="JobTester", email="jt@example.com")
    db_session.add(user)
    db_session.flush()
    
    setting = Settings(user_id=user.id, key="telegram_chat_id", value="66666")
    db_session.add(setting)
    
    # Seed roadmap and tasks so plan generation actually populates study sessions
    roadmap = Roadmaps(user_id=user.id, title="Test Roadmap", is_active=True)
    db_session.add(roadmap)
    db_session.flush()
    
    month = Months(roadmap_id=roadmap.id, month_number=1, title="M1")
    db_session.add(month)
    db_session.flush()
    
    week = Weeks(month_id=month.id, week_number=1, title="W1")
    db_session.add(week)
    db_session.flush()
    
    topic = Topics(roadmap_id=roadmap.id, week_id=week.id, title="DP")
    db_session.add(topic)
    db_session.flush()
    
    task = Tasks(topic_id=topic.id, title="Fib", estimated_minutes=30)
    db_session.add(task)
    db_session.commit()
    
    # 2. Mock SessionLocal to yield our testing session
    monkeypatch.setattr("app.telegram.scheduler.SessionLocal", lambda: db_session)
    
    # Mock sending to verify calls
    mock_send = AsyncMock()
    monkeypatch.setattr("app.telegram.scheduler.send_telegram_message", mock_send)
    
    # Run morning job (which will auto-generate plan containing the seeded task)
    await send_morning_schedule_job()
    assert mock_send.call_count == 1
    assert "study checklist" in mock_send.call_args[0][1]
    assert "Fib" in mock_send.call_args[0][1]
    
    # Run evening job (detects remaining planned tasks)
    mock_send.reset_mock()
    await send_evening_review_job()
    assert mock_send.call_count == 1
    assert "study block(s) left planned" in mock_send.call_args[0][1]

@pytest.mark.anyio
async def test_telegram_plan_auto_generation_on_demand(db_session):
    # Setup user with roadmap and tasks, but NO pre-generated DailyPlans record for today
    user = Users(name="OnDemandTester", email="ondemand@example.com")
    db_session.add(user)
    db_session.flush()
    
    setting = Settings(user_id=user.id, key="telegram_chat_id", value="55555")
    db_session.add(setting)
    
    roadmap = Roadmaps(user_id=user.id, title="Auto Gen Roadmap", is_active=True, status="active")
    db_session.add(roadmap)
    db_session.flush()
    
    topic = Topics(roadmap_id=roadmap.id, title="Algorithms")
    db_session.add(topic)
    db_session.flush()
    
    task = Tasks(topic_id=topic.id, title="Binary Search", estimated_minutes=45)
    db_session.add(task)
    db_session.commit()
    
    update = MockUpdate(chat_id=55555)
    context = MockContext()
    
    import app.telegram.bot
    original_get_db = app.telegram.bot.get_db
    app.telegram.bot.get_db = lambda: iter([db_session])
    
    try:
        # Requesting /plan (which represents Today's Schedule button) without prior generation
        await plan(update, context)
        assert update.message.reply_text.call_count == 1
        reply = update.message.reply_text.call_args[0][0]
        assert "Daily Plan" in reply
        assert "Binary Search" in reply
    finally:
        app.telegram.bot.get_db = original_get_db


@pytest.mark.anyio
async def test_telegram_keyboard_text_routing(db_session):
    from app.telegram.bot import handle_keyboard_text_or_upload
    
    user = Users(name="KeyboardTester", email="kb@example.com")
    db_session.add(user)
    db_session.flush()
    setting = Settings(user_id=user.id, key="telegram_chat_id", value="44444")
    db_session.add(setting)
    db_session.commit()

    import app.telegram.bot
    original_get_db = app.telegram.bot.get_db
    app.telegram.bot.get_db = lambda: iter([db_session])

    try:
        # Test "todays plan" text routing
        update = MockUpdate(chat_id=44444)
        update.message.text = "todays plan"
        context = MockContext()

        await handle_keyboard_text_or_upload(update, context)
        assert update.message.reply_text.call_count >= 1
        reply = update.message.reply_text.call_args[0][0]
        assert "Daily Plan" in reply

        # Test "📅 Today's Schedule" text routing
        update.message.reply_text.reset_mock()
        update.message.text = "📅 Today's Schedule"
        await handle_keyboard_text_or_upload(update, context)
        assert update.message.reply_text.call_count >= 1
        reply = update.message.reply_text.call_args[0][0]
        assert "Daily Plan" in reply
    finally:
        app.telegram.bot.get_db = original_get_db


