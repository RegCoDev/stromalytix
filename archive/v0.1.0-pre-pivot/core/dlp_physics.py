"""
core/dlp_physics.py

DLP (Digital Light Processing) bioprinting physics model.

DLP uses photopolymerization, NOT extrusion. The relevant physics
is Beer-Lambert cure depth:

    Cd = Dp * ln(E / Ec)

Where:
    Cd = cure depth (mm)
    Dp = penetration depth (mm) — material property
    E  = UV energy dose (mJ/cm²) = intensity × time
    Ec = critical energy for gelation (mJ/cm²)

References:
    Jacobs 1992 — Rapid Prototyping & Manufacturing (Beer-Lambert cure model)
    Grigoryan et al. Science 2019 doi:10.1126/science.aav9292
    Zhu et al. Adv Sci 2017 doi:10.1002/advs.201700175
"""

from dataclasses import dataclass, field
from typing import Optional
import math


# Material defaults: {name: {"Dp_mm": ..., "Ec_mJcm2": ...}}
DLP_MATERIAL_DEFAULTS = {
    "GelMA_10pct_LAP": {"Dp_mm": 0.45, "Ec_mJcm2": 8.0},
    "GelMA_15pct_LAP": {"Dp_mm": 0.38, "Ec_mJcm2": 10.0},
    "PEGDA_10pct": {"Dp_mm": 0.55, "Ec_mJcm2": 6.5},
}

# UV dose viability calibration data:
# (dose_mJcm2, viability_pct, viability_sd)
UV_DOSE_VIABILITY = [
    (20, 96.0, 3.1),
    (50, 93.5, 4.2),
    (100, 88.2, 5.8),
    (150, 79.4, 7.3),
    (200, 68.1, 9.2),
    (300, 52.3, 11.4),
]


@dataclass
class DLPPrintParameters:
    """Input parameters for DLP printability prediction."""
    material_type: str
    uv_intensity_mwcm2: float
    exposure_time_s_per_layer: float
    layer_thickness_mm: float
    n_layers: int
    Dp_mm: Optional[float] = None
    Ec_mJcm2: Optional[float] = None


@dataclass
class DLPPrintabilityReport:
    """DLP printability assessment report."""
    cure_depth_mm: float
    layer_thickness_viable: bool
    interlayer_bonding: str  # "strong" / "adequate" / "weak" / "failed"
    total_uv_dose_mJcm2: float
    predicted_viability_pct: float
    viability_sd: float
    oxygen_inhibition_layer_um: float
    xy_feature_resolution_um: float
    recommendations: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    references: list = field(default_factory=list)


def _interpolate_viability(dose_mJcm2: float) -> tuple:
    """
    Linear interpolation of cell viability from UV dose.
    Returns (viability_pct, sd).
    """
    doses = [pt[0] for pt in UV_DOSE_VIABILITY]
    viabs = [pt[1] for pt in UV_DOSE_VIABILITY]
    sds = [pt[2] for pt in UV_DOSE_VIABILITY]

    if dose_mJcm2 <= doses[0]:
        return viabs[0], sds[0]
    if dose_mJcm2 >= doses[-1]:
        return viabs[-1], sds[-1]

    for i in range(len(doses) - 1):
        if doses[i] <= dose_mJcm2 <= doses[i + 1]:
            t = (dose_mJcm2 - doses[i]) / (doses[i + 1] - doses[i])
            viability = viabs[i] + t * (viabs[i + 1] - viabs[i])
            sd = sds[i] + t * (sds[i + 1] - sds[i])
            return viability, sd

    # Fallback (should not reach here)
    return viabs[-1], sds[-1]


