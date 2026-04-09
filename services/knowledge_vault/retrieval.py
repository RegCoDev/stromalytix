"""
Hybrid retrieval engine for the Stromalytix Knowledge Vault.

Combines BM25 (FTS5) + vector (sqlite-vss) search with Reciprocal Rank Fusion,
optional cross-encoder reranking, and structured parameter lookup.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Optional

from schema import ChunkResult, PaperInfo, ParameterResult

# ---------------------------------------------------------------------------
# Cross-encoder singleton (lazy-loaded)
# ---------------------------------------------------------------------------

_cross_encoder = None


def _get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder

        _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _cross_encoder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize_fts_query(text: str) -> str:
    """Strip FTS5 operators and wrap remaining terms in double quotes."""
    # Remove FTS5 special characters and operators
    text = re.sub(r'[*"()\[\]{}^~]', " ", text)
    # Remove FTS5 boolean keywords (whole-word only)
    text = re.sub(r"\b(NEAR|NOT|OR|AND)\b", " ", text, flags=re.IGNORECASE)
    # Collapse whitespace and split into terms
    terms = text.split()
    if not terms:
        return ""
    # Wrap each term in double quotes for phrase safety
    return " ".join(f'"{t}"' for t in terms if t.strip())


def _build_filter_clause(
    filters: dict | None,
) -> tuple[str, list]:
    """Build SQL WHERE clause fragments from a filters dict.

    Returns (clause_string, params_list).  clause_string already includes
    leading ``AND`` for each predicate so it can be appended directly after
    an existing WHERE.
    """
    if not filters:
        return ("", [])

    parts: list[str] = []
    params: list = []

    # materials: list[str] — JSON containment via LIKE
    if "materials" in filters and filters["materials"]:
        for mat in filters["materials"]:
            parts.append("papers.materials LIKE ?")
            params.append(f'%"{mat}"%')

    # tissue_type: str
    if "tissue_type" in filters and filters["tissue_type"]:
        parts.append("papers.tissue_type = ?")
        params.append(filters["tissue_type"])

    # year_min: int
    if "year_min" in filters and filters["year_min"] is not None:
        parts.append("papers.year >= ?")
        params.append(int(filters["year_min"]))

    # sections: list[str] — chunks.section IN (...)
    if "sections" in filters and filters["sections"]:
        placeholders = ", ".join("?" for _ in filters["sections"])
        parts.append(f"chunks.section IN ({placeholders})")
        params.extend(filters["sections"])

    # clusters: list[str] — JSON containment via LIKE
    if "clusters" in filters and filters["clusters"]:
        for cl in filters["clusters"]:
            parts.append("papers.clusters LIKE ?")
            params.append(f'%"{cl}"%')

    if not parts:
        return ("", [])

    clause = " AND ".join(parts)
    return (clause, params)


# ---------------------------------------------------------------------------
# Search primitives
# ---------------------------------------------------------------------------


def bm25_search(
    conn: sqlite3.Connection,
    query_text: str,
    k: int,
    filters: dict | None = None,
) -> list[tuple[int, int]]:
    """Full-text BM25 search via FTS5.

    Returns list of (chunk_rowid, bm25_rank) tuples.
    Rank is negative (more negative = better match).
    """
    sanitized = _sanitize_fts_query(query_text)
    if not sanitized:
        return []

    filter_clause, filter_params = _build_filter_clause(filters)

    sql = (
        "SELECT chunks_fts.rowid, chunks_fts.rank "
        "FROM chunks_fts "
        "JOIN chunks ON chunks.id = chunks_fts.rowid "
        "JOIN papers ON papers.id = chunks.paper_id "
        "WHERE chunks_fts MATCH ?"
    )
    params: list = [sanitized]

    if filter_clause:
        sql += f" AND {filter_clause}"
        params.extend(filter_params)

    sql += " ORDER BY chunks_fts.rank LIMIT ?"
    params.append(3 * k)

    try:
        rows = conn.execute(sql, params).fetchall()
        return [(row[0], row[1]) for row in rows]
    except Exception:
        # FTS5 MATCH can throw on malformed input
        return []


def vector_search(
    conn: sqlite3.Connection,
    query_embedding: list[float],
    k: int,
    filters: dict | None = None,
) -> list[tuple[int, float]]:
    """Approximate nearest-neighbour search via sqlite-vss.

    Returns list of (chunk_rowid, distance) tuples.
    """
    rows = conn.execute(
        "SELECT rowid, distance FROM chunks_vss WHERE vss_search(embedding, ?) LIMIT ?",
        (json.dumps(query_embedding), 3 * k),
    ).fetchall()

    rows = [(row[0], row[1]) for row in rows]

    # Post-hoc metadata filtering (sqlite-vss can't JOIN in the same query)
    if filters:
        filter_clause, filter_params = _build_filter_clause(filters)
        if filter_clause:
            valid_ids: set[int] = set()
            for row in conn.execute(
                f"SELECT chunks.id FROM chunks "
                f"JOIN papers ON papers.id = chunks.paper_id "
                f"WHERE {filter_clause}",
                filter_params,
            ).fetchall():
                valid_ids.add(row[0])
            rows = [(rid, dist) for rid, dist in rows if rid in valid_ids]

    return rows


# ---------------------------------------------------------------------------
# Fusion & reranking
# ---------------------------------------------------------------------------


def rrf_merge(
    bm25_results: list[tuple[int, int]],
    vector_results: list[tuple[int, float]],
    k: int,
    rrf_k: int = 60,
) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion of BM25 and vector results.

    Returns list of (chunk_rowid, fused_score) sorted descending, limited to k.
    """
    scores: dict[int, float] = {}

    for rank, (rowid, _) in enumerate(bm25_results):
        scores[rowid] = scores.get(rowid, 0) + 1.0 / (rrf_k + rank + 1)

    for rank, (rowid, _) in enumerate(vector_results):
        scores[rowid] = scores.get(rowid, 0) + 1.0 / (rrf_k + rank + 1)

    sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results[:k]


