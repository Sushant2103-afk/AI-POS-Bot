import os
import sys
import asyncio
import datetime
import traceback
from typing import Optional
from contextlib import contextmanager

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.orm import Session
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram.error import Conflict, NetworkError

from app.database.session import SessionLocal
from app.models.core import Users, Settings
from app.models.roadmap import StudySessions, Tasks, DailyPlans, Progress, Topics, Roadmaps, UserFavorites
from app.planner.spaced_repetition import SpacedRepetitionEngine
from app.planner.service import PlannerService
from app.imports.engine import ImportEngine
from app.core.config import settings
from app.core.logging import logger
from app.core.settings_service import get_user_setting, set_user_setting, get_all_user_settings

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def start_health_check_server():
    try:
        port = int(os.environ.get("PORT", 8000))
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"Health check HTTP server started on port {port}")
    except Exception as e:
        logger.warning(f"Could not start health check server: {e}")

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_target_message(target):
    """
    Safely resolve a replyable Telegram Message object from any update type.
    Priority: callback_query.message > effective_message > message > direct object.
    """
    if target is None:
        return None
    if hasattr(target, "reply_text") and callable(target.reply_text):
        return target
    if hasattr(target, "callback_query") and target.callback_query is not None:
        cq_msg = getattr(target.callback_query, "message", None)
        if cq_msg is not None:
            return cq_msg
    if hasattr(target, "effective_message") and target.effective_message is not None:
        return target.effective_message
    if hasattr(target, "message") and target.message is not None:
        return target.message
    return None

async def send_or_edit_message(
    target,
    text: str,
    reply_markup=None,
    parse_mode: str = "Markdown",
    disable_web_page_preview: bool = False,
    is_navigational: bool = True
):
    """
    Smart message router:
    - If is_navigational is True and target was triggered via a callback query or inline button message,
      edits the existing message instead of sending a new one.
    - If editing fails or if is_navigational is False (for historical content like Daily Plan, Morning Briefing),
      sends a new message using reply_text.
    """
    target_msg = get_target_message(target)
    if not target_msg:
        return None

    is_editable = False
    editable_msg = target_msg

    if hasattr(target, "callback_query") and target.callback_query and getattr(target.callback_query, "message", None):
        editable_msg = target.callback_query.message
        is_editable = True
    elif hasattr(target_msg, "edit_text"):
        if hasattr(target_msg, "from_user") and target_msg.from_user and getattr(target_msg.from_user, "is_bot", False):
            is_editable = True
        elif hasattr(target, "from_user") and target.from_user and getattr(target.from_user, "is_bot", False):
            is_editable = True

    if is_navigational and is_editable:
        try:
            return await editable_msg.edit_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )
        except Exception as e:
            err_str = str(e)
            if "Message is not modified" in err_str:
                return editable_msg
            logger.warning(f"Could not edit message, falling back to reply_text: {e}")

    return await target_msg.reply_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        disable_web_page_preview=disable_web_page_preview
    )

def get_user_id_by_chat_id(db: Session, chat_id: int, user_name: Optional[str] = None) -> int:
    setting = db.query(Settings).filter(
        Settings.key == "telegram_chat_id",
        Settings.value == str(chat_id)
    ).first()
    if setting:
        return setting.user_id
    
    # Check if user #1 exists and no chat ID is assigned yet
    default_user = db.query(Users).filter(Users.id == 1).first()
    has_chat_setting = db.query(Settings).filter(Settings.key == "telegram_chat_id").first()
    
    if default_user and not has_chat_setting:
        chat_setting = Settings(user_id=default_user.id, key="telegram_chat_id", value=str(chat_id))
        db.add(chat_setting)
        db.commit()
        return default_user.id

    # Create new isolated user profile for new Telegram users (e.g. friends)
    name = user_name or f"Telegram User {chat_id}"
    email = f"tg_{chat_id}@example.com"
    new_user = Users(name=name, email=email)
    db.add(new_user)
    db.flush()
    
    chat_setting = Settings(user_id=new_user.id, key="telegram_chat_id", value=str(chat_id))
    db.add(chat_setting)
    db.commit()
    return new_user.id

