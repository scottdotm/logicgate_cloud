"""
Unit tests for Multi-Tenant Authentication System
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

# Add workspace root to sys.path for logicgate_cloud imports
_WORKSPACE_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_WORKSPACE_ROOT))

from logicgate_cloud.auth.multi_tenant_auth import AuthMiddleware, MultiTenantAuth  # noqa: E402


class TestMultiTenantAuth(unittest.TestCase):
    """Test cases for MultiTenantAuth"""

    def setUp(self):
        """Set up test database"""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")  # noqa: SIM115
        self.test_db_path = self.test_db.name
        self.test_db.close()

        self.auth = MultiTenantAuth(self.test_db_path, "test_jwt_secret_at_least_32_chars")

        # Create test tenant
        self.tenant_id = "test-tenant-123"
        self._create_test_tenant()

    def tearDown(self):
        """Clean up test database"""
        try:
            if os.path.exists(self.test_db_path):
                os.unlink(self.test_db_path)
        except PermissionError:
            # Windows file locking - skip cleanup
            pass

    def _create_test_tenant(self):
        """Create a test tenant in the database"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                tenant_id VARCHAR(36) PRIMARY KEY,
                tenant_name VARCHAR(255) NOT NULL,
                tenant_slug VARCHAR(100) UNIQUE NOT NULL,
                subscription_tier VARCHAR(50) DEFAULT 'starter',
                status VARCHAR(50) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute(
            "INSERT OR IGNORE INTO tenants (tenant_id, tenant_name, tenant_slug) VALUES (?, ?, ?)",
            (self.tenant_id, "Test Tenant", "test"),
        )

        conn.commit()
        conn.close()

    def test_password_hashing(self):
        """Test password hashing and verification"""
        password = "TestPassword123!"
        password_hash = self.auth.hash_password(password)

        # Hash should be in format: algorithm$salt$key
        self.assertIn("$", password_hash)
        self.assertTrue(password_hash.startswith("pbkdf2_sha256$"))

        # Verify correct password
        self.assertTrue(self.auth.verify_password(password, password_hash))

        # Verify incorrect password
        self.assertFalse(self.auth.verify_password("WrongPassword", password_hash))

    def test_user_creation(self):
        """Test user creation"""
        email = "test@example.com"
        password = "TestPassword123!"
        full_name = "Test User"
        role = "operator"

        user_id = self.auth.create_user(self.tenant_id, email, password, full_name, role)

        self.assertIsNotNone(user_id)
        self.assertIsInstance(user_id, int)

        # Test duplicate user creation
        duplicate_id = self.auth.create_user(self.tenant_id, email, password, full_name, role)
        self.assertIsNone(duplicate_id)

    def test_user_authentication(self):
        """Test user authentication"""
        email = "auth@example.com"
        password = "AuthPassword123!"

        # Create user
        user_id = self.auth.create_user(self.tenant_id, email, password)
        self.assertIsNotNone(user_id)

        # Authenticate with correct credentials
        user_info = self.auth.authenticate_user(self.tenant_id, email, password)
        self.assertIsNotNone(user_info)
        self.assertEqual(user_info["email"], email)
        self.assertEqual(user_info["tenant_id"], self.tenant_id)
        self.assertEqual(user_info["role"], "operator")

        # Authenticate with wrong password
        wrong_info = self.auth.authenticate_user(self.tenant_id, email, "WrongPassword")
        self.assertIsNone(wrong_info)

        # Authenticate with wrong tenant
        wrong_tenant_info = self.auth.authenticate_user("wrong-tenant", email, password)
        self.assertIsNone(wrong_tenant_info)

    def test_session_management(self):
        """Test session creation and validation"""
        email = "session@example.com"
        password = "SessionPassword123!"

        # Create user
        user_id = self.auth.create_user(self.tenant_id, email, password)

        # Create session
        session_id = self.auth.create_session(user_id, self.tenant_id, "127.0.0.1", "TestAgent")

        self.assertIsNotNone(session_id)
        self.assertIsInstance(session_id, str)

        # Validate session
        session_info = self.auth.validate_session(session_id)
        self.assertIsNotNone(session_info)
        self.assertEqual(session_info["user_id"], user_id)
        self.assertEqual(session_info["tenant_id"], self.tenant_id)

        # Revoke session
        revoked = self.auth.revoke_session(session_id)
        self.assertTrue(revoked)

        # Validate revoked session
        revoked_info = self.auth.validate_session(session_id)
        self.assertIsNone(revoked_info)

    def test_jwt_tokens(self):
        """Test JWT token generation and validation"""
        email = "jwt@example.com"
        password = "JwtPassword123!"

        # Create user
        user_id = self.auth.create_user(self.tenant_id, email, password)
        self.assertIsNotNone(user_id)
        user_info = self.auth.authenticate_user(self.tenant_id, email, password)

        # Generate JWT
        token = self.auth.generate_jwt(user_info)
        self.assertIsNotNone(token)
        self.assertIsInstance(token, str)

        # Validate JWT
        decoded = self.auth.validate_jwt(token)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["email"], email)
        self.assertEqual(decoded["tenant_id"], self.tenant_id)
        self.assertEqual(decoded["role"], "operator")

    def test_role_permissions(self):
        """Test role-based permission checking"""
        # Test role hierarchy
        self.assertTrue(self.auth.check_role_permission("admin", "viewer"))
        self.assertTrue(self.auth.check_role_permission("admin", "operator"))
        self.assertTrue(self.auth.check_role_permission("admin", "admin"))

        self.assertTrue(self.auth.check_role_permission("operator", "viewer"))
        self.assertTrue(self.auth.check_role_permission("operator", "operator"))
        self.assertFalse(self.auth.check_role_permission("operator", "admin"))

        self.assertTrue(self.auth.check_role_permission("viewer", "viewer"))
        self.assertFalse(self.auth.check_role_permission("viewer", "operator"))
        self.assertFalse(self.auth.check_role_permission("viewer", "admin"))

    def test_get_tenant_users(self):
        """Test retrieving all users for a tenant"""
        # Create multiple users
        self.auth.create_user(self.tenant_id, "user1@example.com", "Pass123!", "User 1", "admin")
        self.auth.create_user(self.tenant_id, "user2@example.com", "Pass123!", "User 2", "operator")
        self.auth.create_user(self.tenant_id, "user3@example.com", "Pass123!", "User 3", "viewer")

        # Get all users
        users = self.auth.get_tenant_users(self.tenant_id)

        self.assertEqual(len(users), 3)

        # Verify user roles
        roles = [user["role"] for user in users]
        self.assertIn("admin", roles)
        self.assertIn("operator", roles)
        self.assertIn("viewer", roles)


