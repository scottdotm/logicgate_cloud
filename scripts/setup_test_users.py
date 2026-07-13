"""
Setup Test Users for LogicGate Multi-Tenant SaaS

This script creates test users for development and testing purposes.
Run this after setting up the database to create default users.
"""

import sqlite3
from pathlib import Path

# Project root is two levels up from this script
BASE_DIR = Path(__file__).parent.parent

SHARED_DB_PATH = BASE_DIR / "logicgate_shared.db"


def create_test_users():
    """Create test users for the horizon tenant"""

    if not SHARED_DB_PATH.exists():
        print(f"[ERROR] Database not found at {SHARED_DB_PATH}")
        print("Please run fix_migration.py first to create the database.")
        return False

    conn = sqlite3.connect(str(SHARED_DB_PATH))
    cursor = conn.cursor()

    # Check if horizon tenant exists
    cursor.execute("SELECT tenant_id FROM tenants WHERE tenant_slug = 'horizon'")
    result = cursor.fetchone()

    if not result:
        print("[ERROR] Horizon tenant not found. Please run fix_migration.py first.")
        conn.close()
        return False

    tenant_id = result[0]
    print(f"[SETUP] Using tenant_id: {tenant_id}")

    # Test users to create
    test_users = [
        {
            "email": "admin@horizonavionics.com",
            "password": "Admin123!",
            "full_name": "System Administrator",
            "role": "admin",
        },
        {
            "email": "operator@horizonavionics.com",
            "password": "Operator123!",
            "full_name": "Field Operator",
            "role": "operator",
        },
        {
            "email": "viewer@horizonavionics.com",
            "password": "Viewer123!",
            "full_name": "Analytics Viewer",
            "role": "viewer",
        },
    ]

    # Import auth system for password hashing
    try:
        from auth.multi_tenant_auth import MultiTenantAuth

        auth = MultiTenantAuth(str(SHARED_DB_PATH), "test_jwt_secret")
    except ImportError:
        print("[WARNING] Auth module not available, using simple password hash")

        # Fallback: simple hash for testing
        def simple_hash(password):
            return hashlib.sha256(password.encode()).hexdigest()

        import hashlib

        auth = None

    created_count = 0

    for user_data in test_users:
        email = user_data["email"]
        password = user_data["password"]
        full_name = user_data["full_name"]
        role = user_data["role"]

        # Check if user already exists
        cursor.execute(
            "SELECT user_id FROM users WHERE tenant_id = ? AND email = ?", (tenant_id, email)
        )

        if cursor.fetchone():
            print(f"[SKIP] User {email} already exists")
            continue

        # Create user
        if auth:
            user_id = auth.create_user(tenant_id, email, password, full_name, role)
        else:
            # Fallback creation
            password_hash = simple_hash(password)
            cursor.execute(
                """
                INSERT INTO users (tenant_id, email, password_hash, full_name, role)
                VALUES (?, ?, ?, ?, ?)
                """,
                (tenant_id, email, password_hash, full_name, role),
            )
            user_id = cursor.lastrowid

        if user_id:
            print(f"[CREATE] User {email} created (role: {role})")
            created_count += 1
        else:
            print(f"[ERROR] Failed to create user {email}")

    conn.commit()
    conn.close()

    if created_count > 0:
        print(f"\n[SUCCESS] Created {created_count} test users")
        print("\nTest Credentials:")
        print("=" * 50)
        for user_data in test_users:
            print(f"Email: {user_data['email']}")
            print(f"Password: {user_data['password']}")
            print(f"Role: {user_data['role']}")
            print("-" * 50)
        print("\nLogin at: http://127.0.0.1:8080/login")
        return True
    else:
        print("[INFO] No new users created (all may already exist)")
        return False


def create_additional_tenant_users():
    """Create users for additional test tenants"""

    conn = sqlite3.connect(str(SHARED_DB_PATH))
    cursor = conn.cursor()

    # Get all tenants
    cursor.execute("SELECT tenant_id, tenant_slug, tenant_name FROM tenants")
    tenants = cursor.fetchall()

    if len(tenants) <= 1:
        print("[INFO] Only one tenant found, skipping additional tenant users")
        conn.close()
        return

    try:
        from auth.multi_tenant_auth import MultiTenantAuth

        auth = MultiTenantAuth(str(SHARED_DB_PATH), "test_jwt_secret")
    except ImportError:
        print("[WARNING] Auth module not available")
        conn.close()
        return

    for tenant_id, tenant_slug, tenant_name in tenants:
        if tenant_slug == "horizon":
            continue  # Skip horizon, already handled

        print(f"\n[SETUP] Creating users for tenant: {tenant_name} ({tenant_slug})")

        # Create admin user for each tenant
        email = f"admin@{tenant_slug}.com"
        password = "Admin123!"
        full_name = f"{tenant_name} Administrator"
        role = "admin"

        user_id = auth.create_user(tenant_id, email, password, full_name, role)

        if user_id:
            print(f"[CREATE] User {email} created")
        else:
            print(f"[SKIP] User {email} already exists or failed")

    conn.commit()
    conn.close()


def main():
    print("=" * 60)
    print("LogicGate Test User Setup")
    print("=" * 60)

    # Create horizon tenant users
    create_test_users()

    # Optionally create users for other tenants
    print("\n[SETUP] Creating users for additional tenants...")
    create_additional_tenant_users()

    print("\n[SETUP] Test user setup complete!")


if __name__ == "__main__":
    main()
