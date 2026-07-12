import os
import sqlite3

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from logicgate_cloud.lake.models import LakeManager, SurveyStatus
from logicgate_cloud.lake.report import ReportGenerator
from logicgate_cloud.lake.schemas import (
    LakeCreateRequest,
    LakeListResponse,
    LakeResponse,
    LakeUpdateRequest,
    SurveyCreateRequest,
    SurveyImageResponse,
    SurveyListResponse,
    SurveyResponse,
    SurveyUpdateRequest,
)
from logicgate_cloud.lake.service import LakeService
from logicgate_cloud.tenant.multi_tenant import TenantManager

router = APIRouter(prefix="/api/v1/portal", tags=["lake-management"])


def _get_shared_db_path() -> str:
    return os.environ.get("SHARED_DB_PATH", "logicgate_shared.db")


def _get_tenant_db_dir() -> str:
    return os.environ.get("TENANT_DB_DIR", "tenant_databases")


def _get_auth_manager():
    from logicgate_cloud.auth.multi_tenant_auth import AuthMiddleware, MultiTenantAuth

    jwt_secret = os.environ.get("JWT_SECRET")
    if not jwt_secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")

    auth = MultiTenantAuth(_get_shared_db_path(), jwt_secret)
    return AuthMiddleware(auth)


async def _get_current_user(request: Request):
    auth = _get_auth_manager()
    user_info = auth.authenticate_request(request)
    if not user_info:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_info


def _get_tenant_manager():
    return TenantManager(_get_shared_db_path(), _get_tenant_db_dir())


def _get_lake_service():
    return LakeService(
        tenant_manager=_get_tenant_manager(),
        upload_dir=os.environ.get("UPLOAD_DIR", "uploads"),
    )


def _lake_to_response(lake) -> LakeResponse:
    return LakeResponse(
        id=lake.id,
        tenant_id=lake.tenant_id,
        name=lake.name,
        body_id=lake.body_id,
        location=lake.location,
        boundary_geojson=lake.boundary_geojson,
        area_sqm=lake.area_sqm,
        notes=lake.notes,
        created_at=lake.created_at.isoformat(),
        updated_at=lake.updated_at.isoformat() if lake.updated_at else None,
    )


def _survey_to_response(survey) -> SurveyResponse:
    return SurveyResponse(
        id=survey.id,
        tenant_id=survey.tenant_id,
        lake_id=survey.lake_id,
        name=survey.name,
        status=survey.status.value,
        scheduled_at=survey.scheduled_at.isoformat() if survey.scheduled_at else None,
        completed_at=survey.completed_at.isoformat() if survey.completed_at else None,
        pilot_name=survey.pilot_name,
        drone_name=survey.drone_name,
        altitude_m=survey.altitude_m,
        image_count=survey.image_count,
        notes=survey.notes,
        created_at=survey.created_at.isoformat(),
        updated_at=survey.updated_at.isoformat() if survey.updated_at else None,
    )


def _image_to_response(image) -> SurveyImageResponse:
    return SurveyImageResponse(
        id=image.id,
        tenant_id=image.tenant_id,
        survey_id=image.survey_id,
        filename=image.filename,
        original_path=image.original_path,
        thumbnail_path=image.thumbnail_path,
        latitude=image.latitude,
        longitude=image.longitude,
        altitude_m=image.altitude_m,
        captured_at=image.captured_at.isoformat() if image.captured_at else None,
        created_at=image.created_at.isoformat(),
    )


@router.post("/lakes", response_model=LakeResponse)
async def create_lake(payload: LakeCreateRequest, request: Request):
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    service = _get_lake_service()
    try:
        lake = service.create_lake(
            tenant_id=tenant_id,
            name=payload.name,
            body_id=payload.body_id,
            location=payload.location,
            boundary_geojson=payload.boundary_geojson,
            area_sqm=payload.area_sqm,
            notes=payload.notes,
        )
        return _lake_to_response(lake)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create lake: {e}") from e


@router.get("/lakes", response_model=LakeListResponse)
async def list_lakes(request: Request):
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    service = _get_lake_service()
    try:
        lakes = service.list_lakes(tenant_id)
        return LakeListResponse(lakes=[_lake_to_response(lake) for lake in lakes])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list lakes: {e}") from e


@router.get("/lakes/{lake_id}", response_model=LakeResponse)
async def get_lake(lake_id: int, request: Request):
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    service = _get_lake_service()
    lake = service.get_lake(tenant_id, lake_id)
    if not lake:
        raise HTTPException(status_code=404, detail="Lake not found")
    return _lake_to_response(lake)


