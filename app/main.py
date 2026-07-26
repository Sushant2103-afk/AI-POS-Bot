import time
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import users, imports, planner, exports, roadmaps
from app.core.logging import logger

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start Telegram bot background listener and scheduler
    from app.telegram.bot import start_bot_background
    from app.telegram.scheduler import start_scheduler
    
    start_bot_background()
    start_scheduler()
    logger.info("Application Lifespan: Background bot services and scheduler started.")
    
    yield
    
    # Shutdown: Stop notification scheduler
    from app.telegram.scheduler import scheduler
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Application Lifespan: Scheduler stopped.")

app = FastAPI(
    title="AI Personal Operating System (AI-POS) API",
    description="Backend REST engine for SDE curriculum imports and time-block scheduling.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom exception handler for standard unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled system exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal system error occurred. Please review application logs."}
    )

# Request/Response auditing middleware
@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    start_time = time.time()
    path = request.url.path
    method = request.method
    
    logger.info(f"Incoming Request: {method} {path}")
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    logger.info(f"Completed Request: {method} {path} - Status: {response.status_code} - Duration: {duration:.4f}s")
    
    return response

# Root status check endpoint
@app.get("/")
def read_root():
    """System health check and module descriptor."""
    return {
        "status": "online",
        "system": "AI-POS",
        "active_modules": ["Placement Coach", "Universal Import Engine", "Energy Scheduler"]
    }

# Include routing structures
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(imports.router, prefix="/api/imports", tags=["Imports"])
app.include_router(roadmaps.router, prefix="/api/roadmaps", tags=["Roadmaps"])
app.include_router(planner.router, prefix="/api/planner", tags=["Planner"])
app.include_router(exports.router, prefix="/api/exports", tags=["Exports"])
