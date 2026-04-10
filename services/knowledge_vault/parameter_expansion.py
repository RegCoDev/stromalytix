#!/usr/bin/env python3
"""
Expand the parameter library by auto-extracting from methods chunks.

Scans all methods-section chunks, runs regex parameter extraction,
associates parameters with material context, and inserts novel entries
into the parameters table with source='auto_extracted'.
"""

import json
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from db import init_db
from extraction_regex import (
    PARAMETER_PATTERNS,
    extract_parameters,
    extract_materials,
    split_sentences,
)
from ingest import _load_entity_dict

# Maps parameter names to the table_name field used in the parameters table
PARAM_TABLE_MAP = {
    "stiffness": "scaffold_materials",
    "porosity": "scaffold_materials",
    "pore_size": "scaffold_materials",
    "concentration_wv": "scaffold_materials",
    "uv_dose": "scaffold_materials",
    "crosslink_time": "scaffold_materials",
    "cell_density": "proliferation",
    "viability": "proliferation",
    "temperature": "culture_conditions",
    "flow_rate": "fabrication",
    "print_speed": "fabrication",
    "nozzle_diameter": "fabrication",
    "pressure": "fabrication",
    "concentration_mg_ml": "scaffold_materials",
}


def _is_duplicate(
    conn: sqlite3.Connection,
    parameter: str,
    material: str | None,
    value: float,
) -> bool:
    """Check if a similar parameter entry already exists (10% tolerance)."""
    if material:
        rows = conn.execute(
            """SELECT id, value FROM parameters
               WHERE parameter = ? AND material = ?""",
            (parameter, material),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, value FROM parameters
               WHERE parameter = ? AND (material IS NULL OR material = '')""",
            (parameter,),
        ).fetchall()

    for row in rows:
        existing_val = row["value"]
        if existing_val is None:
            continue
        denom = max(abs(existing_val), 0.001)
        if abs(existing_val - value) / denom < 0.1:
            return True

    return False


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Auto-extract parameters from methods chunks")
    parser.add_argument("--db", type=str, default="vault.db", help="Path to vault.db")
    parser.add_argument("--limit", type=int, default=0, help="Max chunks (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="Extract but don't insert")
    args = parser.parse_args()

    print(f"[param-expand] Connecting to {args.db} ...")
    conn = init_db(args.db)
    entity_dict = _load_entity_dict()

    # Fetch methods chunks with paper metadata
    query = """
        SELECT c.id, c.text, c.paper_id, p.pmid, p.materials
        FROM chunks c
        JOIN papers p ON p.id = c.paper_id
        WHERE c.section = 'methods'
    """
    if args.limit > 0:
        query += f" LIMIT {args.limit}"

    rows = conn.execute(query).fetchall()
    total = len(rows)
    print(f"[param-expand] Found {total} methods chunks to scan")

    # Stats
    auto_counter = 0
    stats_new: dict[str, int] = {}
    stats_dup = 0
    errors: list[str] = []

    # Determine next auto_id by checking existing auto_extracted entries
    existing_auto = conn.execute(
        "SELECT COUNT(*) as cnt FROM parameters WHERE source = 'auto_extracted'"
    ).fetchone()
    auto_counter_start = existing_auto["cnt"] if existing_auto else 0
    auto_counter = auto_counter_start

    t0 = time.time()

    for i, row in enumerate(rows):
        chunk_text = row["text"]
        pmid = row["pmid"]

        sentences = split_sentences(chunk_text)

        for sentence in sentences:
            params = extract_parameters(sentence)
            if not params:
                continue

            # Extract materials for context association
            materials = extract_materials(sentence, entity_dict)
            # Primary material context (first match, or None)
            material_name = materials[0]["material_name"] if materials else None

            for p in params:
                param_name = p["parameter_name"]
                value = p["value"]
                unit = p["unit"]
                table_name = PARAM_TABLE_MAP.get(param_name, "misc")

                # Skip unreasonable values
                if value <= 0:
                    continue

                # Check for duplicates
                if _is_duplicate(conn, param_name, material_name, value):
                    stats_dup += 1
                    continue

                auto_counter += 1
                param_id = f"auto_{auto_counter:04d}"

                if not args.dry_run:
                    try:
                        conn.execute(
                            """INSERT OR IGNORE INTO parameters
                               (id, table_name, parameter, value, unit,
                                material, pmid, source, confidence, extra)
                               VALUES (?, ?, ?, ?, ?, ?, ?, 'auto_extracted', 'low', '{}')""",
                            (param_id, table_name, param_name, value, unit,
                             material_name, pmid),
                        )
                    except Exception as e:
                        errors.append(f"{param_id}: {e}")
                        continue

                stats_new[param_name] = stats_new.get(param_name, 0) + 1

        # Progress
        if (i + 1) % 100 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            added = sum(stats_new.values())
            print(f"[param-expand] {i + 1}/{total} chunks "
                  f"({rate:.1f}/s, {added} new, {stats_dup} dups)")

    if not args.dry_run:
        conn.commit()

    elapsed = time.time() - t0
    total_added = sum(stats_new.values())

    # Final report
    print("\n" + "=" * 60)
    print("PARAMETER EXPANSION COMPLETE")
    print("=" * 60)
    print(f"  Chunks scanned:      {total}")
    print(f"  New parameters:      {total_added}")
    print(f"  Duplicates skipped:  {stats_dup}")
    print(f"  Elapsed:             {elapsed:.1f}s")
    if stats_new:
        print("\n  New parameters by type:")
        for param, count in sorted(stats_new.items(), key=lambda x: -x[1]):
            table = PARAM_TABLE_MAP.get(param, "misc")
            print(f"    {param:25s}  {count:5d}  ({table})")
    if errors:
        print(f"\n  Errors ({len(errors)}):")
        for err in errors[:20]:
            print(f"    {err}")
    print()


if __name__ == "__main__":
    main()
