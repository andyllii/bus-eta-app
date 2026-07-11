"""
Logging boilerplate.

Provides a configured root logger that writes human-readable, timestamped
lines to both the console and ``logs/app.log``. Call ``get_logger(__name__)``
from any module to obtain a child logger.
"""
import logging
import os

from config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _ensure_log_dir() -> str:
    os.makedirs(settings.log_dir, exist_ok=True)
    return settings.log_dir


def get_logger(name: str) -> logging.Logger:
    """Return a logger named ``name`` with console + file handlers."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured (avoids duplicate handlers on reload)

    logger.setLevel(getattr(logging, settings.log_level, logging.INFO))

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    try:
        log_dir = _ensure_log_dir()
        file_handler = logging.FileHandler(os.path.join(log_dir, "app.log"), encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as exc:  # pragma: no cover - logging must never crash the app
        logger.warning("Could not attach file handler: %s", exc)

    logger.propagate = False
    return logger
