"""
Test API rate limiting middleware
"""

import time


def test_rate_limiter_initialization():
    """Test that rate limiter initializes correctly"""
    print("Testing rate limiter initialization...")

    from logicgate_cloud.api.rate_limiting import RateLimitAlgorithm, RateLimitConfig, RateLimiter

    config = RateLimitConfig(
        requests_per_minute=10, burst_size=5, algorithm=RateLimitAlgorithm.SLIDING_WINDOW
    )

    limiter = RateLimiter(config)

    assert limiter is not None
    assert limiter.config.requests_per_minute == 10
    assert limiter.config.burst_size == 5
    assert limiter.config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW

    print("✓ Rate limiter initialization test passed")


def test_sliding_window_rate_limiting():
    """Test sliding window rate limiting"""
    print("Testing sliding window rate limiting...")

    from logicgate_cloud.api.rate_limiting import RateLimitAlgorithm, RateLimitConfig, RateLimiter

    config = RateLimitConfig(
        requests_per_minute=5, burst_size=5, algorithm=RateLimitAlgorithm.SLIDING_WINDOW
    )

    limiter = RateLimiter(config)
    identifier = "test_user_1"

    # Should allow first 5 requests
    for i in range(5):
        assert limiter.check_rate_limit(identifier), f"Request {i + 1} should be allowed"

    # 6th request should be denied
    assert not limiter.check_rate_limit(identifier), "6th request should be denied"

    print("✓ Sliding window rate limiting test passed")


def test_token_bucket_rate_limiting():
    """Test token bucket rate limiting"""
    print("Testing token bucket rate limiting...")

    from logicgate_cloud.api.rate_limiting import RateLimitAlgorithm, RateLimitConfig, RateLimiter

    config = RateLimitConfig(
        requests_per_minute=60,  # 1 per second
        burst_size=3,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
    )

    limiter = RateLimiter(config)
    identifier = "test_user_2"

    # Should allow burst of 3 requests
    for i in range(3):
        assert limiter.check_rate_limit(identifier), f"Burst request {i + 1} should be allowed"

    # 4th request should be denied (bucket empty)
    assert not limiter.check_rate_limit(identifier), "4th request should be denied (bucket empty)"

    # Wait for token refill
    time.sleep(1.1)

    # Should allow request after refill
    assert limiter.check_rate_limit(identifier), "Request after refill should be allowed"

    print("✓ Token bucket rate limiting test passed")


def test_fixed_window_rate_limiting():
    """Test fixed window rate limiting"""
    print("Testing fixed window rate limiting...")

    from logicgate_cloud.api.rate_limiting import RateLimitAlgorithm, RateLimitConfig, RateLimiter

    config = RateLimitConfig(
        requests_per_minute=5, burst_size=5, algorithm=RateLimitAlgorithm.FIXED_WINDOW
    )

    limiter = RateLimiter(config)
    identifier = "test_user_3"

    # Should allow first 5 requests
    for i in range(5):
        assert limiter.check_rate_limit(identifier), f"Request {i + 1} should be allowed"

    # 6th request should be denied
    assert not limiter.check_rate_limit(identifier), "6th request should be denied"

    print("✓ Fixed window rate limiting test passed")


def test_remaining_requests():
    """Test getting remaining requests"""
    print("Testing remaining requests...")

    from logicgate_cloud.api.rate_limiting import RateLimitAlgorithm, RateLimitConfig, RateLimiter

    config = RateLimitConfig(
        requests_per_minute=10, burst_size=5, algorithm=RateLimitAlgorithm.SLIDING_WINDOW
    )

    limiter = RateLimiter(config)
    identifier = "test_user_4"

    # Initially should have full allowance
    remaining = limiter.get_remaining_requests(identifier)
    assert remaining == 10, f"Should have 10 remaining, got {remaining}"

    # After 3 requests
    for _ in range(3):
        limiter.check_rate_limit(identifier)

    remaining = limiter.get_remaining_requests(identifier)
    assert remaining == 7, f"Should have 7 remaining, got {remaining}"

    print("✓ Remaining requests test passed")


