"""
Lake and Survey models for the lake management vertical.

Uses SQLite (consistent with the rest of logicgate_cloud) and stores data in the
tenant-specific database created by TenantManager.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SurveyStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Lake:
    id: int
    tenant_id: int
    name: str
    body_id: str | None
    location: str | None
    boundary_geojson: str | None
    area_sqm: float | None
    notes: str | None
    created_at: datetime
    updated_at: datetime | None


@dataclass
class Survey:
    id: int
    tenant_id: int
    lake_id: int
    name: str
    status: SurveyStatus
    scheduled_at: datetime | None
    completed_at: datetime | None
    pilot_name: str | None
    drone_name: str | None
    altitude_m: float | None
    image_count: int
    notes: str | None
    created_at: datetime
    updated_at: datetime | None


@dataclass
class SurveyImage:
    id: int
    tenant_id: int
    survey_id: int
    filename: str
    original_path: str
    thumbnail_path: str | None
    latitude: float | None
    longitude: float | None
    altitude_m: float | None
    captured_at: datetime | None
    created_at: datetime


class LakeManager:
    """Manages lake and survey data in a tenant-specific SQLite database."""

    def __init__(self, tenant_db_path: str):
        self.tenant_db_path = tenant_db_path
        self._ensure_tables()

    def _ensure_tables(self):
        """Create lake, survey, and survey_image tables if they do not exist."""
        conn = sqlite3.connect(self.tenant_db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lakes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                body_id TEXT,
                location TEXT,
                boundary_geojson TEXT,
                area_sqm REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS surveys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                lake_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                scheduled_at TIMESTAMP,
                completed_at TIMESTAMP,
                pilot_name TEXT,
                drone_name TEXT,
                altitude_m REAL,
                image_count INTEGER DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lake_id) REFERENCES lakes(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS survey_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                survey_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                original_path TEXT NOT NULL,
                thumbnail_path TEXT,
                latitude REAL,
                longitude REAL,
                altitude_m REAL,
                captured_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (survey_id) REFERENCES surveys(id)
            )
        """)

        conn.commit()
        conn.close()

    def create_lake(
        self,
        tenant_id: int,
        name: str,
        body_id: str | None = None,
        location: str | None = None,
        boundary_geojson: str | None = None,
        area_sqm: float | None = None,
        notes: str | None = None,
    ) -> int:
        conn = sqlite3.connect(self.tenant_db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO lakes (tenant_id, name, body_id, location, boundary_geojson, area_sqm, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (tenant_id, name, body_id, location, boundary_geojson, area_sqm, notes),
        )
        lake_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return lake_id

    def get_lake(self, tenant_id: int, lake_id: int) -> Lake | None:
        conn = sqlite3.connect(self.tenant_db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tenant_id, name, body_id, location, boundary_geojson, area_sqm, notes, created_at, updated_at
            FROM lakes
            WHERE tenant_id = ? AND id = ?
        """,
            (tenant_id, lake_id),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_lake(row)

    def list_lakes(self, tenant_id: int) -> list[Lake]:
        conn = sqlite3.connect(self.tenant_db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tenant_id, name, body_id, location, boundary_geojson, area_sqm, notes, created_at, updated_at
            FROM lakes
            WHERE tenant_id = ?
            ORDER BY created_at DESC
        """,
            (tenant_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_lake(row) for row in rows]

    def _row_to_lake(self, row: tuple) -> Lake:
        return Lake(
            id=row[0],
            tenant_id=row[1],
            name=row[2],
            body_id=row[3],
            location=row[4],
            boundary_geojson=row[5],
            area_sqm=row[6],
            notes=row[7],
            created_at=datetime.fromisoformat(row[8]),
            updated_at=datetime.fromisoformat(row[9]) if row[9] else None,
        )

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
    ) -> int:
        conn = sqlite3.connect(self.tenant_db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO surveys (tenant_id, lake_id, name, status, scheduled_at, pilot_name, drone_name, altitude_m, notes)
            VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)
        """,
            (tenant_id, lake_id, name, scheduled_at, pilot_name, drone_name, altitude_m, notes),
        )
        survey_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return survey_id

    def get_survey(self, tenant_id: int, survey_id: int) -> Survey | None:
        conn = sqlite3.connect(self.tenant_db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tenant_id, lake_id, name, status, scheduled_at, completed_at, pilot_name, drone_name,
                   altitude_m, image_count, notes, created_at, updated_at
            FROM surveys
            WHERE tenant_id = ? AND id = ?
        """,
            (tenant_id, survey_id),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_survey(row)

    def list_surveys(self, tenant_id: int, lake_id: int | None = None) -> list[Survey]:
        conn = sqlite3.connect(self.tenant_db_path)
        cursor = conn.cursor()
        query = """
            SELECT id, tenant_id, lake_id, name, status, scheduled_at, completed_at, pilot_name, drone_name,
                   altitude_m, image_count, notes, created_at, updated_at
            FROM surveys
            WHERE tenant_id = ?
        """
        params = [tenant_id]
        if lake_id is not None:
            query += " AND lake_id = ?"
            params.append(lake_id)
        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_survey(row) for row in rows]

    def update_survey_status(self, tenant_id: int, survey_id: int, status: SurveyStatus) -> bool:
        conn = sqlite3.connect(self.tenant_db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE surveys
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND id = ?
        """,
            (status.value, tenant_id, survey_id),
        )
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def _row_to_survey(self, row: tuple) -> Survey:
        return Survey(
            id=row[0],
            tenant_id=row[1],
            lake_id=row[2],
            name=row[3],
            status=SurveyStatus(row[4]),
            scheduled_at=datetime.fromisoformat(row[5]) if row[5] else None,
            completed_at=datetime.fromisoformat(row[6]) if row[6] else None,
            pilot_name=row[7],
            drone_name=row[8],
            altitude_m=row[9],
            image_count=row[10],
            notes=row[11],
            created_at=datetime.fromisoformat(row[12]),
            updated_at=datetime.fromisoformat(row[13]) if row[13] else None,
        )

    def add_image(
        self,
        tenant_id: int,
        survey_id: int,
        filename: str,
        original_path: str,
        thumbnail_path: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        altitude_m: float | None = None,
        captured_at: datetime | None = None,
    ) -> int:
        conn = sqlite3.connect(self.tenant_db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO survey_images (tenant_id, survey_id, filename, original_path, thumbnail_path,
                                       latitude, longitude, altitude_m, captured_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                tenant_id,
                survey_id,
                filename,
                original_path,
                thumbnail_path,
                latitude,
                longitude,
                altitude_m,
                captured_at,
            ),
        )
        image_id = cursor.lastrowid
        cursor.execute(
            """
            UPDATE surveys
            SET image_count = (SELECT COUNT(*) FROM survey_images WHERE survey_id = ?),
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND id = ?
        """,
            (survey_id, tenant_id, survey_id),
        )
        conn.commit()
        conn.close()
        return image_id

    def list_images(self, tenant_id: int, survey_id: int) -> list[SurveyImage]:
        conn = sqlite3.connect(self.tenant_db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tenant_id, survey_id, filename, original_path, thumbnail_path,
                   latitude, longitude, altitude_m, captured_at, created_at
            FROM survey_images
            WHERE tenant_id = ? AND survey_id = ?
            ORDER BY created_at DESC
        """,
            (tenant_id, survey_id),
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_image(row) for row in rows]

    def get_image(self, tenant_id: int, image_id: int) -> SurveyImage | None:
        conn = sqlite3.connect(self.tenant_db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tenant_id, survey_id, filename, original_path, thumbnail_path,
                   latitude, longitude, altitude_m, captured_at, created_at
            FROM survey_images
            WHERE tenant_id = ? AND id = ?
        """,
            (tenant_id, image_id),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_image(row)

    def _row_to_image(self, row: tuple) -> SurveyImage:
        return SurveyImage(
            id=row[0],
            tenant_id=row[1],
            survey_id=row[2],
            filename=row[3],
            original_path=row[4],
            thumbnail_path=row[5],
            latitude=row[6],
            longitude=row[7],
            altitude_m=row[8],
            captured_at=datetime.fromisoformat(row[9]) if row[9] else None,
            created_at=datetime.fromisoformat(row[10]),
        )
