"""
White-Label Configuration System for LogicGate Multi-Tenant SaaS

This system manages custom branding for each tenant including:
- Custom colors and themes
- Logo and favicon management
- Custom domains
- Email branding
- CSS customization
"""

import sqlite3
from pathlib import Path
from typing import Any


class WhiteLabelManager:
    """Manages white-label configuration for tenants"""

    def __init__(self, shared_db_path: str, assets_dir: str):
        self.shared_db_path = shared_db_path
        self.assets_dir = Path(assets_dir)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories for branding assets
        (self.assets_dir / "logos").mkdir(exist_ok=True)
        (self.assets_dir / "favicons").mkdir(exist_ok=True)
        (self.assets_dir / "css").mkdir(exist_ok=True)

    def get_tenant_branding(self, tenant_id: str) -> dict[str, Any]:
        """Get branding configuration for a tenant"""
        conn = sqlite3.connect(self.shared_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT company_name, logo_url, primary_color, secondary_color,
                   custom_domain, custom_css, favicon_url, email_from_name,
                   email_from_address, support_phone, support_email
            FROM tenant_branding
            WHERE tenant_id = ?
            """,
            (tenant_id,),
        )

        result = cursor.fetchone()
        conn.close()

        if not result:
            # Return default branding
            return self._get_default_branding()

        return {
            "company_name": result[0] or "LogicGate",
            "logo_url": result[1],
            "primary_color": result[2] or "#00ff66",
            "secondary_color": result[3] or "#1a1a2e",
            "custom_domain": result[4],
            "custom_css": result[5],
            "favicon_url": result[6],
            "email_from_name": result[7] or "LogicGate Support",
            "email_from_address": result[8] or "support@logicgate.io",
            "support_phone": result[9],
            "support_email": result[10] or "support@logicgate.io",
        }

    def _get_default_branding(self) -> dict[str, Any]:
        """Get default branding configuration"""
        return {
            "company_name": "LogicGate",
            "logo_url": None,
            "primary_color": "#00ff66",
            "secondary_color": "#1a1a2e",
            "custom_domain": None,
            "custom_css": None,
            "favicon_url": None,
            "email_from_name": "LogicGate Support",
            "email_from_address": "support@logicgate.io",
            "support_phone": None,
            "support_email": "support@logicgate.io",
        }

    def update_tenant_branding(self, tenant_id: str, branding: dict[str, Any]) -> bool:
        """Update branding configuration for a tenant"""
        try:
            conn = sqlite3.connect(self.shared_db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO tenant_branding
                (tenant_id, company_name, logo_url, primary_color, secondary_color,
                 custom_domain, custom_css, favicon_url, email_from_name,
                 email_from_address, support_phone, support_email)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    branding.get("company_name"),
                    branding.get("logo_url"),
                    branding.get("primary_color"),
                    branding.get("secondary_color"),
                    branding.get("custom_domain"),
                    branding.get("custom_css"),
                    branding.get("favicon_url"),
                    branding.get("email_from_name"),
                    branding.get("email_from_address"),
                    branding.get("support_phone"),
                    branding.get("support_email"),
                ),
            )

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating branding: {e}")
            return False

    def upload_logo(self, tenant_id: str, logo_data: bytes, file_extension: str) -> str | None:
        """Upload and store a logo for a tenant"""
        try:
            # Generate unique filename
            import uuid

            filename = f"{tenant_id}_{uuid.uuid4().hex[:8]}{file_extension}"
            logo_path = self.assets_dir / "logos" / filename

            # Save the file
            with open(logo_path, "wb") as f:
                f.write(logo_data)

            # Generate URL
            logo_url = f"/branding/logos/{filename}"

            # Update database
            branding = self.get_tenant_branding(tenant_id)
            branding["logo_url"] = logo_url
            self.update_tenant_branding(tenant_id, branding)

            return logo_url
        except Exception as e:
            print(f"Error uploading logo: {e}")
            return None

    def upload_favicon(
        self, tenant_id: str, favicon_data: bytes, file_extension: str
    ) -> str | None:
        """Upload and store a favicon for a tenant"""
        try:
            import uuid

            filename = f"{tenant_id}_{uuid.uuid4().hex[:8]}{file_extension}"
            favicon_path = self.assets_dir / "favicons" / filename

            with open(favicon_path, "wb") as f:
                f.write(favicon_data)

            favicon_url = f"/branding/favicons/{filename}"

            branding = self.get_tenant_branding(tenant_id)
            branding["favicon_url"] = favicon_url
            self.update_tenant_branding(tenant_id, branding)

            return favicon_url
        except Exception as e:
            print(f"Error uploading favicon: {e}")
            return None

    def save_custom_css(self, tenant_id: str, css_content: str) -> bool:
        """Save custom CSS for a tenant"""
        try:
            import uuid

            filename = f"{tenant_id}_{uuid.uuid4().hex[:8]}.css"
            css_path = self.assets_dir / "css" / filename

            with open(css_path, "w") as f:
                f.write(css_content)

            css_url = f"/branding/css/{filename}"

            branding = self.get_tenant_branding(tenant_id)
            branding["custom_css"] = css_url
            self.update_tenant_branding(tenant_id, branding)

            return True
        except Exception as e:
            print(f"Error saving custom CSS: {e}")
            return False

    def validate_color(self, color: str) -> bool:
        """Validate hex color format"""
        import re

        return bool(re.match(r"^#[0-9A-Fa-f]{6}$", color))

    def validate_domain(self, domain: str) -> bool:
        """Validate custom domain format"""
        import re

        return bool(re.match(r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$", domain))

    def generate_branding_css(self, branding: dict[str, Any]) -> str:
        """Generate CSS variables from branding configuration"""
        css = f"""
:root {{
    --brand-primary: {branding.get("primary_color", "#00ff66")};
    --brand-secondary: {branding.get("secondary_color", "#1a1a2e")};
    --brand-company: {branding.get("company_name", "LogicGate")};
}}
"""
        return css

    def get_branding_preview(self, tenant_id: str) -> dict[str, Any]:
        """Get a preview of branding configuration for UI"""
        branding = self.get_tenant_branding(tenant_id)

        return {
            "preview_html": self._generate_preview_html(branding),
            "preview_css": self.generate_branding_css(branding),
            "branding": branding,
        }

    def _generate_preview_html(self, branding: dict[str, Any]) -> str:
        """Generate HTML preview of branding"""
        logo_html = (
            f'<img src="{branding.get("logo_url", "")}" alt="Logo">'
            if branding.get("logo_url")
            else f"<h1>{branding.get('company_name', 'LogicGate')}</h1>"
        )

        return f"""
<div style="background-color: {branding.get("secondary_color", "#1a1a2e")}; color: {branding.get("primary_color", "#00ff66")}; padding: 20px;">
    {logo_html}
    <p>Sample dashboard content</p>
    <button style="background-color: {branding.get("primary_color", "#00ff66")}; color: {branding.get("secondary_color", "#1a1a2e")}; border: none; padding: 10px 20px;">
        Sample Button
    </button>
</div>
"""

    def delete_tenant_branding_assets(self, tenant_id: str) -> bool:
        """Delete all branding assets for a tenant"""
        try:
            # Get current branding
            branding = self.get_tenant_branding(tenant_id)

            # Delete logo
            if branding.get("logo_url"):
                logo_path = self.assets_dir / "logos" / branding["logo_url"].split("/")[-1]
                if logo_path.exists():
                    logo_path.unlink()

            # Delete favicon
            if branding.get("favicon_url"):
                favicon_path = self.assets_dir / "favicons" / branding["favicon_url"].split("/")[-1]
                if favicon_path.exists():
                    favicon_path.unlink()

            # Delete custom CSS
            if branding.get("custom_css"):
                css_path = self.assets_dir / "css" / branding["custom_css"].split("/")[-1]
                if css_path.exists():
                    css_path.unlink()

            # Reset branding in database
            self.update_tenant_branding(tenant_id, self._get_default_branding())

            return True
        except Exception as e:
            print(f"Error deleting branding assets: {e}")
            return False


class BrandingTemplateRenderer:
    """Renders templates with tenant branding applied"""

    def __init__(self, white_label_manager: WhiteLabelManager):
        self.wlm = white_label_manager

    def render_template(self, template_content: str, tenant_id: str) -> str:
        """Render a template with tenant branding applied"""
        branding = self.wlm.get_tenant_branding(tenant_id)

        # Replace branding placeholders
        replacements = {
            "{{company_name}}": branding.get("company_name", "LogicGate"),
            "{{primary_color}}": branding.get("primary_color", "#00ff66"),
            "{{secondary_color}}": branding.get("secondary_color", "#1a1a2e"),
            "{{logo_url}}": branding.get("logo_url", ""),
            "{{favicon_url}}": branding.get("favicon_url", ""),
            "{{support_email}}": branding.get("support_email", "support@logicgate.io"),
            "{{support_phone}}": branding.get("support_phone", ""),
            "{{custom_css}}": branding.get("custom_css", ""),
        }

        rendered = template_content
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, value if value else "")

        # Inject branding CSS variables
        branding_css = self.wlm.generate_branding_css(branding)
        rendered = rendered.replace("{{branding_css}}", branding_css)

        return rendered

    def render_email_template(
        self, template_name: str, tenant_id: str, context: dict[str, Any]
    ) -> str:
        """Render an email template with tenant branding"""
        branding = self.wlm.get_tenant_branding(tenant_id)

        # Add branding to context
        context.update(
            {
                "company_name": branding.get("company_name", "LogicGate"),
                "logo_url": branding.get("logo_url", ""),
                "primary_color": branding.get("primary_color", "#00ff66"),
                "support_email": branding.get("support_email", "support@logicgate.io"),
                "support_phone": branding.get("support_phone", ""),
            }
        )

        # Load and render template (simplified - in production use proper template engine)
        template_path = (
            Path(__file__).parent.parent / "templates" / "emails" / f"{template_name}.html"
        )

        if template_path.exists():
            with open(template_path) as f:
                template_content = f.read()

            return self.render_template(template_content, tenant_id)

        return ""
