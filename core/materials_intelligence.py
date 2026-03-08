"""
core/materials_intelligence.py

Materials Intelligence — value for bioink manufacturers.
Input: material characterization data (rheology, gelation, lot ID)
Output: predicted customer outcomes + lot release recommendation

Positioned for Cytoink as:
"Know which lots will succeed in your customers' labs
before they run a single experiment."
"""

from dataclasses import dataclass, field
from typing import Optional
import math


@dataclass
class BioinkLotCharacterization:
    """Rheology and physical characterization of a bioink lot."""
    lot_id: str
    material_name: str

    # Rheology
    storage_modulus_pa: Optional[float] = None
    loss_modulus_pa: Optional[float] = None
    tan_delta: Optional[float] = None
    viscosity_pas_at_37c: Optional[float] = None
    gelation_time_s: Optional[float] = None
    gelation_temp_c: Optional[float] = None

    # Crosslinking
    crosslink_density: Optional[float] = None
    uv_dose_mwcm2_s: Optional[float] = None

    # Physical
    swelling_ratio: Optional[float] = None
    degradation_rate_day: Optional[float] = None

    # Cell-relevant
    amine_content_mmol_g: Optional[float] = None
    rgd_density_pmol_cm2: Optional[float] = None

    # Provenance
    synthesis_date: Optional[str] = None
    supplier_lot: Optional[str] = None
    qa_notes: Optional[str] = None


@dataclass
class LotIntelligenceReport:
    """
    Predicted performance report for a bioink lot.
    """
    lot_id: str
    material_name: str

    # Core predictions
    predicted_stiffness_kpa: float
    stiffness_uncertainty_kpa: float
    predicted_printability_score: float
    predicted_cell_viability_day3_pct: float
    predicted_cell_viability_day7_pct: float

    # Process recommendations
    recommended_nozzle_diameter_mm: float
    recommended_print_speed_mms: float
    recommended_crosslink_time_s: float
    recommended_cell_density_per_ml: float

    # Release decision
    release_recommendation: str  # "RELEASE"|"CONDITIONAL"|"HOLD"
    release_rationale: str

    # Benchmarking
    benchmark_percentile: float

    # Confidence
    confidence: str
    data_gaps: list = field(default_factory=list)


# Material defaults when rheology unavailable
_MATERIAL_DEFAULTS = {
    "GelMA 6%": (8.0, 2.0),
    "GelMA 4%": (4.0, 1.5),
    "Fibrin 10mg/mL": (1.5, 0.8),
    "Collagen I": (2.0, 1.0),
    "Alginate 2%": (10.0, 3.0),
    "PEGDA": (15.0, 4.0),
}


def predict_lot_performance(char: BioinkLotCharacterization) -> LotIntelligenceReport:
    """
    Predict customer-relevant performance from material characterization.

    Based on structure-property relationships from literature:
    - G' -> stiffness (rubber elasticity theory)
    - Gelation time -> printability window
    - Swelling ratio -> dimensional stability
    - Tan delta -> viscoelastic behavior during printing
    """
    data_gaps = []
    confidence_factors = 0

    # Stiffness prediction from G'
    if char.storage_modulus_pa:
        sw = char.swelling_ratio or 1.0
        predicted_stiffness = (char.storage_modulus_pa / 1000) * (sw ** -2.33)
        stiffness_uncertainty = predicted_stiffness * 0.15
        confidence_factors += 2
    else:
        defaults = _MATERIAL_DEFAULTS.get(char.material_name, (5.0, 2.5))
        predicted_stiffness, stiffness_uncertainty = defaults
        data_gaps.append("storage_modulus_pa — stiffness estimated from material name only")

    # Printability prediction
    if char.viscosity_pas_at_37c and char.gelation_time_s:
        visc_score = 1.0 - abs(math.log10(char.viscosity_pas_at_37c / 100)) / 2
        gel_score = (
            1.0 if 30 <= char.gelation_time_s <= 120
            else max(0, 1 - abs(char.gelation_time_s - 75) / 75)
        )
        printability = min(1.0, max(0.3, (visc_score + gel_score) / 2))
        confidence_factors += 2
    else:
        printability = 0.72
        data_gaps.append("viscosity + gelation_time — printability estimated")

    # Viability prediction
    base_viability_day3 = 83.0
    base_viability_day7 = 79.0

    if predicted_stiffness > 10:
        stiffness_penalty = (predicted_stiffness - 10) * 0.8
        base_viability_day3 -= stiffness_penalty
        base_viability_day7 -= stiffness_penalty * 1.5

    if char.degradation_rate_day and char.degradation_rate_day > 5:
        base_viability_day7 -= (char.degradation_rate_day - 5) * 0.5

    predicted_viability_day3 = max(40, min(97, base_viability_day3))
    predicted_viability_day7 = max(35, min(95, base_viability_day7))

    # Process recommendations
    if char.viscosity_pas_at_37c:
        if char.viscosity_pas_at_37c < 50:
            nozzle = 0.25
            speed = 8.0
        elif char.viscosity_pas_at_37c < 150:
            nozzle = 0.41
            speed = 10.0
        else:
            nozzle = 0.6
            speed = 5.0
    else:
        nozzle = 0.41
        speed = 8.0

    crosslink_time = char.uv_dose_mwcm2_s / 10 if char.uv_dose_mwcm2_s else 60
    crosslink_time = max(30, min(120, crosslink_time))

    # Release decision
    if printability >= 0.75 and predicted_viability_day3 >= 80:
        release = "RELEASE"
        rationale = (
            f"Lot meets printability (score={printability:.2f}) "
            f"and viability (predicted day-3: {predicted_viability_day3:.0f}%) thresholds."
        )
    elif printability >= 0.60 and predicted_viability_day3 >= 70:
        release = "CONDITIONAL"
        rationale = (
            f"Marginal printability ({printability:.2f}). "
            f"Recommend increasing crosslink time by 15s."
        )
    else:
        release = "HOLD"
        rationale = (
            f"Predicted viability ({predicted_viability_day3:.0f}%) "
            f"or printability ({printability:.2f}) below threshold."
        )

    confidence = (
        "high" if confidence_factors >= 3
        else "medium" if confidence_factors >= 1
        else "low"
    )

    return LotIntelligenceReport(
        lot_id=char.lot_id,
        material_name=char.material_name,
        predicted_stiffness_kpa=round(predicted_stiffness, 1),
        stiffness_uncertainty_kpa=round(stiffness_uncertainty, 1),
        predicted_printability_score=round(printability, 3),
        predicted_cell_viability_day3_pct=round(predicted_viability_day3, 1),
        predicted_cell_viability_day7_pct=round(predicted_viability_day7, 1),
        recommended_nozzle_diameter_mm=nozzle,
        recommended_print_speed_mms=speed,
        recommended_crosslink_time_s=crosslink_time,
        recommended_cell_density_per_ml=1_000_000,
        release_recommendation=release,
        release_rationale=rationale,
        benchmark_percentile=0.65,
        confidence=confidence,
        data_gaps=data_gaps,
    )
