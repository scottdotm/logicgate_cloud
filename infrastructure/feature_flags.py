"""
LogicGate Feature Flag System
Manages feature flags for gradual rollouts and A/B testing.
"""

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any

from logicgate_cloud.config.settings import get_settings
from logicgate_cloud.infrastructure.cache import get_cache_manager

# Infrastructure imports
from logicgate_cloud.infrastructure.logging import LogLevel, get_logger


class FlagType(Enum):
    """Feature flag types"""

    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
    USER_LIST = "user_list"
    ORGANIZATION_LIST = "organization_list"
    CONFIGURATION = "configuration"


class FlagStatus(Enum):
    """Feature flag status"""

    DISABLED = "disabled"
    ENABLED = "enabled"
    ROLLOUT = "rollout"


@dataclass
class FeatureFlag:
    """Feature flag data"""

    id: str
    name: str
    description: str
    flag_type: FlagType
    status: FlagStatus
    value: Any
    rollout_percentage: float  # 0-100 for percentage flags
    enabled_users: list[str]
    enabled_organizations: list[str]
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None


class FeatureFlagManager:
    """Manages feature flags for the application"""

    def __init__(self, db_path: str = None):
        self.logger = get_logger("feature_flags", LogLevel.INFO)
        self.settings = get_settings()
        self.cache_manager = get_cache_manager()

        # Use database path from settings if not provided
        if db_path is None and hasattr(self.settings, "shared_db_path"):
            db_path = self.settings.shared_db_path
        elif db_path is None:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logicgate_shared.db"
            )

        self.db_path = db_path
        self._initialize_database()
        self._load_flags()

    def _initialize_database(self):
        """Initialize feature flags database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feature_flags (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                flag_type TEXT NOT NULL,
                status TEXT DEFAULT 'disabled',
                value TEXT,
                rollout_percentage REAL DEFAULT 0,
                enabled_users TEXT,
                enabled_organizations TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flag_usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flag_id TEXT NOT NULL,
                user_id TEXT,
                organization_id TEXT,
                is_enabled BOOLEAN,
                context TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (flag_id) REFERENCES feature_flags(id)
            )
        """)

        conn.commit()
        conn.close()
        self.logger.info("Feature flags database initialized")

    def _load_flags(self):
        """Load feature flags from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM feature_flags")
        results = cursor.fetchall()
        conn.close()

        self.flags = {}
        for row in results:
            flag = FeatureFlag(
                id=row[0],
                name=row[1],
                description=row[2],
                flag_type=FlagType(row[3]),
                status=FlagStatus(row[4]),
                value=json.loads(row[5]) if row[5] else None,
                rollout_percentage=row[6] or 0,
                enabled_users=json.loads(row[7]) if row[7] else [],
                enabled_organizations=json.loads(row[8]) if row[8] else [],
                created_at=datetime.fromisoformat(row[9]),
                updated_at=datetime.fromisoformat(row[10]),
                expires_at=datetime.fromisoformat(row[11]) if row[11] else None,
            )
            self.flags[flag.name] = flag

    def create_flag(
        self,
        name: str,
        description: str,
        flag_type: FlagType,
        value: Any = None,
        rollout_percentage: float = 0,
    ) -> FeatureFlag:
        """Create a new feature flag"""
        flag_id = f"flag_{int(datetime.now().timestamp())}"

        flag = FeatureFlag(
            id=flag_id,
            name=name,
            description=description,
            flag_type=flag_type,
            status=FlagStatus.DISABLED,
            value=value,
            rollout_percentage=rollout_percentage,
            enabled_users=[],
            enabled_organizations=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            expires_at=None,
        )

        self._save_flag(flag)
        self.flags[name] = flag
        self.logger.info(f"Created feature flag: {name}")

        return flag

    def _save_flag(self, flag: FeatureFlag):
        """Save flag to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO feature_flags
            (id, name, description, flag_type, status, value, rollout_percentage,
             enabled_users, enabled_organizations, expires_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                flag.id,
                flag.name,
                flag.description,
                flag.flag_type.value,
                flag.status.value,
                json.dumps(flag.value) if flag.value else None,
                flag.rollout_percentage,
                json.dumps(flag.enabled_users),
                json.dumps(flag.enabled_organizations),
                flag.expires_at.isoformat() if flag.expires_at else None,
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        conn.close()

        # Clear cache
        cache_key = f"feature_flag:{flag.name}"
        self.cache_manager.delete(cache_key)

    def enable_flag(self, name: str, rollout_percentage: float = 100) -> bool:
        """Enable a feature flag"""
        if name not in self.flags:
            return False

        flag = self.flags[name]
        flag.status = FlagStatus.ROLLOUT if rollout_percentage < 100 else FlagStatus.ENABLED
        flag.rollout_percentage = rollout_percentage
        flag.updated_at = datetime.now()

        self._save_flag(flag)
        self.logger.info(f"Enabled feature flag: {name} ({rollout_percentage}%)")

        return True

    def disable_flag(self, name: str) -> bool:
        """Disable a feature flag"""
        if name not in self.flags:
            return False

        flag = self.flags[name]
        flag.status = FlagStatus.DISABLED
        flag.updated_at = datetime.now()

        self._save_flag(flag)
        self.logger.info(f"Disabled feature flag: {name}")

        return True

    def add_user_to_flag(self, name: str, user_id: str) -> bool:
        """Add a user to the enabled list for a flag"""
        if name not in self.flags:
            return False

        flag = self.flags[name]
        if user_id not in flag.enabled_users:
            flag.enabled_users.append(user_id)
            flag.updated_at = datetime.now()
            self._save_flag(flag)

        return True

    def add_organization_to_flag(self, name: str, organization_id: str) -> bool:
        """Add an organization to the enabled list for a flag"""
        if name not in self.flags:
            return False

        flag = self.flags[name]
        if organization_id not in flag.enabled_organizations:
            flag.enabled_organizations.append(organization_id)
            flag.updated_at = datetime.now()
            self._save_flag(flag)

        return True

    def is_enabled(
        self, name: str, user_id: str = None, organization_id: str = None, context: dict = None
    ) -> bool:
        """Check if a feature flag is enabled for a given context"""
        # Check cache first
        cache_key = f"feature_flag:{name}:{user_id}:{organization_id}"
        cached = self.cache_manager.get(cache_key)
        if cached is not None:
            return cached

        if name not in self.flags:
            self.logger.warning(f"Feature flag not found: {name}")
            return False

        flag = self.flags[name]

        # Check if flag is expired
        if flag.expires_at and datetime.now() > flag.expires_at:
            self.logger.warning(f"Feature flag expired: {name}")
            return False

        # Check if flag is disabled
        if flag.status == FlagStatus.DISABLED:
            return False

        # Check if flag is fully enabled
        if flag.status == FlagStatus.ENABLED:
            self._log_flag_usage(flag.id, user_id, organization_id, True, context)
            self.cache_manager.set(cache_key, True, ttl=300)  # Cache for 5 minutes
            return True

        # Check user list
        if user_id and user_id in flag.enabled_users:
            self._log_flag_usage(flag.id, user_id, organization_id, True, context)
            self.cache_manager.set(cache_key, True, ttl=300)
            return True

        # Check organization list
        if organization_id and organization_id in flag.enabled_organizations:
            self._log_flag_usage(flag.id, user_id, organization_id, True, context)
            self.cache_manager.set(cache_key, True, ttl=300)
            return True

        # Check percentage rollout
        if flag.flag_type == FlagType.PERCENTAGE and user_id:
            # Use hash of user_id for consistent rollout
            user_hash = hash(user_id) % 100
            is_enabled = user_hash < flag.rollout_percentage
            self._log_flag_usage(flag.id, user_id, organization_id, is_enabled, context)
            self.cache_manager.set(cache_key, is_enabled, ttl=300)
            return is_enabled

        self._log_flag_usage(flag.id, user_id, organization_id, False, context)
        return False

    def get_flag_value(self, name: str, default: Any = None) -> Any:
        """Get the value of a configuration flag"""
        if name not in self.flags:
            return default

        flag = self.flags[name]
        if flag.flag_type == FlagType.CONFIGURATION:
            return flag.value

        return default

    def _log_flag_usage(
        self, flag_id: str, user_id: str, organization_id: str, is_enabled: bool, context: dict
    ):
        """Log flag usage for analytics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO flag_usage_logs
                (flag_id, user_id, organization_id, is_enabled, context)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    flag_id,
                    user_id,
                    organization_id,
                    is_enabled,
                    json.dumps(context) if context else None,
                ),
            )

            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Error logging flag usage: {e}")

    def get_flag_stats(self, name: str) -> dict:
        """Get statistics for a feature flag"""
        if name not in self.flags:
            return {}

        flag = self.flags[name]

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                COUNT(*) as total_checks,
                SUM(CASE WHEN is_enabled = 1 THEN 1 ELSE 0 END) as enabled_count,
                COUNT(DISTINCT user_id) as unique_users
            FROM flag_usage_logs
            WHERE flag_id = ?
        """,
            (flag.id,),
        )

        result = cursor.fetchone()
        conn.close()

        return {
            "flag_name": name,
            "status": flag.status.value,
            "rollout_percentage": flag.rollout_percentage,
            "total_checks": result[0] or 0,
            "enabled_count": result[1] or 0,
            "unique_users": result[2] or 0,
            "enable_rate": (result[1] / result[0] * 100) if result[0] > 0 else 0,
        }

    def get_all_flags(self) -> list[dict]:
        """Get all feature flags"""
        return [
            {
                "name": flag.name,
                "description": flag.description,
                "type": flag.flag_type.value,
                "status": flag.status.value,
                "rollout_percentage": flag.rollout_percentage,
                "enabled_users": len(flag.enabled_users),
                "enabled_organizations": len(flag.enabled_organizations),
            }
            for flag in self.flags.values()
        ]


