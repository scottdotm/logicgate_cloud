"""
LogicGate Structured Logging
Structured logging with error tracking and Sentry integration.
"""

import json
import logging
import logging.handlers
import os
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class LogLevel(StrEnum):
    """Log levels"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(StrEnum):
    """Log formats"""

    JSON = "json"
    TEXT = "text"


@dataclass
class LogContext:
    """Structured log context"""

    user_id: int | None = None
    request_id: str | None = None
    asset_id: int | None = None
    session_id: str | None = None
    ip_address: str | None = None
    extra: dict[str, Any] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        if self.extra:
            result.update(self.extra)
        return result


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add context from record
        if hasattr(record, "context"):
            log_data["context"] = record.context

        return json.dumps(log_data)


class StructuredLogger:
    """Structured logger with context support"""

    def __init__(
        self, name: str, level: LogLevel = LogLevel.INFO, format: LogFormat = LogFormat.JSON
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.value))

        # Remove existing handlers
        self.logger.handlers.clear()

        # Create handler
        handler = logging.StreamHandler(sys.stdout)

        # Set formatter
        if format == LogFormat.JSON:
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            )

        self.logger.addHandler(handler)

        self._context: LogContext | None = None

    def set_context(self, context: LogContext):
        """Set log context"""
        self._context = context

    def clear_context(self):
        """Clear log context"""
        self._context = None

    @contextmanager
    def context(self, **kwargs):
        """Context manager for temporary log context"""
        old_context = self._context
        self._context = LogContext(**kwargs)
        try:
            yield
        finally:
            self._context = old_context

    def _log(self, level: LogLevel, message: str, **kwargs):
        """Internal log method"""
        extra = {}
        if self._context:
            extra["context"] = self._context.to_dict()

        if kwargs:
            if "context" in extra:
                extra["context"].update(kwargs)
            else:
                extra["context"] = kwargs

        self.logger.log(getattr(logging, level.value), message, extra=extra)

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self._log(LogLevel.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs):
        """Log exception with traceback"""
        self.logger.exception(
            message, extra={"context": self._context.to_dict() if self._context else {}}
        )


class SentryIntegration:
    """Sentry integration for error tracking"""

    def __init__(self, dsn: str = None, environment: str = "development"):
        self.dsn = dsn or os.getenv("SENTRY_DSN")
        self.environment = environment
        self.enabled = False

        if self.dsn:
            self._initialize_sentry()

    def _initialize_sentry(self):
        """Initialize Sentry SDK"""
        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration

            sentry_sdk.init(
                dsn=self.dsn,
                environment=self.environment,
                integrations=[LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)],
                traces_sample_rate=0.1,
                profiles_sample_rate=0.1,
                before_send=self._before_send,
            )

            self.enabled = True
        except ImportError:
            print("Sentry SDK not installed, error tracking disabled")

    def _before_send(self, event: dict, hint: dict) -> dict | None:
        """Filter events before sending to Sentry"""
        # Filter out certain exceptions if needed
        if hint:
            exc_info = hint.get("exc_info")
            if exc_info:
                exc_type = exc_info[0]
                # Filter out specific exception types
                if exc_type.__name__ in ["KeyboardInterrupt", "SystemExit"]:
                    return None

        return event

    def capture_exception(self, exception: Exception, context: dict = None):
        """Capture exception in Sentry"""
        if not self.enabled:
            return

        try:
            import sentry_sdk

            sentry_sdk.capture_exception(exception, extra=context or {})
        except Exception:
            pass

    def capture_message(self, message: str, level: str = "info", context: dict = None):
        """Capture message in Sentry"""
        if not self.enabled:
            return

        try:
            import sentry_sdk

            sentry_sdk.capture_message(message, level=level, extra=context or {})
        except Exception:
            pass

    def set_user_context(self, user_id: int, email: str = None, username: str = None):
        """Set user context in Sentry"""
        if not self.enabled:
            return

        try:
            import sentry_sdk

            sentry_sdk.set_user({"id": str(user_id), "email": email, "username": username})
        except Exception:
            pass

    def clear_context(self):
        """Clear Sentry context"""
        if not self.enabled:
            return

        try:
            import sentry_sdk

            sentry_sdk.set_user(None)
        except Exception:
            pass

    def add_breadcrumb(self, category: str, message: str, level: str = "info", data: dict = None):
        """Add breadcrumb to Sentry"""
        if not self.enabled:
            return

        try:
            import sentry_sdk

            sentry_sdk.add_breadcrumb(
                category=category, message=message, level=level, data=data or {}
            )
        except Exception:
            pass


class LogManager:
    """Manages multiple loggers"""

    def __init__(self):
        self.loggers: dict[str, StructuredLogger] = {}
        self.sentry: SentryIntegration | None = None

    def get_logger(
        self, name: str, level: LogLevel = LogLevel.INFO, format: LogFormat = LogFormat.JSON
    ) -> StructuredLogger:
        """Get or create a logger"""
        if name not in self.loggers:
            self.loggers[name] = StructuredLogger(name, level, format)
        return self.loggers[name]

    def initialize_sentry(self, dsn: str = None, environment: str = "development"):
        """Initialize Sentry integration"""
        self.sentry = SentryIntegration(dsn, environment)

    def capture_exception(self, exception: Exception, context: dict = None):
        """Capture exception across all loggers"""
        if self.sentry:
            self.sentry.capture_exception(exception, context)

    def set_user_context(self, user_id: int, email: str = None, username: str = None):
        """Set user context across all loggers"""
        if self.sentry:
            self.sentry.set_user_context(user_id, email, username)

        # Also set context in all loggers
        for logger in self.loggers.values():
            logger.set_context(LogContext(user_id=user_id))


# Singleton instance
_log_manager: LogManager | None = None


def get_log_manager() -> LogManager:
    """Get the singleton log manager instance"""
    global _log_manager
    if _log_manager is None:
        _log_manager = LogManager()
    return _log_manager


def get_logger(
    name: str, level: LogLevel = LogLevel.INFO, format: LogFormat = LogFormat.JSON
) -> StructuredLogger:
    """Get a logger by name"""
    return get_log_manager().get_logger(name, level, format)


def setup_logging(
    level: LogLevel = LogLevel.INFO,
    format: LogFormat = LogFormat.JSON,
    sentry_dsn: str = None,
    environment: str = "development",
):
    """Setup logging configuration"""
    manager = get_log_manager()

    if sentry_dsn:
        manager.initialize_sentry(sentry_dsn, environment)

    # Configure root logger
    root_logger = manager.get_logger("root", level, format)

    return manager


# Decorator for logging function calls
def log_execution(logger_name: str = None, level: LogLevel = LogLevel.INFO):
    """Decorator to log function execution"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger(logger_name or func.__module__)
            logger.log(level, f"Executing {func.__name__}", args=args, kwargs=kwargs)

            try:
                result = func(*args, **kwargs)
                logger.log(level, f"Completed {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}", error=str(e))
                raise

        return wrapper

    return decorator


# Decorator for error tracking
def track_errors(sentry_context: dict = None):
    """Decorator to track errors in Sentry"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                manager = get_log_manager()
                manager.capture_exception(e, sentry_context)
                raise

        return wrapper

    return decorator


if __name__ == "__main__":
    print("Testing Structured Logging...")

    # Setup logging
    manager = setup_logging(level=LogLevel.INFO, format=LogFormat.JSON)

    # Get logger
    logger = get_logger("test_module")

    # Test logging
    logger.info("Test info message", user_id=1, request_id="req_123")
    logger.warning("Test warning message", asset_id=5)
    logger.error("Test error message", error_code="TEST_001")

    # Test context
    with logger.context(user_id=2, request_id="req_456"):
        logger.info("Message with context")

    # Test exception tracking
    try:
        raise ValueError("Test exception")
    except Exception as e:
        manager.capture_exception(e, {"test": "context"})

    # Test decorator
    @log_execution(level=LogLevel.DEBUG)
    def test_function(x):
        return x * 2

    result = test_function(5)
    print(f"Function result: {result}")

    print("Structured Logging test complete!")
