"""
Test infrastructure integration with existing modules
Verifies that cache, logging, and exceptions work correctly in integrated modules
"""

import tempfile

from logicgate_cloud.core.exceptions import InvalidCredentialsException, ResourceNotFoundException
from logicgate_cloud.infrastructure.cache import cached, get_cache_manager
from logicgate_cloud.infrastructure.logging import LogLevel, get_logger


def test_cache_integration():
    """Test that cache manager works correctly"""
    print("Testing cache integration...")

    cache = get_cache_manager()

    # Test set and get
    cache.set("test_key", {"data": "test_value"}, ttl=60)
    result = cache.get("test_key")

    assert result is not None
    assert result["data"] == "test_value"

    # Test delete
    cache.delete("test_key")
    result = cache.get("test_key")
    assert result is None

    print("✓ Cache integration test passed")


def test_logging_integration():
    """Test that structured logging works correctly"""
    print("Testing logging integration...")

    logger = get_logger("test_integration", LogLevel.INFO)

    # Test logging with context
    logger.info("Test message", test_param="value", number=42)
    logger.warning("Warning message", severity="high")
    logger.error("Error message", error_code="TEST_001")

    print("✓ Logging integration test passed")


def test_exception_integration():
    """Test that custom exceptions work correctly"""
    print("Testing exception integration...")

    try:
        raise InvalidCredentialsException()
    except InvalidCredentialsException as e:
        assert "Invalid credentials" in str(e)
        assert e.code.value == "AUTH_001"

    try:
        raise ResourceNotFoundException("User", "123")
    except ResourceNotFoundException as e:
        assert "User" in str(e)
        assert "123" in str(e)
        assert e.code.value == "RES_001"

    print("✓ Exception integration test passed")


def test_cached_decorator():
    """Test that @cached decorator works correctly"""
    print("Testing @cached decorator...")

    call_count = 0

    @cached(ttl=60)
    def expensive_function(x, y):
        nonlocal call_count
        call_count += 1
        return x + y

    # First call - should execute function
    result1 = expensive_function(5, 10)
    assert result1 == 15
    assert call_count == 1

    # Second call with same args - should use cache
    result2 = expensive_function(5, 10)
    assert result2 == 15
    assert call_count == 1  # Should not increment

    # Different args - should execute function
    result3 = expensive_function(3, 7)
    assert result3 == 10
    assert call_count == 2

    print("✓ @cached decorator test passed")


def test_auth_system_integration():
    """Test that auth_system uses infrastructure correctly"""
    print("Testing auth_system integration...")

    try:
        from auth_system import AuthenticationManager
    except ImportError:
        print("⊘ Skipping auth_system test (bcrypt not installed)")
        return

    # Create temporary database
    test_db = tempfile.mktemp(suffix=".db")

    try:
        auth_manager = AuthenticationManager(test_db)

        # Verify infrastructure components are initialized
        assert auth_manager.cache_manager is not None
        assert auth_manager.logger is not None

        # Test user creation
        user_id = auth_manager.create_user(
            username="test_user",
            email="test@example.com",
            password="SecurePass123!",
            full_name="Test User",
        )

        assert user_id > 0

        # Test authentication with custom exception
        try:
            auth_manager.authenticate("test_user", "wrong_password")
            raise AssertionError("Should have raised InvalidCredentialsException")
        except InvalidCredentialsException:
            pass  # Expected

        print("✓ Auth system integration test passed")

    finally:
        # Close any database connections before cleanup
        try:
            if "auth_manager" in locals():
                # Force close any connections
                import gc

                gc.collect()
        except Exception:
            pass

        # Try to remove the file with retries
        for _ in range(3):
            try:
                if os.path.exists(test_db):
                    os.remove(test_db)
                break
            except PermissionError:
                import time

                time.sleep(0.1)


def test_asset_manager_integration():
    """Test that asset_manager uses infrastructure correctly"""
    print("Testing asset_manager integration...")

    from assets.asset_manager import AssetManager, AssetType

    # Create temporary database
    test_db = tempfile.mktemp(suffix=".db")

    try:
        asset_manager = AssetManager(test_db)

        # Verify infrastructure components are initialized
        assert asset_manager.cache_manager is not None
        assert asset_manager.logger is not None

        # Test asset registration
        asset_id = asset_manager.register_asset(
            tenant_id="tenant_1",
            asset_name="Test Drone",
            asset_type=AssetType.DRONE,
            serial_number="SN001",
        )

        assert asset_id is not None

        # Test asset retrieval with caching
        asset = asset_manager.get_asset(asset_id)
        assert asset is not None
        assert asset["asset_name"] == "Test Drone"

        # Second retrieval should use cache
        asset2 = asset_manager.get_asset(asset_id)
        assert asset2 is not None
        assert asset2["asset_name"] == "Test Drone"

        print("✓ Asset manager integration test passed")

    finally:
        # Close any database connections before cleanup
        try:
            if "asset_manager" in locals():
                # Force close any connections
                import gc

                gc.collect()
        except Exception:
            pass

        # Try to remove the file with retries
        for _ in range(3):
            try:
                if os.path.exists(test_db):
                    os.remove(test_db)
                break
            except PermissionError:
                import time

                time.sleep(0.1)


