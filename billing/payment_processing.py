# payment_processing.py
"""
LogicGate Payment Processing Integration
Subscription billing, payment processing, and invoice management.
"""

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from logicgate_cloud.config.settings import get_settings
from logicgate_cloud.core.exceptions import ErrorCode, ErrorSeverity, LogicGateException
from logicgate_cloud.infrastructure.cache import get_cache_manager

# Infrastructure imports
from logicgate_cloud.infrastructure.logging import LogLevel, get_logger


class PaymentGateway(Enum):
    """Payment gateway providers"""

    STRIPE = "stripe"
    PAYPAL = "paypal"
    BRAINTREE = "braintree"
    SQUARE = "square"


class SubscriptionStatus(Enum):
    """Subscription status"""

    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    TRIALING = "trialing"
    UNPAID = "unpaid"


class InvoiceStatus(Enum):
    """Invoice status"""

    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


@dataclass
class Subscription:
    """Subscription data"""

    id: int
    tenant_id: int
    plan_id: int
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    canceled_at: datetime | None
    created_at: datetime


@dataclass
class PaymentMethod:
    """Payment method data"""

    id: int
    tenant_id: int
    gateway: PaymentGateway
    token: str
    last4: str
    expiry_month: int
    expiry_year: int
    is_default: bool
    created_at: datetime


@dataclass
class Invoice:
    """Invoice data"""

    id: int
    tenant_id: int
    subscription_id: int
    amount: float
    currency: str
    status: InvoiceStatus
    due_date: datetime
    paid_at: datetime | None
    created_at: datetime


@dataclass
class Payment:
    """Payment transaction data"""

    id: int
    invoice_id: int
    amount: float
    currency: str
    status: str
    gateway: PaymentGateway
    gateway_transaction_id: str
    created_at: datetime


class PaymentProcessor:
    """Base class for payment gateway integration"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def create_customer(self, email: str, name: str) -> str:
        """Create a customer in the payment gateway"""
        raise NotImplementedError

    def create_payment_method(self, customer_id: str, token: str) -> str:
        """Create a payment method"""
        raise NotImplementedError

    def create_subscription(self, customer_id: str, plan_id: str) -> str:
        """Create a subscription"""
        raise NotImplementedError

    def cancel_subscription(self, subscription_id: str):
        """Cancel a subscription"""
        raise NotImplementedError

    def create_invoice(self, customer_id: str, amount: float, currency: str) -> str:
        """Create an invoice"""
        raise NotImplementedError

    def process_payment(self, payment_method_id: str, amount: float, currency: str) -> str:
        """Process a payment"""
        raise NotImplementedError


class StripeProcessor(PaymentProcessor):
    """Stripe payment gateway integration"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://api.stripe.com/v1"

    def create_customer(self, email: str, name: str) -> str:
        """Create a Stripe customer"""
        # Placeholder for Stripe API call
        return f"cus_{hash(email)}"

    def create_payment_method(self, customer_id: str, token: str) -> str:
        """Create a Stripe payment method"""
        # Placeholder for Stripe API call
        return f"pm_{hash(token)}"

    def create_subscription(self, customer_id: str, plan_id: str) -> str:
        """Create a Stripe subscription"""
        # Placeholder for Stripe API call
        return f"sub_{hash(customer_id + plan_id)}"

    def cancel_subscription(self, subscription_id: str):
        """Cancel a Stripe subscription"""
        # Placeholder for Stripe API call
        pass


class PayPalProcessor(PaymentProcessor):
    """PayPal payment gateway integration"""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://api.paypal.com/v1"

    def create_customer(self, email: str, name: str) -> str:
        """Create a PayPal customer"""
        # Placeholder for PayPal API call
        return f"pp_{hash(email)}"

    def create_payment_method(self, customer_id: str, token: str) -> str:
        """Create a PayPal payment method"""
        # Placeholder for PayPal API call
        return f"pm_{hash(token)}"

    def create_subscription(self, customer_id: str, plan_id: str) -> str:
        """Create a PayPal subscription"""
        # Placeholder for PayPal API call
        return f"sub_{hash(customer_id + plan_id)}"

    def cancel_subscription(self, subscription_id: str):
        """Cancel a PayPal subscription"""
        # Placeholder for PayPal API call
        pass


