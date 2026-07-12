"""Public and portal API routers for the security toolkit."""

import os
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from logicgate_cloud.security_toolkit.assessment_service import AssessmentService
from logicgate_cloud.security_toolkit.common.exceptions import (
    AssessmentNotFoundError,
    InvalidDomainError,
    ScanError,
    TenantLimitError,
)
from logicgate_cloud.security_toolkit.common.schemas import (
    AnswerSubmitRequest,
    AssessmentCreateRequest,
    AssessmentResponse,
    FindingResponse,
    FreeScanRequest,
    FreeScanSummary,
    ReportResponse,
)
from logicgate_cloud.security_toolkit.report import ReportGenerator

public_router = APIRouter(prefix="/api/v1/public/security", tags=["security"])
portal_router = APIRouter(prefix="/api/v1/portal/security", tags=["security-portal"])


def _get_db_path() -> str:
    return os.environ.get("SHARED_DB_PATH", "logicgate_shared.db")


def _get_assessment_service() -> AssessmentService:
    return AssessmentService(_get_db_path())


def _get_auth_manager():
    from logicgate_cloud.auth.multi_tenant_auth import AuthMiddleware, MultiTenantAuth

    jwt_secret = os.environ.get("JWT_SECRET")
    if not jwt_secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
    return AuthMiddleware(MultiTenantAuth(_get_db_path(), jwt_secret))


def _get_tenant_plan(tenant_id: int) -> str:
    """Resolve the tenant's plan slug from the database."""
    from logicgate_cloud.tenant.multi_tenant import TenantManager

    manager = TenantManager(_get_db_path())
    tenant = manager.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    plan = tenant.plan.value if hasattr(tenant.plan, "value") else tenant.plan
    return plan if isinstance(plan, str) else str(plan)


async def _get_current_user(request: Request):
    auth = _get_auth_manager()
    user_info = auth.authenticate_request(request)
    if not user_info:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_info


def _assessment_to_response(assessment) -> AssessmentResponse:
    return AssessmentResponse(
        id=assessment.id,
        tenant_id=assessment.tenant_id,
        domain=assessment.domain,
        status=assessment.status,
        assessment_type=assessment.assessment_type,
        nist_score=assessment.nist_score,
        created_at=assessment.created_at,
        completed_at=assessment.completed_at,
    )


def _finding_to_response(finding) -> FindingResponse:
    return FindingResponse(
        id=finding.id,
        assessment_id=finding.assessment_id,
        nist_function=finding.nist_function,
        nist_category=finding.nist_category,
        severity=finding.severity,
        title=finding.title,
        description=finding.description,
        evidence=finding.evidence,
        recommendation=finding.recommendation,
        effort=finding.effort,
    )


@public_router.post("/scan", response_model=FreeScanSummary)
async def free_scan(request: FreeScanRequest):
    """Run a free, non-intrusive external scan for a domain."""
    service = _get_assessment_service()
    try:
        summary = await service.run_free_scan(request.domain)
        return FreeScanSummary(**summary)
    except InvalidDomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScanError as exc:
        raise HTTPException(status_code=500, detail=f"Scan failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected scan error: {exc}") from exc


@portal_router.post("/assessments", response_model=AssessmentResponse)
async def create_assessment(payload: AssessmentCreateRequest, request: Request):
    """Create a new assessment for the authenticated tenant."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    plan = _get_tenant_plan(tenant_id)

    service = _get_assessment_service()
    try:
        assessment = await service.create_assessment(
            tenant_id=tenant_id,
            plan=plan,
            domain=payload.domain,
            assessment_type=payload.assessment_type.value,
        )
        return _assessment_to_response(assessment)
    except TenantLimitError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create assessment: {exc}") from exc


@portal_router.post("/assessments/{assessment_id}/scan", response_model=AssessmentResponse)
async def run_assessment_scan(assessment_id: int, request: Request):
    """Run the external scan portion of an existing assessment."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    service = _get_assessment_service()
    try:
        assessment = await service.run_external_scan(tenant_id, assessment_id)
        return _assessment_to_response(assessment)
    except AssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidDomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scan failed: {exc}") from exc


