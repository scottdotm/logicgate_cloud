from pydantic import BaseModel, EmailStr, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "logicgate_cloud"


class PlanResponse(BaseModel):
    id: str
    name: str
    price: int
    description: str
    max_assets: int
    max_users: int
    max_storage_gb: int
    features: list[str]


class PublicPlansResponse(BaseModel):
    plans: list[PlanResponse]


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str
    company: str
    plan: str = "freemium"


class SignupResponse(BaseModel):
    success: bool
    tenant_id: int | None = None
    message: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    success: bool
    token: str | None = None
    message: str


class SubscriptionResponse(BaseModel):
    tenant_id: int
    plan: str
    status: str
    trial_ends_at: str | None = None
    subscription_ends_at: str | None = None
    max_assets: int
    max_users: int
    max_storage_gb: int


class CheckoutRequest(BaseModel):
    plan: str
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    success: bool
    checkout_url: str | None = None
    message: str