# Global feature flag manager instance
_flag_manager = None


def get_feature_flag_manager() -> FeatureFlagManager:
    """Get the global feature flag manager instance"""
    global _flag_manager
    if _flag_manager is None:
        _flag_manager = FeatureFlagManager()
    return _flag_manager


def feature_flag(flag_name: str, default: bool = False):
    """Decorator to conditionally execute code based on feature flag"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            manager = get_feature_flag_manager()
            if manager.is_enabled(flag_name):
                return func(*args, **kwargs)
            return default

        return wrapper

    return decorator


def if_flag_enabled(flag_name: str, user_id: str = None, organization_id: str = None):
    """Context manager to conditionally execute code based on feature flag"""
    from contextlib import contextmanager

    @contextmanager
    def manager():
        flag_manager = get_feature_flag_manager()
        yield flag_manager.is_enabled(flag_name, user_id, organization_id)

    return manager()


# Convenience functions for common flag checks
def is_new_ui_enabled(user_id: str = None, organization_id: str = None) -> bool:
    """Check if new UI is enabled"""
    manager = get_feature_flag_manager()
    return manager.is_enabled("new_ui", user_id, organization_id)


def is_advanced_analytics_enabled(user_id: str = None, organization_id: str = None) -> bool:
    """Check if advanced analytics is enabled"""
    manager = get_feature_flag_manager()
    return manager.is_enabled("advanced_analytics", user_id, organization_id)


def is_swarm_mode_enabled(user_id: str = None, organization_id: str = None) -> bool:
    """Check if swarm mode is enabled"""
    manager = get_feature_flag_manager()
    return manager.is_enabled("swarm_mode", user_id, organization_id)


if __name__ == "__main__":
    print("Testing Feature Flag System...")

    manager = FeatureFlagManager()

    # Create a test flag
    flag = manager.create_flag(
        name="test_feature",
        description="Test feature flag",
        flag_type=FlagType.PERCENTAGE,
        rollout_percentage=50,
    )
    print(f"Created flag: {flag.name}")

    # Enable the flag
    manager.enable_flag("test_feature", 50)
    print("Flag enabled at 50% rollout")

    # Test flag for different users
    user_1_enabled = manager.is_enabled("test_feature", user_id="user_1")
    user_2_enabled = manager.is_enabled("test_feature", user_id="user_2")
    print(f"User 1 enabled: {user_1_enabled}")
    print(f"User 2 enabled: {user_2_enabled}")

    # Get flag stats
    stats = manager.get_flag_stats("test_feature")
    print(f"Flag stats: {stats}")

    # Get all flags
    all_flags = manager.get_all_flags()
    print(f"Total flags: {len(all_flags)}")

    print("Feature Flag System test complete!")
