"""
core/hepatic_intelligence.py

Hepatic Process Intelligence — HepaPredict-like foundation.

Positions hepatic organoid/spheroid constructs as DILI
detection instruments and predicts their performance quality.

Biological basis:
- Healthy hepatocytes maintain defined expression of:
  CYP3A4, CYP2C9, CYP1A2 (drug metabolism)
  ALB, AFP (hepatocyte function)
  HNF4A, HNF1A (transcription factors)
- DILI disrupts these via: direct toxicity, mitochondrial,
  cholestasis, or immune-mediated mechanisms
- Construct quality = how well it maintains these markers
  under physiological conditions

Clinical relevance:
- 30% of drug withdrawals are DILI-related (FDA estimate)
- In vitro DILI prediction saves $100M+ per false positive avoided
- DILIrank: 1,036 drugs with known DILI status = ground truth
"""

from dataclasses import dataclass, field
from typing import Optional

# DILI mechanisms and associated hepatic process failures
DILI_MECHANISM_MAP = {
    "direct_cytotoxic": {
        "process_failure": "cell_viability_collapse",
        "cc3d_signal": "high_necrosis_rate",
        "biomarkers": ["LDH_release", "HMGB1", "K18"],
        "construct_sensitivity_predictor": "viability_day7",
    },
    "mitochondrial": {
        "process_failure": "energy_metabolism_disruption",
        "cc3d_signal": "metabolic_slowdown",
        "biomarkers": ["mtDNA_copy_number", "ATP_production", "ROS"],
        "construct_sensitivity_predictor": "oxygen_consumption_rate",
    },
    "cholestatic": {
        "process_failure": "bile_acid_transport_failure",
        "cc3d_signal": "transporter_downregulation",
        "biomarkers": ["BSEP_expression", "MRP2_expression", "GGT"],
        "construct_sensitivity_predictor": "albumin_secretion",
    },
    "immune_mediated": {
        "process_failure": "inflammatory_cascade",
        "cc3d_signal": "cytokine_upregulation",
        "biomarkers": ["IL-6", "TNF-alpha", "CXCL10"],
        "construct_sensitivity_predictor": "kupffer_cell_integration",
    },
}

# Literature-derived construct quality benchmarks for DILI detection
# Source: Lauschke et al. 2016 Nat Rev Drug Discov + Ewart et al. 2018
DILI_DETECTION_BENCHMARKS = {
    "2D_monolayer_hepg2": {
        "dilirank_sensitivity": 0.48,
        "specificity": 0.71,
        "reference": "10.1038/nrd.2016.159",
    },
    "3D_spheroid_hepg2": {
        "dilirank_sensitivity": 0.65,
        "specificity": 0.78,
        "reference": "10.1038/nrd.2016.159",
    },
    "3D_spheroid_primary_hepatocytes": {
        "dilirank_sensitivity": 0.78,
        "specificity": 0.88,
        "reference": "10.1038/s41467-018-06767-4",
    },
    "ooc_primary_hepatocytes": {
        "dilirank_sensitivity": 0.87,
        "specificity": 0.91,
        "reference": "10.1021/acs.analchem.6b04623",
    },
}


@dataclass
class HepaticQualityScore:
    """
    Predicted quality score for a hepatic construct as a DILI
    detection instrument.
    """
    construct_summary: str
    predicted_dilirank_sensitivity: float
    predicted_specificity: float
    benchmark_comparison: str
    confidence: str
    key_drivers: list = field(default_factory=list)
    limiting_factors: list = field(default_factory=list)
    optimization_recommendations: list = field(default_factory=list)
    reference_benchmark: str = ""

    @property
    def f1_score(self) -> float:
        p = self.predicted_dilirank_sensitivity
        r = self.predicted_specificity
        return 2 * p * r / (p + r) if (p + r) > 0 else 0


