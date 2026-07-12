"""
Test WebSocket Authentication Middleware
Tests WebSocket connection authentication and message authorization.
"""

import asyncio
import sys
from pathlib import Path

# Add workspace root to sys.path for logicgate_cloud imports
_WORKSPACE_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_WORKSPACE_ROOT))


def test_websocket_auth_config():
    """Test WebSocket authentication configuration"""
    print("Testing WebSocket authentication configuration...")

    from logicgate_cloud.api.websocket_auth import WebSocketAuthConfig

    config = WebSocketAuthConfig()

    assert config.token_expiry_seconds == 3600
    assert config.refresh_token_expiry_seconds == 604800
    assert config.require_authentication is True
    assert config.allow_anonymous is False
    assert config.max_connections_per_user == 10

    print("✓ WebSocket authentication configuration test passed")


def test_websocket_auth_middleware_initialization():
    """Test WebSocket authentication middleware initialization"""
    print("Testing WebSocket authentication middleware initialization...")

    from logicgate_cloud.api.websocket_auth import WebSocketAuthConfig, WebSocketAuthMiddleware

    config = WebSocketAuthConfig()
    middleware = WebSocketAuthMiddleware(config)

    assert middleware.config is not None
    assert middleware.logger is not None
    assert middleware.cache_manager is not None
    assert middleware._active_connections == {}

    print("✓ WebSocket authentication middleware initialization test passed")


async def test_anonymous_connection():
    """Test anonymous WebSocket connection"""
    print("Testing anonymous WebSocket connection...")

    from logicgate_cloud.api.websocket_auth import WebSocketAuthConfig, WebSocketAuthMiddleware

    config = WebSocketAuthConfig(require_authentication=False)
    middleware = WebSocketAuthMiddleware(config)

    context = await middleware.authenticate_connection("conn_1", None)

    assert context["authenticated"] is False
    assert context["user_id"] == "anonymous"
    assert context["connection_id"] == "conn_1"

    print("✓ Anonymous WebSocket connection test passed")


async def test_token_validation():
    """Test token validation"""
    print("Testing token validation...")

    from logicgate_cloud.api.websocket_auth import WebSocketAuthConfig, WebSocketAuthMiddleware

    config = WebSocketAuthConfig()
    middleware = WebSocketAuthMiddleware(config)

    # Test valid token
    user_info = await middleware._validate_token("valid_user123")
    assert user_info is not None
    assert user_info["user_id"] == "user123"

    # Test invalid token
    user_info = await middleware._validate_token("invalid_token")
    assert user_info is None

    print("✓ Token validation test passed")


async def test_authentication_with_valid_token():
    """Test authentication with valid token"""
    print("Testing authentication with valid token...")

    from logicgate_cloud.api.websocket_auth import WebSocketAuthConfig, WebSocketAuthMiddleware

    config = WebSocketAuthConfig()
    middleware = WebSocketAuthMiddleware(config)

    context = await middleware.authenticate_connection("conn_2", "valid_user456")

    assert context["authenticated"] is True
    assert context["user_id"] == "user456"
    assert context["connection_id"] == "conn_2"
    assert "read" in context["permissions"]

    print("✓ Authentication with valid token test passed")


async def test_authentication_with_invalid_token():
    """Test authentication with invalid token"""
    print("Testing authentication with invalid token...")

    from core.exceptions import AuthenticationException

    from logicgate_cloud.api.websocket_auth import WebSocketAuthConfig, WebSocketAuthMiddleware

    config = WebSocketAuthConfig()
    middleware = WebSocketAuthMiddleware(config)

    try:
        await middleware.authenticate_connection("conn_3", "invalid_token")
        raise AssertionError("Should have raised AuthenticationException")
    except AuthenticationException as e:
        assert "Invalid authentication token" in str(e)

    print("✓ Authentication with invalid token test passed")