def rerank_crossencoder(
    query_text: str,
    conn: sqlite3.Connection,
    candidates: list[tuple[int, float]],
    k: int,
) -> list[tuple[int, float]]:
    """Re-score candidates with a cross-encoder model.

    Lazy-loads ``cross-encoder/ms-marco-MiniLM-L-6-v2``.
    Returns top-k (chunk_id, cross_encoder_score) sorted descending.
    """
    if not candidates:
        return []

    ce = _get_cross_encoder()

    # Load chunk texts
    chunk_ids = [cid for cid, _ in candidates]
    placeholders = ", ".join("?" for _ in chunk_ids)
    rows = conn.execute(
        f"SELECT id, text FROM chunks WHERE id IN ({placeholders})",
        chunk_ids,
    ).fetchall()

    id_to_text: dict[int, str] = {row[0]: row[1] for row in rows}

    # Build pairs for the cross-encoder
    pairs: list[tuple[str, str]] = []
    ordered_ids: list[int] = []
    for cid, _ in candidates:
        text = id_to_text.get(cid)
        if text is not None:
            pairs.append((query_text, text))
            ordered_ids.append(cid)

    if not pairs:
        return []

    scores = ce.predict(pairs)

    scored = list(zip(ordered_ids, [float(s) for s in scores]))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


# ---------------------------------------------------------------------------
# Result loading
# ---------------------------------------------------------------------------


