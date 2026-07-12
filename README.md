# LogicGate Cloud

Multi-tenant SaaS backend for the LogicGate industrial asset platform.

## First Vertical: Lake Management

The initial go-to-market focus is **lake management and environmental monitoring** for lake associations and environmental consultants in Wisconsin Lake Country (pilot: Okauchee Lake).

A tenant can:
- Register a lake (`/api/v1/portal/lakes`).
- Schedule and track shoreline surveys (`/api/v1/portal/lakes/{lake_id}/surveys`).
- Upload drone imagery (`/api/v1/portal/surveys/{survey_id}/images`).
- Download a PDF survey report (`/api/v1/portal/surveys/{survey_id}/report`).

## Scope

This directory contains the cloud-side components that power the customer-facing website, self-service portal, and business operations:

- **Tenant management** — multi-tenant registration, isolation, and resource quotas.
- **Authentication** — customer accounts, sessions, API keys, and multi-tenant RBAC.
- **Billing** — subscriptions, plans, Stripe integration, and invoicing.
- **Lake management** — lakes, surveys, image uploads, and PDF reports.
- **Notifications** — welcome emails, onboarding, and trial expiration alerts.
- **Analytics** — usage analytics, tenant-level metrics, and reporting.
- **Portal** — customer self-service dashboard and API surface for the external website.
- **Branding** — white-label configuration for OEM partners.

## What Does NOT Belong Here

- Ground station / mesh receiver code (belongs in `logicgate_master_base`).
- Edge node / field gateway code (belongs in `logicgate_edge_node`).

## API Surface for the External Website

The website project calls this backend via these endpoints:

### Public
- `GET /api/v1/public/health` — System health.
- `GET /api/v1/public/plans` — Pricing tiers.
- `GET /api/v1/public/inquiries/landing` — Lake survey landing page.
- `GET /api/v1/public/partners/pitch` — Partner pitch page.
- `GET /api/v1/public/demo-report` — Download a sample lake survey report.
- `POST /api/v1/public/inquiries` — Submit a pilot inquiry.
- `POST /api/v1/public/tenants` — Pilot sign-up.
- `POST /api/v1/public/checkout` — Stripe checkout session.

### Portal
- `POST /api/v1/portal/auth/login` — Customer portal login.
- `GET /api/v1/portal/subscription` — Current subscription and usage.
- `POST /api/v1/portal/lakes` — Create a lake.
- `GET /api/v1/portal/lakes` — List lakes.
- `GET /api/v1/portal/lakes/{lake_id}` — Get a lake.
- `POST /api/v1/portal/lakes/{lake_id}/surveys` — Create a survey.
- `GET /api/v1/portal/surveys/{survey_id}` — Get a survey.
- `PATCH /api/v1/portal/surveys/{survey_id}` — Update a survey.
- `POST /api/v1/portal/surveys/{survey_id}/images` — Upload survey images.
- `POST /api/v1/portal/surveys/{survey_id}/report` — Generate and download a PDF report.

## Runtime

`logicgate_cloud` is designed to run as a Python web service (Linux server) behind a reverse proxy. It communicates with ground station deployments through well-defined APIs, not through direct file access.

## Database

SQLite is used for demos and early pilots. PostgreSQL is the planned production target once the first paid customers are onboarded.

## Ground-Station Upload Contract

The ground station (or a drone operator) can create a survey and upload media using an API key:

```bash
export API_KEY="lg_..."

# Create a survey
curl -X POST https://api.logicgate.example/api/v1/portal/lakes/$LAKE_ID/surveys \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"lake_id": 1, "name": "Okauchee Lake - May 2026"}'

# Upload an image
curl -X POST https://api.logicgate.example/api/v1/portal/surveys/$SURVEY_ID/images \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@DJI_0001.JPG"
```