def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Persistent bottom navigation keyboard buttons for Telegram UI."""
    keyboard = [
        [KeyboardButton("📅 Today's Schedule"), KeyboardButton("⏳ Pending Tasks")],
        [KeyboardButton("📥 Upload Curriculum"), KeyboardButton("🗂 Roadmaps")],
        [KeyboardButton("⚡ Auto-Schedule Today"), KeyboardButton("📂 Learning History")],
        [KeyboardButton("📊 Progress Stats"), KeyboardButton("⚙️ Settings")],
        [KeyboardButton("❓ Help & Guide")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def build_plan_message_and_markup(db: Session, user_id: int, target_date):
    """Builds formatted plan text along with structured, block-indexed inline buttons per task."""
    plan = db.query(DailyPlans).filter(
        DailyPlans.user_id == user_id,
        DailyPlans.date == target_date
    ).first()
    
    if not plan or not plan.study_sessions:
        try:
            planner = PlannerService(db)
            plan = planner.generate_daily_plan(user_id, target_date)
        except Exception as e:
            logger.error(f"Error auto-generating daily plan for User #{user_id}: {e}")

    if not plan or not plan.study_sessions:
        msg = (
            f"📅 *Daily Plan • {target_date}*\n"
            f"───────────────────────────\n\n"
            f"ℹ️ *No study sessions scheduled for today.*\n"
            f"Upload a syllabus or click Auto-Schedule below to generate your plan."
        )
        inline_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📥 Upload Curriculum", callback_data="act_upload_prompt"),
                InlineKeyboardButton("⚡ Auto-Schedule Now", callback_data="act_schedule")
            ],
            [InlineKeyboardButton("⏰ Set Custom Time", callback_data="act_set_schedule_menu")]
        ])
        return msg, inline_kb
        
    fav_task_ids = set(f.task_id for f in db.query(UserFavorites.task_id).filter(UserFavorites.user_id == user_id).all())

    completed_count = sum(1 for s in plan.study_sessions if s.status == "completed")
    total_sessions = len(plan.study_sessions)
    progress_pct = int((completed_count / total_sessions) * 100) if total_sessions > 0 else 0
    progress_bar = "▓" * (progress_pct // 10) + "░" * (10 - (progress_pct // 10))

    msg = (
        f"📅 *Daily Plan • {target_date}*\n"
        f"📊 *Progress:* `{progress_bar}` *{progress_pct}%* ({completed_count}/{total_sessions} done)\n"
        f"───────────────────────────\n\n"
    )
    inline_buttons = []
    
    for idx, s in enumerate(plan.study_sessions, 1):
        task = s.task
        if not task:
            continue
            
        status_icon = "✅" if s.status == "completed" else ("⏭" if s.status == "skipped" else ("⏰" if s.status == "reminded" else "⏳"))
        status_text = "COMPLETED" if s.status == "completed" else ("SKIPPED" if s.status == "skipped" else ("REMINDED" if s.status == "reminded" else "PENDING"))
        
        task_name = task.title
        est_min = task.estimated_minutes
        energy = task.energy_level.upper()
        is_fav = task.id in fav_task_ids

        msg += f"🔹 *Block #{idx}* • `{s.start_time} - {s.end_time}` {status_icon}\n"
        msg += f"   📌 *Task:* {task_name}\n"
        msg += f"   ⚡ `{energy}` Energy | ⏱ `{est_min} min` | `{status_text}`\n"
        if task.description:
            msg += f"   📝 _{task.description[:70]}_\n"
        msg += "\n"
        
        if s.status == "completed":
            inline_buttons.append([
                InlineKeyboardButton(f"✅ Block #{idx} Completed", callback_data=f"act_noop_{s.id}")
            ])
        else:
            fav_label = f"⭐ Fav #{idx}" if is_fav else f"☆ Fav #{idx}"
            inline_buttons.append([
                InlineKeyboardButton(f"✅ Done #{idx}", callback_data=f"act_complete_{s.id}"),
                InlineKeyboardButton(f"⏰ Remind #{idx}", callback_data=f"act_remind_{s.id}"),
                InlineKeyboardButton(f"⏭ Skip #{idx}", callback_data=f"act_skip_{s.id}")
            ])
            inline_buttons.append([
                InlineKeyboardButton(f"📚 Resources #{idx}", callback_data=f"act_resources_{s.id}"),
                InlineKeyboardButton(fav_label, callback_data=f"act_fav_{task.id}")
            ])

    inline_buttons.append([
        InlineKeyboardButton("⚡ Re-Schedule Today", callback_data="act_schedule"),
        InlineKeyboardButton("📥 Upload Syllabus", callback_data="act_upload_prompt")
    ])
    inline_buttons.append([
        InlineKeyboardButton("📊 Progress Stats", callback_data="act_stats"),
        InlineKeyboardButton("⚙️ Settings", callback_data="act_set_main_menu")
    ])
    
    return msg, InlineKeyboardMarkup(inline_buttons)


def format_daily_plan_message(db: Session, user_id: int, target_date) -> str:
    msg, _ = build_plan_message_and_markup(db, user_id, target_date)
    return msg

# --- Global Telegram Error Handler ---

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends exact raw Python exception traceback directly to Telegram."""
    if isinstance(context.error, (Conflict, NetworkError)) or "Conflict" in str(context.error):
        logger.warning(f"Transient polling conflict/network error ignored: {context.error}")
        return

    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    logger.error(f"Global exception caught in Telegram bot: {tb_string}")

    target_msg = get_target_message(update)
    if target_msg:
        try:
            formatted_error = (
                f"🚨 *Telegram Handler Exception*\n\n"
                f"```python\n{tb_string[-3500:]}\n```"
            )
            await target_msg.reply_text(formatted_error, parse_mode="Markdown")
        except Exception:
            try:
                await target_msg.reply_text(f"🚨 Exception: {str(context.error)}")
            except Exception as e:
                logger.error(f"Failed to send exception message to user: {e}")

# --- Primary Command & UI Helpers ---

async def show_main_menu(target_message, chat_id: int):
    target_msg = get_target_message(target_message)
    if not target_msg:
        return
    with get_db() as db:
        user_id = get_user_id_by_chat_id(db, chat_id) or 1
        
        welcome_text = (
            f"🤖 *AI Personal Operating System (AI-POS)* (User #{user_id})\n\n"
            "Select an option below to manage your learning & study schedule:\n\n"
            "• 📅 *Today's Schedule*: View current study plan.\n"
            "• ⚡ *Auto-Schedule*: Generate smart time slots.\n"
            "• 🗂 *Roadmaps*: Manage active study roadmaps.\n"
            "• 📚 *Resources*: Get domain-tailored documentation & tutorials.\n"
            "• ⚙️ *Settings*: Configure Study Mode & Preferences."
        )
        
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📅 Today's Plan", callback_data="act_plan"),
                InlineKeyboardButton("⚡ Auto-Schedule", callback_data="act_schedule")
            ],
            [
                InlineKeyboardButton("🗂 Roadmaps", callback_data="act_rm_list"),
                InlineKeyboardButton("⚙️ Settings", callback_data="act_set_main_menu")
            ],
            [
                InlineKeyboardButton("📊 Analytics & Stats", callback_data="act_stats"),
                InlineKeyboardButton("📂 Learning History", callback_data="act_hist_completed")
            ]
        ])
        
        await send_or_edit_message(target_message, welcome_text, reply_markup=markup, is_navigational=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = get_target_message(update)
    chat_id = update.effective_chat.id if update.effective_chat else 1
    with get_db() as db:
        args = getattr(context, "args", [])
        if args and args[0].isdigit():
            user_id = int(args[0])
            user = db.query(Users).filter(Users.id == user_id).first()
            user_name = user.name if user else f"User {user_id}"
            from app.core.settings_service import set_user_setting
            set_user_setting(db, user_id, "telegram_chat_id", str(chat_id))
            reply_text = f"✅ Telegram Chat ID linked to AI-POS User ID {user_id} ({user_name})."
            if target_msg:
                await target_msg.reply_text(reply_text, reply_markup=get_main_reply_keyboard())
            return

    if target_msg:
        await target_msg.reply_text(
            "👋 *Welcome to AI Personal Operating System (AI-POS)!*\n"
            "Use the navigation buttons at the bottom of your screen or the inline options below.",
            parse_mode="Markdown",
            reply_markup=get_main_reply_keyboard()
        )

    await show_main_menu(update, chat_id)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = get_target_message(update)
    help_text = (
        "❓ *AI-POS Telegram Guide & Commands*\n\n"
        "• `/plan` - View today's scheduled study blocks.\n"
        "• `/schedule` - Auto-generate / re-schedule today's plan.\n"
        "• `/pending` - View pending study tasks for today.\n"
        "• `/complete <block_id>` - Mark a study block completed.\n"
        "• `/roadmaps` - Manage active study roadmaps.\n"
        "• `/stats` - View your overall study completion progress.\n"
        "• `/settings` - Configure Custom Study Time vs Automatic Mode.\n\n"
        "💡 *Tip:* Use the bottom navigation buttons for quick access!"
    )
    if target_msg:
        await target_msg.reply_text(help_text, parse_mode="Markdown", reply_markup=get_main_reply_keyboard())

async def _send_plan(target_message, chat_id: int):
    target_msg = get_target_message(target_message)
    if not target_msg:
        return
    with get_db() as db:
        try:
            user_id = get_user_id_by_chat_id(db, chat_id) or 1
            today_date = datetime.date.today()
            msg, markup = build_plan_message_and_markup(db, user_id, today_date)
            await target_msg.reply_text(msg, parse_mode="Markdown", reply_markup=markup)
        except Exception:
            tb = traceback.format_exc()
            await target_msg.reply_text(tb)

async def plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = get_target_message(update)
    chat_id = update.effective_chat.id if update.effective_chat else 1
    await _send_plan(target_msg, chat_id)


async def _send_schedule(target_message, chat_id: int):
    target_msg = get_target_message(target_message)
    if not target_msg:
        return
    with get_db() as db:
        try:
            user_id = get_user_id_by_chat_id(db, chat_id) or 1
            today_date = datetime.date.today()
            planner = PlannerService(db)
            
            await target_msg.reply_text("⚡ *Generating daily study plan...*", parse_mode="Markdown")
            planner.generate_daily_plan(user_id, today_date)
            
            msg, markup = build_plan_message_and_markup(db, user_id, today_date)
            await target_msg.reply_text(f"✅ *Schedule Updated!*\n\n" + msg, parse_mode="Markdown", reply_markup=markup)
        except Exception:
            tb = traceback.format_exc()
            await target_msg.reply_text(tb)

async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = get_target_message(update)
    chat_id = update.effective_chat.id if update.effective_chat else 1
    await _send_schedule(target_msg, chat_id)

async def _send_stats(target_message, chat_id: int):
    target_msg = get_target_message(target_message)
    if not target_msg:
        return
    with get_db() as db:
        try:
            user_id = get_user_id_by_chat_id(db, chat_id) or 1
            all_tasks = db.query(Tasks).all()
            total_cnt = len(all_tasks)
            completed_cnt = len([t for t in all_tasks if t.is_completed])
            
            pct = (completed_cnt / total_cnt * 100.0) if total_cnt > 0 else 0.0
            
            roadmaps = db.query(Roadmaps).filter(Roadmaps.user_id == user_id).all()
            
            msg = (
                f"📊 *AI-POS Progress & Analytics*\n\n"
                f"• *Total Tasks*: {total_cnt}\n"
                f"• *Completed Tasks*: {completed_cnt}\n"
                f"• *Overall Completion Rate*: {pct:.1f}%\n"
                f"• *Active Roadmaps*: {len(roadmaps)}\n\n"
                f"Keep up the consistent effort!"
            )
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚡ Auto-Schedule Today", callback_data="act_schedule")],
                [InlineKeyboardButton("🗂 Manage Roadmaps", callback_data="act_rm_list")],
                [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="act_main_menu")]
            ])
            await send_or_edit_message(target_message, msg, reply_markup=markup, is_navigational=True)
        except Exception:
            tb = traceback.format_exc()
            await send_or_edit_message(target_message, tb, is_navigational=False)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = get_target_message(update)
    chat_id = update.effective_chat.id if update.effective_chat else 1
    await _send_stats(target_msg, chat_id)

