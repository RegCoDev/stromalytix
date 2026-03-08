"""Tests for materials intelligence module."""
from core.materials_intelligence import (
    BioinkLotCharacterization,
    LotIntelligenceReport,
    predict_lot_performance,
)


def _make_char(**overrides):
    defaults = dict(lot_id="LOT-001", material_name="GelMA 6%")
    defaults.update(overrides)
    return BioinkLotCharacterization(**defaults)


def test_characterization_dataclass_instantiates():
    c = _make_char(storage_modulus_pa=8000, viscosity_pas_at_37c=100)
    assert c.lot_id == "LOT-001"
    assert c.storage_modulus_pa == 8000


def test_predict_high_modulus_gives_high_stiffness():
    c = _make_char(storage_modulus_pa=15000)
    report = predict_lot_performance(c)
    assert report.predicted_stiffness_kpa > 10


def test_predict_low_modulus_gives_low_stiffness():
    c = _make_char(storage_modulus_pa=2000)
    report = predict_lot_performance(c)
    assert report.predicted_stiffness_kpa < 5


def test_low_viscosity_recommends_small_nozzle():
    c = _make_char(viscosity_pas_at_37c=30, gelation_time_s=60)
    report = predict_lot_performance(c)
    assert report.recommended_nozzle_diameter_mm == 0.25


def test_high_viscosity_recommends_large_nozzle():
    c = _make_char(viscosity_pas_at_37c=200, gelation_time_s=60)
    report = predict_lot_performance(c)
    assert report.recommended_nozzle_diameter_mm == 0.6


def test_high_stiffness_reduces_viability_prediction():
    soft = _make_char(storage_modulus_pa=5000)
    hard = _make_char(storage_modulus_pa=25000)
    r_soft = predict_lot_performance(soft)
    r_hard = predict_lot_performance(hard)
    assert r_soft.predicted_cell_viability_day3_pct > r_hard.predicted_cell_viability_day3_pct


def test_release_when_thresholds_met():
    c = _make_char(viscosity_pas_at_37c=100, gelation_time_s=60)
    report = predict_lot_performance(c)
    assert report.release_recommendation == "RELEASE"


def test_hold_when_viability_below_threshold():
    c = _make_char(storage_modulus_pa=50000)
    report = predict_lot_performance(c)
    assert report.release_recommendation in ("HOLD", "CONDITIONAL")


def test_data_gaps_reported_when_missing_rheology():
    c = _make_char()  # no storage_modulus_pa
    report = predict_lot_performance(c)
    assert len(report.data_gaps) > 0
    assert any("storage_modulus" in g for g in report.data_gaps)


def test_confidence_high_when_full_data():
    c = _make_char(
        storage_modulus_pa=8000,
        viscosity_pas_at_37c=100,
        gelation_time_s=60,
        swelling_ratio=1.2,
    )
    report = predict_lot_performance(c)
    assert report.confidence == "high"


def test_confidence_low_when_no_data():
    c = _make_char()
    report = predict_lot_performance(c)
    assert report.confidence == "low"


def test_material_defaults_used_for_known_material():
    c = _make_char(material_name="Alginate 2%")
    report = predict_lot_performance(c)
    assert report.predicted_stiffness_kpa == 10.0


def test_report_has_all_fields():
    c = _make_char(storage_modulus_pa=8000, viscosity_pas_at_37c=100, gelation_time_s=60)
    report = predict_lot_performance(c)
    assert isinstance(report, LotIntelligenceReport)
    assert report.lot_id == "LOT-001"
    assert 0 <= report.predicted_printability_score <= 1
    assert report.release_recommendation in ("RELEASE", "CONDITIONAL", "HOLD")
    assert report.recommended_cell_density_per_ml == 1_000_000
