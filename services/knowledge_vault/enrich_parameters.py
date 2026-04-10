#!/usr/bin/env python3
"""Enrich auto-extracted parameters with conditions/context using Gemini Flash.

Reads literature parameters that have PMIDs but no conditions, finds the
source methods text in the vault, and asks Gemini to extract the experimental
context surrounding each parameter value.

Uses Gemini 2.5 Flash (free tier) via the REST API.
"""

import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY", "AIzaSyAhGYTSBSiu-HLtBs56SzcDJaDqHuqV7h0"
)
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

DB_PATH = str(Path(__file__).parent / "vault.db")
BATCH_PAUSE = 0.5  # seconds between API calls (rate limit)


def call_gemini(prompt: str, max_tokens: int = 500) -> str | None:
    """Call Gemini Flash via REST API. Returns text or None on failure."""
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.1,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        GEMINI_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")
    except Exception as e:
        print(f"  Gemini error: {e}")
    return None


def extract_context(param_row: dict, methods_text: str) -> dict | None:
    """Ask Gemini to extract experimental context for a specific parameter.

    Returns {"conditions": str, "notes": str} or None on failure.
    """
    param_name = param_row["parameter"]
    value = param_row["value"]
    unit = param_row["unit"] or ""
    material = param_row["material"] or "unknown material"

    # Truncate methods text to ~2000 chars around the value mention
    text = methods_text[:3000]

    prompt = f"""From this methods section, extract the experimental conditions for this specific measurement:

Parameter: {param_name}
Value: {value} {unit}
Material: {material}

Methods text:
{text}

Return ONLY a JSON object with two fields:
- "conditions": one line describing the experimental conditions (temperature, concentration, method, equipment). Be specific. If you can't find conditions for this exact value, return null.
- "notes": one sentence summarizing what this measurement means in context. If unclear, return null.

Example:
{{"conditions": "37°C, PBS, 5% w/v GelMA, photocrosslinked (LAP 0.05%, 405nm, 10mW/cm², 30s)", "notes": "Compressive modulus measured by unconfined compression after 24h swelling."}}

Return ONLY valid JSON, nothing else."""

    response = call_gemini(prompt)
    if not response:
        return None

    # Parse JSON from response
    response = response.strip()
    response = re.sub(r"^```json\s*", "", response)
    response = re.sub(r"\s*```$", "", response)

    try:
        result = json.loads(response)
        conditions = result.get("conditions")
        notes = result.get("notes")
        # Validate — reject if Gemini hallucinated or returned null
        if not conditions and not notes:
            return None
        return {
            "conditions": conditions or "",
            "notes": notes or "",
        }
    except (json.JSONDecodeError, TypeError):
        return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Enrich parameters with Gemini Flash")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--limit", type=int, default=0, help="Max params to process (0=all)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    # Find literature params needing enrichment
    query = """
        SELECT p.id, p.parameter, p.value, p.unit, p.material, p.pmid,
               p.conditions, p.notes
        FROM parameters p
        WHERE p.source = 'literature'
        AND (p.conditions IS NULL OR p.conditions = '')
        AND p.pmid IS NOT NULL AND p.pmid != ''
    """
    if args.limit:
        query += f" LIMIT {args.limit}"

    params = [dict(r) for r in conn.execute(query).fetchall()]
    print(f"Parameters needing enrichment: {len(params)}")

    if not params:
        print("Nothing to enrich.")
        return

    enriched = 0
    skipped = 0
    failed = 0

    for i, param in enumerate(params):
        pmid = param["pmid"]

        # Find methods text for this paper
        methods_row = conn.execute("""
            SELECT c.text FROM chunks c
            JOIN papers pa ON pa.id = c.paper_id
            WHERE pa.pmid = ? AND c.section = 'methods'
            LIMIT 1
        """, (pmid,)).fetchone()

        if not methods_row or not methods_row["text"]:
            skipped += 1
            continue

        # Call Gemini
        result = extract_context(param, methods_row["text"])

        if result and (result["conditions"] or result["notes"]):
            if not args.dry_run:
                conn.execute("""
                    UPDATE parameters
                    SET conditions = COALESCE(NULLIF(?, ''), conditions),
                        notes = COALESCE(NULLIF(?, ''), notes)
                    WHERE id = ?
                """, (result["conditions"], result["notes"], param["id"]))
                if (i + 1) % 20 == 0:
                    conn.commit()
            enriched += 1
            if (i + 1) % 10 == 0:
                print(f"  [{i+1}/{len(params)}] enriched={enriched}, skipped={skipped}, failed={failed}")
        else:
            failed += 1

        time.sleep(BATCH_PAUSE)

    conn.commit()
    conn.close()

    print(f"\n=== ENRICHMENT COMPLETE ===")
    print(f"  Processed: {len(params)}")
    print(f"  Enriched: {enriched}")
    print(f"  Skipped (no methods text): {skipped}")
    print(f"  Failed (Gemini couldn't extract): {failed}")


if __name__ == "__main__":
    main()
