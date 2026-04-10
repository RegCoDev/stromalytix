"""
Knowledge Vault — Regex-based protocol extraction engine (Tier 1).

Extracts structured protocol steps from methods-section text using regex
patterns and heuristics. No LLM calls.
"""

import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from ingest import _load_entity_dict

# ---------------------------------------------------------------------------
# Parameter extraction patterns: name -> (regex, default_unit)
# ---------------------------------------------------------------------------

PARAMETER_PATTERNS = {
    "stiffness": (r'(\d+\.?\d*)\s*(?:±\s*\d+\.?\d*)?\s*kPa', "kPa"),
    "porosity": (r'(\d+\.?\d*)\s*(?:±\s*\d+\.?\d*)?\s*%\s*(?:porosity|porous|pore)', "%"),
    "pore_size": (r'pore\s*size\s*(?:of\s+|[:=]\s*)?(\d+\.?\d*)\s*(?:±\s*\d+\.?\d*)?\s*(?:μm|um|µm)', "μm"),
    "concentration_wv": (r'(\d+\.?\d*)\s*%\s*(?:w/v|wt)', "% w/v"),
    "concentration_mg_ml": (r'(\d+\.?\d*)\s*(?:mg/mL|mg/ml)', "mg/mL"),
    "temperature": (r'(\d+\.?\d*)\s*°?\s*C(?:\b)', "°C"),
    "cell_density": (r'(\d+\.?\d*)\s*[×x]\s*10\^?\s*(\d+)\s*(?:cells?(?:/mL)?)', "cells/mL"),
    "uv_dose": (r'(\d+\.?\d*)\s*(?:mW/cm[²2]|J/cm[²2])', "mW/cm²"),
    "crosslink_time": (r'(?:crosslink|UV|photo\w*)\w*\s+(?:for\s+)?(\d+\.?\d*)\s*(s|sec|min|h)', ""),
    "viability": (r'(?:viability|survival)\s*(?:of\s+|was\s+|[:=]\s*)?(\d+\.?\d*)\s*%', "%"),
    "flow_rate": (r'(\d+\.?\d*)\s*(?:μL/min|uL/min|mL/min|mL/h)', ""),
    "print_speed": (r'(?:print|extrusion)\s*speed\s*(?:of\s+|[:=]\s*)?(\d+\.?\d*)\s*(?:mm/s|mm/min)', ""),
    "nozzle_diameter": (r'(?:nozzle|needle)\s*(?:diameter|gauge|size)\s*(?:of\s+|[:=]\s*)?(\d+\.?\d*)\s*(?:μm|um|G|mm)', ""),
    "pressure": (r'(\d+\.?\d*)\s*(?:kPa|psi|bar)\s*(?:pressure)?', ""),
}

# Pre-compile parameter patterns
_PARAM_COMPILED = {
    name: (re.compile(pat, re.IGNORECASE), unit)
    for name, (pat, unit) in PARAMETER_PATTERNS.items()
}

# ---------------------------------------------------------------------------
# Action type keywords
# ---------------------------------------------------------------------------

ACTION_KEYWORDS = {
    "cell_sourcing": ["harvested", "isolated", "obtained from", "purchased from", "ATCC", "thawed", "passage"],
    "cell_expansion": ["expanded", "passaged", "grown to confluence", "subcultured", "proliferated", "maintained in", "scaled up", "bioreactor", "spinner flask", "stirred tank"],
    "material_prep": ["dissolved", "prepared", "mixed", "reconstituted", "hydrated", "sterilized", "filtered", "degassed", "functionalized", "decellularized"],
    "crosslinking": ["crosslinked", "cross-linked", "photocrosslinked", "UV cured", "photopolymerized", "gelled", "gelation", "CaCl2", "transglutaminase", "enzymatic crosslink"],
    "fabrication": ["printed", "bioprinted", "extruded", "cast", "electrospun", "molded", "assembled", "deposited", "layer-by-layer", "textured", "structured"],
    "cell_seeding": ["seeded", "encapsulated", "suspended in", "loaded", "cell-laden", "mixed with cells", "inoculated"],
    "culture": ["cultured", "incubated", "maintained at", "supplemented with", "media changed", "perfused", "CO2", "differentiated", "matured", "conditioned"],
    "assay": ["stained", "imaged", "measured", "quantified", "analyzed", "Live/Dead", "MTT", "ELISA", "qPCR", "Western", "H&E", "immunofluorescence", "SEM", "rheolog", "texture analysis", "tensile", "compression test", "myotube", "fusion index"],
}

