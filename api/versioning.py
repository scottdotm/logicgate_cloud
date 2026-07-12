"""
LogicGate API Versioning
API version management with version routing and deprecation support.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from functools import wraps


class APIVersion(StrEnum):
    """API version identifiers"""

    V1 = "v1"
    V2 = "v2"
    LATEST = "latest"


class VersionStatus(StrEnum):
    """API version status"""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"
    BETA = "beta"


@dataclass
class VersionInfo:
    """API version information"""

    version: APIVersion
    status: VersionStatus
    released_at: datetime
    deprecated_at: datetime | None = None
    sunset_at: datetime | None = None
    description: str = ""


class APIVersionManager:
    """Manages API versions and routing"""

    def __init__(self):
        self.versions: dict[APIVersion, VersionInfo] = {}
        self.routes: dict[str, dict[APIVersion, Callable]] = {}
        self._initialize_default_versions()

    def _initialize_default_versions(self):
        """Initialize default API versions"""
        self.register_version(
            APIVersion.V1,
            VersionStatus.ACTIVE,
            datetime(2024, 1, 1),
            description="Initial API version",
        )

        self.register_version(
            APIVersion.V2,
            VersionStatus.BETA,
            datetime(2024, 6, 1),
            description="Enhanced API with new features",
        )

    def register_version(
        self,
        version: APIVersion,
        status: VersionStatus,
        released_at: datetime,
        deprecated_at: datetime = None,
        sunset_at: datetime = None,
        description: str = "",
    ):
        """Register an API version"""
        self.versions[version] = VersionInfo(
            version=version,
            status=status,
            released_at=released_at,
            deprecated_at=deprecated_at,
            sunset_at=sunset_at,
            description=description,
        )

    def get_version_info(self, version: APIVersion) -> VersionInfo | None:
        """Get information about a specific version"""
        return self.versions.get(version)

    def get_active_versions(self) -> list[APIVersion]:
        """Get all active API versions"""
        return [v for v, info in self.versions.items() if info.status == VersionStatus.ACTIVE]

    def get_latest_version(self) -> APIVersion:
        """Get the latest API version"""
        active_versions = self.get_active_versions()
        if active_versions:
            return max(active_versions, key=lambda v: self.versions[v].released_at)
        return APIVersion.V1

    def register_route(self, path: str, version: APIVersion, handler: Callable):
        """Register a route handler for a specific version"""
        if path not in self.routes:
            self.routes[path] = {}
        self.routes[path][version] = handler

    def get_route_handler(self, path: str, version: APIVersion) -> Callable | None:
        """Get the handler for a specific route and version"""
        if path in self.routes and version in self.routes[path]:
            return self.routes[path][version]

        # Fallback to latest version if requested version not found
        latest = self.get_latest_version()
        if path in self.routes and latest in self.routes[path]:
            return self.routes[path][latest]

        return None

    def deprecate_version(
        self, version: APIVersion, deprecated_at: datetime = None, sunset_at: datetime = None
    ):
        """Deprecate an API version"""
        if version in self.versions:
            self.versions[version].status = VersionStatus.DEPRECATED
            self.versions[version].deprecated_at = deprecated_at or datetime.now()
            self.versions[version].sunset_at = sunset_at

    def sunset_version(self, version: APIVersion):
        """Sunset (remove) an API version"""
        if version in self.versions:
            self.versions[version].status = VersionStatus.SUNSET


def versioned(version: APIVersion):
    """Decorator to mark a route handler for a specific API version"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper._api_version = version
        return wrapper

    return decorator


class VersionMiddleware:
    """Middleware for API version handling"""

    def __init__(self, version_manager: APIVersionManager):
        self.version_manager = version_manager

    def extract_version(self, request) -> APIVersion:
        """Extract API version from request"""
        # Check version from URL path
        path_parts = request.path.split("/")
        if len(path_parts) > 1 and path_parts[1].startswith("v"):
            try:
                return APIVersion(path_parts[1])
            except ValueError:
                pass

        # Check version from header
        version_header = request.headers.get("API-Version", request.headers.get("Accept-Version"))
        if version_header:
            try:
                return APIVersion(version_header)
            except ValueError:
                pass

        # Default to latest
        return self.version_manager.get_latest_version()

    def check_version_status(self, version: APIVersion) -> bool:
        """Check if version is still supported"""
        version_info = self.version_manager.get_version_info(version)
        if not version_info:
            return False

        return version_info.status != VersionStatus.SUNSET


# Singleton instance
_version_manager: APIVersionManager | None = None


def get_version_manager() -> APIVersionManager:
    """Get the singleton version manager instance"""
    global _version_manager
    if _version_manager is None:
        _version_manager = APIVersionManager()
    return _version_manager


if __name__ == "__main__":
    print("Testing API Versioning...")

    manager = get_version_manager()

    # Test version registration
    manager.register_version(
        APIVersion.V2, VersionStatus.ACTIVE, datetime(2024, 6, 1), description="Enhanced API"
    )

    # Test version info
    v1_info = manager.get_version_info(APIVersion.V1)
    print(f"V1 status: {v1_info.status}")

    # Test active versions
    active = manager.get_active_versions()
    print(f"Active versions: {[v.value for v in active]}")

    # Test latest version
    latest = manager.get_latest_version()
    print(f"Latest version: {latest.value}")

    print("API Versioning test complete!")
