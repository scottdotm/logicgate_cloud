"""SQLAlchemy ORM models for the security toolkit."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for security toolkit ORM models."""


class AssessmentStatus(StrEnum):
    """Lifecycle states for a security assessment."""

    PENDING = "pending"
    SCANNING = "scanning"
    AWAITING_INPUT = "awaiting_input"
    COMPLETE = "complete"
    FAILED = "failed"


class AssessmentType(StrEnum):
    """Types of assessment offered."""

    FREE_EXTERNAL = "free_external"
    PAID_FULL = "paid_full"


class Severity(StrEnum):
    """Finding severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class SecurityAssessment(Base):
    """A tenant-scoped security assessment."""

    __tablename__ = "security_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=AssessmentStatus.PENDING
    )
    assessment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    nist_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    report_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    findings: Mapped[list["SecurityFinding"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan", lazy="selectin"
    )
    answers: Mapped[list["QuestionnaireAnswer"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<SecurityAssessment id={self.id} tenant_id={self.tenant_id} status={self.status}>"


class SecurityFinding(Base):
    """A single finding from an assessment."""

    __tablename__ = "security_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("security_assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    nist_function: Mapped[str] = mapped_column(String(50), nullable=False)
    nist_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    effort: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    assessment: Mapped["SecurityAssessment"] = relationship(back_populates="findings")

    def __repr__(self) -> str:
        return f"<SecurityFinding id={self.id} severity={self.severity} title={self.title[:30]}>"


class QuestionnaireAnswer(Base):
    """A tenant's answer to a questionnaire question."""

    __tablename__ = "questionnaire_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("security_assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    question_key: Mapped[str] = mapped_column(String(100), nullable=False)
    answer: Mapped[str | None] = mapped_column(String(50), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    assessment: Mapped["SecurityAssessment"] = relationship(back_populates="answers")

    def __repr__(self) -> str:
        return f"<QuestionnaireAnswer id={self.id} question_key={self.question_key}>"
