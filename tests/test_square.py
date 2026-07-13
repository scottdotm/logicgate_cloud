import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from logicgate_cloud.billing.square_manager import SquareBillingManager
from logicgate_cloud.tenant.multi_tenant import TenantManager


@pytest.fixture
def square_manager():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_shared.db")
        os.environ["SQUARE_PLAN_ID_STARTER"] = "plan_variation_starter"
        os.environ["SQUARE_PLAN_ID_PROFESSIONAL"] = "plan_variation_professional"
        os.environ["SQUARE_PLAN_ID_ENTERPRISE"] = "plan_variation_enterprise"
        yield SquareBillingManager(
            access_token="sq_test_token",
            location_id="L_TEST",
            shared_db_path=db_path,
            webhook_secret="whsec_test",
            environment="sandbox",
        )


def test_create_checkout_missing_access_token():
    with patch.dict(os.environ, {"SQUARE_PLAN_ID_STARTER": "plan_variation_starter"}, clear=False):
        manager = SquareBillingManager(access_token="", location_id="L_TEST")
        with pytest.raises(RuntimeError, match="SQUARE_ACCESS_TOKEN"):
            manager.create_checkout("starter", "https://example.com/success")


def test_create_checkout_missing_location_id(square_manager):
    manager = SquareBillingManager(
        access_token="sq_test_token",
        location_id="",
        shared_db_path=square_manager.shared_db_path,
    )
    with pytest.raises(RuntimeError, match="SQUARE_LOCATION_ID"):
        manager.create_checkout("starter", "https://example.com/success")


def test_create_checkout_missing_plan_id(square_manager):
    with patch.dict(os.environ, {"SQUARE_PLAN_ID_STARTER": ""}, clear=False), pytest.raises(
        RuntimeError, match="SQUARE_PLAN_ID_STARTER"
    ):
        square_manager.create_checkout("starter", "https://example.com/success")


def test_create_checkout_success(square_manager):
    payment_link = MagicMock()
    payment_link.url = "https://checkout.square.site/test/123"

    response = MagicMock()
    response.errors = []
    response.payment_link = payment_link

    with patch.object(
        square_manager, "_client", return_value=MagicMock()
    ) as mock_client_factory:
        mock_client = mock_client_factory.return_value
        mock_client.checkout.payment_links.create.return_value = response

        url = square_manager.create_checkout("starter", "https://example.com/success")

    assert url == "https://checkout.square.site/test/123"
    mock_client.checkout.payment_links.create.assert_called_once()
    call_kwargs = mock_client.checkout.payment_links.create.call_args.kwargs
    assert call_kwargs["quick_pay"]["price_money"]["amount"] == 4900
    assert call_kwargs["checkout_options"]["subscription_plan_id"] == "plan_variation_starter"


def test_verify_signature_valid(square_manager):
    import base64
    import hashlib
    import hmac

    payload = '{"type":"test"}'
    notification_url = "https://example.com/api/v1/public/square/webhook"
    content = notification_url + payload
    expected = base64.b64encode(
        hmac.new(
            b"whsec_test",
            content.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    assert square_manager.verify_signature(payload, expected, notification_url) is True


def test_verify_signature_invalid(square_manager):
    assert square_manager.verify_signature(b'{"type":"test"}', "bad", "https://example.com") is False


def test_handle_webhook_event_subscription_created(square_manager):
    tenant_manager = TenantManager(square_manager.shared_db_path)
    tenant = tenant_manager.create_tenant(name="Test Tenant", plan="free")
    tenant_manager.update_tenant(tenant.id, square_customer_id="cus_123")

    event = {
        "type": "subscription.created",
        "data": {
            "object": {
                "subscription": {
                    "id": "sub_123",
                    "customer_id": "cus_123",
                    "plan_variation_id": "plan_variation_starter",
                    "status": "ACTIVE",
                }
            }
        },
    }

    result = square_manager.handle_webhook_event(event)

    assert result == {"tenant_id": tenant.id, "action": "subscription_created"}
    updated = tenant_manager.get_tenant_by_square_subscription("sub_123")
    assert updated.square_customer_id == "cus_123"
    assert updated.square_subscription_id == "sub_123"


def test_handle_webhook_event_subscription_updated(square_manager):
    tenant_manager = TenantManager(square_manager.shared_db_path)
    tenant = tenant_manager.create_tenant(name="Test Tenant", plan="starter")
    tenant_manager.update_tenant(
        tenant.id,
        square_customer_id="cus_123",
        square_subscription_id="sub_123",
    )

    event = {
        "type": "subscription.updated",
        "data": {
            "object": {
                "subscription": {
                    "id": "sub_123",
                    "customer_id": "cus_123",
                    "status": "CANCELED",
                }
            }
        },
    }

    result = square_manager.handle_webhook_event(event)

    assert result == {"tenant_id": tenant.id, "action": "subscription_cancelled"}
    updated = tenant_manager.get_tenant_by_square_subscription("sub_123")
    assert updated.status.value == "cancelled"
