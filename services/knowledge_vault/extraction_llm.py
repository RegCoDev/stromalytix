"""
Knowledge Vault — LLM-based protocol extraction engine (Tier 2).

Uses Anthropic API (Claude Haiku) to extract structured protocols from
methods text.  Only called when Tier 1 regex completeness_score < threshold.
"""

import json
import os
import re
from typing import Optional


def extract_protocol_llm(
    chunk_text: str,
    paper_metadata: dict,
) -> Optional[dict]:
    """Extract protocol from methods text using Claude Haiku.

    Returns same structure as extract_protocol_regex, or None on failure.
    Requires ANTHROPIC_API_KEY in environment.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    prompt = _build_prompt(chunk_text)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except ImportError:
        # SDK not installed — fall back to raw httpx
        return _extract_via_httpx(chunk_text, paper_metadata, api_key)

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        json_str = response.content[0].text.strip()
        result = _parse_json_response(json_str)
        if result is None:
            return None

        result["completeness_score"] = 0.9  # LLM extraction assumed high quality
        return result

    except Exception as e:
        print(f"LLM extraction failed: {e}")
        return None


def _extract_via_httpx(
    chunk_text: str,
    paper_metadata: dict,
    api_key: str,
) -> Optional[dict]:
    """Fallback: call Anthropic API directly via httpx (no SDK needed)."""
    try:
        import httpx
    except ImportError:
        print("LLM extraction unavailable: neither anthropic SDK nor httpx installed")
        return None

    prompt = _build_prompt(chunk_text)

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()

        json_str = data["content"][0]["text"].strip()
        result = _parse_json_response(json_str)
        if result is None:
            return None

        result["completeness_score"] = 0.9
        return result

    except Exception as e:
        print(f"LLM extraction (httpx) failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_prompt(chunk_text: str) -> str:
    """Build the extraction prompt, capping text to 3000 chars."""
    return f"""Extract a structured laboratory protocol from this methods section text.

Return ONLY valid JSON with this structure:
{{
  "protocol": {{
    "target_tissue": "tissue type or null",
    "biofab_method": "fabrication method or null",
    "overall_outcome": "brief outcome or null"
  }},
  "steps": [
    {{
      "seq": 1,
      "action_type": "cell_sourcing|cell_expansion|material_prep|crosslinking|fabrication|cell_seeding|culture|assay",
      "description": "Brief description of what was done",
      "duration": "e.g. 24 h",
      "temperature": "e.g. 37°C",
      "equipment": "equipment used or null",
      "materials": [{{"name": "material", "concentration": "5% w/v"}}],
      "cells": [{{"cell_type": "type", "density": "1e6/mL"}}],
      "parameters": [{{"name": "stiffness", "value": 10.0, "unit": "kPa"}}]
    }}
  ]
}}

Methods text:
{chunk_text[:3000]}

Return ONLY valid JSON, no other text."""


def _parse_json_response(json_str: str) -> Optional[dict]:
    """Parse JSON from an LLM response, stripping markdown fences."""
    # Remove markdown code block wrappers
    json_str = re.sub(r'^```json\s*', '', json_str)
    json_str = re.sub(r'\s*```$', '', json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"LLM returned invalid JSON: {e}")
        return None
