from datetime import datetime

from pydantic import BaseModel, Field


class LakeCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    body_id: str | None = Field(None, max_length=128)
    location: str | None = Field(None, max_length=255)
    boundary_geojson: str | None = None
    area_sqm: float | None = None
    notes: str | None = None


class LakeUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    body_id: str | None = Field(None, max_length=128)
    location: str | None = Field(None, max_length=255)
    boundary_geojson: str | None = None
    area_sqm: float | None = None
    notes: str | None = None


class LakeResponse(BaseModel):
    id: int
    tenant_id: int
    name: str
    body_id: str | None = None
    location: str | None = None
    boundary_geojson: str | None = None
    area_sqm: float | None = None
    notes: str | None = None
    created_at: str
    updated_at: str | None = None


class SurveyCreateRequest(BaseModel):
    lake_id: int
    name: str = Field(..., min_length=1, max_length=255)
    scheduled_at: datetime | None = None
    pilot_name: str | None = Field(None, max_length=128)
    drone_name: str | None = Field(None, max_length=128)
    altitude_m: float | None = None
    notes: str | None = None


class SurveyUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    scheduled_at: datetime | None = None
    pilot_name: str | None = Field(None, max_length=128)
    drone_name: str | None = Field(None, max_length=128)
    altitude_m: float | None = None
    notes: str | None = None
    status: str | None = None


class SurveyResponse(BaseModel):
    id: int
    tenant_id: int
    lake_id: int
    name: str
    status: str
    scheduled_at: str | None = None
    completed_at: str | None = None
    pilot_name: str | None = None
    drone_name: str | None = None
    altitude_m: float | None = None
    image_count: int
    notes: str | None = None
    created_at: str
    updated_at: str | None = None


class SurveyImageResponse(BaseModel):
    id: int
    tenant_id: int
    survey_id: int
    filename: str
    original_path: str
    thumbnail_path: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude_m: float | None = None
    captured_at: str | None = None
    created_at: str


class SurveyListResponse(BaseModel):
    surveys: list[SurveyResponse]


class LakeListResponse(BaseModel):
    lakes: list[LakeResponse]
