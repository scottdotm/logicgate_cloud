"""Policy service for the security toolkit."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from logicgate_cloud.security_toolkit.common.service import TenantScopedService
from logicgate_cloud.security_toolkit.policies.models import Policy, PolicyTemplate
from logicgate_cloud.security_toolkit.policies.templates import (
    BUILT_IN_POLICIES,
    BUILT_IN_POLICY_INDEX,
)


class PolicyService(TenantScopedService):
    """Service for managing policy templates and tenant policies."""

    async def seed_templates(self) -> int:
        """Ensure built-in policy templates exist in the database."""
        async with self.session() as session:
            count = 0
            for template in BUILT_IN_POLICIES:
                result = await session.execute(
                    select(PolicyTemplate).where(PolicyTemplate.key == template.key)
                )
                existing = result.scalar_one_or_none()
                if not existing:
                    session.add(
                        PolicyTemplate(
                            key=template.key,
                            title=template.title,
                            content=template.content,
                            nist_function=template.nist_function,
                            nist_category=template.nist_category,
                        )
                    )
                    count += 1
            await session.commit()
            return count

    async def list_templates(self) -> list[PolicyTemplate]:
        """List all built-in policy templates."""
        async with self.session() as session:
            result = await session.execute(select(PolicyTemplate))
            return list(result.scalars().all())

    async def get_template(self, key: str) -> PolicyTemplate | None:
        """Get a single built-in template by key."""
        async with self.session() as session:
            result = await session.execute(select(PolicyTemplate).where(PolicyTemplate.key == key))
            return result.scalar_one_or_none()

    async def list_policies(self, tenant_id: int) -> list[Policy]:
        """List policies for a tenant."""
        async with self.session() as session:
            result = await session.execute(
                select(Policy)
                .where(Policy.tenant_id == tenant_id)
                .order_by(Policy.updated_at.desc())
            )
            return list(result.scalars().all())

    async def get_policy(self, tenant_id: int, policy_id: int) -> Policy | None:
        """Get a tenant policy by ID."""
        async with self.session() as session:
            result = await session.execute(
                select(Policy).where(Policy.id == policy_id, Policy.tenant_id == tenant_id)
            )
            return result.scalar_one_or_none()

    async def create_policy(self, tenant_id: int, plan: str, data: dict[str, Any]) -> Policy:
        """Create a policy, optionally from a template."""
        async with self.session() as session:
            count_result = await session.execute(
                select(func.count(Policy.id)).where(Policy.tenant_id == tenant_id)
            )
            current_count = count_result.scalar() or 0
            await self.check_limit(tenant_id, "policies", current_count, plan)

            template_key = data.get("template_key")
            if template_key:
                template = BUILT_IN_POLICY_INDEX.get(template_key)
                if not template:
                    raise ValueError(f"Unknown template key: {template_key}")
                policy = Policy(
                    tenant_id=tenant_id,
                    template_key=template_key,
                    title=data.get("title") or template.title,
                    content=data.get("content") or template.content,
                    nist_function=data.get("nist_function") or template.nist_function,
                    nist_category=data.get("nist_category") or template.nist_category,
                    status=data.get("status") or "draft",
                )
            else:
                policy = Policy(
                    tenant_id=tenant_id,
                    title=data["title"],
                    content=data.get("content") or "",
                    nist_function=data.get("nist_function"),
                    nist_category=data.get("nist_category"),
                    status=data.get("status") or "draft",
                )

            session.add(policy)
            await session.commit()
            await session.refresh(policy)
            return policy

    async def update_policy(
        self, tenant_id: int, policy_id: int, data: dict[str, Any]
    ) -> Policy | None:
        """Update a tenant policy."""
        async with self.session() as session:
            result = await session.execute(
                select(Policy).where(Policy.id == policy_id, Policy.tenant_id == tenant_id)
            )
            policy = result.scalar_one_or_none()
            if not policy:
                return None

            for field in ("title", "content", "status"):
                if field in data and data[field] is not None:
                    setattr(policy, field, data[field])
            policy.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(policy)
            return policy

    async def delete_policy(self, tenant_id: int, policy_id: int) -> bool:
        """Delete a tenant policy."""
        async with self.session() as session:
            result = await session.execute(
                select(Policy).where(Policy.id == policy_id, Policy.tenant_id == tenant_id)
            )
            policy = result.scalar_one_or_none()
            if not policy:
                return False
            await session.delete(policy)
            await session.commit()
            return True
