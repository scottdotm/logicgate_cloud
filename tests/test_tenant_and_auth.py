import os
import tempfile

import pytest

import logicgate_cloud  # noqa: F401
from logicgate_cloud.auth.multi_tenant_auth import MultiTenantAuth
from logicgate_cloud.tenant.multi_tenant import TenantManager, TenantPlan


@pytest.fixture
def tenant_manager():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_shared.db")
        tenant_db_dir = os.path.join(tmp_dir, "tenants")
        yield TenantManager(db_path, tenant_db_dir)


@pytest.fixture
def auth_manager(tenant_manager):
    return MultiTenantAuth(tenant_manager.shared_db_path, "a" * 32)


def test_create_tenant(tenant_manager):
    tenant = tenant_manager.create_tenant(name="Acme Corp", plan=TenantPlan.FREE)
    assert tenant.name == "Acme Corp"
    assert tenant.plan == TenantPlan.FREE
    assert tenant.slug == "acme-corp"


def test_get_tenant(tenant_manager):
    tenant = tenant_manager.create_tenant(name="Acme Corp", plan=TenantPlan.STARTER)
    fetched = tenant_manager.get_tenant(tenant.id)
    assert fetched is not None
    assert fetched.id == tenant.id
    assert fetched.plan == TenantPlan.STARTER


def test_user_lifecycle(tenant_manager, auth_manager):
    tenant = tenant_manager.create_tenant(name="Acme Corp", plan=TenantPlan.FREE)
    tenant_id = str(tenant.id)

    user_id = auth_manager.create_user(
        tenant_id=tenant_id,
        email="admin@example.com",
        password="securepass123",
        full_name="Admin User",
        role="admin",
    )
    assert user_id is not None

    found = auth_manager.find_user_by_email("admin@example.com")
    assert found is not None
    assert found["tenant_id"] == tenant_id

    result = auth_manager.authenticate_user_by_email("admin@example.com", "securepass123")
    assert result is not None
    assert result["email"] == "admin@example.com"

    bad_result = auth_manager.authenticate_user_by_email("admin@example.com", "wrongpassword")
    assert bad_result is None


def test_jwt_lifecycle(auth_manager, tenant_manager):
    tenant = tenant_manager.create_tenant(name="Acme Corp", plan=TenantPlan.FREE)
    user_id = auth_manager.create_user(
        tenant_id=str(tenant.id),
        email="admin@example.com",
        password="securepass123",
        full_name="Admin User",
        role="admin",
    )

    user_info = auth_manager.authenticate_user_by_email("admin@example.com", "securepass123")
    token = auth_manager.generate_jwt(user_info)
    assert token is not None

    decoded = auth_manager.validate_jwt(token)
    assert decoded is not None
    assert decoded["user_id"] == user_id


def test_update_tenant_stripe_fields(tenant_manager):
    tenant = tenant_manager.create_tenant(name="Acme Corp", plan=TenantPlan.STARTER)
    success = tenant_manager.update_tenant(
        tenant.id,
        status="active",
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_123",
    )
    assert success is True

    fetched = tenant_manager.get_tenant_by_stripe_subscription("sub_123")
    assert fetched is not None
    assert fetched.id == tenant.id
    assert fetched.status.value == "active"
