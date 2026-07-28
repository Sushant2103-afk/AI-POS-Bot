import os
import sys
import asyncio

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set default local test database if not explicitly set
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///./ai_pos_dev.db"

from app.core.config import settings
from app.database.session import engine
from app.database.base import Base
from scripts.init_db import init_db

async def verify_bot_token(token: str):
    """Verifies Telegram bot token and returns bot details."""
    from telegram import Bot
    try:
        bot = Bot(token=token)
        me = await bot.get_me()
        return me
    except Exception as e:
        return None

# Configure UTF-8 encoding for standard output on Windows shells
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def main():
    print("=" * 65)
    print(" [TEST] AI-POS LOCAL TEST BOT INITIALIZER")
    print("=" * 65)

    # 1. Initialize local test database tables
    db_url = os.environ.get("DATABASE_URL", "sqlite:///./ai_pos_dev.db")
    print(f"[*] Test Database: {db_url}")
    print("[*] Initializing test database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        init_db()
    except Exception as e:
        print(f"[*] Database initialization notice: {e}")

    # 2. Check Telegram Bot Token
    token = settings.TELEGRAM_BOT_TOKEN or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token or token.strip() == "":
        print("\n[ERROR] TELEGRAM_BOT_TOKEN is missing in your .env file!")
        print("How to fix:")
        print("   1. Open Telegram and search for @BotFather")
        print("   2. Send /newbot to create your Test Bot (e.g. MyAIPosTestBot)")
        print("   3. Copy the HTTP API token provided by BotFather")
        print("   4. Paste it into your .env file: TELEGRAM_BOT_TOKEN=your_token_here")
        print("   5. Re-run: python scripts/run_test_bot.py\n")
        sys.exit(1)

    # 3. Verify Bot with Telegram API
    bot_info = asyncio.run(verify_bot_token(token))
    
    if bot_info:
        bot_username = f"@{bot_info.username}"
        bot_name = bot_info.first_name
    else:
        bot_username = "Unknown"
        bot_name = "Test Bot"

    print("\n" + "=" * 65)
    print(f" [ONLINE] LOCAL TEST BOT IS NOW ONLINE: {bot_name} ({bot_username})")
    print("=" * 65)
    print(f" Bot Handle     : {bot_username}")
    print(f" Local Database : {db_url}")
    print(f" Environment    : {settings.ENV} (Local Testing)")
    print("-----------------------------------------------------------------")
    print(" Open Telegram and chat with your test bot to verify new features.")
    print(" Press Ctrl + C in this terminal to stop the local test bot.")
    print("=" * 65 + "\n")


    # 4. Import and run main Telegram bot application
    from app.telegram.bot import main as run_bot
    run_bot()

if __name__ == "__main__":
    main()
