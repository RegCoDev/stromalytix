"""
Knowledge Vault — Protocol Graph API endpoints.

Exposes search, match, novelty scoring, and stats over the protocol graph.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from auth import verify_api_key
from protocol_db import get_protocol, query_protocols, match_protocols, get_protocol_stats
from protocol_schema import (
    Protocol,
    ProtocolListResponse,
    ProtocolMatchRequest,
    ProtocolMatchResponse,
    ProtocolMatchResult,
    ProtocolStatsResponse,
    NoveltyRequest,
    NoveltyResponse,
    NoveltyStepScore,
)

protocol_router = APIRouter(prefix="/protocols", tags=["protocols"])


# ---------------------------------------------------------------------------
# GET /protocols — filtered list
# ---------------------------------------------------------------------------

@protocol_router.get("", response_model=ProtocolListResponse)
async def list_protocols(
    request: Request,
    tissue_type: str | None = Query(None),
    biofab_method: str | None = Query(None),
    material: str | None = Query(None),
    cell_type: str | None = Query(None),
    confidence: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _key: str = Depends(verify_api_key),
):
    """Search protocols with optional filters on tissue, method, material, cell type."""
    db = request.app.state.db
    protocols, total = query_protocols(
        db,
        tissue_type=tissue_type,
        biofab_method=biofab_method,
        material=material,
        cell_type=cell_type,
        confidence=confidence,
        limit=limit,
        offset=offset,
    )
    return ProtocolListResponse(protocols=protocols, total=total)


# ---------------------------------------------------------------------------
# GET /protocols/stats — aggregate counts
# ---------------------------------------------------------------------------

@protocol_router.get("/stats", response_model=ProtocolStatsResponse)
async def protocol_stats(
    request: Request,
    _key: str = Depends(verify_api_key),
):
    """Aggregate counts across the protocol graph."""
    db = request.app.state.db
    stats = get_protocol_stats(db)
    return ProtocolStatsResponse(**stats)


# ---------------------------------------------------------------------------
# GET /protocols/{protocol_id} — full protocol with nested steps
# ---------------------------------------------------------------------------

@protocol_router.get("/{protocol_id}", response_model=Protocol)
async def get_protocol_detail(
    protocol_id: int,
    request: Request,
    _key: str = Depends(verify_api_key),
):
    """Return a full protocol with all nested steps, materials, cells, parameters, outcomes."""
    db = request.app.state.db
    protocol = get_protocol(db, protocol_id)
    if protocol is None:
        raise HTTPException(status_code=404, detail=f"Protocol {protocol_id} not found")
    return protocol


# ---------------------------------------------------------------------------
# POST /protocols/match — similarity scoring
# ---------------------------------------------------------------------------

@protocol_router.post("/match", response_model=ProtocolMatchResponse)
async def match_protocols_endpoint(
    req: ProtocolMatchRequest,
    request: Request,
    _key: str = Depends(verify_api_key),
):
    """Score protocols against provided criteria and return top matches."""
    db = request.app.state.db
    matches = match_protocols(
        db,
        scaffold_material=req.scaffold_material,
        cell_types=req.cell_types,
        target_tissue=req.target_tissue,
        biofab_method=req.biofab_method,
        stiffness_kpa=req.stiffness_kpa,
    )
    top = matches[:20]
    return ProtocolMatchResponse(
        matches=[ProtocolMatchResult(**m) for m in top],
        total=len(matches),
    )


# ---------------------------------------------------------------------------
# POST /protocols/novelty — novelty scoring
# ---------------------------------------------------------------------------

@protocol_router.post("/novelty", response_model=NoveltyResponse)
async def novelty_score(
    req: NoveltyRequest,
    request: Request,
    _key: str = Depends(verify_api_key),
):
    """Score novelty of a proposed protocol relative to existing database."""
    db = request.app.state.db

    total_protocols = db.execute("SELECT COUNT(*) FROM protocols").fetchone()[0]
    if total_protocols == 0:
        return NoveltyResponse(
            overall_novelty=1.0,
            step_scores=[],
            gaps=[f"step {i}: {s.get('action_type', 'unknown')}" for i, s in enumerate(req.steps, 1)],
            total_protocols_checked=0,
        )

    step_scores = []
    gaps = []

    for i, step in enumerate(req.steps, 1):
        action_type = step.get("action_type", "")
        materials = step.get("materials", [])

        # Count protocols with a step of the same action_type
        if action_type:
            matching = db.execute(
                """SELECT COUNT(DISTINCT ps.protocol_id)
                   FROM protocol_steps ps
                   WHERE LOWER(ps.action_type) = LOWER(?)""",
                (action_type,),
            ).fetchone()[0]
        else:
            matching = 0

        # Further filter by materials if provided
        if materials and matching > 0:
            placeholders = ",".join("?" for _ in materials)
            matching = db.execute(
                f"""SELECT COUNT(DISTINCT ps.protocol_id)
                    FROM protocol_steps ps
                    JOIN step_materials sm ON sm.step_id = ps.id
                    WHERE LOWER(ps.action_type) = LOWER(?)
                      AND LOWER(sm.material_name) IN ({placeholders})""",
                [action_type] + [m.lower() for m in materials],
            ).fetchone()[0]

        novelty = 1.0 - (matching / total_protocols)

        step_scores.append(NoveltyStepScore(
            seq=i,
            action_type=action_type or "unknown",
            novelty=round(novelty, 4),
            matching_protocols=matching,
            description=step.get("description", ""),
        ))

        if matching == 0:
            desc = step.get("description", action_type or f"step {i}")
            gaps.append(f"Step {i} ({action_type}): {desc}")

    overall = sum(s.novelty for s in step_scores) / len(step_scores) if step_scores else 1.0

    return NoveltyResponse(
        overall_novelty=round(overall, 4),
        step_scores=step_scores,
        gaps=gaps,
        total_protocols_checked=total_protocols,
    )