# ---------------------------------------------------------------------------
# Duration and equipment patterns
# ---------------------------------------------------------------------------

DURATION_PATTERN = re.compile(
    r'(?:for|during|over|after)\s+(\d+\.?\d*)\s*(seconds?|sec|s|minutes?|min|hours?|h|days?|d|weeks?|wk)',
    re.IGNORECASE,
)

EQUIPMENT_PATTERNS = [
    (re.compile(r'(\d+)[-\s]well\s+plate', re.IGNORECASE), "well plate"),
    (re.compile(r'(Cellink|INKREDIBLE|BioX|Allevi|EnvisionTEC|RegenHU)\s*\w*', re.IGNORECASE), "bioprinter"),
    (re.compile(r'(incubator|biosafety cabinet|centrifuge|rheometer|plate reader)', re.IGNORECASE), "lab equipment"),
    (re.compile(r'(?:UV|LED)\s*(?:lamp|light|source)', re.IGNORECASE), "light source"),
]

# Abbreviations that should NOT trigger sentence splits
_ABBREV = re.compile(r'\b(?:Dr|Mr|Mrs|Ms|Fig|Figs|et al|e\.g|i\.e|vs|approx|ca|no|vol)\.\s*$', re.IGNORECASE)


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def split_sentences(text: str) -> list[str]:
    """Split text on sentence boundaries (period + space), preserving
    common abbreviations like 'Dr.', 'Fig.', 'et al.', 'e.g.', 'i.e.', 'vs.'."""
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    if not text:
        return []

    sentences: list[str] = []
    buf: list[str] = []

    # Split on ". " or ".\n" but then check if it's actually an abbreviation
    parts = re.split(r'(?<=\.)\s+', text)

    for part in parts:
        buf.append(part)
        joined = " ".join(buf)

        # If the current buffer ends with an abbreviation, keep accumulating
        if _ABBREV.search(joined):
            continue

        sentences.append(joined)
        buf = []

    # Flush any remaining buffer
    if buf:
        sentences.append(" ".join(buf))

    return [s.strip() for s in sentences if s.strip()]


def classify_action_type(sentence: str) -> tuple[str, float]:
    """Return (action_type, confidence) for a sentence.

    Scores each action type by counting keyword matches.  Returns the
    highest-scoring type if score > 0, else ("unknown", 0.0).
    Confidence is normalized to 0-1.
    """
    sentence_lower = sentence.lower()
    best_type = "unknown"
    best_score = 0
    max_possible = 0

    for action_type, keywords in ACTION_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw.lower() in sentence_lower)
        max_possible = max(max_possible, len(keywords))
        if count > best_score:
            best_score = count
            best_type = action_type

    if best_score == 0:
        return ("unknown", 0.0)

    # Normalize: score / number of keywords in winning category
    n_keywords = len(ACTION_KEYWORDS[best_type])
    confidence = min(best_score / max(n_keywords, 1), 1.0)
    return (best_type, round(confidence, 3))


def extract_parameters(sentence: str) -> list[dict]:
    """Run all PARAMETER_PATTERNS against sentence.

    Returns list of {"parameter_name", "value", "unit", "source_sentence"}.
    Handles cell_density specially (mantissa x 10^exponent).
    """
    results: list[dict] = []

    for name, (pattern, default_unit) in _PARAM_COMPILED.items():
        m = pattern.search(sentence)
        if not m:
            continue

        if name == "cell_density":
            # Two capture groups: mantissa and exponent
            mantissa = float(m.group(1))
            exponent = int(m.group(2))
            value = mantissa * (10 ** exponent)
            unit = default_unit
        elif name == "crosslink_time":
            # Two groups: number and time unit
            value = float(m.group(1))
            unit = m.group(2)
        elif name == "flow_rate":
            value = float(m.group(1))
            # Extract unit from match context
            unit_m = re.search(r'(μL/min|uL/min|mL/min|mL/h)', m.group(0), re.IGNORECASE)
            unit = unit_m.group(1) if unit_m else default_unit
        elif name == "print_speed":
            value = float(m.group(1))
            unit_m = re.search(r'(mm/s|mm/min)', m.group(0), re.IGNORECASE)
            unit = unit_m.group(1) if unit_m else default_unit
        elif name == "nozzle_diameter":
            value = float(m.group(1))
            unit_m = re.search(r'(μm|um|G|mm)', m.group(0), re.IGNORECASE)
            unit = unit_m.group(1) if unit_m else default_unit
        elif name == "pressure":
            value = float(m.group(1))
            unit_m = re.search(r'(kPa|psi|bar)', m.group(0), re.IGNORECASE)
            unit = unit_m.group(1) if unit_m else default_unit
        else:
            value = float(m.group(1))
            unit = default_unit

        results.append({
            "parameter_name": name,
            "value": value,
            "unit": unit,
            "source_sentence": sentence,
        })

    return results


