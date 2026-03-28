"""
Design of Experiments (DOE) for 3D cell culture parameter screening.

Generates factorial and screening designs around a user's protocol,
runs the analysis pipeline on each combination, and returns a results
table for heatmap visualization.

Supports:
- Full factorial (2-3 factors, 2-3 levels each)
- One-at-a-time (OAT) sensitivity screening
- Fractional factorial (Plackett-Burman style for 4+ factors)
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from core.fem_solver import predict_scaffold_deformation, predict_stress_distribution


# ---------------------------------------------------------------------------
# Factor definitions
# ---------------------------------------------------------------------------

@dataclass
class Factor:
    name: str
    unit: str
    low: float
    center: float
    high: float
    key: str  # maps to analysis function kwarg


# Default screening factors for 3D culture
DEFAULT_FACTORS = {
    "stiffness": Factor("Stiffness", "kPa", 1.0, 8.0, 20.0, "stiffness_kpa"),
    "cell_density": Factor("Cell density", "M/mL", 0.5, 5.0, 15.0, "cell_density_millions"),
    "porosity": Factor("Porosity", "%", 40.0, 70.0, 90.0, "porosity_percent"),
}


def factors_from_profile(profile) -> dict[str, Factor]:
    """Create factor definitions centered on the user's actual protocol values."""
    stiffness = getattr(profile, "stiffness_kpa", None) or 8.0
    density_m = (getattr(profile, "cell_density_per_ml", None) or 5e6) / 1e6
    porosity = getattr(profile, "porosity_percent", None) or 70.0

    return {
        "stiffness": Factor(
            "Stiffness", "kPa",
            low=max(0.5, stiffness * 0.25),
            center=stiffness,
            high=min(50.0, stiffness * 3.0),
            key="stiffness_kpa",
        ),
        "cell_density": Factor(
            "Cell density", "M/mL",
            low=max(0.1, density_m * 0.2),
            center=density_m,
            high=min(30.0, density_m * 3.0),
            key="cell_density_millions",
        ),
        "porosity": Factor(
            "Porosity", "%",
            low=max(20.0, porosity - 25.0),
            center=porosity,
            high=min(95.0, porosity + 20.0),
            key="porosity_percent",
        ),
    }


# ---------------------------------------------------------------------------
# Design generators
# ---------------------------------------------------------------------------

def full_factorial(factors: dict[str, Factor], levels: int = 3) -> list[dict]:
    """Generate a full factorial design.

    levels=2: low/high only (2^k runs)
    levels=3: low/center/high (3^k runs)
    """
    factor_list = list(factors.values())
    if levels == 2:
        level_vals = {f.key: [f.low, f.high] for f in factor_list}
    else:
        level_vals = {f.key: [f.low, f.center, f.high] for f in factor_list}

    keys = list(level_vals.keys())
    combos = list(itertools.product(*[level_vals[k] for k in keys]))

    runs = []
    for combo in combos:
        run = {k: v for k, v in zip(keys, combo)}
        runs.append(run)
    return runs


def one_at_a_time(factors: dict[str, Factor], steps: int = 5) -> list[dict]:
    """OAT screening: vary each factor while holding others at center."""
    factor_list = list(factors.values())
    center = {f.key: f.center for f in factor_list}
    runs = []

    for f in factor_list:
        values = np.linspace(f.low, f.high, steps)
        for v in values:
            run = dict(center)
            run[f.key] = float(v)
            run["_varied_factor"] = f.name
            runs.append(run)

    return runs


def plackett_burman_screen(factors: dict[str, Factor]) -> list[dict]:
    """Plackett-Burman-style fractional factorial for 3 factors.

    Uses a fold-over design: 2^(k-1) + center point = 5 runs for k=3.
    Much more efficient than full 3^3 = 27 runs.
    """
    factor_list = list(factors.values())
    k = len(factor_list)

    # For 3 factors, use half-fraction + center + mirror = 5 runs
    runs = []

    # Center point
    center = {f.key: f.center for f in factor_list}
    runs.append(dict(center))

    # Half-fraction corners
    signs = list(itertools.product([-1, 1], repeat=k))
    # Take half (balanced subset)
    for s in signs[:len(signs) // 2 + 1]:
        run = {}
        for i, f in enumerate(factor_list):
            if s[i] == -1:
                run[f.key] = f.low
            else:
                run[f.key] = f.high
        runs.append(run)

    return runs


# ---------------------------------------------------------------------------
# Run analysis on a design
# ---------------------------------------------------------------------------

def evaluate_design(runs: list[dict]) -> list[dict]:
    """Run the mechanics analysis pipeline on each design point.

    Returns the input runs enriched with output metrics.
    """
    results = []
    for run in runs:
        stiffness = run.get("stiffness_kpa", 8.0)
        density_m = run.get("cell_density_millions", 5.0)
        porosity = run.get("porosity_percent", 70.0)

        deform = predict_scaffold_deformation(
            stiffness_kpa=stiffness,
            cell_density_per_ml=density_m * 1e6,
        )
        stress = predict_stress_distribution(
            stiffness_kpa=stiffness,
            porosity_percent=porosity,
        )

        result = dict(run)
        result["strain_pct"] = deform["strain_percent"]
        result["deformation_um"] = deform["max_deformation_um"]
        result["integrity_risk"] = deform["failure_risk"]
        result["stress_kt"] = stress["stress_concentration_factor"]
        result["effective_stiffness_kpa"] = stress["effective_local_stiffness_kpa"]
        result["stress_risk"] = stress["heterogeneity_risk"]

        # Composite score: 0 (best) to 1 (worst)
        strain_score = min(1.0, deform["strain_percent"] / 15.0)
        kt_score = min(1.0, (stress["stress_concentration_factor"] - 1.0) / 9.0)
        result["composite_risk_score"] = round(0.6 * strain_score + 0.4 * kt_score, 3)

        results.append(result)

    return results


def find_optimal(results: list[dict]) -> dict:
    """Find the design point with the lowest composite risk score."""
    if not results:
        return {}
    return min(results, key=lambda r: r.get("composite_risk_score", 999))


def design_summary(results: list[dict], factors: dict[str, Factor]) -> str:
    """Generate a one-paragraph summary of the DOE results."""
    if not results:
        return "No design points evaluated."

    optimal = find_optimal(results)
    worst = max(results, key=lambda r: r.get("composite_risk_score", 0))

    factor_list = list(factors.values())
    opt_params = ", ".join(
        f"{f.name}={optimal.get(f.key, '?'):.1f} {f.unit}"
        for f in factor_list
    )
    worst_params = ", ".join(
        f"{f.name}={worst.get(f.key, '?'):.1f} {f.unit}"
        for f in factor_list
    )

    return (
        f"**Best combination:** {opt_params} "
        f"(strain {optimal['strain_pct']:.2f}%, Kt {optimal['stress_kt']:.1f}x, "
        f"risk score {optimal['composite_risk_score']:.3f}). "
        f"**Worst:** {worst_params} "
        f"(strain {worst['strain_pct']:.2f}%, Kt {worst['stress_kt']:.1f}x, "
        f"risk score {worst['composite_risk_score']:.3f}). "
        f"Screened {len(results)} combinations."
    )
