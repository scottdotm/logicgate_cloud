"""Documentation service for the security toolkit."""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from logicgate_cloud.security_toolkit.common.service import TenantScopedService
from logicgate_cloud.security_toolkit.docs.models import Document


class DocumentService(TenantScopedService):
    """Service for managing IT documentation and runbooks."""

    async def list_documents(self, tenant_id: int) -> list[Document]:
        """List documents for a tenant."""
        async with self.session() as session:
            result = await session.execute(
                select(Document)
                .where(Document.tenant_id == tenant_id)
                .order_by(Document.updated_at.desc())
            )
            return list(result.scalars().all())

    async def get_document(self, tenant_id: int, document_id: int) -> Document | None:
        """Get a tenant document by ID."""
        async with self.session() as session:
            result = await session.execute(
                select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
            )
            return result.scalar_one_or_none()

    async def create_document(self, tenant_id: int, plan: str, data: dict[str, Any]) -> Document:
        """Create a document."""
        async with self.session() as session:
            count_result = await session.execute(
                select(func.count(Document.id)).where(Document.tenant_id == tenant_id)
            )
            current_count = count_result.scalar() or 0
            await self.check_limit(tenant_id, "docs", current_count, plan)

            doc = Document(
                tenant_id=tenant_id,
                parent_id=data.get("parent_id"),
                title=data["title"],
                doc_type=data["doc_type"],
                content=data.get("content", ""),
                tags=json.dumps(data["tags"]) if data.get("tags") else None,
                status=data.get("status") or "draft",
            )
            session.add(doc)
            await session.commit()
            await session.refresh(doc)
            return doc

    async def update_document(
        self, tenant_id: int, document_id: int, data: dict[str, Any]
    ) -> Document | None:
        """Update a tenant document."""
        async with self.session() as session:
            result = await session.execute(
                select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
            )
            doc = result.scalar_one_or_none()
            if not doc:
                return None

            for field in ("title", "doc_type", "content", "status"):
                if field in data and data[field] is not None:
                    setattr(doc, field, data[field])

            if "parent_id" in data:
                doc.parent_id = data["parent_id"]
            if "tags" in data:
                doc.tags = json.dumps(data["tags"]) if data["tags"] else None

            doc.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(doc)
            return doc

    async def delete_document(self, tenant_id: int, document_id: int) -> bool:
        """Delete a tenant document."""
        async with self.session() as session:
            result = await session.execute(
                select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
            )
            doc = result.scalar_one_or_none()
            if not doc:
                return False
            await session.delete(doc)
            await session.commit()
            return True
