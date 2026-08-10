from __future__ import annotations

import re
import unicodedata
from html import escape
from pathlib import Path
from typing import Any, Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, HRFlowable, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle


NAVY = colors.HexColor("#17324D")
TEAL = colors.HexColor("#147D83")
CORAL = colors.HexColor("#C54F45")
PALE = colors.HexColor("#EEF5F6")
SLATE = colors.HexColor("#566573")


def _font() -> str:
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial Unicode.ttf"):
        if Path(path).exists():
            pdfmetrics.registerFont(TTFont("DigestSans", path))
            return "DigestSans"
    return "Helvetica"


FONT = _font()


def clean(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    for source, target in {"\u2010": "-", "\u2011": "-", "\u2013": "-", "\u2014": "-", "\u2192": "->"}.items():
        text = text.replace(source, target)
    return re.sub(r"\s+", " ", text).strip()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "kicker": ParagraphStyle("kicker", parent=base["Normal"], fontName=FONT, fontSize=9, leading=11, textColor=TEAL, spaceAfter=5),
        "cover": ParagraphStyle("cover", parent=base["Title"], fontName=FONT, fontSize=27, leading=32, textColor=NAVY, spaceAfter=10),
        "title": ParagraphStyle("title", parent=base["Heading1"], fontName=FONT, fontSize=18, leading=22, textColor=NAVY, spaceAfter=7),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName=FONT, fontSize=11, leading=14, textColor=CORAL, spaceBefore=7, spaceAfter=3),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontName=FONT, fontSize=9.5, leading=12, textColor=TEAL, spaceBefore=5, spaceAfter=2),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName=FONT, fontSize=8.4, leading=10.8, textColor=NAVY, spaceAfter=4),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontName=FONT, fontSize=7.2, leading=9.2, textColor=SLATE, spaceAfter=3),
        "bullet": ParagraphStyle("bullet", parent=base["BodyText"], fontName=FONT, fontSize=8, leading=10.2, leftIndent=11, firstLineIndent=-7, bulletIndent=2, textColor=NAVY, spaceAfter=2),
        "tag": ParagraphStyle("tag", parent=base["BodyText"], fontName=FONT, fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.white),
    }


def para(value: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(clean(value)), style)


def bullets(values: Iterable[Any], style: ParagraphStyle) -> list[Paragraph]:
    return [Paragraph(f"<bullet>&bull;</bullet>{escape(clean(value))}", style) for value in values or []]