async def test_connection_limit():
    """Test connection limit enforcement"""
    print("Testing connection limit enforcement...")

    from core.exceptions import AuthenticationException

    from logicgate_cloud.api.websocket_auth import WebSocketAuthConfig, WebSocketAuthMiddleware

    config = WebSocketAuthConfig(max_connections_per_user=2)
    middleware = WebSocketAuthMiddleware(config)

    # Create connections up to limit
    await middleware.authenticate_connection("conn_4", "valid_user1")
    await middleware.authenticate_connection("conn_5", "valid_user1")

    # Try to exceed limit
    try:
        await middleware.authenticate_connection("conn_6", "valid_user1")
        raise AssertionError("Should have raised AuthenticationException")
    except AuthenticationException as e:
        assert "Maximum connections" in str(e)

    print("✓ Connection limit test passed")


async def test_connection_registration():
    """Test connection registration"""
    print("Testing connection registration...")

    from logicgate_cloud.api.websocket_auth import WebSocketAuthConfig, WebSocketAuthMiddleware

    config = WebSocketAuthConfig()
    middleware = WebSocketAuthMiddleware(config)

    await middleware.authenticate_connection("conn_7", "valid_user2")

    assert "conn_7" in middleware._active_connections
    assert middleware._active_connections["conn_7"]["user_id"] == "user2"

    print("✓ Connection registration test passed")


async def test_connection_disconnection():
    """Test connection disconnection"""
    print("Testing connection disconnection...")

    from logicgate_cloud.api.websocket_auth import WebSocketAuthConfig, WebSocketAuthMiddleware

    config = WebSocketAuthConfig()
    middleware = WebSocketAuthMiddleware(config)

    await middleware.authenticate_connection("conn_8", "valid_user3")
    assert "conn_8" in middleware._active_connections

    await middleware.disconnect("conn_8")
    assert "conn_8" not in middleware._active_connections

    print("✓ Connection disconnection test passed")


def test_is_authenticated():
    """Test is_authenticated check"""
    print("Testing is_authenticated check...")

    from logicgate_cloud.api.websocket_auth import WebSocketAuthConfig, WebSocketAuthMiddleware

    async def run_test():
        config = WebSocketAuthConfig()
        middleware = WebSocketAuthMiddleware(config)

        # Not authenticated initially
        assert middleware.is_authenticated("conn_9") is False

        # After authentication
        await middleware.authenticate_connection("conn_9", "valid_user4")
        assert middleware.is_authenticated("conn_9") is True

    asyncio.run(run_test())

    print("✓ is_authenticated check test passed")


def test_get_user_id():
    """Test get_user_id"""
    print("Testing get_user_id...")

    from logicgate_cloud.api.websocket_auth import WebSocketAuthConfig, WebSocketAuthMiddleware

    async def run_test():
        config = WebSocketAuthConfig()
        middleware = WebSocketAuthMiddleware(config)

        # No user initially
        assert middleware.get_user_id("conn_10") is None

        # After authentication
        await middleware.authenticate_connection("conn_10", "valid_user5")
        assert middleware.get_user_id("conn_10") == "user5"

    asyncio.run(run_test())

    print("✓ get_user_id test passed")


def test_has_permission():
    """Test has_permission check"""
    print("Testing has_permission check...")

    from logicgate_cloud.api.websocket_auth import WebSocketAuthConfig, WebSocketAuthMiddleware

    async def run_test():
        config = WebSocketAuthConfig()
        middleware = WebSocketAuthMiddleware(config)

        await middleware.authenticate_connection("conn_11", "valid_user6")

        # Has read permission
        assert middleware.has_permission("conn_11", "read") is True

        # Has write permission
        assert middleware.has_permission("conn_11", "write") is True

        # Does not have admin permission
        assert middleware.has_permission("conn_11", "admin") is False

    asyncio.run(run_test())

    print("✓ has_permission check test passed")


def test_get_active_connections():
    """Test get_active_connections"""
    print("Testing get_active_connections...")

    from logicgate_cloud.api.websocket_auth import WebSocketAuthConfig, WebSocketAuthMiddleware

    async def run_test():
        config = WebSocketAuthConfig()
        middleware = WebSocketAuthMiddleware(config)

        await middleware.authenticate_connection("conn_12", "valid_user7")
        await middleware.authenticate_connection("conn_13", "valid_user8")

        connections = middleware.get_active_connections()
        assert len(connections) == 2
        assert "conn_12" in connections
        assert "conn_13" in connections

    asyncio.run(run_test())

    print("✓ get_active_connections test passed")


