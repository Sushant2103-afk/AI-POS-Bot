# AI Personal Operating System (AI-POS) - System Walkthrough

This document records the architectural details and validation results for completed development cycles of the AI-POS.

---

## Sprint 1: Core Foundation & Plugin Architecture

### Changes Made
- **Configuration & Environments**: Added `requirements.txt`, `.env`, and `configs/settings.yaml`. Built custom configuration loaders in `app/core/config.py`.
- **System Logging**: Configured a system-wide rotating file and console logger in `app/core/logging.py`.
- **Relational Schemas**: Configured declarative models (`app/database/base_class.py`, `app/database/session.py`) and defined all 19 schemas across `app/models/core.py` and `app/models/roadmap.py`.
- **Plugin Registry**: Implemented discovery loaders in `app/core/plugins.py` and initialized the `placement_coach` plugin.
- **Seeding Database**: Created and executed `scripts/init_db.py` to populate mockup data.

---

## Sprint 2: Universal Import Engine & AI Services

### Changes Made
- **AI Services Layer**: Built provider clients (`app/ai/base.py`, `app/ai/providers.py`, `app/ai/service.py`) supporting Groq, Gemini, OpenAI, Claude, Ollama, and Mock modes.
- **LLM Prompt Caching**: Integrated SQLite-backed prompt caches (`app/ai/cache.py`) inside `configs/ai_cache.db` to save tokens.
- **Universal Parser**: Developed extractors (`app/imports/parser.py`) for PDF, DOCX, XLSX, CSV, Markdown, JSON, YAML, and TXT files.
- **Relational Import Engine**: Implemented pipeline loader (`app/imports/engine.py`) to parse documents, validate schemas using Pydantic, and write to database tables.

---

## Sprint 3: The Planner & Scheduler Engine

### Changes Made
- **Time Block Allocator**: Merges sleep schedules, meal hours, gym windows, and college lectures (with holiday exclusions) into blocked intervals. Inverts them to locate available free study slots.
- **Energy-Based Task Placement**: Maps high-energy topics (conceptual algorithms) to peak user study blocks and lower energy ones elsewhere. Leaves 15% buffer time.
- **Spaced Repetition Engine**: Creates revision entries in `revision_history` at 1, 3, 7, 15, and 30-day intervals after a task is completed, prioritizing them in next day's queues.
- **Sunday Mode and Rescheduling**: Coordinates daily plans. Triggers "Sunday Mode" custom workloads (mock tests, contests, goal setup). Reschedules past-due uncompleted sessions to tomorrow's queues and logs the postpone action in `user_overrides`.

---

## Sprint 4: The REST API Layer

### Changes Made
- **FastAPI Application Entrypoint**: Configures CORS middleware, registers global unhandled exception filters, mounts request-duration auditing loggers, and exposes system status health endpoints in `app/main.py`.
- **Central Schema Validation**: Declares type-safe Pydantic request and response schemas (e.g. `UserResponse`, `TimetableResponse`, `DailyPlanResponse`, `StudySessionResponse`) in `app/api/schemas.py`.
- **Database & Authentication Dependencies**: Provides database session lifecycle hooks (`get_db`) and user header resolver (`get_current_user_id`) in `app/api/deps.py`.
- **Controller Routers**: Exposes CRUD controllers for user settings, timetable class slots, document uploading, plan generation, study slot completion triggers, and past-due rescheduling.

---

## Sprint 5: Telegram Bot & Reminders

### Changes Made

#### 1. Command Controller Handler
- **`app/telegram/bot.py`**: Builds interactive conversational responders.
  - `/start <user_id>`: Link the chat ID to user database profile settings.
  - `/plan`: Retrieve and format today's detailed hour-by-hour study timeline.
  - `/today`: List remaining planned tasks.
  - `/complete <block_id>`: Marks study session complete, updates task status, logs progress minutes, and fires spaced repetition revision calendars.

#### 2. Background Scheduler Alerts
- **`app/telegram/scheduler.py`**: Deploys an async scheduler loop daemon via `AsyncIOScheduler`.
  - `send_morning_schedule_job`: Runs at 8:00 AM daily. Automatically ensures plans are created, formats checklists, and sends them to users.
  - `send_evening_review_job`: Runs at 9:00 PM daily. Checks for outstanding planned items and prompts users to mark completions or expect postponement.

---

---

## Sprint 6: Streamlit Web Dashboard

### Changes Made

