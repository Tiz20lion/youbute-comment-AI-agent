"""
Logging configuration for YouTube Comment Automation Bot
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

import structlog
from pythonjsonlogger import jsonlogger

from app.config import settings


def setup_logging(log_level: Optional[str] = None) -> None:
    """
    Setup structured logging configuration
    
    Args:
        log_level: Override default log level
    """
    # Use provided log level or default from settings
    level = log_level or settings.LOG_LEVEL
    
    # Create logs directory if it doesn't exist
    log_dir = Path(settings.LOGS_DIRECTORY)
    log_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    logging.root.handlers = []
    logging.root.setLevel(getattr(logging, level.upper()))
    
    # Create formatters
    if settings.LOG_FORMAT.lower() == "json":
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, level.upper()))
    
    # File handler with daily rotation
    if settings.LOG_FILE:
        # Create daily log file with date in filename
        log_path = Path(settings.LOG_FILE)
        log_dir = log_path.parent
        log_name = log_path.stem
        log_extension = log_path.suffix
        
        # Generate today's log filename: app_2024-01-15.log
        today = datetime.now().strftime("%Y-%m-%d")
        daily_log_file = log_dir / f"{log_name}_{today}{log_extension}"
        
        # Use TimedRotatingFileHandler for daily rotation
        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=str(daily_log_file),
            when='midnight',
            interval=1,
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding="utf-8",
            utc=False
        )
        
        # Set the suffix for rotated files to include date
        file_handler.suffix = "%Y-%m-%d"
        
        file_handler.setFormatter(formatter)
        file_handler.setLevel(getattr(logging, level.upper()))
        logging.root.addHandler(file_handler)
    
    logging.root.addHandler(console_handler)
    
    # Configure structlog to use the standard logging system
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )
    
    # Set specific loggers to appropriate levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def _parse_size(size_str: str) -> int:
    """
    Parse size string (e.g., '10MB') to bytes
    
    Args:
        size_str: Size string like '10MB', '1GB', etc.
        
    Returns:
        Size in bytes
    """
    size_str = size_str.upper()
    
    if size_str.endswith('KB'):
        return int(size_str[:-2]) * 1024
    elif size_str.endswith('MB'):
        return int(size_str[:-2]) * 1024 * 1024
    elif size_str.endswith('GB'):
        return int(size_str[:-2]) * 1024 * 1024 * 1024
    else:
        return int(size_str)


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger instance
    
    Args:
        name: Logger name
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name) 