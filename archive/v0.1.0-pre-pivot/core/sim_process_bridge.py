"""
Simulation-Process Bridge: convergent signal synthesis.

Detects when simulation predictions and empirical process data
agree (convergent signals) or disagree (divergent signals).
Updates CompanyContext calibration when actual outcomes arrive.

This is the layer that makes simulation predictions ACTIONABLE
by grounding them in real process evidence.
"""
from typing import Optional

from core.company_context import CompanyContext, SimulationPrediction


def detect_convergent_signals(context: CompanyContext) -> list:
    """
    Scan active predictions and validated data for convergent signals.

    A convergent signal occurs when:
    - A simulation prediction aligns with empirical observation
    - A batch effect matches a predicted failure mode
    - Multiple evidence layers point the same direction

    Returns list of signal dicts:
    [{"signal_type": str, "confidence": str, "summary": str,
      "prediction_id": str|None, "evidence": list}]
    """
    signals = []

    # Check validated predictions for high accuracy
    for pred in context.validated_predictions:
        p = pred if isinstance(pred, dict) else pred.__dict__
        score = p.get("accuracy_score", 0)
        if score and score >= 0.7:
            signals.append({
                "signal_type": "prediction_confirmed",
                "confidence": "high" if score >= 0.9 else "medium",
                "summary": (
                    f"Prediction {p.get('prediction_id', '?')} confirmed: "
                    f"{p.get('construct_summary', '?')} — "
                    f"accuracy {score:.0%}"
                ),
                "prediction_id": p.get("prediction_id"),
                "evidence": [
                    f"Predicted: {p.get('predicted_outcomes', [])}",
                    f"Actual: {p.get('actual_outcomes', {})}",
                ],
            })

    # Check flagged lots against active predictions
    for lot in context.flagged_lots:
        lot_info = lot if isinstance(lot, dict) else {"lot_id": str(lot)}
        lot_id = lot_info.get("lot_id", "")
        lot_issue = lot_info.get("issue", "")

        for pred in context.active_predictions:
            p = pred if isinstance(pred, dict) else pred.__dict__
            failure_mode = p.get("predicted_failure_mode", "")
            # Check if lot issue matches predicted failure mode
            if (lot_issue and failure_mode and
                    _fuzzy_match(lot_issue, failure_mode)):
                signals.append({
                    "signal_type": "lot_failure_predicted",
                    "confidence": p.get("confidence", "medium"),
                    "summary": (
                        f"Lot {lot_id} issue '{lot_issue}' matches "
                        f"predicted failure mode '{failure_mode}'"
                    ),
                    "prediction_id": p.get("prediction_id"),
                    "evidence": [
                        f"Lot issue: {lot_issue}",
                        f"Predicted failure: {failure_mode}",
                        f"Affected runs: {lot_info.get('affected_runs', '?')}",
                    ],
                })

    # Check hypotheses with both supporting and contradicting evidence
    for hyp in context.hypotheses:
        h = hyp if isinstance(hyp, dict) else hyp.__dict__
        if h.get("status") != "open":
            continue
        n_for = len(h.get("evidence_for", []))
        n_against = len(h.get("evidence_against", []))
        if n_for >= 2 and n_against == 0:
            signals.append({
                "signal_type": "hypothesis_convergent",
                "confidence": "medium",
                "summary": (
                    f"Hypothesis '{h.get('statement', '?')[:80]}' has "
                    f"{n_for} supporting evidence, 0 contradictions"
                ),
                "prediction_id": None,
                "evidence": h.get("evidence_for", []),
            })
        elif n_for > 0 and n_against > 0:
            signals.append({
                "signal_type": "hypothesis_contested",
                "confidence": "low",
                "summary": (
                    f"Hypothesis '{h.get('statement', '?')[:80]}' is contested: "
                    f"{n_for} for, {n_against} against"
                ),
                "prediction_id": None,
                "evidence": (
                    [f"FOR: {e}" for e in h.get("evidence_for", [])] +
                    [f"AGAINST: {e}" for e in h.get("evidence_against", [])]
                ),
            })

    return signals


def update_calibration_from_outcome(
    context: CompanyContext,
    prediction_id: str,
    actual_outcomes: dict,
) -> dict:
    """
    When an actual outcome arrives, validate the prediction
    and update calibration parameters.

    Returns summary of what changed.
    """
    changes = []

    # Validate the prediction
    context.validate_prediction(prediction_id, actual_outcomes)

    # Update calibration for each measured parameter
    for param, value in actual_outcomes.items():
        if isinstance(value, (int, float)):
            old_val = context.simulation_calibration.get(param)
            context.update_calibration(param, value)
            if old_val is not None:
                drift = abs(value - old_val) / max(abs(old_val), 1e-6) * 100
                changes.append({
                    "parameter": param,
                    "old_value": old_val,
                    "new_value": value,
                    "drift_percent": round(drift, 1),
                })
            else:
                changes.append({
                    "parameter": param,
                    "old_value": None,
                    "new_value": value,
                    "drift_percent": 0,
                })

    context.save()

    return {
        "prediction_id": prediction_id,
        "calibration_updates": changes,
        "new_accuracy": context.get_prediction_accuracy(),
    }


def create_prediction_from_simulation(
    context: CompanyContext,
    construct_summary: str,
    biofab_method: str,
    fem_result: Optional[dict] = None,
    key_parameters: Optional[dict] = None,
) -> SimulationPrediction:
    """
    Create a SimulationPrediction from simulation outputs (FEA, CC3D, etc.)
    and register it in the company context.
    """
    import uuid
    from datetime import datetime

    predicted_outcomes = []
    predicted_failure_mode = "none"
    confidence = "medium"

    if fem_result:
        risk = fem_result.get("failure_risk", "low")
        strain = fem_result.get("strain_percent", 0)
        predicted_outcomes.append(f"strain={strain}%")
        if risk == "high":
            predicted_failure_mode = "scaffold_deformation"
            confidence = "high"
            predicted_outcomes.append("deformation_failure_likely")
        elif risk == "medium":
            predicted_failure_mode = "moderate_deformation"

    pred = SimulationPrediction(
        prediction_id=f"sim_{uuid.uuid4().hex[:8]}",
        timestamp=datetime.now().isoformat(),
        construct_summary=construct_summary,
        biofab_method=biofab_method,
        predicted_outcomes=predicted_outcomes,
        predicted_failure_mode=predicted_failure_mode,
        confidence=confidence,
        key_parameters=key_parameters or {},
    )

    context.add_prediction(pred)
    context.save()
    return pred


def get_p1_alerts(context: CompanyContext) -> list:
    """
    Return P1 (highest priority) alerts where simulation and
    empirical signals overlap.
    """
    signals = detect_convergent_signals(context)
    return [
        s for s in signals
        if s["confidence"] == "high"
        or s["signal_type"] == "lot_failure_predicted"
    ]


def _fuzzy_match(a: str, b: str) -> bool:
    """Simple word-overlap matching for lot issues vs failure modes."""
    a_words = set(a.lower().split())
    b_words = set(b.lower().split())
    # Remove common stop words
    stop = {"the", "a", "an", "is", "in", "of", "and", "or", "to", "for"}
    a_words -= stop
    b_words -= stop
    if not a_words or not b_words:
        return False
    overlap = len(a_words & b_words)
    return overlap >= 1
