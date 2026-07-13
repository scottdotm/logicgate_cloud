"""
Tenant Identification Middleware for LogicGate Multi-Tenant SaaS

This middleware handles tenant identification from various sources:
- Subdomain (tenant.logicgate.io)
- Custom domain (tracking.customer.com)
- API key header
- JWT token claims
"""

import sqlite3
from functools import wraps
from http.server import BaseHTTPRequestHandler
from typing import Any


class TenantContext:
    """Stores tenant information for the current request"""

    def __init__(
        self,
        tenant_id: str,
        tenant_name: str,
        tenant_slug: str,
        subscription_tier: str,
        branding: dict[str, Any],
        subscription_renews_at: str = None,
    ):
        self.tenant_id = tenant_id
        self.tenant_name = tenant_name
        self.tenant_slug = tenant_slug
        self.subscription_tier = subscription_tier
        self.branding = branding
        self.subscription_renews_at = subscription_renews_at
        self.user_id = None
        self.user_role = None


class TenantMiddleware:
    """Middleware for identifying and validating tenants"""

    def __init__(self, shared_db_path: str):
        self.shared_db_path = shared_db_path
        self._tenant_cache = {}  # Simple in-memory cache

    def get_tenant_from_subdomain(self, host: str) -> str | None:
        """Extract tenant slug from subdomain"""
        # Handle localhost for development
        if host in ["localhost", "127.0.0.1"]:
            return "default"

        # Extract subdomain from host
        # tenant.logicgate.io -> tenant
        # tracking.customer.com -> tracking.customer.com (custom domain)

        parts = host.split(".")

        # Check for custom domain (not logicgate.io)
        if len(parts) > 2 and parts[-2:] != ["logicgate", "io"]:
            # This is a custom domain, look it up
            return self.get_tenant_by_custom_domain(host)

        # Extract subdomain from logicgate.io
        if len(parts) >= 3 and parts[-2:] == ["logicgate", "io"]:
            subdomain = parts[0]
            if subdomain not in ["www", "api"]:
                return subdomain

        return "default"

    def get_tenant_by_custom_domain(self, domain: str) -> str | None:
        """Look up tenant by custom domain"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT t.tenant_slug FROM tenants t JOIN tenant_branding tb ON t.tenant_id = tb.tenant_id WHERE tb.custom_domain = ?",
            (domain,),
        )

        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None

    def get_tenant_by_api_key(self, api_key: str) -> dict[str, Any] | None:
        """Look up tenant by API key"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT t.tenant_id, t.tenant_name, t.tenant_slug, t.plan
            FROM tenants t
            JOIN api_keys ak ON t.tenant_id = ak.tenant_id
            WHERE ak.key_hash = ? AND ak.status = 'active'
            """,
            (self._hash_api_key(api_key),),
        )

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                "tenant_id": result[0],
                "tenant_name": result[1],
                "tenant_slug": result[2],
                "subscription_tier": result[3],
            }
        return None

    def get_tenant_info(self, tenant_slug: str) -> TenantContext | None:
        """Get complete tenant information including branding"""
        # Check cache first
        if tenant_slug in self._tenant_cache:
            return self._tenant_cache[tenant_slug]

        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT t.tenant_id, t.tenant_name, t.tenant_slug, t.plan, t.subscription_ends_at,
                   tb.company_name, tb.logo_url, tb.primary_color, tb.secondary_color,
                   tb.custom_domain, tb.custom_css, tb.favicon_url
            FROM tenants t
            LEFT JOIN tenant_branding tb ON t.tenant_id = tb.tenant_id
            WHERE t.tenant_slug = ? AND t.status = 'active'
            """,
            (tenant_slug,),
        )

        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        branding = {
            "company_name": result[5],
            "logo_url": result[6],
            "primary_color": result[7],
            "secondary_color": result[8],
            "custom_domain": result[9],
            "custom_css": result[10],
            "favicon_url": result[11],
        }

        context = TenantContext(
            tenant_id=result[0],
            tenant_name=result[1],
            tenant_slug=result[2],
            subscription_tier=result[3],
            branding=branding,
            subscription_renews_at=result[4],
        )

        # Cache the result
        self._tenant_cache[tenant_slug] = context

        return context

    def _hash_api_key(self, api_key: str) -> str:
        """Hash API key for storage (SHA-256)"""
        import hashlib

        return hashlib.sha256(api_key.encode()).hexdigest()

    def validate_tenant_access(
        self, tenant_context: TenantContext, required_tier: str = None
    ) -> bool:
        """Validate tenant has access to required features based on subscription tier"""
        tier_hierarchy = {"free": 0, "starter": 1, "professional": 2, "enterprise": 3}

        if required_tier:
            current_level = tier_hierarchy.get(tenant_context.subscription_tier, 0)
            required_level = tier_hierarchy.get(required_tier, 0)
            return current_level >= required_level

        return True

    def identify_tenant(self, handler: BaseHTTPRequestHandler) -> TenantContext | None:
        """Identify tenant from request handler"""
        host = handler.headers.get("Host", "localhost")
        tenant_slug = self.get_tenant_from_subdomain(host)

        # For development on localhost, use the 'horizon' tenant
        if tenant_slug == "default" or "localhost" in host or "127.0.0.1" in host:
            tenant_slug = "horizon"

        if not tenant_slug:
            return None

        return self.get_tenant_info(tenant_slug)


def tenant_required(middleware: TenantMiddleware):
    """Decorator to require valid tenant context"""

    def decorator(func):
        @wraps(func)
        def wrapper(request_handler, *args, **kwargs):
            # Extract tenant from request
            host = request_handler.headers.get("Host", "localhost")
            tenant_slug = middleware.get_tenant_from_subdomain(host)

            if not tenant_slug:
                request_handler.send_error(400, "Invalid tenant")
                return

            tenant_context = middleware.get_tenant_info(tenant_slug)

            if not tenant_context:
                request_handler.send_error(404, "Tenant not found")
                return

            # Attach tenant context to request handler
            request_handler.tenant_context = tenant_context

            return func(request_handler, *args, **kwargs)

        return wrapper

    return decorator


def apply_tenant_middleware(handler_class, middleware: TenantMiddleware):
    """Apply tenant middleware to a request handler class"""
    original_do_GET = handler_class.do_GET  # noqa: N806
    original_do_POST = handler_class.do_POST  # noqa: N806

    def do_GET_with_tenant(self):  # noqa: N802
        host = self.headers.get("Host", "localhost")
        tenant_slug = middleware.get_tenant_from_subdomain(host)

        if tenant_slug:
            self.tenant_context = middleware.get_tenant_info(tenant_slug)

        return original_do_GET(self)

    def do_POST_with_tenant(self):  # noqa: N802
        host = self.headers.get("Host", "localhost")
        tenant_slug = middleware.get_tenant_from_subdomain(host)

        if tenant_slug:
            self.tenant_context = middleware.get_tenant_info(tenant_slug)

        return original_do_POST(self)

    handler_class.do_GET = do_GET_with_tenant
    handler_class.do_POST = do_POST_with_tenant

    return handler_class
