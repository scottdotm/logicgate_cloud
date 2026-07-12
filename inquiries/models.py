"""
Pilot inquiry model for the lake management vertical.

Stores leads from the landing page in the shared SQLite database.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Inquiry:
    id: int
    email: str
    name: str
    organization: str | None
    lake_name: str | None
    phone: str | None
    message: str | None
    interest: str
    part_107: str | None
    existing_clients: str | None
    status: str
    created_at: datetime


class InquiryManager:
    """Manages pilot inquiries in the shared database."""

    def __init__(self, shared_db_path: str):
        self.shared_db_path = shared_db_path
        self._ensure_table()

    def _ensure_table(self):
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inquiries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                name TEXT NOT NULL,
                organization TEXT,
                lake_name TEXT,
                phone TEXT,
                message TEXT,
                interest TEXT DEFAULT 'lake_survey',
                part_107 TEXT,
                existing_clients TEXT,
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def create(
        self,
        email: str,
        name: str,
        organization: str | None = None,
        lake_name: str | None = None,
        phone: str | None = None,
        message: str | None = None,
        interest: str = "lake_survey",
        part_107: str | None = None,
        existing_clients: str | None = None,
    ) -> int:
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO inquiries (email, name, organization, lake_name, phone, message, interest, part_107, existing_clients)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                email,
                name,
                organization,
                lake_name,
                phone,
                message,
                interest,
                part_107,
                existing_clients,
            ),
        )
        inquiry_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return inquiry_id

    def list(self, status: str | None = None, limit: int = 100) -> list[Inquiry]:
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()
        query = "SELECT * FROM inquiries"
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_inquiry(row) for row in rows]

    def get(self, inquiry_id: int) -> Inquiry | None:
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM inquiries WHERE id = ?", (inquiry_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_inquiry(row)

    def update_status(self, inquiry_id: int, status: str) -> bool:
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE inquiries SET status = ? WHERE id = ?", (status, inquiry_id))
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def _row_to_inquiry(self, row: tuple) -> Inquiry:
        return Inquiry(
            id=row[0],
            email=row[1],
            name=row[2],
            organization=row[3],
            lake_name=row[4],
            phone=row[5],
            message=row[6],
            interest=row[7],
            part_107=row[8],
            existing_clients=row[9],
            status=row[10],
            created_at=datetime.fromisoformat(row[11]),
        )