async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = get_target_message(update)
    chat_id = update.effective_chat.id if update.effective_chat else 1
    with get_db() as db:
        try:
            user_id = get_user_id_by_chat_id(db, chat_id) or 1
            today_date = datetime.date.today()
            
            plan_rec = db.query(DailyPlans).filter(
                DailyPlans.user_id == user_id,
                DailyPlans.date == today_date
            ).first()
            
            if not plan_rec or not plan_rec.study_sessions:
                await target_msg.reply_text(
                    f"📅 No study plan found for today ({today_date}).",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡ Auto-Schedule Now", callback_data="act_schedule")]])
                )
                return
                
            pending_sessions = [s for s in plan_rec.study_sessions if s.status == "planned"]
            if not pending_sessions:
                await target_msg.reply_text("🎉 All tasks for today are completed! Excellent job!")
                return
                
            msg = f"⏳ *Pending Tasks for Today ({today_date})*\n\n"
            inline_buttons = []
            for s in pending_sessions:
                t_name = s.task.title if s.task else "Session"
                msg += f"• *Block {s.id}:* {s.start_time} - {s.end_time}\n"
                msg += f"  Task: {t_name} ({s.task.estimated_minutes if s.task else 60} mins)\n\n"
                inline_buttons.append([
                    InlineKeyboardButton(f"✅ Complete Block {s.id}", callback_data=f"act_complete_{s.id}"),
                    InlineKeyboardButton("📚 Resources", callback_data=f"act_resources_{s.id}")
                ])
                
            await target_msg.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_buttons))
        except Exception:
            tb = traceback.format_exc()
            await target_msg.reply_text(tb)

today = pending

async def complete(update: Update, context: ContextTypes.DEFAULT_TYPE):

    target_msg = get_target_message(update)
    chat_id = update.effective_chat.id if update.effective_chat else 1
    args = context.args
    
    if not args or not args[0].isdigit():
        if target_msg:
            await target_msg.reply_text("⚠️ Usage: Tap a button or use `/complete <block_id>`")
        return
        
    session_id = int(args[0])
    await process_completion(target_msg, chat_id, session_id)

async def process_completion(target_msg, chat_id: int, session_id: int):
    if target_msg is not None and not hasattr(target_msg, "reply_text"):
        target_msg = get_target_message(target_msg)
    with get_db() as db:
        try:
            user_id = get_user_id_by_chat_id(db, chat_id) or 1
            session = db.query(StudySessions).join(
                DailyPlans, DailyPlans.id == StudySessions.daily_plan_id
            ).filter(
                DailyPlans.user_id == user_id,
                StudySessions.id == session_id
            ).first()
            
            if not session:
                if target_msg:
                    await target_msg.reply_text(f"❌ Study block ID {session_id} not found.")
                return
                
            if session.status == "completed":
                if target_msg:
                    await target_msg.reply_text(f"✅ Block {session_id} was already marked completed.")
                return
                
            session.status = "completed"
            task = db.query(Tasks).filter(Tasks.id == session.task_id).first()
            if task:
                task.is_completed = True
                progress = Progress(
                    task_id=task.id,
                    completed_at=datetime.datetime.utcnow(),
                    actual_minutes_spent=task.estimated_minutes,
                    notes="Completed via Telegram UI Button."
                )
                db.add(progress)
                
                repetition_engine = SpacedRepetitionEngine(db)
                repetition_engine.schedule_revisions(task.id, session.daily_plan.date)
                
            db.commit()
            task_title = task.title if task else "Study Task"
            
            today_date = datetime.date.today()
            msg, markup = build_plan_message_and_markup(db, user_id, today_date)
            reply_text = f"🎉 *Success!* Block {session_id} (*{task_title}*) marked completed!\n\n" + msg
            if target_msg:
                await target_msg.reply_text(reply_text, parse_mode="Markdown", reply_markup=markup)
        except Exception:
            tb = traceback.format_exc()
            if target_msg:
                await target_msg.reply_text(tb)

