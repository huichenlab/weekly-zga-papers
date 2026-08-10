import json

from pipeline.emailer import send_report_email
from pipeline.qa import validate_pdf
from pipeline.report_pdf import render_report
from pipeline.sources import _category, is_relevant
from pipeline.summarize import _fallback


def fixture_report():
    paper = {
        "id": "10.0000/test",
        "title": "A test of zygotic genome activation",
        "authors": "A. Author, B. Scientist",
        "journal": "Test Journal",
        "category": "review",
        "article_type": "Review",
        "publication_date": "2026-08-08",
        "doi": "10.0000/test",
        "canonical_url": "https://doi.org/10.0000/test",
        "abstract": "This review synthesizes mechanisms controlling genome activation.",
        "access_note": "Fixture abstract.",
        "source": "fixture",
    }
    analyzed = _fallback(paper)
    return {
        "coverage": {"start": "2026-08-02", "end": "2026-08-08", "query_start": "2026-08-02"},
        "retrieved_at": "2026-08-09T00:00:00Z",
        "papers": [analyzed],
        "synthesis": {
            "themes": ["Genome activation timing"],
            "methods_trends": ["Nascent RNA profiling"],
            "ranked_grant_directions": [{"rank": 1, "title": "Test timing", "rationale": "MBT access", "significance": "high", "novelty": "medium", "feasibility": "high", "risk": "medium"}],
            "why_xenopus_now": "Direct access to MBT stages.",
        },
        "source_note": "Synthetic test fixture.",
    }


def test_relevance_and_categories():
    assert is_relevant("Control of zygotic genome activation")
    assert not is_relevant("A study of adult liver metabolism")
    assert _category(["Review"], "MED") == "review"
    assert _category(["Preprint"], "PPR") == "preprint"


def test_pdf_render_and_qa(tmp_path):
    output = tmp_path / "fixture.pdf"
    render_report(fixture_report(), output)
    result = validate_pdf(output, tmp_path / "qa")
    assert result["pages"] >= 3
    assert result["bytes"] > 5_000


def test_email_without_secrets_is_pending(monkeypatch, tmp_path):
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    pdf = tmp_path / "fixture.pdf"
    pdf.write_bytes(b"%PDF fixture")
    result = send_report_email(fixture_report(), pdf)
    assert result["status"] == "pending"
    assert result["recipient"] == "huic@sc.edu"