def render_report(report: dict[str, Any], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    doc = BaseDocTemplate(str(output), pagesize=landscape(letter), leftMargin=0.5 * inch, rightMargin=0.5 * inch, topMargin=0.5 * inch, bottomMargin=0.45 * inch, title=f"Weekly ZGA/MZT digest {report['coverage']['end']}", author="Weekly ZGA/MZT GitHub pipeline")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")

    def decorate(canvas, current_doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#CBD6DE"))
        canvas.line(doc.leftMargin, 0.33 * inch, landscape(letter)[0] - doc.rightMargin, 0.33 * inch)
        canvas.setFont(FONT, 6.8)
        canvas.setFillColor(SLATE)
        canvas.drawString(doc.leftMargin, 0.19 * inch, "Weekly ZGA/MZT literature infographic | Automated synthesis - verify before grant use")
        canvas.drawRightString(landscape(letter)[0] - doc.rightMargin, 0.19 * inch, str(current_doc.page))
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="digest", frames=[frame], onPage=decorate)])
    papers = report.get("papers") or []
    counts = {category: sum(1 for paper in papers if paper.get("category") == category) for category in ("research", "review", "preprint")}
    story: list[Any] = [
        Spacer(1, 0.15 * inch),
        para("WEEKLY LITERATURE RADAR", styles["kicker"]),
        para("Zygotic genome activation & maternal-to-zygotic transition", styles["cover"]),
        para(f"Coverage: {report['coverage']['start']} to {report['coverage']['end']} | Retrieved: {report['retrieved_at']}", styles["body"]),
        HRFlowable(width="100%", thickness=4, color=TEAL, spaceAfter=10),
        Table([[para(f"{counts['research']}\nRESEARCH", styles["tag"]), para(f"{counts['review']}\nREVIEWS", styles["tag"]), para(f"{counts['preprint']}\nPREPRINTS", styles["tag"])]], colWidths=[doc.width / 3] * 3, style=TableStyle([("BACKGROUND", (0, 0), (0, 0), TEAL), ("BACKGROUND", (1, 0), (1, 0), CORAL), ("BACKGROUND", (2, 0), (2, 0), NAVY), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)])),
        para("Coverage and evidence", styles["h2"]),
        para(report.get("source_note"), styles["body"]),
        para("Why early Xenopus now", styles["h2"]),
        para((report.get("synthesis") or {}).get("why_xenopus_now"), styles["body"]),
    ]
    if not papers:
        story += [para("No qualifying papers found", styles["title"]), para("The configured sources and concepts were searched for this window. See the structured JSON report for query details and source errors.", styles["body"])]

    for index, paper in enumerate(papers, start=1):
        label = {"research": "PRIMARY RESEARCH", "review": "REVIEW & FIELD SYNTHESIS", "preprint": "PREPRINT - NOT PEER REVIEWED"}.get(paper.get("category"), "PAPER")
        story += [PageBreak(), para(f"{label} | {index} OF {len(papers)}", styles["kicker"]), para(paper.get("title"), styles["title"]), para(paper.get("authors"), styles["small"])]
        metadata = f"{paper.get('journal')} | {paper.get('article_type')} | {paper.get('publication_date')} | DOI/ID: {paper.get('doi') or paper.get('id')} | {paper.get('canonical_url')}"
        story.append(Table([[para(metadata, styles["small"])]], colWidths=[doc.width], style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7D7DD")), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)])))
        heading = "CENTRAL SYNTHESIS" if paper.get("category") == "review" else "MAIN DISCOVERY"
        story += [para(heading, styles["h2"]), para(paper.get("main_discovery"), styles["body"]), para("IMPORTANCE & IMPLICATION", styles["h2"]), para(paper.get("importance_implication"), styles["body"]), para("MAIN / NEW TECHNOLOGIES, TOOLS & METHODS", styles["h2"]), *bullets(paper.get("methods") or [], styles["bullet"]), para("DECISIVE EVIDENCE", styles["h2"]), *bullets(paper.get("key_evidence") or [], styles["bullet"]), para("LIMITATIONS & ACCESS", styles["h2"]), *bullets((paper.get("limitations") or []) + [paper.get("access_note")], styles["bullet"])]
        for idea_index, idea in enumerate(paper.get("grant_ideas") or [], start=1):
            story += [PageBreak(), para(f"EARLY XENOPUS GRANT IDEA {idea_index} | PAPER {index}", styles["kicker"]), para(idea.get("title"), styles["title"])]
            for heading_text, key in (("FALSIFIABLE HYPOTHESIS", "hypothesis"), ("RATIONALE & XENOPUS ADVANTAGE", "rationale"), ("STAGE, PERTURBATION & ASSAY", "design"), ("READOUTS & ESSENTIAL CONTROLS", "readouts_controls"), ("SUPPORTING VS. REFUTING RESULT", "support_refute"), ("NOVELTY, FEASIBILITY & RISK", "novelty_feasibility_risk")):
                story += [para(heading_text, styles["h2"]), para(idea.get(key), styles["body"])]

    synthesis = report.get("synthesis") or {}
    story += [PageBreak(), para("CROSS-PAPER SYNTHESIS", styles["title"]), HRFlowable(width="100%", thickness=4, color=CORAL, spaceAfter=8), para("CONVERGENT MECHANISMS / THEMES", styles["h2"]), *bullets(synthesis.get("themes") or [], styles["bullet"]), para("METHODS & TECHNOLOGY TRENDS", styles["h2"]), *bullets(synthesis.get("methods_trends") or [], styles["bullet"]), para("RANKED GRANT DIRECTIONS", styles["h2"])]
    for item in synthesis.get("ranked_grant_directions") or []:
        story += [para(f"#{item.get('rank')} {item.get('title')}", styles["h3"]), para(" | ".join(f"{key.title()}: {clean(item.get(key))}" for key in ("rationale", "significance", "novelty", "feasibility", "risk")), styles["body"])]
    story += [para("SOURCE / METHOD NOTE", styles["h2"]), para(report.get("source_note"), styles["small"])]
    doc.build(story)
    return output