async def process_remind(target_msg, chat_id: int, session_id: int):
    if target_msg is not None and not hasattr(target_msg, "reply_text"):
        target_msg = get_target_message(target_msg)
    with get_db() as db:
        try:
            user_id = get_user_id_by_chat_id(db, chat_id) or 1
            session = db.query(StudySessions).filter(StudySessions.id == session_id).first()
            if session:
                session.status = "reminded"
                db.commit()
                task_title = session.task.title if session.task else "Study Task"
                today_date = datetime.date.today()
                msg, markup = build_plan_message_and_markup(db, user_id, today_date)
                reply_text = f"⏰ *Remind Later set for Block {session_id}* (*{task_title}*)!\n\n" + msg
                await target_msg.reply_text(reply_text, parse_mode="Markdown", reply_markup=markup)
            else:
                await target_msg.reply_text(f"❌ Session #{session_id} not found.")
        except Exception:
            tb = traceback.format_exc()
            await target_msg.reply_text(tb)

async def process_skip(target_msg, chat_id: int, session_id: int):
    if target_msg is not None and not hasattr(target_msg, "reply_text"):
        target_msg = get_target_message(target_msg)
    with get_db() as db:
        try:
            user_id = get_user_id_by_chat_id(db, chat_id) or 1
            session = db.query(StudySessions).filter(StudySessions.id == session_id).first()
            if session:
                session.status = "skipped"
                if session.task:
                    session.task.skip_count = (session.task.skip_count or 0) + 1
                db.commit()
                task_title = session.task.title if session.task else "Study Task"
                today_date = datetime.date.today()
                msg, markup = build_plan_message_and_markup(db, user_id, today_date)
                reply_text = f"⏭ *Skipped Block {session_id}* (*{task_title}*). Moved to upcoming pool.\n\n" + msg
                await target_msg.reply_text(reply_text, parse_mode="Markdown", reply_markup=markup)
            else:
                await target_msg.reply_text(f"❌ Session #{session_id} not found.")
        except Exception:
            tb = traceback.format_exc()
            await target_msg.reply_text(tb)

async def process_fav(target_msg, chat_id: int, task_id: int):
    if target_msg is not None and not hasattr(target_msg, "reply_text"):
        target_msg = get_target_message(target_msg)
    with get_db() as db:
        try:
            user_id = get_user_id_by_chat_id(db, chat_id) or 1
            fav = db.query(UserFavorites).filter(UserFavorites.user_id == user_id, UserFavorites.task_id == task_id).first()
            task = db.query(Tasks).filter(Tasks.id == task_id).first()
            task_title = task.title if task else f"Task #{task_id}"
            
            if fav:
                db.delete(fav)
                db.commit()
                await target_msg.reply_text(f"⭐ Removed *{task_title}* from Favorites.", parse_mode="Markdown")
            else:
                new_fav = UserFavorites(user_id=user_id, task_id=task_id)
                db.add(new_fav)
                db.commit()
                await target_msg.reply_text(f"⭐ Added *{task_title}* to Favorites!", parse_mode="Markdown")
        except Exception:
            tb = traceback.format_exc()
            await target_msg.reply_text(tb)

async def process_resources(target_message, chat_id: int, session_id: int):
    target_msg = get_target_message(target_message)
    if not target_msg:
        return
    with get_db() as db:
        try:
            session = db.query(StudySessions).filter(StudySessions.id == session_id).first()
            if not session or not session.task:
                await target_msg.reply_text(f"❌ Block #{session_id} task not found.")
                return
                
            task = session.task
            topic_title = task.topic.title if (task.topic and task.topic.title) else "General Study"
            subject_name = (task.topic.roadmap.title or task.topic.roadmap.category) if (task.topic and hasattr(task.topic, "roadmap") and task.topic.roadmap) else topic_title

            from app.ai.resources import recommend_resources
            from app.ai.practice import analyze_smart_practice
            import urllib.parse

            resources = recommend_resources(
                task_title=task.title,
                topic_title=topic_title,
                subject=subject_name,
                learning_objective=task.description
            )
            practice_info = analyze_smart_practice(
                task_title=task.title,
                topic_title=topic_title,
                estimated_minutes=task.estimated_minutes,
                priority=task.priority,
                energy_level=task.energy_level
            )

            lines = [
                "📚 *Learning Resources & Accessible Links*",
                f"📌 *Task:* {task.title}\n"
            ]

            inline_buttons = []

            for idx, r in enumerate(resources, 1):
                cat = r.get("category", "Resource")
                r_title = str(r.get("title", "Link")).replace("[", "(").replace("]", ")")
                r_url = str(r.get("url", "")).strip()
                r_desc = str(r.get("description", "")).replace("_", " ")

                if not r_url or not r_url.startswith("http"):
                    query = urllib.parse.quote_plus(f"{task.title} {r_title}")
                    r_url = f"https://www.google.com/search?q={query}"
                else:
                    r_url = urllib.parse.quote(r_url, safe=":/%?&=#+-_.~")

                lines.append(f"🔹 *{idx}. {cat}*")
                lines.append(f"  🔗 [{r_title}]({r_url})")
                if r_desc:
                    lines.append(f"  _{r_desc}_\n")

                btn_label = f"🔗 {idx}. {r_title[:24]}"
                inline_buttons.append([InlineKeyboardButton(btn_label, url=r_url)])

            if practice_info.is_practice_required and practice_info.platforms:
                lines.append(f"💻 *Recommended Practice Platforms ({practice_info.practice_category})*")
                for p in practice_info.platforms:
                    p_url = urllib.parse.quote(p.url.strip(), safe=":/%?&=#+-_.~") if p.url and p.url.startswith("http") else f"https://www.google.com/search?q={urllib.parse.quote_plus(p.name)}"
                    p_name = p.name.replace("[", "(").replace("]", ")")
                    lines.append(f"• [{p_name}]({p_url}) — _{p.description}_")
                    inline_buttons.append([InlineKeyboardButton(f"💻 Practice: {p_name[:22]}", url=p_url)])
                lines.append("")

            lines.append(f"⏱ *Est. Learning Time:* {practice_info.estimated_practice_duration}")
            lines.append(f"⚡ *Difficulty:* {practice_info.difficulty}")

            inline_buttons.append([InlineKeyboardButton("🔙 Back to Today's Plan", callback_data="act_plan")])

            msg = "\n".join(lines)
            await send_or_edit_message(target_msg, msg, reply_markup=InlineKeyboardMarkup(inline_buttons), is_navigational=False)
        except Exception:
            tb = traceback.format_exc()
            await target_msg.reply_text(tb)

# --- Settings & Learning History Menus ---

