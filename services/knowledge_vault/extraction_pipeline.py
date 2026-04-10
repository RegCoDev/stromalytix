#!/usr/bin/env python3
"""
Protocol extraction pipeline.

Reads methods chunks from vault.db, runs Tier 1 (regex) and optionally
Tier 2 (LLM) extraction, and populates the protocol graph tables.
"""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from db import init_db
from ingest import _load_entity_dict
from extraction_regex import extract_protocol_regex
from extraction_llm import extract_protocol_llm
from protocol_schema import (
    Protocol, ProtocolStep, StepMaterial, StepCell, StepParameter,
)


# ---------------------------------------------------------------------------
# Protocol DB helpers (inline — no separate module needed)
# ---------------------------------------------------------------------------

def _ensure_protocol_tables(conn: sqlite3.Connection) -> None:
    """Create protocol graph tables if they do not exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS protocols (
            id                INTEGER PRIMARY KEY,
            paper_id          INTEGER REFERENCES papers(id) ON DELETE CASCADE,
            source_pmid       TEXT,
            target_tissue     TEXT,
            application_domain TEXT,
            biofab_method     TEXT,
            overall_outcome   TEXT,
            confidence        TEXT NOT NULL DEFAULT 'low',
            extraction_method TEXT NOT NULL DEFAULT 'regex',
            created_at        TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_protocols_paper ON protocols(paper_id);
        CREATE INDEX IF NOT EXISTS idx_protocols_pmid ON protocols(source_pmid);

        CREATE TABLE IF NOT EXISTS protocol_steps (
            id              INTEGER PRIMARY KEY,
            protocol_id     INTEGER NOT NULL REFERENCES protocols(id) ON DELETE CASCADE,
            seq             INTEGER NOT NULL,
            action_type     TEXT NOT NULL,
            description     TEXT NOT NULL,
            duration        TEXT,
            temperature     TEXT,
            equipment       TEXT,
            conditions      TEXT,
            raw_text        TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_steps_protocol ON protocol_steps(protocol_id);

        CREATE TABLE IF NOT EXISTS step_materials (
            id            INTEGER PRIMARY KEY,
            step_id       INTEGER NOT NULL REFERENCES protocol_steps(id) ON DELETE CASCADE,
            material_name TEXT NOT NULL,
            material_type TEXT,
            concentration TEXT,
            volume        TEXT
        );

        CREATE TABLE IF NOT EXISTS step_cells (
            id        INTEGER PRIMARY KEY,
            step_id   INTEGER NOT NULL REFERENCES protocol_steps(id) ON DELETE CASCADE,
            cell_type TEXT NOT NULL,
            source    TEXT,
            passage   TEXT,
            density   TEXT,
            viability TEXT
        );

        CREATE TABLE IF NOT EXISTS step_parameters (
            id                INTEGER PRIMARY KEY,
            step_id           INTEGER NOT NULL REFERENCES protocol_steps(id) ON DELETE CASCADE,
            parameter_name    TEXT NOT NULL,
            value             REAL,
            unit              TEXT,
            confidence        TEXT DEFAULT 'low',
            extraction_method TEXT DEFAULT 'regex',
            source_sentence   TEXT
        );
    """)
    conn.commit()


