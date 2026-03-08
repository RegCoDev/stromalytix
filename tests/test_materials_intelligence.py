"""Tests for physics-grounded materials intelligence module."""
import math

from core.materials_intelligence import (
    BioinkLotCharacterization,
    LotIntelligenceReport,
    predict_lot_performance,
    predict_stiffness_from_rheology,
    predict_printability,
    predict_viability_from_stiffness,
    release_decision,
    MECHANO_VIABILITY_CURVES,
)


def _make_char(**overrides):
    defaults = dict(lot_id="LOT-001", material_name="GelMA 6%")
    defaults.update(overrides)
    return BioinkLotCharacterization(**defaults)


# --- Stiffness (Flory-Rehner) ---

def test_stiffness_from_rheology_high_G_prime_gives_high_E():
    E, unc = predict_stiffness_from_rheology(15000, swelling_ratio=4.0)
    assert E > 20  # 3 * 15 * 4^(-1/3) ~ 28.3


def test_stiffness_flory_correction_with_swelling():
    """Higher swelling → lower effective stiffness."""
    E_low_swell, _ = predict_stiffness_from_rheology(8000, swelling_ratio=2.0)
    E_high_swell, _ = predict_stiffness_from_rheology(8000, swelling_ratio=8.0)
    assert E_low_swell > E_high_swell


def test_stiffness_uncertainty_approximately_12pct():
    """Nichol 2010: R^2=0.94, residual SD ~12%."""
    E, unc = predict_stiffness_from_rheology(8000, swelling_ratio=4.0)
    ratio = unc / E
    assert 0.10 < ratio < 0.15  # approximately 12%


def test_stiffness_formula_correctness():
    """E = 3 * G' * Q^(-1/3), verify directly."""
    G_pa = 10000
    Q = 4.0
    E_expected = 3 * (G_pa / 1000) * (Q ** (-1.0 / 3.0))
    E, _ = predict_stiffness_from_rheology(G_pa, swelling_ratio=Q)
    assert abs(E - E_expected) < 0.1


# --- Printability (Herschel-Bulkley) ---

def test_printability_optimal_viscosity_scores_high():
    score, unc, limiting = predict_printability(100, 60)
    assert score > 0.85  # 100 Pa*s is optimal center


def test_printability_poor_gelation_time_reduces_score():
    good_score, _, _ = predict_printability(100, 60)
    bad_score, _, _ = predict_printability(100, 200)  # too slow
    assert bad_score < good_score


def test_printability_too_fast_gelation_flagged():
    score, _, limiting = predict_printability(100, 10)
    assert score < 0.7
    assert "fast" in (limiting or "").lower() or score < 0.5


def test_printability_returns_uncertainty():
    _, unc, _ = predict_printability(100, 60)
    assert unc > 0
    assert unc < 0.3


def test_printability_no_data_returns_default():
    score, unc, limiting = predict_printability(None, None)
    assert score == 0.65
    assert "Insufficient" in limiting


# --- Viability (mechanotransduction curves) ---

def test_viability_hepatocyte_high_stiffness_penalty():
    """Hepatocytes lose viability at high stiffness."""
    v_soft, _, _, _ = predict_viability_from_stiffness(2.0, ["HepG2"])
    v_hard, _, _, _ = predict_viability_from_stiffness(10.0, ["HepG2"])
    assert v_soft > v_hard


def test_viability_huvec_optimal_range():
    """HUVECs prefer moderate stiffness (4-12 kPa)."""
    v_opt, _, _, _ = predict_viability_from_stiffness(8.0, ["HUVEC"])
    v_soft, _, _, _ = predict_viability_from_stiffness(1.0, ["HUVEC"])
    assert v_opt > v_soft


