from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .emailer import send_report_email
from .qa import validate_pdf
from .report_pdf import render_report
from .sources import SEARCH_PHRASES, fetch_weekly_papers
from .summarize import summarize_paper, synthesize


def load_state(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {"version": 1, "processed_ids": {}, "runs": []}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the weekly ZGA/MZT research and review infographic")
    parser.add_argument("--state", default="state/weekly_state.json")
    parser.add_argument("--pdf-dir", default="pdf")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--date", help="Coverage end date (YYYY-MM-DD); defaults to current America/New_York date")
    args = parser.parse_args()

    end = dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(ZoneInfo("America/New_York")).date()
    coverage_start = end - dt.timedelta(days=6)
    state_path = Path(args.state)
    state = load_state(state_path)
    query_start = coverage_start if not state.get("last_successful_run") else end - dt.timedelta(days=13)
    candidates = fetch_weekly_papers(query_start, end)
    processed = state.get("processed_ids") or {}
    selected = []
    for paper in candidates:
        key = str(paper.get("id") or paper.get("doi") or paper.get("title")).lower()
        if key in processed:
            continue
        publication_date = str(paper.get("publication_date") or "")
        paper["late_indexed"] = bool(publication_date and publication_date < coverage_start.isoformat())
        selected.append(paper)

    analyzed = [summarize_paper(paper) for paper in selected]
    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()
    report = {
        "coverage": {"start": coverage_start.isoformat(), "end": end.isoformat(), "query_start": query_start.isoformat()},
        "retrieved_at": retrieved_at,
        "papers": analyzed,
        "synthesis": synthesize(analyzed),
        "search_phrases": list(SEARCH_PHRASES),
        "source_note": "Discovery used Europe PMC and Crossref public APIs with a 7-day reporting window and 14-day late-indexing lookback. Summaries used only retrieved metadata/abstracts and a local Ollama model; no OpenAI service was called. Full text was not assumed.",
    }
    year = str(end.year)
    pdf_path = Path(args.pdf_dir) / year / f"zga_mzt_weekly_{end.isoformat()}.pdf"
    report_path = Path(args.reports_dir) / year / f"zga_mzt_weekly_{end.isoformat()}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    render_report(report, pdf_path)
    qa = validate_pdf(pdf_path)
    email = send_report_email(report, pdf_path)

    updated = json.loads(json.dumps(state))
    updated["version"] = 1
    updated["last_successful_run"] = retrieved_at
    updated.setdefault("processed_ids", {})
    for paper in selected:
        key = str(paper.get("id") or paper.get("doi") or paper.get("title")).lower()
        updated["processed_ids"][key] = {"title": paper.get("title"), "publication_date": paper.get("publication_date"), "report": report_path.as_posix()}
    updated.setdefault("runs", []).append({"coverage": report["coverage"], "pdf": pdf_path.as_posix(), "report": report_path.as_posix(), "papers": len(analyzed), "qa": qa, "email": email})
    updated["runs"] = updated["runs"][-104:]
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n")
    print(f"Created {pdf_path} ({qa['pages']} pages); email status: {email['status']}")


if __name__ == "__main__":
    main()

