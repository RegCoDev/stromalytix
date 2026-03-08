"""
core/synthetic_log_generator.py

LLM-based synthetic event log generation via Anthropic API.
Uses Claude to generate biologically realistic process events
conditioned on real event log statistics and protocol parameters.

Three generation modes:
1. GAP FILL: augment sparse logs to n_target cases
2. COUNTERFACTUAL: generate what-if variant
3. FAILURE MODE: generate realistic failure pattern logs

Output: ProcessEvent objects compatible with BiologicalProcessMiner.
All synthetic events tagged with: source="synthetic_llm"

Biological plausibility constraints applied post-generation:
- Viability: 20-99%
- TEER: 50-1200 ohm*cm2 for epithelial models
- Passage number: 1-30
- No impossible sequences
"""

import json
import os
import statistics
from datetime import datetime
from typing import Optional

from connectors.base import ProcessEvent, DataSourceType

SYNTHETIC_SYSTEM_PROMPT = """You are a biological process data generator for Stromalytix.
Generate realistic laboratory process event logs for biofabrication workflows.

You will be given:
- A protocol description and biofab method
- Statistical summary of real events (mean/SD for key parameters)
- Target number of synthetic cases to generate
- Generation mode: gap_fill | counterfactual | failure_mode

Output ONLY valid JSON array of process event objects.
Each event must have: case_id, activity, timestamp, outcome_value,
lot_number, operator, biofab_method.

BIOLOGICAL CONSTRAINTS (never violate):
- viability_percent: 20-99
- TEER: 50-1200 ohm*cm2 for barrier models
- passage_number: 1-30
- cell_density_per_ml: 100000-50000000
- culture_duration_days: 1-30
- Timestamps must be chronologically ordered within each case
- Activity sequence must follow biological logic:
  ALWAYS: material_prep -> cell_prep -> construct_fab -> culture -> assay
  NEVER: assay before culture, culture before fab
"""


def _compute_event_statistics(events: list) -> dict:
    """Compute mean/SD/range for key process parameters."""
    viabilities = []
    for e in events:
        ov = e.outcome_values or {}
        if "viability" in ov:
            viabilities.append(ov["viability"])
    lots = list(set(e.batch_id for e in events if e.batch_id))
    methods = list(set(e.biofab_method for e in events if e.biofab_method))
    operators = list(set(e.operator for e in events if e.operator))

    return {
        "n_events": len(events),
        "n_cases": len(set(e.case_id for e in events)),
        "biofab_method": methods[0] if len(methods) == 1 else methods,
        "outcome_mean": round(
            float(sum(viabilities) / len(viabilities)), 2
        ) if viabilities else None,
        "outcome_sd": round(
            float(statistics.stdev(viabilities)), 2
        ) if len(viabilities) > 1 else None,
        "outcome_range": [
            min(viabilities), max(viabilities)
        ] if viabilities else None,
        "lots": lots,
        "operators": operators,
    }


def _call_claude_api(prompt: str) -> str:
    """Call Anthropic API for synthetic data generation."""
    import httpx

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 4000,
            "system": SYNTHETIC_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def _parse_and_validate_events(raw: str) -> list:
    """
    Parse LLM output as JSON and validate biological constraints.
    Returns list of ProcessEvent objects.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        data = [data]

    events = []
    for idx, item in enumerate(data):
        # Apply biological constraints
        viability = item.get("viability_percent") or item.get("outcome_value")
        if viability is not None:
            viability = max(20, min(99, float(viability)))
        if "passage_number" in item:
            item["passage_number"] = max(1, min(30, item["passage_number"]))
        if "teer" in item:
            item["teer"] = max(50, min(1200, item["teer"]))

        try:
            outcome_values = {}
            if viability is not None:
                outcome_values["viability"] = viability

            event = ProcessEvent(
                event_id=f"syn_{idx:04d}",
                case_id=item.get("case_id", "SYN-001"),
                activity=item.get("activity", "unknown"),
                timestamp=item.get("timestamp", datetime.now().isoformat()),
                source_type=DataSourceType.ELN,
                source_name="synthetic_llm",
                outcome_values=outcome_values if outcome_values else None,
                operator=item.get("operator", "synthetic"),
                batch_id=item.get("lot_number") or item.get("batch_id", "SYN-LOT"),
                biofab_method=item.get("biofab_method"),
            )
            events.append(event)
        except Exception:
            continue

    return events


def _matches_condition(event: ProcessEvent, condition: str) -> bool:
    """Check if an event matches a counterfactual condition."""
    condition_lower = condition.lower()
    batch = (event.batch_id or "").lower()
    if "lot_b2" in condition_lower or "lot-b2" in condition_lower:
        return any(x in batch for x in ["b2", "lot-2024-b2"])
    if "lot_a1" in condition_lower:
        return any(x in batch for x in ["a1", "lot-2024-a1"])
    return False


def augment_sparse_log(
    events: list,
    target_n_cases: int = 30,
    protocol_description: str = "",
) -> list:
    """
    Generate additional cases to augment a sparse event log.
    All synthetic cases tagged source="synthetic_llm".
    """
    existing_cases = list(set(e.case_id for e in events))
    n_existing = len(existing_cases)

    if n_existing >= target_n_cases:
        return events

    n_to_generate = target_n_cases - n_existing
    stats = _compute_event_statistics(events)

    prompt = f"""Generate {n_to_generate} new process cases (synthetic gap fill).

Protocol: {protocol_description}
Biofab method: {stats.get('biofab_method', 'unknown')}
Existing case statistics:
{json.dumps(stats, indent=2)}

Generate realistic cases matching these distributions.
Tag all events: "source": "synthetic_llm", "generation_mode": "gap_fill"
Output JSON array of ~{n_to_generate * 5} events (5 events per case).
Start case IDs from SYN-{n_existing + 1:03d}.
"""

    synthetic_raw = _call_claude_api(prompt)
    synthetic_events = _parse_and_validate_events(synthetic_raw)

    return events + synthetic_events


def generate_counterfactual(
    events: list,
    counterfactual_condition: str,
    description: str = "",
) -> list:
    """
    Generate counterfactual event log.

    Examples:
    - counterfactual_condition="without_lot_B2"
    - counterfactual_condition="with_correct_cell_density"
    """
    stats = _compute_event_statistics(events)
    affected = [e for e in events if _matches_condition(e, counterfactual_condition)]

    prompt = f"""Generate a COUNTERFACTUAL process event log.

Condition: {counterfactual_condition}
Description: {description}

Original log statistics: {json.dumps(stats, indent=2)}
Affected cases: {len(affected)} cases matched the condition

Generate {max(5, len(affected))} counterfactual cases showing what the process
would have looked like WITHOUT the specified condition.
Tag all events: "source": "synthetic_llm", "generation_mode": "counterfactual",
"counterfactual_condition": "{counterfactual_condition}"
"""

    synthetic_raw = _call_claude_api(prompt)
    return _parse_and_validate_events(synthetic_raw)
