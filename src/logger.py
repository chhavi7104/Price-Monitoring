"""
logger.py
---------
Application-wide logger factory. Logs go both to the console (INFO+) and to
a rotating log file under LOGS_DIR (DEBUG+), so a long-running / scheduled
run doesn't silently grow one giant file forever.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str = "price_monitor") -> logging.Logger:
    """
    Return a configured logger. Safe to call multiple times (e.g. once per
    module) — handlers are only attached once per logger name.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Console handler — concise, INFO and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating file handler — verbose, DEBUG and above
    Path(settings.logs_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(settings.logs_dir) / "price_monitor.log"
    file_handler = RotatingFileHandler(
        log_file, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger
