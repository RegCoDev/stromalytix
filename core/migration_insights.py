"""
Migration & gradient insights for tissue-engineering constructs.

Generates qualitative hypotheses and quantitative estimates about how
fabricated (engineered) and spontaneous (emergent) gradients drive cell
migration, based on the construct profile and the parameter library.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from core.models import ConstructProfile
from core import parameter_library as plib


@dataclass
class Insight:
    category: str          # "gradient_type" grouping
    headline: str          # one-line qualitative statement
    detail: str            # quantitative backing / mechanism
    confidence: str        # high / medium / low
    sources: list[str] = field(default_factory=list)  # DOIs


@dataclass
class MigrationReport:
    insights: list[Insight] = field(default_factory=list)

    @property
    def by_category(self) -> dict[str, list[Insight]]:
        out: dict[str, list[Insight]] = {}
        for ins in self.insights:
            out.setdefault(ins.category, []).append(ins)
        return out


def analyse(profile: ConstructProfile) -> MigrationReport:
    """Generate migration and gradient insights for the given construct."""
    rpt = MigrationReport()
    material = (profile.scaffold_material or "").strip()
    material_lower = material.lower()
    cell_types = profile.cell_types or []
    scaffold_type = (profile.scaffold_type or "").strip().lower()
    pore_um = profile.pore_size_um
    dims = profile.scaffold_dimensions_mm or [4.0, 4.0, 2.0]
    half_thickness_mm = min(dims) / 2.0
    duration_days = profile.culture_duration_days or 14
    o2_pct = profile.oxygen_tension_percent or 20.0

    _spontaneous_o2_gradient(rpt, material, material_lower, cell_types,
                             half_thickness_mm, duration_days, o2_pct)
    _nutrient_waste_gradients(rpt, material_lower, half_thickness_mm,
                              profile.media_change_interval_hours,
                              profile.medium_volume_ml, duration_days)
    _stiffness_gradient(rpt, material_lower, scaffold_type, profile.stiffness_kpa)
    _geometric_guidance(rpt, scaffold_type, pore_um, profile.scaffold_architecture)
    _migration_kinetics(rpt, material, material_lower, scaffold_type,
                        cell_types, pore_um, half_thickness_mm, duration_days)
    _degradation_front(rpt, material_lower, scaffold_type, cell_types, duration_days)

    return rpt


# ── Individual gradient analyses ──────────────────────────────────────


def _spontaneous_o2_gradient(
    rpt: MigrationReport,
    material: str,
    material_lower: str,
    cell_types: list[str],
    half_mm: float,
    duration_days: int,
    o2_pct: float,
):
    d_match = plib.get_o2_diffusion(material) if material else None
    d_val = d_match["value"] if d_match else 2.5e-5  # fallback: dilute hydrogel
    doi_d = d_match.get("doi", "") if d_match else ""

    q_vals = []
    for ct in cell_types:
        q_match = plib.get_o2_consumption(ct)
        if q_match:
            q_vals.append((ct, q_match["value"], q_match.get("doi", "")))

    if not q_vals:
        q_vals = [("generic mammalian", 2e-17, "")]

    ct_name, q_val, doi_q = q_vals[0]
    density = 1e6  # cells/mL default

    half_cm = half_mm * 0.1
    # Krogh cylinder: critical thickness L_crit = sqrt(2 * D * C0 / (q * rho))
    c0_mol = o2_pct / 100.0 * 0.21e-3  # mol/cm3 at ~20% O2 in medium, approx
    denom = q_val * density * 1e6  # consumption per cm3
    if denom > 0 and c0_mol > 0:
        l_crit_cm = math.sqrt(2 * d_val * c0_mol / denom)
        l_crit_mm = l_crit_cm * 10.0
    else:
        l_crit_mm = 99.0

    sources = [s for s in [doi_d, doi_q] if s]

    if l_crit_mm < half_mm:
        severity = "steep"
        rpt.insights.append(Insight(
            "Spontaneous O2 Gradient",
            f"A steep O2 gradient will form spontaneously within this construct.",
            f"Estimated O2 penetration depth: ~{l_crit_mm:.2f} mm "
            f"(construct half-thickness {half_mm:.1f} mm). Cells beyond this depth "
            f"will experience hypoxia (<1% O2), which can act as a potent chemotactic "
            f"signal driving migration toward the periphery or inducing HIF-1α–mediated "
            f"phenotype shifts. This is an emergent gradient — not engineered.",
            "high" if d_match else "medium",
            sources,
        ))
        rpt.insights.append(Insight(
            "Spontaneous O2 Gradient",
            "Hypoxia-driven migration is expected to bias cell distribution toward the surface.",
            f"At cell density ~10⁶/mL with Q_o2 = {q_val:.1e} mol/cell/s in {material or 'hydrogel'}, "
            f"the central ~{max(0, (half_mm - l_crit_mm)*2):.1f} mm will be chronically hypoxic "
            f"by day 2–3. Cells capable of aerotaxis will migrate outward; non-motile cells will die.",
            "medium",
            sources,
        ))
    else:
        rpt.insights.append(Insight(
            "Spontaneous O2 Gradient",
            "O2 gradients in this construct are expected to be mild.",
            f"Estimated O2 penetration depth (~{l_crit_mm:.1f} mm) exceeds the construct "
            f"half-thickness ({half_mm:.1f} mm). Cells throughout the construct should remain "
            f"above the hypoxic threshold. O2-driven chemotaxis is unlikely to be a dominant "
            f"migration cue in this geometry.",
            "high" if d_match else "medium",
            sources,
        ))

    # Gradient steepness estimate
    if l_crit_mm < half_mm and l_crit_mm > 0:
        gradient_pct_per_mm = (o2_pct / l_crit_mm)
        rpt.insights.append(Insight(
            "Spontaneous O2 Gradient",
            f"O2 gradient steepness: ~{gradient_pct_per_mm:.1f}% O2 per mm.",
            f"Published chemotaxis thresholds are typically 1–3% O2 per mm. "
            f"{'This gradient exceeds the threshold and will likely drive directed migration.' if gradient_pct_per_mm > 1 else 'This gradient is below typical chemotactic thresholds — migration may be stochastic rather than directed.'}",
            "medium",
            sources,
        ))


def _nutrient_waste_gradients(
    rpt: MigrationReport,
    material_lower: str,
    half_mm: float,
    media_interval_h: Optional[float],
    medium_ml: Optional[float],
    duration_days: int,
):
    interval = media_interval_h or 48.0
    vol = medium_ml or 2.0

    if interval >= 48 and half_mm > 1.0:
        rpt.insights.append(Insight(
            "Nutrient / Waste Gradients",
            "Glucose depletion and lactate accumulation will create secondary gradients.",
            f"With {interval:.0f}-hour media changes and {vol:.1f} mL medium, glucose "
            f"in the scaffold interior will decline faster than at the surface. Lactate and "
            f"CO2 accumulate centrally, lowering local pH. These metabolic gradients reinforce "
            f"the O2 gradient — cells experience compound stress toward the core.",
            "medium",
        ))
    else:
        rpt.insights.append(Insight(
            "Nutrient / Waste Gradients",
            "Nutrient gradients are expected to be manageable with current protocol.",
            f"Media changed every {interval:.0f} h with {vol:.1f} mL volume. "
            f"For a construct with half-thickness {half_mm:.1f} mm, diffusion of glucose "
            f"(D ~ 6e-6 cm²/s) is ~5× faster than O2 consumption-driven depletion at this scale. "
            f"Waste products should not reach toxic levels between changes.",
            "low",
        ))


def _stiffness_gradient(
    rpt: MigrationReport,
    material_lower: str,
    scaffold_type: str,
    stiffness_kpa: Optional[float],
):
    degradable = scaffold_type in ("degradable", "hybrid", "")

    if degradable and stiffness_kpa:
        rpt.insights.append(Insight(
            "Fabricated / Emergent Stiffness Gradient",
            "Degradation will create a time-evolving stiffness gradient (durotaxis cue).",
            f"As cells at the scaffold surface degrade the matrix (initial stiffness "
            f"~{stiffness_kpa} kPa), the periphery softens while the interior retains its "
            f"original stiffness. This creates a stiffness gradient pointing inward, which can "
            f"drive durotaxis (migration toward stiffer substrate) for mesenchymal cell types. "
            f"Competing with the outward O2 gradient, the net migration direction depends on "
            f"cell type and gradient magnitudes.",
            "medium",
        ))
    elif stiffness_kpa and stiffness_kpa > 50:
        rpt.insights.append(Insight(
            "Fabricated / Emergent Stiffness Gradient",
            "Rigid scaffold — no significant stiffness gradients expected.",
            f"At {stiffness_kpa} kPa (non-degradable), the scaffold stiffness is spatially "
            f"uniform and stable over time. Durotaxis is not expected to be a migration driver. "
            f"Cell positioning will be governed by initial seeding and surface topology.",
            "high",
        ))


def _geometric_guidance(
    rpt: MigrationReport,
    scaffold_type: str,
    pore_um: Optional[float],
    architecture: Optional[str],
):
    arch = (architecture or "").lower()

    if arch in ("gyroid", "schwarz_p", "diamond", "lidinoid"):
        rpt.insights.append(Insight(
            "Contact Guidance (Geometric)",
            f"TPMS ({arch}) architecture provides continuous, curved surfaces for contact guidance.",
            f"Cells migrating on TPMS surfaces experience continuous curvature changes that "
            f"can bias migration direction (curvotaxis). Unlike straight channels, TPMS pores "
            f"are fully interconnected — there are no dead ends. This promotes uniform cell "
            f"distribution if pore size allows migration."
            + (f" At {pore_um} µm pore size, cells can freely traverse the pore network." if pore_um and pore_um > 50 else ""),
            "medium",
        ))
    elif arch in ("woodpile", "grid"):
        rpt.insights.append(Insight(
            "Contact Guidance (Geometric)",
            f"Filament lattice ({arch}) creates directional channels for anisotropic migration.",
            f"The parallel strut arrangement creates preferential migration paths along "
            f"the filament direction. Cells tend to align with and migrate along fibers "
            f"(contact guidance). This can produce anisotropic cell distributions — denser "
            f"along filaments, sparser in cross-directions.",
            "medium",
        ))

    if pore_um:
        if pore_um > 200:
            rpt.insights.append(Insight(
                "Contact Guidance (Geometric)",
                "Large pore size favors migration but reduces cell-scaffold contact.",
                f"At {pore_um} µm, pores are >10× typical cell diameter. Cells can "
                f"migrate freely through the pore network but have fewer anchor points. "
                f"Migration speed may be high but directionality low (random walk).",
                "medium",
            ))
        elif pore_um > 50:
            rpt.insights.append(Insight(
                "Contact Guidance (Geometric)",
                "Moderate pore size balances migration and scaffold contact.",
                f"At {pore_um} µm, pores are ~3–15× cell diameter. Cells maintain "
                f"contact with pore walls while migrating, enabling both contact guidance "
                f"and efficient nutrient transport. This is near the optimal range for "
                f"most tissue engineering applications.",
                "high",
            ))
        else:
            rpt.insights.append(Insight(
                "Contact Guidance (Geometric)",
                "Small pore size will severely restrict cell migration.",
                f"At {pore_um} µm, pores approach or are below the nuclear diameter "
                f"(~12 µm). Cells must deform their nucleus to squeeze through, making "
                f"migration very slow or impossible without proteolytic ECM degradation.",
                "high",
                ["10.1083/jcb.201210152"],
            ))


def _migration_kinetics(
    rpt: MigrationReport,
    material: str,
    material_lower: str,
    scaffold_type: str,
    cell_types: list[str],
    pore_um: Optional[float],
    half_mm: float,
    duration_days: int,
):
    for ct in cell_types:
        mig = plib.get_migration_speed(ct, material or None)
        if mig:
            speed = mig["value"]  # µm/h
            doi = mig.get("doi", "")
            depth_um_per_day = speed * 24 * 0.7  # ~70% efficiency (persistence, turning)
            total_depth_um = depth_um_per_day * duration_days
            total_depth_mm = total_depth_um / 1000.0

            if total_depth_mm >= half_mm:
                verdict = (
                    f"cells can theoretically migrate through the full construct "
                    f"half-thickness ({half_mm:.1f} mm) within the {duration_days}-day culture."
                )
            else:
                verdict = (
                    f"cells will penetrate ~{total_depth_mm:.2f} mm in {duration_days} days — "
                    f"{'roughly half' if total_depth_mm > half_mm * 0.4 else 'only a fraction of'} "
                    f"the construct half-thickness ({half_mm:.1f} mm)."
                )

            rpt.insights.append(Insight(
                "Migration Kinetics",
                f"{ct}: expected migration speed ~{speed} µm/h in {material or 'matrix'}.",
                f"At ~{speed} µm/h with ~70% persistence factor, {verdict} "
                f"{'Perfusion or chemotactic gradients could accelerate this.' if total_depth_mm < half_mm else ''}",
                mig.get("confidence", "medium"),
                [doi] if doi else [],
            ))
        else:
            non_degradable = material_lower in (
                "pcl", "plga", "pdms", "polystyrene", "peg", "alginate",
            )
            if non_degradable:
                rpt.insights.append(Insight(
                    "Migration Kinetics",
                    f"{ct}: migration through {material or 'this scaffold'} is not expected.",
                    f"This material is non-degradable or lacks adhesion ligands. Cells will "
                    f"remain on the surface or in pre-formed pores. Bulk infiltration requires "
                    f"a degradable matrix component.",
                    "high",
                ))
            else:
                rpt.insights.append(Insight(
                    "Migration Kinetics",
                    f"{ct}: no published 3D migration speed for this cell-matrix combination.",
                    f"Migration in {material or 'unspecified matrix'} cannot be estimated "
                    f"from the current library. Consider Boyden chamber or time-lapse experiments "
                    f"to calibrate.",
                    "low",
                ))


def _degradation_front(
    rpt: MigrationReport,
    material_lower: str,
    scaffold_type: str,
    cell_types: list[str],
    duration_days: int,
):
    if scaffold_type not in ("degradable", "hybrid", ""):
        return

    mat_match = plib.get_material_property(material_lower, "degradation_rate")
    if not mat_match:
        return

    half_life = mat_match.get("value")
    doi = mat_match.get("doi", "")
    if not half_life or half_life <= 0:
        return

    unit = mat_match.get("unit", "days")
    if "week" in unit:
        half_life_days = half_life * 7
    elif "month" in unit:
        half_life_days = half_life * 30
    else:
        half_life_days = half_life

    fraction_remaining = 0.5 ** (duration_days / half_life_days) if half_life_days > 0 else 0

    rpt.insights.append(Insight(
        "Degradation-Driven Migration",
        f"Scaffold will degrade to ~{fraction_remaining*100:.0f}% of original by day {duration_days}.",
        f"Degradation half-life: {half_life} {unit}. As the matrix degrades, pore size increases "
        f"and stiffness decreases — both of which facilitate migration. MMP-secreting cells at "
        f"the invasion front create a self-reinforcing degradation gradient: "
        f"cells degrade → pores open → more cells migrate in → more degradation. "
        f"This positive feedback loop can accelerate infiltration beyond what constant-speed "
        f"estimates predict.",
        mat_match.get("confidence", "medium"),
        [doi] if doi else [],
    ))
