"""Tests for the security toolkit."""

import pytest

from logicgate_cloud.security_toolkit.common.exceptions import InvalidDomainError
from logicgate_cloud.security_toolkit.questionnaire import (
    QUESTION_BANK,
    generate_findings_from_answers,
    score_questionnaire,
)
from logicgate_cloud.security_toolkit.scanner.external import ExternalScanner


def test_question_bank_covers_nist_functions():
    """Every question maps to a known NIST CSF function."""
    functions = {q.nist_function for q in QUESTION_BANK}
    assert functions.issubset({"ID", "PR", "DE", "RS", "RC", "GV"})
    assert len(QUESTION_BANK) >= 10


def test_score_questionnaire_perfect_answers():
    """All 'yes' answers produce a high score."""
    answers = {q.key: "yes" for q in QUESTION_BANK}
    result = score_questionnaire(answers)
    assert result["overall_score"] == 5.0
    assert all(score == 5.0 for score in result["per_function"].values())


def test_score_questionnaire_all_no():
    """All 'no' answers produce a low score."""
    answers = {q.key: "no" for q in QUESTION_BANK}
    result = score_questionnaire(answers)
    assert result["overall_score"] < 2.0


def test_generate_findings_from_answers():
    """Poor answers generate findings."""
    answers = {"pr_mfa": "no"}
    findings = generate_findings_from_answers(answers)
    assert len(findings) == 1
    assert findings[0]["nist_function"] == "PR"
    assert findings[0]["severity"] in ("high", "medium")


def test_external_scanner_domain_normalization():
    """The scanner normalizes HTTP prefixes and paths."""
    scanner = ExternalScanner()
    assert scanner._normalize_domain("https://Example.com/path") == "example.com"
    assert scanner._normalize_domain("http://sub.example.com") == "sub.example.com"


def test_external_scanner_score_computation():
    """Score computation penalizes severity correctly."""
    scanner = ExternalScanner()
    findings = [
        {"severity": "critical"},
        {"severity": "high"},
    ]
    score = scanner._compute_score(findings)
    assert score == 2.0


@pytest.mark.asyncio
async def test_free_scan_returns_summary():
    """A free scan against a stable domain returns a structured summary."""
    scanner = ExternalScanner()
    summary = await scanner.scan("example.com")
    assert "domain" in summary
    assert "overall_score" in summary
    assert 0.0 <= summary["overall_score"] <= 5.0
    assert "checks" in summary
    assert "findings" in summary


@pytest.mark.asyncio
async def test_free_scan_invalid_domain():
    """Invalid domains raise InvalidDomainError."""
    scanner = ExternalScanner()
    with pytest.raises(InvalidDomainError):
        await scanner.scan("not_a_domain")
