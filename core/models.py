"""
Pydantic Models for Stromalytix

Data models for construct profiles and variance reports.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ConstructProfile(BaseModel):
    """
    Tissue engineering construct profile collected via chat assessment.

    Represents the parameters of a 3D cell culture construct that will be
    benchmarked against literature.
    """
    application_domain: Optional[str] = None  # "tissue_engineering" | "cellular_agriculture"
    target_tissue: Optional[str] = None
    cell_types: Optional[List[str]] = None
    scaffold_material: Optional[str] = None
    stiffness_kpa: Optional[float] = None
    porosity_percent: Optional[float] = None
    cell_density_per_ml: Optional[float] = None
    experimental_goal: Optional[str] = None
    primary_readout: Optional[str] = None
    raw_responses: Optional[Dict[str, str]] = None

    # Scaffold geometry
    scaffold_architecture: Optional[str] = None
    pore_size_um: Optional[float] = None
    scaffold_dimensions_mm: Optional[List[float]] = None
    scaffold_type: Optional[str] = None
    biofab_method: Optional[str] = None

    # Culture protocol
    culture_format: Optional[str] = None
    culture_duration_days: Optional[int] = None
    media_change_interval_hours: Optional[float] = None
    medium_volume_ml: Optional[float] = None
    media_type: Optional[str] = None
    perfusion_rate_ul_min: Optional[float] = None
    oxygen_tension_percent: Optional[float] = None

    class Config:
        json_schema_extra = {
            "example": {
                "target_tissue": "cardiac",
                "cell_types": ["cardiomyocytes", "fibroblasts"],
                "scaffold_material": "GelMA",
                "stiffness_kpa": 10.0,
                "porosity_percent": 70.0,
                "cell_density_per_ml": 1e6,
                "experimental_goal": "disease_modeling",
                "primary_readout": "contractility",
                "scaffold_architecture": "gyroid",
                "pore_size_um": 300.0,
                "scaffold_dimensions_mm": [4.0, 4.0, 4.0],
                "scaffold_type": "degradable",
                "biofab_method": "bioprinting",
                "culture_format": "wellplate",
                "culture_duration_days": 14,
                "media_change_interval_hours": 48.0,
                "medium_volume_ml": 2.0,
                "media_type": "DMEM",
                "perfusion_rate_ul_min": 0.0,
                "oxygen_tension_percent": 20.0,
            }
        }


class VarianceReport(BaseModel):
    """
    Process variance analysis report comparing construct to literature benchmarks.

    Quantifies deviations from published best practices and flags risk areas.
    """
    construct_profile: ConstructProfile
    benchmark_ranges: Dict[str, Dict] = Field(
        default_factory=dict,
        description="Literature-derived ranges per parameter (e.g., {'stiffness_kpa': {'min': 5, 'max': 15, 'unit': 'kPa'}})"
    )
    deviation_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="Normalized deviation scores per parameter: -1 to 1, where 0 = on benchmark"
    )
    risk_flags: Dict[str, str] = Field(
        default_factory=dict,
        description="Risk assessment per parameter: 'green' | 'yellow' | 'red'"
    )
    ai_narrative: str = Field(
        default="",
        description="3-4 sentence AI-generated analysis citing PMIDs from literature"
    )
    supporting_pmids: List[str] = Field(
        default_factory=list,
        description="List of PubMed IDs supporting the analysis"
    )
    key_references: List[Dict] = Field(
        default_factory=list,
        description="Key references with full citation objects: {pmid, title, year, relevance_note}"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "construct_profile": {
                    "target_tissue": "cardiac",
                    "scaffold_material": "GelMA",
                    "stiffness_kpa": 10.0
                },
                "benchmark_ranges": {
                    "stiffness_kpa": {"min": 8, "max": 12, "unit": "kPa", "optimal": 10}
                },
                "deviation_scores": {
                    "stiffness_kpa": 0.0
                },
                "risk_flags": {
                    "stiffness_kpa": "green"
                },
                "ai_narrative": "Your GelMA stiffness of 10 kPa aligns well with published cardiac tissue benchmarks (PMID: 12345678). This range has been shown to support cardiomyocyte maturation and contractility.",
                "supporting_pmids": ["12345678", "87654321"]
            }
        }
