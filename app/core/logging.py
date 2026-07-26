import sys
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging(env: str = "development") -> logging.Logger:
    logger = logging.getLogger("ai_pos")
    
    # Set logging level depending on environment
    if env == "development":
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    # Prevent handler duplication if setup is rerun
    if logger.handlers:
        return logger

    # Format config
    log_format = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s.%(filename)s:%(lineno)d] - %(message)s"
    )

    # Console output handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    # Resolve logs directory path inside workspace
    workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    logs_dir = os.path.join(workspace_dir, "logs")
    try:
        os.makedirs(logs_dir, exist_ok=True)
        # File handler with rotation (10 MB per file, max 5 backup copies)
        log_file = os.path.join(logs_dir, "app.log")
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)
    except Exception:
        # Fallback if logging to directory is restricted
        pass

    return logger

# Pre-initialize using global configuration settings
from app.core.config import settings
logger = setup_logging(settings.ENV)
