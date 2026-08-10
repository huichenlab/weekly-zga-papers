from __future__ import annotations

import datetime as dt
import html
import re
from typing import Any

import requests


SEARCH_PHRASES = (
    "zygotic genome activation",
    "embryonic genome activation",
    "maternal-to-zygotic transition",
    "maternal zygotic transition",
    "maternal RNA clearance",
)

EXCLUDED_TITLE_TERMS = (
    "correction",
    "retraction",
    "editorial",
    "news and views",
    "news & views",
)


def clean_markup(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def is_relevant(title: str, abstract: str = "") -> bool:
    text = f"{title} {abstract}".lower()
    if any(term in title.lower() for term in EXCLUDED_TITLE_TERMS):
        return False
    exact = any(phrase.lower() in text for phrase in SEARCH_PHRASES)
    concepts = (
        all(word in text for word in ("zygotic", "genome", "activation")),
        all(word in text for word in ("maternal", "zygotic", "transition")),
        all(word in text for word in ("embryonic", "genome", "activation")),
        all(word in text for word in ("maternal", "rna", "clearance")),
    )
    return exact or any(concepts)


def _category(pub_types: list[str], source: str) -> str:
    joined = " ".join(pub_types).lower()
    if source.lower() in {"ppr", "biorxiv", "medrxiv"} or "preprint" in joined:
        return "preprint"
    if "review" in joined or "systematic review" in joined or "meta-analysis" in joined:
        return "review"
    return "research"


def _date_from_parts(item: dict[str, Any]) -> str:
    for key in ("published-online", "published-print", "published", "issued", "created"):
        parts = ((item.get(key) or {}).get("date-parts") or [[]])[0]
        if parts:
            year = int(parts[0])
            month = int(parts[1]) if len(parts) > 1 else 1
            day = int(parts[2]) if len(parts) > 2 else 1
            return dt.date(year, month, day).isoformat()
    return ""


def _crossref_authors(item: dict[str, Any]) -> str:
    names = []
    for author in item.get("author") or []:
        name = " ".join(part for part in (author.get("given"), author.get("family")) if part)
        if name:
            names.append(name)
    return ", ".join(names[:12]) + (", et al." if len(names) > 12 else "")


def fetch_europe_pmc(start: dt.date, end: dt.date, session: requests.Session) -> list[dict[str, Any]]:
    concept_query = " OR ".join(f'TITLE_ABS:\"{phrase}\"' for phrase in SEARCH_PHRASES)
    query = f"({concept_query}) AND FIRST_PDATE:[{start.isoformat()} TO {end.isoformat()}]"
    response = session.get(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        params={"query": query, "format": "json", "pageSize": 1000, "resultType": "core"},
        timeout=90,
    )
    response.raise_for_status()
    papers: list[dict[str, Any]] = []
    for item in response.json().get("resultList", {}).get("result", []):
        title = clean_markup(str(item.get("title") or ""))
        abstract = clean_markup(str(item.get("abstractText") or ""))
        if not title or not is_relevant(title, abstract):
            continue
        pub_types = list((item.get("pubTypeList") or {}).get("pubType") or [])
        source = str(item.get("source") or "Europe PMC")
        doi = str(item.get("doi") or "").strip()
        persistent_id = doi or str(item.get("pmcid") or item.get("pmid") or item.get("id") or "")
        papers.append(
            {
                "id": persistent_id.lower(),
                "title": title,
                "authors": str(item.get("authorString") or ""),
                "journal": str(item.get("journalTitle") or source),
                "category": _category(pub_types, source),
                "article_type": ", ".join(pub_types) or "unspecified",
                "publication_date": str(item.get("firstPublicationDate") or "")[:10],
                "doi": doi,
                "canonical_url": f"https://doi.org/{doi}" if doi else f"https://europepmc.org/article/{source}/{item.get('id')}",
                "abstract": abstract,
                "access_note": "Europe PMC abstract/metadata; full text not assumed.",
                "source": "Europe PMC",
            }
        )
    return papers


def fetch_crossref(start: dt.date, end: dt.date, session: requests.Session) -> list[dict[str, Any]]:
    papers: list[dict[str, Any]] = []
    headers = {"User-Agent": "weekly-zga-papers/1.0 (https://github.com/huichenlab/weekly-zga-papers)"}
    for phrase in SEARCH_PHRASES:
        response = session.get(
            "https://api.crossref.org/works",
            params={
                "query.bibliographic": phrase,
                "filter": f"from-pub-date:{start.isoformat()},until-pub-date:{end.isoformat()}",
                "rows": 100,
                "sort": "published",
                "order": "desc",
            },
            headers=headers,
            timeout=90,
        )
        response.raise_for_status()
        for item in response.json().get("message", {}).get("items", []):
            title = clean_markup(" ".join(item.get("title") or []))
            abstract = clean_markup(str(item.get("abstract") or ""))
            if not title or not is_relevant(title, abstract):
                continue
            doi = str(item.get("DOI") or "").strip()
            sub_type = str(item.get("subtype") or item.get("type") or "journal-article")
            category = "preprint" if item.get("type") == "posted-content" else ("review" if "review" in sub_type.lower() else "research")
            papers.append(
                {
                    "id": (doi or title).lower(),
                    "title": title,
                    "authors": _crossref_authors(item),
                    "journal": " ".join(item.get("container-title") or []) or str(item.get("publisher") or "Crossref"),
                    "category": category,
                    "article_type": sub_type,
                    "publication_date": _date_from_parts(item),
                    "doi": doi,
                    "canonical_url": str(item.get("URL") or (f"https://doi.org/{doi}" if doi else "")),
                    "abstract": abstract,
                    "access_note": "Crossref publisher-deposited metadata/abstract; full text not assumed.",
                    "source": "Crossref",
                }
            )
    return papers


def fetch_weekly_papers(start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    session = requests.Session()
    candidates: list[dict[str, Any]] = []
    errors: list[str] = []
    for label, fetcher in (("Europe PMC", fetch_europe_pmc), ("Crossref", fetch_crossref)):
        try:
            candidates.extend(fetcher(start, end, session))
        except requests.RequestException as exc:
            errors.append(f"{label}: {type(exc).__name__}: {exc}")
    if not candidates and errors:
        raise RuntimeError("All literature sources failed: " + " | ".join(errors))

    merged: dict[str, dict[str, Any]] = {}
    for paper in candidates:
        key = str(paper.get("doi") or paper.get("id") or paper.get("title")).lower().strip()
        if not key:
            continue
        existing = merged.get(key)
        if not existing or len(str(paper.get("abstract") or "")) > len(str(existing.get("abstract") or "")):
            merged[key] = paper
    return sorted(merged.values(), key=lambda item: (item.get("publication_date", ""), item.get("title", "")))
