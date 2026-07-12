import os
import tempfile

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