def build_settings_menu(db: Session, user_id: int):
    s = get_all_user_settings(db, user_id)
    mode = s.get("schedule_mode", "auto")
    start_t = s.get("custom_start_time", "18:30")
    hrs = s.get("study_hours_per_day", "6.0")
    sun_mode = s.get("sunday_mode", "roadmap_plus_revision")

    mode_label = "⚡ Automatic" if mode == "auto" else f"🕒 Custom ({start_t})"
    sun_label_map = {
        "roadmap_plus_revision": "📚 Roadmap + Revision",
        "roadmap_normal": "➡️ Continue Roadmap",
        "revision_focus": "🔄 Revision Focus",
        "practice_focus": "💻 Practice Focus",
        "project_focus": "🛠️ Project Focus",
        "custom": "⚡ Custom Sunday"
    }

    msg = (
        "⚙️ *AI-POS Automation & Study Preferences*\n\n"
        f"• 🕒 *Schedule Mode*: {mode_label}\n"
        f"• ⏰ *Custom Start Time*: `{start_t}`\n"
        f"• 📚 *Daily Study Hours*: `{hrs}h / day`\n"
        f"• 🗓️ *Sunday Strategy*: `{sun_label_map.get(sun_mode, sun_mode)}`\n"
        f"• 🤖 *AI Provider*: `{s.get('ai_provider', 'groq').upper()}`\n"
        f"• 🌍 *Time Zone*: `{s.get('timezone', 'Asia/Kolkata')}`\n\n"
        "Select a category below to configure options:"
    )

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🕒 Study Schedule Mode", callback_data="act_set_schedule_menu"),
            InlineKeyboardButton("📚 Daily Study Hours", callback_data="act_set_hours_menu")
        ],
        [
            InlineKeyboardButton("🗂 Manage Roadmaps", callback_data="act_rm_list"),
            InlineKeyboardButton("📥 Upload Curriculum", callback_data="act_upload_prompt")
        ],
        [
            InlineKeyboardButton("⚡ Auto-Schedule Today", callback_data="act_schedule"),
            InlineKeyboardButton("📊 Overall Progress", callback_data="act_stats")
        ]
    ])
    return msg, markup

def build_study_schedule_menu(db: Session, user_id: int):
    cur_mode = get_user_setting(db, user_id, "schedule_mode", "auto")
    start_time = get_user_setting(db, user_id, "custom_start_time", "18:30")
    hrs = get_user_setting(db, user_id, "study_hours_per_day", "6.0")
    sun_mode = get_user_setting(db, user_id, "sunday_mode", "roadmap_plus_revision")

    msg = (
        "🕒 *Study Schedule Configuration*\n\n"
        f"Current Mode: *{'⚡ Automatic Scheduling' if cur_mode == 'auto' else '🕒 Custom Start Time (' + start_time + ')'}*\n"
        f"Daily Study Target: *{hrs} Hours*\n"
        f"Sunday Mode: *{sun_mode}*\n\n"
        "• *Custom Study Time*: Starts your daily plan at a fixed preferred start time.\n"
        "• *Automatic Scheduling*: Smart planner auto-allocates slots based on college timetable & sleep.\n"
        "• *Sunday Mode*: Dynamic roadmap-driven Sunday planning strategy."
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Switch to Automatic", callback_data="act_set_mode_auto"),
            InlineKeyboardButton("🕒 Switch to Custom", callback_data="act_set_mode_custom")
        ],
        [
            InlineKeyboardButton("⏰ Set Start Time (18:30)", callback_data="act_set_time_1830"),
            InlineKeyboardButton("⏰ Set Start Time (06:30)", callback_data="act_set_time_0630")
        ],
        [
            InlineKeyboardButton("📚 4 Hours/Day", callback_data="act_set_hrs_4"),
            InlineKeyboardButton("📚 6 Hours/Day", callback_data="act_set_hrs_6"),
            InlineKeyboardButton("📚 8 Hours/Day", callback_data="act_set_hrs_8")
        ],
        [
            InlineKeyboardButton("🗓️ Sunday: Roadmap+Rev", callback_data="act_set_sunday_roadmap_plus_revision"),
            InlineKeyboardButton("🗓️ Sunday: Normal", callback_data="act_set_sunday_roadmap_normal")
        ],
        [
            InlineKeyboardButton("🗓️ Sunday: Revision", callback_data="act_set_sunday_revision_focus"),
            InlineKeyboardButton("🗓️ Sunday: Practice", callback_data="act_set_sunday_practice_focus")
        ],
        [InlineKeyboardButton("⬅️ Back to Settings", callback_data="act_set_main_menu")]
    ])
    return msg, markup

async def show_settings_menu(target_message, chat_id: int):
    target_msg = get_target_message(target_message)
    if not target_msg:
        return
    with get_db() as db:
        user_id = get_user_id_by_chat_id(db, chat_id) or 1
        msg, markup = build_settings_menu(db, user_id)
        await send_or_edit_message(target_message, msg, reply_markup=markup, is_navigational=True)


def build_hours_settings_menu(db: Session, user_id: int):
    hrs = get_user_setting(db, user_id, "study_hours_per_day", "6.0")
    msg = (
        "📚 *Daily Study Target Hours Configuration*\n\n"
        "Current Daily Target: *" + str(hrs) + " Hours / Day*\n\n"
        "Select your target daily study allocation below:"
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📚 2 Hours/Day", callback_data="act_set_hrs_2"),
            InlineKeyboardButton("📚 4 Hours/Day", callback_data="act_set_hrs_4"),
            InlineKeyboardButton("📚 6 Hours/Day", callback_data="act_set_hrs_6")
        ],
        [
            InlineKeyboardButton("📚 8 Hours/Day", callback_data="act_set_hrs_8"),
            InlineKeyboardButton("📚 10 Hours/Day", callback_data="act_set_hrs_10"),
            InlineKeyboardButton("📚 12 Hours/Day", callback_data="act_set_hrs_12")
        ],
        [InlineKeyboardButton("⬅️ Back to Settings", callback_data="act_set_main_menu")]
    ])
    return msg, markup

async def show_hours_settings_menu(target_message, chat_id: int):
    target_msg = get_target_message(target_message)
    if not target_msg:
        return
    with get_db() as db:
        user_id = get_user_id_by_chat_id(db, chat_id) or 1
        msg, markup = build_hours_settings_menu(db, user_id)
        await send_or_edit_message(target_message, msg, reply_markup=markup, is_navigational=True)


async def show_schedule_settings_menu(target_message, chat_id: int):
    target_msg = get_target_message(target_message)
    if not target_msg:
        return
    with get_db() as db:
        user_id = get_user_id_by_chat_id(db, chat_id) or 1
        msg, markup = build_study_schedule_menu(db, user_id)
        await send_or_edit_message(target_message, msg, reply_markup=markup, is_navigational=True)

