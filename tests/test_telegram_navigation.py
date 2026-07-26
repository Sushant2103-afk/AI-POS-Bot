import pytest
from unittest.mock import AsyncMock, MagicMock
import datetime

from app.models.core import Users, Settings
from app.models.roadmap import Roadmaps, Months, Weeks, Topics, Tasks, StudySessions, DailyPlans
from app.telegram.bot import (
    send_or_edit_message,
    show_main_menu,
    show_settings_menu,
    show_schedule_settings_menu,
    show_roadmaps_menu,
    show_delete_roadmap_selection,
    show_learning_history,
    handle_callback_query,
    _send_plan,
    _send_stats,
    prompt_curriculum_upload
)

class MockBotUser:
    def __init__(self, is_bot=True):
        self.is_bot = is_bot

class MockMessage:
    def __init__(self, message_id=101, is_bot=True):
        self.message_id = message_id
        self.from_user = MockBotUser(is_bot=is_bot)
        self.reply_text = AsyncMock()
        self.edit_text = AsyncMock()
        self.text = ""

class MockCallbackQuery:
    def __init__(self, data: str, message: MockMessage):
        self.data = data
        self.message = message
        self.answer = AsyncMock()

class MockUpdate:
    def __init__(self, chat_id: int = 12345, callback_data: str = None):
        self.effective_chat = MagicMock(id=chat_id)
        self.message = MockMessage()
        self.effective_message = self.message
        if callback_data:
            self.callback_query = MockCallbackQuery(callback_data, self.message)
        else:
            self.callback_query = None

@pytest.mark.anyio
async def test_send_or_edit_message_navigation_edits_existing():
    # Test that navigational updates with callback query edit existing message
    update = MockUpdate(chat_id=12345, callback_data="act_set_main_menu")
    await send_or_edit_message(update, "Settings Screen", is_navigational=True)

    update.message.edit_text.assert_called_once()
    assert "Settings Screen" in update.message.edit_text.call_args[1]["text"]
    update.message.reply_text.assert_not_called()

@pytest.mark.anyio
async def test_send_or_edit_message_historical_sends_new_message():
    # Test that non-navigational updates (historical records) send a new message
    update = MockUpdate(chat_id=12345, callback_data="act_plan")
    await send_or_edit_message(update, "Daily Plan Record", is_navigational=False)

    update.message.reply_text.assert_called_once()
    assert "Daily Plan Record" in update.message.reply_text.call_args[1]["text"]
    update.message.edit_text.assert_not_called()

@pytest.mark.anyio
async def test_telegram_menu_navigation_flow(db_session):
    user = Users(name="NavTester", email="nav@example.com")
    db_session.add(user)
    db_session.flush()

    setting = Settings(user_id=user.id, key="telegram_chat_id", value="12345")
    db_session.add(setting)

    roadmap = Roadmaps(user_id=user.id, title="Python Mastery", is_active=True)
    db_session.add(roadmap)
    db_session.commit()

    import app.telegram.bot
    original_get_db = app.telegram.bot.get_db
    app.telegram.bot.get_db = lambda: iter([db_session])

    try:
        # 1. Main Menu -> Settings (callback query)
        update_set = MockUpdate(chat_id=12345, callback_data="act_set_main_menu")
        await handle_callback_query(update_set, MagicMock())

        # Should edit message in place
        update_set.message.edit_text.assert_called_once()
        assert "Automation & Study Preferences" in update_set.message.edit_text.call_args[1]["text"]

        # 2. Settings -> Schedule Settings
        update_sched = MockUpdate(chat_id=12345, callback_data="act_set_schedule_menu")
        await handle_callback_query(update_sched, MagicMock())

        update_sched.message.edit_text.assert_called_once()
        assert "Study Schedule Configuration" in update_sched.message.edit_text.call_args[1]["text"]

        # 3. Settings -> Manage Roadmaps
        update_rm = MockUpdate(chat_id=12345, callback_data="act_rm_list")
        await handle_callback_query(update_rm, MagicMock())

        update_rm.message.edit_text.assert_called_once()
        assert "Python Mastery" in update_rm.message.edit_text.call_args[1]["text"]

        # 4. Back to Main Menu
        update_back = MockUpdate(chat_id=12345, callback_data="act_main_menu")
        await handle_callback_query(update_back, MagicMock())

        update_back.message.edit_text.assert_called_once()
        assert "AI Personal Operating System" in update_back.message.edit_text.call_args[1]["text"]

    finally:
        app.telegram.bot.get_db = original_get_db
