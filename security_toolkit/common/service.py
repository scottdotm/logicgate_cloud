"""Base service with tenant isolation and database lifecycle helpers."""

import os
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from logicgate_cloud.billing.tier_manager import TierLimits
from logicgate_cloud.security_toolkit.common.exceptions import TenantLimitError


class TenantScopedService:
    """Base class for services that operate on tenant-scoped data."""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = os.environ.get("SHARED_DB_PATH", "logicgate_shared.db")
        self.db_path = db_path
        self._async_url = self._to_async_url(db_path)
        self._engine = create_async_engine(self._async_url, echo=False, future=True)
        self._session_factory = sessionmaker(
            bind=self._engine, class_=AsyncSession, expire_on_commit=False
        )

    @staticmethod
    def _to_async_url(path: str) -> str:
        """Convert a SQLite file path to an async SQLite URL."""
        if path.startswith("sqlite:///"):
            path = path.replace("sqlite:///", "", 1)
        elif path.startswith("sqlite+aiosqlite:///"):
            return path
        return f"sqlite+aiosqlite:///{path}"

    @asynccontextmanager
    async def session(self):
        """Provide an async database session."""
        async with self._session_factory() as session:
            yield session

    async def check_limit(
        self, tenant_id: int, resource: str, current_count: int, plan: str
    ) -> None:
        """Raise TenantLimitError if the tenant would exceed its plan limit."""
        is_within, limit = TierLimits.check_limit(plan, resource, current_count)
        if not is_within:
            raise TenantLimitError(
                f"Tenant {tenant_id} has reached the plan limit for {resource} ({limit})."
            )

    async def has_feature(self, tenant_id: int, plan: str, feature: str) -> bool:
        """Return whether the tenant's plan includes a feature."""
        return TierLimits.has_feature(plan, feature)

    async def dispose(self):
        """Dispose of the async engine and release database connections."""
        await self._engine.dispose()
