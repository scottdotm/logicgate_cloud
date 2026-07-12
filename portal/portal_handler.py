"""
Customer Self-Service Portal for LogicGate Multi-Tenant SaaS

This portal provides:
- Account management
- Subscription management
- Usage analytics
- Branding configuration
- API key management
- Invoice history
- Support requests
"""

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from typing import Any

from jinja2 import Environment, FileSystemLoader


class PortalHandler:
    """Handles customer self-service portal requests"""

    def __init__(self, shared_db_path: str, templates_dir: str):
        self.shared_db_path = shared_db_path
        self.templates_dir = templates_dir
        self.jinja_env = Environment(loader=FileSystemLoader(templates_dir))

        # Import other managers (using absolute imports)
        try:
            from alerts.alert_system import AlertSystem
            from analytics.historical_analysis import HistoricalAnalysis
            from assets.asset_manager import AssetManager
            from command.command_system import CommandSystem
            from export.data_export import DataExport
            from geofence.geofence_system import GeofenceSystem
            from reporting.report_generator import ReportGenerator

            from analytics.usage_analytics import UsageAnalytics
            from billing.stripe_manager import StripeBillingManager
            from branding.white_label_manager import WhiteLabelManager
        except ImportError:
            # Fallback for testing without full module structure
            StripeBillingManager = None  # noqa: N806,F841
            UsageAnalytics = None  # noqa: N806,F841
            WhiteLabelManager = None  # noqa: N806,F841
            AssetManager = None  # noqa: N806,F841
            CommandSystem = None  # noqa: N806,F841
            AlertSystem = None  # noqa: N806,F841
            ReportGenerator = None  # noqa: N806,F841
            DataExport = None  # noqa: N806,F841
            GeofenceSystem = None  # noqa: N806,F841
            HistoricalAnalysis = None  # noqa: N806,F841

        # Initialize managers (would need proper config in production)
        self.stripe_manager = None  # Would need API key
        if UsageAnalytics:
            self.analytics = UsageAnalytics(shared_db_path)
        else:
            self.analytics = None
        if WhiteLabelManager:
            self.branding_manager = WhiteLabelManager(shared_db_path, "assets/branding")
        else:
            self.branding_manager = None
        if AssetManager:
            self.asset_manager = AssetManager(shared_db_path)
        else:
            self.asset_manager = None
        if CommandSystem:
            self.command_system = CommandSystem(shared_db_path)
        else:
            self.command_system = None
        if AlertSystem:
            self.alert_system = AlertSystem(shared_db_path)
        else:
            self.alert_system = None
        if ReportGenerator:
            self.report_generator = ReportGenerator(shared_db_path)
        else:
            self.report_generator = None
        if DataExport:
            self.data_export = DataExport(shared_db_path)
        else:
            self.data_export = None
        if GeofenceSystem:
            self.geofence_system = GeofenceSystem(shared_db_path)
        else:
            self.geofence_system = None
        if HistoricalAnalysis:
            self.historical_analysis = HistoricalAnalysis(shared_db_path)
        else:
            self.historical_analysis = None

    def handle_portal_request(self, handler: BaseHTTPRequestHandler, path: str):
        """Route portal requests to appropriate handlers"""
        # Extract tenant context from handler
        tenant_context = getattr(handler, "tenant_context", None)

        if not tenant_context:
            handler.send_response(302)
            handler.send_header("Location", "/login")
            handler.end_headers()
            return

        # Route based on path
        if path == "/portal" or path == "/portal/":
            self.render_dashboard(handler, tenant_context)
        elif path == "/portal/account":
            self.render_account_settings(handler, tenant_context)
        elif path == "/portal/subscription":
            self.render_subscription(handler, tenant_context)
        elif path == "/portal/usage":
            self.render_usage_analytics(handler, tenant_context)
        elif path == "/portal/branding":
            self.render_branding_settings(handler, tenant_context)
        elif path == "/portal/api-keys":
            self.render_api_keys(handler, tenant_context)
        elif path == "/portal/invoices":
            self.render_invoices(handler, tenant_context)
        elif path == "/portal/support":
            self.render_support(handler, tenant_context)
        elif path == "/portal/assets":
            self.render_assets(handler, tenant_context)
        elif path == "/portal/commands":
            self.render_commands(handler, tenant_context)
        elif path == "/portal/alerts":
            self.render_alerts(handler, tenant_context)
        elif path == "/portal/reports":
            self.render_reports(handler, tenant_context)
        elif path == "/portal/export":
            self.render_export(handler, tenant_context)
        elif path == "/portal/geofences":
            self.render_geofences(handler, tenant_context)
        elif path == "/portal/analysis":
            self.render_analysis(handler, tenant_context)
        else:
            handler.send_response(404)
            handler.end_headers()

    def render_dashboard(self, handler: BaseHTTPRequestHandler, tenant_context):
        """Render main portal dashboard"""
        branding = self.branding_manager.get_tenant_branding(tenant_context.tenant_id)
        usage_today = self.analytics.get_tenant_usage_today(tenant_context.tenant_id)

        # Get user info from handler
        user_info = getattr(handler, "user_info", {})

        # Get subscription limits based on tier
        limits = self._get_tier_limits(tenant_context.subscription_tier)

        # Get active assets count
        active_assets = self._get_active_assets_count(tenant_context.tenant_id)

        template = self.jinja_env.get_template("portal/dashboard.html")
        html = template.render(
            company_name=branding.get("company_name", "LogicGate"),
            primary_color=branding.get("primary_color", "#00ff66"),
            secondary_color=branding.get("secondary_color", "#1a1a2e"),
            logo_url=branding.get("logo_url"),
            favicon_url=branding.get("favicon_url"),
            custom_css=branding.get("custom_css"),
            user_name=user_info.get("full_name", "User"),
            user_email=user_info.get("email", ""),
            active_page="dashboard",
            tenant_name=tenant_context.tenant_name,
            subscription_tier=tenant_context.subscription_tier,
            usage_today=usage_today,
            active_assets=active_assets,
            api_limit=limits["api_rate_limit"],
            storage_limit=limits["storage_gb"],
            asset_limit=limits["max_assets"],
            subscription_renews_at=tenant_context.subscription_renews_at,
            current_date=datetime.now().strftime("%B %d, %Y"),
            current_location="Milwaukee, WI",
            current_year=datetime.now().year,
        )

        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.end_headers()
        handler.wfile.write(html.encode())

    def render_account_settings(self, handler: BaseHTTPRequestHandler, tenant_context):
        """Render account settings page"""
        branding = self.branding_manager.get_tenant_branding(tenant_context.tenant_id)

        # Get user info from handler
        user_info = getattr(handler, "user_info", {})

        # Get tenant details
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT tenant_name, contact_email, contact_phone, billing_address, created_at
            FROM tenants
            WHERE tenant_id = ?
            """,
            (tenant_context.tenant_id,),
        )

        result = cursor.fetchone()
        conn.close()

        tenant_details = {
            "name": result[0] if result else "",
            "email": result[1] if result else "",
            "phone": result[2] if result else "",
            "address": result[3] if result else "",
            "created_at": result[4] if result else "",
        }

        template = self.jinja_env.get_template("portal/account.html")
        html = template.render(
            company_name=branding.get("company_name", "LogicGate"),
            primary_color=branding.get("primary_color", "#00ff66"),
            secondary_color=branding.get("secondary_color", "#1a1a2e"),
            logo_url=branding.get("logo_url"),
            favicon_url=branding.get("favicon_url"),
            custom_css=branding.get("custom_css"),
            user_name=user_info.get("full_name", "User"),
            user_email=user_info.get("email", ""),
            active_page="account",
            tenant_details=tenant_details,
            current_location="Milwaukee, WI",
            current_year=datetime.now().year,
        )

        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.end_headers()
        handler.wfile.write(html.encode())

    def render_subscription(self, handler: BaseHTTPRequestHandler, tenant_context):
        """Render subscription management page"""
        branding = self.branding_manager.get_tenant_branding(tenant_context.tenant_id)

        # Get user info from handler
        user_info = getattr(handler, "user_info", {})

        # Get subscription details
        subscription_status = None
        if self.stripe_manager:
            subscription_status = self.stripe_manager.get_subscription_status(
                tenant_context.tenant_id
            )
        else:
            # Mock subscription status for testing
            subscription_status = {
                "status": "active",
                "current_period_end": datetime.now() + timedelta(days=30),
                "cancel_at_period_end": False,
            }

        # Get billing summary
        billing_summary = self.analytics.calculate_billing(
            tenant_context.tenant_id, tenant_context.subscription_tier
        )

        template = self.jinja_env.get_template("portal/subscription.html")
        html = template.render(
            company_name=branding.get("company_name", "LogicGate"),
            primary_color=branding.get("primary_color", "#00ff66"),
            secondary_color=branding.get("secondary_color", "#1a1a2e"),
            logo_url=branding.get("logo_url"),
            favicon_url=branding.get("favicon_url"),
            custom_css=branding.get("custom_css"),
            user_name=user_info.get("full_name", "User"),
            user_email=user_info.get("email", ""),
            active_page="subscription",
            subscription_tier=tenant_context.subscription_tier,
            subscription_status=subscription_status,
            billing_summary=billing_summary,
            subscription_renews_at=tenant_context.subscription_renews_at,
            current_year=datetime.now().year,
        )

        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.end_headers()
        handler.wfile.write(html.encode())

    def render_usage_analytics(self, handler: BaseHTTPRequestHandler, tenant_context):
        """Render usage analytics page"""
        branding = self.branding_manager.get_tenant_branding(tenant_context.tenant_id)

        # Get user info from handler
        user_info = getattr(handler, "user_info", {})

        # Get subscription limits
        limits = self._get_tier_limits(tenant_context.subscription_tier)

        # Get active assets count
        active_assets = self._get_active_assets_count(tenant_context.tenant_id)

        usage_today = self.analytics.get_tenant_usage_today(tenant_context.tenant_id)
        usage_month = self.analytics.get_usage_summary(tenant_context.tenant_id, "month")
        usage_trends = {
            "api_requests": self.analytics.get_usage_trends(
                tenant_context.tenant_id, "api_requests"
            ),
            "storage": self.analytics.get_usage_trends(tenant_context.tenant_id, "storage_gb"),
        }

        # Check for usage alerts
        usage_alerts = self._check_usage_alerts(tenant_context.tenant_id, usage_today, limits)

        template = self.jinja_env.get_template("portal/usage.html")
        html = template.render(
            company_name=branding.get("company_name", "LogicGate"),
            primary_color=branding.get("primary_color", "#00ff66"),
            secondary_color=branding.get("secondary_color", "#1a1a2e"),
            logo_url=branding.get("logo_url"),
            favicon_url=branding.get("favicon_url"),
            custom_css=branding.get("custom_css"),
            user_name=user_info.get("full_name", "User"),
            user_email=user_info.get("email", ""),
            active_page="usage",
            usage_today=usage_today,
            usage_month=usage_month,
            usage_trends=usage_trends,
            usage_alerts=usage_alerts,
            api_limit=limits["api_rate_limit"],
            storage_limit=limits["storage_gb"],
            asset_limit=limits["max_assets"],
            active_assets=active_assets,
            current_date=datetime.now().strftime("%B %d, %Y"),
            current_year=datetime.now().year,
        )

        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.end_headers()
        handler.wfile.write(html.encode())

    def render_branding_settings(self, handler: BaseHTTPRequestHandler, tenant_context):
        """Render branding settings page"""
        branding = self.branding_manager.get_tenant_branding(tenant_context.tenant_id)
        preview = self.branding_manager.get_branding_preview(tenant_context.tenant_id)

        # Get user info from handler
        user_info = getattr(handler, "user_info", {})

        template = self.jinja_env.get_template("portal/branding.html")
        html = template.render(
            company_name=branding.get("company_name", "LogicGate"),
            primary_color=branding.get("primary_color", "#00ff66"),
            secondary_color=branding.get("secondary_color", "#1a1a2e"),
            logo_url=branding.get("logo_url"),
            favicon_url=branding.get("favicon_url"),
            custom_css=branding.get("custom_css"),
            user_name=user_info.get("full_name", "User"),
            user_email=user_info.get("email", ""),
            active_page="branding",
            branding=branding,
            preview=preview,
            current_year=datetime.now().year,
        )

        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.end_headers()
        handler.wfile.write(html.encode())

    def render_api_keys(self, handler: BaseHTTPRequestHandler, tenant_context):
        """Render API keys management page"""
        branding = self.branding_manager.get_tenant_branding(tenant_context.tenant_id)

        # Get user info from handler
        user_info = getattr(handler, "user_info", {})

        # Get API keys for tenant
        api_keys = self._get_tenant_api_keys(tenant_context.tenant_id)

        template = self.jinja_env.get_template("portal/api_keys.html")
        html = template.render(
            company_name=branding.get("company_name", "LogicGate"),
            primary_color=branding.get("primary_color", "#00ff66"),
            secondary_color=branding.get("secondary_color", "#1a1a2e"),
            logo_url=branding.get("logo_url"),
            favicon_url=branding.get("favicon_url"),
            custom_css=branding.get("custom_css"),
            user_name=user_info.get("full_name", "User"),
            user_email=user_info.get("email", ""),
            active_page="api-keys",
            api_keys=api_keys,
            current_year=datetime.now().year,
        )

        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.end_headers()
        handler.wfile.write(html.encode())

    def _get_tenant_api_keys(self, tenant_id: str) -> list:
        """Get API keys for a tenant"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        # Create api_keys table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id VARCHAR(36) NOT NULL,
                key_name VARCHAR(255) NOT NULL,
                key_hash VARCHAR(64) NOT NULL,
                key_prefix VARCHAR(10) NOT NULL,
                status VARCHAR(50) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                INDEX idx_tenant_keys (tenant_id)
            )
        """)

        cursor.execute(
            """
            SELECT key_name, key_prefix, status, created_at, last_used_at
            FROM api_keys
            WHERE tenant_id = ?
            ORDER BY created_at DESC
            """,
            (tenant_id,),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                {
                    "name": row[0],
                    "prefix": row[1],
                    "status": row[2],
                    "created_at": row[3],
                    "last_used_at": row[4],
                }
            )

        conn.close()
        return results

    def create_api_key(self, tenant_id: str, key_name: str) -> str | None:
        """Create a new API key for a tenant"""
        try:
            # Generate API key
            api_key = f"lg_{uuid.uuid4().hex}"
            key_prefix = api_key[:10]
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            conn = sqlite3.connect(self.shared_db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO api_keys (tenant_id, key_name, key_hash, key_prefix)
                VALUES (?, ?, ?, ?)
                """,
                (tenant_id, key_name, key_hash, key_prefix),
            )

            conn.commit()
            conn.close()

            return api_key
        except Exception as e:
            print(f"Error creating API key: {e}")
            return None

    def revoke_api_key(self, tenant_id: str, key_prefix: str) -> bool:
        """Revoke an API key"""
        try:
            conn = sqlite3.connect(self.shared_db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE api_keys
                SET status = 'revoked'
                WHERE tenant_id = ? AND key_prefix = ?
                """,
                (tenant_id, key_prefix),
            )

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error revoking API key: {e}")
            return False

    def render_invoices(self, handler: BaseHTTPRequestHandler, tenant_context):
        """Render invoice history page"""
        branding = self.branding_manager.get_tenant_branding(tenant_context.tenant_id)

        # Get user info from handler
        user_info = getattr(handler, "user_info", {})

        invoices = []
        if self.stripe_manager:
            invoices = self.stripe_manager.get_invoice_history(tenant_context.tenant_id)
        else:
            # Mock invoices for testing
            invoices = [
                {
                    "id": "INV-001",
                    "created": datetime.now() - timedelta(days=30),
                    "amount": 199.00,
                    "status": "paid",
                },
                {
                    "id": "INV-002",
                    "created": datetime.now() - timedelta(days=60),
                    "amount": 199.00,
                    "status": "paid",
                },
            ]

        # Get billing summary
        billing_summary = self.analytics.calculate_billing(
            tenant_context.tenant_id, tenant_context.subscription_tier
        )

        template = self.jinja_env.get_template("portal/invoices.html")
        html = template.render(
            company_name=branding.get("company_name", "LogicGate"),
            primary_color=branding.get("primary_color", "#00ff66"),
            secondary_color=branding.get("secondary_color", "#1a1a2e"),
            logo_url=branding.get("logo_url"),
            favicon_url=branding.get("favicon_url"),
            custom_css=branding.get("custom_css"),
            user_name=user_info.get("full_name", "User"),
            user_email=user_info.get("email", ""),
            active_page="invoices",
            invoices=invoices,
            billing_summary=billing_summary,
            subscription_renews_at=tenant_context.subscription_renews_at,
            subscription_tier=tenant_context.subscription_tier,
            current_year=datetime.now().year,
        )

        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.end_headers()
        handler.wfile.write(html.encode())

    def render_support(self, handler: BaseHTTPRequestHandler, tenant_context):
        """Render support page"""
        branding = self.branding_manager.get_tenant_branding(tenant_context.tenant_id)

        # Get user info from handler
        user_info = getattr(handler, "user_info", {})

        template = self.jinja_env.get_template("portal/support.html")
        html = template.render(
            company_name=branding.get("company_name", "LogicGate"),
            primary_color=branding.get("primary_color", "#00ff66"),
            secondary_color=branding.get("secondary_color", "#1a1a2e"),
            logo_url=branding.get("logo_url"),
            favicon_url=branding.get("favicon_url"),
            custom_css=branding.get("custom_css"),
            user_name=user_info.get("full_name", "User"),
            user_email=user_info.get("email", ""),
            active_page="support",
            support_email=branding.get("support_email", "support@logicgate.io"),
            support_phone=branding.get("support_phone"),
            current_date=datetime.now().strftime("%B %d, %Y"),
            current_year=datetime.now().year,
        )

        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.end_headers()
        handler.wfile.write(html.encode())

    def handle_portal_update(
        self, handler: BaseHTTPRequestHandler, path: str, post_data: dict[str, Any]
    ):
        """Handle POST requests for portal updates"""
        tenant_context = getattr(handler, "tenant_context", None)

        if not tenant_context:
            handler.send_response(401)
            handler.end_headers()
            return

        if path == "/portal/account/update":
            self.update_account_settings(handler, tenant_context, post_data)
        elif path == "/portal/branding/update":
            self.update_branding_settings(handler, tenant_context, post_data)
        elif path == "/portal/api-keys/create":
            self.handle_create_api_key(handler, tenant_context, post_data)
        elif path == "/portal/api-keys/revoke":
            self.handle_revoke_api_key(handler, tenant_context, post_data)
        else:
            handler.send_response(404)
            handler.end_headers()

    def update_account_settings(
        self, handler: BaseHTTPRequestHandler, tenant_context, post_data: dict[str, Any]
    ):
        """Update account settings"""
        try:
            conn = sqlite3.connect(self.shared_db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE tenants
                SET contact_email = ?, contact_phone = ?, billing_address = ?
                WHERE tenant_id = ?
                """,
                (
                    post_data.get("email"),
                    post_data.get("phone"),
                    post_data.get("address"),
                    tenant_context.tenant_id,
                ),
            )

            conn.commit()
            conn.close()

            # Return success
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"success": True}).encode())
        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())

    def update_branding_settings(
        self, handler: BaseHTTPRequestHandler, tenant_context, post_data: dict[str, Any]
    ):
        """Update branding settings"""
        try:
            branding_data = {
                "company_name": post_data.get("company_name"),
                "primary_color": post_data.get("primary_color"),
                "secondary_color": post_data.get("secondary_color"),
                "email_from_name": post_data.get("email_from_name"),
                "email_from_address": post_data.get("email_from_address"),
                "support_phone": post_data.get("support_phone"),
                "support_email": post_data.get("support_email"),
            }

            success = self.branding_manager.update_tenant_branding(
                tenant_context.tenant_id, branding_data
            )

            if success:
                handler.send_response(200)
                handler.send_header("Content-Type", "application/json")
                handler.end_headers()
                handler.wfile.write(json.dumps({"success": True}).encode())
            else:
                handler.send_response(500)
                handler.send_header("Content-Type", "application/json")
                handler.end_headers()
                handler.wfile.write(json.dumps({"success": False}).encode())
        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())

    def handle_create_api_key(
        self, handler: BaseHTTPRequestHandler, tenant_context, post_data: dict[str, Any]
    ):
        """Handle API key creation"""
        api_key = self.create_api_key(tenant_context.tenant_id, post_data.get("key_name"))

        if api_key:
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"success": True, "api_key": api_key}).encode())
        else:
            handler.send_response(500)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"success": False}).encode())

    def handle_revoke_api_key(
        self, handler: BaseHTTPRequestHandler, tenant_context, post_data: dict[str, Any]
    ):
        """Handle API key revocation"""
        success = self.revoke_api_key(tenant_context.tenant_id, post_data.get("key_prefix"))

        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"success": success}).encode())

    def _get_tier_limits(self, tier: str) -> dict[str, Any]:
        """Get limits for a subscription tier"""
        tier_limits = {
            "starter": {"api_rate_limit": 100, "storage_gb": 10, "max_assets": 10},
            "professional": {"api_rate_limit": 500, "storage_gb": 100, "max_assets": 100},
            "enterprise": {"api_rate_limit": 5000, "storage_gb": 1000, "max_assets": -1},
        }
        return tier_limits.get(tier, tier_limits["starter"])

    def _get_active_assets_count(self, tenant_id: str) -> int:
        """Get count of active assets for a tenant"""
        try:
            # This would query the tenant database in production
            # For now, return a mock value
            return 3
        except Exception as e:
            print(f"Error getting active assets count: {e}")
            return 0

    def _check_usage_alerts(
        self, tenant_id: str, usage_today: dict[str, Any], limits: dict[str, Any]
    ) -> list:
        """Check for usage alerts based on current usage and limits"""
        alerts = []

        # Check API usage
        api_usage = usage_today.get("api_requests", 0)
        api_limit = limits.get("api_rate_limit", 100)
        if api_usage >= api_limit * 0.9:
            alerts.append(
                {
                    "type": "api_limit",
                    "severity": "warning",
                    "message": "Approaching API rate limit",
                    "current": api_usage,
                    "limit": api_limit,
                }
            )

        # Check storage usage
        storage_usage = usage_today.get("storage_gb", 0)
        storage_limit = limits.get("storage_gb", 10)
        if storage_usage >= storage_limit * 0.9:
            alerts.append(
                {
                    "type": "storage_limit",
                    "severity": "warning",
                    "message": "Approaching storage limit",
                    "current": storage_usage,
                    "limit": storage_limit,
                }
            )

        return alerts

    def render_assets(self, handler: BaseHTTPRequestHandler, tenant_context):
        """Render assets management page"""
        if self.asset_manager:
            assets = self.asset_manager.get_tenant_assets(tenant_context.tenant_id)
            groups = self.asset_manager.get_tenant_groups(tenant_context.tenant_id)
            stats = self.asset_manager.get_asset_statistics(tenant_context.tenant_id)
        else:
            assets = []
            groups = []
            stats = {}

        template = self.jinja_env.get_template("portal/assets.html")
        html = template.render(
            tenant=tenant_context,
            branding=self.branding_manager.get_tenant_branding(tenant_context.tenant_id)
            if self.branding_manager
            else {},
            assets=assets,
            groups=groups,
            stats=stats,
        )

        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.end_headers()
        handler.wfile.write(html.encode())

    def render_commands(self, handler: BaseHTTPRequestHandler, tenant_context):
        """Render commands management page"""
        if self.command_system:
            commands = self.command_system.get_tenant_commands(tenant_context.tenant_id, limit=50)
            pending = self.command_system.get_pending_commands()
        else:
            commands = []
            pending = []

        template = self.jinja_env.get_template("portal/commands.html")
        html = template.render(
            tenant=tenant_context,
            branding=self.branding_manager.get_tenant_branding(tenant_context.tenant_id)
            if self.branding_manager
            else {},
            commands=commands,
            pending_commands=pending,
        )

        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.end_headers()
        handler.wfile.write(html.encode())

    def render_alerts(self, handler: BaseHTTPRequestHandler, tenant_context):
        """Render alerts management page"""
        if self.alert_system:
            alerts = self.alert_system.get_alert_history(tenant_context.tenant_id, limit=100)
            rules = self.alert_system.get_tenant_alert_rules(tenant_context.tenant_id)
            suppressions = self.alert_system.get_active_suppressions(tenant_context.tenant_id)
        else:
            alerts = []
            rules = []
            suppressions = []

        template = self.jinja_env.get_template("portal/alerts.html")
        html = template.render(
            tenant=tenant_context,
            branding=self.branding_manager.get_tenant_branding(tenant_context.tenant_id)
            if self.branding_manager
            else {},
            alerts=alerts,
            rules=rules,
            suppressions=suppressions,
        )

        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.end_headers()
        handler.wfile.write(html.encode())

    def render_reports(self, handler: BaseHTTPRequestHandler, tenant_context):
        """Render reports page"""
        if self.report_generator:
            reports = self.report_generator.get_tenant_reports(tenant_context.tenant_id, limit=50)
        else:
            reports = []

        template = self.jinja_env.get_template("portal/reports.html")
        html = template.render(
            tenant=tenant_context,
            branding=self.branding_manager.get_tenant_branding(tenant_context.tenant_id)
            if self.branding_manager
            else {},
            reports=reports,
        )

        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.end_headers()
        handler.wfile.write(html.encode())

    def render_export(self, handler: BaseHTTPRequestHandler, tenant_context):
        """Render data export page"""
        if self.data_export:
            exports = self.data_export.get_export_history(tenant_context.tenant_id, limit=50)
        else:
            exports = []

        template = self.jinja_env.get_template("portal/export.html")
        html = template.render(
            tenant=tenant_context,
            branding=self.branding_manager.get_tenant_branding(tenant_context.tenant_id)
            if self.branding_manager
            else {},
            exports=exports,
        )

        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.end_headers()
        handler.wfile.write(html.encode())

    def render_geofences(self, handler: BaseHTTPRequestHandler, tenant_context):
        """Render geofences management page"""
        if self.geofence_system:
            geofences = self.geofence_system.get_tenant_geofences(tenant_context.tenant_id)
            breaches = self.geofence_system.get_breach_history(tenant_context.tenant_id, limit=50)
        else:
            geofences = []
            breaches = []

        template = self.jinja_env.get_template("portal/geofences.html")
        html = template.render(
            tenant=tenant_context,
            branding=self.branding_manager.get_tenant_branding(tenant_context.tenant_id)
            if self.branding_manager
            else {},
            geofences=geofences,
            breaches=breaches,
        )

        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.end_headers()
        handler.wfile.write(html.encode())

    def render_analysis(self, handler: BaseHTTPRequestHandler, tenant_context):
        """Render historical analysis page"""
        template = self.jinja_env.get_template("portal/analysis.html")
        html = template.render(
            tenant=tenant_context,
            branding=self.branding_manager.get_tenant_branding(tenant_context.tenant_id)
            if self.branding_manager
            else {},
            historical_analysis=self.historical_analysis is not None,
        )

        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.end_headers()
        handler.wfile.write(html.encode())
