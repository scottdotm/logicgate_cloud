"""
Lake survey PDF report generator.

Uses ReportLab to create a human-readable PDF report from a survey and its images.
"""

import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
)
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from logicgate_cloud.lake.service import LakeService


class ReportGenerator:
    """Generate a PDF report for a lake survey."""

    def __init__(self, lake_service: LakeService):
        self.lake_service = lake_service

    def generate(self, tenant_id: int, survey_id: int, output_path: str) -> str:
        """Generate a PDF report and return the output path."""
        survey = self.lake_service.get_survey(tenant_id, survey_id)
        if not survey:
            raise ValueError(f"Survey {survey_id} not found")

        lake = self.lake_service.get_lake(tenant_id, survey.lake_id)
        if not lake:
            raise ValueError(f"Lake {survey.lake_id} not found")

        images = self.lake_service.list_images(tenant_id, survey_id)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.6 * inch,
            leftMargin=0.6 * inch,
            topMargin=0.8 * inch,
            bottomMargin=0.8 * inch,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "LakeTitle",
            parent=styles["Heading1"],
            fontSize=22,
            spaceAfter=14,
            textColor=colors.HexColor("#1a365d"),
        )
        heading_style = ParagraphStyle(
            "LakeHeading",
            parent=styles["Heading2"],
            fontSize=14,
            spaceAfter=8,
            textColor=colors.HexColor("#2c5282"),
        )
        body_style = styles["BodyText"]
        body_style.fontSize = 10

        story = []

        # Cover
        story.append(Paragraph(f"Lake Survey Report: {lake.name}", title_style))
        story.append(Paragraph(f"Survey: {survey.name}", heading_style))
        story.append(Spacer(1, 0.2 * inch))

        meta_data = [
            ["Lake", lake.name],
            ["Location", lake.location or "Not specified"],
            ["Body ID", lake.body_id or "Not specified"],
            ["Survey Date", _fmt_datetime(survey.scheduled_at or survey.created_at)],
            ["Completed", _fmt_datetime(survey.completed_at) if survey.completed_at else "Pending"],
            ["Pilot", survey.pilot_name or "Not specified"],
            ["Drone", survey.drone_name or "Not specified"],
            ["Altitude", f"{survey.altitude_m} m" if survey.altitude_m else "Not specified"],
            ["Images", str(len(images))],
            ["Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ]
        meta_table = Table(meta_data, colWidths=[1.6 * inch, 4.8 * inch])
        meta_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf2f7")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(meta_table)
        story.append(Spacer(1, 0.3 * inch))

        # Notes
        if lake.notes:
            story.append(Paragraph("Lake Notes", heading_style))
            story.append(Paragraph(lake.notes, body_style))
            story.append(Spacer(1, 0.2 * inch))

        if survey.notes:
            story.append(Paragraph("Survey Notes", heading_style))
            story.append(Paragraph(survey.notes, body_style))
            story.append(Spacer(1, 0.2 * inch))

        # Image gallery
        if images:
            story.append(PageBreak())
            story.append(Paragraph("Image Gallery", heading_style))
            story.append(
                Paragraph(
                    "The following images were captured during the survey. GPS coordinates are extracted from image EXIF when available.",
                    body_style,
                )
            )
            story.append(Spacer(1, 0.2 * inch))

            for img in images:
                story.append(Paragraph(f"Image: {img.filename}", styles["Heading3"]))
                if os.path.exists(img.thumbnail_path or ""):
                    try:
                        story.append(RLImage(img.thumbnail_path, width=4.5 * inch, height=3 * inch))
                    except Exception:
                        story.append(Paragraph("(thumbnail unavailable)", body_style))
                else:
                    story.append(Paragraph("(thumbnail unavailable)", body_style))

                img_meta = [
                    ["Filename", img.filename],
                    ["Latitude", f"{img.latitude:.6f}" if img.latitude else "Not available"],
                    ["Longitude", f"{img.longitude:.6f}" if img.longitude else "Not available"],
                    ["Altitude", f"{img.altitude_m} m" if img.altitude_m else "Not available"],
                    [
                        "Captured",
                        _fmt_datetime(img.captured_at) if img.captured_at else "Not available",
                    ],
                ]
                img_table = Table(img_meta, colWidths=[1.4 * inch, 5 * inch])
                img_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f7fafc")),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                            ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("LEFTPADDING", (0, 0), (-1, -1), 4),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                story.append(img_table)
                story.append(Spacer(1, 0.2 * inch))

        doc.build(story)
        return output_path


def _fmt_datetime(dt) -> str:
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")
