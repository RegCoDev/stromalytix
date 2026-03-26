"""
Structured parameter lookup for literature-derived simulation values.

Provides typed lookups for O2 transport (D_o2, Q_o2, Km_o2),
proliferation kinetics, adhesion energies, scaffold material properties,
and gel penetration / migration parameters. Falls back gracefully when
no match is found, returning a gap report so the LLM brief generator
knows which parameters it must estimate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "parameters"

_CACHE: dict[str, list[dict]] = {}


def _load_table(name: str) -> list[dict]:
    if name in _CACHE:
        return _CACHE[name]
    path = _DATA_DIR / f"{name}.json"
    if not path.exists():
        _CACHE[name] = []
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _CACHE[name] = data
    return data


def _score_match(entry: dict, **filters) -> float:
    """Score how well an entry matches the given filters (0-1, higher=better)."""
    if not filters:
        return 1.0

    total = 0
    matched = 0
    for key, target in filters.items():
        if target is None:
            continue
        total += 1
        val = entry.get(key)
        if val is None:
            continue
        if isinstance(val, str) and isinstance(target, str):
            if target.lower() in val.lower() or val.lower() in target.lower():
                matched += 1
        elif val == target:
            matched += 1

    return matched / max(total, 1)


def lookup(
    table: str,
    parameter: str,
    k: int = 3,
    **filters,
) -> list[dict]:
    """Find the best-matching entries from a parameter table.

    Args:
        table: Table name (e.g. "o2_transport", "proliferation")
        parameter: Parameter name to filter on (e.g. "D_o2", "doubling_time")
        k: Max results to return
        **filters: Additional filters (material, cell_type, etc.)

    Returns:
        List of matching entries sorted by relevance (best first).
    """
    entries = _load_table(table)
    candidates = [e for e in entries if e.get("parameter") == parameter]

    scored = [(e, _score_match(e, **filters)) for e in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)

    return [e for e, s in scored[:k] if s > 0]


def get_o2_diffusion(material: str) -> Optional[dict]:
    """Look up O2 diffusion coefficient for a scaffold material."""
    results = lookup("o2_transport", "D_o2", k=1, material=material)
    return results[0] if results else None


def get_o2_consumption(cell_type: str) -> Optional[dict]:
    """Look up O2 consumption rate for a cell type."""
    results = lookup("o2_transport", "Q_o2", k=1, cell_type=cell_type)
    return results[0] if results else None


def get_doubling_time(
    cell_type: str,
    substrate_stiffness_kpa: Optional[float] = None,
) -> Optional[dict]:
    """Look up doubling time for a cell type."""
    filters: dict = {"cell_type": cell_type}
    if substrate_stiffness_kpa is not None:
        filters["substrate_stiffness_kpa"] = substrate_stiffness_kpa
    results = lookup("proliferation", "doubling_time", k=1, **filters)
    return results[0] if results else None


def get_contact_inhibition(cell_type: str) -> Optional[dict]:
    """Look up contact inhibition threshold for a cell type."""
    results = lookup("proliferation", "contact_inhibition", k=1, cell_type=cell_type)
    return results[0] if results else None


def get_adhesion(cell_type: str, substrate: Optional[str] = None) -> list[dict]:
    """Look up adhesion energies involving a cell type."""
    filters: dict = {"cell_type": cell_type}
    if substrate:
        filters["substrate"] = substrate
    j_scaffold = lookup("adhesion", "J_cell_scaffold", k=2, **filters)
    j_cell = lookup("adhesion", "J_cell_cell", k=2, **filters)
    j_medium = lookup("adhesion", "J_cell_medium", k=1, **filters)
    return j_scaffold + j_cell + j_medium


def get_material_property(
    material: str,
    parameter: str = "stiffness",
) -> Optional[dict]:
    """Look up a scaffold material property."""
    results = lookup("scaffold_materials", parameter, k=1, material=material)
    return results[0] if results else None


def get_km_o2(cell_type: Optional[str] = None) -> Optional[dict]:
    """Look up Michaelis-Menten Km for O2 consumption (half-saturation constant)."""
    filters: dict = {}
    if cell_type:
        filters["cell_type"] = cell_type
    results = lookup("o2_transport", "Km_o2", k=1, **filters)
    return results[0] if results else None


def get_migration_speed(
    cell_type: str,
    material: Optional[str] = None,
) -> Optional[dict]:
    """Look up 3D migration speed for a cell type in a given matrix."""
    filters: dict = {"cell_type": cell_type}
    if material:
        filters["material"] = material
    results = lookup("gel_penetration", "migration_speed", k=1, **filters)
    return results[0] if results else None


def get_mmp_secretion(cell_type: str) -> Optional[dict]:
    """Look up MMP secretion rate for a cell type."""
    results = lookup("gel_penetration", "MMP_secretion_rate", k=1, cell_type=cell_type)
    return results[0] if results else None


def get_critical_pore_size(cell_type: Optional[str] = None) -> Optional[dict]:
    """Look up minimum pore size for cell migration without proteolysis."""
    filters: dict = {}
    if cell_type:
        filters["cell_type"] = cell_type
    results = lookup("gel_penetration", "critical_pore_size", k=1, **filters)
    return results[0] if results else None


def gap_report(profile) -> dict:
    """Analyse a ConstructProfile and report parameter coverage.

    Returns a dict mapping parameter names to either a matched library
    entry (with DOI) or None (indicating the LLM must estimate).
    """
    report: dict = {}

    material = getattr(profile, "scaffold_material", None)
    cell_types = getattr(profile, "cell_types", None) or []
    stiffness = getattr(profile, "stiffness_kpa", None)
    scaffold_type = getattr(profile, "scaffold_type", None)

    # O2 diffusion
    if material:
        report["D_o2"] = _entry_summary(get_o2_diffusion(material))
    else:
        report["D_o2"] = None

    # O2 consumption per cell type
    for ct in cell_types:
        report[f"Q_o2_{ct}"] = _entry_summary(get_o2_consumption(ct))

    # Km_o2 (Michaelis-Menten half-saturation for O2 Hill function)
    km_match = get_km_o2()
    report["Km_o2"] = _entry_summary(km_match)

    # Doubling times
    for ct in cell_types:
        report[f"doubling_time_{ct}"] = _entry_summary(get_doubling_time(ct, stiffness))

    # Adhesion
    for ct in cell_types:
        matches = get_adhesion(ct, material)
        report[f"adhesion_{ct}"] = _entry_summary(matches[0]) if matches else None

    # Material properties
    if material:
        for prop in ("stiffness", "swelling_ratio", "degradation_rate", "pore_size"):
            match = get_material_property(material, prop)
            report[f"{prop}_{material}"] = _entry_summary(match)

    # Gel penetration / migration (relevant for degradable or hybrid scaffolds)
    if scaffold_type in ("degradable", "hybrid", None):
        for ct in cell_types:
            report[f"migration_speed_{ct}"] = _entry_summary(
                get_migration_speed(ct, material)
            )
            report[f"MMP_secretion_{ct}"] = _entry_summary(
                get_mmp_secretion(ct)
            )
        report["critical_pore_size"] = _entry_summary(get_critical_pore_size())

    return report


def _entry_summary(entry: Optional[dict]) -> Optional[dict]:
    if entry is None:
        return None
    return {
        "value": entry.get("value"),
        "unit": entry.get("unit"),
        "confidence": entry.get("confidence"),
        "doi": entry.get("doi"),
        "id": entry.get("id"),
    }


def clear_cache():
    """Clear the in-memory parameter cache (useful after updating JSON files)."""
    _CACHE.clear()
