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
    target_tissue: Optional[str] = None
    cell_types: Optional[List[str]] = None
    scaffold_material: Optional[str] = None
    stiffness_kpa: Optional[float] = None
    porosity_percent: Optional[float] = None
    cell_density_per_ml: Optional[float] = None
    experimental_goal: Optional[str] = None  # disease_modeling | drug_screening | basic_research
    primary_readout: Optional[str] = None  # viability | contractility | metabolic_activity | gene_expression
    raw_responses: Optional[Dict[str, str]] = None

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
                "raw_responses": {
                    "tissue": "I'm working on heart tissue",
                    "cells": "cardiomyocytes and fibroblasts"
                }
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
