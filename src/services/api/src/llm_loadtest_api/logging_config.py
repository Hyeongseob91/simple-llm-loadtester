"""Structured logging configuration using structlog."""

import logging
import sys
import uuid
from typing import Any, Dict

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Configure standard logging
logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=logging.INFO,
)


def configure_logging() -> None:
    """Configure structured logging with structlog."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (usually module name).

    Returns:
        Configured structlog logger.
    """
    return structlog.get_logger(name)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests with request ID tracking."""

    async def dispatch(self, request: Request, call_next):
        """Process request and log with request ID.

        Args:
            request: FastAPI request object.
            call_next: Next middleware in chain.

        Returns:
            Response object.
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Bind request ID to context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )

        # Get logger
        logger = get_logger("api.request")

        # Log request
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            query_params=str(request.query_params),
        )

        # Process request
        try:
            response = await call_next(request)

            # Log response
            logger.info(
                "request_completed",
                status_code=response.status_code,
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as exc:
            # Log error
            logger.error(
                "request_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise


def log_benchmark_event(
    event: str,
    run_id: str,
    extra: Dict[str, Any] = None,
) -> None:
    """Log benchmark-related events.

    Args:
        event: Event name (e.g., "benchmark_started", "benchmark_completed").
        run_id: Benchmark run ID.
        extra: Additional context to log.
    """
    logger = get_logger("api.benchmark")

    log_data = {
        "run_id": run_id,
    }

    if extra:
        log_data.update(extra)

    logger.info(event, **log_data)
