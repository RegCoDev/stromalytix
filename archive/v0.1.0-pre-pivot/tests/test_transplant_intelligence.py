"""Tests for transplant process intelligence module."""
from core.transplant_intelligence import (
    NMPTimepoint,
    TransplantWorkflowParameters,
    TransplantConformanceReport,
    analyze_nmp_trace,
    compute_workflow_conformance,
    NMP_REFERENCE_RANGES,
)


def _make_params(**overrides):
    defaults = dict(
        donor_age=55,
        donor_type="dbd",
        donor_steatosis_pct=10,
        cold_ischemia_time_h=8.0,
        warm_ischemia_time_min=35,
        recipient_meld_score=18,
    )
    defaults.update(overrides)
    return TransplantWorkflowParameters(**defaults)


def _make_good_nmp_trace():
    return [
        NMPTimepoint(
            time_min=120,
            lactate_mmol_l=1.8,
            bile_ph=7.4,
            arterial_flow_ml_min=200,
            o2_consumption_mmol_h=35,
        ),
    ]


def _make_poor_nmp_trace():
    return [
        NMPTimepoint(
            time_min=240,
            lactate_mmol_l=6.0,
            bile_ph=6.7,
            arterial_flow_ml_min=70,
            o2_consumption_mmol_h=12,
        ),
    ]


def test_compute_conformance_returns_report():
    params = _make_params()
    report = compute_workflow_conformance(params)
    assert isinstance(report, TransplantConformanceReport)
    assert 0 <= report.overall_conformance_score <= 1
    assert 0 <= report.ead_risk_score <= 1
    assert report.ead_risk_category in ("low", "moderate", "high")


def test_dcd_donor_increases_risk():
    dbd = compute_workflow_conformance(_make_params(donor_type="dbd"))
    dcd = compute_workflow_conformance(_make_params(donor_type="dcd"))
    assert dcd.ead_risk_score > dbd.ead_risk_score


def test_high_steatosis_increases_risk():
    low = compute_workflow_conformance(_make_params(donor_steatosis_pct=5))
    high = compute_workflow_conformance(_make_params(donor_steatosis_pct=40))
    assert high.ead_risk_score > low.ead_risk_score


def test_long_cold_ischemia_increases_risk():
    short = compute_workflow_conformance(_make_params(cold_ischemia_time_h=5.0))
    long = compute_workflow_conformance(_make_params(cold_ischemia_time_h=16.0))
    assert long.ead_risk_score > short.ead_risk_score


def test_good_nmp_reduces_risk():
    no_nmp = compute_workflow_conformance(
        _make_params(donor_type="dcd", cold_ischemia_time_h=12.0)
    )
    with_nmp = compute_workflow_conformance(
        _make_params(
            donor_type="dcd",
            cold_ischemia_time_h=12.0,
            nmp_trace=_make_good_nmp_trace(),
        )
    )
    assert with_nmp.ead_risk_score < no_nmp.ead_risk_score


def test_poor_nmp_increases_risk():
    baseline = compute_workflow_conformance(_make_params())
    poor_nmp = compute_workflow_conformance(
        _make_params(nmp_trace=_make_poor_nmp_trace())
    )
    assert poor_nmp.ead_risk_score > baseline.ead_risk_score


def test_dcd_plus_steatosis_compound_effect():
    """DCD + steatosis >20% should trigger compound risk."""
    dcd_only = compute_workflow_conformance(
        _make_params(donor_type="dcd", donor_steatosis_pct=10)
    )
    compound = compute_workflow_conformance(
        _make_params(donor_type="dcd", donor_steatosis_pct=25)
    )
    # Compound should be more than additive
    assert compound.ead_risk_score > dcd_only.ead_risk_score
    assert any("compound" in r.lower() for r in compound.active_risk_factors)


def test_lactate_clearance_scoring_thresholds():
    fast_clear = [NMPTimepoint(time_min=45, lactate_mmol_l=2.0)]
    result = analyze_nmp_trace(fast_clear)
    assert result["lactate_score"] == 1.0  # <1h clearance

    slow_clear = [
        NMPTimepoint(time_min=60, lactate_mmol_l=4.0),
        NMPTimepoint(time_min=180, lactate_mmol_l=2.0),
    ]
    result2 = analyze_nmp_trace(slow_clear)
    assert result2["lactate_score"] < 1.0  # 3h clearance


def test_ead_probability_range_valid():
    # Low risk
    low = compute_workflow_conformance(
        _make_params(donor_age=30, cold_ischemia_time_h=4.0)
    )
    assert 0 < low.predicted_ead_probability < 1

    # High risk
    high = compute_workflow_conformance(
        _make_params(
            donor_age=75,
            donor_type="dcd",
            donor_steatosis_pct=40,
            cold_ischemia_time_h=16.0,
            warm_ischemia_time_min=70,
            recipient_meld_score=35,
        )
    )
    assert 0 < high.predicted_ead_probability < 1
    assert high.predicted_ead_probability > low.predicted_ead_probability


def test_low_risk_recommendation_text():
    report = compute_workflow_conformance(
        _make_params(donor_age=30, cold_ischemia_time_h=4.0)
    )
    assert "standard" in report.recommendation.lower() or "routine" in report.recommendation.lower()


def test_high_risk_recommendation_includes_review():
    report = compute_workflow_conformance(
        _make_params(
            donor_age=75,
            donor_type="dcd",
            donor_steatosis_pct=40,
            cold_ischemia_time_h=16.0,
            warm_ischemia_time_min=70,
        )
    )
    assert "review" in report.recommendation.lower() or "nmp" in report.recommendation.lower()


def test_analyze_nmp_trace_empty_returns_no_data():
    result = analyze_nmp_trace([])
    assert result["assessment"] == "no_nmp_data"
    assert result["score"] is None


def test_analyze_nmp_trace_good_lactate_high_score():
    trace = [NMPTimepoint(time_min=90, lactate_mmol_l=1.5, o2_consumption_mmol_h=30)]
    result = analyze_nmp_trace(trace)
    assert result["assessment"] == "viable"
    assert result["composite_nmp_score"] >= 0.75


def test_references_include_dois():
    report = compute_workflow_conformance(_make_params())
    assert any("doi:" in ref for ref in report.references)


def test_confidence_high_with_full_data():
    report = compute_workflow_conformance(_make_params())
    assert report.confidence == "high"


def test_step_scores_include_donor_assessment():
    report = compute_workflow_conformance(_make_params())
    assert "donor_assessment" in report.step_scores
    assert 0 <= report.step_scores["donor_assessment"] <= 1


def test_nmp_viability_assessment_populated():
    report = compute_workflow_conformance(
        _make_params(nmp_trace=_make_good_nmp_trace())
    )
    assert report.nmp_viability_assessment in ("viable", "marginal", "non_viable")
