"""
WebSocket Authentication Middleware
Authentication and authorization for WebSocket connections.
"""

import time
from dataclasses import dataclass
from typing import Any

from config.settings import get_settings
from core.exceptions import AuthenticationException, ErrorCode
from infrastructure.cache import get_cache_manager
from infrastructure.logging import LogLevel, get_logger


@dataclass
class WebSocketAuthConfig:
    """WebSocket authentication configuration"""

    token_expiry_seconds: int = 3600  # 1 hour
    refresh_token_expiry_seconds: int = 604800  # 7 days
    require_authentication: bool = True
    allow_anonymous: bool = False
    max_connections_per_user: int = 10


class WebSocketAuthMiddleware:
    """WebSocket authentication middleware"""

    def __init__(self, config: WebSocketAuthConfig = None):
        self.config = config or WebSocketAuthConfig()
        self.logger = get_logger("websocket_auth", LogLevel.INFO)
        self.cache_manager = get_cache_manager()
        self.settings = get_settings()

        # Track active connections
        self._active_connections: dict[str, dict[str, Any]] = {}

    async def authenticate_connection(
        self, connection_id: str, token: str | None = None, headers: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Authenticate a WebSocket connection

        Args:
            connection_id: Unique connection identifier
            token: Authentication token
            headers: HTTP headers from connection request

        Returns:
            Authentication context with user info
        """
        # Check if authentication is required
        if not self.config.require_authentication:
            return self._create_anonymous_context(connection_id)

        # Check if anonymous connections are allowed
        if self.config.allow_anonymous and not token:
            return self._create_anonymous_context(connection_id)

        # Validate token
        if not token:
            self.logger.warning(
                "Authentication failed: No token provided", connection_id=connection_id
            )
            raise AuthenticationException(
                "Authentication token required", ErrorCode.AUTH_TOKEN_INVALID
            )

        # Validate token from cache or database
        user_info = await self._validate_token(token)

        if not user_info:
            self.logger.warning("Authentication failed: Invalid token", connection_id=connection_id)
            raise AuthenticationException(
                "Invalid authentication token", ErrorCode.AUTH_TOKEN_INVALID
            )

        # Check connection limits
        await self._check_connection_limit(user_info["user_id"])

        # Register connection
        self._register_connection(connection_id, user_info)

        self.logger.info(
            "WebSocket connection authenticated",
            connection_id=connection_id,
            user_id=user_info["user_id"],
        )

        return {
            "authenticated": True,
            "user_id": user_info["user_id"],
            "connection_id": connection_id,
            "permissions": user_info.get("permissions", []),
            "authenticated_at": time.time(),
        }

    def _create_anonymous_context(self, connection_id: str) -> dict[str, Any]:
        """Create anonymous authentication context"""
        return {
            "authenticated": False,
            "user_id": "anonymous",
            "connection_id": connection_id,
            "permissions": [],
            "authenticated_at": time.time(),
        }

    async def _validate_token(self, token: str) -> dict[str, Any] | None:
        """Validate authentication token

        Args:
            token: Authentication token

        Returns:
            User info if valid, None otherwise
        """
        # Check cache first
        cache_key = f"ws_token:{token}"
        cached_info = self.cache_manager.get(cache_key)

        if cached_info:
            return cached_info

        # Validate token (in production, this would validate JWT or check database)
        # For now, we'll do a simple validation
        try:
            # Simulate token validation
            if token.startswith("valid_"):
                user_info = {
                    "user_id": token.replace("valid_", ""),
                    "permissions": ["read", "write"],
                    "token": token,
                }

                # Cache the validated token
                self.cache_manager.set(cache_key, user_info, ttl=self.config.token_expiry_seconds)

                return user_info
        except Exception as e:
            self.logger.error("Token validation error", error=str(e))

        return None

    async def _check_connection_limit(self, user_id: str):
        """Check if user has exceeded connection limit"""
        user_connections = [
            conn for conn in self._active_connections.values() if conn.get("user_id") == user_id
        ]

        if len(user_connections) >= self.config.max_connections_per_user:
            self.logger.warning(
                "Connection limit exceeded",
                user_id=user_id,
                current=len(user_connections),
                limit=self.config.max_connections_per_user,
            )
            raise AuthenticationException(
                f"Maximum connections ({self.config.max_connections_per_user}) exceeded",
                ErrorCode.AUTH_PERMISSION_DENIED,
            )

    def _register_connection(self, connection_id: str, user_info: dict[str, Any]):
        """Register an authenticated connection"""
        self._active_connections[connection_id] = {
            "user_id": user_info["user_id"],
            "authenticated_at": time.time(),
            "permissions": user_info.get("permissions", []),
            "token": user_info.get("token"),
        }

    async def disconnect(self, connection_id: str):
        """Handle connection disconnection"""
        if connection_id in self._active_connections:
            user_id = self._active_connections[connection_id]["user_id"]
            del self._active_connections[connection_id]

            self.logger.info(
                "WebSocket connection disconnected", connection_id=connection_id, user_id=user_id
            )

    def is_authenticated(self, connection_id: str) -> bool:
        """Check if a connection is authenticated"""
        if connection_id not in self._active_connections:
            return False

        return self._active_connections[connection_id].get("authenticated", True)

    def get_user_id(self, connection_id: str) -> str | None:
        """Get user ID for a connection"""
        if connection_id not in self._active_connections:
            return None

        return self._active_connections[connection_id].get("user_id")

    def has_permission(self, connection_id: str, permission: str) -> bool:
        """Check if connection has specific permission"""
        if connection_id not in self._active_connections:
            return False

        permissions = self._active_connections[connection_id].get("permissions", [])
        return permission in permissions or "admin" in permissions

    def get_active_connections(self) -> dict[str, dict[str, Any]]:
        """Get all active connections"""
        return self._active_connections.copy()

    def get_user_connections(self, user_id: str) -> list:
        """Get all connections for a specific user"""
        return [
            conn_id
            for conn_id, conn_info in self._active_connections.items()
            if conn_info.get("user_id") == user_id
        ]


class WebSocketMessageAuthenticator:
    """Authenticate individual WebSocket messages"""

    def __init__(self, auth_middleware: WebSocketAuthMiddleware):
        self.auth_middleware = auth_middleware
        self.logger = get_logger("websocket_message_auth", LogLevel.INFO)

    async def authenticate_message(self, connection_id: str, message: dict[str, Any]) -> bool:
        """Authenticate a message from a connection

        Args:
            connection_id: Connection identifier
            message: Message to authenticate

        Returns:
            True if message is authorized
        """
        # Check if connection is authenticated
        if not self.auth_middleware.is_authenticated(connection_id):
            self.logger.warning(
                "Message from unauthenticated connection", connection_id=connection_id
            )
            return False

        # Check message-specific permissions if needed
        required_permission = message.get("required_permission")
        if required_permission and not self.auth_middleware.has_permission(
            connection_id, required_permission
        ):
            self.logger.warning(
                "Permission denied for message",
                connection_id=connection_id,
                permission=required_permission,
            )
            return False

        return True

    async def validate_message_format(self, message: dict[str, Any]) -> bool:
        """Validate message format"""
        required_fields = ["type", "data"]

        for field in required_fields:
            if field not in message:
                self.logger.warning("Invalid message format", missing_field=field)
                return False

        return True


def get_websocket_auth_middleware() -> WebSocketAuthMiddleware:
    """Get the singleton WebSocket authentication middleware instance"""
    return WebSocketAuthMiddleware()
