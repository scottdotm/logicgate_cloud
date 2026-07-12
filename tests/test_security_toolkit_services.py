"""Service-layer tests for the security toolkit utilities."""

import os
import tempfile
from contextlib import suppress

import pytest

from logicgate_cloud.security_toolkit.assessment_service import AssessmentService
from logicgate_cloud.security_toolkit.assets.service import AssetService
from logicgate_cloud.security_toolkit.common.exceptions import TenantLimitError
from logicgate_cloud.security_toolkit.common.models import Base
from logicgate_cloud.security_toolkit.docs.service import DocumentService
from logicgate_cloud.security_toolkit.policies.service import PolicyService
from logicgate_cloud.security_toolkit.report import ReportGenerator
from logicgate_cloud.security_toolkit.tasks.service import TaskService


@pytest.fixture
async def db_path():
    """Provide a temporary SQLite database path for tests."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Create tables synchronously using the shared Base metadata
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(engine)
    engine.dispose()

    yield path
    with suppress(PermissionError):
        os.unlink(path)


@pytest.fixture
async def policy_service(db_path):
    service = PolicyService(db_path)
    await service.seed_templates()
    return service


@pytest.fixture
async def doc_service(db_path):
    return DocumentService(db_path)


@pytest.fixture
async def task_service(db_path):
    return TaskService(db_path)


@pytest.fixture
async def asset_service(db_path):
    return AssetService(db_path)


@pytest.fixture
async def assessment_service(db_path):
    return AssessmentService(db_path)


@pytest.fixture
async def report_generator(db_path):
    report_dir = tempfile.mkdtemp()
    return ReportGenerator(db_path, report_dir=report_dir)


@pytest.mark.asyncio
async def test_policy_service_seed_and_list(policy_service):
    templates = await policy_service.list_templates()
    assert len(templates) >= 10


@pytest.mark.asyncio
async def test_policy_service_create_from_template(policy_service):
    policy = await policy_service.create_policy(
        tenant_id=1,
        plan="starter",
        data={"template_key": "mfa_policy"},
    )
    assert policy.title == "Multi-Factor Authentication Policy"
    assert policy.template_key == "mfa_policy"
    assert policy.tenant_id == 1


@pytest.mark.asyncio
async def test_policy_service_limit_enforced(policy_service):
    for _ in range(3):
        await policy_service.create_policy(tenant_id=2, plan="freemium", data={"title": "Test"})

    with pytest.raises(TenantLimitError):
        await policy_service.create_policy(tenant_id=2, plan="freemium", data={"title": "Test"})


@pytest.mark.asyncio
async def test_document_service_crud(doc_service):
    doc = await doc_service.create_document(
        tenant_id=1,
        plan="starter",
        data={"title": "Network Diagram", "doc_type": "network", "content": "..."},
    )
    assert doc.title == "Network Diagram"

    docs = await doc_service.list_documents(tenant_id=1)
    assert len(docs) == 1

    updated = await doc_service.update_document(
        tenant_id=1, document_id=doc.id, data={"title": "Updated"}
    )
    assert updated.title == "Updated"

    deleted = await doc_service.delete_document(tenant_id=1, document_id=doc.id)
    assert deleted is True


@pytest.mark.asyncio
async def test_task_service_create_and_list(task_service):
    task = await task_service.create_task(
        tenant_id=1,
        plan="starter",
        data={"title": "Patch servers", "priority": "high"},
    )
    assert task.title == "Patch servers"

    tasks = await task_service.list_tasks(tenant_id=1)
    assert len(tasks) == 1


@pytest.mark.asyncio
async def test_asset_service_create_and_limit(asset_service):
    asset = await asset_service.create_asset(
        tenant_id=1,
        plan="starter",
        data={"name": "Office Router", "asset_type": "network"},
    )
    assert asset.name == "Office Router"

    assets = await asset_service.list_assets(tenant_id=1)
    assert len(assets) == 1


@pytest.mark.asyncio
async def test_assessment_service_free_scan_and_paid_flow(assessment_service):
    summary = await assessment_service.run_free_scan("example.com")
    assert 0.0 <= summary["overall_score"] <= 5.0

    assessment = await assessment_service.create_assessment(
        tenant_id=1,
        plan="starter",
        domain="example.com",
        assessment_type="paid_full",
    )
    assert assessment.status == "pending"

    scanned = await assessment_service.run_external_scan(tenant_id=1, assessment_id=assessment.id)
    assert scanned.status in ("awaiting_input", "complete")

    answers = {q.key: "no" for q in []}  # placeholder; questionnaire imported later
    from logicgate_cloud.security_toolkit.questionnaire import QUESTION_BANK

    answers = {q.key: "no" for q in QUESTION_BANK}
    completed = await assessment_service.submit_questionnaire(
        tenant_id=1, assessment_id=assessment.id, answers=answers
    )
    assert completed.status == "complete"
    assert completed.nist_score is not None


@pytest.mark.asyncio
async def test_assessment_service_tenant_isolation(assessment_service):
    a1 = await assessment_service.create_assessment(
        tenant_id=1, plan="starter", domain="tenant1.com", assessment_type="paid_full"
    )
    a2 = await assessment_service.create_assessment(
        tenant_id=2, plan="starter", domain="tenant2.com", assessment_type="paid_full"
    )

    list1 = await assessment_service.list_assessments(tenant_id=1)
    assert all(a.tenant_id == 1 for a in list1)
    ids1 = {a.id for a in list1}
    assert a1.id in ids1
    assert a2.id not in ids1


@pytest.mark.asyncio
async def test_report_generator_creates_html(assessment_service, report_generator):
    from logicgate_cloud.security_toolkit.questionnaire import QUESTION_BANK

    assessment = await assessment_service.create_assessment(
        tenant_id=1, plan="starter", domain="example.com", assessment_type="paid_full"
    )
    await assessment_service.run_external_scan(tenant_id=1, assessment_id=assessment.id)
    answers = {q.key: "no" for q in QUESTION_BANK}
    await assessment_service.submit_questionnaire(
        tenant_id=1, assessment_id=assessment.id, answers=answers
    )

    result = await report_generator.generate_html_report(tenant_id=1, assessment_id=assessment.id)
    assert "path" in result
    assert os.path.exists(result["path"])

    with open(result["path"], encoding="utf-8") as f:
        html = f.read()
    assert "Security Assessment Report" in html
    assert "example.com" in html


@pytest.mark.asyncio
async def test_report_generator_creates_pdf(assessment_service, report_generator):
    from logicgate_cloud.security_toolkit.questionnaire import QUESTION_BANK

    assessment = await assessment_service.create_assessment(
        tenant_id=1, plan="starter", domain="example.com", assessment_type="paid_full"
    )
    await assessment_service.run_external_scan(tenant_id=1, assessment_id=assessment.id)
    answers = {q.key: "no" for q in QUESTION_BANK}
    await assessment_service.submit_questionnaire(
        tenant_id=1, assessment_id=assessment.id, answers=answers
    )

    result = await report_generator.generate_pdf_report(tenant_id=1, assessment_id=assessment.id)
    assert "path" in result
    assert os.path.exists(result["path"])
    assert result["path"].endswith(".pdf")
