"""Task tracker service for the security toolkit."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from logicgate_cloud.security_toolkit.common.service import TenantScopedService
from logicgate_cloud.security_toolkit.tasks.models import Task


class TaskService(TenantScopedService):
    """Service for managing security and IT tasks."""

    async def list_tasks(self, tenant_id: int) -> list[Task]:
        """List tasks for a tenant."""
        async with self.session() as session:
            result = await session.execute(
                select(Task).where(Task.tenant_id == tenant_id).order_by(Task.created_at.desc())
            )
            return list(result.scalars().all())

    async def get_task(self, tenant_id: int, task_id: int) -> Task | None:
        """Get a tenant task by ID."""
        async with self.session() as session:
            result = await session.execute(
                select(Task).where(Task.id == task_id, Task.tenant_id == tenant_id)
            )
            return result.scalar_one_or_none()

    async def create_task(self, tenant_id: int, plan: str, data: dict[str, Any]) -> Task:
        """Create a task."""
        async with self.session() as session:
            count_result = await session.execute(
                select(func.count(Task.id)).where(Task.tenant_id == tenant_id)
            )
            current_count = count_result.scalar() or 0
            await self.check_limit(tenant_id, "tasks", current_count, plan)

            task = Task(
                tenant_id=tenant_id,
                title=data["title"],
                description=data.get("description"),
                status=data.get("status") or "backlog",
                priority=data.get("priority") or "medium",
                severity=data.get("severity"),
                assignee_user_id=data.get("assignee_user_id"),
                due_date=data.get("due_date"),
                source_finding_id=data.get("source_finding_id"),
                source_assessment_id=data.get("source_assessment_id"),
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            return task

    async def create_tasks_from_findings(
        self, tenant_id: int, plan: str, finding_ids: list[int]
    ) -> list[Task]:
        """Create tasks from a list of security findings."""
        from logicgate_cloud.security_toolkit.common.models import SecurityFinding

        async with self.session() as session:
            count_result = await session.execute(
                select(func.count(Task.id)).where(Task.tenant_id == tenant_id)
            )
            current_count = count_result.scalar() or 0
            await self.check_limit(tenant_id, "tasks", current_count + len(finding_ids), plan)

            result = await session.execute(
                select(SecurityFinding).where(
                    SecurityFinding.id.in_(finding_ids),
                    SecurityFinding.tenant_id == tenant_id,
                )
            )
            findings = result.scalars().all()

            created_tasks = []
            for finding in findings:
                task = Task(
                    tenant_id=tenant_id,
                    title=f"Remediate: {finding.title}",
                    description=finding.recommendation,
                    status="backlog",
                    priority="high" if finding.severity in ("critical", "high") else "medium",
                    severity=finding.severity,
                    source_finding_id=finding.id,
                    source_assessment_id=finding.assessment_id,
                )
                session.add(task)
                created_tasks.append(task)

            await session.commit()
            for task in created_tasks:
                await session.refresh(task)
            return created_tasks

    async def update_task(self, tenant_id: int, task_id: int, data: dict[str, Any]) -> Task | None:
        """Update a tenant task."""
        async with self.session() as session:
            result = await session.execute(
                select(Task).where(Task.id == task_id, Task.tenant_id == tenant_id)
            )
            task = result.scalar_one_or_none()
            if not task:
                return None

            for field in (
                "title",
                "description",
                "status",
                "priority",
                "severity",
                "assignee_user_id",
                "due_date",
            ):
                if field in data and data[field] is not None:
                    setattr(task, field, data[field])

            task.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(task)
            return task

    async def delete_task(self, tenant_id: int, task_id: int) -> bool:
        """Delete a tenant task."""
        async with self.session() as session:
            result = await session.execute(
                select(Task).where(Task.id == task_id, Task.tenant_id == tenant_id)
            )
            task = result.scalar_one_or_none()
            if not task:
                return False
            await session.delete(task)
            await session.commit()
            return True
