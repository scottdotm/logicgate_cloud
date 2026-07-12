import os

from fastapi import APIRouter, HTTPException, Request

from logicgate_cloud.schemas import LoginRequest, LoginResponse, SubscriptionResponse

router = APIRouter(prefix="/api/v1/portal", tags=["portal"])


def _get_shared_db_path() -> str:
    return os.environ.get("SHARED_DB_PATH", "logicgate_shared.db")


def _get_auth_manager():
    from logicgate_cloud.auth.multi_tenant_auth import AuthMiddleware, MultiTenantAuth

    jwt_secret = os.environ.get("JWT_SECRET")
    if not jwt_secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")

    auth = MultiTenantAuth(_get_shared_db_path(), jwt_secret)
    return AuthMiddleware(auth)


async def _get_current_user(request: Request):
    auth = _get_auth_manager()
    user_info = auth.authenticate_request(request)
    if not user_info:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_info


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    auth = _get_auth_manager()

    try:
        result = auth.auth.authenticate_user_by_email(request.email, request.password)
        if result:
            token = auth.auth.generate_jwt(result)
            return LoginResponse(success=True, token=token, message="Login successful")
        return LoginResponse(success=False, token=None, message="Invalid credentials")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {e}") from e


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(request: Request):
    user_info = await _get_current_user(request)
    tenant_id = user_info.get("tenant_id")

    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context missing")

    from logicgate_cloud.tenant.multi_tenant import TenantManager

    try:
        manager = TenantManager(_get_shared_db_path())
        tenant = manager.get_tenant(int(tenant_id))
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Public API uses "freemium" for the free tier
        plan_value = tenant.plan.value if hasattr(tenant.plan, "value") else tenant.plan
        public_plan = "freemium" if plan_value == "free" else plan_value

        return SubscriptionResponse(
            tenant_id=tenant.id,
            plan=public_plan,
            status=tenant.status,
            trial_ends_at=tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
            subscription_ends_at=tenant.subscription_ends_at.isoformat()
            if tenant.subscription_ends_at
            else None,
            max_assets=tenant.max_assets,
            max_users=tenant.max_users,
            max_storage_gb=tenant.storage_quota_mb // 1024,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load subscription: {e}") from e