def extract_materials(sentence: str, entity_dict: dict) -> list[dict]:
    """Match materials from entity_dict against sentence.

    Returns list of {"material_name", "concentration"}.
    Tries to find concentration near the material mention.
    """
    sentence_lower = sentence.lower()
    results: list[dict] = []

    conc_pattern = re.compile(
        r'(\d+\.?\d*)\s*(?:%\s*(?:w/v|wt)|mg/mL|mg/ml|mM|μM|μg/mL|ng/mL)',
        re.IGNORECASE,
    )

    for mat in entity_dict.get("materials", []):
        if mat.lower() in sentence_lower:
            # Try to find concentration near the material mention
            concentration: Optional[str] = None
            idx = sentence_lower.index(mat.lower())
            # Search within a 120-char window around the material mention
            window_start = max(0, idx - 60)
            window_end = min(len(sentence), idx + len(mat) + 60)
            window = sentence[window_start:window_end]
            cm = conc_pattern.search(window)
            if cm:
                concentration = cm.group(0).strip()

            results.append({
                "material_name": mat,
                "concentration": concentration,
            })

    return results


def extract_cells(sentence: str, entity_dict: dict) -> list[dict]:
    """Match cell types from entity_dict.

    Returns list of {"cell_type", "density", "source"}.
    """
    sentence_lower = sentence.lower()
    results: list[dict] = []

    density_pattern = re.compile(
        r'(\d+\.?\d*)\s*[×x]\s*10\^?\s*(\d+)\s*(?:cells?(?:/mL)?)',
        re.IGNORECASE,
    )
    source_pattern = re.compile(
        r'(?:from|obtained from|purchased from|sourced from)\s+([^,.;]+)',
        re.IGNORECASE,
    )

    for ct in entity_dict.get("cell_types", []):
        if ct.lower() in sentence_lower:
            density: Optional[str] = None
            source: Optional[str] = None

            dm = density_pattern.search(sentence)
            if dm:
                mantissa = float(dm.group(1))
                exponent = int(dm.group(2))
                density = f"{mantissa}e{exponent} cells/mL"

            sm = source_pattern.search(sentence)
            if sm:
                source = sm.group(1).strip()

            results.append({
                "cell_type": ct,
                "density": density,
                "source": source,
            })

    return results


def extract_duration(sentence: str) -> Optional[str]:
    """Match DURATION_PATTERN. Returns duration string or None."""
    m = DURATION_PATTERN.search(sentence)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return None


def extract_equipment(sentence: str) -> Optional[str]:
    """Match EQUIPMENT_PATTERNS. Returns equipment description or None."""
    for pattern, category in EQUIPMENT_PATTERNS:
        m = pattern.search(sentence)
        if m:
            return f"{m.group(0)} ({category})"
    return None


