"""
Knowledge Vault — Protocol Graph database operations.

CRUD layer for the protocol graph: protocols, steps, materials, cells,
parameters, and outcomes.  All functions take an explicit sqlite3.Connection
so callers control transaction scope.
"""

import json
import sqlite3
from typing import Optional

from protocol_schema import (
    Protocol,
    ProtocolStep,
    StepCell,
    StepMaterial,
    StepOutcome,
    StepParameter,
)


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

def create_protocol_tables(conn: sqlite3.Connection):
    """Create protocol graph tables. Called from db.init_db()."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS protocols (
            id INTEGER PRIMARY KEY,
            paper_id INTEGER REFERENCES papers(id),
            source_pmid TEXT,
            target_tissue TEXT,
            application_domain TEXT,
            biofab_method TEXT,
            overall_outcome TEXT,
            confidence TEXT DEFAULT 'low',
            extraction_method TEXT DEFAULT 'regex',
            extracted_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_protocols_paper_id ON protocols(paper_id);
        CREATE INDEX IF NOT EXISTS idx_protocols_tissue ON protocols(target_tissue);
        CREATE INDEX IF NOT EXISTS idx_protocols_biofab ON protocols(biofab_method);

        CREATE TABLE IF NOT EXISTS protocol_steps (
            id INTEGER PRIMARY KEY,
            protocol_id INTEGER REFERENCES protocols(id) ON DELETE CASCADE,
            seq INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            description TEXT NOT NULL,
            duration TEXT,
            temperature TEXT,
            equipment TEXT,
            conditions TEXT,
            raw_text TEXT,
            source_chunk_id INTEGER REFERENCES chunks(id)
        );
        CREATE INDEX IF NOT EXISTS idx_steps_protocol ON protocol_steps(protocol_id, seq);
        CREATE INDEX IF NOT EXISTS idx_steps_action ON protocol_steps(action_type);

        CREATE TABLE IF NOT EXISTS step_materials (
            step_id INTEGER REFERENCES protocol_steps(id) ON DELETE CASCADE,
            material_name TEXT NOT NULL,
            material_type TEXT,
            concentration TEXT,
            volume TEXT,
            PRIMARY KEY (step_id, material_name)
        );

        CREATE TABLE IF NOT EXISTS step_cells (
            step_id INTEGER REFERENCES protocol_steps(id) ON DELETE CASCADE,
            cell_type TEXT NOT NULL,
            source TEXT,
            passage TEXT,
            density TEXT,
            viability TEXT,
            PRIMARY KEY (step_id, cell_type)
        );

        CREATE TABLE IF NOT EXISTS step_parameters (
            id INTEGER PRIMARY KEY,
            step_id INTEGER REFERENCES protocol_steps(id) ON DELETE CASCADE,
            parameter_name TEXT NOT NULL,
            value REAL,
            unit TEXT,
            confidence TEXT DEFAULT 'low',
            extraction_method TEXT DEFAULT 'regex',
            source_sentence TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_step_params_name ON step_parameters(parameter_name);

        CREATE TABLE IF NOT EXISTS step_outcomes (
            id INTEGER PRIMARY KEY,
            step_id INTEGER REFERENCES protocol_steps(id) ON DELETE CASCADE,
            assay_type TEXT,
            timepoint TEXT,
            value REAL,
            unit TEXT,
            success_threshold REAL,
            comparison TEXT
        );
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Insert
# ---------------------------------------------------------------------------

def insert_protocol(conn: sqlite3.Connection, protocol: Protocol) -> int:
    """Insert a full protocol with all nested steps, materials, cells,
    parameters, and outcomes.  Returns the new protocol id."""

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
        step_id = _insert_step(conn, protocol_id, step)
        for mat in step.materials:
            _insert_material(conn, step_id, mat)
        for cell in step.cells:
            _insert_cell(conn, step_id, cell)
        for param in step.parameters:
            _insert_parameter(conn, step_id, param)
        for outcome in step.outcomes:
            _insert_outcome(conn, step_id, outcome)

    conn.commit()
    return protocol_id


def _insert_step(conn: sqlite3.Connection, protocol_id: int, step: ProtocolStep) -> int:
    cur = conn.execute(
        """INSERT INTO protocol_steps
           (protocol_id, seq, action_type, description, duration,
            temperature, equipment, conditions, raw_text)
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
    return cur.lastrowid


