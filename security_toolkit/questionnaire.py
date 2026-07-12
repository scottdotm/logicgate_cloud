"""NIST CSF questionnaire bank and scoring engine."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Question:
    """A single NIST CSF-aligned questionnaire question."""

    key: str
    text: str
    nist_function: str
    nist_category: str
    weight: float
    answer_type: str  # yes_no, yes_no_partial, text
    guidance: str

    def score_answer(self, answer: str | None) -> float:
        """Return a score between 0.0 and 1.0 for the given answer."""
        if answer is None:
            return 0.0
        answer = answer.strip().lower()
        if answer in ("yes", "implemented"):
            return 1.0
        if answer in ("partial", "in_progress"):
            return 0.5
        if answer in ("no", "not_implemented"):
            return 0.0
        return 0.0


QUESTION_BANK: list[Question] = [
    Question(
        key="id_asset_inventory",
        text="Does the organization maintain an inventory of critical devices, systems, and data?",
        nist_function="ID",
        nist_category="Asset Management",
        weight=1.0,
        answer_type="yes_no",
        guidance="Include laptops, servers, mobile devices, cloud accounts, and critical data repositories.",
    ),
    Question(
        key="id_risk_assessment",
        text="Has a cybersecurity risk assessment been performed in the last 12 months?",
        nist_function="ID",
        nist_category="Risk Assessment",
        weight=1.0,
        answer_type="yes_no",
        guidance="A formal or informal risk assessment that identifies key threats and mitigations counts.",
    ),
    Question(
        key="pr_mfa",
        text="Is multi-factor authentication required for all cloud/email accounts and remote access?",
        nist_function="PR",
        nist_category="Access Control",
        weight=1.5,
        answer_type="yes_no_partial",
        guidance="MFA should be enforced for M365/Google Workspace, VPN, banking, and any system with sensitive data.",
    ),
    Question(
        key="pr_password_policy",
        text="Does the organization enforce a password policy requiring strong, unique passwords?",
        nist_function="PR",
        nist_category="Identity Management",
        weight=1.0,
        answer_type="yes_no_partial",
        guidance="A password manager and policy against password reuse satisfies this control.",
    ),
    Question(
        key="pr_patch_management",
        text="Are systems and applications patched regularly (at least monthly for critical updates)?",
        nist_function="PR",
        nist_category="Maintenance",
        weight=1.0,
        answer_type="yes_no_partial",
        guidance="Include OS updates, browser updates, and third-party application patching.",
    ),
    Question(
        key="pr_encryption",
        text="Is sensitive data encrypted at rest and in transit?",
        nist_function="PR",
        nist_category="Data Security",
        weight=1.0,
        answer_type="yes_no_partial",
        guidance="HTTPS for websites, full-disk encryption on laptops, and encrypted cloud storage count.",
    ),
    Question(
        key="pr_backups",
        text="Are backups performed regularly and tested at least annually?",
        nist_function="PR",
        nist_category="Data Security",
        weight=1.5,
        answer_type="yes_no_partial",
        guidance="Backups should be offline or immutable and cover critical business data.",
    ),
    Question(
        key="de_logging",
        text="Are logs collected and reviewed for security events?",
        nist_function="DE",
        nist_category="Anomalies and Events",
        weight=1.0,
        answer_type="yes_no_partial",
        guidance="This can be built-in M365/Google Workspace logs, firewall logs, or an endpoint monitoring tool.",
    ),
    Question(
        key="de_endpoint_protection",
        text="Is endpoint protection (anti-malware/EDR) installed on all workstations and servers?",
        nist_function="DE",
        nist_category="Continuous Monitoring",
        weight=1.0,
        answer_type="yes_no_partial",
        guidance="Modern EDR is preferred, but traditional antivirus with active monitoring counts as partial.",
    ),
    Question(
        key="rs_incident_plan",
        text="Does the organization have a documented incident response plan?",
        nist_function="RS",
        nist_category="Response Planning",
        weight=1.0,
        answer_type="yes_no",
        guidance="A simple plan that defines who to call, how to isolate systems, and how to document events is sufficient.",
    ),
    Question(
        key="rc_recovery_plan",
        text="Does the organization have a documented disaster recovery / business continuity plan?",
        nist_function="RC",
        nist_category="Recovery Planning",
        weight=1.0,
        answer_type="yes_no",
        guidance="Include RTO/RPO targets, backup restoration procedures, and key contact lists.",
    ),
    Question(
        key="gv_training",
        text="Do employees receive cybersecurity awareness training at least annually?",
        nist_function="GV",
        nist_category="Cybersecurity Risk Management Strategy",
        weight=1.0,
        answer_type="yes_no_partial",
        guidance="Phishing simulations, security awareness videos, or formal training all satisfy this.",
    ),
]

QUESTION_INDEX: dict[str, Question] = {q.key: q for q in QUESTION_BANK}


def get_question(key: str) -> Question | None:
    """Return a question by key."""
    return QUESTION_INDEX.get(key)


def get_all_questions() -> list[Question]:
    """Return the full question bank."""
    return list(QUESTION_BANK)


def score_questionnaire(answers: dict[str, str | None]) -> dict[str, Any]:
    """Score a completed questionnaire and return per-function scores."""
    function_scores: dict[str, list[float]] = {}
    function_weights: dict[str, list[float]] = {}

    for key, answer in answers.items():
        question = get_question(key)
        if not question:
            continue
        score = question.score_answer(answer)
        function_scores.setdefault(question.nist_function, []).append(score)
        function_weights.setdefault(question.nist_function, []).append(question.weight)

    overall_score = 0.0
    overall_weight = 0.0
    per_function = {}

    for func in function_scores:
        weighted_sum = sum(
            s * w for s, w in zip(function_scores[func], function_weights[func], strict=False)
        )
        total_weight = sum(function_weights[func])
        func_score = (weighted_sum / total_weight * 5.0) if total_weight > 0 else 0.0
        per_function[func] = round(func_score, 1)
        overall_score += weighted_sum * 1.0
        overall_weight += total_weight

    overall = (overall_score / overall_weight * 5.0) if overall_weight > 0 else 0.0

    return {
        "overall_score": round(overall, 1),
        "per_function": per_function,
        "answered_count": len(answers),
        "total_count": len(QUESTION_BANK),
    }


def generate_findings_from_answers(answers: dict[str, str | None]) -> list[dict[str, Any]]:
    """Generate findings for questions that score poorly."""
    findings = []
    for key, answer in answers.items():
        question = get_question(key)
        if not question:
            continue
        score = question.score_answer(answer)
        if score < 1.0:
            severity = "high" if score == 0.0 and question.weight >= 1.0 else "medium"
            findings.append(
                {
                    "nist_function": question.nist_function,
                    "nist_category": question.nist_category,
                    "severity": severity,
                    "title": f"{question.nist_category} control gap",
                    "description": question.text,
                    "evidence": {"answer": answer, "expected": "yes or implemented"},
                    "recommendation": question.guidance,
                    "effort": "small" if question.weight < 1.5 else "medium",
                }
            )
    return findings
