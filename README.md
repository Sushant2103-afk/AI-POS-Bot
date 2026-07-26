# AI Companion System (AI-POS)

A production-ready AI Personal Operating System & Companion platform built with **FastAPI**, **Streamlit**, **SQLAlchemy**, **Pydantic v2**, and multi-provider AI integration (Groq, OpenAI, Anthropic, Gemini, Mock).

---

## 🌟 Key Features

- **FastAPI REST Backend**: Comprehensive API endpoints for users, dynamic scheduling, spaced repetition, energy tracking, data import/export, and plugin management.
- **Streamlit Web Dashboard**: Interactive multi-tab UI for setting up goals, daily schedule optimization, mock interview practice, progress analytics, and export options.
- **Telegram Bot Integration**: Conversational interface for daily study check-ins, flashcard reviews, energy logging, and quick task entry.
- **Multi-Provider AI Service**: Unified AI router supporting Groq (llama-3.3-70b-versatile), OpenAI, Anthropic, Gemini, with automatic fallback and prompt-caching.
- **Export & Import Engine**: Multi-format data export (PDF, Markdown, CSV, JSON) and calendar/task import parsing.
- **Plugin Architecture**: Modular placement coach and skill plugins that seamlessly integrate into the main engine.
- **Docker Support**: Containerized setup via Dockerfile and docker-compose.yml.

---

## 📁 Directory Structure

`
AI_Companion/
├── app/
│   ├── ai/               # AI provider routers, cache layer, service handlers
│   ├── api/              # FastAPI routers, endpoints, schemas, dependencies
│   ├── core/             # Application config, logging system, plugin core loader
│   ├── database/         # DB session, base models, metadata
│   ├── exports/          # Export engine (PDF, Markdown, CSV, JSON)
│   ├── frontend/         # Streamlit frontend views, main launcher, custom CSS
│   ├── imports/          # Import parser and engine
│   ├── models/           # SQLAlchemy ORM models (core, roadmap, user)
│   ├── planner/          # Energy scheduler, time allocator, spaced repetition
│   ├── plugins/          # Extension plugins (e.g., placement_coach)
│   ├── telegram/         # Telegram bot & notification scheduler
│   └── main.py           # FastAPI application entry point
├── configs/              # System configuration files
├── docs/                 # Documentation & API references
├── logs/                 # System log files
├── roadmaps/             # Skill roadmaps & curricula templates
├── scripts/              # Helper utility scripts
├── tests/                # Comprehensive Pytest test suite (24 tests)
├── .env.example          # Environment variables template
├── Dockerfile            # Container configuration
├── docker-compose.yml    # Multi-service docker orchestrator
└── requirements.txt      # Python dependencies
`

---

## 🚀 Quick Start Guide

### 1. Installation

`ash
# Navigate to the folder
cd AI_Companion

# Create a virtual environment
python -m venv venv
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
`

### 2. Environment Configuration

Copy .env.example to .env and fill in your API credentials:

`ash
cp .env.example .env
`

### 3. Run FastAPI Backend

`ash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
`
- API Docs: http://localhost:8000/docs

### 4. Run Streamlit Frontend Dashboard

`ash
streamlit run app/frontend/main.py
`
- UI Dashboard: http://localhost:8501

### 5. Run Telegram Bot

`ash
python -m app.telegram.bot
`

---

## 🧪 Running Tests

Execute the complete test suite with 100% pass rate:

`ash
pytest
`

---

## 🐳 Running with Docker

`ash
docker-compose up --build
`
