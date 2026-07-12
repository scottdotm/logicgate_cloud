"""
Tests for the lake management vertical: lake, survey, image upload, and report generation.
"""

import io
import os
import tempfile
from datetime import datetime
from pathlib import Path

import logicgate_cloud  # noqa: F401
from logicgate_cloud.auth.multi_tenant_auth import MultiTenantAuth
from logicgate_cloud.lake.models import SurveyStatus
from logicgate_cloud.lake.report import ReportGenerator
from logicgate_cloud.lake.service import LakeService
from logicgate_cloud.tenant.multi_tenant import TenantManager


def _setup_user_and_tenant(base_dir: str, email="survey@example.com", password="Pass1234!"):
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    shared_db = base_dir / "shared.db"
    tenant_dir = base_dir / "tenants"
    jwt_secret = "test_jwt_secret_at_least_32_chars_long"

    auth = MultiTenantAuth(str(shared_db), jwt_secret)
    tenant_manager = TenantManager(str(shared_db), str(tenant_dir))

    tenant = tenant_manager.create_tenant("Test Survey Co")
    user_id = auth.create_user(
        str(tenant.id), email, password, full_name="Survey Tester", role="admin"
    )
    token = auth.generate_jwt(
        {
            "tenant_id": str(tenant.id),
            "user_id": user_id,
            "email": email,
            "role": "admin",
        }
    )

    return tenant, user_id, token, tenant_manager, auth


def test_create_lake_and_survey():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        tenant, user_id, token, tenant_manager, auth = _setup_user_and_tenant(str(tmp_path / "db"))

        service = LakeService(tenant_manager, upload_dir=str(tmp_path / "uploads"))
        lake = service.create_lake(
            tenant_id=tenant.id,
            name="Okauchee Lake",
            location="Okauchee, WI",
            body_id="WI-1001",
            area_sqm=1234567.0,
            notes="Test lake for pilot survey",
        )

        assert lake.name == "Okauchee Lake"
        assert lake.location == "Okauchee, WI"
        assert lake.body_id == "WI-1001"

        survey = service.create_survey(
            tenant_id=tenant.id,
            lake_id=lake.id,
            name="Spring Vegetation Survey",
            scheduled_at=datetime(2026, 5, 15, 10, 0, 0),
            pilot_name="Scott",
            drone_name="Mavic 3",
            altitude_m=80.0,
            notes="Focus on northern shoreline",
        )

        assert survey.lake_id == lake.id
        assert survey.name == "Spring Vegetation Survey"
        assert survey.status == SurveyStatus.PENDING

        surveys = service.list_surveys(tenant.id, lake_id=lake.id)
        assert len(surveys) == 1


def test_upload_image_and_update_count():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        tenant, user_id, token, tenant_manager, auth = _setup_user_and_tenant(str(tmp_path / "db"))

        service = LakeService(tenant_manager, upload_dir=str(tmp_path / "uploads"))
        lake = service.create_lake(tenant_id=tenant.id, name="Okauchee Lake")
        survey = service.create_survey(tenant_id=tenant.id, lake_id=lake.id, name="Survey 1")

        # Create a tiny valid PNG
        from PIL import Image

        img_bytes = io.BytesIO()
        Image.new("RGB", (100, 100), color="blue").save(img_bytes, format="PNG")
        img_bytes.seek(0)

        class FakeFile:
            filename = "test.png"
            file = img_bytes

        image = service.add_image(tenant.id, survey.id, FakeFile())
        assert image.filename == "test.png"
        assert os.path.exists(image.original_path)
        assert image.thumbnail_path is not None

        survey = service.get_survey(tenant.id, survey.id)
        assert survey.image_count == 1


def test_generate_report():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        tenant, user_id, token, tenant_manager, auth = _setup_user_and_tenant(str(tmp_path / "db"))

        service = LakeService(tenant_manager, upload_dir=str(tmp_path / "uploads"))
        lake = service.create_lake(tenant_id=tenant.id, name="Okauchee Lake")
        survey = service.create_survey(tenant_id=tenant.id, lake_id=lake.id, name="Report Survey")

        # Upload a tiny image
        from PIL import Image

        img_bytes = io.BytesIO()
        Image.new("RGB", (200, 150), color="green").save(img_bytes, format="PNG")
        img_bytes.seek(0)

        class FakeFile:
            filename = "sample.png"
            file = img_bytes

        service.add_image(tenant.id, survey.id, FakeFile())

        generator = ReportGenerator(service)
        output_path = str(tmp_path / "report.pdf")
        generator.generate(tenant.id, survey.id, output_path)

        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0


def test_update_survey_status():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        tenant, user_id, token, tenant_manager, auth = _setup_user_and_tenant(str(tmp_path / "db"))

        service = LakeService(tenant_manager, upload_dir=str(tmp_path / "uploads"))
        lake = service.create_lake(tenant_id=tenant.id, name="Okauchee Lake")
        survey = service.create_survey(tenant_id=tenant.id, lake_id=lake.id, name="Survey 2")

        service.update_survey_status(tenant.id, survey.id, SurveyStatus.COMPLETED)
        updated = service.get_survey(tenant.id, survey.id)
        assert updated.status == SurveyStatus.COMPLETED


