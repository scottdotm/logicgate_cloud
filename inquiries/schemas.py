from pydantic import BaseModel, EmailStr, Field


class InquiryCreateRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)
    organization: str | None = Field(None, max_length=255)
    lake_name: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    message: str | None = None
    interest: str = Field(default="lake_survey", max_length=50)
    part_107: str | None = Field(None, max_length=50)
    existing_clients: str | None = Field(None, max_length=50)


class InquiryResponse(BaseModel):
    id: int
    email: str
    name: str
    organization: str | None = None
    lake_name: str | None = None
    phone: str | None = None
    message: str | None = None
    interest: str
    part_107: str | None = None
    existing_clients: str | None = None
    status: str
    created_at: str


class InquiryCreateResponse(BaseModel):
    success: bool
    inquiry_id: int
    message: str