def predict_dlp_printability(params: DLPPrintParameters) -> DLPPrintabilityReport:
    """
    Predict DLP printability using Beer-Lambert cure depth model.

    Cd = Dp * ln(E / Ec)

    Where E = intensity * time (energy dose per layer).
    """
    # Resolve material properties
    Dp = params.Dp_mm
    Ec = params.Ec_mJcm2
    if Dp is None or Ec is None:
        defaults = DLP_MATERIAL_DEFAULTS.get(params.material_type)
        if defaults is None:
            raise ValueError(
                f"Unknown material '{params.material_type}' and no Dp/Ec provided. "
                f"Known materials: {list(DLP_MATERIAL_DEFAULTS.keys())}"
            )
        if Dp is None:
            Dp = defaults["Dp_mm"]
        if Ec is None:
            Ec = defaults["Ec_mJcm2"]

    # Energy dose per layer (mJ/cm²)
    E_per_layer = params.uv_intensity_mwcm2 * params.exposure_time_s_per_layer

    # Beer-Lambert cure depth
    if E_per_layer <= Ec:
        cure_depth = 0.0
    else:
        cure_depth = Dp * math.log(E_per_layer / Ec)

    # Layer thickness viability
    layer_thickness_viable = cure_depth >= params.layer_thickness_mm

    # Interlayer bonding assessment
    if cure_depth <= 0:
        interlayer_bonding = "failed"
    else:
        ratio = cure_depth / params.layer_thickness_mm
        if ratio >= 1.5:
            interlayer_bonding = "strong"
        elif ratio >= 1.1:
            interlayer_bonding = "adequate"
        elif ratio >= 0.8:
            interlayer_bonding = "weak"
        else:
            interlayer_bonding = "failed"

    # Total UV dose across all layers
    total_uv_dose = E_per_layer * params.n_layers

    # Viability from UV dose (cumulative dose matters)
    predicted_viability, viability_sd = _interpolate_viability(total_uv_dose)

    # Oxygen inhibition layer estimate (Zhu et al. 2017)
    # Typical range 10-50 um, scales inversely with intensity
    if params.uv_intensity_mwcm2 > 0:
        oxygen_inhibition_layer_um = 30.0 / (params.uv_intensity_mwcm2 / 10.0)
        oxygen_inhibition_layer_um = max(5.0, min(50.0, oxygen_inhibition_layer_um))
    else:
        oxygen_inhibition_layer_um = 50.0

    # XY feature resolution (Grigoryan et al. 2019)
    # Approximation: resolution ~ Dp * 1000 * 0.5 (in um)
    xy_feature_resolution_um = Dp * 1000.0 * 0.5

    # Recommendations
    recommendations = []
    warnings = []

    if interlayer_bonding == "weak":
        recommendations.append(
            "Increase exposure time or UV intensity to improve interlayer bonding. "
            "Target cure depth >= 1.5x layer thickness."
        )
    if interlayer_bonding == "failed":
        recommendations.append(
            "Cure depth insufficient for layer adhesion. "
            "Increase UV dose or reduce layer thickness."
        )

    if total_uv_dose > 200:
        warnings.append(
            f"Total UV dose {total_uv_dose:.0f} mJ/cm² exceeds 200 mJ/cm² — "
            f"significant viability reduction expected (predicted {predicted_viability:.1f}%)."
        )
    if total_uv_dose > 100:
        recommendations.append(
            "Consider reducing number of layers or exposure time to limit cumulative UV dose."
        )

    if predicted_viability < 70.0:
        warnings.append(
            f"Predicted viability {predicted_viability:.1f}% below 70% threshold. "
            f"Reduce UV exposure or use more photosensitive resin."
        )

    if oxygen_inhibition_layer_um > 30.0:
        recommendations.append(
            "Oxygen inhibition layer is thick — consider nitrogen purge or "
            "increasing UV intensity."
        )

    # References
    references = [
        "Jacobs 1992 — Rapid Prototyping & Manufacturing (Beer-Lambert cure model)",
        "Grigoryan et al. Science 2019 doi:10.1126/science.aav9292",
        "Zhu et al. Adv Sci 2017 doi:10.1002/advs.201700175",
    ]

    return DLPPrintabilityReport(
        cure_depth_mm=round(cure_depth, 4),
        layer_thickness_viable=layer_thickness_viable,
        interlayer_bonding=interlayer_bonding,
        total_uv_dose_mJcm2=round(total_uv_dose, 2),
        predicted_viability_pct=round(predicted_viability, 1),
        viability_sd=round(viability_sd, 1),
        oxygen_inhibition_layer_um=round(oxygen_inhibition_layer_um, 1),
        xy_feature_resolution_um=round(xy_feature_resolution_um, 1),
        recommendations=recommendations,
        warnings=warnings,
        references=references,
    )