class TestAuthMiddleware(unittest.TestCase):
    """Test cases for AuthMiddleware"""

    def setUp(self):
        """Set up test database and middleware"""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")  # noqa: SIM115
        self.test_db_path = self.test_db.name
        self.test_db.close()

        self.auth = MultiTenantAuth(self.test_db_path, "test_jwt_secret_at_least_32_chars")
        self.middleware = AuthMiddleware(self.auth)

        # Create test tenant and user
        self.tenant_id = "test-tenant-456"
        self._create_test_tenant()
        self.user_id = self.auth.create_user(self.tenant_id, "middleware@example.com", "Pass123!")

    def tearDown(self):
        """Clean up test database"""
        try:
            if os.path.exists(self.test_db_path):
                os.unlink(self.test_db_path)
        except PermissionError:
            # Windows file locking - skip cleanup
            pass

    def _create_test_tenant(self):
        """Create a test tenant in the database"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                tenant_id VARCHAR(36) PRIMARY KEY,
                tenant_name VARCHAR(255) NOT NULL,
                tenant_slug VARCHAR(100) UNIQUE NOT NULL,
                subscription_tier VARCHAR(50) DEFAULT 'starter',
                status VARCHAR(50) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute(
            "INSERT OR IGNORE INTO tenants (tenant_id, tenant_name, tenant_slug) VALUES (?, ?, ?)",
            (self.tenant_id, "Test Tenant", "test"),
        )

        conn.commit()
        conn.close()

    def test_cookie_extraction(self):
        """Test cookie extraction from header"""
        # Test valid cookie
        cookie_header = "session_id=test_session_123; other=value"
        session_id = self.middleware._extract_cookie(cookie_header, "session_id")
        self.assertEqual(session_id, "test_session_123")

        # Test missing cookie
        missing = self.middleware._extract_cookie(cookie_header, "missing")
        self.assertIsNone(missing)

        # Test empty header
        empty = self.middleware._extract_cookie("", "session_id")
        self.assertIsNone(empty)


if __name__ == "__main__":
    unittest.main()