def test_viability_interpolation_between_calibrated_points():
    """5 kPa hepatocyte viability should be between 4 kPa and 6 kPa values."""
    curve = MECHANO_VIABILITY_CURVES["hepatocyte"]
    v_4kpa = next(pt[1] for pt in curve if pt[0] == 4.0)
    v_6kpa = next(pt[1] for pt in curve if pt[0] == 6.0)
    v_5kpa, _, _, _ = predict_viability_from_stiffness(5.0, ["HepG2"])
    assert v_6kpa < v_5kpa < v_4kpa


def test_viability_returns_reference_doi():
    _, _, ref, _ = predict_viability_from_stiffness(4.0, ["HepG2"])
    assert ref.startswith("10.")  # DOI format


def test_viability_default_curve_for_unknown_cell():
    _, _, _, limiting = predict_viability_from_stiffness(4.0, ["SomeRareCell"])
    assert limiting is not None
    assert "not in calibrated" in limiting


def test_viability_neuron_curve_exists():
    v, _, ref, _ = predict_viability_from_stiffness(0.5, ["neuron"])
    assert v > 80  # neurons prefer very soft substrates


# --- Release decision ---

def test_release_when_all_criteria_met():
    decision, rationale = release_decision(0.85, 85.0, 80.0)
    assert decision == "RELEASE"


def test_hold_when_viability_below_minimum():
    decision, rationale = release_decision(0.80, 60.0, 55.0)
    assert decision == "HOLD"


def test_conditional_with_adjustment_recommendations():
    decision, rationale = release_decision(0.65, 75.0, 70.0)
    assert decision == "CONDITIONAL"
    assert "marginal" in rationale.lower() or "crosslink" in rationale.lower()


# --- Full pipeline ---

def test_predict_lot_performance_returns_report():
    char = _make_char(
        storage_modulus_pa=8000,
        viscosity_pas_at_37c=100,
        gelation_time_s=60,
        swelling_ratio=4.0,
    )
    report = predict_lot_performance(char)
    assert isinstance(report, LotIntelligenceReport)
    assert report.lot_id == "LOT-001"
    assert report.predicted_stiffness_kpa > 0
    assert report.stiffness_uncertainty_kpa > 0


def test_uncertainty_reported_for_all_predictions():
    char = _make_char(
        storage_modulus_pa=8000,
        viscosity_pas_at_37c=100,
        gelation_time_s=60,
    )
    report = predict_lot_performance(char)
    assert report.stiffness_uncertainty_kpa > 0
    assert report.printability_uncertainty > 0
    assert report.viability_sd_pct > 0


def test_references_populated():
    char = _make_char(
        storage_modulus_pa=8000,
        viscosity_pas_at_37c=100,
        gelation_time_s=60,
    )
    report = predict_lot_performance(char)
    assert len(report.references) >= 2
    assert any("Nichol" in r for r in report.references)
    assert any("Ouyang" in r for r in report.references)


def test_data_gaps_when_missing_rheology():
    char = _make_char()  # no storage_modulus_pa
    report = predict_lot_performance(char)
    assert len(report.data_gaps) > 0
    assert any("storage_modulus" in g for g in report.data_gaps)


def test_confidence_high_with_full_data():
    char = _make_char(
        storage_modulus_pa=8000,
        viscosity_pas_at_37c=100,
        gelation_time_s=60,
        swelling_ratio=4.0,
    )
    report = predict_lot_performance(char)
    assert report.confidence == "high"


def test_confidence_low_with_no_data():
    char = _make_char()
    report = predict_lot_performance(char)
    assert report.confidence == "low"


def test_low_viscosity_recommends_small_nozzle():
    char = _make_char(viscosity_pas_at_37c=30, gelation_time_s=60)
    report = predict_lot_performance(char)
    assert report.recommended_nozzle_diameter_mm == 0.25


def test_high_viscosity_recommends_large_nozzle():
    char = _make_char(viscosity_pas_at_37c=200, gelation_time_s=60)
    report = predict_lot_performance(char)
    assert report.recommended_nozzle_diameter_mm == 0.6
