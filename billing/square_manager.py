"""Square billing integration for LogicGate multi-tenant SaaS."""

import base64
import hashlib
import hmac
import os
import uuid
from typing import Any

from square import Square
from square.environment import SquareEnvironment


class SquareBillingManager:
    """Manages Square checkout and subscription lifecycle."""

    def __init__(
        self,
        access_token: str | None = None,
        location_id: str | None = None,
        shared_db_path: str | None = None,
        webhook_secret: str | None = None,
        environment: str | None = None,
    ):
        self.access_token = access_token or os.environ.get("SQUARE_ACCESS_TOKEN")
        self.location_id = location_id or os.environ.get("SQUARE_LOCATION_ID")
        self.webhook_secret = webhook_secret or os.environ.get("SQUARE_WEBHOOK_SECRET")
        self.shared_db_path = shared_db_path or os.environ.get(
            "SHARED_DB_PATH", "logicgate_shared.db"
        )
        self.environment = self._resolve_environment(
            environment or os.environ.get("SQUARE_ENVIRONMENT", "production")
        )

        self.plans = {
            "starter": {
                "name": "Starter",
                "price_monthly": 4900,  # $49.00 in cents
                "price_yearly": 49000,
                "max_assets": 10,
                "max_users": 5,
            },
            "professional": {
                "name": "Professional",
                "price_monthly": 19900,  # $199.00 in cents
                "price_yearly": 199000,
                "max_assets": 100,
                "max_users": 25,
            },
            "enterprise": {
                "name": "Enterprise",
                "price_monthly": 99900,  # $999.00 in cents
                "price_yearly": 999000,
                "max_assets": -1,
                "max_users": -1,
            },
        }

        # Reverse-lookup map from SQUARE_PLAN_ID_* environment variables to
        # LogicGate plan IDs.
        self._square_plan_to_logicgate_plan: dict[str, str] = {}
        for plan in self.plans:
            plan_id = os.environ.get(f"SQUARE_PLAN_ID_{plan.upper()}")
            if plan_id:
                self._square_plan_to_logicgate_plan[plan_id] = plan

    def _resolve_environment(self, environment: str | SquareEnvironment) -> SquareEnvironment:
        if isinstance(environment, SquareEnvironment):
            return environment
        if str(environment).upper() == "SANDBOX":
            return SquareEnvironment.SANDBOX
        return SquareEnvironment.PRODUCTION

    def _client(self) -> Square:
        if not self.access_token:
            raise RuntimeError("SQUARE_ACCESS_TOKEN is not configured")
        return Square(token=self.access_token, environment=self.environment)

    def _get_plan_for_variation(self, plan_variation_id: str | None) -> str | None:
        return self._square_plan_to_logicgate_plan.get(plan_variation_id)

    def create_checkout(self, plan: str, success_url: str, cancel_url: str | None = None) -> str:
        """Create a Square subscription checkout link for the requested plan."""
        plan_config = self.plans.get(plan)
        if not plan_config:
            raise ValueError(f"Invalid plan: {plan}")

        plan_id = os.environ.get(f"SQUARE_PLAN_ID_{plan.upper()}")
        if not plan_id:
            raise RuntimeError(f"SQUARE_PLAN_ID_{plan.upper()} is not configured")

        client = self._client()

        if not self.location_id:
            raise RuntimeError("SQUARE_LOCATION_ID is not configured")

        response = client.checkout.payment_links.create(
            idempotency_key=str(uuid.uuid4()),
            quick_pay={
                "name": f"LogicGate {plan_config['name']} Plan",
                "price_money": {
                    "amount": plan_config["price_monthly"],
                    "currency": "USD",
                },
                "location_id": self.location_id,
            },
            checkout_options={
                "subscription_plan_id": plan_id,
                "redirect_url": success_url,
            },
        )

        if response.errors:
            raise RuntimeError(f"Square checkout error: {response.errors}")

        return response.payment_link.url

    def verify_signature(self, payload: bytes | str, signature: str, notification_url: str) -> bool:
        """Verify a Square webhook HMAC-SHA256 signature."""
        if not self.webhook_secret or not signature:
            return False

        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")

        content = notification_url + payload
        digest = hmac.new(
            self.webhook_secret.encode("utf-8"),
            content.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected, signature)

    def handle_webhook_event(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Update the tenant record based on a Square webhook event.

        Returns a dict with the affected tenant_id and action, or None when
        the event does not require a tenant update.
        """
        from logicgate_cloud.tenant.multi_tenant import TenantManager

        tenant_manager = TenantManager(self.shared_db_path)
        event_type = event.get("type")
        data = event.get("data", {})
        obj = data.get("object", {})

        if event_type == "subscription.created":
            subscription = obj.get("subscription", {})
            customer_id = subscription.get("customer_id")
            subscription_id = subscription.get("id")
            plan_variation_id = subscription.get("plan_variation_id")
            status = subscription.get("status")
            if not customer_id or not subscription_id:
                return None

            plan = self._get_plan_for_variation(plan_variation_id)
            tenant = tenant_manager.get_tenant_by_square_customer(customer_id)

            if tenant is None:
                tenant = tenant_manager.create_tenant(
                    name=f"Square Customer {customer_id[-8:]}",
                    plan=plan or "free",
                    trial_days=0,
                )

            if plan:
                tenant_manager.update_tenant_plan(tenant.id, plan)

            tenant_manager.update_tenant(
                tenant.id,
                square_customer_id=customer_id,
                square_subscription_id=subscription_id,
                status="active" if status == "ACTIVE" else "trial",
            )
            return {"tenant_id": tenant.id, "action": "subscription_created"}

        if event_type == "subscription.updated":
            subscription = obj.get("subscription", {})
            customer_id = subscription.get("customer_id")
            subscription_id = subscription.get("id")
            status = subscription.get("status")
            if not subscription_id:
                return None

            tenant = tenant_manager.get_tenant_by_square_subscription(subscription_id)
            if tenant is None and customer_id:
                tenant = tenant_manager.get_tenant_by_square_customer(customer_id)
            if tenant is None:
                return None

            new_status = tenant.status.value
            if status == "ACTIVE":
                new_status = "active"
            elif status == "CANCELED":
                new_status = "cancelled"
            elif status == "PENDING":
                new_status = "trial"

            tenant_manager.update_tenant(
                tenant.id,
                square_customer_id=customer_id or tenant.square_customer_id,
                square_subscription_id=subscription_id,
                status=new_status,
            )
            return {"tenant_id": tenant.id, "action": f"subscription_{new_status}"}

        if event_type == "invoice.payment_made":
            invoice = obj.get("invoice", {})
            subscription_id = invoice.get("subscription_id")
            recipient = invoice.get("primary_recipient", {})
            customer_id = recipient.get("customer_id")
            email = recipient.get("email_address")
            if not customer_id:
                return None

            tenant = tenant_manager.get_tenant_by_square_customer(customer_id)
            if tenant is None and subscription_id:
                tenant = tenant_manager.get_tenant_by_square_subscription(subscription_id)
            if tenant is None and email:
                tenant = self._find_tenant_by_email(tenant_manager, email)

            if tenant is None:
                return None

            tenant_manager.update_tenant(
                tenant.id,
                status="active",
                square_customer_id=customer_id,
                square_subscription_id=subscription_id or tenant.square_subscription_id,
            )
            return {"tenant_id": tenant.id, "action": "payment_made"}

        return None

    def _find_tenant_by_email(self, tenant_manager, email: str):
        """Find a tenant by looking up a user email in the auth system."""
        from logicgate_cloud.auth.multi_tenant_auth import MultiTenantAuth

        jwt_secret = os.environ.get("JWT_SECRET")
        if not jwt_secret:
            return None

        auth = MultiTenantAuth(tenant_manager.shared_db_path, jwt_secret)
        user = auth.find_user_by_email(email)
        if not user:
            return None

        tenant_id = user.get("tenant_id")
        if not tenant_id:
            return None

        return tenant_manager.get_tenant(int(tenant_id))
