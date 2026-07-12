"""Pydantic schemas for policies."""

from datetime import datetime

from pydantic import BaseModel, Field


class PolicyTemplateResponse(BaseModel):
    key: str
    title: str
    nist_function: str | None
    nist_category: str | None


class PolicyTemplateDetailResponse(PolicyTemplateResponse):
    content: str


class PolicyCreateRequest(BaseModel):
    template_key: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = None
    nist_function: str | None = None
    nist_category: str | None = None


class PolicyUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = None
    status: str | None = None


class PolicyResponse(BaseModel):
    id: int
    tenant_id: int
    template_key: str | None
    title: str
    content: str
    nist_function: str | None
    nist_category: str | None
    status: str
    created_at: datetime
    updated_at: datetime
