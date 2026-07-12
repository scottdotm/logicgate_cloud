"""Domain-specific exceptions for the security toolkit."""


class SecurityToolkitError(Exception):
    """Base exception for the security toolkit."""


class TenantLimitError(SecurityToolkitError):
    """Raised when a tenant exceeds its plan limits."""


class AssessmentNotFoundError(SecurityToolkitError):
    """Raised when an assessment cannot be found."""


class ScanError(SecurityToolkitError):
    """Raised when an external scan fails."""


class InvalidDomainError(SecurityToolkitError):
    """Raised when a domain is invalid or cannot be scanned."""
