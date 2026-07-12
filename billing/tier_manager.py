# tier_manager.py
"""
LogicGate Tier Management System
Handles freemium and paid tier logic, limits, and upgrades.
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta

# Database path
SHARED_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logicgate_shared.db")


class TierLimits:
    """Defines limits for each subscription tier"""

    TIERS = {
        "freemium": {
            "name": "Freemium",
            "price": 0,
            "max_assets": 3,
            "max_storage_gb": 5,
            "max_users": 1,
            "max_geofences": 5,
            "max_alert_rules": 10,
            "max_security_assessments": 0,
            "max_policies": 3,
            "max_docs": 5,
            "max_tasks": 10,
            "max_it_assets": 10,
            "historical_data_days": 7,
            "api_calls_per_day": 100,
            "features": [
                "basic_fleet_visibility",
                "real_time_telemetry",
                "basic_geofencing",
                "web_dashboard",
                "email_support",
            ],
            "excluded_features": [
                "command_control",
                "advanced_analytics",
                "custom_reports",
                "api_access",
                "white_labeling",
                "priority_support",
                "sla",
            ],
        },
        "starter": {
            "name": "Starter",
            "price": 99,
            "max_assets": 5,
            "max_storage_gb": 10,
            "max_users": 2,
            "max_geofences": 10,
            "max_alert_rules": 25,
            "max_security_assessments": 10,
            "max_policies": -1,
            "max_docs": 25,
            "max_tasks": 50,
            "max_it_assets": 50,
            "historical_data_days": 30,
            "api_calls_per_day": 1000,
            "features": [
                "basic_fleet_visibility",
                "real_time_telemetry",
                "basic_geofencing",
                "web_dashboard",
                "email_support",
                "command_control",
                "basic_analytics",
                "security_assessment",
            ],
            "excluded_features": [
                "advanced_analytics",
                "custom_reports",
                "api_access",
                "white_labeling",
                "priority_support",
                "sla",
            ],
        },
        "professional": {
            "name": "Professional",
            "price": 299,
            "max_assets": 25,
            "max_storage_gb": 50,
            "max_users": 5,
            "max_geofences": 25,
            "max_alert_rules": 100,
            "max_security_assessments": 50,
            "max_policies": -1,
            "max_docs": -1,
            "max_tasks": -1,
            "max_it_assets": -1,
            "historical_data_days": 90,
            "api_calls_per_day": 10000,
            "features": [
                "basic_fleet_visibility",
                "real_time_telemetry",
                "basic_geofencing",
                "web_dashboard",
                "email_support",
                "command_control",
                "basic_analytics",
                "advanced_analytics",
                "custom_reports",
                "api_access",
                "security_assessment",
            ],
            "excluded_features": ["white_labeling", "priority_support", "sla"],
        },
        "enterprise": {
            "name": "Enterprise",
            "price": 799,
            "max_assets": -1,  # Unlimited
            "max_storage_gb": -1,  # Unlimited
            "max_users": -1,  # Unlimited
            "max_geofences": -1,  # Unlimited
            "max_alert_rules": -1,  # Unlimited
            "max_security_assessments": -1,  # Unlimited
            "max_policies": -1,
            "max_docs": -1,
            "max_tasks": -1,
            "max_it_assets": -1,
            "historical_data_days": 365,
            "api_calls_per_day": -1,  # Unlimited
            "features": [
                "basic_fleet_visibility",
                "real_time_telemetry",
                "basic_geofencing",
                "web_dashboard",
                "email_support",
                "command_control",
                "basic_analytics",
                "advanced_analytics",
                "custom_reports",
                "api_access",
                "white_labeling",
                "priority_support",
                "sla",
                "security_assessment",
            ],
            "excluded_features": [],
        },
    }

    @classmethod
    def get_tier_limits(cls, tier: str) -> dict:
        """Get limits for a specific tier"""
        return cls.TIERS.get(tier.lower(), cls.TIERS["freemium"])

    @classmethod
    def check_limit(cls, tier: str, resource: str, current_value: int) -> tuple[bool, int | None]:
        """
        Check if current value exceeds tier limit
        Returns (is_within_limit, limit_value)
        """
        limits = cls.get_tier_limits(tier)
        limit_key = f"max_{resource}"

        if limit_key not in limits:
            return True, None

        limit = limits[limit_key]

        # -1 means unlimited
        if limit == -1:
            return True, None

        return current_value < limit, limit

    @classmethod
    def has_feature(cls, tier: str, feature: str) -> bool:
        """Check if tier has access to a specific feature"""
        limits = cls.get_tier_limits(tier)
        return feature in limits["features"]

    @classmethod
    def get_all_tiers(cls) -> list[dict]:
        """Get all available tiers with their details"""
        return [{"id": tier_id, **tier_data} for tier_id, tier_data in cls.TIERS.items()]


class TierManager:
    """Manages tier assignments and upgrades for organizations"""

    def __init__(self, db_path: str = SHARED_DB_PATH):
        self.db_path = db_path
        self._initialize_database()

    def _initialize_database(self):
        """Initialize tier management database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Organizations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                tier TEXT DEFAULT 'freemium',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                trial_end_date TIMESTAMP,
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT
            )
        """)

        # Tier usage tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tier_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER,
                resource_type TEXT,
                current_count INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES organizations(id)
            )
        """)

        # Tier change history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tier_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER,
                old_tier TEXT,
                new_tier TEXT,
                reason TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES organizations(id)
            )
        """)

        conn.commit()
        conn.close()

    def create_organization(self, name: str, tier: str = "freemium", trial_days: int = 14) -> int:
        """
        Create a new organization with specified tier
        Returns organization ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        trial_end_date = None
        if trial_days > 0:
            trial_end_date = (datetime.now() + timedelta(days=trial_days)).isoformat()

        cursor.execute(
            """
            INSERT INTO organizations (name, tier, trial_end_date)
            VALUES (?, ?, ?)
        """,
            (name, tier, trial_end_date),
        )

        org_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Initialize usage tracking
        self._initialize_usage_tracking(org_id)

        return org_id

    def _initialize_usage_tracking(self, org_id: int):
        """Initialize usage tracking for a new organization"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        resources = ["assets", "storage", "users", "geofences", "alert_rules"]

        for resource in resources:
            cursor.execute(
                """
                INSERT INTO tier_usage (organization_id, resource_type, current_count)
                VALUES (?, ?, 0)
            """,
                (org_id, resource),
            )

        conn.commit()
        conn.close()

    def get_organization_tier(self, org_id: int) -> str:
        """Get current tier for an organization"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT tier FROM organizations WHERE id = ?
        """,
            (org_id,),
        )

        result = cursor.fetchone()
        conn.close()

        return result[0] if result else "freemium"

    def update_tier(self, org_id: int, new_tier: str, reason: str = "") -> bool:
        """
        Update organization's tier
        Returns True if successful
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get current tier
        cursor.execute(
            """
            SELECT tier FROM organizations WHERE id = ?
        """,
            (org_id,),
        )

        result = cursor.fetchone()
        if not result:
            conn.close()
            return False

        old_tier = result[0]

        # Update tier
        cursor.execute(
            """
            UPDATE organizations
            SET tier = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (new_tier, org_id),
        )

        # Log tier change
        cursor.execute(
            """
            INSERT INTO tier_changes (organization_id, old_tier, new_tier, reason)
            VALUES (?, ?, ?, ?)
        """,
            (org_id, old_tier, new_tier, reason),
        )

        conn.commit()
        conn.close()

        return True

    def get_usage(self, org_id: int, resource_type: str) -> int:
        """Get current usage count for a resource"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT current_count FROM tier_usage
            WHERE organization_id = ? AND resource_type = ?
        """,
            (org_id, resource_type),
        )

        result = cursor.fetchone()
        conn.close()

        return result[0] if result else 0

    def update_usage(self, org_id: int, resource_type: str, count: int) -> bool:
        """Update usage count for a resource"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE tier_usage
            SET current_count = ?, updated_at = CURRENT_TIMESTAMP
            WHERE organization_id = ? AND resource_type = ?
        """,
            (count, org_id, resource_type),
        )

        conn.commit()
        conn.close()

        return True

    def increment_usage(self, org_id: int, resource_type: str) -> tuple[bool, int | None]:
        """
        Increment usage count for a resource
        Returns (success, new_count)
        """
        tier = self.get_organization_tier(org_id)
        current_count = self.get_usage(org_id, resource_type)

        # Check if increment would exceed limit
        within_limit, limit = TierLimits.check_limit(tier, resource_type, current_count + 1)

        if not within_limit:
            return False, limit

        # Increment
        new_count = current_count + 1
        self.update_usage(org_id, resource_type, new_count)

        return True, new_count

    def decrement_usage(self, org_id: int, resource_type: str) -> int:
        """Decrement usage count for a resource"""
        current_count = self.get_usage(org_id, resource_type)
        new_count = max(0, current_count - 1)
        self.update_usage(org_id, resource_type, new_count)
        return new_count

    def check_can_add(self, org_id: int, resource_type: str) -> tuple[bool, int | None]:
        """
        Check if organization can add more of a resource
        Returns (can_add, current_limit)
        """
        tier = self.get_organization_tier(org_id)
        current_count = self.get_usage(org_id, resource_type)

        return TierLimits.check_limit(tier, resource_type, current_count + 1)

    def get_tier_status(self, org_id: int) -> dict:
        """Get complete tier status for an organization"""
        tier = self.get_organization_tier(org_id)
        limits = TierLimits.get_tier_limits(tier)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get organization details
        cursor.execute(
            """
            SELECT name, tier, created_at, trial_end_date
            FROM organizations WHERE id = ?
        """,
            (org_id,),
        )

        org_result = cursor.fetchone()

        # Get current usage
        cursor.execute(
            """
            SELECT resource_type, current_count FROM tier_usage
            WHERE organization_id = ?
        """,
            (org_id,),
        )

        usage_results = cursor.fetchall()
        conn.close()

        usage_dict = dict(usage_results)

        # Build status
        status = {
            "organization_id": org_id,
            "organization_name": org_result[0] if org_result else "",
            "tier": tier,
            "tier_name": limits["name"],
            "price": limits["price"],
            "created_at": org_result[2] if org_result else "",
            "trial_end_date": org_result[3] if org_result else None,
            "is_trial": org_result[3] is not None if org_result else False,
            "limits": {
                "assets": limits["max_assets"],
                "storage_gb": limits["max_storage_gb"],
                "users": limits["max_users"],
                "geofences": limits["max_geofences"],
                "alert_rules": limits["max_alert_rules"],
                "historical_data_days": limits["historical_data_days"],
                "api_calls_per_day": limits["api_calls_per_day"],
            },
            "usage": usage_dict,
            "features": limits["features"],
            "excluded_features": limits["excluded_features"],
        }

        return status

    def is_trial_active(self, org_id: int) -> bool:
        """Check if organization's trial is still active"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT trial_end_date FROM organizations WHERE id = ?
        """,
            (org_id,),
        )

        result = cursor.fetchone()
        conn.close()

        if not result or not result[0]:
            return False

        trial_end = datetime.fromisoformat(result[0])
        return datetime.now() < trial_end

    def get_trial_days_remaining(self, org_id: int) -> int | None:
        """Get remaining trial days for an organization"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT trial_end_date FROM organizations WHERE id = ?
        """,
            (org_id,),
        )

        result = cursor.fetchone()
        conn.close()

        if not result or not result[0]:
            return None

        trial_end = datetime.fromisoformat(result[0])
        remaining = trial_end - datetime.now()
        return max(0, remaining.days)

    def end_trial(self, org_id: int, convert_to_tier: str = "starter") -> bool:
        """
        End trial and convert to specified tier
        Returns True if successful
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE organizations
            SET trial_end_date = NULL, tier = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (convert_to_tier, org_id),
        )

        conn.commit()
        conn.close()

        return True

    def get_upgrade_options(self, org_id: int) -> list[dict]:
        """Get available upgrade options for an organization"""
        current_tier = self.get_organization_tier(org_id)
        all_tiers = TierLimits.get_all_tiers()

        # Filter out current tier and lower tiers
        tier_order = ["freemium", "starter", "professional", "enterprise"]
        current_index = tier_order.index(current_tier)

        upgrade_options = [
            tier for tier in all_tiers if tier_order.index(tier["id"]) > current_index
        ]

        return upgrade_options

    def get_downgrade_options(self, org_id: int) -> list[dict]:
        """Get available downgrade options for an organization"""
        current_tier = self.get_organization_tier(org_id)
        all_tiers = TierLimits.get_all_tiers()

        # Filter out current tier and higher tiers
        tier_order = ["freemium", "starter", "professional", "enterprise"]
        current_index = tier_order.index(current_tier)

        downgrade_options = [
            tier for tier in all_tiers if tier_order.index(tier["id"]) < current_index
        ]

        return downgrade_options


