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
    api_key = _anthropic_key_for_expand()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    llm = ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        temperature=0.2,
        max_tokens=2048,
        api_key=api_key,
    )
    profile_json = profile.model_dump_json(indent=2)
    narrative = report.ai_narrative[:4000] if report.ai_narrative else ""

    prompt = f"""You are a tissue engineering methods advisor. The user has a construct profile,
a variance summary, and a prioritized checklist of gaps. Write a concise **methods & materials plan**
as markdown (use ## and ### headings, bullet lists).

Do not invent PMID numbers. If something is unknown, say what experiment would resolve it.

CONSTRUCT PROFILE (JSON):
{profile_json}

VARIANCE SUMMARY (excerpt):
{narrative}

PRIORITIZED CHECKLIST (from tool-derived gaps):
{checklist_text}

Structure your answer roughly as:
## Measurements and assays
## Materials and sourcing
## Sequencing and milestones
## Risks and mitigations

Keep total length under 900 words."""

    response = llm.invoke(prompt)
    return (response.content or "").strip()
