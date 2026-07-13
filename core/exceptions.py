"""
LogicGate Exception Hierarchy
Custom exception classes for structured error handling.
"""

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Standard error codes"""

    # Authentication errors (AUTH_xxx)
    AUTH_INVALID_CREDENTIALS = "AUTH_001"
    AUTH_TOKEN_EXPIRED = "AUTH_002"
    AUTH_TOKEN_INVALID = "AUTH_003"
    AUTH_MFA_REQUIRED = "AUTH_004"
    AUTH_MFA_INVALID = "AUTH_005"
    AUTH_PERMISSION_DENIED = "AUTH_006"
    AUTH_SESSION_EXPIRED = "AUTH_007"

    # Validation errors (VAL_xxx)
    VAL_INVALID_INPUT = "VAL_001"
    VAL_MISSING_FIELD = "VAL_002"
    VAL_INVALID_FORMAT = "VAL_003"
    VAL_OUT_OF_RANGE = "VAL_004"
    VAL_DUPLICATE = "VAL_005"

    # Resource errors (RES_xxx)
    RES_NOT_FOUND = "RES_001"
    RES_ALREADY_EXISTS = "RES_002"
    RES_CONFLICT = "RES_003"
    RES_LOCKED = "RES_004"
    RES_QUOTA_EXCEEDED = "RES_005"

    # Database errors (DB_xxx)
    DB_CONNECTION_ERROR = "DB_001"
    DB_QUERY_ERROR = "DB_002"
    DB_CONSTRAINT_ERROR = "DB_003"
    DB_TIMEOUT = "DB_004"

    # External service errors (EXT_xxx)
    EXT_SERVICE_UNAVAILABLE = "EXT_001"
    EXT_TIMEOUT = "EXT_002"
    EXT_RATE_LIMITED = "EXT_003"
    EXT_INVALID_RESPONSE = "EXT_004"

    # Business logic errors (BIZ_xxx)
    BIZ_INVALID_STATE = "BIZ_001"
    BIZ_OPERATION_NOT_ALLOWED = "BIZ_002"
    BIZ_RULE_VIOLATION = "BIZ_003"

    # System errors (SYS_xxx)
    SYS_INTERNAL_ERROR = "SYS_001"
    SYS_CONFIGURATION_ERROR = "SYS_002"
    SYS_RESOURCE_EXHAUSTED = "SYS_003"


class ErrorSeverity(StrEnum):
    """Error severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LogicGateException(Exception):  # noqa: N818
    """Base exception class for all LogicGate errors"""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.SYS_INTERNAL_ERROR,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ):
        self.message = message
        self.code = code
        self.severity = severity
        self.details = details or {}
        self.context = context or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary"""
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "severity": self.severity.value,
                "details": self.details,
                "context": self.context,
            }
        }


class AuthenticationException(LogicGateException):
    """Authentication-related exceptions"""

    def __init__(
        self, message: str, code: ErrorCode = ErrorCode.AUTH_INVALID_CREDENTIALS, **kwargs
    ):
        super().__init__(message, code, ErrorSeverity.HIGH, **kwargs)


class ValidationException(LogicGateException):
    """Validation-related exceptions"""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.VAL_INVALID_INPUT, **kwargs):
        super().__init__(message, code, ErrorSeverity.LOW, **kwargs)


class ResourceException(LogicGateException):
    """Resource-related exceptions"""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.RES_NOT_FOUND, **kwargs):
        super().__init__(message, code, ErrorSeverity.MEDIUM, **kwargs)


class DatabaseException(LogicGateException):
    """Database-related exceptions"""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.DB_CONNECTION_ERROR, **kwargs):
        super().__init__(message, code, ErrorSeverity.HIGH, **kwargs)


class ExternalServiceException(LogicGateException):
    """External service-related exceptions"""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.EXT_SERVICE_UNAVAILABLE, **kwargs):
        super().__init__(message, code, ErrorSeverity.MEDIUM, **kwargs)


class BusinessException(LogicGateException):
    """Business logic-related exceptions"""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.BIZ_INVALID_STATE, **kwargs):
        super().__init__(message, code, ErrorSeverity.MEDIUM, **kwargs)


class SystemException(LogicGateException):
    """System-related exceptions"""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.SYS_INTERNAL_ERROR, **kwargs):
        super().__init__(message, code, ErrorSeverity.CRITICAL, **kwargs)


# Specific exception classes for common scenarios
class InvalidCredentialsException(AuthenticationException):
    """Invalid credentials provided"""

    def __init__(
        self, message: str = "Invalid credentials provided", details: dict[str, Any] | None = None
    ):
        super().__init__(message, ErrorCode.AUTH_INVALID_CREDENTIALS, details=details)


class TokenExpiredException(AuthenticationException):
    """Authentication token has expired"""

    def __init__(self, details: dict[str, Any] | None = None):
        super().__init__(
            "Authentication token has expired", ErrorCode.AUTH_TOKEN_EXPIRED, details=details
        )


class PermissionDeniedException(AuthenticationException):
    """Permission denied for operation"""

    def __init__(self, resource: str, action: str, details: dict[str, Any] | None = None):
        super().__init__(
            f"Permission denied: {action} on {resource}",
            ErrorCode.AUTH_PERMISSION_DENIED,
            details=details or {"resource": resource, "action": action},
        )


class ResourceNotFoundException(ResourceException):
    """Resource not found"""

    def __init__(self, resource_type: str, resource_id: str, details: dict[str, Any] | None = None):
        super().__init__(
            f"{resource_type} with ID '{resource_id}' not found",
            ErrorCode.RES_NOT_FOUND,
            details=details or {"resource_type": resource_type, "resource_id": resource_id},
        )


class ResourceConflictException(ResourceException):
    """Resource conflict (e.g., duplicate)"""

    def __init__(self, resource_type: str, resource_id: str, details: dict[str, Any] | None = None):
        super().__init__(
            f"Conflict for {resource_type} with ID '{resource_id}'",
            ErrorCode.RES_CONFLICT,
            details=details or {"resource_type": resource_type, "resource_id": resource_id},
        )


class ValidationFailedException(ValidationException):
    """Validation failed"""

    def __init__(self, field: str, reason: str, details: dict[str, Any] | None = None):
        super().__init__(
            f"Validation failed for field '{field}': {reason}",
            ErrorCode.VAL_INVALID_INPUT,
            details=details or {"field": field, "reason": reason},
        )


class DatabaseConnectionException(DatabaseException):
    """Database connection error"""

    def __init__(self, details: dict[str, Any] | None = None):
        super().__init__(
            "Failed to connect to database", ErrorCode.DB_CONNECTION_ERROR, details=details
        )


class ServiceUnavailableException(ExternalServiceException):
    """External service unavailable"""

    def __init__(self, service_name: str, details: dict[str, Any] | None = None):
        super().__init__(
            f"Service '{service_name}' is unavailable",
            ErrorCode.EXT_SERVICE_UNAVAILABLE,
            details=details or {"service": service_name},
        )


class RateLimitExceededException(ExternalServiceException):
    """Rate limit exceeded"""

    def __init__(self, service: str, limit: int, details: dict[str, Any] | None = None):
        super().__init__(
            f"Rate limit exceeded for {service}",
            ErrorCode.EXT_RATE_LIMITED,
            details=details or {"service": service, "limit": limit},
        )


# Exception handler utilities
class ExceptionHandler:
    """Utility class for handling exceptions"""

    @staticmethod
    def handle_exception(exc: Exception) -> dict[str, Any]:
        """Convert exception to standardized error response"""
        if isinstance(exc, LogicGateException):
            return exc.to_dict()

        # Handle standard Python exceptions
        if isinstance(exc, ValueError):
            return LogicGateException(
                str(exc), ErrorCode.VAL_INVALID_INPUT, ErrorSeverity.LOW
            ).to_dict()

        if isinstance(exc, KeyError):
            return LogicGateException(
                f"Missing required field: {str(exc)}",
                ErrorCode.VAL_MISSING_FIELD,
                ErrorSeverity.LOW,
            ).to_dict()

        if isinstance(exc, TimeoutError):
            return LogicGateException(
                "Operation timed out", ErrorCode.EXT_TIMEOUT, ErrorSeverity.MEDIUM
            ).to_dict()

        # Unknown exception
        return LogicGateException(
            str(exc) if str(exc) else "An unexpected error occurred",
            ErrorCode.SYS_INTERNAL_ERROR,
            ErrorSeverity.CRITICAL,
        ).to_dict()

    @staticmethod
    def log_exception(exc: Exception, logger, context: dict[str, Any] = None):
        """Log exception with appropriate level"""
        if isinstance(exc, LogicGateException):
            if exc.severity == ErrorSeverity.CRITICAL:
                logger.critical(exc.message, extra={"error": exc.to_dict(), "context": context})
            elif exc.severity == ErrorSeverity.HIGH:
                logger.error(exc.message, extra={"error": exc.to_dict(), "context": context})
            elif exc.severity == ErrorSeverity.MEDIUM:
                logger.warning(exc.message, extra={"error": exc.to_dict(), "context": context})
            else:
                logger.info(exc.message, extra={"error": exc.to_dict(), "context": context})
        else:
            logger.error(f"Unexpected error: {str(exc)}", exc_info=True, extra={"context": context})


# Decorator for exception handling
def handle_exceptions(default_return=None):
    """Decorator to handle exceptions gracefully"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except LogicGateException:
                raise  # Re-raise LogicGate exceptions
            except Exception as e:
                # Convert to LogicGate exception
                raise SystemException(str(e)) from e

        return wrapper

    return decorator


if __name__ == "__main__":
    print("Testing Exception Hierarchy...")

    # Test custom exception
    exc = InvalidCredentialsException()
    print(f"Exception dict: {exc.to_dict()}")

    # Test exception handler
    handler = ExceptionHandler()
    error_dict = handler.handle_exception(exc)
    print(f"Handled error: {error_dict}")

    # Test resource not found
    not_found = ResourceNotFoundException("User", "123")
    print(f"Not found error: {not_found.to_dict()}")

    print("Exception Hierarchy test complete!")
