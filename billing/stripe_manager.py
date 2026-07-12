"""
Stripe Billing Integration for LogicGate Multi-Tenant SaaS

This system handles:
- Customer creation and management
- Subscription creation and updates
- Payment processing
- Webhook handling
- Invoice management
- Usage-based billing
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Any

import stripe


class StripeBillingManager:
    """Manages Stripe billing operations"""

    def __init__(self, stripe_secret_key: str, shared_db_path: str, webhook_secret: str = None):
        stripe.api_key = stripe_secret_key
        self.shared_db_path = shared_db_path
        self.webhook_secret = webhook_secret

        # Plan configuration
        self.plans = {
            "starter": {
                "name": "Starter",
                "price_monthly": 4900,  # $49.00 in cents
                "price_yearly": 49000,  # $490.00 in cents
                "max_assets": 10,
                "max_users": 5,
                "api_rate_limit": 100,
            },
            "professional": {
                "name": "Professional",
                "price_monthly": 19900,  # $199.00 in cents
                "price_yearly": 199000,  # $1990.00 in cents
                "max_assets": 100,
                "max_users": 25,
                "api_rate_limit": 500,
            },
            "enterprise": {
                "name": "Enterprise",
                "price_monthly": 99900,  # $999.00 in cents
                "price_yearly": 999000,  # $9990.00 in cents
                "max_assets": -1,  # Unlimited
                "max_users": -1,  # Unlimited
                "api_rate_limit": 5000,
            },
        }

    def create_customer(
        self, tenant_id: str, email: str, name: str, payment_method_id: str = None
    ) -> str | None:
        """Create a Stripe customer for a tenant"""
        try:
            customer_data = {"email": email, "name": name, "metadata": {"tenant_id": tenant_id}}

            if payment_method_id:
                customer_data["payment_method"] = payment_method_id
                customer_data["invoice_settings"] = {"default_payment_method": payment_method_id}

            customer = stripe.Customer.create(**customer_data)

            # Update tenant with Stripe customer ID
            self._update_tenant_stripe_id(tenant_id, customer.id)

            return customer.id
        except Exception as e:
            print(f"Error creating Stripe customer: {e}")
            return None

    def _update_tenant_stripe_id(self, tenant_id: str, stripe_customer_id: str):
        """Update tenant with Stripe customer ID"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE tenants SET stripe_customer_id = ? WHERE tenant_id = ?",
            (stripe_customer_id, tenant_id),
        )

        conn.commit()
        conn.close()

    def create_subscription(
        self, tenant_id: str, plan_id: str, billing_interval: str = "month"
    ) -> str | None:
        """Create a subscription for a tenant"""
        try:
            # Get tenant's Stripe customer ID
            stripe_customer_id = self._get_tenant_stripe_id(tenant_id)

            if not stripe_customer_id:
                raise ValueError("Tenant does not have a Stripe customer ID")

            # Get plan configuration
            plan_config = self.plans.get(plan_id)
            if not plan_config:
                raise ValueError(f"Invalid plan: {plan_id}")

            # Create subscription
            subscription = stripe.Subscription.create(
                customer=stripe_customer_id,
                items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {"name": f"LogicGate {plan_config['name']} Plan"},
                            "unit_amount": plan_config["price_monthly"]
                            if billing_interval == "month"
                            else plan_config["price_yearly"],
                            "recurring": {"interval": billing_interval},
                        },
                        "quantity": 1,
                    }
                ],
                metadata={"tenant_id": tenant_id, "plan_id": plan_id},
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"],
            )

            # Update tenant subscription
            self._update_tenant_subscription(tenant_id, plan_id, subscription.id, billing_interval)

            return subscription.id
        except Exception as e:
            print(f"Error creating subscription: {e}")
            return None

    def _get_tenant_stripe_id(self, tenant_id: str) -> str | None:
        """Get Stripe customer ID for a tenant"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT stripe_customer_id FROM tenants WHERE tenant_id = ?", (tenant_id,))

        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None

    def _update_tenant_subscription(
        self, tenant_id: str, plan_id: str, subscription_id: str, billing_interval: str
    ):
        """Update tenant subscription information"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        # Calculate renewal date
        renewal_date = datetime.now() + timedelta(days=30 if billing_interval == "month" else 365)

        cursor.execute(
            """
            UPDATE tenants
            SET subscription_tier = ?, subscription_renews_at = ?
            WHERE tenant_id = ?
            """,
            (plan_id, renewal_date.isoformat(), tenant_id),
        )

        conn.commit()
        conn.close()

    def update_subscription(self, subscription_id: str, new_plan_id: str) -> bool:
        """Update an existing subscription to a new plan"""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)

            # Get new plan configuration
            new_plan_config = self.plans.get(new_plan_id)
            if not new_plan_config:
                raise ValueError(f"Invalid plan: {new_plan_id}")

            # Update subscription item
            stripe.SubscriptionItem.modify(
                subscription["items"]["data"][0].id,
                price_data={
                    "currency": "usd",
                    "product_data": {"name": f"LogicGate {new_plan_config['name']} Plan"},
                    "unit_amount": new_plan_config["price_monthly"],
                    "recurring": {
                        "interval": subscription["items"]["data"][0].price.recurring.interval
                    },
                },
            )

            # Update metadata
            stripe.Subscription.modify(subscription_id, metadata={"plan_id": new_plan_id})

            return True
        except Exception as e:
            print(f"Error updating subscription: {e}")
            return False

    def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> bool:
        """Cancel a subscription"""
        try:
            stripe.Subscription.delete(subscription_id, at_period_end=at_period_end)
            return True
        except Exception as e:
            print(f"Error cancelling subscription: {e}")
            return False

    def create_payment_intent(
        self, tenant_id: str, amount: int, description: str = None
    ) -> dict[str, Any] | None:
        """Create a payment intent for one-time payments"""
        try:
            stripe_customer_id = self._get_tenant_stripe_id(tenant_id)

            if not stripe_customer_id:
                raise ValueError("Tenant does not have a Stripe customer ID")

            payment_intent = stripe.PaymentIntent.create(
                amount=amount,
                currency="usd",
                customer=stripe_customer_id,
                description=description,
                metadata={"tenant_id": tenant_id},
            )

            return {
                "client_secret": payment_intent.client_secret,
                "payment_intent_id": payment_intent.id,
            }
        except Exception as e:
            print(f"Error creating payment intent: {e}")
            return None

    def handle_webhook(self, payload: str, sig_header: str) -> bool:
        """Handle Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, self.webhook_secret)

            # Handle different event types
            if event["type"] == "invoice.payment_succeeded":
                self._handle_payment_succeeded(event["data"]["object"])
            elif event["type"] == "invoice.payment_failed":
                self._handle_payment_failed(event["data"]["object"])
            elif event["type"] == "customer.subscription.deleted":
                self._handle_subscription_deleted(event["data"]["object"])
            elif event["type"] == "customer.subscription.updated":
                self._handle_subscription_updated(event["data"]["object"])

            return True
        except Exception as e:
            print(f"Error handling webhook: {e}")
            return False

    def _handle_payment_succeeded(self, invoice: dict[str, Any]):
        """Handle successful payment"""
        subscription_id = invoice.get("subscription")
        if subscription_id:
            # Renew subscription in database
            self._renew_subscription(subscription_id)

    def _handle_payment_failed(self, invoice: dict[str, Any]):
        """Handle failed payment"""
        subscription_id = invoice.get("subscription")
        if subscription_id:
            # Mark subscription as overdue
            self._mark_subscription_overdue(subscription_id)

    def _handle_subscription_deleted(self, subscription: dict[str, Any]):
        """Handle subscription cancellation"""
        tenant_id = subscription.get("metadata", {}).get("tenant_id")
        if tenant_id:
            # Downgrade to free tier or suspend
            self._suspend_tenant(tenant_id)

    def _handle_subscription_updated(self, subscription: dict[str, Any]):
        """Handle subscription update"""
        tenant_id = subscription.get("metadata", {}).get("tenant_id")
        plan_id = subscription.get("metadata", {}).get("plan_id")

        if tenant_id and plan_id:
            # Update tenant tier
            self._update_tenant_subscription(tenant_id, plan_id, subscription["id"], "month")

    def _renew_subscription(self, subscription_id: str):
        """Renew subscription in database"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        # Get tenant_id from subscription metadata (would need to store this)
        # For now, just update renewal date
        renewal_date = datetime.now() + timedelta(days=30)

        cursor.execute(
            "UPDATE tenants SET subscription_renews_at = ? WHERE stripe_customer_id IN (SELECT stripe_customer_id FROM tenants WHERE stripe_customer_id IS NOT NULL)",
            (renewal_date.isoformat(),),
        )

        conn.commit()
        conn.close()

    def _mark_subscription_overdue(self, subscription_id: str):
        """Mark subscription as overdue"""
        # Implementation would update tenant status
        pass

    def _suspend_tenant(self, tenant_id: str):
        """Suspend tenant due to subscription cancellation"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute("UPDATE tenants SET status = 'suspended' WHERE tenant_id = ?", (tenant_id,))

        conn.commit()
        conn.close()

    def get_subscription_status(self, tenant_id: str) -> dict[str, Any] | None:
        """Get subscription status for a tenant"""
        try:
            stripe_customer_id = self._get_tenant_stripe_id(tenant_id)

            if not stripe_customer_id:
                return None

            subscriptions = stripe.Subscription.list(
                customer=stripe_customer_id, status="active", limit=1
            )

            if subscriptions.data:
                subscription = subscriptions.data[0]
                return {
                    "subscription_id": subscription.id,
                    "status": subscription.status,
                    "plan_id": subscription.metadata.get("plan_id"),
                    "current_period_end": subscription.current_period_end,
                    "cancel_at_period_end": subscription.cancel_at_period_end,
                }

            return None
        except Exception as e:
            print(f"Error getting subscription status: {e}")
            return None

    def create_usage_record(self, tenant_id: str, quantity: int, action: str = "increment") -> bool:
        """Create a usage record for usage-based billing"""
        try:
            stripe_customer_id = self._get_tenant_stripe_id(tenant_id)

            if not stripe_customer_id:
                return False

            # Get active subscription
            subscriptions = stripe.Subscription.list(
                customer=stripe_customer_id, status="active", limit=1
            )

            if not subscriptions.data:
                return False

            subscription = subscriptions.data[0]

            # Create usage record
            stripe.UsageRecord.create(
                quantity=quantity,
                action=action,
                subscription=subscription.id,
                timestamp=int(datetime.now().timestamp()),
            )

            return True
        except Exception as e:
            print(f"Error creating usage record: {e}")
            return False

    def get_invoice_history(self, tenant_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get invoice history for a tenant"""
        try:
            stripe_customer_id = self._get_tenant_stripe_id(tenant_id)

            if not stripe_customer_id:
                return []

            invoices = stripe.Invoice.list(customer=stripe_customer_id, limit=limit)

            return [
                {
                    "id": invoice.id,
                    "amount": invoice.amount_paid,
                    "currency": invoice.currency,
                    "status": invoice.status,
                    "created": invoice.created,
                    "invoice_pdf": invoice.invoice_pdf,
                }
                for invoice in invoices.data
            ]
        except Exception as e:
            print(f"Error getting invoice history: {e}")
            return []