def test_rate_limit_reset():
    """Test resetting rate limit"""
    print("Testing rate limit reset...")

    from logicgate_cloud.api.rate_limiting import RateLimitAlgorithm, RateLimitConfig, RateLimiter

    config = RateLimitConfig(
        requests_per_minute=5, burst_size=5, algorithm=RateLimitAlgorithm.SLIDING_WINDOW
    )

    limiter = RateLimiter(config)
    identifier = "test_user_5"

    # Use up all requests
    for _ in range(5):
        limiter.check_rate_limit(identifier)

    # Should be denied
    assert not limiter.check_rate_limit(identifier), "Should be denied after using all requests"

    # Reset
    limiter.reset_rate_limit(identifier)

    # Should be allowed again
    assert limiter.check_rate_limit(identifier), "Should be allowed after reset"

    print("✓ Rate limit reset test passed")


def test_rate_limit_middleware():
    """Test rate limit middleware"""
    print("Testing rate limit middleware...")

    from logicgate_cloud.api.rate_limiting import RateLimitConfig, RateLimitMiddleware

    config = RateLimitConfig(requests_per_minute=5, burst_size=5)

    middleware = RateLimitMiddleware(config)

    assert middleware is not None
    assert middleware.config.requests_per_minute == 5

    # Test with request
    request = {"user_id": "user_123"}

    # Process 5 requests
    for _ in range(5):
        result = middleware.process_request(request)
        assert result["rate_limit_remaining"] >= 0

    # 6th request should raise exception
    try:
        middleware.process_request(request)
        raise AssertionError("Should have raised RateLimitExceededException")
    except Exception as e:
        assert "Rate limit" in str(e)

    print("✓ Rate limit middleware test passed")


def test_rate_limit_decorator():
    """Test rate limiting decorator"""
    print("Testing rate limiting decorator...")

    from logicgate_cloud.core.exceptions import RateLimitExceededException

    from logicgate_cloud.api.rate_limiting import RateLimitAlgorithm, RateLimitConfig, rate_limit

    config = RateLimitConfig(
        requests_per_minute=3, burst_size=3, algorithm=RateLimitAlgorithm.SLIDING_WINDOW
    )

    @rate_limit(config=config)
    def test_function(user_id):
        return f"Success for {user_id}"

    # Should allow first 3 calls
    for _ in range(3):
        result = test_function("user_decorator_test")
        assert "Success" in result

    # 4th call should raise exception
    try:
        test_function("user_decorator_test")
        raise AssertionError("Should have raised RateLimitExceededException")
    except RateLimitExceededException:
        pass  # Expected

    print("✓ Rate limiting decorator test passed")


def test_multiple_identifiers():
    """Test rate limiting with multiple identifiers"""
    print("Testing multiple identifiers...")

    from logicgate_cloud.api.rate_limiting import RateLimitAlgorithm, RateLimitConfig, RateLimiter

    config = RateLimitConfig(
        requests_per_minute=3, burst_size=3, algorithm=RateLimitAlgorithm.SLIDING_WINDOW
    )

    limiter = RateLimiter(config)

    # User 1 should be limited
    for _ in range(3):
        assert limiter.check_rate_limit("user_1")
    assert not limiter.check_rate_limit("user_1")

    # User 2 should still have full allowance
    for _ in range(3):
        assert limiter.check_rate_limit("user_2")

    print("✓ Multiple identifiers test passed")


def run_all_tests():
    """Run all rate limiting tests"""
    print("\n" + "=" * 60)
    print("Running Rate Limiting Tests")
    print("=" * 60 + "\n")

    try:
        test_rate_limiter_initialization()
        test_sliding_window_rate_limiting()
        test_token_bucket_rate_limiting()
        test_fixed_window_rate_limiting()
        test_remaining_requests()
        test_rate_limit_reset()
        test_rate_limit_middleware()
        test_rate_limit_decorator()
        test_multiple_identifiers()

        print("\n" + "=" * 60)
        print("✓ All rate limiting tests passed!")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    run_all_tests()
