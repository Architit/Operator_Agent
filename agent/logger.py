"""
Common logging setup for OperatorAgent.

This module configures a rotating file logger used across all modules of
the OperatorAgent project. Log messages are written to
``Archive/Logs/operator.log`` with automatic rotation when the file
reaches approximately 5 MB in size, keeping up to five backups. Each
log entry includes an ISO 8601 timestamp in UTC with a ``Z`` suffix,
the log level in square brackets, and the message.

Environment variable ``OPERATOR_LOG_LEVEL`` can be set to one of
``DEBUG``, ``INFO``, ``WARNING`` or ``ERROR`` to override the default
logging level.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import time
from pathlib import Path
from typing import Optional

_handler: Optional[logging.Handler] = None


def _initialize_handler() -> logging.Handler:
    """Create and return a RotatingFileHandler configured for operator logs.

    The handler writes to ``Archive/Logs/operator.log`` relative to the
    project root, rotates at ~5 MB and keeps up to five backups.  It
    configures a formatter that outputs UTC timestamps in ISO 8601 with
    a ``Z`` suffix.
    """
    global _handler
    if _handler is not None:
        return _handler
    # Determine log file path relative to this module
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    logs_dir = project_root / "Archive" / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "operator.log"
    # Create rotating file handler
    handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=5_242_880,
        backupCount=5,
        encoding="utf-8"
    )
    # Formatter: ISO8601 UTC with 'Z' suffix and level in square brackets
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ"
    )
    # Use UTC for timestamps
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    # Mark handler to avoid duplication
    setattr(handler, "_operator_handler", True)
    # Determine log level from environment or default
    level_name = os.getenv("OPERATOR_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    handler.setLevel(level)
    _handler = handler
    return handler


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a configured logger for OperatorAgent.

    This logger writes to the common ``operator.log`` file with
    size-based rotation. Subsequent calls for the same logger name
    reuse the existing handler and do not add duplicates.

    Parameters:
        name: The name of the logger to retrieve. If ``None``, the root
            logger is used.

    Returns:
        A configured ``logging.Logger`` instance.
    """
    logger = logging.getLogger(name)
    # Ensure basic configuration only once per logger
    handler = _initialize_handler()
    # Check if this handler is already attached to avoid duplicates
    if not any(getattr(h, "_operator_handler", False) for h in logger.handlers):
        logger.addHandler(handler)
    # Set logger level based on environment
    level_name = os.getenv("OPERATOR_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)
    # Prevent propagation to avoid duplicate messages in parent loggers
    logger.propagate = False
    return logger


def set_level(level_name: str) -> None:
    """Override the log level for the common handler and associated loggers.

    Parameters:
        level_name: A string representing the desired log level (e.g.
            ``"DEBUG"``, ``"INFO"``, ``"WARNING"``, ``"ERROR"``).

    Raises:
        ValueError: If an invalid level name is provided.
    """
    level_name = level_name.upper()
    if not hasattr(logging, level_name):
        raise ValueError(f"Invalid log level: {level_name}")
    level = getattr(logging, level_name)
    handler = _initialize_handler()
    handler.setLevel(level)
    # Update all loggers using this handler
    for logger_name in list(logging.Logger.manager.loggerDict.keys()):
        logger_obj = logging.getLogger(logger_name)
        if any(getattr(h, "_operator_handler", False) for h in logger_obj.handlers):
            logger_obj.setLevel(level)
    # Also update root logger if it uses the handler
    root_logger = logging.getLogger()
    if any(getattr(h, "_operator_handler", False) for h in root_logger.handlers):
        root_logger.setLevel(level)