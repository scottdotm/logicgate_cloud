"""
Multi-Tenant Authentication System for LogicGate SaaS

This system handles:
- User authentication with tenant isolation
- Role-based access control (RBAC)
- Session management
- API key authentication
- SSO integration (Azure AD, Okta, Google Workspace)
- Password management
- Multi-factor authentication
"""

import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from typing import Any

import jwt


class MultiTenantAuth:
    """Multi-tenant authentication system"""

    def __init__(self, shared_db_path: str, jwt_secret: str):
        self.shared_db_path = shared_db_path
        self.jwt_secret = jwt_secret
        self._ensure_auth_tables()

    def _ensure_auth_tables(self):
        """Ensure authentication tables exist"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        # Users table (already in schema, but ensure it exists)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id VARCHAR(36) NOT NULL,
                email VARCHAR(255) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                role VARCHAR(50) DEFAULT 'operator',
                status VARCHAR(50) DEFAULT 'active',
                last_login_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tenant_id, email)
            )
        """)

        # Create indexes for users table (with error handling)
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tenant_users ON users(tenant_id)")
        except sqlite3.Error as e:
            print(f"[AUTH] Warning: Could not create idx_tenant_users index: {e}")

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_email ON users(email)")
        except sqlite3.Error as e:
            print(f"[AUTH] Warning: Could not create idx_user_email index: {e}")

        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id VARCHAR(64) PRIMARY KEY,
                user_id INTEGER NOT NULL,
                tenant_id VARCHAR(36) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address VARCHAR(45),
                user_agent TEXT
            )
        """)

        # Create indexes for sessions table (with error handling)
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_user ON sessions(user_id)")
        except sqlite3.Error as e:
            print(f"[AUTH] Warning: Could not create idx_session_user index: {e}")

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_tenant ON sessions(tenant_id)")
        except sqlite3.Error as e:
            print(f"[AUTH] Warning: Could not create idx_session_tenant index: {e}")

        # MFA secrets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mfa_secrets (
                user_id INTEGER PRIMARY KEY,
                secret VARCHAR(32) NOT NULL,
                backup_codes TEXT,
                enabled BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # SSO identities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sso_identities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider VARCHAR(50) NOT NULL,
                provider_user_id VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                raw_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(provider, provider_user_id)
            )
        """)

        # Create index for sso_identities table (with error handling)
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sso_user ON sso_identities(user_id)")
        except sqlite3.Error as e:
            print(f"[AUTH] Warning: Could not create idx_sso_user index: {e}")

        # Password reset tokens
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                token VARCHAR(64) PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # API keys for tenant-scoped service access
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                key_name VARCHAR(255) NOT NULL,
                key_hash VARCHAR(64) NOT NULL,
                key_prefix VARCHAR(16) NOT NULL,
                status VARCHAR(20) DEFAULT 'active',
                last_used_at TIMESTAMP,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tenant_id, key_name)
            )
        """)

        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash, key_prefix)"
            )
        except sqlite3.Error as e:
            print(f"[AUTH] Warning: Could not create idx_api_keys_hash index: {e}")

        conn.commit()
        conn.close()

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt or PBKDF2"""
        # Using PBKDF2 for simplicity (bcrypt recommended for production)
        salt = secrets.token_bytes(32)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
        return f"pbkdf2_sha256${salt.hex()}${key.hex()}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        try:
            algorithm, salt_hex, key_hex = password_hash.split("$")
            salt = bytes.fromhex(salt_hex)
            key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
            return secrets.compare_digest(key.hex(), key_hex)
        except Exception:
            return False

    def create_user(
        self,
        tenant_id: str,
        email: str,
        password: str,
        full_name: str = None,
        role: str = "operator",
    ) -> int | None:
        """Create a new user for a tenant"""
        try:
            password_hash = self.hash_password(password)

            conn = sqlite3.connect(self.shared_db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO users (tenant_id, email, password_hash, full_name, role)
                VALUES (?, ?, ?, ?, ?)
                """,
                (tenant_id, email, password_hash, full_name, role),
            )

            user_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return user_id
        except sqlite3.IntegrityError:
            # User already exists
            return None
        except Exception as e:
            print(f"Error creating user: {e}")
            return None

    def authenticate_user(self, tenant_id: str, email: str, password: str) -> dict[str, Any] | None:
        """Authenticate a user with email and password"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT user_id, tenant_id, email, password_hash, full_name, role, status
            FROM users
            WHERE tenant_id = ? AND email = ? AND status = 'active'
            """,
            (tenant_id, email),
        )

        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        return self._authenticate_result(result, password)

    def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Find a user by email across all tenants"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT user_id, tenant_id, email, full_name, role, status
            FROM users
            WHERE email = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (email,),
        )

        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        return {
            "user_id": result[0],
            "tenant_id": result[1],
            "email": result[2],
            "full_name": result[3],
            "role": result[4],
            "status": result[5],
        }

    def authenticate_user_by_email(self, email: str, password: str) -> dict[str, Any] | None:
        """Authenticate a user by email alone, looking up the tenant automatically"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT user_id, tenant_id, email, password_hash, full_name, role, status
            FROM users
            WHERE email = ? AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (email,),
        )

        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        return self._authenticate_result(result, password)

    def _authenticate_result(self, result: tuple, password: str) -> dict[str, Any] | None:
        """Common authentication logic from a database row"""
        user_id, tenant_id, email, password_hash, full_name, role, status = result

        if not self.verify_password(password, password_hash):
            return None

        # Update last login
        self._update_last_login(user_id)

        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "email": email,
            "full_name": full_name,
            "role": role,
        }

    def _update_last_login(self, user_id: int):
        """Update user's last login timestamp"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,)
        )

        conn.commit()
        conn.close()

    def create_session(
        self, user_id: int, tenant_id: str, ip_address: str = None, user_agent: str = None
    ) -> str:
        """Create a new session for a user"""
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=24)

        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO sessions (session_id, user_id, tenant_id, expires_at, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, user_id, tenant_id, expires_at.isoformat(), ip_address, user_agent),
        )

        conn.commit()
        conn.close()

        return session_id

    def validate_session(self, session_id: str) -> dict[str, Any] | None:
        """Validate a session and return user info"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT s.session_id, s.user_id, s.tenant_id, s.expires_at,
                   u.email, u.full_name, u.role, u.status
            FROM sessions s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.session_id = ? AND s.expires_at > CURRENT_TIMESTAMP
            """,
            (session_id,),
        )

        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        session_id, user_id, tenant_id, expires_at, email, full_name, role, status = result

        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "email": email,
            "full_name": full_name,
            "role": role,
            "session_id": session_id,
        }

    def revoke_session(self, session_id: str) -> bool:
        """Revoke a session"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

        conn.commit()
        conn.close()
        return True

    def revoke_all_user_sessions(self, user_id: int) -> bool:
        """Revoke all sessions for a user"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

        conn.commit()
        conn.close()
        return True

    def generate_jwt(self, user_info: dict[str, Any], expires_hours: int = 24) -> str:
        """Generate a JWT token for API authentication"""
        payload = {
            "user_id": user_info["user_id"],
            "tenant_id": user_info["tenant_id"],
            "email": user_info["email"],
            "role": user_info["role"],
            "exp": datetime.utcnow() + timedelta(hours=expires_hours),
            "iat": datetime.utcnow(),
        }

        token = jwt.encode(payload, self.jwt_secret, algorithm="HS256")
        return token

    def validate_jwt(self, token: str) -> dict[str, Any] | None:
        """Validate a JWT token"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def create_api_key(
        self, tenant_id: int, user_id: int, key_name: str, expires_at: datetime | None = None
    ) -> str | None:
        """Create a new API key for a tenant user. Returns the plaintext key once."""
        import hashlib

        # Generate a key with a recognizable prefix
        prefix = "lg_"
        random_part = secrets.token_urlsafe(32)
        api_key = f"{prefix}{random_part}"

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key_prefix = api_key[:10]

        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO api_keys (tenant_id, user_id, key_name, key_hash, key_prefix, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    tenant_id,
                    user_id,
                    key_name,
                    key_hash,
                    key_prefix,
                    expires_at.isoformat() if expires_at else None,
                ),
            )
            conn.commit()
            conn.close()
            return api_key
        except sqlite3.IntegrityError:
            conn.close()
            return None

    def revoke_api_key(self, tenant_id: int, key_name: str) -> bool:
        """Revoke an API key by name."""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE api_keys SET status = 'revoked' WHERE tenant_id = ? AND key_name = ?
        """,
            (tenant_id, key_name),
        )
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def list_api_keys(self, tenant_id: int) -> list[dict[str, Any]]:
        """List active API keys for a tenant."""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, key_name, key_prefix, status, last_used_at, expires_at, created_at
            FROM api_keys
            WHERE tenant_id = ?
            ORDER BY created_at DESC
        """,
            (tenant_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": row[0],
                "key_name": row[1],
                "key_prefix": row[2],
                "status": row[3],
                "last_used_at": row[4],
                "expires_at": row[5],
                "created_at": row[6],
            }
            for row in rows
        ]

    def authenticate_api_key(self, api_key: str) -> dict[str, Any] | None:
        """Authenticate using API key"""
        import hashlib

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key_prefix = api_key[:10]

        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT ak.tenant_id, ak.key_name, ak.user_id, u.email, u.role
            FROM api_keys ak
            JOIN users u ON ak.user_id = u.user_id
            WHERE ak.key_hash = ? AND ak.key_prefix = ? AND ak.status = 'active'
            LIMIT 1
            """,
            (key_hash, key_prefix),
        )

        result = cursor.fetchone()

        if result:
            cursor.execute(
                """
                UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP
                WHERE key_hash = ? AND key_prefix = ?
            """,
                (key_hash, key_prefix),
            )
            conn.commit()

        conn.close()

        if result:
            return {
                "tenant_id": result[0],
                "key_name": result[1],
                "user_id": result[2],
                "email": result[3],
                "role": result[4],
                "auth_type": "api_key",
            }

        return None

    def check_role_permission(self, user_role: str, required_role: str) -> bool:
        """Check if user role has required permission"""
        role_hierarchy = {"viewer": 1, "operator": 2, "admin": 3}

        user_level = role_hierarchy.get(user_role, 0)
        required_level = role_hierarchy.get(required_role, 0)

        return user_level >= required_level

    def require_role(self, required_role: str):
        """Decorator to require specific role"""

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Get user from context (would be set by middleware)
                user_info = getattr(args[0], "user_info", None)

                if not user_info:
                    raise PermissionError("Not authenticated")

                if not self.check_role_permission(user_info.get("role"), required_role):
                    raise PermissionError(f"Role '{required_role}' required")

                return func(*args, **kwargs)

            return wrapper

        return decorator

    def require_tenant_access(self, user_tenant_id: str, required_tenant_id: str) -> bool:
        """Check if user has access to required tenant"""
        return user_tenant_id == required_tenant_id

    def create_password_reset_token(self, email: str) -> str | None:
        """Create a password reset token"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT user_id FROM users WHERE email = ? AND status = 'active'", (email,))

        result = cursor.fetchone()

        if not result:
            conn.close()
            return None

        user_id = result[0]
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=1)

        cursor.execute(
            """
            INSERT INTO password_reset_tokens (token, user_id, expires_at)
            VALUES (?, ?, ?)
            """,
            (token, user_id, expires_at.isoformat()),
        )

        conn.commit()
        conn.close()

        return token

    def validate_password_reset_token(self, token: str) -> int | None:
        """Validate a password reset token and return user_id"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT user_id, expires_at, used
            FROM password_reset_tokens
            WHERE token = ?
            """,
            (token,),
        )

        result = cursor.fetchone()

        if not result:
            conn.close()
            return None

        user_id, expires_at, used = result

        if used or datetime.fromisoformat(expires_at) < datetime.now():
            conn.close()
            return None

        return user_id

    def reset_password(self, token: str, new_password: str) -> bool:
        """Reset password using token"""
        user_id = self.validate_password_reset_token(token)

        if not user_id:
            return False

        password_hash = self.hash_password(new_password)

        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE user_id = ?", (password_hash, user_id)
            )

            cursor.execute("UPDATE password_reset_tokens SET used = TRUE WHERE token = ?", (token,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error resetting password: {e}")
            conn.close()
            return False

    def get_tenant_users(self, tenant_id: str) -> list[dict[str, Any]]:
        """Get all users for a tenant"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT user_id, email, full_name, role, status, last_login_at, created_at
            FROM users
            WHERE tenant_id = ?
            ORDER BY created_at DESC
            """,
            (tenant_id,),
        )

        users = []
        for row in cursor.fetchall():
            users.append(
                {
                    "user_id": row[0],
                    "email": row[1],
                    "full_name": row[2],
                    "role": row[3],
                    "status": row[4],
                    "last_login_at": row[5],
                    "created_at": row[6],
                }
            )

        conn.close()
        return users

    def update_user_role(self, user_id: int, new_role: str) -> bool:
        """Update user role"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute("UPDATE users SET role = ? WHERE user_id = ?", (new_role, user_id))

        conn.commit()
        conn.close()
        return True

    def deactivate_user(self, user_id: int) -> bool:
        """Deactivate a user"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute("UPDATE users SET status = 'inactive' WHERE user_id = ?", (user_id,))

        conn.commit()
        conn.close()
        return True


class AuthMiddleware:
    """Authentication middleware for HTTP handlers"""

    def __init__(self, auth_system: MultiTenantAuth):
        self.auth = auth_system

    def authenticate_request(self, handler) -> dict[str, Any] | None:
        """Authenticate an HTTP request"""
        # Check for session cookie
        cookie_header = handler.headers.get("Cookie", "")
        session_id = self._extract_cookie(cookie_header, "session_id")

        if session_id:
            user_info = self.auth.validate_session(session_id)
            if user_info:
                return user_info

        # Check for JWT token in Authorization header
        auth_header = handler.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            user_info = self.auth.validate_jwt(token)
            if user_info:
                return user_info

        # Check for API key
        api_key = handler.headers.get("X-API-Key")
        if api_key:
            user_info = self.auth.authenticate_api_key(api_key)
            if user_info:
                return user_info

        return None

    def _extract_cookie(self, cookie_header: str, cookie_name: str) -> str | None:
        """Extract a specific cookie from the Cookie header"""
        cookies = cookie_header.split(";")
        for cookie in cookies:
            if "=" in cookie:
                name, value = cookie.strip().split("=", 1)
                if name == cookie_name:
                    return value
        return None

    def require_auth(self, required_role: str = None):
        """Decorator to require authentication"""

        def decorator(func):
            @wraps(func)
            def wrapper(handler, *args, **kwargs):
                user_info = self.authenticate_request(handler)

                if not user_info:
                    handler.send_response(401)
                    handler.send_header("Content-Type", "application/json")
                    handler.end_headers()
                    handler.wfile.write(b'{"error": "Authentication required"}')
                    return

                # Attach user info to handler
                handler.user_info = user_info

                # Check role if required
                if required_role and not self.auth.check_role_permission(
                    user_info.get("role"), required_role
                ):
                    handler.send_response(403)
                    handler.send_header("Content-Type", "application/json")
                    handler.end_headers()
                    handler.wfile.write(b'{"error": "Insufficient permissions"}')
                    return

                return func(handler, *args, **kwargs)

            return wrapper

        return decorator


def apply_auth_middleware(handler_class, auth_middleware: AuthMiddleware):
    """Apply authentication middleware to a request handler class"""
    original_do_GET = handler_class.do_GET  # noqa: N806
    original_do_POST = handler_class.do_POST  # noqa: N806

    def do_GET_with_auth(self):  # noqa: N802
        # Try to authenticate
        user_info = auth_middleware.authenticate_request(self)
        if user_info:
            self.user_info = user_info

        return original_do_GET(self)

    def do_POST_with_auth(self):  # noqa: N802
        # Try to authenticate
        user_info = auth_middleware.authenticate_request(self)
        if user_info:
            self.user_info = user_info

        return original_do_POST(self)

    handler_class.do_GET = do_GET_with_auth
    handler_class.do_POST = do_POST_with_auth

    return handler_class
