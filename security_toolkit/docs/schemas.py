"""Pydantic schemas for IT documentation."""

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    doc_type: str = Field(..., min_length=1, max_length=50)
    content: str
    parent_id: int | None = None
    tags: list[str] | None = None
    status: str | None = "draft"


class DocumentUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    doc_type: str | None = None
    content: str | None = None
    parent_id: int | None = None
    tags: list[str] | None = None
    status: str | None = None


class DocumentResponse(BaseModel):
    id: int
    tenant_id: int
    parent_id: int | None
    title: str
    doc_type: str
    content: str
    tags: list[str] | None
    status: str
    created_at: datetime
    updated_at: datetime