def test_telemetry_server_integration():
    """Test that telemetry_server uses infrastructure correctly"""
    print("Testing telemetry_server integration...")

    from websocket.telemetry_server import TelemetryWebSocketServer

    # Create server instance
    server = TelemetryWebSocketServer(host="127.0.0.1", port=8765)

    # Verify infrastructure components are initialized
    assert server.cache_manager is not None
    assert server.logger is not None

    print("✓ Telemetry server integration test passed")


def test_flight_planning_integration():
    """Test that flight_planning uses infrastructure correctly"""
    print("Testing flight_planning integration...")

    try:
        from flight_planning_integration import FlightPlanningManager
    except ImportError:
        print("⊘ Skipping flight_planning_integration test (module not available)")
        return

    # Create temporary database
    test_db = tempfile.mktemp(suffix=".db")

    try:
        flight_manager = FlightPlanningManager(test_db)

        # Verify infrastructure components are initialized
        assert flight_manager.cache_manager is not None
        assert flight_manager.logger is not None

        print("✓ Flight planning integration test passed")

    finally:
        if os.path.exists(test_db):
            os.remove(test_db)


def test_collaborative_mission_integration():
    """Test that collaborative_mission uses infrastructure correctly"""
    print("Testing collaborative_mission integration...")

    try:
        from collaborative_mission import CollaborativeMissionManager
    except ImportError:
        print("⊘ Skipping collaborative_mission test (module not available)")
        return

    # Create temporary database
    test_db = tempfile.mktemp(suffix=".db")

    try:
        mission_manager = CollaborativeMissionManager(test_db)

        # Verify infrastructure components are initialized
        assert mission_manager.cache_manager is not None
        assert mission_manager.logger is not None

        print("✓ Collaborative mission integration test passed")

    finally:
        if os.path.exists(test_db):
            os.remove(test_db)


def test_multi_tenant_integration():
    """Test that multi_tenant uses infrastructure correctly"""
    print("Testing multi_tenant integration...")

    from logicgate_cloud.tenant.multi_tenant import TenantManager

    # Create temporary database
    test_db = tempfile.mktemp(suffix=".db")
    tenant_dir = tempfile.mktemp(suffix="_tenants")

    try:
        tenant_manager = TenantManager(test_db, tenant_dir)

        # Verify infrastructure components are initialized
        assert tenant_manager.cache_manager is not None
        assert tenant_manager.logger is not None

        print("✓ Multi-tenant integration test passed")

    finally:
        if os.path.exists(test_db):
            os.remove(test_db)
        if os.path.exists(tenant_dir):
            import shutil

            shutil.rmtree(tenant_dir, ignore_errors=True)


def test_performance_monitoring_integration():
    """Test that performance_monitoring uses infrastructure correctly"""
    print("Testing performance_monitoring integration...")

    try:
        from performance_monitoring import PerformanceMonitor
    except ImportError:
        print("⊘ Skipping performance_monitoring test (psutil not installed)")
        return

    # Create temporary database
    test_db = tempfile.mktemp(suffix=".db")

    try:
        perf_monitor = PerformanceMonitor(test_db)

        # Verify infrastructure components are initialized
        assert perf_monitor.cache_manager is not None
        assert perf_monitor.logger is not None

        print("✓ Performance monitoring integration test passed")

    finally:
        if os.path.exists(test_db):
            os.remove(test_db)


def run_all_tests():
    """Run all infrastructure integration tests"""
    print("\n" + "=" * 60)
    print("Running Infrastructure Integration Tests")
    print("=" * 60 + "\n")

    try:
        test_cache_integration()
        test_logging_integration()
        test_exception_integration()
        test_cached_decorator()
        test_auth_system_integration()
        test_asset_manager_integration()
        test_telemetry_server_integration()
        test_flight_planning_integration()
        test_collaborative_mission_integration()
        test_multi_tenant_integration()
        test_performance_monitoring_integration()

        print("\n" + "=" * 60)
        print("✓ All infrastructure integration tests passed!")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
