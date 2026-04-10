"""
Knowledge Vault — FastAPI sidecar

Semantic search + parameter lookup over the Stromalytix literature corpus.
Exposes /query, /ingest, /explain endpoints for the Streamlit app and agents.

Security: API key auth. Never expose without STROMALYTIX_API_KEY.
"""

from contextlib import asynccontextmanager
import json
import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends

from db import init_db, close_db
from embedder import Embedder
from retrieval import hybrid_search, search_parameters
from ingest import ingest_papers as _ingest_papers, ingest_parameters as _ingest_params, ingest_benchmarks as _ingest_benchmarks
from auth import verify_api_key as _verify_api_key
from protocol_api import protocol_router
from schema import (
    QueryRequest, QueryResponse, ChunkResult,
    IngestRequest, IngestResponse,
    ParameterIngestRequest,
    HealthResponse, StatsResponse,
    ExplainRequest, ExplainResponse,
)

# --------------- Auth ---------------

from auth import STROMALYTIX_API_KEY

_INSECURE_API_KEYS = frozenset({
    "dev-key-change-me",
    "change-me-in-production",
    "CHANGE_ME_BEFORE_DEPLOY",
})
_enforce = os.environ.get("STROMALYTIX_ENFORCE_API_KEY", "").lower() in ("1", "true", "yes")
_allow_weak = os.environ.get("STROMALYTIX_ALLOW_WEAK_KEY", "").lower() in ("1", "true", "yes")
if _enforce and STROMALYTIX_API_KEY in _INSECURE_API_KEYS and not _allow_weak:
    raise SystemExit(
        "STROMALYTIX_API_KEY is a placeholder. Set a strong secret. "
        "For local dev: unset STROMALYTIX_ENFORCE_API_KEY or set STROMALYTIX_ALLOW_WEAK_KEY=1."
    )

DB_PATH = os.environ.get("VAULT_DB_PATH", "vault.db")

# Re-export for backward compatibility
verify_api_key = _verify_api_key


# --------------- Lifespan ---------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = init_db(DB_PATH)
    app.state.embedder = Embedder()
    yield
    close_db()


app = FastAPI(title="Stromalytix Knowledge Vault", lifespan=lifespan)
app.include_router(protocol_router)


# --------------- Endpoints ---------------

@app.get("/health", response_model=HealthResponse)
async def health():
    """Public health check — no API key required."""
    db = app.state.db
    paper_count = db.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    chunk_count = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    param_count = db.execute("SELECT COUNT(*) FROM parameters").fetchone()[0]

    db_size_mb = 0.0
    db_file = Path(DB_PATH)
    if db_file.exists():
        db_size_mb = round(db_file.stat().st_size / (1024 * 1024), 2)

    emb = app.state.embedder
    return HealthResponse(
        status="ok",
        paper_count=paper_count,
        chunk_count=chunk_count,
        parameter_count=param_count,
        embedding_model=emb.model_name,
        embedding_dims=emb.dims,
        db_size_mb=db_size_mb,
    )


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest, _key: str = Depends(verify_api_key)):
    """Hybrid BM25 + vector search over chunks and parameters."""
    t0 = time.perf_counter()
    db = app.state.db
    emb = app.state.embedder

    query_embedding = emb.embed_text(req.text)
    chunks, params = hybrid_search(
        conn=db,
        query_text=req.text,
        query_embedding=query_embedding,
        k=req.k,
        filters=req.filters,
        rerank=req.rerank,
        include_parameters=req.include_parameters,
    )

    elapsed = (time.perf_counter() - t0) * 1000
    return QueryResponse(
        chunks=chunks,
        parameters=params,
        total_chunks=len(chunks),
        query_ms=round(elapsed, 2),
    )


@app.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest, _key: str = Depends(verify_api_key)):
    """Ingest paper records with entity extraction, chunking, and embedding."""
    db = app.state.db
    emb = app.state.embedder
    stats = _ingest_papers(db, emb, req.records, req.cluster)
    return IngestResponse(**stats)


@app.post("/ingest/parameters")
async def ingest_params_endpoint(req: ParameterIngestRequest, _key: str = Depends(verify_api_key)):
    """Ingest parameter library entries."""
    db = app.state.db
    count = _ingest_params(db, req.table_name, req.entries)
    return {"ingested": count, "table_name": req.table_name}


@app.get("/paper/{pmid}")
async def get_paper(pmid: str, _key: str = Depends(verify_api_key)):
    """Return a single paper by PMID, or 404."""
    db = app.state.db
    row = db.execute("SELECT * FROM papers WHERE pmid = ?", (pmid,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Paper with PMID {pmid} not found")
    paper = dict(row)
    # Deserialise JSON list columns
    for col in ("authors", "clusters", "materials", "cell_types"):
        if isinstance(paper.get(col), str):
            try:
                paper[col] = json.loads(paper[col])
            except (json.JSONDecodeError, TypeError):
                paper[col] = []
    return paper


@app.get("/stats", response_model=StatsResponse)
async def stats(_key: str = Depends(verify_api_key)):
    """Aggregate counts by cluster and parameter table."""
    db = app.state.db

    total_papers = db.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    total_chunks = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    total_params = db.execute("SELECT COUNT(*) FROM parameters").fetchone()[0]

    # Papers by cluster — clusters is a JSON array column
    papers_by_cluster: dict[str, int] = {}
    for row in db.execute("SELECT clusters FROM papers").fetchall():
        try:
            clusters = json.loads(row["clusters"])
        except (json.JSONDecodeError, TypeError):
            clusters = []
        for c in clusters:
            papers_by_cluster[c] = papers_by_cluster.get(c, 0) + 1

    # Parameters by table_name
    params_by_table: dict[str, int] = {}
    for row in db.execute("SELECT table_name, COUNT(*) as cnt FROM parameters GROUP BY table_name").fetchall():
        params_by_table[row["table_name"]] = row["cnt"]

    return StatsResponse(
        papers_by_cluster=papers_by_cluster,
        parameters_by_table=params_by_table,
        total_papers=total_papers,
        total_chunks=total_chunks,
        total_parameters=total_params,
    )


@app.post("/explain", response_model=ExplainResponse)
async def explain(req: ExplainRequest, _key: str = Depends(verify_api_key)):
    """Build synthesis-ready context with reranking for LLM explanation."""
    t0 = time.perf_counter()
    db = app.state.db
    emb = app.state.embedder

    query_embedding = emb.embed_text(req.text)
    chunks, params = hybrid_search(
        conn=db,
        query_text=req.text,
        query_embedding=query_embedding,
        k=req.k,
        filters=None,
        rerank=req.rerank,
        include_parameters=True,
    )

    # Build formatted context string for LLM consumption
    lines = []
    for chunk in chunks:
        p = chunk.paper
        lines.append(f"[PMID:{p.pmid}] {p.title} ({p.year})")
        lines.append(f"  Section: {chunk.section} | Score: {chunk.score:.3f}")
        lines.append(f"  {chunk.text[:500]}")
        lines.append("")
    if params:
        lines.append("--- PARAMETER LIBRARY ---")
        for param in params:
            lines.append(f"  {param.parameter}: {param.value} {param.unit or ''} ({param.material or ''}) [confidence: {param.confidence or '?'}]")

    elapsed = (time.perf_counter() - t0) * 1000
    return ExplainResponse(
        context_blocks=chunks,
        parameter_context=params,
        formatted_context="\n".join(lines),
        query_ms=round(elapsed, 2),
    )
