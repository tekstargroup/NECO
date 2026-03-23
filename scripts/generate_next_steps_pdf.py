#!/usr/bin/env python3
"""Generate PDF: Next Steps Guide + QA Checklist for NECO decision product."""

import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, ListFlowable, ListItem,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "pdf")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "NECO_Next_Steps_and_QA_Checklist.pdf")


def _p(text, style_name):
    return Paragraph(text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), style_name)


def build_story(styles):
    story = []

    # Title
    story.append(Paragraph("NECO — Next Steps & QA Checklist", styles["Title"]))
    story.append(Spacer(1, 0.2 * inch))
    story.append(_p("From Process to Decision Product", styles["Heading2"]))
    story.append(Spacer(1, 0.3 * inch))

    # --- Part 1: Next Steps Guide ---
    story.append(Paragraph("Part 1: Next Steps Guide", styles["Heading1"]))
    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("The Gap", styles["Heading2"]))
    story.append(_p("NECO has a strong engine, cleaner UI, and good process. But it has not yet built a decision product. Missing piece: explainability + evidence + control.", styles["Normal"]))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Priority Order (Do in This Order)", styles["Heading2"]))
    story.append(Spacer(1, 0.1 * inch))

    # Table: Rename language
    data = [
        ["Current", "Replace With"],
        ["Recommended HTS", "Alternative HTS identified"],
        ["Confidence", "Evidence strength"],
        ["Risk", "Review level"],
    ]
    t = Table(data, colWidths=[2 * inch, 3 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2 * inch))

    items = [
        "1. Rename language — Recommended to Alternative identified; Confidence to Evidence strength; Risk to Review level",
        "2. Build real evidence layer — Page/field/value/ruling (implement per evidence mapping spec)",
        "3. Add per-item decision — Accept | Override | Skip per row; optional Accept all safe",
        "4. Improve drawer — Strengthen why it fits / why it may not with real data",
        "5. Export block — X items require review + Go to Review CTA",
        "6. Decision test — Run 4-question validation for each flagged item",
        "7. Time test — First decision under 60 seconds",
    ]
    for item in items:
        story.append(_p(f"&bull; {item}", styles["Normal"]))
    story.append(Spacer(1, 0.3 * inch))

    story.append(Paragraph("Decision Validation (MANDATORY)", styles["Heading2"]))
    story.append(_p("For each flagged item, test manually. If any answer is no, UI is not done.", styles["Normal"]))
    story.append(Spacer(1, 0.1 * inch))
    for q in [
        "1. Can I explain in 1 sentence why NECO surfaced this?",
        "2. Can I explain why the alternative HTS might be better?",
        "3. Can I explain what the risk is if I'm wrong?",
        "4. Can I decide accept vs reject in under 30 seconds?",
    ]:
        story.append(_p(q, styles["Normal"]))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Time-to-Value Tests", styles["Heading2"]))
    story.append(_p("Full flow: under 5 minutes. First decision: under 60 seconds.", styles["Normal"]))
    story.append(Spacer(1, 0.3 * inch))

    # --- Part 2: QA Checklist Updates ---
    story.append(PageBreak())
    story.append(Paragraph("Part 2: QA Checklist Updates (Sprint 13 & 14)", styles["Heading1"]))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("New Sections Added to Sprint 13", styles["Heading2"]))
    story.append(Paragraph("Decision validation (MANDATORY)", styles["Heading2"]))
    for q in [
        "1. Why surfaced? — Can I explain in 1 sentence why NECO surfaced this item?",
        "2. Why alternative? — Can I explain why the alternative HTS might be better?",
        "3. What risk? — Can I explain what the risk is if I'm wrong?",
        "4. Decide fast — Can I decide accept vs reject in under 30 seconds?",
    ]:
        story.append(_p(q, styles["Normal"]))
    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("Time-to-value", styles["Heading2"]))
    story.append(_p("Full flow: Login to export in under 5 minutes.", styles["Normal"]))
    story.append(_p("First decision: Understand and act on one item in under 60 seconds.", styles["Normal"]))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Export Gating Copy Update", styles["Heading2"]))
    story.append(_p("Banner: X items require review before export is available.", styles["Normal"]))
    story.append(_p("CTA: Go to Review (links to Reviews tab).", styles["Normal"]))
    story.append(Spacer(1, 0.3 * inch))

    story.append(Paragraph("Sign-off", styles["Heading2"]))
    story.append(_p("Sprint 13: All Section 1-8, edge-case, decision validation, and time-to-value items must pass.", styles["Normal"]))
    story.append(_p("Sprint 14: All Upload UX and Export items must pass.", styles["Normal"]))
    story.append(Spacer(1, 0.2 * inch))

    return story


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    styles = getSampleStyleSheet()
    story = build_story(styles)
    doc = SimpleDocTemplate(
        OUTPUT_FILE,
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )
    doc.build(story)
    print(OUTPUT_FILE)
    return OUTPUT_FILE


if __name__ == "__main__":
    main()