# Convenience functions for common operations
def create_freemium_organization(name: str) -> int:
    """Create a new freemium organization"""
    manager = TierManager()
    return manager.create_organization(name, tier="freemium", trial_days=0)


def create_trial_organization(name: str, trial_days: int = 14) -> int:
    """Create a new organization with trial period"""
    manager = TierManager()
    return manager.create_organization(name, tier="starter", trial_days=trial_days)


def check_feature_access(org_id: int, feature: str) -> bool:
    """Check if organization has access to a feature"""
    manager = TierManager()
    tier = manager.get_organization_tier(org_id)
    return TierLimits.has_feature(tier, feature)


def can_add_asset(org_id: int) -> tuple[bool, int | None]:
    """Check if organization can add another asset"""
    manager = TierManager()
    return manager.check_can_add(org_id, "assets")


def add_asset(org_id: int) -> tuple[bool, int | None]:
    """Add an asset to organization's usage"""
    manager = TierManager()
    return manager.increment_usage(org_id, "assets")


def remove_asset(org_id: int) -> int:
    """Remove an asset from organization's usage"""
    manager = TierManager()
    return manager.decrement_usage(org_id, "assets")


if __name__ == "__main__":
    # Test the tier manager
    print("Testing Tier Manager...")

    # Create a freemium organization
    org_id = create_freemium_organization("Test Company")
    print(f"Created organization with ID: {org_id}")

    # Check tier status
    manager = TierManager()
    status = manager.get_tier_status(org_id)
    print(f"Tier status: {json.dumps(status, indent=2, default=str)}")

    # Test adding assets
    can_add, limit = can_add_asset(org_id)
    print(f"Can add asset: {can_add}, Limit: {limit}")

    # Add assets up to limit
    for i in range(3):
        success, new_count = add_asset(org_id)
        print(f"Added asset {i + 1}: Success={success}, Count={new_count}")

    # Try to exceed limit
    success, new_count = add_asset(org_id)
    print(f"Tried to exceed limit: Success={success}, Count={new_count}")

    # Test tier upgrade
    upgrade_options = manager.get_upgrade_options(org_id)
    print(f"Upgrade options: {len(upgrade_options)}")

    # Upgrade to starter
    manager.update_tier(org_id, "starter", "Manual upgrade test")
    print("Upgraded to starter")

    # Check new status
    status = manager.get_tier_status(org_id)
    print(f"New tier status: {json.dumps(status, indent=2, default=str)}")

    print("Tier Manager test complete!")
