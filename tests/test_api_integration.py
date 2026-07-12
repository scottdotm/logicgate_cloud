"""
API Endpoint Integration Tests
Tests API endpoints with full infrastructure integration.
"""

import sys
from pathlib import Path

# Add workspace root and shared ground-station modules to sys.path
_BASE_DIR = Path(__file__).parent.parent
_WORKSPACE_ROOT = _BASE_DIR.parent
_MASTER_BASE_DIR = _WORKSPACE_ROOT / "logicgate_master_base"
for _path in (_MASTER_BASE_DIR, _WORKSPACE_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


def test_api_docs_endpoint():
    """Test API documentation endpoint"""
    print("Testing API docs endpoint...")

    from api.docs_server import get_docs_server

    docs_server = get_docs_server()

    # Test spec retrieval
    spec_json = docs_server.get_spec(format="json")
    assert spec_json is not None
    assert "openapi" in spec_json

    # Test HTML generation
    swagger_html = docs_server.get_swagger_html()
    assert swagger_html is not None
    assert "swagger-ui" in swagger_html

    redoc_html = docs_server.get_redoc_html()
    assert redoc_html is not None
    assert "redoc" in redoc_html

    print("✓ API docs endpoint test passed")


def test_rate_limiting_endpoint():
    """Test rate limiting on API endpoints"""
    print("Testing rate limiting endpoint...")

    from core.exceptions import RateLimitExceededException

    from logicgate_cloud.api.rate_limiting import RateLimitConfig, RateLimitMiddleware

    config = RateLimitConfig(requests_per_minute=5, burst_size=5)

    middleware = RateLimitMiddleware(config)

    # Test successful requests
    request = {"user_id": "test_user_1"}
    for _ in range(5):
        result = middleware.process_request(request)
        assert result["rate_limit_remaining"] >= 0

    # Test rate limit exceeded
    try:
        middleware.process_request(request)
        raise AssertionError("Should have raised RateLimitExceededException")
    except RateLimitExceededException as e:
        assert "api" in str(e).lower()

    print("✓ Rate limiting endpoint test passed")


def test_rate_limit_info_endpoint():
    """Test rate limit info endpoint"""
    print("Testing rate limit info endpoint...")

    from logicgate_cloud.api.rate_limiting import RateLimitConfig, RateLimitMiddleware

    config = RateLimitConfig(requests_per_minute=10)
    middleware = RateLimitMiddleware(config)

    # Get rate limit info
    info = middleware.get_rate_limit_info("test_user_2")

    assert info["remaining"] <= 10
    assert info["limit"] == 10
    assert info["algorithm"] in ["token_bucket", "sliding_window", "fixed_window"]

    print("✓ Rate limit info endpoint test passed")


def test_rate_limit_different_users():
    """Test rate limiting with different users"""
    print("Testing rate limiting with different users...")

    from logicgate_cloud.api.rate_limiting import RateLimitConfig, RateLimitMiddleware

    config = RateLimitConfig(requests_per_minute=3)
    middleware = RateLimitMiddleware(config)

    # User 1 uses all requests
    request1 = {"user_id": "user_1"}
    for _ in range(3):
        middleware.process_request(request1)

    # User 1 should be rate limited
    try:
        middleware.process_request(request1)
        raise AssertionError("User 1 should be rate limited")
    except Exception:
        pass  # Expected

    # User 2 should still have full allowance
    request2 = {"user_id": "user_2"}
    for _ in range(3):
        result = middleware.process_request(request2)
        assert result["rate_limit_remaining"] >= 0

    print("✓ Rate limiting different users test passed")


def test_rate_limit_reset():
    """Test rate limit reset functionality"""
    print("Testing rate limit reset...")

    from logicgate_cloud.api.rate_limiting import RateLimitConfig, RateLimitMiddleware

    config = RateLimitConfig(requests_per_minute=2)
    middleware = RateLimitMiddleware(config)

    request = {"user_id": "user_reset_test"}

    # Use up requests
    for _ in range(2):
        middleware.process_request(request)

    # Should be rate limited
    try:
        middleware.process_request(request)
        raise AssertionError("Should be rate limited")
    except Exception:
        pass  # Expected

    # Reset
    identifier = middleware.get_identifier(request)
    middleware.limiter.reset_rate_limit(identifier)

    # Should work again
    result = middleware.process_request(request)
    assert result["rate_limit_remaining"] >= 0

    print("✓ Rate limit reset test passed")


def test_openapi_spec_validation():
    """Test OpenAPI spec is valid"""
    print("Testing OpenAPI spec validation...")

    from api.docs_server import get_docs_server

    docs_server = get_docs_server()
    spec = docs_server.load_openapi_spec()

    # Validate required fields
    assert "openapi" in spec
    assert spec["openapi"] == "3.0.0"
    assert "info" in spec
    assert "title" in spec["info"]
    assert "version" in spec["info"]
    assert "paths" in spec

    # Validate paths
    assert "/api/auth/login" in spec["paths"]
    assert "/api/telemetry" in spec["paths"]
    assert "/api/assets" in spec["paths"]

    # Validate components
    assert "components" in spec
    assert "schemas" in spec["components"]

    print("✓ OpenAPI spec validation test passed")


def test_openapi_schemas():
    """Test OpenAPI schemas are defined"""
    print("Testing OpenAPI schemas...")

    from api.docs_server import get_docs_server

    docs_server = get_docs_server()
    spec = docs_server.load_openapi_spec()

    schemas = spec["components"]["schemas"]

    # Check key schemas exist
    assert "Asset" in schemas
    assert "Command" in schemas
    assert "Alert" in schemas

    # Validate Asset schema
    asset_schema = schemas["Asset"]
    assert "properties" in asset_schema
    assert "asset_id" in asset_schema["properties"]
    assert "asset_name" in asset_schema["properties"]

    print("✓ OpenAPI schemas test passed")


def test_api_security_schemes():
    """Test API security schemes"""
    print("Testing API security schemes...")

    from api.docs_server import get_docs_server

    docs_server = get_docs_server()
    spec = docs_server.load_openapi_spec()

    # Check security schemes
    assert "securitySchemes" in spec["components"]
    security_schemes = spec["components"]["securitySchemes"]

    assert "cookieAuth" in security_schemes
    cookie_auth = security_schemes["cookieAuth"]
    assert cookie_auth["type"] == "apiKey"
    assert cookie_auth["in"] == "cookie"

    print("✓ API security schemes test passed")


def test_rate_limit_decorator():
    """Test rate limiting decorator on functions"""
    print("Testing rate limiting decorator...")

    from core.exceptions import RateLimitExceededException

    from logicgate_cloud.api.rate_limiting import RateLimitAlgorithm, RateLimitConfig, rate_limit

    config = RateLimitConfig(requests_per_minute=3, algorithm=RateLimitAlgorithm.SLIDING_WINDOW)

    @rate_limit(config=config)
    def api_function(user_id):
        return {"success": True, "user_id": user_id}

    # Should allow first 3 calls
    for _ in range(3):
        result = api_function("decorator_user")
        assert result["success"]

    # 4th call should raise exception
    try:
        api_function("decorator_user")
        raise AssertionError("Should have raised RateLimitExceededException")
    except RateLimitExceededException:
        pass  # Expected

    print("✓ Rate limiting decorator test passed")


def test_api_response_headers():
    """Test API response headers for rate limiting"""
    print("Testing API response headers...")

    from logicgate_cloud.api.rate_limiting import RateLimitConfig, RateLimitMiddleware

    config = RateLimitConfig(requests_per_minute=10)
    middleware = RateLimitMiddleware(config)

    request = {"user_id": "headers_user"}
    response = middleware.process_request(request)

    # Check response headers
    assert "rate_limit_remaining" in response
    assert "rate_limit_limit" in response
    assert "rate_limit_reset" in response

    assert response["rate_limit_limit"] == 10
    assert response["rate_limit_remaining"] <= 10

    print("✓ API response headers test passed")


def test_rate_limit_algorithms():
    """Test different rate limiting algorithms"""
    print("Testing rate limiting algorithms...")

    from logicgate_cloud.api.rate_limiting import (
        RateLimitAlgorithm,
        RateLimitConfig,
        RateLimitMiddleware,
    )

    algorithms = [
        RateLimitAlgorithm.TOKEN_BUCKET,
        RateLimitAlgorithm.SLIDING_WINDOW,
        RateLimitAlgorithm.FIXED_WINDOW,
    ]

    for algorithm in algorithms:
        config = RateLimitConfig(requests_per_minute=5, algorithm=algorithm)
        middleware = RateLimitMiddleware(config)

        request = {"user_id": f"algo_test_{algorithm.value}"}

        # Should allow 5 requests
        for _ in range(5):
            result = middleware.process_request(request)
            assert result["rate_limit_remaining"] >= 0

    print("✓ Rate limiting algorithms test passed")


def run_all_tests():
    """Run all API integration tests"""
    print("\n" + "=" * 60)
    print("Running API Integration Tests")
    print("=" * 60 + "\n")

    try:
        test_api_docs_endpoint()
        test_rate_limiting_endpoint()
        test_rate_limit_info_endpoint()
        test_rate_limit_different_users()
        test_rate_limit_reset()
        test_openapi_spec_validation()
        test_openapi_schemas()
        test_api_security_schemes()
        test_rate_limit_decorator()
        test_api_response_headers()
        test_rate_limit_algorithms()

        print("\n" + "=" * 60)
        print("✓ All API integration tests passed!")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    run_all_tests()