def insert_protocol(conn: sqlite3.Connection, protocol: Protocol) -> int:
    """Insert a Protocol (with steps and sub-entities) into the DB.

    Returns the protocol row id.
    """
    cur = conn.execute(
        """INSERT INTO protocols
           (paper_id, source_pmid, target_tissue, application_domain,
            biofab_method, overall_outcome, confidence, extraction_method)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            protocol.paper_id,
            protocol.source_pmid,
            protocol.target_tissue,
            protocol.application_domain,
            protocol.biofab_method,
            protocol.overall_outcome,
            protocol.confidence,
            protocol.extraction_method,
        ),
    )
    protocol_id = cur.lastrowid

    for step in protocol.steps:
        step_cur = conn.execute(
            """INSERT INTO protocol_steps
               (protocol_id, seq, action_type, description,
                duration, temperature, equipment, conditions, raw_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                protocol_id,
                step.seq,
                step.action_type,
                step.description,
                step.duration,
                step.temperature,
                step.equipment,
                json.dumps(step.conditions) if step.conditions else None,
                step.raw_text,
            ),
        )
        step_id = step_cur.lastrowid

        for mat in step.materials:
            conn.execute(
                """INSERT INTO step_materials
                   (step_id, material_name, material_type, concentration, volume)
                   VALUES (?, ?, ?, ?, ?)""",
                (step_id, mat.material_name, mat.material_type,
                 mat.concentration, mat.volume),
            )

        for cell in step.cells:
            conn.execute(
                """INSERT INTO step_cells
                   (step_id, cell_type, source, passage, density, viability)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (step_id, cell.cell_type, cell.source, cell.passage,
                 cell.density, cell.viability),
            )

        for param in step.parameters:
            conn.execute(
                """INSERT INTO step_parameters
                   (step_id, parameter_name, value, unit, confidence,
                    extraction_method, source_sentence)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (step_id, param.parameter_name, param.value, param.unit,
                 param.confidence, param.extraction_method,
                 param.source_sentence),
            )

    conn.commit()
    return protocol_id


# ---------------------------------------------------------------------------
# Result → Protocol model conversion
# ---------------------------------------------------------------------------