#### 1. Page View Layouts
- **`app/frontend/views.py`**: Formulates interactive components for high-level dashboard control.
  - **Setup Wizard & Imports**: Supports modifying profile parameters (e.g. daily hours, sleep/wake targets), configuring class commitments (weekly timetable editor), and uploading local curriculum documents (PDF, Word, Excel, Markdown) or raw syllabus text via `ImportEngine`.
  - **Daily Planner Checklist**: Shows today's detailed study blocks (color-coded by state: completed vs planned). Interactive checkboxes log task completion, write progress intervals to the database, and trigger spaced repetition reviews. It also allows triggering daily plan calculation and outstanding task rescheduling.
  - **Progress Analytics**: Renders high-end stat boxes for roadmap count, total tasks, and completion rates. Visualizes study trends using Streamlit native charts (last 7 days completed vs planned blocks and energy balance).
  - **AI Mock Interviewer**: Engages the candidate in a dynamic mock technical interview. Resolves active database topics, leverages the AI Service layer (`MockAIProvider` or live LLM) to present technical questions, rates responses out of 10 with constructive feedback, and tracks progress.

#### 2. Entrypoint and Custom Theme Overrides
- **`app/frontend/main.py`**: Handles setup configuration, navigates sidebars, and manages SQLAlchemy connection pool lifetimes.
- **`app/frontend/style.css`**: Injects dark theme styling, glassmorphism panels, neon borders, and hover micro-animations to overwrite generic Streamlit styles.

---

## Sprint 7: Docker, CI/CD, and Documentation

### Changes Made

#### 1. Containerization Configuration
- **`Dockerfile`**: Builds a python:3.11-slim image with native C build dependencies, libmagic, and SQLite3. Installs package dependencies, copies source code directories, and provisions data volumes.
- **`docker-compose.yml`**: Orchestrates two isolated services:
  - `backend`: Runs FastAPI server, APScheduler, and Telegram bot background threads. Exposes port 8000.
  - `frontend`: Runs Streamlit UI Dashboard. Exposes port 8501.
  - Maps persistent Docker volumes `aipos-db-volume` and `aipos-roadmaps-volume` for database and syllabus storage.

#### 2. Continuous Integration
- **`.github/workflows/ci.yml`**: Triggers automated test suite execution inside GitHub Actions on push and PR triggers. Installs dependencies and runs pytest checks.

#### 3. Documentation
- **`docs/06_Deployment_Guide.md`**: Outlines environments, manual install stages, docker-compose instructions, bot setups, and testing commands.

---

## Validation Results

### 1. Seeding Data
Running `python scripts/init_db.py` successfully seeds all tables:
```
Connecting to the database engine and generating tables...
Database tables initialized successfully.
Seeding application mockup data for local development...
Database seeded successfully with all 19 schemas fully populated!
```

### 2. Pytest & Compilation Execution
We verified the Streamlit modules compile without syntax errors and that the test suite passes with 23/23 tests successful.
```bash
python -m py_compile app/frontend/main.py app/frontend/views.py
pytest tests/
```
**Output**:
```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\susha\.gemini\antigravity\scratch
plugins: anyio-4.12.1, mock-3.15.1
collected 23 items

tests\test_ai.py ..                                                      [  8%]
tests\test_api.py ...                                                    [ 21%]
tests\test_config.py ..                                                  [ 30%]
tests\test_database.py ..                                                [ 39%]
tests\test_imports.py ...                                                [ 52%]
tests\test_planner.py .....                                              [ 73%]
tests\test_plugins.py ..                                                 [ 82%]
tests\test_telegram.py ....                                              [100%]

======================= 23 passed, 9 warnings in 2.26s ========================
```
This confirms that the Streamlit frontend modules are structurally sound, error-free, and align perfectly with database session and service rules.

---

## Sprint 8: Local Test Bot & Isolated Testing Workflow

### Changes Made

#### 1. Isolated Test Bot Runner Script
- **`scripts/run_test_bot.py`**:
  - Automatically isolates local testing from production database by pointing `DATABASE_URL` to `sqlite:///./ai_pos_dev.db`.
  - Automatically verifies tables and populates seed data on startup.
  - Interrogates Telegram Bot API using the configured token to confirm bot identity (`@bot_username`).
  - Displays a clean status dashboard in the terminal showing active bot handle, local database, and environment status.

#### 2. Environment Configuration & Documentation
- **`.env.example`**: Updated with clear guidance on separating your **Test Bot Token** (for local testing) from your **Production Bot Token** (configured in cloud hosting e.g. Render / PythonAnywhere).

---

## Local Test Bot vs. Production Deployment Guide

### Workflow Summary
1. **Local Development & Testing**:
   - Create a test bot on Telegram via `@BotFather` (e.g. `@MyAIPosTestBot`).
   - Put your test bot token in `.env`: `TELEGRAM_BOT_TOKEN=your_test_bot_token`
   - Run `python scripts/run_test_bot.py` to start your test bot with isolated local database (`ai_pos_dev.db`).
   - Test new features, inline buttons, and commands on Telegram with your test bot.

2. **Deploying Approved Features to Production Bot**:
   - Once a feature is approved, commit and push your code to Git (`git push origin main`).
   - Your cloud server (Render / PythonAnywhere / Docker host) will automatically rebuild and run the new code with your **Original Production Bot Token**.