class SubscriptionManager:
    """Manages subscriptions and billing"""

    def __init__(self, db_path: str = None):
        self.logger = get_logger("subscription_manager", LogLevel.INFO)
        self.settings = get_settings()
        self.cache_manager = get_cache_manager()

        # Use database path from settings if not provided
        if db_path is None and hasattr(self.settings, "shared_db_path"):
            db_path = self.settings.shared_db_path
        elif db_path is None:
            db_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "logicgate_shared.db"
            )

        self.db_path = db_path
        self.processors = {}
        self._initialize_database()
        self._initialize_plans()

    def _initialize_database(self):
        """Initialize billing database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscription_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price_monthly REAL NOT NULL,
                price_yearly REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                max_assets INTEGER,
                max_users INTEGER,
                storage_quota_mb INTEGER,
                api_rate_limit INTEGER,
                features TEXT,
                is_active BOOLEAN DEFAULT 1,
                stripe_plan_id TEXT,
                paypal_plan_id TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                plan_id INTEGER NOT NULL,
                status TEXT DEFAULT 'trialing',
                current_period_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                current_period_end TIMESTAMP,
                cancel_at_period_end BOOLEAN DEFAULT 0,
                canceled_at TIMESTAMP,
                gateway_subscription_id TEXT,
                gateway TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (plan_id) REFERENCES subscription_plans(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                gateway TEXT NOT NULL,
                token TEXT NOT NULL,
                last4 TEXT,
                expiry_month INTEGER,
                expiry_year INTEGER,
                is_default BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                subscription_id INTEGER,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                status TEXT DEFAULT 'draft',
                due_date TIMESTAMP,
                paid_at TIMESTAMP,
                gateway_invoice_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (subscription_id) REFERENCES subscriptions(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                status TEXT NOT NULL,
                gateway TEXT NOT NULL,
                gateway_transaction_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id)
            )
        """)

        conn.commit()
        conn.close()
        self.logger.info("Billing database initialized")

    def _initialize_plans(self):
        """Initialize default subscription plans"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        default_plans = [
            (
                "Free",
                "Basic plan for individuals",
                0,
                0,
                "USD",
                5,
                3,
                1000,
                1000,
                json.dumps(["Basic fleet management", "Real-time telemetry"]),
                None,
                None,
            ),
            (
                "Starter",
                "For small teams",
                49,
                490,
                "USD",
                25,
                10,
                10000,
                5000,
                json.dumps(["All Free features", "Advanced analytics", "Priority support"]),
                "starter_monthly",
                "starter_yearly",
            ),
            (
                "Professional",
                "For growing businesses",
                199,
                1990,
                "USD",
                100,
                50,
                100000,
                20000,
                json.dumps(
                    ["All Starter features", "API access", "Custom integrations", "SLA guarantee"]
                ),
                "pro_monthly",
                "pro_yearly",
            ),
            (
                "Enterprise",
                "For large organizations",
                999,
                9990,
                "USD",
                -1,
                -1,
                -1,
                100000,
                json.dumps(
                    [
                        "All Professional features",
                        "Unlimited assets",
                        "Dedicated support",
                        "Custom contracts",
                    ]
                ),
                "enterprise_monthly",
                "enterprise_yearly",
            ),
        ]

        for plan in default_plans:
            cursor.execute(
                """
                INSERT OR IGNORE INTO subscription_plans
                (name, description, price_monthly, price_yearly, currency, max_assets, max_users,
                 storage_quota_mb, api_rate_limit, features, stripe_plan_id, paypal_plan_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                plan,
            )

        conn.commit()
        conn.close()

    def add_processor(self, gateway: PaymentGateway, processor: PaymentProcessor):
        """Add a payment processor"""
        self.processors[gateway.value] = processor

    def create_subscription(
        self,
        tenant_id: int,
        plan_id: int,
        gateway: PaymentGateway = PaymentGateway.STRIPE,
        billing_cycle: str = "monthly",
    ) -> Subscription:
        """Create a subscription for a tenant"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get plan details
            cursor.execute("SELECT * FROM subscription_plans WHERE id = ?", (plan_id,))
            plan = cursor.fetchone()

            if not plan:
                conn.close()
                self.logger.error("Plan not found", plan_id=plan_id)
                raise ValueError("Plan not found")

            # Calculate period end
            period_end = datetime.now() + timedelta(days=30 if billing_cycle == "monthly" else 365)

            # Create subscription record
            cursor.execute(
                """
                INSERT INTO subscriptions
                (tenant_id, plan_id, status, current_period_start, current_period_end, gateway)
                VALUES (?, ?, 'trialing', CURRENT_TIMESTAMP, ?, ?)
            """,
                (tenant_id, plan_id, period_end.isoformat(), gateway.value),
            )

            subscription_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Clear cache
            cache_key = f"subscription:{tenant_id}"
            self.cache_manager.delete(cache_key)

            self.logger.info(
                "Subscription created",
                subscription_id=subscription_id,
                tenant_id=tenant_id,
                plan_id=plan_id,
                gateway=gateway.value,
            )

            return self.get_subscription(subscription_id)
        except Exception as e:
            self.logger.error(
                "Failed to create subscription", tenant_id=tenant_id, plan_id=plan_id, error=str(e)
            )
            raise LogicGateException(
                message=f"Failed to create subscription: {str(e)}",
                code=ErrorCode.DATABASE_ERROR,
                severity=ErrorSeverity.MEDIUM,
            ) from e

    def get_subscription(self, subscription_id: int) -> Subscription | None:
        """Get subscription by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM subscriptions WHERE id = ?", (subscription_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        return Subscription(
            id=result[0],
            tenant_id=result[1],
            plan_id=result[2],
            status=SubscriptionStatus(result[3]),
            current_period_start=datetime.fromisoformat(result[4]),
            current_period_end=datetime.fromisoformat(result[5]),
            cancel_at_period_end=bool(result[6]),
            canceled_at=datetime.fromisoformat(result[7]) if result[7] else None,
            created_at=datetime.fromisoformat(result[10]),
        )

    def cancel_subscription(self, subscription_id: int, at_period_end: bool = True) -> bool:
        """Cancel a subscription"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if at_period_end:
            cursor.execute(
                """
                UPDATE subscriptions
                SET cancel_at_period_end = 1
                WHERE id = ?
            """,
                (subscription_id,),
            )
        else:
            cursor.execute(
                """
                UPDATE subscriptions
                SET status = 'cancelled', canceled_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (subscription_id,),
            )

        conn.commit()
        conn.close()

        return True

    def add_payment_method(
        self,
        tenant_id: int,
        gateway: PaymentGateway,
        token: str,
        last4: str,
        expiry_month: int,
        expiry_year: int,
    ) -> int:
        """Add a payment method"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO payment_methods
            (tenant_id, gateway, token, last4, expiry_month, expiry_year, is_default)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
            (
                tenant_id,
                gateway.value if isinstance(gateway, PaymentGateway) else gateway,
                token,
                last4,
                expiry_month,
                expiry_year,
            ),
        )

        method_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return method_id

    def create_invoice(
        self, tenant_id: int, subscription_id: int, amount: float, due_date: datetime = None
    ) -> Invoice:
        """Create an invoice"""
        if due_date is None:
            due_date = datetime.now() + timedelta(days=30)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO invoices
            (tenant_id, subscription_id, amount, status, due_date)
            VALUES (?, ?, ?, 'open', ?)
        """,
            (tenant_id, subscription_id, amount, due_date.isoformat()),
        )

        invoice_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return self.get_invoice(invoice_id)

    def get_invoice(self, invoice_id: int) -> Invoice | None:
        """Get invoice by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        return Invoice(
            id=result[0],
            tenant_id=result[1],
            subscription_id=result[2],
            amount=result[3],
            currency=result[4],
            status=InvoiceStatus(result[5]),
            due_date=datetime.fromisoformat(result[6]),
            paid_at=datetime.fromisoformat(result[7]) if result[7] else None,
            created_at=datetime.fromisoformat(result[9]),
        )

    def process_payment(
        self, invoice_id: int, payment_method_id: int, gateway: PaymentGateway
    ) -> Payment:
        """Process a payment for an invoice"""
        invoice = self.get_invoice(invoice_id)

        if not invoice:
            raise ValueError("Invoice not found")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get payment method
        cursor.execute(
            """
            SELECT * FROM payment_methods WHERE id = ?
        """,
            (payment_method_id,),
        )

        payment_method = cursor.fetchone()

        if not payment_method:
            conn.close()
            raise ValueError("Payment method not found")

        # Process payment through gateway
        if gateway.value in self.processors:
            # This would call the actual payment gateway
            gateway_transaction_id = f"txn_{hash(str(invoice_id) + str(payment_method_id))}"
            status = "succeeded"
        else:
            # Simulate payment
            gateway_transaction_id = f"txn_sim_{invoice_id}"
            status = "succeeded"

        # Create payment record
        cursor.execute(
            """
            INSERT INTO payments
            (invoice_id, amount, currency, status, gateway, gateway_transaction_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                invoice_id,
                invoice.amount,
                invoice.currency,
                status,
                gateway.value,
                gateway_transaction_id,
            ),
        )

        payment_id = cursor.lastrowid

        # Update invoice status
        cursor.execute(
            """
            UPDATE invoices
            SET status = 'paid', paid_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (invoice_id,),
        )

        conn.commit()
        conn.close()

        return self.get_payment(payment_id)

    def get_payment(self, payment_id: int) -> Payment | None:
        """Get payment by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        return Payment(
            id=result[0],
            invoice_id=result[1],
            amount=result[2],
            currency=result[3],
            status=result[4],
            gateway=PaymentGateway(result[5]),
            gateway_transaction_id=result[6],
            created_at=datetime.fromisoformat(result[7]),
        )

    def get_plans(self) -> list[dict]:
        """Get all subscription plans"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM subscription_plans WHERE is_active = 1 ORDER BY price_monthly ASC"
        )
        results = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "price_monthly": row[3],
                "price_yearly": row[4],
                "currency": row[5],
                "max_assets": row[6],
                "max_users": row[7],
                "storage_quota_mb": row[8],
                "api_rate_limit": row[9],
                "features": json.loads(row[10]),
            }
            for row in results
        ]

    def check_billing_status(self, tenant_id: int) -> dict:
        """Check billing status for a tenant"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get active subscription
        cursor.execute(
            """
            SELECT s.*, p.name as plan_name, p.price_monthly
            FROM subscriptions s
            JOIN subscription_plans p ON s.plan_id = p.id
            WHERE s.tenant_id = ? AND s.status IN ('active', 'trialing')
            ORDER BY s.created_at DESC
            LIMIT 1
        """,
            (tenant_id,),
        )

        subscription = cursor.fetchone()

        # Get unpaid invoices
        cursor.execute(
            """
            SELECT COUNT(*), SUM(amount)
            FROM invoices
            WHERE tenant_id = ? AND status = 'open' AND due_date < CURRENT_TIMESTAMP
        """,
            (tenant_id,),
        )

        overdue = cursor.fetchone()

        conn.close()

        if subscription:
            return {
                "has_subscription": True,
                "plan_name": subscription[10],
                "price_monthly": subscription[11],
                "status": subscription[3],
                "period_end": subscription[5],
                "overdue_invoices": overdue[0],
                "overdue_amount": overdue[1] or 0,
            }

        return {
            "has_subscription": False,
            "overdue_invoices": overdue[0],
            "overdue_amount": overdue[1] or 0,
        }


# Convenience functions
def create_subscription(tenant_id: int, plan_id: int) -> Subscription:
    """Create a subscription"""
    manager = SubscriptionManager()
    return manager.create_subscription(tenant_id, plan_id)


def get_available_plans() -> list[dict]:
    """Get available subscription plans"""
    manager = SubscriptionManager()
    return manager.get_plans()


if __name__ == "__main__":
    print("Testing Payment Processing System...")

    # Get plans
    plans = get_available_plans()
    print(f"Available plans: {len(plans)}")

    # Test billing status check
    manager = SubscriptionManager()
    status = manager.check_billing_status(1)
    print(f"Billing status: {status}")

    print("Payment Processing System test complete!")
