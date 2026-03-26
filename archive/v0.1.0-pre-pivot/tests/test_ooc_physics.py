"""Tests for Organ-on-Chip physics models (shear stress + TEER)."""
import math

from core.ooc_physics import (
    predict_wall_shear_stress,
    predict_teer,
    OOC_TEER_CURVES,
)


# --- Wall shear stress ---

def test_shear_stress_formula_correct():
    """Verify tau = 6*mu*Q / (w*h^2) numerically."""
    # Use known values and verify
    flow_rate_ul_min = 10.0
    width_um = 1000.0
    height_um = 200.0
    viscosity = 0.001  # Pa*s (water)

    result = predict_wall_shear_stress(flow_rate_ul_min, width_um, height_um, viscosity)

    # Manual calculation
    Q_m3s = 10.0 * 1e-9 / 60.0
    w_m = 1000.0 * 1e-6
    h_m = 200.0 * 1e-6
    tau_pa = 6.0 * 0.001 * Q_m3s / (w_m * h_m * h_m)
    tau_dyn = tau_pa * 10.0

    assert abs(result - tau_dyn) < 1e-6


def test_shear_increases_with_flow_rate():
    """Higher flow rate should produce higher shear stress."""
    low = predict_wall_shear_stress(1.0, 500.0, 100.0)
    high = predict_wall_shear_stress(10.0, 500.0, 100.0)
    assert high > low
    # Should be exactly 10x since linear relationship
    assert abs(high / low - 10.0) < 0.01


# --- TEER prediction ---

def test_teer_returns_plausible_range():
    """TEER should be in physiologically plausible range (50-1500)."""
    teer, sd = predict_teer("caco2", 1.0, 14)
    assert 50 <= teer <= 1500
    assert sd > 0


def test_teer_caco2_has_data():
    """Caco-2 should have calibration data in OOC_TEER_CURVES."""
    assert "caco2" in OOC_TEER_CURVES
    assert len(OOC_TEER_CURVES["caco2"]) > 0
