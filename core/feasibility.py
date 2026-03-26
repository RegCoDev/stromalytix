"""
Feasibility analysis for tissue-engineering construct proposals.

Cross-references the user's desired construct against the parameter library
to classify each simulation axis as FEASIBLE / MARGINAL / ASPIRATIONAL and
suggest concrete alternatives where data is weak.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from core.models import ConstructProfile, VarianceReport
from core import parameter_library as plib


@dataclass
class FeasibilityItem:
    axis: str
    tier: str  # "feasible", "marginal", "aspirational"
    detail: str
    suggestion: Optional[str] = None


@dataclass
class FeasibilityReport:
    items: list[FeasibilityItem] = field(default_factory=list)
    overall: str = "feasible"

    @property
    def feasible(self) -> list[FeasibilityItem]:
        return [i for i in self.items if i.tier == "feasible"]

    @property
    def marginal(self) -> list[FeasibilityItem]:
        return [i for i in self.items if i.tier == "marginal"]

    @property
    def aspirational(self) -> list[FeasibilityItem]:
        return [i for i in self.items if i.tier == "aspirational"]


_NON_DEGRADABLE = {"pcl", "plga", "pdms", "polystyrene", "peg"}

_MATERIAL_STIFFNESS_RANGES: dict[str, tuple[float, float]] = {
    "gelma": (0.5, 50),
    "collagen": (0.1, 5),
    "fibrin": (0.05, 2),
    "alginate": (1, 100),
    "matrigel": (0.05, 0.5),
    "pcl": (200_000, 400_000),
    "plga": (1_000_000, 7_000_000),
    "pdms": (5, 3_000),
    "peg": (1, 500),
    "ha": (0.5, 100),
    "silk fibroin": (1, 30),
}


def analyse(profile: ConstructProfile, report: Optional[VarianceReport] = None) -> FeasibilityReport:
    """Run all feasibility checks against the parameter library."""
    fr = FeasibilityReport()
    material = (profile.scaffold_material or "").strip().lower()
    cell_types = profile.cell_types or []
    scaffold_type = (profile.scaffold_type or "").strip().lower()

    _check_o2_transport(fr, material, cell_types)
    _check_proliferation(fr, cell_types, profile.stiffness_kpa)
    _check_adhesion(fr, cell_types, material)
    _check_material_stiffness(fr, material, profile.stiffness_kpa)
    _check_pore_vs_migration(fr, material, scaffold_type, cell_types, profile.pore_size_um)
    _check_culture_duration(fr, profile, material, cell_types)
    _check_scaffold_migration(fr, scaffold_type, material, cell_types)

    tiers = [i.tier for i in fr.items]
    if "aspirational" in tiers:
        fr.overall = "aspirational"
    elif "marginal" in tiers:
        fr.overall = "marginal"
    else:
        fr.overall = "feasible"
    return fr


def _check_o2_transport(fr: FeasibilityReport, material: str, cell_types: list[str]):
    if not material:
        fr.items.append(FeasibilityItem(
            "O2 Diffusion in Scaffold",
            "marginal",
            "No scaffold material specified — O2 transport will use generic hydrogel defaults.",
            "Specify a material (e.g. collagen, alginate) for literature-grounded D_o2.",
        ))
        return

    match = plib.get_o2_diffusion(material)
    if match:
        conf = match.get("confidence", "medium")
        if conf == "high":
            fr.items.append(FeasibilityItem(
                "O2 Diffusion in Scaffold",
                "feasible",
                f"D_o2 in {material} is literature-backed ({match.get('doi', 'N/A')}).",
            ))
        else:
            fr.items.append(FeasibilityItem(
                "O2 Diffusion in Scaffold",
                "marginal",
                f"D_o2 for {material} exists but confidence is {conf}.",
                "Consider experimental validation of O2 diffusivity in your specific formulation.",
            ))
    else:
        alts = []
        for probe in ("collagen", "alginate", "fibrin", "agarose"):
            if plib.get_o2_diffusion(probe):
                alts.append(probe)
        suggestion = None
        if alts:
            suggestion = f"No published D_o2 for {material}. Materials with known D_o2: {', '.join(alts)}."
        fr.items.append(FeasibilityItem(
            "O2 Diffusion in Scaffold",
            "aspirational",
            f"No O2 diffusion data found for {material} — simulation will rely on LLM estimate.",
            suggestion,
        ))

    for ct in cell_types:
        match = plib.get_o2_consumption(ct)
        if match:
            fr.items.append(FeasibilityItem(
                f"O2 Consumption ({ct})",
                "feasible",
                f"Q_o2 for {ct} is literature-backed.",
            ))
        else:
            fr.items.append(FeasibilityItem(
                f"O2 Consumption ({ct})",
                "marginal",
                f"No specific Q_o2 for {ct} — will use generic mammalian cell estimate.",
                "Consider using a well-characterised cell type (HepG2, MSC, HUVEC) for O2 validation.",
            ))


def _check_proliferation(fr: FeasibilityReport, cell_types: list[str], stiffness: Optional[float]):
    for ct in cell_types:
        match = plib.get_doubling_time(ct, stiffness)
        if match:
            fr.items.append(FeasibilityItem(
                f"Proliferation Kinetics ({ct})",
                "feasible",
                f"Doubling time for {ct} available ({match.get('value')} {match.get('unit', 'h')}).",
            ))
        else:
            fr.items.append(FeasibilityItem(
                f"Proliferation Kinetics ({ct})",
                "marginal",
                f"No doubling time for {ct} — will use a generic 24 h estimate.",
                "Check ATCC datasheets for your specific cell line.",
            ))


def _check_adhesion(fr: FeasibilityReport, cell_types: list[str], material: str):
    for ct in cell_types:
        matches = plib.get_adhesion(ct, material or None)
        if matches:
            fr.items.append(FeasibilityItem(
                f"Cell-ECM Adhesion ({ct})",
                "feasible",
                f"J-values for {ct} found in library ({len(matches)} entries).",
            ))
        else:
            fr.items.append(FeasibilityItem(
                f"Cell-ECM Adhesion ({ct})",
                "marginal",
                f"No CC3D J-values for {ct} — using Foty & Steinberg generic tissue estimates.",
                "Hanging-drop or micropipette aspiration data for your cells would improve accuracy.",
            ))


def _check_material_stiffness(fr: FeasibilityReport, material: str, target_kpa: Optional[float]):
    if not material or target_kpa is None:
        return
    known_range = _MATERIAL_STIFFNESS_RANGES.get(material)
    if known_range is None:
        return
    lo, hi = known_range
    if lo <= target_kpa <= hi:
        fr.items.append(FeasibilityItem(
            "Target Stiffness",
            "feasible",
            f"{target_kpa} kPa is achievable with {material} (published range {lo}–{hi} kPa).",
        ))
    else:
        fr.items.append(FeasibilityItem(
            "Target Stiffness",
            "aspirational",
            f"{target_kpa} kPa is outside the published range for {material} ({lo}–{hi} kPa).",
            f"Achievable range for {material}: {lo}–{hi} kPa. "
            "Consider cross-linking optimisation or a different material.",
        ))


def _check_pore_vs_migration(
    fr: FeasibilityReport, material: str, scaffold_type: str,
    cell_types: list[str], pore_um: Optional[float],
):
    if not pore_um:
        return
    crit = plib.get_critical_pore_size()
    if not crit:
        return
    crit_val = crit.get("value", 7.0)
    if pore_um >= crit_val:
        fr.items.append(FeasibilityItem(
            "Pore Size vs Cell Migration",
            "feasible",
            f"Pore size {pore_um} um exceeds critical migration threshold ({crit_val} um).",
        ))
    else:
        fr.items.append(FeasibilityItem(
            "Pore Size vs Cell Migration",
            "aspirational",
            f"Pore size {pore_um} um is below the critical threshold for protease-independent migration ({crit_val} um).",
            "Cells will require MMP-driven proteolysis to migrate — viable in degradable gels but not rigid scaffolds.",
        ))


def _check_culture_duration(
    fr: FeasibilityReport, profile: ConstructProfile,
    material: str, cell_types: list[str],
):
    days = profile.culture_duration_days
    if not days:
        return

    dims = profile.scaffold_dimensions_mm or [4.0, 4.0, 4.0]
    half_thickness_mm = min(dims) / 2.0

    d_match = plib.get_o2_diffusion(material) if material else None
    if d_match and d_match.get("value"):
        d_o2_cm2s = d_match["value"]
        half_cm = half_thickness_mm * 0.1
        penetration_time_s = (half_cm ** 2) / (2 * d_o2_cm2s)
        penetration_time_h = penetration_time_s / 3600

        if penetration_time_h < 1.0:
            fr.items.append(FeasibilityItem(
                "O2 Penetration vs Culture Duration",
                "feasible",
                f"O2 reaches centre in ~{penetration_time_h:.1f} h — "
                f"well within the {days}-day culture.",
            ))
        elif penetration_time_h < days * 24 * 0.1:
            fr.items.append(FeasibilityItem(
                "O2 Penetration vs Culture Duration",
                "marginal",
                f"O2 steady-state reached in ~{penetration_time_h:.0f} h. "
                "A necrotic core may develop during the initial transient.",
                "Consider perfusion or reducing scaffold thickness.",
            ))
        else:
            fr.items.append(FeasibilityItem(
                "O2 Penetration vs Culture Duration",
                "aspirational",
                f"O2 penetration time (~{penetration_time_h:.0f} h) is a large fraction of the culture. "
                "Severe hypoxia and central necrosis are likely.",
                "Use perfusion bioreactor, reduce scaffold thickness, or increase porosity.",
            ))


def _check_scaffold_migration(
    fr: FeasibilityReport, scaffold_type: str, material: str, cell_types: list[str],
):
    if not cell_types:
        return
    non_deg = material in _NON_DEGRADABLE or scaffold_type in ("rigid", "non-degradable")
    if non_deg:
        fr.items.append(FeasibilityItem(
            "Cell Penetration into Scaffold",
            "aspirational" if scaffold_type not in ("", "rigid", "non-degradable") else "marginal",
            f"{'Non-degradable' if non_deg else 'Rigid'} scaffold — "
            "cells are confined to the surface / pre-formed pores.",
            "If bulk cell infiltration is needed, consider a degradable hydrogel (GelMA, collagen, fibrin).",
        ))
        return

    for ct in cell_types:
        mig = plib.get_migration_speed(ct, material or None)
        if mig:
            fr.items.append(FeasibilityItem(
                f"Cell Migration ({ct})",
                "feasible",
                f"3D migration speed for {ct} is literature-backed ({mig.get('value')} {mig.get('unit', 'um/h')}).",
            ))
        else:
            fr.items.append(FeasibilityItem(
                f"Cell Migration ({ct})",
                "marginal",
                f"No migration data for {ct} in {material or 'unspecified matrix'}.",
                "Time-lapse confocal of cells in your specific gel would calibrate this.",
            ))
