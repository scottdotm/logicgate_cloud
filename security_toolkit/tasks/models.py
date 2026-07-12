"""Task tracker ORM models for the security toolkit."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from logicgate_cloud.security_toolkit.common.models import Base


class Task(Base):
    """Tenant-owned IT/security task."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="backlog")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    assignee_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_finding_id: Mapped[int | None] = mapped_column(
        ForeignKey("security_findings.id", ondelete="SET NULL"), nullable=True
    )
    source_assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("security_assessments.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    def __repr__(self) -> str:
        return f"<Task id={self.id} tenant_id={self.tenant_id} title={self.title[:30]}>"
