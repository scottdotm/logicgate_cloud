"""Pydantic schemas for the asset inventory."""

from datetime import datetime

from pydantic import BaseModel, Field


class AssetCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    asset_type: str = Field(..., min_length=1, max_length=50)
    owner: str | None = None
    location: str | None = None
    status: str | None = "active"
    purchase_date: str | None = None
    renewal_date: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


class AssetUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    asset_type: str | None = None
    owner: str | None = None
    location: str | None = None
    status: str | None = None
    purchase_date: str | None = None
    renewal_date: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


class AssetResponse(BaseModel):
    id: int
    tenant_id: int
    name: str
    asset_type: str
    owner: str | None
    location: str | None
    status: str
    purchase_date: str | None
    renewal_date: str | None
    notes: str | None
    tags: list[str] | None
    created_at: datetime
    updated_at: datetime