@router.patch("/lakes/{lake_id}", response_model=LakeResponse)
async def update_lake(lake_id: int, payload: LakeUpdateRequest, request: Request):
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    service = _get_lake_service()
    manager = LakeManager(service.tenant_manager.get_tenant_database_path(tenant_id))
    lake = manager.get_lake(tenant_id, lake_id)
    if not lake:
        raise HTTPException(status_code=404, detail="Lake not found")

    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return _lake_to_response(lake)

    conn = sqlite3.connect(manager.tenant_db_path)
    cursor = conn.cursor()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [tenant_id, lake_id]
    cursor.execute(
        f"UPDATE lakes SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ? AND id = ?",
        values,
    )
    conn.commit()
    conn.close()

    return _lake_to_response(manager.get_lake(tenant_id, lake_id))


@router.post("/lakes/{lake_id}/surveys", response_model=SurveyResponse)
async def create_survey(lake_id: int, payload: SurveyCreateRequest, request: Request):
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    if payload.lake_id != lake_id:
        raise HTTPException(status_code=400, detail="Lake ID mismatch")

    service = _get_lake_service()
    try:
        survey = service.create_survey(
            tenant_id=tenant_id,
            lake_id=lake_id,
            name=payload.name,
            scheduled_at=payload.scheduled_at,
            pilot_name=payload.pilot_name,
            drone_name=payload.drone_name,
            altitude_m=payload.altitude_m,
            notes=payload.notes,
        )
        return _survey_to_response(survey)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create survey: {e}") from e


@router.get("/lakes/{lake_id}/surveys", response_model=SurveyListResponse)
async def list_surveys(lake_id: int, request: Request):
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    service = _get_lake_service()
    try:
        surveys = service.list_surveys(tenant_id, lake_id=lake_id)
        return SurveyListResponse(surveys=[_survey_to_response(s) for s in surveys])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list surveys: {e}") from e


@router.get("/surveys/{survey_id}", response_model=SurveyResponse)
async def get_survey(survey_id: int, request: Request):
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    service = _get_lake_service()
    survey = service.get_survey(tenant_id, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    return _survey_to_response(survey)


@router.patch("/surveys/{survey_id}", response_model=SurveyResponse)
async def update_survey(survey_id: int, payload: SurveyUpdateRequest, request: Request):
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    service = _get_lake_service()
    manager = LakeManager(service.tenant_manager.get_tenant_database_path(tenant_id))
    survey = manager.get_survey(tenant_id, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    data = payload.model_dump(exclude_unset=True)
    allowed = {"name", "scheduled_at", "pilot_name", "drone_name", "altitude_m", "notes", "status"}
    updates = {k: v for k, v in data.items() if k in allowed and v is not None}

    if "status" in updates:
        try:
            status = SurveyStatus(updates["status"])
            updates["status"] = status.value
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid status: {updates['status']}") from e

    if not updates:
        return _survey_to_response(survey)

    conn = sqlite3.connect(manager.tenant_db_path)
    cursor = conn.cursor()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [tenant_id, survey_id]
    cursor.execute(
        f"UPDATE surveys SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ? AND id = ?",
        values,
    )
    conn.commit()
    conn.close()

    return _survey_to_response(manager.get_survey(tenant_id, survey_id))


@router.post("/surveys/{survey_id}/images", response_model=SurveyImageResponse)
async def upload_image(request: Request, survey_id: int, file: UploadFile = File(...)):  # noqa: B008
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    service = _get_lake_service()
    try:
        image = service.add_image(tenant_id, survey_id, file)
        return _image_to_response(image)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {e}") from e


@router.get("/surveys/{survey_id}/images", response_model=list[SurveyImageResponse])
async def list_images(survey_id: int, request: Request):
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    service = _get_lake_service()
    try:
        images = service.list_images(tenant_id, survey_id)
        return [_image_to_response(img) for img in images]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list images: {e}") from e


@router.get("/surveys/{survey_id}/images/{image_id}", response_model=SurveyImageResponse)
async def get_image(survey_id: int, image_id: int, request: Request):
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    service = _get_lake_service()
    image = service.get_image(tenant_id, image_id)
    if not image or image.survey_id != survey_id:
        raise HTTPException(status_code=404, detail="Image not found")
    return _image_to_response(image)


@router.post("/surveys/{survey_id}/report")
async def generate_report(survey_id: int, request: Request):
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])

    service = _get_lake_service()
    survey = service.get_survey(tenant_id, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    output_dir = os.path.join(service._tenant_upload_path(tenant_id), f"survey_{survey_id}")
    output_path = os.path.join(output_dir, f"survey_{survey_id}_report.pdf")

    try:
        generator = ReportGenerator(service)
        generator.generate(tenant_id, survey_id, output_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {e}") from e

    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=f"{survey.name}_report.pdf".replace(" ", "_"),
    )
