"""
Comprehensive Unit Tests for Infrastructure Modules
Tests all infrastructure components: cache, logging, exceptions, settings
"""

def test_cache_manager_basic():
    """Test basic cache manager operations"""
    print("Testing cache manager basic operations...")

    from logicgate_cloud.infrastructure.cache import get_cache_manager

    cache = get_cache_manager()

    # Test set and get
    cache.set("test_key", "test_value", ttl=60)
    value = cache.get("test_key")
    assert value == "test_value"

    # Test delete
    cache.delete("test_key")
    value = cache.get("test_key")
    assert value is None

    print("✓ Cache manager basic operations test passed")


def test_cache_manager_expiration():
    """Test cache expiration"""
    print("Testing cache expiration...")

    import time

    from logicgate_cloud.infrastructure.cache import get_cache_manager

    cache = get_cache_manager()

    # Check if using Redis (has actual TTL support)
    # CacheManager uses backends list, check if first backend is RedisCache
    has_redis = any(b.__class__.__name__ == "RedisCache" for b in cache.backends)
    if not has_redis:
        print("⊘ Cache expiration test skipped (in-memory cache has no TTL)")
        return

    # Set with short TTL
    cache.set("expire_key", "expire_value", ttl=1)

    # Should be available immediately
    value = cache.get("expire_key")
    assert value == "expire_value"

    # Wait for expiration
    time.sleep(2)

    # Should be expired
    value = cache.get("expire_key")
    assert value is None

    print("✓ Cache expiration test passed")


def test_cache_manager_types():
    """Test cache with different data types"""
    print("Testing cache with different data types...")

    from logicgate_cloud.infrastructure.cache import get_cache_manager

    cache = get_cache_manager()

    # Test string
    cache.set("string_key", "string_value", ttl=60)
    assert cache.get("string_key") == "string_value"

    # Test integer
    cache.set("int_key", 42, ttl=60)
    assert cache.get("int_key") == 42

    # Test list
    cache.set("list_key", [1, 2, 3], ttl=60)
    assert cache.get("list_key") == [1, 2, 3]

    # Test dict
    cache.set("dict_key", {"key": "value"}, ttl=60)
    assert cache.get("dict_key") == {"key": "value"}

    # Cleanup
    cache.delete("string_key")
    cache.delete("int_key")
    cache.delete("list_key")
    cache.delete("dict_key")

    print("✓ Cache types test passed")


def test_logger_basic():
    """Test basic logging operations"""
    print("Testing basic logging operations...")

    from logicgate_cloud.infrastructure.logging import LogLevel, get_logger

    logger = get_logger("test_logger", LogLevel.INFO)

    # Test different log levels
    logger.info("Info message", test_param="value")
    logger.warning("Warning message", severity="high")
    logger.error("Error message", error_code="TEST_001")

    print("✓ Basic logging operations test passed")


def test_logger_context():
    """Test logging with context"""
    print("Testing logging with context...")

    from logicgate_cloud.infrastructure.logging import LogLevel, get_logger

    logger = get_logger("context_logger", LogLevel.INFO)

    # Test with context
    logger.info("Message with context", user_id="user_123", action="test_action", result="success")

    print("✓ Logging context test passed")


def test_logger_levels():
    """Test different log levels"""
    print("Testing different log levels...")

    from logicgate_cloud.infrastructure.logging import LogLevel, get_logger

    # Test with different levels
    debug_logger = get_logger("debug_logger", LogLevel.DEBUG)
    info_logger = get_logger("info_logger", LogLevel.INFO)
    warning_logger = get_logger("warning_logger", LogLevel.WARNING)
    error_logger = get_logger("error_logger", LogLevel.ERROR)

    debug_logger.debug("Debug message")
    info_logger.info("Info message")
    warning_logger.warning("Warning message")
    error_logger.error("Error message")

    print("✓ Log levels test passed")


def test_exceptions_basic():
    """Test basic exception creation"""
    print("Testing basic exception creation...")

    from logicgate_cloud.core.exceptions import (
        AuthenticationException,
        DatabaseException,
        LogicGateException,
        ResourceException,
        ValidationException,
    )

    # Test LogicGateException
    exc = LogicGateException("Test message")
    assert exc.message == "Test message"
    assert exc.severity.value == "medium"

    # Test AuthenticationException
    auth_exc = AuthenticationException("Auth failed")
    assert auth_exc.message == "Auth failed"
    assert auth_exc.severity.value == "high"

    # Test ValidationException
    val_exc = ValidationException("Validation failed")
    assert val_exc.message == "Validation failed"
    assert val_exc.severity.value == "low"

    # Test ResourceException
    res_exc = ResourceException("Resource not found")
    assert res_exc.message == "Resource not found"
    assert res_exc.severity.value == "medium"

    # Test DatabaseException
    db_exc = DatabaseException("Database error")
    assert db_exc.message == "Database error"
    assert db_exc.severity.value == "high"

    print("✓ Basic exception creation test passed")