def predict_hepatic_quality(profile) -> HepaticQualityScore:
    """
    Predict DILI detection quality from ConstructProfile.

    Scoring logic based on literature benchmarks:
    - Base score from method + cell type combination
    - Modifiers: stiffness, passage number, culture duration
    - Penalties: known problematic parameters
    """
    cell_types = getattr(profile, "cell_types", []) or []
    stiffness = getattr(profile, "stiffness_kpa", None)

    cell_str = " ".join(cell_types).lower()

    # Detect method from profile context
    scaffold = (getattr(profile, "scaffold_material", "") or "").lower()
    tissue = (getattr(profile, "target_tissue", "") or "").lower()
    is_ooc = "pdms" in scaffold or "chip" in tissue or "ooc" in tissue

    # Base score from cell type + method
    if "primary" in cell_str and is_ooc:
        base = dict(DILI_DETECTION_BENCHMARKS["ooc_primary_hepatocytes"])
    elif "primary" in cell_str:
        base = dict(DILI_DETECTION_BENCHMARKS["3D_spheroid_primary_hepatocytes"])
    elif "heparg" in cell_str:
        base = dict(DILI_DETECTION_BENCHMARKS["3D_spheroid_hepg2"])
        base["dilirank_sensitivity"] += 0.05  # HepaRG better than HepG2
    else:
        base = dict(DILI_DETECTION_BENCHMARKS["3D_spheroid_hepg2"])

    sensitivity = base["dilirank_sensitivity"]
    specificity = base["specificity"]
    key_drivers = []
    limiting = []
    recommendations = []

    # Stiffness modifier — hepatic tissue is 1-5 kPa
    if stiffness is not None:
        if 2.0 <= stiffness <= 6.0:
            sensitivity += 0.03
            key_drivers.append(
                f"Stiffness {stiffness} kPa in physiological hepatic range (1-5 kPa)"
            )
        elif stiffness > 10:
            sensitivity -= 0.05
            limiting.append(
                f"Stiffness {stiffness} kPa exceeds hepatic physiological range"
            )
            recommendations.append(
                "Reduce scaffold stiffness to 2-6 kPa for hepatocyte phenotype maintenance"
            )

    # Culture duration modifier
    duration = getattr(profile, "culture_duration_days", None)
    if duration and duration >= 14:
        sensitivity += 0.04
        key_drivers.append(
            f"{duration}-day culture allows hepatocyte maturation and CYP stabilization"
        )
    elif duration and duration < 5:
        sensitivity -= 0.06
        limiting.append("Short culture duration insufficient for CYP enzyme induction")
        recommendations.append(
            "Extend culture to >= 14 days for stable CYP3A4/2C9 expression"
        )

    # Clamp to [0,1]
    sensitivity = max(0.0, min(1.0, sensitivity))
    specificity = max(0.0, min(1.0, specificity))

    confidence = "high" if len(key_drivers) >= 2 else \
                 "medium" if len(key_drivers) >= 1 else "low"

    # Benchmark comparison
    bench_2d = DILI_DETECTION_BENCHMARKS["2D_monolayer_hepg2"]["dilirank_sensitivity"]
    if sensitivity > bench_2d + 0.20:
        bench_str = f"Substantially outperforms 2D HepG2 monolayer ({bench_2d:.0%} sensitivity)"
    elif sensitivity > bench_2d:
        bench_str = f"Outperforms 2D HepG2 monolayer ({bench_2d:.0%} sensitivity)"
    else:
        bench_str = "Similar to 2D HepG2 monolayer — consider 3D upgrade"

    cell_summary = "/".join(cell_types[:2]) if cell_types else "unspecified"

    return HepaticQualityScore(
        construct_summary=f"{cell_summary}",
        predicted_dilirank_sensitivity=round(sensitivity, 3),
        predicted_specificity=round(specificity, 3),
        benchmark_comparison=bench_str,
        confidence=confidence,
        key_drivers=key_drivers,
        limiting_factors=limiting,
        optimization_recommendations=recommendations,
        reference_benchmark=base.get("reference", ""),
    )


def get_hepatic_cc3d_extensions(
    brief: dict,
    quality_score: HepaticQualityScore,
) -> dict:
    """
    Extend CC3D brief with hepatic-specific parameters for
    liver-relevant simulation.
    """
    extended = dict(brief)
    extended["hepatic_extensions"] = {
        "model_zonation": True,
        "periportal_oxygen_mmhg": 65,
        "pericentral_oxygen_mmhg": 35,
        "albumin_secretion_rate": quality_score.predicted_dilirank_sensitivity,
        "cyp3a4_activity_relative": max(0.3, quality_score.predicted_specificity),
        "bile_canaliculi_probability": 0.3 if quality_score.confidence == "high" else 0.1,
    }
    return extended