def _insert_material(conn: sqlite3.Connection, step_id: int, mat: StepMaterial):
    conn.execute(
        """INSERT OR IGNORE INTO step_materials
           (step_id, material_name, material_type, concentration, volume)
           VALUES (?, ?, ?, ?, ?)""",
        (step_id, mat.material_name, mat.material_type, mat.concentration, mat.volume),
    )


def _insert_cell(conn: sqlite3.Connection, step_id: int, cell: StepCell):
    conn.execute(
        """INSERT OR IGNORE INTO step_cells
           (step_id, cell_type, source, passage, density, viability)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (step_id, cell.cell_type, cell.source, cell.passage, cell.density, cell.viability),
    )


def _insert_parameter(conn: sqlite3.Connection, step_id: int, param: StepParameter):
    conn.execute(
        """INSERT INTO step_parameters
           (step_id, parameter_name, value, unit, confidence,
            extraction_method, source_sentence)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            step_id,
            param.parameter_name,
            param.value,
            param.unit,
            param.confidence,
            param.extraction_method,
            param.source_sentence,
        ),
    )


def _insert_outcome(conn: sqlite3.Connection, step_id: int, outcome: StepOutcome):
    conn.execute(
        """INSERT INTO step_outcomes
           (step_id, assay_type, timepoint, value, unit,
            success_threshold, comparison)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            step_id,
            outcome.assay_type,
            outcome.timepoint,
            outcome.value,
            outcome.unit,
            outcome.success_threshold,
            outcome.comparison,
        ),
    )


# ---------------------------------------------------------------------------
# Read — single protocol (full graph)
# ---------------------------------------------------------------------------

def get_protocol(conn: sqlite3.Connection, protocol_id: int) -> Optional[Protocol]:
    """Load a full protocol with all nested steps, materials, cells,
    parameters, and outcomes.  Returns None if the protocol does not exist."""

    row = conn.execute(
        "SELECT * FROM protocols WHERE id = ?", (protocol_id,)
    ).fetchone()
    if row is None:
        return None

    protocol = Protocol(
        id=row["id"],
        paper_id=row["paper_id"],
        source_pmid=row["source_pmid"],
        target_tissue=row["target_tissue"],
        application_domain=row["application_domain"],
        biofab_method=row["biofab_method"],
        overall_outcome=row["overall_outcome"],
        confidence=row["confidence"],
        extraction_method=row["extraction_method"],
    )

    step_rows = conn.execute(
        "SELECT * FROM protocol_steps WHERE protocol_id = ? ORDER BY seq",
        (protocol_id,),
    ).fetchall()

    for sr in step_rows:
        step = ProtocolStep(
            id=sr["id"],
            seq=sr["seq"],
            action_type=sr["action_type"],
            description=sr["description"],
            duration=sr["duration"],
            temperature=sr["temperature"],
            equipment=sr["equipment"],
            conditions=json.loads(sr["conditions"]) if sr["conditions"] else None,
            raw_text=sr["raw_text"],
        )

        # Materials
        step.materials = [
            StepMaterial(
                material_name=m["material_name"],
                material_type=m["material_type"],
                concentration=m["concentration"],
                volume=m["volume"],
            )
            for m in conn.execute(
                "SELECT * FROM step_materials WHERE step_id = ?", (sr["id"],)
            ).fetchall()
        ]

        # Cells
        step.cells = [
            StepCell(
                cell_type=c["cell_type"],
                source=c["source"],
                passage=c["passage"],
                density=c["density"],
                viability=c["viability"],
            )
            for c in conn.execute(
                "SELECT * FROM step_cells WHERE step_id = ?", (sr["id"],)
            ).fetchall()
        ]

        # Parameters
        step.parameters = [
            StepParameter(
                parameter_name=p["parameter_name"],
                value=p["value"],
                unit=p["unit"],
                confidence=p["confidence"],
                extraction_method=p["extraction_method"],
                source_sentence=p["source_sentence"],
            )
            for p in conn.execute(
                "SELECT * FROM step_parameters WHERE step_id = ?", (sr["id"],)
            ).fetchall()
        ]

        # Outcomes
        step.outcomes = [
            StepOutcome(
                assay_type=o["assay_type"],
                timepoint=o["timepoint"],
                value=o["value"],
                unit=o["unit"],
                success_threshold=o["success_threshold"],
                comparison=o["comparison"],
            )
            for o in conn.execute(
                "SELECT * FROM step_outcomes WHERE step_id = ?", (sr["id"],)
            ).fetchall()
        ]

        protocol.steps.append(step)

    return protocol


# ---------------------------------------------------------------------------
# Query — filtered list
# ---------------------------------------------------------------------------

def query_protocols(
    conn: sqlite3.Connection,
    tissue_type: Optional[str] = None,
    biofab_method: Optional[str] = None,
    material: Optional[str] = None,
    cell_type: Optional[str] = None,
    confidence: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return a filtered list of protocol summaries and total count.

    When *material* or *cell_type* is supplied, the query JOINs into
    step_materials / step_cells respectively (DISTINCT on protocol id).
    """

    select = """
        SELECT DISTINCT p.id, p.source_pmid, pa.title AS paper_title,
               p.target_tissue, p.biofab_method, p.confidence,
               p.extraction_method,
               (SELECT COUNT(*) FROM protocol_steps ps WHERE ps.protocol_id = p.id) AS step_count
        FROM protocols p
        LEFT JOIN papers pa ON pa.id = p.paper_id
    """
    count_select = """
        SELECT COUNT(DISTINCT p.id)
        FROM protocols p
        LEFT JOIN papers pa ON pa.id = p.paper_id
    """

    joins = []
    wheres = []
    params = []

    if material:
        joins.append(
            "JOIN protocol_steps ps_m ON ps_m.protocol_id = p.id "
            "JOIN step_materials sm ON sm.step_id = ps_m.id"
        )
        wheres.append("LOWER(sm.material_name) LIKE ?")
        params.append(f"%{material.lower()}%")

    if cell_type:
        joins.append(
            "JOIN protocol_steps ps_c ON ps_c.protocol_id = p.id "
            "JOIN step_cells sc ON sc.step_id = ps_c.id"
        )
        wheres.append("LOWER(sc.cell_type) LIKE ?")
        params.append(f"%{cell_type.lower()}%")

    if tissue_type:
        wheres.append("LOWER(p.target_tissue) LIKE ?")
        params.append(f"%{tissue_type.lower()}%")

    if biofab_method:
        wheres.append("LOWER(p.biofab_method) LIKE ?")
        params.append(f"%{biofab_method.lower()}%")

    if confidence:
        wheres.append("p.confidence = ?")
        params.append(confidence)

    join_clause = " ".join(joins)
    where_clause = (" WHERE " + " AND ".join(wheres)) if wheres else ""

    total = conn.execute(
        count_select + join_clause + where_clause, params
    ).fetchone()[0]

    rows = conn.execute(
        select + join_clause + where_clause + " ORDER BY p.id DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()

    results = [
        {
            "id": r["id"],
            "source_pmid": r["source_pmid"],
            "paper_title": r["paper_title"],
            "target_tissue": r["target_tissue"],
            "biofab_method": r["biofab_method"],
            "confidence": r["confidence"],
            "step_count": r["step_count"],
            "extraction_method": r["extraction_method"],
        }
        for r in rows
    ]
    return results, total


# ---------------------------------------------------------------------------
# Match — similarity scoring
# ---------------------------------------------------------------------------

def match_protocols(
    conn: sqlite3.Connection,
    scaffold_material: Optional[str] = None,
    cell_types: Optional[list[str]] = None,
    target_tissue: Optional[str] = None,
    biofab_method: Optional[str] = None,
    stiffness_kpa: Optional[float] = None,
) -> list[dict]:
    """Score each protocol against the provided criteria.

    Score = (number of matching fields) / (number of fields provided).
    Only protocols with score > 0 are returned, sorted descending.
    """

    # Count how many fields were actually provided
    fields_provided = sum([
        scaffold_material is not None,
        cell_types is not None and len(cell_types) > 0,
        target_tissue is not None,
        biofab_method is not None,
        stiffness_kpa is not None,
    ])
    if fields_provided == 0:
        return []

    # Fetch all protocols with paper title
    rows = conn.execute("""
        SELECT p.id, p.source_pmid, pa.title AS paper_title,
               p.target_tissue, p.biofab_method
        FROM protocols p
        LEFT JOIN papers pa ON pa.id = p.paper_id
    """).fetchall()

    # Pre-load materials, cells, and stiffness parameters per protocol
    proto_materials: dict[int, set[str]] = {}
    proto_cells: dict[int, set[str]] = {}
    proto_stiffness: dict[int, list[float]] = {}

    for r in conn.execute("""
        SELECT ps.protocol_id, LOWER(sm.material_name) AS mat
        FROM protocol_steps ps
        JOIN step_materials sm ON sm.step_id = ps.id
    """).fetchall():
        proto_materials.setdefault(r["protocol_id"], set()).add(r["mat"])

    for r in conn.execute("""
        SELECT ps.protocol_id, LOWER(sc.cell_type) AS ct
        FROM protocol_steps ps
        JOIN step_cells sc ON sc.step_id = ps.id
    """).fetchall():
        proto_cells.setdefault(r["protocol_id"], set()).add(r["ct"])

    if stiffness_kpa is not None:
        for r in conn.execute("""
            SELECT ps.protocol_id, sp.value
            FROM protocol_steps ps
            JOIN step_parameters sp ON sp.step_id = ps.id
            WHERE LOWER(sp.parameter_name) IN ('stiffness', 'elastic_modulus',
                  'young_modulus', 'storage_modulus', 'compressive_modulus')
                  AND sp.unit LIKE '%kpa%' AND sp.value IS NOT NULL
        """).fetchall():
            proto_stiffness.setdefault(r["protocol_id"], []).append(r["value"])

    results = []
    for row in rows:
        pid = row["id"]
        score = 0.0
        matching = []

        if scaffold_material is not None:
            mats = proto_materials.get(pid, set())
            if any(scaffold_material.lower() in m for m in mats):
                score += 1.0
                matching.append("scaffold_material")

        if cell_types is not None and len(cell_types) > 0:
            cells = proto_cells.get(pid, set())
            matched_any = any(
                ct.lower() in c for ct in cell_types for c in cells
            )
            if matched_any:
                score += 1.0
                matching.append("cell_types")

        if target_tissue is not None:
            if row["target_tissue"] and target_tissue.lower() in row["target_tissue"].lower():
                score += 1.0
                matching.append("target_tissue")

        if biofab_method is not None:
            if row["biofab_method"] and biofab_method.lower() in row["biofab_method"].lower():
                score += 1.0
                matching.append("biofab_method")

        if stiffness_kpa is not None:
            values = proto_stiffness.get(pid, [])
            if values:
                # Score based on proximity: 1.0 if within 20%, decaying
                closest = min(values, key=lambda v: abs(v - stiffness_kpa))
                ratio = abs(closest - stiffness_kpa) / max(stiffness_kpa, 0.01)
                if ratio < 1.0:
                    score += max(0.0, 1.0 - ratio)
                    matching.append("stiffness_kpa")

        if score > 0:
            results.append({
                "protocol_id": pid,
                "source_pmid": row["source_pmid"],
                "paper_title": row["paper_title"],
                "similarity_score": round(score / fields_provided, 4),
                "matching_fields": matching,
            })

    results.sort(key=lambda r: r["similarity_score"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_protocol_stats(conn: sqlite3.Connection) -> dict:
    """Aggregate counts across the protocol graph."""

    total_protocols = conn.execute("SELECT COUNT(*) FROM protocols").fetchone()[0]
    total_steps = conn.execute("SELECT COUNT(*) FROM protocol_steps").fetchone()[0]
    total_step_params = conn.execute("SELECT COUNT(*) FROM step_parameters").fetchone()[0]

    def _group_counts(sql: str) -> dict[str, int]:
        return {
            row[0] or "unknown": row[1]
            for row in conn.execute(sql).fetchall()
        }

    by_tissue = _group_counts(
        "SELECT target_tissue, COUNT(*) FROM protocols GROUP BY target_tissue"
    )
    by_biofab = _group_counts(
        "SELECT biofab_method, COUNT(*) FROM protocols GROUP BY biofab_method"
    )
    by_action = _group_counts(
        "SELECT action_type, COUNT(*) FROM protocol_steps GROUP BY action_type"
    )
    by_confidence = _group_counts(
        "SELECT confidence, COUNT(*) FROM protocols GROUP BY confidence"
    )
    by_extraction = _group_counts(
        "SELECT extraction_method, COUNT(*) FROM protocols GROUP BY extraction_method"
    )

    return {
        "total_protocols": total_protocols,
        "total_steps": total_steps,
        "total_step_parameters": total_step_params,
        "by_tissue": by_tissue,
        "by_biofab": by_biofab,
        "by_action_type": by_action,
        "by_confidence": by_confidence,
        "by_extraction_method": by_extraction,
    }
