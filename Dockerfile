FROM python:3.11-slim

# Set environment paths and behaviors
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /app

# Install system dependencies for package builds, SQLite, and document processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmagic1 \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python package dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application source directories
COPY app/ ./app/
COPY configs/ ./configs/
COPY scripts/ ./scripts/
COPY imports/ ./imports/
COPY exports/ ./exports/

# Create roadmaps directory for curricular file stores
RUN mkdir -p roadmaps

# Expose ports for FastAPI (8000) and Streamlit Dashboard (8501)
EXPOSE 8000 8501

# Default entry point (can be overridden by docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