def test_exceptions_to_dict():
    """Test exception serialization"""
    print("Testing exception serialization...")

    from logicgate_cloud.core.exceptions import ErrorCode, ErrorSeverity, LogicGateException

    exc = LogicGateException(
        "Test message",
        ErrorCode.VAL_INVALID_INPUT,
        ErrorSeverity.HIGH,
        details={"field": "test_field"},
    )

    exc_dict = exc.to_dict()

    assert exc_dict["error"]["message"] == "Test message"
    assert exc_dict["error"]["code"] == ErrorCode.VAL_INVALID_INPUT.value
    assert exc_dict["error"]["severity"] == ErrorSeverity.HIGH.value
    assert exc_dict["error"]["details"]["field"] == "test_field"

    print("✓ Exception serialization test passed")


def test_settings_basic():
    """Test basic settings access"""
    print("Testing basic settings access...")

    from logicgate_cloud.config.settings import get_settings

    settings = get_settings()

    # Test basic settings
    assert settings.environment is not None
    assert settings.app_name == "LogicGate"
    assert settings.app_version is not None

    # Test sub-settings
    assert settings.database is not None
    assert settings.cache is not None
    assert settings.api is not None

    print("✓ Basic settings access test passed")


def test_settings_subsections():
    """Test settings subsections"""
    print("Testing settings subsections...")

    from logicgate_cloud.config.settings import get_settings

    settings = get_settings()

    # Test database settings
    assert hasattr(settings.database, "url")
    assert hasattr(settings.database, "pool_size")

    # Test cache settings
    assert hasattr(settings.cache, "redis_host")
    assert hasattr(settings.cache, "redis_port")

    # Test API settings
    assert hasattr(settings.api, "host")
    assert hasattr(settings.api, "port")

    # Test security settings
    assert hasattr(settings.security, "secret_key")

    print("✓ Settings subsections test passed")


def test_cached_decorator():
    """Test @cached decorator"""
    print("Testing @cached decorator...")

    from logicgate_cloud.infrastructure.cache import cached

    call_count = 0

    @cached(ttl=10)
    def expensive_function(x):
        nonlocal call_count
        call_count += 1
        return x * 2

    # First call - should execute
    result1 = expensive_function(5)
    assert result1 == 10
    assert call_count == 1

    # Second call with same arg - should use cache
    result2 = expensive_function(5)
    assert result2 == 10
    assert call_count == 1  # Should not increment

    # Different arg - should execute
    result3 = expensive_function(10)
    assert result3 == 20
    assert call_count == 2

    print("✓ @cached decorator test passed")


def test_exception_handler():
    """Test exception handler"""
    print("Testing exception handler...")

    from logicgate_cloud.core.exceptions import ErrorCode, ErrorSeverity, ExceptionHandler, LogicGateException

    # Test LogicGateException handling
    exc = LogicGateException("Test error", ErrorCode.VAL_INVALID_INPUT, ErrorSeverity.MEDIUM)
    result = ExceptionHandler.handle_exception(exc)

    assert result["error"]["message"] == "Test error"
    assert result["error"]["code"] == ErrorCode.VAL_INVALID_INPUT.value
    assert result["error"]["severity"] == ErrorSeverity.MEDIUM.value

    # Test standard exception handling
    try:
        raise ValueError("Invalid value")
    except ValueError as e:
        result = ExceptionHandler.handle_exception(e)
        assert result["error"]["code"] == ErrorCode.VAL_INVALID_INPUT.value

    print("✓ Exception handler test passed")


def test_infrastructure_integration():
    """Test integration of all infrastructure components"""
    print("Testing infrastructure integration...")

    from logicgate_cloud.config.settings import get_settings
    from logicgate_cloud.core.exceptions import LogicGateException
    from logicgate_cloud.infrastructure.cache import get_cache_manager
    from logicgate_cloud.infrastructure.logging import LogLevel, get_logger

    # Get all components
    cache = get_cache_manager()
    logger = get_logger("integration_test", LogLevel.INFO)
    settings = get_settings()

    # Test they work together
    cache.set("integration_key", {"data": "test"}, ttl=60)
    data = cache.get("integration_key")
    assert data == {"data": "test"}

    logger.info(
        "Integration test successful",
        app_name=settings.app_name,
        environment=settings.environment.value,
    )

    # Test exception with logging
    try:
        raise LogicGateException("Integration test error")
    except LogicGateException as e:
        logger.error("Exception occurred", error=e.message)

    # Cleanup
    cache.delete("integration_key")

    print("✓ Infrastructure integration test passed")


def run_all_tests():
    """Run all comprehensive infrastructure tests"""
    print("\n" + "=" * 60)
    print("Running Comprehensive Infrastructure Tests")
    print("=" * 60 + "\n")

    try:
        test_cache_manager_basic()
        test_cache_manager_expiration()
        test_cache_manager_types()
        test_logger_basic()
        test_logger_context()
        test_logger_levels()
        test_exceptions_basic()
        test_exceptions_to_dict()
        test_settings_basic()
        test_settings_subsections()
        test_cached_decorator()
        test_exception_handler()
        test_infrastructure_integration()

        print("\n" + "=" * 60)
        print("✓ All comprehensive infrastructure tests passed!")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    run_all_tests()