async def show_learning_history(target_message, chat_id: int, category: str = "completed"):
    target_msg = get_target_message(target_message)
    if not target_msg:
        return
    with get_db() as db:
        try:
            user_id = get_user_id_by_chat_id(db, chat_id) or 1
            tasks_q = db.query(Tasks)
            if category == "completed":
                tasks = tasks_q.filter(Tasks.is_completed == True).all()
                title = "✅ Completed Tasks"
            elif category == "in_progress":
                tasks = tasks_q.filter(Tasks.is_completed == False, Tasks.skip_count == 0).all()
                title = "🔄 In-Progress Tasks"
            elif category == "skipped":
                tasks = tasks_q.filter(Tasks.skip_count > 0).all()
                title = "⏭ Skipped Tasks"
            else:
                tasks = tasks_q.filter(Tasks.is_completed == True).all()
                title = "📂 Learning History"

            msg = f"📂 *Learning History — {title}*\n\nFound *{len(tasks)}* tasks in this category.\n\n"
            buttons = [
                [
                    InlineKeyboardButton("✅ Completed", callback_data="act_hist_completed"),
                    InlineKeyboardButton("🔄 In Progress", callback_data="act_hist_in_progress"),
                    InlineKeyboardButton("⏭ Skipped", callback_data="act_hist_skipped")
                ]
            ]

            for t in tasks[:8]:
                st_icon = "✅" if t.is_completed else "⏳"
                buttons.append([InlineKeyboardButton(f"{st_icon} {t.title[:35]}", callback_data=f"act_hist_task_{t.id}")])

            buttons.append([InlineKeyboardButton("⬅️ Back to Settings", callback_data="act_set_main_menu")])

            await send_or_edit_message(target_message, msg, reply_markup=InlineKeyboardMarkup(buttons), is_navigational=True)
        except Exception:
            tb = traceback.format_exc()
            await send_or_edit_message(target_message, tb, is_navigational=False)

async def show_roadmaps_menu(target_message, chat_id: int):
    target_msg = get_target_message(target_message)
    if not target_msg:
        return
    with get_db() as db:
        try:
            user_id = get_user_id_by_chat_id(db, chat_id) or 1
            roadmaps = db.query(Roadmaps).filter(Roadmaps.user_id == user_id).order_by(Roadmaps.priority.asc(), Roadmaps.id.asc()).all()

            if not roadmaps:
                msg = "🗂 *Multi-Roadmap Manager*\n\nNo roadmaps found. Upload a curriculum or import a roadmap file to get started!"
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📂 Import New Roadmap", callback_data="act_upload_prompt")],
                    [InlineKeyboardButton("⬅️ Back to Settings", callback_data="act_set_main_menu")]
                ])
                await send_or_edit_message(target_message, msg, reply_markup=kb, is_navigational=True)
                return

            msg = "🗂 *Multi-Roadmap Manager*\n\n"
            buttons = []

            for rm in roadmaps:
                st = rm.status or ("active" if rm.is_active else "paused")
                st_icon = "🟢 ACTIVE" if st == "active" else ("⏸ PAUSED" if st == "paused" else "📦 ARCHIVED")
                prio = rm.priority or 1
                sched = rm.schedule_type or "daily"
                
                all_t = db.query(Tasks).join(Topics, Tasks.topic_id == Topics.id).filter(Topics.roadmap_id == rm.id).all()
                total_cnt = len(all_t)
                done_cnt = len([t for t in all_t if t.is_completed])
                pct = (done_cnt / total_cnt * 100.0) if total_cnt > 0 else 0.0

                msg += f"• *{rm.title}* [{rm.category or 'General'}]\n"
                msg += f"  Status: {st_icon} | Priority: P{prio} | Schedule: {sched}\n"
                msg += f"  Progress: {done_cnt}/{total_cnt} tasks ({pct:.1f}%)\n\n"

                row = []
                if st == "active":
                    if prio != 1:
                        row.append(InlineKeyboardButton(f"🎯 Set Primary #{rm.id}", callback_data=f"act_rm_primary_{rm.id}"))
                    row.append(InlineKeyboardButton(f"⏸ Pause #{rm.id}", callback_data=f"act_rm_pause_{rm.id}"))
                else:
                    row.append(InlineKeyboardButton(f"▶ Switch to Roadmap #{rm.id}", callback_data=f"act_rm_switch_{rm.id}"))
                row.append(InlineKeyboardButton(f"🗑 Delete #{rm.id}", callback_data=f"act_rm_delete_confirm_{rm.id}"))
                
                buttons.append(row)

            buttons.append([
                InlineKeyboardButton("📂 Import New Roadmap", callback_data="act_upload_prompt"),
                InlineKeyboardButton("🗑 Select Roadmap to Delete", callback_data="act_rm_delete_menu")
            ])
            buttons.append([
                InlineKeyboardButton("📊 Overall Stats", callback_data="act_stats"),
                InlineKeyboardButton("⬅️ Back to Settings", callback_data="act_set_main_menu")
            ])

            await send_or_edit_message(target_message, msg, reply_markup=InlineKeyboardMarkup(buttons), is_navigational=True)
        except Exception:
            tb = traceback.format_exc()
            await send_or_edit_message(target_message, tb, is_navigational=False)

async def show_delete_roadmap_selection(target_message, chat_id: int):
    target_msg = get_target_message(target_message)
    if not target_msg:
        return
    with get_db() as db:
        try:
            user_id = get_user_id_by_chat_id(db, chat_id) or 1
            roadmaps = db.query(Roadmaps).filter(Roadmaps.user_id == user_id).order_by(Roadmaps.priority.asc(), Roadmaps.id.asc()).all()

            if not roadmaps:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Roadmaps Menu", callback_data="act_rm_list")]])
                await send_or_edit_message(target_message, "🗂 No roadmaps available to delete.", reply_markup=kb, is_navigational=True)
                return

            msg = "🗑 *Select Which Roadmap to Delete:*\n\nChoose from your active roadmaps below:"
            buttons = []
            for rm in roadmaps:
                st = rm.status or ("active" if rm.is_active else "paused")
                st_icon = "🟢" if st == "active" else "⏸"
                buttons.append([
                    InlineKeyboardButton(f"🗑 {st_icon} {rm.title} (#{rm.id})", callback_data=f"act_rm_delete_confirm_{rm.id}")
                ])
            
            buttons.append([
                InlineKeyboardButton("🔙 Back to Roadmaps Menu", callback_data="act_rm_list")
            ])

            await send_or_edit_message(target_message, msg, reply_markup=InlineKeyboardMarkup(buttons), is_navigational=True)
        except Exception:
            tb = traceback.format_exc()
            await send_or_edit_message(target_message, tb, is_navigational=False)

