import datetime
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database.session import SessionLocal
from app.models.core import Settings
from app.models.roadmap import DailyPlans
from app.planner.service import PlannerService
from app.telegram.bot import bot_app, format_daily_plan_message
from app.core.logging import logger

scheduler = AsyncIOScheduler()

async def send_telegram_message(chat_id: str, text: str):
    """
    Sends a message via Telegram. Falls back to logging if the bot is in mock mode.
    """
    if bot_app and bot_app.bot:
        try:
            await bot_app.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
            logger.info(f"Notification sent successfully to chat ID {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send Telegram message to chat ID {chat_id}: {e}")
    else:
        logger.info(f"📢 [Mock Telegram Alert to Chat {chat_id}]:\n{text}")

async def send_morning_schedule_job():
    """
    Morning study plan notification job.
    Runs daily to generate and send the user's study checklist.
    """
    logger.info("Triggering morning schedule notification job...")
    db = SessionLocal()
    try:
        # Find all users with Telegram chat IDs mapped
        mappings = db.query(Settings).filter(Settings.key == "telegram_chat_id").all()
        today = datetime.date.today()
        
        for m in mappings:
            user_id = m.user_id
            chat_id = m.value
            
            # Ensure today's plan is generated (auto-generation)
            try:
                planner_service = PlannerService(db)
                planner_service.generate_daily_plan(user_id, today)
            except Exception as pe:
                logger.warning(f"Could not auto-generate plan for user {user_id}: {pe}")
                
            msg = format_daily_plan_message(db, user_id, today)
            # Prefix with morning greeting
            prefix = "☀️ *Good Morning! Here is your study checklist for today:*\n\n"
            await send_telegram_message(chat_id, prefix + msg)
            
    except Exception as e:
        logger.error(f"Error in send_morning_schedule_job: {e}")
    finally:
        db.close()

async def send_evening_review_job():
    """
    Evening wrap-up job.
    Prompts users to finish remaining tasks before rescheduling runs tomorrow.
    """
    logger.info("Triggering evening review notification job...")
    db = SessionLocal()
    try:
        mappings = db.query(Settings).filter(Settings.key == "telegram_chat_id").all()
        today = datetime.date.today()
        
        for m in mappings:
            user_id = m.user_id
            chat_id = m.value
            
            plan = db.query(DailyPlans).filter(
                DailyPlans.user_id == user_id,
                DailyPlans.date == today
            ).first()
            
            if not plan or not plan.study_sessions:
                continue
                
            pending = [s for s in plan.study_sessions if s.status == "planned"]
            if pending:
                msg = f"🌙 *Evening Review Reminder*\n\nYou have *{len(pending)}* study block(s) left planned for today:\n"
                for s in pending:
                    msg += f"• {s.start_time} - {s.end_time}: {s.task.title}\n"
                msg += "\nComplete them tonight by running `/complete <block_id>` to avoid them being postponed!"
                await send_telegram_message(chat_id, msg)
            else:
                await send_telegram_message(
                    chat_id, 
                    "⭐️ *Great Job!* You've completed all study slots scheduled for today! Keep it up! 🎉"
                )
    except Exception as e:
        logger.error(f"Error in send_evening_review_job: {e}")
    finally:
        db.close()

def start_scheduler():
    """
    Configure and run the background APScheduler jobs.
    Note: Standard times are set to 08:00 and 21:00.
    """
    if not scheduler.running:
        # Schedule morning job at 08:00 daily
        scheduler.add_job(
            send_morning_schedule_job,
            "cron",
            hour=8,
            minute=0,
            id="morning_schedule_job",
            replace_existing=True
        )
        
        # Schedule evening job at 21:00 daily
        scheduler.add_job(
            send_evening_review_job,
            "cron",
            hour=21,
            minute=0,
            id="evening_review_job",
            replace_existing=True
        )
        
        scheduler.start()
        logger.info("Background notification scheduler started.")