def extract_protocol_regex(
    chunk_text: str,
    paper_metadata: dict,
    entity_dict: Optional[dict] = None,
) -> dict:
    """Main orchestrator: extract a structured protocol from methods text.

    Args:
        chunk_text: Raw methods section text.
        paper_metadata: Dict with keys like pmid, target_tissue, biofab_method, etc.
        entity_dict: Pre-loaded entity dict (loads default if None).

    Returns:
        {"protocol": {...}, "steps": [...], "completeness_score": float}
    """
    if entity_dict is None:
        entity_dict = _load_entity_dict()

    sentences = split_sentences(chunk_text)
    if not sentences:
        return {
            "protocol": {
                "target_tissue": paper_metadata.get("target_tissue"),
                "biofab_method": paper_metadata.get("biofab_method"),
                "overall_outcome": None,
            },
            "steps": [],
            "completeness_score": 0.0,
        }

    # Extract per-sentence data
    sentence_data: list[dict] = []
    for sent in sentences:
        action_type, confidence = classify_action_type(sent)
        params = extract_parameters(sent)
        materials = extract_materials(sent, entity_dict)
        cells = extract_cells(sent, entity_dict)
        duration = extract_duration(sent)
        equipment = extract_equipment(sent)

        # Extract temperature from params if present
        temp_str = None
        for p in params:
            if p["parameter_name"] == "temperature":
                temp_str = f"{p['value']} {p['unit']}"
                break

        sentence_data.append({
            "sentence": sent,
            "action_type": action_type,
            "confidence": confidence,
            "parameters": params,
            "materials": materials,
            "cells": cells,
            "duration": duration,
            "temperature": temp_str,
            "equipment": equipment,
        })

    # Group consecutive sentences with same action_type into steps
    steps: list[dict] = []
    current_group: list[dict] = []
    current_type: Optional[str] = None

    for sd in sentence_data:
        if sd["action_type"] == current_type or (current_type is not None and sd["action_type"] == "unknown"):
            # Continue current group (unknown sentences join the preceding group)
            current_group.append(sd)
        else:
            if current_group:
                steps.append(_merge_group(current_group, len(steps) + 1))
            current_group = [sd]
            current_type = sd["action_type"]

    if current_group:
        steps.append(_merge_group(current_group, len(steps) + 1))

    # Calculate completeness
    identified = sum(1 for sd in sentence_data if sd["action_type"] != "unknown")
    completeness_score = round(identified / len(sentence_data), 3) if sentence_data else 0.0

    return {
        "protocol": {
            "target_tissue": paper_metadata.get("target_tissue"),
            "biofab_method": paper_metadata.get("biofab_method"),
            "overall_outcome": None,
        },
        "steps": steps,
        "completeness_score": completeness_score,
    }


def _merge_group(group: list[dict], seq: int) -> dict:
    """Merge a group of sentence-level extractions into a single protocol step."""
    # Use the action type of the first non-unknown sentence
    action_type = "unknown"
    for sd in group:
        if sd["action_type"] != "unknown":
            action_type = sd["action_type"]
            break

    description = " ".join(sd["sentence"] for sd in group)
    raw_text = description

    # Merge all extracted data
    all_params: list[dict] = []
    all_materials: list[dict] = []
    all_cells: list[dict] = []
    duration = None
    temperature = None
    equipment = None

    for sd in group:
        all_params.extend(sd["parameters"])
        all_materials.extend(sd["materials"])
        all_cells.extend(sd["cells"])
        if sd["duration"] and not duration:
            duration = sd["duration"]
        if sd["temperature"] and not temperature:
            temperature = sd["temperature"]
        if sd["equipment"] and not equipment:
            equipment = sd["equipment"]

    # Deduplicate materials by name
    seen_mats: set[str] = set()
    deduped_mats: list[dict] = []
    for mat in all_materials:
        if mat["material_name"] not in seen_mats:
            seen_mats.add(mat["material_name"])
            deduped_mats.append(mat)

    # Deduplicate cells by type
    seen_cells: set[str] = set()
    deduped_cells: list[dict] = []
    for cell in all_cells:
        if cell["cell_type"] not in seen_cells:
            seen_cells.add(cell["cell_type"])
            deduped_cells.append(cell)

    # Truncate description to first 300 chars for the summary
    desc_summary = description[:300].rstrip()
    if len(description) > 300:
        desc_summary += "..."

    return {
        "seq": seq,
        "action_type": action_type,
        "description": desc_summary,
        "duration": duration,
        "temperature": temperature,
        "equipment": equipment,
        "materials": [
            {"name": m["material_name"], "concentration": m["concentration"]}
            for m in deduped_mats
        ],
        "cells": [
            {"cell_type": c["cell_type"], "density": c["density"]}
            for c in deduped_cells
        ],
        "parameters": [
            {"name": p["parameter_name"], "value": p["value"], "unit": p["unit"]}
            for p in all_params
        ],
        "raw_text": raw_text,
    }