def test_get_user_connections():
    """Test get_user_connections"""
    print("Testing get_user_connections...")

    from logicgate_cloud.api.websocket_auth import WebSocketAuthConfig, WebSocketAuthMiddleware

    async def run_test():
        config = WebSocketAuthConfig()
        middleware = WebSocketAuthMiddleware(config)

        await middleware.authenticate_connection("conn_14", "valid_user9")
        await middleware.authenticate_connection("conn_15", "valid_user9")
        await middleware.authenticate_connection("conn_16", "valid_user10")

        user9_connections = middleware.get_user_connections("user9")
        assert len(user9_connections) == 2
        assert "conn_14" in user9_connections
        assert "conn_15" in user9_connections

        user10_connections = middleware.get_user_connections("user10")
        assert len(user10_connections) == 1
        assert "conn_16" in user10_connections

    asyncio.run(run_test())

    print("✓ get_user_connections test passed")


async def test_message_authenticator():
    """Test message authenticator"""
    print("Testing message authenticator...")

    from logicgate_cloud.api.websocket_auth import (
        WebSocketAuthConfig,
        WebSocketAuthMiddleware,
        WebSocketMessageAuthenticator,
    )

    config = WebSocketAuthConfig()
    middleware = WebSocketAuthMiddleware(config)
    msg_auth = WebSocketMessageAuthenticator(middleware)

    # Authenticate connection
    await middleware.authenticate_connection("conn_17", "valid_user11")

    # Test valid message
    message = {"type": "test", "data": {"key": "value"}}
    assert await msg_auth.authenticate_message("conn_17", message) is True

    # Test message format validation
    assert await msg_auth.validate_message_format(message) is True

    # Test invalid message format
    invalid_message = {"type": "test"}  # Missing data
    assert await msg_auth.validate_message_format(invalid_message) is False

    # Test unauthenticated connection
    assert await msg_auth.authenticate_message("conn_18", message) is False

    print("✓ Message authenticator test passed")


def test_message_permission_check():
    """Test message permission check"""
    print("Testing message permission check...")

    from logicgate_cloud.api.websocket_auth import (
        WebSocketAuthConfig,
        WebSocketAuthMiddleware,
        WebSocketMessageAuthenticator,
    )

    async def run_test():
        config = WebSocketAuthConfig()
        middleware = WebSocketAuthMiddleware(config)
        msg_auth = WebSocketMessageAuthenticator(middleware)

        # Authenticate connection
        await middleware.authenticate_connection("conn_19", "valid_user12")

        # Message with required permission that user has
        message = {"type": "test", "data": {}, "required_permission": "read"}
        assert await msg_auth.authenticate_message("conn_19", message) is True

        # Message with required permission that user doesn't have
        message = {"type": "test", "data": {}, "required_permission": "admin"}
        assert await msg_auth.authenticate_message("conn_19", message) is False

    asyncio.run(run_test())

    print("✓ Message permission check test passed")


def run_all_tests():
    """Run all WebSocket authentication tests"""
    print("\n" + "=" * 60)
    print("Running WebSocket Authentication Tests")
    print("=" * 60 + "\n")

    try:
        test_websocket_auth_config()
        test_websocket_auth_middleware_initialization()
        asyncio.run(test_anonymous_connection())
        asyncio.run(test_token_validation())
        asyncio.run(test_authentication_with_valid_token())
        asyncio.run(test_authentication_with_invalid_token())
        asyncio.run(test_connection_limit())
        asyncio.run(test_connection_registration())
        asyncio.run(test_connection_disconnection())
        test_is_authenticated()
        test_get_user_id()
        test_has_permission()
        test_get_active_connections()
        test_get_user_connections()
        asyncio.run(test_message_authenticator())
        test_message_permission_check()

        print("\n" + "=" * 60)
        print("✓ All WebSocket authentication tests passed!")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    run_all_tests()
