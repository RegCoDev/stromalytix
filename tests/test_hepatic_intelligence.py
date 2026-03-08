"""Tests for hepatic intelligence module — DILI detection prediction."""
from types import SimpleNamespace

from core.hepatic_intelligence import (
    predict_hepatic_quality,
    get_hepatic_cc3d_extensions,
    HepaticQualityScore,
    DILI_MECHANISM_MAP,
    DILI_DETECTION_BENCHMARKS,
)


def _make_profile(**kwargs):
    return SimpleNamespace(**kwargs)


def test_predict_quality_returns_score():
    profile = _make_profile(
        cell_types=["HepG2"],
        stiffness_kpa=5.0,
        scaffold_material="GelMA",
        target_tissue="liver",
    )
    score = predict_hepatic_quality(profile)
    assert isinstance(score, HepaticQualityScore)
    assert 0 < score.predicted_dilirank_sensitivity <= 1
    assert 0 < score.predicted_specificity <= 1


def test_primary_hepatocytes_score_higher_than_hepg2():
    hepg2 = predict_hepatic_quality(_make_profile(
        cell_types=["HepG2"], stiffness_kpa=5.0,
        scaffold_material="GelMA", target_tissue="liver",
    ))
    primary = predict_hepatic_quality(_make_profile(
        cell_types=["primary hepatocytes"], stiffness_kpa=5.0,
        scaffold_material="GelMA", target_tissue="liver",
    ))
    assert primary.predicted_dilirank_sensitivity > hepg2.predicted_dilirank_sensitivity


def test_ooc_scores_highest():
    ooc = predict_hepatic_quality(_make_profile(
        cell_types=["primary hepatocytes"], stiffness_kpa=3.0,
        scaffold_material="PDMS", target_tissue="liver-on-chip",
    ))
    spheroid = predict_hepatic_quality(_make_profile(
        cell_types=["primary hepatocytes"], stiffness_kpa=3.0,
        scaffold_material="GelMA", target_tissue="liver",
    ))
    assert ooc.predicted_dilirank_sensitivity > spheroid.predicted_dilirank_sensitivity


def test_high_stiffness_penalty_applied():
    low = predict_hepatic_quality(_make_profile(
        cell_types=["HepG2"], stiffness_kpa=4.0,
        scaffold_material="GelMA", target_tissue="liver",
    ))
    high = predict_hepatic_quality(_make_profile(
        cell_types=["HepG2"], stiffness_kpa=25.0,
        scaffold_material="GelMA", target_tissue="liver",
    ))
    assert low.predicted_dilirank_sensitivity > high.predicted_dilirank_sensitivity
    assert any("exceeds" in f for f in high.limiting_factors)


def test_short_culture_penalty_applied():
    short = predict_hepatic_quality(_make_profile(
        cell_types=["HepG2"], stiffness_kpa=5.0,
        scaffold_material="GelMA", target_tissue="liver",
        culture_duration_days=3,
    ))
    long = predict_hepatic_quality(_make_profile(
        cell_types=["HepG2"], stiffness_kpa=5.0,
        scaffold_material="GelMA", target_tissue="liver",
        culture_duration_days=21,
    ))
    assert long.predicted_dilirank_sensitivity > short.predicted_dilirank_sensitivity


def test_physiological_stiffness_bonus_applied():
    phys = predict_hepatic_quality(_make_profile(
        cell_types=["HepG2"], stiffness_kpa=4.0,
        scaffold_material="GelMA", target_tissue="liver",
    ))
    assert any("physiological" in d.lower() for d in phys.key_drivers)


def test_f1_score_computed_correctly():
    score = HepaticQualityScore(
        construct_summary="test",
        predicted_dilirank_sensitivity=0.8,
        predicted_specificity=0.9,
        benchmark_comparison="test",
        confidence="high",
    )
    expected = 2 * 0.8 * 0.9 / (0.8 + 0.9)
    assert abs(score.f1_score - expected) < 1e-6


def test_f1_score_zero_when_both_zero():
    score = HepaticQualityScore(
        construct_summary="test",
        predicted_dilirank_sensitivity=0.0,
        predicted_specificity=0.0,
        benchmark_comparison="test",
        confidence="low",
    )
    assert score.f1_score == 0


def test_hepatic_cc3d_extensions_adds_zonation():
    score = HepaticQualityScore(
        construct_summary="test",
        predicted_dilirank_sensitivity=0.78,
        predicted_specificity=0.88,
        benchmark_comparison="test",
        confidence="high",
    )
    extended = get_hepatic_cc3d_extensions({"cell_types": ["HepG2"]}, score)
    assert "hepatic_extensions" in extended
    ext = extended["hepatic_extensions"]
    assert ext["model_zonation"] is True
    assert ext["periportal_oxygen_mmhg"] == 65
    assert ext["pericentral_oxygen_mmhg"] == 35
    assert ext["bile_canaliculi_probability"] == 0.3  # high confidence


def test_dili_mechanism_map_has_required_keys():
    for mechanism, data in DILI_MECHANISM_MAP.items():
        assert "process_failure" in data
        assert "biomarkers" in data
        assert len(data["biomarkers"]) > 0


def test_benchmarks_ordered_by_complexity():
    """More complex models should have higher sensitivity."""
    b = DILI_DETECTION_BENCHMARKS
    assert b["2D_monolayer_hepg2"]["dilirank_sensitivity"] < \
           b["3D_spheroid_hepg2"]["dilirank_sensitivity"] < \
           b["3D_spheroid_primary_hepatocytes"]["dilirank_sensitivity"] < \
           b["ooc_primary_hepatocytes"]["dilirank_sensitivity"]
