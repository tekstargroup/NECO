#!/usr/bin/env python3
"""Generate PDF: Sprint 20 Next Steps + Research Tasks for NECO Compliance Signal Engine."""

import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, ListFlowable, ListItem,
)
from reportlab.lib.enums import TA_LEFT

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output", "pdf")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "Sprint20_Next_Steps_and_Research.pdf")


def _p(text, style):
    return Paragraph(
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
        style,
    )


def build_story(styles):
    story = []

    # Title
    story.append(Paragraph("Sprint 20: Next Steps &amp; Research", styles["Title"]))
    story.append(Spacer(1, 0.15 * inch))
    story.append(_p("Compliance Signal Engine — Source Validation", styles["Heading2"]))
    story.append(Spacer(1, 0.3 * inch))

    # Test results
    story.append(Paragraph("Test Results (March 18, 2026)", styles["Heading1"]))
    story.append(Spacer(1, 0.1 * inch))
    data = [
        ["Source", "Status", "Items"],
        ["EU_TAXUD", "OK", "30"],
        ["JOC", "OK", "40"],
        ["USDA_FSIS", "Empty (403 Forbidden)", "0"],
    ]
    t = Table(data, colWidths=[2 * inch, 2.5 * inch, 1 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3 * inch))

    # Next steps
    story.append(Paragraph("Next Steps (Do These Now)", styles["Heading1"]))
    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("1. API Key — Congress.gov", styles["Heading2"]))
    story.append(_p("• Go to https://api.congress.gov/sign-up", styles["Normal"]))
    story.append(_p("• Register for free API key", styles["Normal"]))
    story.append(_p("• Add to backend/.env: CONGRESS_API_KEY=your_key", styles["Normal"]))
    story.append(_p("• Restart backend", styles["Normal"]))
    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("2. USDA FSIS — Fix 403", styles["Heading2"]))
    story.append(_p("• Current URL returns 403 Forbidden (blocks non-browser)", styles["Normal"]))
    story.append(_p("• Try FSIS API instead: https://www.fsis.usda.gov/api", styles["Normal"]))
    story.append(_p("• Or try different RSS: fsis-content/rss/recalls", styles["Normal"]))
    story.append(_p("• Or add browser-like User-Agent to requests", styles["Normal"]))
    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("3. Run Full Test", styles["Heading2"]))
    story.append(_p("cd backend && source venv/bin/activate", styles["Normal"]))
    story.append(_p("python scripts/test_regulatory_sources.py", styles["Normal"]))
    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("4. Poll + Process", styles["Heading2"]))
    story.append(_p("• Signal Health page → Poll now", styles["Normal"]))
    story.append(_p("• Signal Health page → Process now", styles["Normal"]))
    story.append(_p("• Signal Health page → Refresh HTS", styles["Normal"]))
    story.append(_p("• Verify PSC Radar shows alerts", styles["Normal"]))
    story.append(Spacer(1, 0.3 * inch))

    # Research section
    story.append(PageBreak())
    story.append(Paragraph("What Still Needs Research", styles["Heading1"]))
    story.append(Spacer(1, 0.2 * inch))

    research_items = [
        ("CBP_CROSS", [
            "rulings.cbp.gov may use client-side rendering",
            "Visit https://rulings.cbp.gov/search, open DevTools → Network",
            "See if there's an API call when searching",
            "If no API: consider Playwright/headless browser",
        ]),
        ("WHITE_HOUSE_BRIEFING", [
            "404 — feed moved",
            "Visit https://www.whitehouse.gov/briefing-room/",
            "Look for RSS link in page source or footer",
            "May need different URL or accept no RSS",
        ]),
        ("SUPPLY_CHAIN_DIVE", [
            "404 — no native RSS found",
            "Check if site offers RSS",
            "Option: use rss.app to generate feed from supplychaindive.com",
            "Or remove source if not critical",
        ]),
        ("FLEXPORT_BLOG", [
            "404 — feed may have moved",
            "Visit https://www.flexport.com/blog/",
            "Check for RSS link",
            "If none: remove or use third-party RSS generator",
        ]),
        ("WTO_DISPUTES", [
            "Verify library RSS works",
            "Current: http://www.wto.org/library/rss/latest_news_e.xml",
            "Gateway: https://www.wto.org/english/res_e/webcas_e/rss_e.htm",
            "Test; if fail, WTO may have moved feeds",
        ]),
        ("USDA_FSIS (continued)", [
            "403 persists after URL change",
            "Research: FSIS API docs, GovDelivery RSS alternatives",
            "Email option: https://public.govdelivery.com/accounts/USFSIS/subscriber/new",
        ]),
    ]

    for source, tasks in research_items:
        story.append(Paragraph(source, styles["Heading2"]))
        for task in tasks:
            story.append(_p(f"• {task}", styles["Normal"]))
        story.append(Spacer(1, 0.15 * inch))

    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("Reference Docs", styles["Heading2"]))
    story.append(_p("• docs/SPRINT20_SOURCE_SETUP_GUIDE.md — Full setup checklist", styles["Normal"]))
    story.append(_p("• docs/SOURCE_VALIDATION_GUIDE.md — How to test, add, fix sources", styles["Normal"]))
    story.append(_p("• docs/REGULATORY_SOURCES_TROUBLESHOOTING.md — Proxy, CLI, general help", styles["Normal"]))

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
    print(f"Created: {OUTPUT_FILE}")
    return OUTPUT_FILE


if __name__ == "__main__":
    main()
