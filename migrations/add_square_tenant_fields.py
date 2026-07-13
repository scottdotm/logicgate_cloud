"""Add Square billing fields to the tenants table.

Run with: python -m logicgate_cloud.migrations.add_square_tenant_fields
"""

import os
import sqlite3


def add_square_fields(db_path: str = None):
    if db_path is None:
        db_path = os.environ.get("SHARED_DB_PATH", "logicgate_shared.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for table in ("tenants", "organizations"):
        for column in ("square_customer_id", "square_subscription_id"):
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
                print(f"Added column: {column} to {table}")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower() or "no such table" in str(e).lower():
                    print(f"Skipped {column} for {table}: {e}")
                else:
                    raise

    conn.commit()
    conn.close()


if __name__ == "__main__":
    add_square_fields()
