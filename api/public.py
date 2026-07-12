import os
import tempfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from logicgate_cloud.inquiries.models import InquiryManager
from logicgate_cloud.inquiries.schemas import InquiryCreateRequest, InquiryCreateResponse
from logicgate_cloud.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    HealthResponse,
    PlanResponse,
    PublicPlansResponse,
    SignupRequest,
    SignupResponse,
)

router = APIRouter(prefix="/api/v1/public", tags=["public"])


# Lazily initialize managers to avoid heavy import-time work
def _get_shared_db_path() -> str:
    return os.environ.get("SHARED_DB_PATH", "logicgate_shared.db")


def _get_tenant_manager():
    from logicgate_cloud.tenant.multi_tenant import TenantManager

    return TenantManager(_get_shared_db_path())


def _get_tier_limits():
    from logicgate_cloud.billing.tier_manager import TierLimits

    return TierLimits


def _get_auth_manager():
    from logicgate_cloud.auth.multi_tenant_auth import MultiTenantAuth

    jwt_secret = os.environ.get("JWT_SECRET")
    if not jwt_secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
    return MultiTenantAuth(_get_shared_db_path(), jwt_secret)


def _get_email_service():
    from logicgate_cloud.notifications.email_triggers import EmailTriggerManager

    return EmailTriggerManager(_get_shared_db_path())


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse()


@router.get("/plans", response_model=PublicPlansResponse)
async def list_plans():
    tier_limits = _get_tier_limits()
    raw = tier_limits.get_all_tiers()

    plans = []
    for tier in raw:
        plans.append(
            PlanResponse(
                id=tier["id"],
                name=tier["name"],
                price=tier["price"],
                description=tier.get("description", f"{tier['name']} plan"),
                max_assets=tier["max_assets"],
                max_users=tier["max_users"],
                max_storage_gb=tier["max_storage_gb"],
                features=tier["features"],
            )
        )

    return PublicPlansResponse(plans=plans)