def test_lake_api_endpoints():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["SHARED_DB_PATH"] = str(tmp_path / "shared.db")
        os.environ["TENANT_DB_DIR"] = str(tmp_path / "tenants")
        os.environ["UPLOAD_DIR"] = str(tmp_path / "uploads")
        os.environ["JWT_SECRET"] = "test_jwt_secret_at_least_32_chars_long"
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
        os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_dummy"

        tenant, user_id, token, tenant_manager, auth = _setup_user_and_tenant(str(tmp_path))

        from fastapi.testclient import TestClient

        from logicgate_cloud.main import app

        client = TestClient(app)
        headers = {"Authorization": f"Bearer {token}"}

        # Create lake
        lake_resp = client.post(
            "/api/v1/portal/lakes",
            json={
                "name": "Okauchee Lake",
                "location": "Okauchee, WI",
                "body_id": "WI-1001",
            },
            headers=headers,
        )
        if lake_resp.status_code != 200:
            raise AssertionError(f"Lake create failed: {lake_resp.status_code} {lake_resp.text}")
        lake_id = lake_resp.json()["id"]

        # List lakes
        list_resp = client.get("/api/v1/portal/lakes", headers=headers)
        assert list_resp.status_code == 200
        assert len(list_resp.json()["lakes"]) == 1

        # Create survey
        survey_resp = client.post(
            f"/api/v1/portal/lakes/{lake_id}/surveys",
            json={
                "lake_id": lake_id,
                "name": "API Survey",
                "pilot_name": "Scott",
                "drone_name": "Mavic 3",
            },
            headers=headers,
        )
        assert survey_resp.status_code == 200
        survey_id = survey_resp.json()["id"]

        # Get survey
        get_resp = client.get(f"/api/v1/portal/surveys/{survey_id}", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "API Survey"

        # Update survey status
        patch_resp = client.patch(
            f"/api/v1/portal/surveys/{survey_id}",
            json={"status": "completed"},
            headers=headers,
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["status"] == "completed"

        # Upload image
        from PIL import Image

        img_bytes = io.BytesIO()
        Image.new("RGB", (200, 150), color="green").save(img_bytes, format="PNG")
        img_bytes.seek(0)

        upload_resp = client.post(
            f"/api/v1/portal/surveys/{survey_id}/images",
            files={"file": ("api.png", img_bytes, "image/png")},
            headers=headers,
        )
        assert upload_resp.status_code == 200, upload_resp.text
        assert upload_resp.json()["filename"] == "api.png"

        # Generate report
        report_resp = client.post(
            f"/api/v1/portal/surveys/{survey_id}/report",
            headers=headers,
        )
        assert report_resp.status_code == 200
        assert report_resp.headers["content-type"] == "application/pdf"
        assert len(report_resp.content) > 0


def test_public_inquiry():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["SHARED_DB_PATH"] = str(tmp_path / "shared.db")
        os.environ["TENANT_DB_DIR"] = str(tmp_path / "tenants")
        os.environ["JWT_SECRET"] = "test_jwt_secret_at_least_32_chars_long"
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
        os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_dummy"

        from fastapi.testclient import TestClient

        from logicgate_cloud.main import app

        client = TestClient(app)

        resp = client.post(
            "/api/v1/public/inquiries",
            json={
                "name": "Lake Manager",
                "email": "manager@okaucheelake.org",
                "organization": "Okauchee Lake Association",
                "lake_name": "Okauchee Lake",
                "message": "Interested in a spring vegetation survey.",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["inquiry_id"] > 0

        # Landing page should be served
        page = client.get("/api/v1/public/inquiries/landing")
        assert page.status_code == 200
        assert "LogicGate Lake Surveys" in page.text


def test_public_inquiry_partner_fields():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["SHARED_DB_PATH"] = str(tmp_path / "shared.db")
        os.environ["TENANT_DB_DIR"] = str(tmp_path / "tenants")
        os.environ["JWT_SECRET"] = "test_jwt_secret_at_least_32_chars_long"
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
        os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_dummy"

        from fastapi.testclient import TestClient

        from logicgate_cloud.main import app

        client = TestClient(app)

        resp = client.post(
            "/api/v1/public/inquiries",
            json={
                "name": "Drone Pilot",
                "email": "pilot@droneco.com",
                "organization": "DroneCo",
                "phone": "262-555-0100",
                "part_107": "yes",
                "existing_clients": "yes",
                "message": "I serve lake associations in Waukesha County.",
                "interest": "lake_survey_partner",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["inquiry_id"] > 0

        # Partner pitch page should be served
        pitch = client.get("/api/v1/public/partners/pitch")
        assert pitch.status_code == 200
        assert "Partner Pitch" in pitch.text

        # Demo report should return a PDF
        report = client.get("/api/v1/public/demo-report")
        assert report.status_code == 200
        assert report.headers["content-type"] == "application/pdf"
        assert len(report.content) > 0
