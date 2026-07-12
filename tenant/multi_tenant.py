# multi_tenant.py
"""
LogicGate Multi-Tenant Support for SaaS Deployment
Multi-tenant architecture with tenant isolation, resource management, and billing.
"""

import json
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from config.settings import get_settings
from infrastructure.cache import cached, get_cache_manager
from infrastructure.logging import LogLevel, get_logger

# Database path
SHARED_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logicgate_shared.db")
TENANT_DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tenants")


class TenantStatus(Enum):
    """Tenant account status"""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    CANCELLED = "cancelled"


class TenantPlan(Enum):
    """Subscription plans"""

    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class TenantTier(Enum):
    """Service tiers"""

    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"


@dataclass
class Tenant:
    """Tenant organization data"""

    id: int
    name: str
    slug: str
    status: TenantStatus
    plan: TenantPlan
    tier: TenantTier
    max_assets: int
    max_users: int
    storage_quota_mb: int
    api_rate_limit: int
    created_at: datetime
    trial_ends_at: datetime | None
    subscription_ends_at: datetime | None


@dataclass
class TenantUser:
    """Tenant user data"""

    id: int
    tenant_id: int
    user_id: int
    role: str
    permissions: list[str]
    created_at: datetime


class TenantManager:
    """Manages multi-tenant operations"""

    def __init__(self, shared_db_path: str = SHARED_DB_PATH, tenant_db_dir: str = TENANT_DB_DIR):
        self.shared_db_path = shared_db_path
        self.tenant_db_dir = tenant_db_dir
        self.cache_manager = get_cache_manager()
        self.settings = get_settings()
        self.logger = get_logger("multi_tenant", LogLevel.INFO)
        self._initialize_tenant_directory()
        self._initialize_shared_database()

    def _initialize_tenant_directory(self):
        """Create tenant database directory"""
        if not os.path.exists(self.tenant_db_dir):
            os.makedirs(self.tenant_db_dir)

    def _initialize_shared_database(self):
        """Initialize shared multi-tenant database"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'trial',
                plan TEXT DEFAULT 'free',
                tier TEXT DEFAULT 'basic',
                max_assets INTEGER DEFAULT 5,
                max_users INTEGER DEFAULT 3,
                storage_quota_mb INTEGER DEFAULT 1000,
                api_rate_limit INTEGER DEFAULT 1000,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                trial_ends_at TIMESTAMP,
                subscription_ends_at TIMESTAMP,
                billing_email TEXT,
                billing_address TEXT,
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tenant_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT DEFAULT 'member',
                permissions TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                UNIQUE(tenant_id, user_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tenant_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tenant_invitations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                role TEXT DEFAULT 'member',
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                accepted_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            )
        """)

        conn.commit()
        conn.close()

    def create_tenant(
        self, name: str, plan: TenantPlan = TenantPlan.FREE, trial_days: int = 14
    ) -> Tenant:
        """Create a new tenant"""
        # Generate unique slug
        slug = self._generate_slug(name)

        # Calculate trial end date
        trial_ends = datetime.now() + timedelta(days=trial_days)

        # Get plan limits
        limits = self._get_plan_limits(plan)

        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO tenants
            (name, slug, status, plan, tier, max_assets, max_users,
             storage_quota_mb, api_rate_limit, trial_ends_at)
            VALUES (?, ?, 'trial', ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                name,
                slug,
                plan.value if isinstance(plan, TenantPlan) else plan,
                limits["tier"],
                limits["max_assets"],
                limits["max_users"],
                limits["storage_quota_mb"],
                limits["api_rate_limit"],
                trial_ends.isoformat(),
            ),
        )

        tenant_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Create tenant-specific database
        self._create_tenant_database(tenant_id, slug)

        return self.get_tenant(tenant_id)

    def _generate_slug(self, name: str) -> str:
        """Generate a unique slug from tenant name"""
        base_slug = name.lower().replace(" ", "-").replace("_", "-")
        slug = base_slug
        counter = 1

        # Ensure uniqueness
        while self._slug_exists(slug):
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    def _slug_exists(self, slug: str) -> bool:
        """Check if slug already exists"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM tenants WHERE slug = ?", (slug,))
        exists = cursor.fetchone() is not None

        conn.close()
        return exists

    def _get_plan_limits(self, plan: TenantPlan) -> dict:
        """Get resource limits for a plan"""
        limits = {
            TenantPlan.FREE: {
                "tier": "basic",
                "max_assets": 5,
                "max_users": 3,
                "storage_quota_mb": 1000,
                "api_rate_limit": 1000,
            },
            TenantPlan.STARTER: {
                "tier": "standard",
                "max_assets": 25,
                "max_users": 10,
                "storage_quota_mb": 10000,
                "api_rate_limit": 5000,
            },
            TenantPlan.PROFESSIONAL: {
                "tier": "premium",
                "max_assets": 100,
                "max_users": 50,
                "storage_quota_mb": 100000,
                "api_rate_limit": 20000,
            },
            TenantPlan.ENTERPRISE: {
                "tier": "premium",
                "max_assets": -1,  # Unlimited
                "max_users": -1,  # Unlimited
                "storage_quota_mb": -1,  # Unlimited
                "api_rate_limit": 100000,
            },
        }

        return limits.get(plan, limits[TenantPlan.FREE])

    def _create_tenant_database(self, tenant_id: int, slug: str):
        """Create tenant-specific database"""
        tenant_db_path = os.path.join(self.tenant_db_dir, f"{slug}.db")

        conn = sqlite3.connect(tenant_db_path)
        cursor = conn.cursor()

        # Create tenant-specific tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                serial_number TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flight_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                duration REAL,
                distance REAL,
                FOREIGN KEY (asset_id) REFERENCES assets(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flight_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flight_log_id INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                latitude REAL,
                longitude REAL,
                altitude REAL,
                speed REAL,
                battery REAL,
                FOREIGN KEY (flight_log_id) REFERENCES flight_logs(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tenant_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Set default settings
        cursor.execute("""
            INSERT OR REPLACE INTO tenant_settings (key, value)
            VALUES ('timezone', 'UTC')
        """)

        conn.commit()
        conn.close()

    @cached(ttl=600)
    def get_tenant(self, tenant_id: int) -> Tenant | None:
        """Get tenant by ID with caching"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            self.logger.warning("Tenant not found", tenant_id=tenant_id)
            return None

        return self._row_to_tenant(result)

    def get_tenant_by_slug(self, slug: str) -> Tenant | None:
        """Get tenant by slug"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tenants WHERE slug = ?", (slug,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        return self._row_to_tenant(result)

    def update_tenant_plan(
        self, tenant_id: int, new_plan: TenantPlan, subscription_ends_at: datetime = None
    ) -> bool:
        """Update tenant subscription plan"""
        limits = self._get_plan_limits(new_plan)

        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE tenants
            SET plan = ?, tier = ?, max_assets = ?, max_users = ?,
                storage_quota_mb = ?, api_rate_limit = ?, subscription_ends_at = ?
            WHERE id = ?
        """,
            (
                new_plan.value if isinstance(new_plan, TenantPlan) else new_plan,
                limits["tier"],
                limits["max_assets"],
                limits["max_users"],
                limits["storage_quota_mb"],
                limits["api_rate_limit"],
                subscription_ends_at.isoformat() if subscription_ends_at else None,
                tenant_id,
            ),
        )

        conn.commit()
        conn.close()

        return True

    def update_tenant(self, tenant_id: int, **kwargs) -> bool:
        """Update arbitrary tenant fields."""
        if not kwargs:
            return True

        allowed_fields = {
            "name",
            "status",
            "plan",
            "tier",
            "max_assets",
            "max_users",
            "storage_quota_mb",
            "api_rate_limit",
            "trial_ends_at",
            "subscription_ends_at",
            "billing_email",
            "billing_address",
            "stripe_customer_id",
            "stripe_subscription_id",
        }

        fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not fields:
            return False

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values())
        values.append(tenant_id)

        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()
        cursor.execute(f"UPDATE tenants SET {set_clause} WHERE id = ?", values)
        conn.commit()
        conn.close()
        return True

    def get_tenant_by_stripe_subscription(self, stripe_subscription_id: str) -> Tenant | None:
        """Find tenant by Stripe subscription ID."""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM tenants WHERE stripe_subscription_id = ?", (stripe_subscription_id,)
        )
        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        return self._row_to_tenant(result)

    def _row_to_tenant(self, result: tuple) -> Tenant:
        """Convert a tenants row into a Tenant dataclass."""
        return Tenant(
            id=result[0],
            name=result[1],
            slug=result[2],
            status=TenantStatus(result[3]) if result[3] else TenantStatus.TRIAL,
            plan=TenantPlan(result[4]) if result[4] else TenantPlan.FREE,
            tier=TenantTier(result[5]) if result[5] else TenantTier.BASIC,
            max_assets=result[6],
            max_users=result[7],
            storage_quota_mb=result[8],
            api_rate_limit=result[9],
            created_at=datetime.fromisoformat(result[10]) if result[10] else datetime.now(),
            trial_ends_at=datetime.fromisoformat(result[11]) if result[11] else None,
            subscription_ends_at=datetime.fromisoformat(result[12]) if result[12] else None,
        )

    def add_user_to_tenant(
        self, tenant_id: int, user_id: int, role: str = "member", permissions: list[str] = None
    ) -> int:
        """Add a user to a tenant"""
        if permissions is None:
            permissions = []

        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO tenant_users
            (tenant_id, user_id, role, permissions)
            VALUES (?, ?, ?, ?)
        """,
            (tenant_id, user_id, role, json.dumps(permissions)),
        )

        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return user_id

    def remove_user_from_tenant(self, tenant_id: int, user_id: int) -> bool:
        """Remove a user from a tenant"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM tenant_users
            WHERE tenant_id = ? AND user_id = ?
        """,
            (tenant_id, user_id),
        )

        conn.commit()
        conn.close()

        return True

    def get_tenant_users(self, tenant_id: int) -> list[TenantUser]:
        """Get all users for a tenant"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM tenant_users WHERE tenant_id = ?
        """,
            (tenant_id,),
        )

        results = cursor.fetchall()
        conn.close()

        return [
            TenantUser(
                id=row[0],
                tenant_id=row[1],
                user_id=row[2],
                role=row[3],
                permissions=json.loads(row[4]),
                created_at=datetime.fromisoformat(row[5]),
            )
            for row in results
        ]

    def record_usage(self, tenant_id: int, metric_name: str, metric_value: float):
        """Record tenant usage metric"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO tenant_usage (tenant_id, metric_name, metric_value)
            VALUES (?, ?, ?)
        """,
            (tenant_id, metric_name, metric_value),
        )

        conn.commit()
        conn.close()

    def get_tenant_usage(
        self,
        tenant_id: int,
        metric_name: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> list[dict]:
        """Get tenant usage metrics"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM tenant_usage WHERE tenant_id = ?"
        params = [tenant_id]

        if metric_name:
            query += " AND metric_name = ?"
            params.append(metric_name)

        if start_date:
            query += " AND recorded_at >= ?"
            params.append(start_date.isoformat())

        if end_date:
            query += " AND recorded_at <= ?"
            params.append(end_date.isoformat())

        query += " ORDER BY recorded_at DESC"

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "tenant_id": row[1],
                "metric_name": row[2],
                "metric_value": row[3],
                "recorded_at": row[4],
            }
            for row in results
        ]

    def check_resource_limits(self, tenant_id: int) -> dict:
        """Check if tenant is within resource limits"""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return {"valid": False, "error": "Tenant not found"}

        # Check asset count
        tenant_db_path = os.path.join(self.tenant_db_dir, f"{tenant.slug}.db")
        conn = sqlite3.connect(tenant_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM assets")
        asset_count = cursor.fetchone()[0]

        conn.close()

        # Check user count
        user_count = len(self.get_tenant_users(tenant_id))

        limits = {
            "assets": {
                "current": asset_count,
                "limit": tenant.max_assets,
                "within_limit": tenant.max_assets == -1 or asset_count <= tenant.max_assets,
            },
            "users": {
                "current": user_count,
                "limit": tenant.max_users,
                "within_limit": tenant.max_users == -1 or user_count <= tenant.max_users,
            },
        }

        all_within_limit = all(limit["within_limit"] for limit in limits.values())

        return {"valid": all_within_limit, "limits": limits}

    def invite_user_to_tenant(
        self, tenant_id: int, email: str, role: str = "member", expires_hours: int = 48
    ) -> str:
        """Invite a user to join a tenant"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=expires_hours)

        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO tenant_invitations
            (tenant_id, email, role, token, expires_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (tenant_id, email, role, token, expires_at.isoformat()),
        )

        conn.commit()
        conn.close()

        return token

    def accept_invitation(self, token: str, user_id: int) -> bool:
        """Accept a tenant invitation"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT tenant_id, email, role, expires_at
            FROM tenant_invitations
            WHERE token = ? AND accepted_at IS NULL
        """,
            (token,),
        )

        result = cursor.fetchone()

        if not result:
            conn.close()
            return False

        tenant_id, email, role, expires_at = result

        # Check if expired
        if datetime.now() > datetime.fromisoformat(expires_at):
            conn.close()
            return False

        # Add user to tenant
        self.add_user_to_tenant(tenant_id, user_id, role)

        # Mark invitation as accepted
        cursor.execute(
            """
            UPDATE tenant_invitations
            SET accepted_at = CURRENT_TIMESTAMP
            WHERE token = ?
        """,
            (token,),
        )

        conn.commit()
        conn.close()

        return True

    def get_tenant_database_path(self, tenant_id: int) -> str | None:
        """Get the database path for a tenant"""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return None

        return os.path.join(self.tenant_db_dir, f"{tenant.slug}.db")


class TenantContext:
    """Context manager for tenant-specific operations"""

    def __init__(self, tenant_manager: TenantManager, tenant_id: int):
        self.tenant_manager = tenant_manager
        self.tenant_id = tenant_id
        self.tenant_db_path = None
        self.conn = None

    def __enter__(self):
        tenant = self.tenant_manager.get_tenant(self.tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {self.tenant_id} not found")

        self.tenant_db_path = self.tenant_manager.get_tenant_database_path(self.tenant_id)
        self.conn = sqlite3.connect(self.tenant_db_path)

        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()


# Convenience functions
def create_tenant(name: str, plan: TenantPlan = TenantPlan.FREE) -> Tenant:
    """Create a new tenant"""
    manager = TenantManager()
    return manager.create_tenant(name, plan)


def get_tenant_by_slug(slug: str) -> Tenant | None:
    """Get tenant by slug"""
    manager = TenantManager()
    return manager.get_tenant_by_slug(slug)


if __name__ == "__main__":
    print("Testing Multi-Tenant System...")

    # Create tenant
    tenant = create_tenant("Acme Drone Services", TenantPlan.STARTER)
    print(f"Created tenant: {tenant.name} (ID: {tenant.id})")

    # Check resource limits
    manager = TenantManager()
    limits = manager.check_resource_limits(tenant.id)
    print(f"Resource limits: {limits}")

    # Invite user
    token = manager.invite_user_to_tenant(tenant.id, "user@example.com")
    print(f"Invitation token: {token}")

    print("Multi-Tenant System test complete!")
