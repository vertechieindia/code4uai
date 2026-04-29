from __future__ import annotations
"""Structured logging for code4u.ai."""
import logging
import sys
import structlog

def configure_logging(*, level: str = "INFO", json_logs: bool = False) -> None:
    processors = [structlog.contextvars.merge_contextvars, structlog.stdlib.add_logger_name, structlog.stdlib.add_log_level, structlog.processors.TimeStamper(fmt="iso"), structlog.processors.StackInfoRenderer()]
    if json_logs: processors.append(structlog.processors.JSONRenderer())
    else: processors.append(structlog.dev.ConsoleRenderer(colors=True))
    structlog.configure(processors=processors, wrapper_class=structlog.stdlib.BoundLogger, context_class=dict, logger_factory=structlog.stdlib.LoggerFactory(), cache_logger_on_first_use=True)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=getattr(logging, level.upper()))

def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)

