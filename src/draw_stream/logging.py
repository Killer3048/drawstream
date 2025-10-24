"""Logging bootstrap utilities."""

from __future__ import annotations

import logging
from logging.config import dictConfig

from .config import LogLevel, get_settings


def configure_logging(level: LogLevel | str | None = None) -> None:
    """Configure root logging with a structured, leveled formatter."""

    settings = get_settings()
    resolved_level = (level or settings.log_level).upper()

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S",
                }
            },
            "handlers": {
                "stderr": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": resolved_level,
                }
            },
            "loggers": {
                "": {
                    "handlers": ["stderr"],
                    "level": resolved_level,
                    "propagate": False,
                },
                "uvicorn": {
                    "handlers": ["stderr"],
                    "level": resolved_level,
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["stderr"],
                    "level": resolved_level,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["stderr"],
                    "level": resolved_level,
                    "propagate": False,
                },
            },
        }
    )

    logging.getLogger(__name__).debug("Logging configured", extra={"level": resolved_level})

