"""Portal API routers for security toolkit utilities: policies, docs, tasks, assets."""

import json

from fastapi import APIRouter, HTTPException, Request

from logicgate_cloud.security_toolkit.api.security_toolkit import (
    _get_current_user,
    _get_db_path,
    _get_tenant_plan,
)
from logicgate_cloud.security_toolkit.assets.models import Asset
from logicgate_cloud.security_toolkit.assets.schemas import (
    AssetCreateRequest,
    AssetResponse,
    AssetUpdateRequest,
)
from logicgate_cloud.security_toolkit.assets.service import AssetService
from logicgate_cloud.security_toolkit.docs.models import Document
from logicgate_cloud.security_toolkit.docs.schemas import (
    DocumentCreateRequest,
    DocumentResponse,
    DocumentUpdateRequest,
)
from logicgate_cloud.security_toolkit.docs.service import DocumentService
from logicgate_cloud.security_toolkit.policies.schemas import (
    PolicyCreateRequest,
    PolicyResponse,
    PolicyTemplateDetailResponse,
    PolicyTemplateResponse,
    PolicyUpdateRequest,
)
from logicgate_cloud.security_toolkit.policies.service import PolicyService
from logicgate_cloud.security_toolkit.tasks.models import Task
from logicgate_cloud.security_toolkit.tasks.schemas import (
    BulkCreateFromFindingsRequest,
    TaskCreateRequest,
    TaskResponse,
    TaskUpdateRequest,
)
from logicgate_cloud.security_toolkit.tasks.service import TaskService

utilities_router = APIRouter(prefix="/api/v1/portal/security", tags=["security-utilities"])


# ---------- Helpers ----------


def _get_policy_service() -> PolicyService:
    return PolicyService(_get_db_path())


def _get_document_service() -> DocumentService:
    return DocumentService(_get_db_path())


def _get_task_service() -> TaskService:
    return TaskService(_get_db_path())


def _get_asset_service() -> AssetService:
    return AssetService(_get_db_path())


