"""Tests for DLP bioprinting physics model (Beer-Lambert cure depth)."""
import math

from core.dlp_physics import (
    DLPPrintParameters,
    DLPPrintabilityReport,
    DLP_MATERIAL_DEFAULTS,
    UV_DOSE_VIABILITY,
    predict_dlp_printability,
)


def _make_params(**overrides):
    defaults = dict(
        material_type="GelMA_10pct_LAP",
        uv_intensity_mwcm2=10.0,
        exposure_time_s_per_layer=2.0,
        layer_thickness_mm=0.05,
        n_layers=10,
    )
    defaults.update(overrides)
    return DLPPrintParameters(**defaults)


# --- Beer-Lambert cure depth ---

def test_cure_depth_beer_lambert_formula():
    """Verify Cd = Dp * ln(E / Ec) numerically."""
    params = _make_params(
        uv_intensity_mwcm2=20.0,
        exposure_time_s_per_layer=2.0,
        Dp_mm=0.45,
        Ec_mJcm2=8.0,
    )
    report = predict_dlp_printability(params)
    E = 20.0 * 2.0  # 40 mJ/cm²
    expected_cd = 0.45 * math.log(E / 8.0)
    assert abs(report.cure_depth_mm - round(expected_cd, 4)) < 0.001


def test_cure_depth_zero_when_below_threshold():
    """When E <= Ec, cure depth should be 0."""
    params = _make_params(
        uv_intensity_mwcm2=2.0,
        exposure_time_s_per_layer=2.0,
        Dp_mm=0.45,
        Ec_mJcm2=8.0,
    )
    # E = 4 mJ/cm² < Ec = 8 mJ/cm²
    report = predict_dlp_printability(params)
    assert report.cure_depth_mm == 0.0


# --- Interlayer bonding ---

def test_interlayer_bonding_strong_when_cure_exceeds_layer():
    """Strong bonding when cure depth >= 1.5x layer thickness."""
    params = _make_params(
        uv_intensity_mwcm2=50.0,
        exposure_time_s_per_layer=5.0,
        layer_thickness_mm=0.05,
        Dp_mm=0.45,
        Ec_mJcm2=8.0,
    )
    # E = 250, Cd = 0.45 * ln(250/8) ~ 1.52 mm >> 0.05
    report = predict_dlp_printability(params)
    assert report.interlayer_bonding == "strong"


def test_interlayer_bonding_failed_when_below():
    """Failed bonding when cure depth is far below layer thickness."""
    params = _make_params(
        uv_intensity_mwcm2=2.0,
        exposure_time_s_per_layer=2.0,
        layer_thickness_mm=0.05,
        Dp_mm=0.45,
        Ec_mJcm2=8.0,
    )
    # E = 4 < Ec = 8, cure depth = 0
    report = predict_dlp_printability(params)
    assert report.interlayer_bonding == "failed"


# --- Viability ---

def test_high_uv_dose_reduces_viability():
    """High cumulative UV dose should reduce predicted viability."""
    low_dose = _make_params(
        uv_intensity_mwcm2=5.0,
        exposure_time_s_per_layer=1.0,
        n_layers=2,
    )
    high_dose = _make_params(
        uv_intensity_mwcm2=50.0,
        exposure_time_s_per_layer=2.0,
        n_layers=5,
    )
    report_low = predict_dlp_printability(low_dose)
    report_high = predict_dlp_printability(high_dose)
    assert report_low.predicted_viability_pct > report_high.predicted_viability_pct


def test_viability_above_threshold_at_low_dose():
    """At low UV dose, viability should be >= 90%."""
    params = _make_params(
        uv_intensity_mwcm2=5.0,
        exposure_time_s_per_layer=1.0,
        n_layers=2,
    )
    # Total dose = 10 mJ/cm²
    report = predict_dlp_printability(params)
    assert report.predicted_viability_pct >= 90.0


# --- Warnings and recommendations ---

def test_dlp_warnings_for_exceeded_dose():
    """Should warn when total UV dose exceeds 200 mJ/cm²."""
    params = _make_params(
        uv_intensity_mwcm2=50.0,
        exposure_time_s_per_layer=2.0,
        n_layers=5,
    )
    # Total dose = 500 mJ/cm²
    report = predict_dlp_printability(params)
    assert any("200" in w for w in report.warnings)


def test_recommendations_for_weak_interlayer():
    """Should recommend fixes when interlayer bonding is weak."""
    # Need cure_depth / layer_thickness between 0.8 and 1.1
    # Cd = Dp * ln(E/Ec), need Cd ~ 0.045 for layer=0.05
    # 0.045 = 0.45 * ln(E/8) => ln(E/8) = 0.1 => E/8 = 1.105 => E = 8.84
    params = _make_params(
        uv_intensity_mwcm2=8.84,
        exposure_time_s_per_layer=1.0,
        layer_thickness_mm=0.05,
        Dp_mm=0.45,
        Ec_mJcm2=8.0,
        n_layers=1,
    )
    report = predict_dlp_printability(params)
    assert report.interlayer_bonding == "weak"
    assert any("interlayer" in r.lower() or "bonding" in r.lower()
               for r in report.recommendations)


# --- References ---

def test_references_populated():
    """Report should contain literature references."""
    params = _make_params()
    report = predict_dlp_printability(params)
    assert len(report.references) >= 2
    assert any("Jacobs" in r for r in report.references)
    assert any("Grigoryan" in r for r in report.references)
