"""
Demo Data Generator for Stromalytix

Generates a realistic VarianceReport for cardiac tissue without calling any LLMs.
Used for testing and demo purposes.
"""

import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import ConstructProfile, VarianceReport


def generate_demo_report() -> VarianceReport:
    """Generate demo cardiac tissue report for testing.

    Returns a fully populated VarianceReport with realistic cardiac tissue
    engineering data. No LLM calls are made.
    """
    profile = ConstructProfile(
        target_tissue="cardiac",
        cell_types=["cardiomyocytes", "fibroblasts"],
        scaffold_material="GelMA",
        stiffness_kpa=10.0,
        porosity_percent=70.0,
        cell_density_per_ml=1e6,
        experimental_goal="disease_modeling",
        primary_readout="contractility",
    )

    return VarianceReport(
        construct_profile=profile,
        benchmark_ranges={
            "stiffness_kpa": {
                "min": 8,
                "max": 12,
                "unit": "kPa",
                "source_pmids": ["34561899", "33245678"],
            },
            "porosity_percent": {
                "min": 60,
                "max": 80,
                "unit": "%",
                "source_pmids": ["34561899"],
            },
            "cell_density_per_ml": {
                "min": 5e5,
                "max": 2e6,
                "unit": "cells/mL",
                "source_pmids": ["33245678"],
            },
        },
        deviation_scores={
            "stiffness_kpa": 0.0,
            "porosity_percent": 0.0,
            "cell_density_per_ml": -0.1,
        },
        risk_flags={
            "stiffness_kpa": "green",
            "porosity_percent": "green",
            "cell_density_per_ml": "green",
        },
        ai_narrative=(
            "Your GelMA construct with 10 kPa stiffness aligns well with published "
            "cardiac tissue benchmarks (PMID: 34561899). The porosity of 70% falls "
            "within the optimal range for nutrient diffusion (PMID: 33245678). Cell "
            "density of 1e6 cells/mL is within the recommended range for cardiac "
            "constructs (PMID: 31987654). Overall, this protocol shows low risk across "
            "all parameters (PMID: 30123456, PMID: 29876543)."
        ),
        supporting_pmids=[
            "34561899",
            "33245678",
            "31987654",
            "30123456",
            "29876543",
        ],
        key_references=[
            {
                "pmid": "34561899",
                "title": "GelMA Hydrogels for Cardiac Tissue Engineering",
                "year": "2021",
                "relevance_note": "Optimal stiffness ranges for cardiomyocyte maturation",
            },
            {
                "pmid": "33245678",
                "title": "Porosity and Cell Density in 3D Cardiac Constructs",
                "year": "2020",
                "relevance_note": "Cell density and porosity benchmarks",
            },
            {
                "pmid": "31987654",
                "title": "Bioink Optimization for Heart-on-Chip Models",
                "year": "2019",
                "relevance_note": "GelMA rheology and cell viability correlation",
            },
        ],
    )


if __name__ == "__main__":
    report = generate_demo_report()
    print(f"Target tissue: {report.construct_profile.target_tissue}")
    print(f"Benchmark params: {list(report.benchmark_ranges.keys())}")
    print(f"Supporting PMIDs: {report.supporting_pmids}")
    print("Demo report generated successfully.")
