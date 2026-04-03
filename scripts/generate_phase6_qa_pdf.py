#!/usr/bin/env python3
"""
Build a printable PDF from docs/PHASE6_MANUAL_TESTING_AND_QA_HARNESS.md (Phase 6 + QA inventory).

Usage (from repo root):
  python scripts/generate_phase6_qa_pdf.py
  python scripts/generate_phase6_qa_pdf.py --out output/MyName.pdf

Requires: reportlab (backend venv has it)
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

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


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _clean_md_links(s: str) -> str:
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)


def _inline_to_xml(s: str) -> str:
    s = _clean_md_links(s)

    def _code(m: re.Match) -> str:
        return "<font name='Courier'>" + html.escape(m.group(1)) + "</font>"

    s = re.sub(r"`([^`]+)`", _code, s)
    parts = re.split(r"(\*\*.+?\*\*)", s)
    out: list[str] = []
    for p in parts:
        if p.startswith("**") and p.endswith("**") and len(p) > 4:
            inner = html.escape(p[2:-2])
            out.append(f"<b>{inner}</b>")
        else:
            out.append(html.escape(p))
    return "".join(out)


def _parse_table(rows: list[str]) -> Table:
    data: list[list[str]] = []
    for row in rows:
        if re.match(r"^\|[\s\-:|]+\|?\s*$", row.strip()):
            continue
        cells = [c.strip() for c in row.strip().split("|") if c.strip() != ""]
        if cells:
            data.append([Paragraph(_inline_to_xml(c), _styles["TableCell"]) for c in cells])
    if not data:
        return Table([["(empty)"]])
    t = Table(data, colWidths=None, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


_styles: dict[str, ParagraphStyle] = {}


def _init_styles() -> None:
    global _styles
    base = getSampleStyleSheet()
    _styles = {
        "Title": ParagraphStyle(
            name="Title",
            parent=base["Heading1"],
            fontSize=16,
            spaceAfter=12,
            textColor=colors.HexColor("#111111"),
        ),
        "H2": ParagraphStyle(
            name="H2",
            parent=base["Heading2"],
            fontSize=13,
            spaceBefore=14,
            spaceAfter=8,
            textColor=colors.HexColor("#1a1a1a"),
        ),
        "H3": ParagraphStyle(
            name="H3",
            parent=base["Heading3"],
            fontSize=11,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "Body": ParagraphStyle(
            name="Body",
            parent=base["Normal"],
            fontSize=9.5,
            leading=12,
            spaceAfter=6,
        ),
        "TableCell": ParagraphStyle(
            name="TableCell",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
        ),
        "Footer": ParagraphStyle(
            name="Footer",
            parent=base["Normal"],
            fontSize=8,
            textColor=colors.grey,
            spaceBefore=12,
        ),
    }


def md_to_story(md_path: Path) -> list:
    _init_styles()
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    story: list = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped == "---":
            story.append(Spacer(1, 8))
            i += 1
            continue

        if stripped.startswith("# ") and not stripped.startswith("##"):
            story.append(Paragraph(_inline_to_xml(stripped[2:]), _styles["Title"]))
            i += 1
            continue

        if stripped.startswith("## "):
            story.append(Paragraph(_inline_to_xml(stripped[3:]), _styles["H2"]))
            i += 1
            continue

        if stripped.startswith("### "):
            story.append(Paragraph(_inline_to_xml(stripped[4:]), _styles["H3"]))
            i += 1
            continue

        if stripped.startswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            story.append(_parse_table(block))
            story.append(Spacer(1, 8))
            continue

        if not stripped:
            i += 1
            continue

        story.append(Paragraph(_inline_to_xml(line), _styles["Body"]))
        i += 1

    return story


def main() -> None:
    root = _repo_root()
    md_path = root / "docs" / "PHASE6_MANUAL_TESTING_AND_QA_HARNESS.md"
    if not md_path.is_file():
        print(f"Missing: {md_path}", file=sys.stderr)
        sys.exit(1)

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        type=Path,
        default=root / "output" / "PHASE6_QA_Harness_NECO.pdf",
        help="Output PDF path",
    )
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    story = md_to_story(md_path)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story.append(Spacer(1, 16))
    story.append(
        Paragraph(
            f"<i>Generated {generated} from docs/PHASE6_MANUAL_TESTING_AND_QA_HARNESS.md "
            f"(Phase 6 checklist + pre-flight + QA harness inventory).</i>",
            _styles["Footer"],
        )
    )

    doc = SimpleDocTemplate(
        str(args.out),
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title="NECO Phase 6 & QA Harness",
    )
    doc.build(story)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
