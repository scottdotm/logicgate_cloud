"""Asset inventory service for the security toolkit."""

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from logicgate_cloud.security_toolkit.assets.models import Asset
from logicgate_cloud.security_toolkit.common.service import TenantScopedService


class AssetService(TenantScopedService):
    """Service for managing tenant asset inventories."""

    async def list_assets(self, tenant_id: int) -> list[Asset]:
        """List assets for a tenant."""
        async with self.session() as session:
            result = await session.execute(
                select(Asset).where(Asset.tenant_id == tenant_id).order_by(Asset.updated_at.desc())
            )
            return list(result.scalars().all())

    async def get_asset(self, tenant_id: int, asset_id: int) -> Asset | None:
        """Get a tenant asset by ID."""
        async with self.session() as session:
            result = await session.execute(
                select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id)
            )
            return result.scalar_one_or_none()

    async def create_asset(self, tenant_id: int, plan: str, data: dict[str, Any]) -> Asset:
        """Create an asset."""
        async with self.session() as session:
            count_result = await session.execute(
                select(func.count(Asset.id)).where(Asset.tenant_id == tenant_id)
            )
            current_count = count_result.scalar() or 0
            await self.check_limit(tenant_id, "it_assets", current_count, plan)

            asset = Asset(
                tenant_id=tenant_id,
                name=data["name"],
                asset_type=data["asset_type"],
                owner=data.get("owner"),
                location=data.get("location"),
                status=data.get("status") or "active",
                purchase_date=data.get("purchase_date"),
                renewal_date=data.get("renewal_date"),
                notes=data.get("notes"),
                tags=json.dumps(data["tags"]) if data.get("tags") else None,
            )
            session.add(asset)
            await session.commit()
            await session.refresh(asset)
            return asset

    async def import_csv(self, tenant_id: int, plan: str, csv_text: str) -> list[Asset]:
        """Import assets from CSV text."""
        async with self.session() as session:
            count_result = await session.execute(
                select(func.count(Asset.id)).where(Asset.tenant_id == tenant_id)
            )
            current_count = count_result.scalar() or 0

            reader = csv.DictReader(io.StringIO(csv_text))
            rows = list(reader)
            await self.check_limit(tenant_id, "it_assets", current_count + len(rows), plan)

            assets = []
            for row in rows:
                asset = Asset(
                    tenant_id=tenant_id,
                    name=row.get("name", "").strip(),
                    asset_type=row.get("asset_type", "").strip(),
                    owner=row.get("owner") or None,
                    location=row.get("location") or None,
                    status=row.get("status") or "active",
                    purchase_date=row.get("purchase_date") or None,
                    renewal_date=row.get("renewal_date") or None,
                    notes=row.get("notes") or None,
                    tags=row.get("tags") or None,
                )
                session.add(asset)
                assets.append(asset)

            await session.commit()
            for asset in assets:
                await session.refresh(asset)
            return assets

    async def update_asset(
        self, tenant_id: int, asset_id: int, data: dict[str, Any]
    ) -> Asset | None:
        """Update a tenant asset."""
        async with self.session() as session:
            result = await session.execute(
                select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id)
            )
            asset = result.scalar_one_or_none()
            if not asset:
                return None

            for field in (
                "name",
                "asset_type",
                "owner",
                "location",
                "status",
                "purchase_date",
                "renewal_date",
                "notes",
            ):
                if field in data and data[field] is not None:
                    setattr(asset, field, data[field])

            if "tags" in data:
                asset.tags = json.dumps(data["tags"]) if data["tags"] else None

            asset.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(asset)
            return asset

    async def delete_asset(self, tenant_id: int, asset_id: int) -> bool:
        """Delete a tenant asset."""
        async with self.session() as session:
            result = await session.execute(
                select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id)
            )
            asset = result.scalar_one_or_none()
            if not asset:
                return False
            await session.delete(asset)
            await session.commit()
            return True