@router.post("/tenants", response_model=SignupResponse)
async def signup(request: SignupRequest):
    tenant_manager = _get_tenant_manager()
    auth_manager = _get_auth_manager()

    # Public API uses "freemium" but TenantManager uses "free"
    internal_plan = "free" if request.plan == "freemium" else request.plan

    try:
        tenant = tenant_manager.create_tenant(
            name=request.company,
            plan=internal_plan,
            trial_days=14 if internal_plan != "free" else 0,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Tenant creation failed: {e}") from e

    try:
        user_id = auth_manager.create_user(
            tenant_id=str(tenant.id),
            email=request.email,
            password=request.password,
            full_name=request.name,
            role="admin",
        )
        if not user_id:
            raise HTTPException(status_code=400, detail="User creation failed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"User creation failed: {e}") from e

    try:
        email_service = _get_email_service()
        trial_days = 14 if internal_plan != "free" else 0
        email_service.trigger_signup_email(
            request.email,
            request.name,
            request.company,
            internal_plan,
            trial_days,
        )
    except Exception:
        # Email is best-effort; don't fail signup if it breaks
        pass

    return SignupResponse(
        success=True,
        tenant_id=tenant.id,
        message="Pilot tenant created successfully.",
    )


@router.post("/stripe/webhook")
async def stripe_webhook(request):
    """Handle Stripe webhook events for subscription lifecycle."""
    stripe_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    stripe_api_key = os.environ.get("STRIPE_SECRET_KEY")
    if not stripe_secret or not stripe_api_key:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    import stripe

    stripe.api_key = stripe_api_key
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, stripe_secret)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload") from e
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature") from e

    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        customer_email = data.get("customer_details", {}).get("email")
        subscription_id = data.get("subscription")
        stripe_customer_id = data.get("customer")
        # Update the tenant record with subscription info
        _activate_subscription(customer_email, subscription_id, stripe_customer_id)

    elif event_type == "invoice.paid":
        subscription_id = data.get("subscription")
        _renew_subscription(subscription_id)

    elif event_type == "customer.subscription.deleted":
        subscription_id = data.get("id")
        _cancel_subscription(subscription_id)

    return {"status": "ok"}


def _activate_subscription(customer_email: str, subscription_id: str, stripe_customer_id: str):
    """Move a tenant from trial/freemium to active after successful checkout."""
    from logicgate_cloud.tenant.multi_tenant import TenantManager

    db_path = _get_shared_db_path()
    tenant_manager = TenantManager(db_path)
    auth_manager = _get_auth_manager()

    try:
        user = auth_manager.find_user_by_email(customer_email)
        if not user:
            return

        tenant = tenant_manager.get_tenant(user["tenant_id"])
        if not tenant:
            return

        tenant_manager.update_tenant(
            tenant.id,
            status="active",
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=subscription_id,
        )
    except Exception as e:
        # Webhook should return 200 even if internal update fails; log instead
        print(f"[STRIPE WEBHOOK] Failed to activate subscription: {e}")


def _renew_subscription(subscription_id: str):
    """Extend subscription period on invoice payment."""
    from logicgate_cloud.tenant.multi_tenant import TenantManager

    db_path = _get_shared_db_path()
    tenant_manager = TenantManager(db_path)
    try:
        tenant = tenant_manager.get_tenant_by_stripe_subscription(subscription_id)
        if tenant:
            tenant_manager.update_tenant(
                tenant.id,
                status="active",
                subscription_ends_at=None,
            )
    except Exception as e:
        print(f"[STRIPE WEBHOOK] Failed to renew subscription: {e}")


def _cancel_subscription(subscription_id: str):
    """Mark tenant as cancelled after Stripe subscription deletion."""
    from logicgate_cloud.tenant.multi_tenant import TenantManager

    db_path = _get_shared_db_path()
    tenant_manager = TenantManager(db_path)
    try:
        tenant = tenant_manager.get_tenant_by_stripe_subscription(subscription_id)
        if tenant:
            tenant_manager.update_tenant(tenant.id, status="cancelled")
    except Exception as e:
        print(f"[STRIPE WEBHOOK] Failed to cancel subscription: {e}")


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(request: CheckoutRequest):
    stripe_secret = os.environ.get("STRIPE_SECRET_KEY")
    if not stripe_secret:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    try:
        import stripe

        stripe.api_key = stripe_secret

        # Look up the price ID for the requested plan from environment variables
        price_id = os.environ.get(f"STRIPE_PRICE_{request.plan.upper()}")
        if not price_id:
            raise HTTPException(
                status_code=400, detail=f"No Stripe price configured for plan {request.plan}"
            )

        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )

        return CheckoutResponse(
            success=True,
            checkout_url=session.url,
            message="Checkout session created.",
        )
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=f"Stripe error: {e}") from e


@router.post("/inquiries", response_model=InquiryCreateResponse)
async def create_inquiry(request: InquiryCreateRequest):
    """Public endpoint for landing-page inquiries."""
    manager = InquiryManager(_get_shared_db_path())
    try:
        inquiry_id = manager.create(
            email=request.email,
            name=request.name,
            organization=request.organization,
            lake_name=request.lake_name,
            phone=request.phone,
            message=request.message,
            interest=request.interest,
            part_107=request.part_107,
            existing_clients=request.existing_clients,
        )
        return InquiryCreateResponse(
            success=True,
            inquiry_id=inquiry_id,
            message="Thank you. We will be in touch soon.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save inquiry: {e}") from e


@router.get("/inquiries/landing")
async def landing_page():
    """Serve the lake-survey landing page HTML."""
    static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
    html_path = os.path.join(static_dir, "lake-survey.html")
    try:
        with open(html_path, encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="Landing page not found") from e


@router.get("/partners/pitch")
async def partner_pitch_page():
    """Serve the partner pitch page HTML."""
    static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
    html_path = os.path.join(static_dir, "partner-pitch.html")
    try:
        with open(html_path, encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="Partner pitch page not found") from e


@router.get("/demo-report")
async def demo_report():
    """Generate and return a sample lake survey report."""
    from logicgate_cloud.lake.demo_report import generate_sample_report

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        output_path = tmp.name

    try:
        generate_sample_report(output_path)
        return FileResponse(
            output_path,
            media_type="application/pdf",
            filename="LogicGate_Lake_Survey_Sample_Report.pdf",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate demo report: {e}") from e
