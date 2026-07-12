"""Pydantic schemas for the task tracker."""

from datetime import datetime

from pydantic import BaseModel, Field


class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    status: str | None = "backlog"
    priority: str | None = "medium"
    severity: str | None = None
    assignee_user_id: int | None = None
    due_date: datetime | None = None
    source_finding_id: int | None = None
    source_assessment_id: int | None = None


class TaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    severity: str | None = None
    assignee_user_id: int | None = None
    due_date: datetime | None = None


class TaskResponse(BaseModel):
    id: int
    tenant_id: int
    title: str
    description: str | None
    status: str
    priority: str
    severity: str | None
    assignee_user_id: int | None
    due_date: datetime | None
    source_finding_id: int | None
    source_assessment_id: int | None
    created_at: datetime
    updated_at: datetime


class BulkCreateFromFindingsRequest(BaseModel):
    finding_ids: list[int]