@portal_router.post("/assessments/{assessment_id}/questionnaire", response_model=AssessmentResponse)
async def submit_questionnaire(assessment_id: int, payload: AnswerSubmitRequest, request: Request):
    """Submit questionnaire answers and finalize a paid assessment."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    answers = {a.question_key: a.answer for a in payload.answers}
    service = _get_assessment_service()
    try:
        assessment = await service.submit_questionnaire(tenant_id, assessment_id, answers)
        return _assessment_to_response(assessment)
    except AssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to submit questionnaire: {exc}"
        ) from exc


@portal_router.get("/assessments", response_model=list[AssessmentResponse])
async def list_assessments(request: Request):
    """List assessments for the authenticated tenant."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    service = _get_assessment_service()
    try:
        assessments = await service.list_assessments(tenant_id)
        return [_assessment_to_response(a) for a in assessments]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list assessments: {exc}") from exc


@portal_router.get("/assessments/{assessment_id}", response_model=dict[str, Any])
async def get_assessment(assessment_id: int, request: Request):
    """Get a single assessment with its findings."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    service = _get_assessment_service()
    try:
        assessment = await service.get_assessment(tenant_id, assessment_id)
        return {
            "assessment": _assessment_to_response(assessment),
            "findings": [_finding_to_response(f) for f in assessment.findings],
        }
    except AssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load assessment: {exc}") from exc


@portal_router.delete("/assessments/{assessment_id}", status_code=204)
async def delete_assessment(assessment_id: int, request: Request):
    """Delete a tenant assessment."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    service = _get_assessment_service()
    try:
        await service.delete_assessment(tenant_id, assessment_id)
        return None
    except AssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete assessment: {exc}") from exc


@portal_router.post("/assessments/{assessment_id}/report", response_model=ReportResponse)
async def generate_report(assessment_id: int, request: Request):
    """Generate a detailed HTML report for a completed assessment."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    generator = ReportGenerator(_get_db_path())
    try:
        result = await generator.generate_html_report(tenant_id, assessment_id)
        return ReportResponse(
            assessment_id=result["assessment_id"],
            download_url=f"/api/v1/portal/security/reports/{result['filename']}",
            generated_at=datetime.now(UTC),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {exc}") from exc


@portal_router.post("/assessments/{assessment_id}/report/pdf", response_model=ReportResponse)
async def generate_pdf_report(assessment_id: int, request: Request):
    """Generate a PDF report for a completed assessment."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    generator = ReportGenerator(_get_db_path())
    try:
        result = await generator.generate_pdf_report(tenant_id, assessment_id)
        return ReportResponse(
            assessment_id=result["assessment_id"],
            download_url=f"/api/v1/portal/security/reports/{result['filename']}",
            generated_at=datetime.now(UTC),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate PDF report: {exc}"
        ) from exc


@portal_router.get("/reports/{filename}")
async def download_report(filename: str, request: Request):
    """Download a generated HTML or PDF report."""
    await _get_current_user(request)

    report_dir = os.environ.get("REPORT_DIR", "reports")
    path = os.path.join(report_dir, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Report not found")

    media_type = "application/pdf" if filename.endswith(".pdf") else "text/html"
    return FileResponse(path, media_type=media_type, filename=filename)


@portal_router.post("/cleanup", response_model=dict[str, int])
async def cleanup_expired_assessments(request: Request):
    """Trigger cleanup of expired assessments (tenant-scoped cleanup planned for future)."""
    await _get_current_user(request)
    service = _get_assessment_service()
    try:
        count = await service.cleanup_expired()
        return {"deleted": count}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {exc}") from exc
