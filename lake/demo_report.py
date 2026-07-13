"""
Generate a sample lake survey report for demo and partner outreach purposes.

This creates a temporary tenant, lake, survey, and sample images, then produces a
PDF report that can be shown to prospective drone service provider partners.
"""

import io
import os
import tempfile
from datetime import datetime

from PIL import Image

from logicgate_cloud.auth.multi_tenant_auth import MultiTenantAuth
from logicgate_cloud.lake.report import ReportGenerator
from logicgate_cloud.lake.service import LakeService
from logicgate_cloud.tenant.multi_tenant import TenantManager


def generate_sample_report(output_path: str) -> str:
    """Generate a demo lake survey report and return the output path."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        shared_db = os.path.join(tmp_dir, "shared.db")
        tenant_dir = os.path.join(tmp_dir, "tenants")
        upload_dir = os.path.join(tmp_dir, "uploads")

        jwt_secret = os.environ.get("JWT_SECRET")
        if not jwt_secret or len(jwt_secret) < 32:
            raise RuntimeError("JWT_SECRET must be set and at least 32 characters long")

        auth = MultiTenantAuth(shared_db, jwt_secret)
        tenant_manager = TenantManager(shared_db, tenant_dir)

        tenant = tenant_manager.create_tenant("Demo Drone Services")
        _ = auth.create_user(
            str(tenant.id),
            "demo@example.com",
            os.environ.get("DEMO_PASSWORD", "DemoPass123!"),
            full_name="Demo Pilot",
            role="admin",
        )

        service = LakeService(tenant_manager, upload_dir=upload_dir)

        lake = service.create_lake(
            tenant_id=tenant.id,
            name="Okauchee Lake",
            location="Okauchee, WI",
            body_id="WI-1001",
            area_sqm=1210000.0,
            notes="Demo lake for pilot partner outreach. This report shows the deliverable your lake clients would receive.",
        )

        survey = service.create_survey(
            tenant_id=tenant.id,
            lake_id=lake.id,
            name="Spring Shoreline Survey - Demo",
            scheduled_at=datetime(2026, 5, 15, 10, 0, 0),
            pilot_name="Scott",
            drone_name="DJI Mavic 3",
            altitude_m=80.0,
            notes="Demo survey showing shoreline vegetation and northern cove coverage.",
        )

        # Generate a few sample images with GPS metadata
        for i in range(3):
            img_bytes = io.BytesIO()
            # Create a blue/green gradient image to simulate lake water and vegetation
            width, height = 400, 300
            img = Image.new("RGB", (width, height))
            for y in range(height):
                for x in range(width):
                    # Top half = blue water, bottom half = green vegetation
                    if y < height * 0.6:
                        img.putpixel((x, y), (30, 100, 180 + y // 4))
                    else:
                        img.putpixel((x, y), (50 + y // 4, 140 + x // 8, 60))
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)

            class FakeFile:
                filename = f"demo_DJI_000{i + 1}.png"
                file = img_bytes

            service.add_image(tenant.id, survey.id, FakeFile())

        generator = ReportGenerator(service)
        generator.generate(tenant.id, survey.id, output_path)

    return output_path


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "sample_lake_survey_report.pdf"
    generate_sample_report(path)
    print(f"Sample report generated: {path}")