def _load_chunk_results(
    conn: sqlite3.Connection,
    rowid_scores: list[tuple[int, float]],
) -> list[ChunkResult]:
    """Load full chunk + paper metadata for a list of (chunk_id, score)."""
    results: list[ChunkResult] = []

    for rank_idx, (chunk_id, score) in enumerate(rowid_scores):
        row = conn.execute(
            "SELECT c.id, c.text, c.section, c.token_count, "
            "       p.pmid, p.title, p.year, p.authors, p.clusters, "
            "       p.materials, p.cell_types "
            "FROM chunks c "
            "JOIN papers p ON p.id = c.paper_id "
            "WHERE c.id = ?",
            (chunk_id,),
        ).fetchone()

        if row is None:
            continue

        def _json_or_list(val) -> list:
            if val is None:
                return []
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    return []
            return val

        paper = PaperInfo(
            pmid=row[4],
            title=row[5],
            year=row[6],
            authors=_json_or_list(row[7]),
            clusters=_json_or_list(row[8]),
            materials=_json_or_list(row[9]),
            cell_types=_json_or_list(row[10]),
        )

        results.append(
            ChunkResult(
                chunk_id=row[0],
                text=row[1],
                section=row[2],
                score=score,
                rank=rank_idx + 1,
                paper=paper,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Parameter search
# ---------------------------------------------------------------------------


def search_parameters(
    conn: sqlite3.Connection,
    query_text: str,
    filters: dict | None = None,
) -> list[ParameterResult]:
    """Keyword search over the parameters table."""
    words = query_text.lower().split()
    clauses: list[str] = []
    params: list[str] = []

    for word in words:
        if len(word) >= 3:
            clauses.append(
                "(LOWER(material) LIKE ? OR LOWER(cell_type) LIKE ? "
                "OR LOWER(parameter) LIKE ? OR LOWER(notes) LIKE ?)"
            )
            params.extend([f"%{word}%"] * 4)

    if not clauses:
        return []

    where = " OR ".join(clauses)
    sql = f"SELECT * FROM parameters WHERE {where} LIMIT 20"

    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception:
        return []

    results: list[ParameterResult] = []
    for row in rows:
        results.append(
            ParameterResult(
                id=str(row[0]),
                table_name=row[1],
                parameter=row[2],
                value=row[3],
                unit=row[4],
                material=row[5],
                cell_type=row[6],
                confidence=row[8],
                doi=row[9],
            )
        )

    return results


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def hybrid_search(
    conn: sqlite3.Connection,
    query_text: str,
    query_embedding: list[float],
    k: int = 10,
    filters: dict | None = None,
    rerank: bool = False,
    include_parameters: bool = True,
) -> tuple[list[ChunkResult], list[ParameterResult]]:
    """Run hybrid BM25 + vector search with RRF fusion.

    Parameters
    ----------
    conn : sqlite3.Connection
        Database connection (must have FTS5 and sqlite-vss loaded).
    query_text : str
        Natural-language query string.
    query_embedding : list[float]
        384-dim embedding of the query (from all-MiniLM-L6-v2 or similar).
    k : int
        Number of results to return.
    filters : dict | None
        Optional metadata filters (materials, tissue_type, year_min, sections, clusters).
    rerank : bool
        Whether to apply cross-encoder reranking.
    include_parameters : bool
        Whether to also search the parameters table.

    Returns
    -------
    tuple of (list[ChunkResult], list[ParameterResult])
    """
    # 1. BM25 search (may fail on empty FTS table or bad query)
    bm25_results = bm25_search(conn, query_text, k, filters)

    # 2. Vector search
    try:
        vec_results = vector_search(conn, query_embedding, k, filters)
    except Exception:
        vec_results = []

    # 3. Merge — handle cases where one side is empty
    if bm25_results and vec_results:
        merged = rrf_merge(bm25_results, vec_results, k)
    elif bm25_results:
        # Vector search returned nothing; use BM25 alone with synthetic scores
        merged = [
            (rowid, 1.0 / (60 + rank + 1))
            for rank, (rowid, _) in enumerate(bm25_results)
        ][:k]
    elif vec_results:
        # BM25 returned nothing; use vector alone with synthetic scores
        merged = [
            (rowid, 1.0 / (60 + rank + 1))
            for rank, (rowid, _) in enumerate(vec_results)
        ][:k]
    else:
        merged = []

    # 4. Optional cross-encoder reranking
    if rerank and merged:
        merged = rerank_crossencoder(query_text, conn, merged, k)

    # 5. Load full results
    chunks = _load_chunk_results(conn, merged)

    # 6. Parameter search
    parameters: list[ParameterResult] = []
    if include_parameters:
        parameters = search_parameters(conn, query_text, filters)

    return (chunks, parameters)
