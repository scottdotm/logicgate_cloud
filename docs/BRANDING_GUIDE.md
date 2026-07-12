# LogicGate Cloud Branding & White-Label Guide

## Overview

This guide covers branding, white-label, and UI customization for the LogicGate Cloud customer portal and the external website project.

## Scope

- Customer self-service portal styling (`portal/`).
- White-label configuration for OEM partners (`branding/white_label_manager.py`).
- Prospect-specific landing pages and dashboards.
- Integration with the external website project for sign-up, pricing, and pilot enrollment.

## Cloud-Specific Branding Configuration

### White-Label Manager

**File:** `logicgate_cloud/branding/white_label_manager.py`

The `WhiteLabelManager` stores tenant-specific branding:

- Primary color
- Logo URL
- Custom CSS
- Prospect-specific dashboard titles

### Customer Portal

**File:** `logicgate_cloud/portal/portal_handler.py`

The portal uses Jinja2 templates. The template directory and base branding are configured at initialization.

## Prospect-Specific Branding

For targeted demos with specific prospects (e.g., Rockwell Automation, Oshkosh Defense):

1. **Identify Prospect Brand Colors** — visit the prospect's website and extract the primary hex color.
2. **Configure White-Label** — use `WhiteLabelManager` to set the tenant's branding.
3. **Custom Landing Page** — the external website project can render a prospect-specific page using the cloud API.
4. **Revert After Demo** — restore default LogicGate branding.

## External Website Integration

The external website project consumes the cloud API to:

- Display pricing tiers (`GET /api/v1/public/plans`).
- Apply prospect-specific branding (`GET /api/v1/portal/branding`).
- Render the "Start Free Pilot" call-to-action (`POST /api/v1/public/tenants`).

## Best Practices

- Maintain WCAG AA contrast ratios.
- Use the same font family across the portal and website.
- Do not rely on color alone for status indicators.
- Provide alt text and ARIA labels for accessibility.

## Maintenance

- **Weekly:** verify portal loads correctly and branding API responds.
- **Monthly:** review prospect-specific themes.
- **Quarterly:** update white-label feature set based on customer feedback.
