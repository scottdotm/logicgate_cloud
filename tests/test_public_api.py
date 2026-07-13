import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure the cloud package sys.path setup runs before importing the app
import logicgate_cloud  # noqa: F401
from logicgate_cloud.main import app


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_shared.db")
        os.environ["SHARED_DB_PATH"] = db_path
        os.environ["JWT_SECRET"] = "a" * 32  # minimum length
        os.environ["STRIPE_SECRET_KEY"] = ""

        yield TestClient(app)


def test_health_check(client):
    response = client.get("/api/v1/public/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_plans(client):
    response = client.get("/api/v1/public/plans")
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert len(data["plans"]) > 0
    assert data["plans"][0]["id"] == "freemium"


def test_signup(client):
    response = client.post(
        "/api/v1/public/tenants",
        json={
            "email": "pilot@example.com",
            "password": "securepass123",
            "name": "Test Pilot",
            "company": "Acme Corp",
            "plan": "freemium",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["tenant_id"] is not None


def test_login_and_subscription(client):
    # Sign up
    client.post(
        "/api/v1/public/tenants",
        json={
            "email": "admin@example.com",
            "password": "securepass123",
            "name": "Admin User",
            "company": "Acme Corp",
            "plan": "freemium",
        },
    )

    # Login
    login_response = client.post(
        "/api/v1/portal/auth/login",
        json={"email": "admin@example.com", "password": "securepass123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["token"]
    assert token is not None

    # Fetch subscription
    subscription_response = client.get(
        "/api/v1/portal/subscription",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert subscription_response.status_code == 200
    data = subscription_response.json()
    assert data["plan"] == "freemium"


def test_unauthenticated_subscription(client):
    response = client.get("/api/v1/portal/subscription")
    assert response.status_code == 401


def test_checkout_creates_stripe_session(client):
    """Smoke test that the public checkout endpoint creates a Stripe session."""
    os.environ["STRIPE_SECRET_KEY"] = "sk_test_0123456789abcdef"
    os.environ["STRIPE_PRICE_TEST"] = "price_test_12345"

    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/test/session_123"

    with patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create:
        response = client.post(
            "/api/v1/public/checkout",
            json={
                "plan": "test",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["checkout_url"] == "https://checkout.stripe.com/test/session_123"
    assert "checkout" in data["message"].lower()

    mock_create.assert_called_once_with(
        mode="subscription",
        line_items=[{"price": "price_test_12345", "quantity": 1}],
        success_url="https://example.com/success",
        cancel_url="https://example.com/cancel",
    )


def test_stripe_webhook_validates_signature(client):
    """Smoke test that a valid Stripe webhook signature is accepted and processed."""
    os.environ["STRIPE_SECRET_KEY"] = "sk_test_0123456789abcdef"
    os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_secret"

    event_payload = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": "cus_test_123",
                "subscription": "sub_test_123",
                "customer_details": {"email": "customer@example.com"},
            }
        },
    }

    with patch("stripe.Webhook.construct_event", return_value=event_payload) as mock_construct:
        response = client.post(
            "/api/v1/public/stripe/webhook",
            json=event_payload,
            headers={"stripe-signature": "t=1234567890,v1=valid_signature"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    mock_construct.assert_called_once()


def test_stripe_webhook_rejects_invalid_signature(client):
    """Smoke test that an invalid Stripe webhook signature returns 400."""
    import stripe

    os.environ["STRIPE_SECRET_KEY"] = "sk_test_0123456789abcdef"
    os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_secret"

    with patch(
        "stripe.Webhook.construct_event",
        side_effect=stripe.error.SignatureVerificationError("Invalid signature", ""),
    ):
        response = client.post(
            "/api/v1/public/stripe/webhook",
            json={"type": "checkout.session.completed"},
            headers={"stripe-signature": "t=1234567890,v1=invalid_signature"},
        )

    assert response.status_code == 400
    assert "signature" in response.json()["detail"].lower()


def test_checkout_creates_square_session(client):
    """Smoke test that the public checkout endpoint creates a Square session."""
    manager = MagicMock()
    manager.create_checkout.return_value = "https://checkout.square.site/test/session_123"

    with patch("logicgate_cloud.api.public._get_square_billing_manager", return_value=manager):
        response = client.post(
            "/api/v1/public/checkout",
            json={
                "plan": "starter",
                "gateway": "square",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["checkout_url"] == "https://checkout.square.site/test/session_123"
    manager.create_checkout.assert_called_once_with(
        plan="starter",
        success_url="https://example.com/success",
        cancel_url="https://example.com/cancel",
    )


def test_square_webhook_validates_signature(client):
    """Smoke test that a valid Square webhook signature is accepted."""
    manager = MagicMock()
    manager.verify_signature.return_value = True
    manager.handle_webhook_event.return_value = {"tenant_id": 1, "action": "payment_made"}

    with patch("logicgate_cloud.api.public._get_square_billing_manager", return_value=manager):
        response = client.post(
            "/api/v1/public/square/webhook",
            json={"type": "invoice.payment_made"},
            headers={"x-square-hmacsha256-signature": "valid_signature"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    manager.verify_signature.assert_called_once()
    manager.handle_webhook_event.assert_called_once()


def test_square_webhook_rejects_invalid_signature(client):
    """Smoke test that an invalid Square webhook signature returns 400."""
    manager = MagicMock()
    manager.verify_signature.return_value = False

    with patch("logicgate_cloud.api.public._get_square_billing_manager", return_value=manager):
        response = client.post(
            "/api/v1/public/square/webhook",
            json={"type": "invoice.payment_made"},
            headers={"x-square-hmacsha256-signature": "invalid_signature"},
        )

    assert response.status_code == 400
    assert "signature" in response.json()["detail"].lower()
