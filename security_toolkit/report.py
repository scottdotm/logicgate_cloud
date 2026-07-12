"""Security assessment report generator."""

import json
import os
from datetime import UTC, datetime
from typing import Any

from jinja2 import Template
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from logicgate_cloud.security_toolkit.assessment_service import AssessmentService

HTML_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Security Assessment Report — {{ domain }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; color: #333; }
        h1 { color: #1a1a1a; }
        h2 { color: #2c2c2c; border-bottom: 2px solid #ddd; padding-bottom: 6px; }
        .score { font-size: 2em; font-weight: bold; }
        .rating-excellent { color: #2e7d32; }
        .rating-good { color: #689f38; }
        .rating-fair { color: #f9a825; }
        .rating-poor { color: #f57c00; }
        .rating-critical { color: #d32f2f; }
        .finding { border: 1px solid #ddd; border-radius: 6px; padding: 16px; margin: 12px 0; }
        .severity-critical { border-left: 6px solid #d32f2f; }
        .severity-high { border-left: 6px solid #f57c00; }
        .severity-medium { border-left: 6px solid #f9a825; }
        .severity-low { border-left: 6px solid #689f38; }
        .severity-info { border-left: 6px solid #9e9e9e; }
        .meta { color: #666; font-size: 0.9em; }
        .recommendation { background: #f5f5f5; padding: 10px; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>Security Assessment Report</h1>
    <p class="meta">Domain: {{ domain }} | Generated: {{ generated_at }} | Assessment ID: {{ assessment_id }}</p>

    <h2>Overall Score</h2>
    <p class="score rating-{{ rating_class }}">{{ score }} / 5.0 — {{ rating }}</p>

    <h2>Executive Summary</h2>
    <p>This assessment evaluated the external security posture and questionnaire responses against the NIST Cybersecurity Framework. The report identifies {{ findings|length }} findings with actionable recommendations.</p>

    <h2>Top Findings</h2>
    {% for finding in findings[:5] %}
    <div class="finding severity-{{ finding.severity }}">
        <strong>[{{ finding.severity|upper }}] {{ finding.title }}</strong><br>
        <span class="meta">NIST: {{ finding.nist_function }} — {{ finding.nist_category or "N/A" }}</span>
        <p>{{ finding.description }}</p>
        <div class="recommendation">
            <strong>Recommendation:</strong> {{ finding.recommendation }}
        </div>
    </div>
    {% endfor %}

    <h2>All Findings</h2>
    {% for finding in findings %}
    <div class="finding severity-{{ finding.severity }}">
        <strong>[{{ finding.severity|upper }}] {{ finding.title }}</strong><br>
        <span class="meta">NIST: {{ finding.nist_function }} — {{ finding.nist_category or "N/A" }} | Effort: {{ finding.effort or "N/A" }}</span>
        <p>{{ finding.description }}</p>
        {% if finding.evidence %}
        <p class="meta"><strong>Evidence:</strong> {{ finding.evidence|tojson }}</p>
        {% endif %}
        <div class="recommendation">
            <strong>Recommendation:</strong> {{ finding.recommendation }}
        </div>
    </div>
    {% endfor %}

    <h2>Methodology & Limitations</h2>
    <p>This assessment uses passive external reconnaissance and a NIST CSF-aligned questionnaire. It does not include penetration testing, internal network scanning, or vulnerability exploitation. Findings should be reviewed by a qualified security professional before acting.</p>
    <p class="meta">Disclaimer: This report is a baseline assessment and is not a guarantee of security or compliance.</p>
</body>
</html>
"""


class ReportGenerator:
    """Generate HTML and PDF reports from a completed assessment."""

    def __init__(self, db_path: str | None = None, report_dir: str | None = None):
        self.assessment_service = AssessmentService(db_path)
        self.report_dir = report_dir or os.environ.get("REPORT_DIR", "reports")
        os.makedirs(self.report_dir, exist_ok=True)

    async def generate_html_report(self, tenant_id: int, assessment_id: int) -> dict[str, Any]:
        """Generate an HTML report for an assessment and return its path."""
        assessment = await self.assessment_service.get_assessment(tenant_id, assessment_id)
        if assessment.status != "complete":
            raise ValueError("Assessment must be complete before generating a report.")

        findings = sorted(
            assessment.findings,
            key=lambda f: ("critical", "high", "medium", "low", "info").index(f.severity),
        )

        rating = self._score_to_rating(assessment.nist_score or 0.0)
        rating_class = rating.lower().replace(" ", "-")

        template = Template(HTML_REPORT_TEMPLATE)
        html = template.render(
            domain=assessment.domain or "N/A",
            assessment_id=assessment.id,
            score=assessment.nist_score,
            rating=rating,
            rating_class=rating_class,
            generated_at=datetime.now(UTC).isoformat(),
            findings=findings,
            tojson=lambda x: json.dumps(x) if x else "",
        )

        filename = f"security_report_{tenant_id}_{assessment.id}.html"
        path = os.path.join(self.report_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

        return {
            "assessment_id": assessment.id,
            "path": path,
            "filename": filename,
        }

    async def generate_pdf_report(self, tenant_id: int, assessment_id: int) -> dict[str, Any]:
        """Generate a PDF report for an assessment and return its path."""
        assessment = await self.assessment_service.get_assessment(tenant_id, assessment_id)
        if assessment.status != "complete":
            raise ValueError("Assessment must be complete before generating a report.")

        findings = sorted(
            assessment.findings,
            key=lambda f: ("critical", "high", "medium", "low", "info").index(f.severity),
        )

        filename = f"security_report_{tenant_id}_{assessment.id}.pdf"
        path = os.path.join(self.report_dir, filename)

        doc = SimpleDocTemplate(path, pagesize=letter)
        styles = getSampleStyleSheet()
        story: list[Any] = []

        title_style = ParagraphStyle(
            "TitleStyle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#1a1a1a"),
            spaceAfter=12,
        )
        story.append(Paragraph("Security Assessment Report", title_style))
        story.append(
            Paragraph(
                f"Domain: {assessment.domain or 'N/A'} | Generated: {datetime.now(UTC).isoformat()}",
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 0.2 * inch))

        score = assessment.nist_score or 0.0
        rating = self._score_to_rating(score)
        story.append(Paragraph(f"Overall Score: {score} / 5.0 — {rating}", styles["Heading2"]))
        story.append(Spacer(1, 0.2 * inch))

        story.append(Paragraph("Executive Summary", styles["Heading2"]))
        story.append(
            Paragraph(
                f"This assessment identified {len(findings)} findings. The following table summarizes the top priorities.",
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 0.1 * inch))

        top_data = [["Severity", "Title", "NIST Function"]]
        for finding in findings[:10]:
            top_data.append([finding.severity.upper(), finding.title, finding.nist_function])

        if len(top_data) > 1:
            table = Table(top_data, colWidths=[1.1 * inch, 4.0 * inch, 1.4 * inch])
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                    ]
                )
            )
            story.append(table)

        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph("Detailed Findings", styles["Heading2"]))

        for finding in findings:
            story.append(Paragraph(f"{finding.title}", styles["Heading3"]))
            story.append(
                Paragraph(
                    f"Severity: {finding.severity.upper()} | NIST: {finding.nist_function} — {finding.nist_category or 'N/A'}",
                    styles["Normal"],
                )
            )
            story.append(Paragraph(finding.description, styles["Normal"]))
            story.append(
                Paragraph(
                    f"<b>Recommendation:</b> {finding.recommendation}",
                    styles["Normal"],
                )
            )
            story.append(Spacer(1, 0.1 * inch))

        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph("Methodology & Limitations", styles["Heading2"]))
        story.append(
            Paragraph(
                "This assessment uses passive external reconnaissance and a NIST CSF-aligned questionnaire. It does not include penetration testing, internal scanning, or exploitation. Findings should be reviewed by a qualified security professional.",
                styles["Normal"],
            )
        )
        story.append(
            Paragraph(
                "Disclaimer: This report is a baseline assessment and is not a guarantee of security or compliance.",
                styles["Italic"],
            )
        )

        doc.build(story)
        return {"assessment_id": assessment.id, "path": path, "filename": filename}

    @staticmethod
    def _score_to_rating(score: float) -> str:
        if score >= 4.5:
            return "Excellent"
        if score >= 3.5:
            return "Good"
        if score >= 2.5:
            return "Fair"
        if score >= 1.5:
            return "Poor"
        return "Critical"