# --- Interactive Callback & Text Router ---

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id

    target_msg = query.message if query.message else get_target_message(update)
    with get_db() as db:
        user_id = get_user_id_by_chat_id(db, chat_id) or 1
        
        try:
            if data == "act_main_menu":
                await show_main_menu(update, chat_id)
            elif data == "act_plan":
                await _send_plan(target_msg, chat_id)
            elif data == "act_schedule":
                await _send_schedule(target_msg, chat_id)
            elif data in ("act_stats", "act_summary"):
                await _send_stats(update, chat_id)
            elif data == "act_upload_prompt":
                await prompt_curriculum_upload(update, context)
            elif data == "act_rm_list":
                await show_roadmaps_menu(update, chat_id)
            elif data == "act_rm_delete_menu":
                await show_delete_roadmap_selection(update, chat_id)
            elif data == "act_set_main_menu":
                await show_settings_menu(update, chat_id)
            elif data == "act_set_schedule_menu":
                await show_schedule_settings_menu(update, chat_id)
            elif data == "act_set_hours_menu":
                await show_hours_settings_menu(update, chat_id)
            elif data == "act_set_mode_auto":
                set_user_setting(db, user_id, "schedule_mode", "auto")
                await show_schedule_settings_menu(update, chat_id)
            elif data == "act_set_mode_custom":
                set_user_setting(db, user_id, "schedule_mode", "custom")
                await show_schedule_settings_menu(update, chat_id)
            elif data == "act_set_time_1830":
                set_user_setting(db, user_id, "custom_start_time", "18:30")
                set_user_setting(db, user_id, "schedule_mode", "custom")
                await show_schedule_settings_menu(update, chat_id)
            elif data == "act_set_time_0630":
                set_user_setting(db, user_id, "custom_start_time", "06:30")
                set_user_setting(db, user_id, "schedule_mode", "custom")
                await show_schedule_settings_menu(update, chat_id)
            elif data.startswith("act_set_hrs_"):
                hrs_val = data.split("_")[-1]
                set_user_setting(db, user_id, "study_hours_per_day", str(hrs_val) + ".0")
                await show_hours_settings_menu(update, chat_id)
            elif data.startswith("act_set_sunday_"):
                sun_val = data.replace("act_set_sunday_", "")
                set_user_setting(db, user_id, "sunday_mode", sun_val)
                await show_schedule_settings_menu(update, chat_id)
            elif data.startswith("act_resources_"):
                session_id = int(data.split("_")[-1])
                await process_resources(target_msg, chat_id, session_id)
            elif data.startswith("act_complete_"):
                session_id = int(data.split("_")[-1])
                await process_completion(target_msg, chat_id, session_id)
            elif data.startswith("act_remind_"):
                session_id = int(data.split("_")[-1])
                await process_remind(target_msg, chat_id, session_id)
            elif data.startswith("act_skip_"):
                session_id = int(data.split("_")[-1])
                await process_skip(target_msg, chat_id, session_id)
            elif data.startswith("act_fav_"):
                task_id = int(data.split("_")[-1])
                await process_fav(target_msg, chat_id, task_id)
            elif data.startswith("act_hist_"):
                cat = data.replace("act_hist_", "")
                await show_learning_history(update, chat_id, cat)
            elif data.startswith("act_rm_pause_"):
                rm_id = int(data.split("_")[-1])
                rm = db.query(Roadmaps).filter(Roadmaps.id == rm_id).first()
                if rm:
                    rm.status = "paused"
                    rm.is_active = False
                    db.commit()
                await show_roadmaps_menu(update, chat_id)
            elif data.startswith("act_rm_resume_"):
                rm_id = int(data.split("_")[-1])
                rm = db.query(Roadmaps).filter(Roadmaps.id == rm_id).first()
                if rm:
                    rm.status = "active"
                    rm.is_active = True
                    db.commit()
                await show_roadmaps_menu(update, chat_id)
            elif data.startswith("act_rm_switch_"):
                rm_id = int(data.split("_")[-1])
                all_rms = db.query(Roadmaps).filter(Roadmaps.user_id == user_id).all()
                for r in all_rms:
                    if r.id == rm_id:
                        r.status = "active"
                        r.is_active = True
                        r.priority = 1
                    else:
                        r.status = "paused"
                        r.is_active = False
                        r.priority = 2
                db.commit()
                try:
                    from app.planner.service import PlannerService
                    PlannerService(db).generate_daily_plan(user_id, datetime.date.today())
                except Exception as e:
                    logger.error(f"Error regenerating plan after roadmap switch: {e}")
                await show_roadmaps_menu(update, chat_id)
            elif data.startswith("act_rm_primary_"):
                rm_id = int(data.split("_")[-1])
                all_rms = db.query(Roadmaps).filter(Roadmaps.user_id == user_id).all()
                for r in all_rms:
                    if r.id == rm_id:
                        r.status = "active"
                        r.is_active = True
                        r.priority = 1
                    elif r.priority == 1:
                        r.priority = 2
                db.commit()
                try:
                    from app.planner.service import PlannerService
                    PlannerService(db).generate_daily_plan(user_id, datetime.date.today())
                except Exception as e:
                    logger.error(f"Error regenerating plan after setting primary roadmap: {e}")
                await show_roadmaps_menu(update, chat_id)
            elif data.startswith("act_rm_delete_confirm_"):
                rm_id = int(data.split("_")[-1])
                rm = db.query(Roadmaps).filter(Roadmaps.id == rm_id).first()
                if not rm:
                    await send_or_edit_message(update, f"❌ Roadmap #{rm_id} not found.", is_navigational=False)
                else:
                    confirm_kb = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(f"✅ Yes, Delete '{rm.title}'", callback_data=f"act_rm_delete_do_{rm_id}"),
                            InlineKeyboardButton("❌ Cancel", callback_data="act_rm_list")
                        ]
                    ])
                    await send_or_edit_message(
                        update,
                        f"⚠️ *Are you sure you want to permanently delete*\n"
                        f"*\"{rm.title}\"* (#{rm_id})?\n\n"
                        f"This action cannot be undone.",
                        reply_markup=confirm_kb,
                        is_navigational=True
                    )
            elif data.startswith("act_rm_delete_do_"):
                rm_id = int(data.split("_")[-1])
                rm = db.query(Roadmaps).filter(Roadmaps.id == rm_id).first()
                if rm:
                    title = rm.title
                    db.delete(rm)
                    db.commit()
                    await send_or_edit_message(update, f"🗑 *Roadmap \"{title}\" (#{rm_id}) has been permanently deleted.*", is_navigational=False)
                await show_roadmaps_menu(update, chat_id)
        except Exception:
            tb = traceback.format_exc()
            if target_msg:
                await target_msg.reply_text(tb)

