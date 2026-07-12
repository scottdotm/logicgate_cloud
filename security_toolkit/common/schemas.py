"""Pydantic v2 request/response schemas for the security toolkit."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from logicgate_cloud.security_toolkit.common.models import (
    AssessmentType,
)


class FreeScanRequest(BaseModel):
    """Public request to run a free external scan."""

    domain: str = Field(..., min_length=3, max_length=255, examples=["example.com"])

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        value = value.strip().lower()
        if value.startswith(("http://", "https://")):
            value = value.split("//", 1)[1]
        if "/" in value:
            value = value.split("/", 1)[0]
        return value


class FreeScanSummary(BaseModel):
    """Summary returned by the free external scan."""

    domain: str
    overall_score: float = Field(..., ge=0.0, le=5.0)
    rating: str
    checks_performed: list[str]
    top_findings: list[dict[str, Any]]


class AssessmentCreateRequest(BaseModel):
    """Portal request to create a new assessment."""

    domain: str | None = Field(default=None, min_length=3, max_length=255)
    assessment_type: AssessmentType = Field(default=AssessmentType.PAID_FULL)


class AssessmentResponse(BaseModel):
    """Basic assessment metadata."""

    id: int
    tenant_id: int
    domain: str | None
    status: str
    assessment_type: str
    nist_score: float | None
    created_at: datetime
    completed_at: datetime | None


class FindingResponse(BaseModel):
    """Detailed finding returned in reports and lists."""

    id: int
    assessment_id: int
    nist_function: str
    nist_category: str | None
    severity: str
    title: str
    description: str
    evidence: dict | None
    recommendation: str
    effort: str | None


class AnswerSubmission(BaseModel):
    """Single questionnaire answer."""

    question_key: str
    answer: str | None
    notes: str | None = None


class AnswerSubmitRequest(BaseModel):
    """Batch submission of questionnaire answers."""

    answers: list[AnswerSubmission]


class ReportResponse(BaseModel):
    """Report download metadata."""

    assessment_id: int
    download_url: str
    generated_at: datetime


class ScanResult(BaseModel):
    """Internal scan result used by the scanner and engine."""

    domain: str
    overall_score: float
    checks: list[dict[str, Any]]
    findings: list[dict[str, Any]]
