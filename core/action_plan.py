"""
Methods & materials action checklist from parameter gaps and feasibility tiers.
"""

from __future__ import annotations

from typing import Any

from core.models import ConstructProfile, VarianceReport
from core import parameter_library as plib
from core.feasibility import analyse as feasibility_analyse


def build_action_checklist(
    profile: ConstructProfile,
    report: VarianceReport,
) -> list[dict[str, Any]]:
    """
    Rows for the Methods & materials tab.

    Keys: priority, parameter, what_to_do, why, source_type
    """
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_row(
        key: str,
        priority: str,
        parameter: str,
        what_to_do: str,
        why: str,
        source_type: str,
    ) -> None:
        if key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "priority": priority,
                "parameter": parameter,
                "what_to_do": what_to_do,
                "why": why,
                "source_type": source_type,
            }
        )

    feas = feasibility_analyse(profile, report)

    for it in feas.aspirational:
        add_row(
            f"feas_asp_{it.axis}",
            "high",
            it.axis,
            it.suggestion or "Gather literature or run a pilot measurement for this axis.",
            it.detail,
            "literature or pilot experiment",
        )
    for it in feas.marginal:
        add_row(
            f"feas_mar_{it.axis}",
            "medium",
            it.axis,
            it.suggestion or "Confirm with a datasheet or small experiment.",
            it.detail,
            "datasheet or pilot",
        )

    gaps = plib.gap_report(profile)
    for param_name, entry in sorted(gaps.items()):
        if entry is None:
            add_row(
                f"gap_none_{param_name}",
                "high",
                param_name.replace("_", " ").title(),
                f"Find or measure a value for {param_name} (simulation uses estimates until grounded).",
                "Missing from parameter library for this construct; increases uncertainty in CC3D and benchmarks.",
                "literature search",
            )
            continue
        conf = (entry.get("confidence") or "").lower()
        if conf == "low":
            add_row(
                f"gap_low_{param_name}",
                "medium",
                param_name.replace("_", " ").title(),
                "Replace low-confidence library value with a direct measurement or stronger citation.",
                "Current value is flagged low confidence in the curated library.",
                "paper or measurement",
            )

    domain = getattr(profile, "application_domain", None) or ""
    if domain == "cellular_agriculture":
        add_row(
            "cellag_serum",
            "high",
            "Serum-free / growth factor panel",
            "Document FGF-2, IGF-1, and medium costs for scale-up; align with differentiation timing.",
            "Cell-ag economics and batch consistency depend on defined medium.",
            "supplier datasheet",
        )
        add_row(
            "cellag_fusion",
            "medium",
            "Myoblast fusion / differentiation",
            "Plan fusion markers (e.g. MHC) and timing vs. proliferation phase for your species.",
            "CC3D defaults do not encode full fusion physics; experimental ground truth matters.",
            "pilot assay",
        )

    risk_red = [k for k, v in (report.risk_flags or {}).items() if v == "red"]
    for rk in risk_red[:8]:
        add_row(
            f"risk_red_{rk}",
            "high",
            rk.replace("_", " ").title(),
            "Mitigate or re-benchmark this parameter; variance report flagged red risk.",
            "Deviation from published safe ranges for this readout.",
            "literature + assay",
        )

    # Experimentalist-facing anchors (not only parameter-library maintenance)
    cells = ", ".join(profile.cell_types or []) or "your cell types"
    mat = profile.scaffold_material or "your matrix/bioink"
    readout = profile.primary_readout or "your primary readout"
    add_row(
        "exp_supplies_reagents",
        "high",
        "Supplies, reagents, and traceability",
        f"Draft a bill-of-materials: medium (and serum-free panel if applicable), {mat}, "
        f"passaging reagents, plastics/bioreactor consumables for {cells}. "
        "Note supplier, catalog hints where known, and which items need lot-specific COAs.",
        "Reviewers, QA, and repro all depend on what actually went into the dish.",
        "supplier datasheets / lab inventory",
    )
    add_row(
        "exp_modeling_followup",
        "medium",
        "Further modeling and simulation",
        "After you ground key numbers, re-benchmark vs literature; use scaffold/FEA views for mechanics; "
        "run or extend CC3D briefs for migration/O₂ hypotheses. Log assumptions (steps, lattice, adhesion).",
        "Cheap in silico iterations reduce blind wet-lab sweeps when fields or mechanics matter.",
        "Stromalytix simulation tab + notebook",
    )
    add_row(
        "exp_people_cores",
        "medium",
        "People, cores, CROs, and collaborators",
        "Line up owners for imaging, histology, mechanical testing, flow cytometry, and (if needed) omics/bioinformatics. "
        f"Flag when {readout} needs a core vs a CRO (GLP, specialized biomechanics, etc.).",
        "Biofabrication spans skills; naming who to ask prevents stalled experiments.",
        "core facility / institutional partners",
    )
    add_row(
        "exp_further_reading",
        "low",
        "Further reading and method standards",
        "Use the variance report references; add 2–3 methods papers for your exact readout and construct class. "
        "Check relevant ASTM/ISO or FDA guidance if you are in a regulated path.",
        "Aligns how you write methods with what facilities and reviewers expect.",
        "PMIDs from report + standards orgs",
    )

    rows.sort(key=lambda r: (0 if r["priority"] == "high" else 1, r["parameter"]))
    return rows


def checklist_to_prompt_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(no checklist items)"
    lines = []
    for r in rows:
        why_snip = r["why"][:200] + ("…" if len(r["why"]) > 200 else "")
        lines.append(
            f"- [{r['priority']}] {r['parameter']}: {r['what_to_do']} "
            f"(why: {why_snip}; source: {r['source_type']})"
        )
    return "\n".join(lines)