async def handle_keyboard_text_or_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = get_target_message(update)
    text = (target_msg.text or "").strip() if target_msg and hasattr(target_msg, "text") and target_msg.text else ""
    chat_id = update.effective_chat.id if update.effective_chat else 1
    
    if text.startswith("/"):
        return

    clean_text = text.lower().replace("'", "").replace("’", "").strip()

    # Check persistent reply keyboard buttons and natural text commands
    if any(k in clean_text for k in ["upload curriculum", "upload syllabus", "upload"]):
        await prompt_curriculum_upload(target_msg, context)
        return
    elif "roadmap" in clean_text:
        await show_roadmaps_menu(target_msg, chat_id)
        return
    elif any(k in clean_text for k in ["todays plan", "today plan", "todays schedule", "today schedule", "schedule", "plan"]):
        await _send_plan(target_msg, chat_id)
        return
    elif "pending" in clean_text:
        await pending(update, context)
        return
    elif any(k in clean_text for k in ["auto-schedule", "auto schedule", "autoschedule", "re-schedule", "reschedule"]):
        await _send_schedule(target_msg, chat_id)
        return
    elif any(k in clean_text for k in ["stat", "progress", "summary", "analytic"]):
        await _send_stats(target_msg, chat_id)
        return
    elif "history" in clean_text:
        await show_learning_history(target_msg, chat_id, "completed")
        return
    elif any(k in clean_text for k in ["setting", "config", "preference"]):
        await show_settings_menu(target_msg, chat_id)
        return
    elif any(k in clean_text for k in ["help", "guide", "menu"]):
        await help_command(update, context)
        return

    # Document upload or raw curriculum text parsing
    if update.message and update.message.document:
        doc = update.message.document
        file_bytes = await doc.get_file()
        content = await file_bytes.download_as_bytearray()
        text_content = content.decode("utf-8", errors="ignore")
        filename = doc.file_name or "curriculum.txt"
    elif text and len(text) > 30 and any(k in clean_text for k in ["syllabus", "curriculum", "week", "month", "module", "topic"]):
        text_content = text
        filename = "pasted_syllabus.txt"
    else:
        if target_msg:
            await target_msg.reply_text(
                "⚠️ I didn't recognize that option.\n\n"
                "Please use the navigation menu buttons below or send a syllabus file to generate a roadmap.",
                reply_markup=get_main_reply_keyboard()
            )
        return

    await target_msg.reply_text("⏳ *Parsing curriculum and generating roadmap...*", parse_mode="Markdown")
    try:
        with get_db() as db:
            user_id = get_user_id_by_chat_id(db, chat_id) or 1
            
            import_engine = ImportEngine(db)
            roadmap = import_engine.import_curriculum(
                user_id=user_id,
                content=text_content,
                file_type="markdown",
                filename=filename
            )
            
            planner = PlannerService(db)
            today_date = datetime.date.today()
            planner.generate_daily_plan(user_id, today_date)
            
            # Check for existing roadmaps that were paused
            paused_rms = db.query(Roadmaps).filter(
                Roadmaps.user_id == user_id,
                Roadmaps.id != roadmap.id,
                Roadmaps.status == "paused"
            ).all()
            
            pause_notice = ""
            if paused_rms:
                paused_titles = ", ".join(f"\"{r.title}\"" for r in paused_rms[:3])
                pause_notice = (
                    f"⏸️ *Previous roadmap(s) paused:* {paused_titles}\n"
                    f"🎯 *Current Active Focus:* \"{roadmap.title}\"\n"
                    f"_(You can resume or switch roadmaps anytime in 🗂 Roadmaps menu)_\n\n"
                )

            msg, markup = build_plan_message_and_markup(db, user_id, today_date)
            
            # Ensure "🗂 Manage Roadmaps" button is available in inline keyboard
            if markup and hasattr(markup, "inline_keyboard"):
                kb_rows = list(markup.inline_keyboard)
                kb_rows.append([InlineKeyboardButton("🗂 Manage / Switch Roadmaps", callback_data="act_rm_list")])
                markup = InlineKeyboardMarkup(kb_rows)

            response_text = (
                f"🎉 *Roadmap Created Successfully!*\n\n"
                f"📌 *Roadmap Title:* {roadmap.title}\n"
                + pause_notice +
                f"📅 *Generated Daily Plan for {today_date}:*\n\n"
                + msg
            )
            await target_msg.reply_text(response_text, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Error importing syllabus: {tb}")
        await target_msg.reply_text(f"❌ *Failed to parse syllabus.*\n\n```python\n{tb}\n```", parse_mode="Markdown")

async def prompt_curriculum_upload(target_message, context: ContextTypes.DEFAULT_TYPE):
    target_msg = get_target_message(target_message)
    if target_msg:
        await target_msg.reply_text(
            "📥 *Upload Curriculum or Syllabus*\n\n"
            "Please send your syllabus text directly in chat or upload a `.txt` / `.md` file.",
            parse_mode="Markdown"
        )

bot_app = None

def start_bot_background():
    """Starts Telegram Bot polling in a background thread for FastAPI lifespan integration."""
    token = os.environ.get("TELEGRAM_TEST_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or settings.TELEGRAM_BOT_TOKEN
    if not token or token == "mock_telegram_token_for_dev":
        logger.warning("Telegram bot token not provided or set to mock; skipping background bot polling.")
        return None
    
    import threading
    bot_thread = threading.Thread(target=main, daemon=True)
    bot_thread.start()
    logger.info("Telegram Bot background thread initiated.")
    return bot_thread

async def post_init_callback(application: Application):
    try:
        from app.telegram.scheduler import start_scheduler
        start_scheduler()
        logger.info("Background notification scheduler started in post_init.")
    except Exception as se:
        logger.warning(f"Could not start background notification scheduler: {se}")

def main():
    global bot_app
    token = os.environ.get("TELEGRAM_TEST_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or settings.TELEGRAM_BOT_TOKEN
    if not token or token == "mock_telegram_token_for_dev":
        logger.error("TELEGRAM_BOT_TOKEN is not set or invalid. Exiting bot.")
        sys.exit(1)

    app = ApplicationBuilder().token(token).post_init(post_init_callback).build()
    bot_app = app
    
    app.add_error_handler(global_error_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("plan", plan))
    app.add_handler(CommandHandler("schedule", schedule))
    app.add_handler(CommandHandler("pending", pending))
    app.add_handler(CommandHandler("complete", complete))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("roadmaps", lambda u, c: show_roadmaps_menu(u, u.effective_chat.id if u.effective_chat else 1)))
    app.add_handler(CommandHandler("settings", lambda u, c: show_settings_menu(u, u.effective_chat.id if u.effective_chat else 1)))

    app.add_handler(CallbackQueryHandler(handle_callback_query))

    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_keyboard_text_or_upload))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_keyboard_text_or_upload))

    start_health_check_server()

    logger.info("Starting AI-POS Telegram Bot Polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