def _result_to_protocol(
    result: dict,
    paper_id: int,
    pmid: str,
    paper_meta: dict,
    extraction_method: str,
) -> Protocol:
    """Convert an extraction result dict into a Protocol pydantic model."""
    proto_data = result.get("protocol", {})
    completeness = result.get("completeness_score", 0.0)

    # Map completeness to confidence label
    if completeness >= 0.7:
        confidence = "high"
    elif completeness >= 0.4:
        confidence = "medium"
    else:
        confidence = "low"

    steps: list[ProtocolStep] = []
    for step_dict in result.get("steps", []):
        materials = [
            StepMaterial(
                material_name=m.get("name", m.get("material_name", "")),
                concentration=m.get("concentration"),
            )
            for m in step_dict.get("materials", [])
        ]
        cells = [
            StepCell(
                cell_type=c.get("cell_type", ""),
                density=c.get("density"),
            )
            for c in step_dict.get("cells", [])
        ]
        parameters = [
            StepParameter(
                parameter_name=p.get("name", p.get("parameter_name", "")),
                value=p.get("value"),
                unit=p.get("unit"),
                extraction_method=extraction_method,
                source_sentence=p.get("source_sentence"),
            )
            for p in step_dict.get("parameters", [])
        ]

        steps.append(ProtocolStep(
            seq=step_dict.get("seq", 0),
            action_type=step_dict.get("action_type", "unknown"),
            description=step_dict.get("description", ""),
            duration=step_dict.get("duration"),
            temperature=step_dict.get("temperature"),
            equipment=step_dict.get("equipment"),
            raw_text=step_dict.get("raw_text"),
            materials=materials,
            cells=cells,
            parameters=parameters,
        ))

    return Protocol(
        paper_id=paper_id,
        source_pmid=pmid,
        target_tissue=proto_data.get("target_tissue") or paper_meta.get("target_tissue"),
        biofab_method=proto_data.get("biofab_method") or paper_meta.get("biofab_method"),
        overall_outcome=proto_data.get("overall_outcome"),
        confidence=confidence,
        extraction_method=extraction_method,
        steps=steps,
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Extract protocols from methods chunks")
    parser.add_argument("--tier", choices=["regex", "llm", "both"], default="regex")
    parser.add_argument(
        "--confidence-threshold", type=float, default=0.4,
        help="Run LLM on chunks with regex completeness below this",
    )
    parser.add_argument("--limit", type=int, default=0, help="Max chunks to process (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="Extract but don't insert")
    parser.add_argument("--db", type=str, default="vault.db", help="Path to vault.db")
    args = parser.parse_args()

    print(f"[pipeline] Connecting to {args.db} ...")
    conn = init_db(args.db)
    _ensure_protocol_tables(conn)

    entity_dict = _load_entity_dict()

    # Fetch methods chunks
    query = """
        SELECT c.id, c.text, c.paper_id, p.pmid,
               p.tissue_type AS target_tissue,
               p.biofab_method,
               p.materials,
               p.cell_types
        FROM chunks c
        JOIN papers p ON p.id = c.paper_id
        WHERE c.section = 'methods'
    """
    if args.limit > 0:
        query += f" LIMIT {args.limit}"

    rows = conn.execute(query).fetchall()
    total = len(rows)
    print(f"[pipeline] Found {total} methods chunks to process")

    # Stats
    stats = {
        "processed": 0,
        "skipped_existing": 0,
        "inserted": 0,
        "llm_fallback": 0,
        "total_steps": 0,
        "total_params": 0,
        "by_action_type": {},
        "errors": [],
    }

    t0 = time.time()

    for i, row in enumerate(rows):
        chunk_id = row["id"]
        paper_id = row["paper_id"]
        pmid = row["pmid"]
        text = row["text"]
        paper_meta = {
            "target_tissue": row["target_tissue"],
            "biofab_method": row["biofab_method"],
            "materials": row["materials"],
            "cell_types": row["cell_types"],
        }

        # Deduplication: skip if this paper already has a protocol
        existing = conn.execute(
            "SELECT id FROM protocols WHERE paper_id = ?", (paper_id,)
        ).fetchone()
        if existing:
            stats["skipped_existing"] += 1
            continue

        # Tier 1: regex
        extraction_method = "regex"
        try:
            result = extract_protocol_regex(text, paper_meta, entity_dict)
        except Exception as e:
            stats["errors"].append(f"chunk {chunk_id} (PMID {pmid}): regex failed: {e}")
            continue

        completeness = result.get("completeness_score", 0.0)

        # Tier 2: LLM fallback if completeness below threshold
        if completeness < args.confidence_threshold and args.tier in ("llm", "both"):
            llm_result = extract_protocol_llm(text, paper_meta)
            if llm_result is not None:
                result = llm_result
                extraction_method = "llm"
                stats["llm_fallback"] += 1

        # Build Protocol model
        protocol = _result_to_protocol(
            result, paper_id, pmid, paper_meta, extraction_method,
        )

        # Skip empty protocols
        if not protocol.steps:
            stats["processed"] += 1
            continue

        # Insert (unless dry-run)
        if not args.dry_run:
            try:
                insert_protocol(conn, protocol)
                stats["inserted"] += 1
            except Exception as e:
                stats["errors"].append(f"chunk {chunk_id} (PMID {pmid}): insert failed: {e}")
                continue
        else:
            stats["inserted"] += 1

        # Count steps and params
        for step in protocol.steps:
            stats["total_steps"] += 1
            stats["total_params"] += len(step.parameters)
            at = step.action_type
            stats["by_action_type"][at] = stats["by_action_type"].get(at, 0) + 1

        stats["processed"] += 1

        # Progress
        if (i + 1) % 100 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            print(f"[pipeline] {i + 1}/{total} chunks processed "
                  f"({rate:.1f} chunks/s, {stats['inserted']} protocols inserted)")

    elapsed = time.time() - t0

    # Final report
    print("\n" + "=" * 60)
    print("EXTRACTION PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Total chunks:        {total}")
    print(f"  Processed:           {stats['processed']}")
    print(f"  Skipped (existing):  {stats['skipped_existing']}")
    print(f"  Protocols inserted:  {stats['inserted']}")
    print(f"  LLM fallbacks:       {stats['llm_fallback']}")
    print(f"  Total steps:         {stats['total_steps']}")
    print(f"  Total parameters:    {stats['total_params']}")
    print(f"  Elapsed:             {elapsed:.1f}s")
    if stats["by_action_type"]:
        print("\n  Steps by action type:")
        for at, count in sorted(stats["by_action_type"].items(), key=lambda x: -x[1]):
            print(f"    {at:20s}  {count}")
    if stats["errors"]:
        print(f"\n  Errors ({len(stats['errors'])}):")
        for err in stats["errors"][:20]:
            print(f"    {err}")
    print()


if __name__ == "__main__":
    main()
