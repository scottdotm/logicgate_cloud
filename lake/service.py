"""
Lake management service layer.

Provides high-level operations for lakes, surveys, images, and storage paths.
"""

import os
import shutil
from contextlib import suppress
from datetime import datetime

from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS

from logicgate_cloud.lake.models import Lake, LakeManager, Survey, SurveyImage, SurveyStatus
from logicgate_cloud.tenant.multi_tenant import TenantManager


class LakeService:
    """High-level service for lake and survey operations."""

    def __init__(self, tenant_manager: TenantManager, upload_dir: str = "uploads"):
        self.tenant_manager = tenant_manager
        self.upload_dir = upload_dir
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir, exist_ok=True)

    def _get_manager(self, tenant_id: int) -> LakeManager:
        tenant = self.tenant_manager.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        db_path = self.tenant_manager.get_tenant_database_path(tenant_id)
        return LakeManager(db_path)

    def _tenant_upload_path(self, tenant_id: int) -> str:
        path = os.path.join(self.upload_dir, f"tenant_{tenant_id}")
        os.makedirs(path, exist_ok=True)
        return path

    def _survey_upload_path(self, tenant_id: int, survey_id: int) -> str:
        path = os.path.join(self._tenant_upload_path(tenant_id), f"survey_{survey_id}")
        os.makedirs(path, exist_ok=True)
        return path

    def create_lake(
        self,
        tenant_id: int,
        name: str,
        body_id: str | None = None,
        location: str | None = None,
        boundary_geojson: str | None = None,
        area_sqm: float | None = None,
        notes: str | None = None,
    ) -> Lake:
        manager = self._get_manager(tenant_id)
        lake_id = manager.create_lake(
            tenant_id=tenant_id,
            name=name,
            body_id=body_id,
            location=location,
            boundary_geojson=boundary_geojson,
            area_sqm=area_sqm,
            notes=notes,
        )
        return manager.get_lake(tenant_id, lake_id)

    def list_lakes(self, tenant_id: int) -> list[Lake]:
        manager = self._get_manager(tenant_id)
        return manager.list_lakes(tenant_id)

    def get_lake(self, tenant_id: int, lake_id: int) -> Lake | None:
        manager = self._get_manager(tenant_id)
        return manager.get_lake(tenant_id, lake_id)

    def create_survey(
        self,
        tenant_id: int,
        lake_id: int,
        name: str,
        scheduled_at: datetime | None = None,
        pilot_name: str | None = None,
        drone_name: str | None = None,
        altitude_m: float | None = None,
        notes: str | None = None,
    ) -> Survey:
        manager = self._get_manager(tenant_id)
        lake = manager.get_lake(tenant_id, lake_id)
        if not lake:
            raise ValueError(f"Lake {lake_id} not found")
        survey_id = manager.create_survey(
            tenant_id=tenant_id,
            lake_id=lake_id,
            name=name,
            scheduled_at=scheduled_at,
            pilot_name=pilot_name,
            drone_name=drone_name,
            altitude_m=altitude_m,
            notes=notes,
        )
        return manager.get_survey(tenant_id, survey_id)

    def list_surveys(self, tenant_id: int, lake_id: int | None = None) -> list[Survey]:
        manager = self._get_manager(tenant_id)
        return manager.list_surveys(tenant_id, lake_id)

    def get_survey(self, tenant_id: int, survey_id: int) -> Survey | None:
        manager = self._get_manager(tenant_id)
        return manager.get_survey(tenant_id, survey_id)

    def update_survey_status(self, tenant_id: int, survey_id: int, status: SurveyStatus) -> bool:
        manager = self._get_manager(tenant_id)
        return manager.update_survey_status(tenant_id, survey_id, status)

    def add_image(self, tenant_id: int, survey_id: int, file) -> SurveyImage:
        """Store an uploaded image and extract GPS/EXIF metadata."""
        manager = self._get_manager(tenant_id)
        survey = manager.get_survey(tenant_id, survey_id)
        if not survey:
            raise ValueError(f"Survey {survey_id} not found")

        survey_dir = self._survey_upload_path(tenant_id, survey_id)
        filename = os.path.basename(file.filename)
        original_path = os.path.join(survey_dir, filename)

        with open(original_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Create thumbnail
        thumbnail_path = os.path.join(survey_dir, f"thumb_{filename}")
        try:
            with Image.open(original_path) as img:
                img.thumbnail((320, 320))
                img.save(thumbnail_path)
        except Exception:
            thumbnail_path = None

        # Extract EXIF GPS and timestamp
        latitude, longitude, altitude, captured_at = _extract_exif(original_path)

        image_id = manager.add_image(
            tenant_id=tenant_id,
            survey_id=survey_id,
            filename=filename,
            original_path=original_path,
            thumbnail_path=thumbnail_path,
            latitude=latitude,
            longitude=longitude,
            altitude_m=altitude,
            captured_at=captured_at,
        )
        return manager.get_image(tenant_id, image_id)

    def list_images(self, tenant_id: int, survey_id: int) -> list[SurveyImage]:
        manager = self._get_manager(tenant_id)
        return manager.list_images(tenant_id, survey_id)

    def get_image(self, tenant_id: int, image_id: int) -> SurveyImage | None:
        manager = self._get_manager(tenant_id)
        return manager.get_image(tenant_id, image_id)


def _extract_exif(image_path: str):
    """Extract GPS coordinates and capture timestamp from image EXIF."""
    latitude = None
    longitude = None
    altitude = None
    captured_at = None

    try:
        with Image.open(image_path) as img:
            exif = img._getexif()
            if not exif:
                return latitude, longitude, altitude, captured_at

            exif_data = {TAGS.get(tag, tag): value for tag, value in exif.items()}

            # DateTimeOriginal
            dt_str = exif_data.get("DateTimeOriginal") or exif_data.get("DateTime")
            if dt_str:
                with suppress(ValueError):
                    captured_at = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")

            # GPSInfo
            gps_info = exif_data.get("GPSInfo")
            if gps_info:
                gps_data = {GPSTAGS.get(key, key): value for key, value in gps_info.items()}
                lat_ref = gps_data.get("GPSLatitudeRef")
                lat = gps_data.get("GPSLatitude")
                lon_ref = gps_data.get("GPSLongitudeRef")
                lon = gps_data.get("GPSLongitude")
                alt = gps_data.get("GPSAltitude")

                if lat and lon:
                    latitude = _convert_dms(lat)
                    if lat_ref == "S":
                        latitude = -latitude
                    longitude = _convert_dms(lon)
                    if lon_ref == "W":
                        longitude = -longitude
                if alt:
                    with suppress(TypeError, ValueError):
                        altitude = float(alt)
    except Exception:
        pass

    return latitude, longitude, altitude, captured_at


def _convert_dms(dms) -> float:
    """Convert degrees/minutes/seconds tuple to decimal degrees."""
    degrees, minutes, seconds = dms
    return float(degrees) + float(minutes) / 60.0 + float(seconds) / 3600.0
