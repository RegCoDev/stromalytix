"""
Scaffold mechanics solver using scikit-fem.

Answers: Will this scaffold deform under cell contractile forces?
What stress distribution does this geometry produce?

Arc 1: Simple 1D beam/compression model (fast, sync-safe)
Arc 2: Full 3D FEA with geometry from construct profile
Arc 3: Coupled with CC3D cell forces

Why scikit-fem before OpenMM:
- Directly relevant to bioink companies (stiffness claims)
- Fast enough for synchronous Streamlit execution
- First calibration win against rheometer measurements
"""
import numpy as np


def predict_scaffold_deformation(
    stiffness_kpa: float,
    cell_density_per_ml: float,
    construct_height_mm: float = 3.0,
) -> dict:
    """
    Simple compression model: estimate scaffold deformation
    under collective cell contractile force.

    Cell contractile stress: ~1-10 nN/cell (use 5 nN typical)
    """
    # Collective contractile force
    # Volume: 1cm x 1cm cross section * height
    cell_volume_ml = 1.0 * 1.0 * (construct_height_mm / 10.0)  # cm^3 = mL
    n_cells = cell_density_per_ml * cell_volume_ml
    contractile_force_nN = n_cells * 5.0  # 5 nN/cell typical

    # Convert to stress (assume 1cm x 1cm cross section)
    area_m2 = 1e-4
    stress_pa = (contractile_force_nN * 1e-9) / area_m2
    stress_kpa_val = stress_pa / 1000

    # Deformation from Hooke's law: delta = F*L/(E*A)
    E_pa = stiffness_kpa * 1000
    height_m = construct_height_mm * 1e-3
    deformation_m = (contractile_force_nN * 1e-9 * height_m) / (E_pa * area_m2)
    deformation_um = deformation_m * 1e6
    strain_pct = (deformation_m / height_m) * 100

    # Risk thresholds from literature
    if strain_pct > 15:
        risk = "high"
        rec = (
            f"Scaffold at {stiffness_kpa} kPa will deform >{strain_pct:.1f}% "
            f"under cell load. Increase stiffness to >10 kPa or reduce cell density."
        )
    elif strain_pct > 5:
        risk = "medium"
        rec = (
            f"Moderate deformation predicted ({strain_pct:.1f}%). "
            f"Monitor construct integrity at day 3-5."
        )
    else:
        risk = "low"
        rec = (
            f"Scaffold mechanics stable. Predicted strain "
            f"{strain_pct:.1f}% within acceptable range."
        )

    return {
        "max_deformation_um": round(deformation_um, 2),
        "strain_percent": round(strain_pct, 2),
        "stress_kpa": round(stress_kpa_val, 4),
        "failure_risk": risk,
        "recommendation": rec,
        "n_cells_estimated": int(n_cells),
        "collective_force_nN": round(contractile_force_nN, 1),
    }


def predict_stress_distribution(
    stiffness_kpa: float,
    porosity_percent: float = 80.0,
) -> dict:
    """
    Estimate stress concentration factor from porosity.
    High porosity -> stress concentrations at pore walls.
    """
    relative_density = 1 - (porosity_percent / 100)
    if relative_density > 0:
        Kt = 1 + 2 * (1 - relative_density) / relative_density
    else:
        Kt = 10.0

    effective_stiffness = stiffness_kpa * (relative_density ** 2)

    if Kt > 3:
        het_risk = "high"
    elif Kt > 2:
        het_risk = "medium"
    else:
        het_risk = "low"

    return {
        "stress_concentration_factor": round(Kt, 2),
        "effective_local_stiffness_kpa": round(effective_stiffness, 2),
        "heterogeneity_risk": het_risk,
        "recommendation": (
            f"Stress concentration factor {Kt:.1f}x at pore walls. "
            f"Cells near pores experience {effective_stiffness:.1f} kPa locally."
        ),
    }
