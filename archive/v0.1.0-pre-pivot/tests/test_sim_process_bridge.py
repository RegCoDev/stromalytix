"""Tests for Simulation-Process Bridge — convergent signal synthesis."""
from pathlib import Path


def test_bridge_importable():
    from core.sim_process_bridge import (
        detect_convergent_signals,
        update_calibration_from_outcome,
        create_prediction_from_simulation,
        get_p1_alerts,
    )
    assert detect_convergent_signals is not None


def test_detect_convergent_signals_empty_context():
    from core.company_context import CompanyContext
    from core.sim_process_bridge import detect_convergent_signals

    ctx = CompanyContext(company_id="t", company_name="T")
    signals = detect_convergent_signals(ctx)
    assert isinstance(signals, list)
    assert len(signals) == 0


def test_detect_convergent_signals_validated_prediction():
    from core.company_context import CompanyContext
    from core.sim_process_bridge import detect_convergent_signals

    ctx = CompanyContext(company_id="t", company_name="T")
    ctx.validated_predictions.append({
        "prediction_id": "p1",
        "construct_summary": "cardiac",
        "accuracy_score": 0.85,
        "predicted_outcomes": ["viability > 80%"],
        "actual_outcomes": {"viability": 87},
    })
    signals = detect_convergent_signals(ctx)
    assert len(signals) == 1
    assert signals[0]["signal_type"] == "prediction_confirmed"
    assert signals[0]["confidence"] == "medium"


def test_detect_lot_failure_predicted():
    from core.company_context import CompanyContext, SimulationPrediction
    from core.sim_process_bridge import detect_convergent_signals

    ctx = CompanyContext(company_id="t", company_name="T")
    ctx.flagged_lots = [{"lot_id": "B2", "issue": "Low viability", "affected_runs": 5}]
    ctx.active_predictions.append({
        "prediction_id": "p2",
        "predicted_failure_mode": "viability drop",
        "confidence": "high",
    })
    signals = detect_convergent_signals(ctx)
    lot_signals = [s for s in signals if s["signal_type"] == "lot_failure_predicted"]
    assert len(lot_signals) == 1
    assert lot_signals[0]["confidence"] == "high"


def test_detect_hypothesis_convergent():
    from core.company_context import CompanyContext
    from core.sim_process_bridge import detect_convergent_signals

    ctx = CompanyContext(company_id="t", company_name="T")
    ctx.hypotheses.append({
        "hypothesis_id": "h1",
        "statement": "B2 caused failure",
        "evidence_for": ["timeline matches", "supplier changed"],
        "evidence_against": [],
        "status": "open",
    })
    signals = detect_convergent_signals(ctx)
    assert len(signals) == 1
    assert signals[0]["signal_type"] == "hypothesis_convergent"


def test_detect_hypothesis_contested():
    from core.company_context import CompanyContext
    from core.sim_process_bridge import detect_convergent_signals

    ctx = CompanyContext(company_id="t", company_name="T")
    ctx.hypotheses.append({
        "hypothesis_id": "h1",
        "statement": "B2 caused failure",
        "evidence_for": ["timeline matches"],
        "evidence_against": ["temperature also changed"],
        "status": "open",
    })
    signals = detect_convergent_signals(ctx)
    contested = [s for s in signals if s["signal_type"] == "hypothesis_contested"]
    assert len(contested) == 1
    assert contested[0]["confidence"] == "low"


def test_update_calibration_from_outcome():
    from core.company_context import CompanyContext, SimulationPrediction
    from core.sim_process_bridge import update_calibration_from_outcome
    from dataclasses import asdict

    ctx = CompanyContext(company_id="cal_test", company_name="Cal")
    pred = SimulationPrediction(
        prediction_id="cal_p1", timestamp="2026-03-01",
        construct_summary="cardiac", biofab_method="bioprinting",
        predicted_outcomes=["viability > 80%"],
        predicted_failure_mode="none", confidence="medium",
        key_parameters={"stiffness_kpa": 10},
    )
    ctx.add_prediction(pred)

    result = update_calibration_from_outcome(ctx, "cal_p1", {"viability": 85.0})
    assert len(result["calibration_updates"]) == 1
    assert result["calibration_updates"][0]["parameter"] == "viability"
    assert result["calibration_updates"][0]["new_value"] == 85.0
    assert ctx.simulation_calibration["viability"] == 85.0
    # Cleanup
    Path(f"data/company_contexts/cal_test.json").unlink(missing_ok=True)


def test_create_prediction_from_simulation():
    from core.company_context import CompanyContext
    from core.sim_process_bridge import create_prediction_from_simulation

    ctx = CompanyContext(company_id="sim_test", company_name="Sim")
    fem_result = {"failure_risk": "high", "strain_percent": 22.5}
    pred = create_prediction_from_simulation(
        ctx, "cardiac patch", "bioprinting",
        fem_result=fem_result,
        key_parameters={"stiffness_kpa": 0.5},
    )
    assert pred.predicted_failure_mode == "scaffold_deformation"
    assert pred.confidence == "high"
    assert len(ctx.active_predictions) == 1
    # Cleanup
    Path(f"data/company_contexts/sim_test.json").unlink(missing_ok=True)


def test_get_p1_alerts_returns_high_confidence():
    from core.company_context import CompanyContext
    from core.sim_process_bridge import get_p1_alerts

    ctx = CompanyContext(company_id="t", company_name="T")
    ctx.validated_predictions.append({
        "prediction_id": "p1",
        "construct_summary": "cardiac",
        "accuracy_score": 0.95,
        "predicted_outcomes": ["viability > 80%"],
        "actual_outcomes": {"viability": 92},
    })
    alerts = get_p1_alerts(ctx)
    assert len(alerts) == 1
    assert alerts[0]["confidence"] == "high"


def test_fuzzy_match():
    from core.sim_process_bridge import _fuzzy_match

    assert _fuzzy_match("Low viability", "viability drop") is True
    assert _fuzzy_match("stiffness issue", "temperature problem") is False
