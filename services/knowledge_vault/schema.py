"""
Knowledge Vault — Pydantic models for API request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional


class QueryRequest(BaseModel):
    text: str
    filters: Optional[dict] = None  # materials, tissue_type, year_min, sections, clusters
    k: int = Field(default=10, ge=1, le=100)
    include_parameters: bool = True
    rerank: bool = False


class PaperInfo(BaseModel):
    pmid: str
    title: str
    year: Optional[int] = None
    authors: list[str] = []
    clusters: list[str] = []
    materials: list[str] = []
    cell_types: list[str] = []


class ChunkResult(BaseModel):
    chunk_id: int
    text: str
    section: str
    score: float
    rank: int
    paper: PaperInfo


class ParameterResult(BaseModel):
    id: str
    table_name: str
    parameter: str
    value: Optional[float] = None
    unit: Optional[str] = None
    material: Optional[str] = None
    cell_type: Optional[str] = None
    confidence: Optional[str] = None
    doi: Optional[str] = None


class QueryResponse(BaseModel):
    chunks: list[ChunkResult]
    parameters: list[ParameterResult] = []
    total_chunks: int
    query_ms: float


class IngestRequest(BaseModel):
    records: list[dict]
    cluster: str = "unknown"


class IngestResponse(BaseModel):
    ingested: int
    skipped_duplicate: int
    chunks_created: int
    errors: list[str] = []


class ParameterIngestRequest(BaseModel):
    table_name: str
    entries: list[dict]


class HealthResponse(BaseModel):
    status: str
    paper_count: int
    chunk_count: int
    parameter_count: int
    embedding_model: str
    embedding_dims: int
    db_size_mb: float


class StatsResponse(BaseModel):
    papers_by_cluster: dict[str, int]
    parameters_by_table: dict[str, int]
    total_papers: int
    total_chunks: int
    total_parameters: int


class ExplainRequest(BaseModel):
    text: str
    k: int = Field(default=15, ge=1, le=50)
    rerank: bool = True


class ExplainResponse(BaseModel):
    context_blocks: list[ChunkResult]
    parameter_context: list[ParameterResult] = []
    formatted_context: str
    query_ms: float
