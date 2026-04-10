"""
Knowledge Vault — Protocol Graph Pydantic models.

Defines the structured representation of tissue-engineering protocols
extracted from published literature: protocols → steps → materials/cells/parameters/outcomes.
"""

from pydantic import BaseModel, Field
from typing import Optional


class StepMaterial(BaseModel):
    material_name: str
    material_type: Optional[str] = None
    concentration: Optional[str] = None
    volume: Optional[str] = None


class StepCell(BaseModel):
    cell_type: str
    source: Optional[str] = None  # primary/iPSC/cell_line
    passage: Optional[str] = None
    density: Optional[str] = None
    viability: Optional[str] = None


class StepParameter(BaseModel):
    parameter_name: str
    value: Optional[float] = None
    unit: Optional[str] = None
    confidence: Optional[str] = "low"
    extraction_method: Optional[str] = "regex"
    source_sentence: Optional[str] = None


class StepOutcome(BaseModel):
    assay_type: Optional[str] = None
    timepoint: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    success_threshold: Optional[float] = None
    comparison: Optional[str] = None


class ProtocolStep(BaseModel):
    id: Optional[int] = None
    seq: int
    action_type: str  # cell_sourcing|cell_expansion|material_prep|crosslinking|fabrication|cell_seeding|culture|assay
    description: str
    duration: Optional[str] = None
    temperature: Optional[str] = None
    equipment: Optional[str] = None
    conditions: Optional[dict] = None
    raw_text: Optional[str] = None
    materials: list[StepMaterial] = []
    cells: list[StepCell] = []
    parameters: list[StepParameter] = []
    outcomes: list[StepOutcome] = []


class Protocol(BaseModel):
    id: Optional[int] = None
    paper_id: Optional[int] = None
    source_pmid: Optional[str] = None
    target_tissue: Optional[str] = None
    application_domain: Optional[str] = None
    biofab_method: Optional[str] = None
    overall_outcome: Optional[str] = None
    confidence: Optional[str] = "low"
    extraction_method: Optional[str] = "regex"
    steps: list[ProtocolStep] = []


# ---------------------------------------------------------------------------
# API response models
# ---------------------------------------------------------------------------

class ProtocolSummary(BaseModel):
    id: int
    source_pmid: Optional[str] = None
    paper_title: Optional[str] = None
    target_tissue: Optional[str] = None
    biofab_method: Optional[str] = None
    confidence: Optional[str] = None
    step_count: int
    extraction_method: Optional[str] = None


class ProtocolListResponse(BaseModel):
    protocols: list[ProtocolSummary]
    total: int


class ProtocolMatchRequest(BaseModel):
    scaffold_material: Optional[str] = None
    cell_types: Optional[list[str]] = None
    target_tissue: Optional[str] = None
    biofab_method: Optional[str] = None
    stiffness_kpa: Optional[float] = None


class ProtocolMatchResult(BaseModel):
    protocol_id: int
    source_pmid: Optional[str] = None
    paper_title: Optional[str] = None
    similarity_score: float
    matching_fields: list[str]


class ProtocolMatchResponse(BaseModel):
    matches: list[ProtocolMatchResult]
    total: int


class NoveltyStepScore(BaseModel):
    seq: int
    action_type: str
    novelty: float  # 0=well-covered, 1=completely novel
    matching_protocols: int
    description: str


class NoveltyRequest(BaseModel):
    steps: list[dict]  # simplified step descriptions


class NoveltyResponse(BaseModel):
    overall_novelty: float
    step_scores: list[NoveltyStepScore]
    gaps: list[str]
    total_protocols_checked: int


class ProtocolStatsResponse(BaseModel):
    total_protocols: int
    total_steps: int
    total_step_parameters: int
    by_tissue: dict[str, int]
    by_biofab: dict[str, int]
    by_action_type: dict[str, int]
    by_confidence: dict[str, int]
    by_extraction_method: dict[str, int]
