"""Structured logging setup using structlog.

Provides JSON-formatted logs for production and human-readable
colored logs for development. All connector activity, API calls,
and data processing steps are logged with full context.
"""

from __future__ import annotations

import logging
import sys

import structlog

from ikerketa.config import settings


def setup_logging() -> None:
    """Configure structlog with appropriate processors.

    Call once at application startup (e.g., in cli.py).
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # Determine if we're in a terminal (dev) or piped (prod)
    is_interactive = sys.stderr.isatty()

    if is_interactive:
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(
            colors=True,
        )
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging so third-party libs route through structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, settings.log_level),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named logger bound with structlog context."""
    return structlog.get_logger(name)
