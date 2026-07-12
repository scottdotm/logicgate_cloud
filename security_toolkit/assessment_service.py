"""Assessment orchestration service for the security toolkit."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from logicgate_cloud.security_toolkit.common.exceptions import (
    AssessmentNotFoundError,
    TenantLimitError,
)
from logicgate_cloud.security_toolkit.common.models import (
    QuestionnaireAnswer,
    SecurityAssessment,
    SecurityFinding,
)
from logicgate_cloud.security_toolkit.common.service import TenantScopedService
from logicgate_cloud.security_toolkit.questionnaire import (
    generate_findings_from_answers,
    score_questionnaire,
)
from logicgate_cloud.security_toolkit.scanner.external import ExternalScanner

ASSESSMENT_RETENTION_DAYS = 30


class AssessmentService(TenantScopedService):
    """Service for creating, running, and scoring security assessments."""

    def __init__(self, db_path: str | None = None):
        super().__init__(db_path)
        self.scanner = ExternalScanner()

    async def run_free_scan(self, domain: str) -> dict[str, Any]:
        """Run a free external scan and return a summary without persisting it."""
        scan = await self.scanner.scan(domain)
        return {
            "domain": scan["domain"],
            "overall_score": scan["overall_score"],
            "rating": scan["rating"],
            "checks_performed": [c["name"] for c in scan["checks"]],
            "top_findings": [
                {
                    "severity": f["severity"],
                    "title": f["title"],
                    "nist_function": f["nist_function"],
                }
                for f in scan["findings"][:3]
            ],
        }

    async def create_assessment(
        self,
        tenant_id: int,
        plan: str,
        domain: str | None = None,
        assessment_type: str = "paid_full",
    ) -> SecurityAssessment:
        """Create a new tenant assessment, enforcing plan limits."""
        if assessment_type == "paid_full" and not await self.has_feature(
            tenant_id, plan, "security_assessment"
        ):
            raise TenantLimitError(
                "Paid security assessments are not included in the current plan."
            )

        async with self.session() as session:
            count_result = await session.execute(
                select(func.count(SecurityAssessment.id)).where(
                    SecurityAssessment.tenant_id == tenant_id,
                    SecurityAssessment.status != "failed",
                )
            )
            current_count = count_result.scalar() or 0
            await self.check_limit(tenant_id, "security_assessments", current_count, plan)

            expires_at = datetime.now(UTC) + timedelta(days=ASSESSMENT_RETENTION_DAYS)
            assessment = SecurityAssessment(
                tenant_id=tenant_id,
                domain=domain,
                status="pending",
                assessment_type=assessment_type,
                expires_at=expires_at,
            )
            session.add(assessment)
            await session.commit()
            await session.refresh(assessment)
            return assessment

    async def run_external_scan(self, tenant_id: int, assessment_id: int) -> SecurityAssessment:
        """Run the external scan for an existing assessment and persist findings."""
        async with self.session() as session:
            assessment = await self._get_assessment(session, tenant_id, assessment_id)
            if not assessment.domain:
                raise AssessmentNotFoundError("Assessment has no domain configured.")

            assessment.status = "scanning"
            await session.commit()

            try:
                scan = await self.scanner.scan(assessment.domain)
            except Exception as exc:
                assessment.status = "failed"
                await session.commit()
                raise exc

            for raw in scan["findings"]:
                finding = SecurityFinding(
                    assessment_id=assessment.id,
                    tenant_id=tenant_id,
                    nist_function=raw["nist_function"],
                    nist_category=raw.get("nist_category"),
                    severity=raw["severity"],
                    title=raw["title"],
                    description=raw["description"],
                    evidence=raw.get("evidence"),
                    recommendation=raw["recommendation"],
                    effort=raw.get("effort"),
                )
                session.add(finding)

            assessment.status = (
                "awaiting_input" if assessment.assessment_type == "paid_full" else "complete"
            )
            assessment.nist_score = scan["overall_score"]
            if assessment.status == "complete":
                assessment.completed_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(assessment)
            return assessment

    async def submit_questionnaire(
        self, tenant_id: int, assessment_id: int, answers: dict[str, str | None]
    ) -> SecurityAssessment:
        """Store questionnaire answers, score them, and finalize the assessment."""
        async with self.session() as session:
            assessment = await self._get_assessment(session, tenant_id, assessment_id)

            # Store answers
            for key, answer in answers.items():
                qa = QuestionnaireAnswer(
                    assessment_id=assessment.id,
                    tenant_id=tenant_id,
                    question_key=key,
                    answer=answer,
                )
                session.add(qa)

            # Generate findings from poor answers
            q_findings = generate_findings_from_answers(answers)
            for raw in q_findings:
                finding = SecurityFinding(
                    assessment_id=assessment.id,
                    tenant_id=tenant_id,
                    nist_function=raw["nist_function"],
                    nist_category=raw.get("nist_category"),
                    severity=raw["severity"],
                    title=raw["title"],
                    description=raw["description"],
                    evidence=raw.get("evidence"),
                    recommendation=raw["recommendation"],
                    effort=raw.get("effort"),
                )
                session.add(finding)

            score = score_questionnaire(answers)
            assessment.nist_score = self._blend_scores(
                assessment.nist_score, score["overall_score"]
            )
            assessment.status = "complete"
            assessment.completed_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(assessment)
            return assessment

    async def get_assessment(self, tenant_id: int, assessment_id: int) -> SecurityAssessment:
        """Fetch a single assessment with its findings and answers."""
        async with self.session() as session:
            assessment = await self._get_assessment(session, tenant_id, assessment_id)
            return assessment

    async def list_assessments(self, tenant_id: int, limit: int = 50) -> list[SecurityAssessment]:
        """List recent assessments for a tenant."""
        async with self.session() as session:
            result = await session.execute(
                select(SecurityAssessment)
                .where(SecurityAssessment.tenant_id == tenant_id)
                .order_by(SecurityAssessment.created_at.desc())
                .limit(limit)
                .options(selectinload(SecurityAssessment.findings))
            )
            return list(result.scalars().all())

    async def delete_assessment(self, tenant_id: int, assessment_id: int) -> None:
        """Delete a tenant assessment."""
        async with self.session() as session:
            assessment = await self._get_assessment(session, tenant_id, assessment_id)
            await session.delete(assessment)
            await session.commit()

    async def cleanup_expired(self) -> int:
        """Delete assessments past their expiration date."""
        async with self.session() as session:
            now = datetime.now(UTC)
            result = await session.execute(
                select(SecurityAssessment).where(
                    SecurityAssessment.expires_at is not None,
                    SecurityAssessment.expires_at < now,
                )
            )
            expired = result.scalars().all()
            for assessment in expired:
                await session.delete(assessment)
            await session.commit()
            return len(expired)

    @staticmethod
    async def _get_assessment(session, tenant_id: int, assessment_id: int) -> SecurityAssessment:
        """Internal helper to load an assessment with relationships."""
        result = await session.execute(
            select(SecurityAssessment)
            .where(
                SecurityAssessment.id == assessment_id,
                SecurityAssessment.tenant_id == tenant_id,
            )
            .options(
                selectinload(SecurityAssessment.findings), selectinload(SecurityAssessment.answers)
            )
        )
        assessment = result.scalar_one_or_none()
        if not assessment:
            raise AssessmentNotFoundError(
                f"Assessment {assessment_id} not found for tenant {tenant_id}."
            )
        return assessment

    @staticmethod
    def _blend_scores(scan_score: float | None, questionnaire_score: float) -> float:
        """Blend external scan score and questionnaire score into a single NIST score."""
        if scan_score is None:
            return round(questionnaire_score, 1)
        return round((scan_score * 0.4) + (questionnaire_score * 0.6), 1)
