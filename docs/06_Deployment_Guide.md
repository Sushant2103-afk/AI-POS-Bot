# AI-POS Production Deployment & Operations Guide

This guide describes how to configure, run, test, and containerize the **AI Personal Operating System (AI-POS)** in local, staging, and production environments.

---

## 1. System Architecture Recap

AI-POS is composed of two primary interface boundaries connected via a shared SQLite database:
1. **Core Engine & Backend Router (FastAPI)**:
   - Exposes RESTful CRUD services for settings, events, import tasks, planner outputs, and completions.
   - Runs background thread loops for the **Telegram bot listener** and the **recurring notifications scheduler** (APScheduler).
2. **Dashboard Portal (Streamlit)**:
   - A highly custom dark-themed UI for configuring profiles, managing commit timetables, visualizing metrics, and running interactive mock technical interviews.

---

## 2. Configuration Settings

### Environment Variables (`.env`)
Create a `.env` file in the root directory:
```bash
# Core Environment Settings
ENV=production
SECRET_KEY=generate-a-strong-random-key-here
DATABASE_URL=sqlite:///./ai_pos.db

# LLM Providers API Keys (Optional - mock mode is used if empty)
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIzaSy...
OPENAI_API_KEY=sk-proj-...
CLAUDE_API_KEY=sk-ant-...

# Telegram Bot configurations (Optional)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstUV
TELEGRAM_CHAT_ID=987654321
```

### Static Configurations (`configs/settings.yaml`)
Define default user profiles, planner bounds, and AI parameters:
```yaml
user_profile:
  name: "Placement Candidate"
  wake_up_time: "07:00"
  sleep_time: "23:00"
  preferred_study_hours: 6
  break_duration_minutes: 15

scheduler:
  buffer_ratio: 0.15 # Reserve 15% of free slots for catch-up
  sunday_mode:
    prioritize_mock_test: true
    prioritize_revision: true
    prioritize_mock_interview: true

revision:
  strategy: [1, 3, 7, 15, 30] # Day intervals for Spaced Repetition

ai:
  provider: "groq"
  model: "llama3-8b-8192"
  temperature: 0.2
```

---

## 3. Local Development Deployment

### Prerequisites
- Python 3.11 or Python 3.12 (specifically tested on Windows and Unix).
- Virtual environment tool.

### Setup Steps
1. **Clone & Virtualenv Setup**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. **Seed & Migrate Database**:
   ```bash
   python scripts/init_db.py
   ```
3. **Launch Backend Server**:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
4. **Launch Streamlit Dashboard**:
   ```bash
   streamlit run app/frontend/main.py --server.port 8501
   ```

---

## 4. Containerized Docker Deployment (Recommended)

Packaging the services as separate Docker runtimes ensures isolation.

### Commands to Run
Build and start the container bundle in detached daemon mode:
```bash
docker-compose up --build -d
```

### Verify Status
```bash
docker-compose ps
docker-compose logs -f
```

### Volume Persistence
Docker-compose automatically maps volumes to ensure SQLite database data is persisted:
- `aipos-db-volume`: Maps to `/app/data` (stores `ai_pos.db`).
- `aipos-roadmaps-volume`: Maps to `/app/roadmaps` (stores uploaded syllabus documents).

---

## 5. Telegram Notification Bot Setup

1. Message **@BotFather** on Telegram.
2. Send `/newbot`, choose a display name and username.
3. Retrieve your **HTTP API Token**.
4. Retrieve your user account chat ID using **@userinfobot**.
5. Save these into `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` inside your `.env` configuration.
6. The background executor in FastAPI will automatically boot up the bot listener and trigger daily schedule broadcasts at 08:00 AM.

---

## 6. Testing

Run backend integrations and pipeline test cases:
```bash
pytest tests/
```
The automated CI/CD pipeline configured inside `.github/workflows/ci.yml` runs these tests on every repository push and merge request.