def _policy_to_response(policy) -> PolicyResponse:
    return PolicyResponse(
        id=policy.id,
        tenant_id=policy.tenant_id,
        template_key=policy.template_key,
        title=policy.title,
        content=policy.content,
        nist_function=policy.nist_function,
        nist_category=policy.nist_category,
        status=policy.status,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


def _template_to_response(template) -> PolicyTemplateResponse:
    return PolicyTemplateResponse(
        key=template.key,
        title=template.title,
        nist_function=template.nist_function,
        nist_category=template.nist_category,
    )


def _template_to_detail_response(template) -> PolicyTemplateDetailResponse:
    return PolicyTemplateDetailResponse(
        key=template.key,
        title=template.title,
        nist_function=template.nist_function,
        nist_category=template.nist_category,
        content=template.content,
    )


def _doc_to_response(doc: Document) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        tenant_id=doc.tenant_id,
        parent_id=doc.parent_id,
        title=doc.title,
        doc_type=doc.doc_type,
        content=doc.content,
        tags=json.loads(doc.tags) if doc.tags else None,
        status=doc.status,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _task_to_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        tenant_id=task.tenant_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        severity=task.severity,
        assignee_user_id=task.assignee_user_id,
        due_date=task.due_date,
        source_finding_id=task.source_finding_id,
        source_assessment_id=task.source_assessment_id,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _asset_to_response(asset: Asset) -> AssetResponse:
    return AssetResponse(
        id=asset.id,
        tenant_id=asset.tenant_id,
        name=asset.name,
        asset_type=asset.asset_type,
        owner=asset.owner,
        location=asset.location,
        status=asset.status,
        purchase_date=asset.purchase_date,
        renewal_date=asset.renewal_date,
        notes=asset.notes,
        tags=json.loads(asset.tags) if asset.tags else None,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


# ---------- Policy Templates ----------


@utilities_router.get("/policy-templates", response_model=list[PolicyTemplateResponse])
async def list_policy_templates(request: Request):
    """List all built-in policy templates."""
    await _get_current_user(request)
    service = _get_policy_service()
    templates = await service.list_templates()
    return [_template_to_response(t) for t in templates]


@utilities_router.get("/policy-templates/{key}", response_model=PolicyTemplateDetailResponse)
async def get_policy_template(key: str, request: Request):
    """Get a single built-in policy template."""
    await _get_current_user(request)
    service = _get_policy_service()
    template = await service.get_template(key)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return _template_to_detail_response(template)


# ---------- Policies ----------


@utilities_router.get("/policies", response_model=list[PolicyResponse])
async def list_policies(request: Request):
    """List tenant policies."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    service = _get_policy_service()
    policies = await service.list_policies(tenant_id)
    return [_policy_to_response(p) for p in policies]


@utilities_router.post("/policies", response_model=PolicyResponse)
async def create_policy(payload: PolicyCreateRequest, request: Request):
    """Create a policy, optionally from a template."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    plan = _get_tenant_plan(tenant_id)

    service = _get_policy_service()
    try:
        policy = await service.create_policy(
            tenant_id, plan, payload.model_dump(exclude_unset=True)
        )
        return _policy_to_response(policy)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@utilities_router.get("/policies/{policy_id}", response_model=PolicyResponse)
async def get_policy(policy_id: int, request: Request):
    """Get a tenant policy."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    service = _get_policy_service()
    policy = await service.get_policy(tenant_id, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return _policy_to_response(policy)


@utilities_router.patch("/policies/{policy_id}", response_model=PolicyResponse)
async def update_policy(policy_id: int, payload: PolicyUpdateRequest, request: Request):
    """Update a tenant policy."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    service = _get_policy_service()
    policy = await service.update_policy(
        tenant_id, policy_id, payload.model_dump(exclude_unset=True)
    )
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return _policy_to_response(policy)


@utilities_router.delete("/policies/{policy_id}", status_code=204)
async def delete_policy(policy_id: int, request: Request):
    """Delete a tenant policy."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    service = _get_policy_service()
    deleted = await service.delete_policy(tenant_id, policy_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Policy not found")
    return None


# ---------- Documents ----------


@utilities_router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(request: Request):
    """List tenant documents."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    service = _get_document_service()
    docs = await service.list_documents(tenant_id)
    return [_doc_to_response(d) for d in docs]


@utilities_router.post("/documents", response_model=DocumentResponse)
async def create_document(payload: DocumentCreateRequest, request: Request):
    """Create a document/runbook."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    plan = _get_tenant_plan(tenant_id)

    service = _get_document_service()
    try:
        doc = await service.create_document(tenant_id, plan, payload.model_dump(exclude_unset=True))
        return _doc_to_response(doc)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@utilities_router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: int, request: Request):
    """Get a tenant document."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    service = _get_document_service()
    doc = await service.get_document(tenant_id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_to_response(doc)


@utilities_router.patch("/documents/{document_id}", response_model=DocumentResponse)
async def update_document(document_id: int, payload: DocumentUpdateRequest, request: Request):
    """Update a tenant document."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    service = _get_document_service()
    doc = await service.update_document(
        tenant_id, document_id, payload.model_dump(exclude_unset=True)
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_to_response(doc)


@utilities_router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: int, request: Request):
    """Delete a tenant document."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    service = _get_document_service()
    deleted = await service.delete_document(tenant_id, document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return None


# ---------- Tasks ----------


@utilities_router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(request: Request):
    """List tenant tasks."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    service = _get_task_service()
    tasks = await service.list_tasks(tenant_id)
    return [_task_to_response(t) for t in tasks]


@utilities_router.post("/tasks", response_model=TaskResponse)
async def create_task(payload: TaskCreateRequest, request: Request):
    """Create a task."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    plan = _get_tenant_plan(tenant_id)

    service = _get_task_service()
    try:
        task = await service.create_task(tenant_id, plan, payload.model_dump(exclude_unset=True))
        return _task_to_response(task)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@utilities_router.post("/tasks/from-findings", response_model=list[TaskResponse])
async def create_tasks_from_findings(payload: BulkCreateFromFindingsRequest, request: Request):
    """Bulk-create tasks from security findings."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    plan = _get_tenant_plan(tenant_id)

    service = _get_task_service()
    try:
        tasks = await service.create_tasks_from_findings(tenant_id, plan, payload.finding_ids)
        return [_task_to_response(t) for t in tasks]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@utilities_router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, request: Request):
    """Get a tenant task."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    service = _get_task_service()
    task = await service.get_task(tenant_id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_to_response(task)


@utilities_router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, payload: TaskUpdateRequest, request: Request):
    """Update a tenant task."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    service = _get_task_service()
    task = await service.update_task(tenant_id, task_id, payload.model_dump(exclude_unset=True))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_to_response(task)


@utilities_router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int, request: Request):
    """Delete a tenant task."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    service = _get_task_service()
    deleted = await service.delete_task(tenant_id, task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return None


# ---------- Assets ----------


@utilities_router.get("/assets", response_model=list[AssetResponse])
async def list_assets(request: Request):
    """List tenant assets."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    service = _get_asset_service()
    assets = await service.list_assets(tenant_id)
    return [_asset_to_response(a) for a in assets]


@utilities_router.post("/assets", response_model=AssetResponse)
async def create_asset(payload: AssetCreateRequest, request: Request):
    """Create an asset."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    plan = _get_tenant_plan(tenant_id)

    service = _get_asset_service()
    try:
        asset = await service.create_asset(tenant_id, plan, payload.model_dump(exclude_unset=True))
        return _asset_to_response(asset)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@utilities_router.get("/assets/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: int, request: Request):
    """Get a tenant asset."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    service = _get_asset_service()
    asset = await service.get_asset(tenant_id, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return _asset_to_response(asset)


@utilities_router.patch("/assets/{asset_id}", response_model=AssetResponse)
async def update_asset(asset_id: int, payload: AssetUpdateRequest, request: Request):
    """Update a tenant asset."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    service = _get_asset_service()
    asset = await service.update_asset(tenant_id, asset_id, payload.model_dump(exclude_unset=True))
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return _asset_to_response(asset)


@utilities_router.delete("/assets/{asset_id}", status_code=204)
async def delete_asset(asset_id: int, request: Request):
    """Delete a tenant asset."""
    user_info = await _get_current_user(request)
    tenant_id = int(user_info["tenant_id"])
    service = _get_asset_service()
    deleted = await service.delete_asset(tenant_id, asset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Asset not found")
    return None
