from __future__ import annotations

import json
import os
import re
from typing import Any

import requests


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


def _ollama(prompt: str) -> dict[str, Any]:
    endpoint = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    response = requests.post(
        f"{endpoint}/api/chat",
        json={
            "model": os.getenv("OLLAMA_MODEL", "qwen3:4b"),
            "messages": [
                {"role": "system", "content": "You are a rigorous developmental-biology literature analyst. Use only supplied evidence. Return JSON only."},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": "json",
            "think": False,
            "options": {"temperature": 0.1, "num_ctx": 32768, "num_predict": 6000},
        },
        timeout=int(os.getenv("OLLAMA_REQUEST_TIMEOUT", "3600")),
    )
    response.raise_for_status()
    return _extract_json(str((response.json().get("message") or {}).get("content") or ""))


def _fallback(paper: dict[str, Any]) -> dict[str, Any]:
    abstract = str(paper.get("abstract") or "No abstract was available from the authorized metadata sources.")
    is_review = paper.get("category") == "review"
    return {
        **paper,
        "main_discovery": ("Central review synthesis (manual verification required): " if is_review else "Abstract-level finding (manual verification required): ") + abstract[:1200],
        "importance_implication": "Potential relevance to ZGA/MZT is established by the title or abstract; detailed implications require inspection of the linked paper.",
        "methods": ["Methods were not reliably extractable from the available metadata."],
        "key_evidence": ["Accessible title/abstract metadata only."],
        "limitations": ["Automated fallback used; full text was not reviewed."],
        "grant_ideas": [
            {
                "title": "Test conservation of the featured mechanism at the Xenopus mid-blastula transition",
                "hypothesis": "Speculative: the featured factor or pathway changes the timing or amplitude of early zygotic transcription in Xenopus.",
                "rationale": "Early Xenopus embryos provide rapid, externally accessible perturbation of pre-MBT and MBT stages.",
                "design": "Perturb the candidate by validated CRISPR, mRNA, or rescue-controlled morpholino; assay stage-matched nascent transcription and candidate targets before and after MBT.",
                "readouts_controls": "Primary readout: nascent RNA or targeted transcript abundance. Controls: uninjected and scrambled controls, rescue, stage matching, orthogonal perturbation, and developmental morphology.",
                "support_refute": "Support: reproducible stage-specific change rescued by wild-type reagent. Refute/redirect: no molecular effect despite validated perturbation, prompting tissue-specific or combinatorial tests.",
                "novelty_feasibility_risk": "Novelty medium; feasibility medium; main risk is weak cross-species conservation.",
            }
        ],
    }


def summarize_paper(paper: dict[str, Any]) -> dict[str, Any]:
    prompt = f"""
Analyze this one ZGA/MZT paper using only the evidence packet below. Category is {paper.get('category')}.
For a review, describe the central synthesis rather than claiming a new experimental discovery.
Generate 1-3 original, falsifiable early-Xenopus laevis/tropicalis grant ideas. Each idea must name a stage/window, perturbation, assay, discriminating readout, essential controls, supporting result, refuting/redirecting result, novelty, feasibility, and risk. Do not invent unpublished data or methods absent from the evidence.

EVIDENCE:
{json.dumps(paper, ensure_ascii=False)}

Return exactly:
{{
  "main_discovery":"",
  "importance_implication":"",
  "methods":[""],
  "key_evidence":[""],
  "limitations":[""],
  "grant_ideas":[{{
    "title":"", "hypothesis":"Speculative: ...", "rationale":"", "design":"", "readouts_controls":"", "support_refute":"", "novelty_feasibility_risk":""
  }}]
}}
""".strip()
    try:
        analysis = _ollama(prompt)
        required = {"main_discovery", "importance_implication", "methods", "key_evidence", "limitations", "grant_ideas"}
        if required - set(analysis) or not (1 <= len(analysis.get("grant_ideas") or []) <= 3):
            raise ValueError("Local-model response failed schema validation")
        return {**paper, **analysis}
    except Exception as exc:
        result = _fallback(paper)
        result["limitations"].append(f"Local-model analysis failed: {type(exc).__name__}.")
        return result


def synthesize(papers: list[dict[str, Any]]) -> dict[str, Any]:
    if not papers:
        return {"themes": [], "methods_trends": [], "ranked_grant_directions": [], "why_xenopus_now": "No qualifying papers were detected."}
    compact = [
        {
            "title": paper.get("title"),
            "category": paper.get("category"),
            "main_discovery": paper.get("main_discovery"),
            "methods": paper.get("methods"),
            "grant_ideas": paper.get("grant_ideas"),
        }
        for paper in papers
    ]
    prompt = f"""
Using only these paper summaries, produce a concise cross-paper synthesis for a future early-Xenopus ZGA/MZT grant. Rank the strongest 2-4 directions by significance, novelty, feasibility, and risk. Return JSON only.
{json.dumps(compact, ensure_ascii=False)}
Schema: {{"themes":[""],"methods_trends":[""],"ranked_grant_directions":[{{"rank":1,"title":"","rationale":"","significance":"","novelty":"","feasibility":"","risk":""}}],"why_xenopus_now":""}}
""".strip()
    try:
        return _ollama(prompt)
    except Exception:
        ideas = []
        for paper in papers:
            for idea in paper.get("grant_ideas") or []:
                ideas.append(idea)
        return {
            "themes": [str(paper.get("main_discovery") or "")[:240] for paper in papers[:4]],
            "methods_trends": sorted({str(method) for paper in papers for method in (paper.get("methods") or [])})[:8],
            "ranked_grant_directions": [
                {"rank": index, "title": idea.get("title", "Xenopus ZGA study"), "rationale": idea.get("rationale", ""), "significance": "Requires expert ranking", "novelty": "Requires expert ranking", "feasibility": "Requires expert ranking", "risk": idea.get("novelty_feasibility_risk", "")}
                for index, idea in enumerate(ideas[:4], start=1)
            ],
            "why_xenopus_now": "External development, rapid perturbation, and direct access to pre-MBT/MBT stages enable fast mechanistic tests of conserved ZGA hypotheses.",
        }

