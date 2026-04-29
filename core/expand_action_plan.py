"""
Methods & materials narrative expansion (Haiku) — isolated from core.rag.

Keeps the Streamlit results UI from importing the heavy RAG/Chroma stack
for this single entrypoint (avoids fragile import chains on Streamlit Cloud).
"""

from __future__ import annotations

import os

from langchain_anthropic import ChatAnthropic

from core.models import ConstructProfile, VarianceReport


def _anthropic_key_for_expand() -> str | None:
    key = os.getenv("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        import streamlit as st

        key = st.secrets.get("ANTHROPIC_API_KEY")
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key
            return key
    except Exception:
        pass
    return None


def expand_action_plan_narrative(
    profile: ConstructProfile,
    report: VarianceReport,
    checklist_text: str,
) -> str:
    """
    Expand the hybrid checklist into a structured methods & materials narrative (markdown).

    Raises RuntimeError if no API key is available.
    """
    # Route through rag._build_llm() — prefers LiteLLM/OpenRouter, falls back to Anthropic
    from core.rag import _build_llm
    llm = _build_llm(temperature=0.2, max_tokens=2048)
    profile_json = profile.model_dump_json(indent=2)
    narrative = report.ai_narrative[:4000] if report.ai_narrative else ""

    ref_lines: list[str] = []
    for ref in (report.key_references or [])[:8]:
        pmid = ref.get("pmid", "")
        title = (ref.get("title") or "")[:120]
        ref_lines.append(f"- PMID {pmid}: {title}")
    if not ref_lines and report.supporting_pmids:
        ref_lines = [f"- PMID {p}" for p in report.supporting_pmids[:10]]
    refs_block = "\n".join(ref_lines) if ref_lines else "(none listed—suggest search terms, not fake PMIDs)"

    prompt = f"""You are a senior methods advisor writing for **bench scientists and lab leads**
(not for software engineers). They need to execute, source, and staff work—not debug the platform.

Use the profile, variance summary, checklist, and reference list below. Write a practical
**methods & materials plan** as markdown (## and ### headings, bullet lists).

Rules:
- Do **not** invent PMID or DOI strings. For further reading, use only PMIDs from the REFERENCE LIST
  section, or name journals/search terms if the list is thin.
- Be specific about **supplies and reagents** (categories, what to order, what needs a COA or lot tracking).
- Include **further modeling**: when FEA, lattice/CC3D-style thought experiments, or re-benchmarking
  after new measurements would save wet-lab time; state assumptions briefly.
- Name **who to involve**: imaging core, histology, mechanical testing, flow, bioinformatics, CRO types,
  co-PI skill sets—tied to this construct and readout where possible.
- If cellular agriculture context appears in the profile, mention food-grade/edible inputs where relevant.

CONSTRUCT PROFILE (JSON):
{profile_json}

VARIANCE SUMMARY (excerpt):
{narrative}

REFERENCE LIST (use these for "further reading" citations only):
{refs_block}

PRIORITIZED CHECKLIST (gaps + experimentalist anchors):
{checklist_text}

Structure your answer as:
## Supplies, reagents, and consumables
## Measurements and assays
## Further modeling and computation (when and why)
## People, cores, CROs, and collaborators
## Further reading (PMIDs from list above only, or search guidance)
## Timeline / milestones
## Risks and mitigations

Keep total length under 1100 words."""

    response = llm.invoke(prompt)
    return (response.content or "").strip()
