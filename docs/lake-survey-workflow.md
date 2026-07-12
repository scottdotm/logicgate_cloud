# Lake Survey Workflow

This document describes the end-to-end workflow for the lake management vertical, from drone data collection to PDF report delivery.

## Overview

The lake management vertical targets lake associations and environmental consultants in Wisconsin Lake Country. The pilot lake is **Okauchee Lake, WI**.

```
Edge Node (drone) → Ground Station (operator) → Cloud SaaS → PDF Report
```

For the MVP, the edge node is not yet integrated live. The operator uploads images from the drone after the flight using the portal or an API key.

## Data model

- **Tenant** — a lake association, environmental consultant, or drone service provider.
- **Lake** — a body of water (e.g., Okauchee Lake) with boundary and metadata.
- **Survey** — a single drone flight over a lake, scheduled for a specific date.
- **SurveyImage** — a geotagged photo captured during the survey.

## Workflow

### 1. Tenant onboarding

The customer signs up via the public website:

```bash
curl -X POST https://api.logicgate.example/api/v1/public/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@okaucheelake.org",
    "password": "SecurePass123!",
    "name": "Jane Admin",
    "company": "Okauchee Lake Association",
    "plan": "freemium"
  }'
```

### 2. Create a lake

```bash
curl -X POST https://api.logicgate.example/api/v1/portal/lakes \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Okauchee Lake",
    "location": "Okauchee, WI",
    "body_id": "WI-1001",
    "notes": "Pilot lake for vegetation monitoring"
  }'
```

### 3. Schedule a survey

```bash
curl -X POST https://api.logicgate.example/api/v1/portal/lakes/$LAKE_ID/surveys \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "lake_id": 1,
    "name": "Spring Vegetation Survey",
    "scheduled_at": "2026-05-15T10:00:00",
    "pilot_name": "Scott",
    "drone_name": "Mavic 3",
    "altitude_m": 80
  }'
```

### 4. Upload images

After the flight, upload the drone images:

```bash
curl -X POST https://api.logicgate.example/api/v1/portal/surveys/$SURVEY_ID/images \
  -H "Authorization: Bearer $JWT" \
  -F "file=@DJI_0001.JPG"
```

The cloud extracts GPS coordinates from EXIF when available.

### 5. Generate a PDF report

```bash
curl -X POST https://api.logicgate.example/api/v1/portal/surveys/$SURVEY_ID/report \
  -H "Authorization: Bearer $JWT" \
  --output "Okauchee_Lake_Spring_Report.pdf"
```

The report contains:
- Cover page with lake and survey metadata.
- Flight details (pilot, drone, altitude, image count).
- Image gallery with thumbnails and GPS coordinates.
- Notes and observations.

## Ground-station integration

The ground station can automate the upload using an API key:

1. Create an API key in the portal.
2. Use the API key as `Authorization: Bearer $API_KEY` for survey and image endpoints.
3. The ground station creates a survey after flight planning and uploads images after the flight.

## Future enhancements

- Automated vegetation classification (invasive species detection).
- Year-over-year shoreline erosion comparison.
- Integration with herbicide treatment maps.
- Live telemetry streaming from the edge node to the cloud.
- S3-backed image storage for production scaling.
