"""Tests for CompanyContext persistent intelligence layer."""
import json
import tempfile
from pathlib import Path


def test_company_context_importable():
    from core.company_context import CompanyContext, SimulationPrediction, Hypothesis
    assert CompanyContext is not None


def test_create_new_returns_valid_context():
    from core.company_context import CompanyContext
    ctx = CompanyContext.create_new("test_co", "Test Company", industry_segment="pharma")
    assert ctx.company_id == "test_co"
    assert ctx.company_name == "Test Company"
    assert ctx.industry_segment == "pharma"
    assert ctx.created != ""
    # Cleanup
    Path(f"data/company_contexts/test_co.json").unlink(missing_ok=True)


def test_add_and_validate_prediction_updates_accuracy():
    from core.company_context import CompanyContext, SimulationPrediction
    ctx = CompanyContext(company_id="t", company_name="T")
    pred = SimulationPrediction(
        prediction_id="p1", timestamp="2026-03-01", construct_summary="cardiac",
        biofab_method="bioprinting", predicted_outcomes=["viability > 80%"],
        predicted_failure_mode="delamination", confidence="medium",
        key_parameters={"stiffness_kpa": 10},
    )
    ctx.add_prediction(pred)
    assert len(ctx.active_predictions) == 1
    ctx.validate_prediction("p1", {"viability": 87})
    assert len(ctx.active_predictions) == 0
    assert len(ctx.validated_predictions) == 1
    assert ctx.get_prediction_accuracy() > 0


def test_hypothesis_lifecycle():
    from core.company_context import CompanyContext
    ctx = CompanyContext(company_id="t", company_name="T")
    hyp = ctx.add_hypothesis("LOT-B2 caused viability drop")
    assert hyp["status"] == "open"
    ctx.update_hypothesis(hyp["hypothesis_id"], "Viability correlates with B2 usage", "for")
    assert len(ctx.hypotheses[0]["evidence_for"]) == 1
    ctx.update_hypothesis(hyp["hypothesis_id"], "Temperature also changed", "against")
    assert len(ctx.hypotheses[0]["evidence_against"]) == 1


def test_calibration_update_stores_value():
    from core.company_context import CompanyContext
    ctx = CompanyContext(company_id="t", company_name="T")
    ctx.update_calibration("GelMA_viability_mean", 87.2)
    assert ctx.simulation_calibration["GelMA_viability_mean"] == 87.2


def test_to_chat_context_string_not_empty():
    from core.company_context import CompanyContext
    ctx = CompanyContext(
        company_id="t", company_name="TestCo",
        industry_segment="pharma",
        biofab_methods=["bioprinting"],
    )
    s = ctx.to_chat_context_string()
    assert "TestCo" in s
    assert len(s) > 0


def test_save_and_load_roundtrip():
    from core.company_context import CompanyContext
    ctx = CompanyContext(
        company_id="roundtrip_test", company_name="Roundtrip",
        industry_segment="biotech", biofab_methods=["ooc"],
    )
    ctx.add_hypothesis("Test hypothesis")
    ctx.save()
    loaded = CompanyContext.load("roundtrip_test")
    assert loaded.company_name == "Roundtrip"
    assert len(loaded.hypotheses) == 1
    # Cleanup
    Path("data/company_contexts/roundtrip_test.json").unlink(missing_ok=True)


def test_centara_demo_context_exists():
    from core.company_context import create_centara_demo_context
    ctx = create_centara_demo_context()
    assert ctx.company_id == "centara_demo"
    assert len(ctx.biofab_methods) == 5
    assert len(ctx.flagged_lots) == 2
    assert len(ctx.hypotheses) == 1
    assert ctx.hypotheses[0]["status"] == "open"
