"""
Tests for core/migration_insights.py — Krogh O2 physics + analysis branches.

Scientific grounding
--------------------
Krogh tissue-cylinder model: Krogh A, J Physiol 1919, PMID 16812529.
  L_crit = sqrt(2 * D * C0 / (q * rho))

Reference values used throughout:
  D   = 2.5e-5 cm^2/s  (O2 diffusivity in dilute hydrogel, fallback)
  C0  = 2.0e-7 mol/cm^3 at 21% O2  (air-saturated medium at 37 C, ~0.2 mM)
  q   = 2.0e-17 mol/cell/s  (generic mammalian default)
  rho = 1e6 cells/cm^3  (standard seeding density, dilute construct)

Hand-calc at these defaults:
  denom  = 2e-17 * 1e6         = 2e-11 mol/(cm^3*s)
  numer  = 2 * 2.5e-5 * 2.0e-7 = 1.0e-11
  L_crit = sqrt(0.5) cm        = 0.7071 cm = 7.071 mm
=> A 4x4x2 mm construct (half-thickness 1 mm) should NOT show central hypoxia.

Dense case (rho = 1e8):
  denom  = 2e-17 * 1e8 = 2e-9
  L_crit = sqrt(1.0e-11 / 2e-9) = sqrt(0.005) cm = 0.07071 cm = 0.707 mm
=> A construct with half-thickness 1 mm at 1e8 cells/cm^3 IS hypoxic.
"""

import math

import pytest

from core.migration_insights import (
    _krogh_penetration_mm,
    analyse,
)
from core.models import ConstructProfile


# ── Reference constants matching the module's fallback defaults ────────

_D_CM2_S = 2.5e-5       # cm^2/s
_Q_MOL_CELL_S = 2e-17   # mol/cell/s
_RHO_DILUTE = 1e6       # cells/cm^3 (standard)
_RHO_DENSE = 1e8        # cells/cm^3 (hypoxic stress case)
_C0_21PCT = 2.0e-7      # mol/cm^3 at 21% O2


# ── 1. Direct numeric / physics-validation tests ───────────────────────


class TestKroghPenetrationHelper:
    """Tests for the pure-physics helper _krogh_penetration_mm."""

    def test_standard_dilute_construct_mm_scale(self):
        """Dilute 1e6 cells/cm^3 at 21% O2 -> L_crit near 7.07 mm (within 5%)."""
        expected_mm = math.sqrt(0.5) * 10.0  # 7.071 mm
        result = _krogh_penetration_mm(_D_CM2_S, _C0_21PCT, _Q_MOL_CELL_S, _RHO_DILUTE)
        assert abs(result - expected_mm) / expected_mm < 0.05, (
            f"Expected ~{expected_mm:.3f} mm, got {result:.3f} mm. "
            "Krogh formula or unit conversion is wrong."
        )

    def test_standard_dilute_exceeds_1mm_halfthickness(self):
        """L_crit >> 1 mm: standard 4x4x2 mm construct (half-thickness 1 mm) is NOT hypoxic."""
        result = _krogh_penetration_mm(_D_CM2_S, _C0_21PCT, _Q_MOL_CELL_S, _RHO_DILUTE)
        assert result > 1.0, (
            f"L_crit ({result:.3f} mm) should exceed 1 mm half-thickness; "
            "false hypoxia flag — check unit factors."
        )

    def test_dense_construct_submm(self):
        """Dense 1e8 cells/cm^3 at 21% O2 -> L_crit < 1 mm (genuine hypoxia risk)."""
        result = _krogh_penetration_mm(_D_CM2_S, _C0_21PCT, _Q_MOL_CELL_S, _RHO_DENSE)
        expected_mm = math.sqrt(1.0e-11 / (2.0e-17 * 1e8)) * 10.0  # 0.707 mm
        assert result < 1.0, (
            f"L_crit ({result:.3f} mm) should be < 1 mm at 1e8 cells/cm^3; "
            "model is not detecting real hypoxia."
        )
        assert abs(result - expected_mm) / expected_mm < 0.05, (
            f"Expected ~{expected_mm:.3f} mm, got {result:.3f} mm."
        )

    def test_scales_linearly_with_o2_tension(self):
        """L_crit at 10% O2 should be 1/sqrt(2.1) times L_crit at 21% O2."""
        c0_10pct = (10.0 / 21.0) * 2.0e-7
        l_21 = _krogh_penetration_mm(_D_CM2_S, _C0_21PCT, _Q_MOL_CELL_S, _RHO_DILUTE)
        l_10 = _krogh_penetration_mm(_D_CM2_S, c0_10pct, _Q_MOL_CELL_S, _RHO_DILUTE)
        ratio = l_10 / l_21
        expected_ratio = math.sqrt(10.0 / 21.0)
        assert abs(ratio - expected_ratio) < 0.01, (
            f"O2 tension scaling incorrect: ratio={ratio:.4f}, expected={expected_ratio:.4f}"
        )

    def test_nonpositive_inputs_return_sentinel(self):
        """Zero or negative density/O2 must return the 99.0 sentinel (no crash)."""
        assert _krogh_penetration_mm(_D_CM2_S, 0.0, _Q_MOL_CELL_S, _RHO_DILUTE) == 99.0
        assert _krogh_penetration_mm(_D_CM2_S, _C0_21PCT, _Q_MOL_CELL_S, 0.0) == 99.0
        assert _krogh_penetration_mm(_D_CM2_S, -1.0, _Q_MOL_CELL_S, _RHO_DILUTE) == 99.0


# ── 2. Integration tests via analyse() — mild-gradient branch ─────────


def _standard_dilute_profile(**overrides) -> ConstructProfile:
    """4x4x2 mm construct, 1 cell type without library match, 21% O2, 1e6 cells/mL."""
    defaults = dict(
        scaffold_material=None,          # forces fallback D = 2.5e-5
        cell_types=["unknown_cell_xyz"],  # no library entry -> fallback q = 2e-17
        scaffold_dimensions_mm=[4.0, 4.0, 2.0],
        oxygen_tension_percent=21.0,
        culture_duration_days=14,
        media_change_interval_hours=24.0,
        medium_volume_ml=2.0,
    )
    defaults.update(overrides)
    return ConstructProfile(**defaults)


class TestAnalyseMildGradientBranch:
    """Standard dilute construct must NOT report central hypoxia."""

    def test_mild_insight_fires(self):
        """analyse() should emit the mild-gradient Insight, not the steep/hypoxia one."""
        profile = _standard_dilute_profile()
        report = analyse(profile)

        o2_insights = [
            ins for ins in report.insights
            if ins.category == "Spontaneous O2 Gradient"
        ]
        assert o2_insights, "No Spontaneous O2 Gradient insights found — analyse() may have changed."

        headlines = [ins.headline for ins in o2_insights]
        detail_texts = [ins.detail for ins in o2_insights]

        # The mild branch headline
        mild_headlines = [h for h in headlines if "mild" in h.lower()]
        assert mild_headlines, (
            f"Expected a 'mild' O2 gradient insight for a dilute 1e6 cells/cm^3 construct "
            f"at 21% O2 (L_crit ~7 mm >> 1 mm half-thickness). Got headlines: {headlines}"
        )

    def test_mild_detail_mentions_exceeds_halfthickness(self):
        """The mild-branch detail must state penetration depth exceeds half-thickness."""
        profile = _standard_dilute_profile()
        report = analyse(profile)

        mild_details = [
            ins.detail for ins in report.insights
            if ins.category == "Spontaneous O2 Gradient" and "mild" in ins.headline.lower()
        ]
        assert mild_details, "Mild O2 insight has no detail text."
        combined = " ".join(mild_details).lower()
        assert "exceeds" in combined or "half-thickness" in combined, (
            f"Mild insight should mention penetration exceeding half-thickness. Got: {mild_details}"
        )

    def test_no_severe_hypoxia_insight_for_dilute_construct(self):
        """No 'steep' or 'hypoxia-driven' insights should fire for the dilute standard case."""
        profile = _standard_dilute_profile()
        report = analyse(profile)

        hypoxia_headlines = [
            ins.headline for ins in report.insights
            if ins.category == "Spontaneous O2 Gradient"
            and ("steep" in ins.headline.lower() or "hypoxia-driven" in ins.headline.lower())
        ]
        assert not hypoxia_headlines, (
            f"False severe-hypoxia flag for dilute 1e6 cells/cm^3 construct. "
            f"Got: {hypoxia_headlines}. "
            "This was the pre-fix bug: c0_mol and denom both had wrong unit factors."
        )


# ── 3. Integration tests via analyse() — steep-gradient / hypoxia branch


class TestAnalyseSteepGradientBranch:
    """High-density or thick construct must still detect genuine hypoxia."""

    def _dense_profile(self) -> ConstructProfile:
        # No direct density param on ConstructProfile; mimic via a construct where
        # the library returns a very high q_val by using a cell type with known
        # high consumption (or just use a tiny construct + default density so
        # half_mm > l_crit).  Easiest approach: make the construct very thick
        # (half_thickness >> l_crit at default density) — l_crit ~7 mm, so a
        # half-thickness of 10 mm triggers hypoxia.
        return ConstructProfile(
            scaffold_material=None,
            cell_types=["unknown_cell_xyz"],
            scaffold_dimensions_mm=[40.0, 40.0, 20.0],  # half-thickness = 10 mm
            oxygen_tension_percent=21.0,
            culture_duration_days=14,
            media_change_interval_hours=24.0,
            medium_volume_ml=2.0,
        )

    def test_steep_gradient_fires_for_thick_construct(self):
        """analyse() fires the steep-gradient Insight when half-thickness >> L_crit."""
        profile = self._dense_profile()
        report = analyse(profile)

        steep_insights = [
            ins for ins in report.insights
            if ins.category == "Spontaneous O2 Gradient"
            and "steep" in ins.headline.lower()
        ]
        assert steep_insights, (
            "Expected steep O2 gradient insight for a 20 mm half-thickness construct "
            "(L_crit ~7 mm << 10 mm half-thickness)."
        )

    def test_steep_gradient_detail_mentions_hypoxia(self):
        """Steep-gradient detail must reference hypoxia."""
        profile = self._dense_profile()
        report = analyse(profile)

        steep_details = [
            ins.detail for ins in report.insights
            if ins.category == "Spontaneous O2 Gradient"
            and "steep" in ins.headline.lower()
        ]
        assert steep_details, "Steep O2 insight missing detail text."
        combined = " ".join(steep_details).lower()
        assert "hypoxia" in combined or "hypoxic" in combined, (
            f"Steep-gradient detail should mention hypoxia. Got: {steep_details}"
        )

    def test_hypoxia_driven_migration_insight_fires(self):
        """The second hypoxia insight (aerotaxis bias) should also fire for thick constructs."""
        profile = self._dense_profile()
        report = analyse(profile)

        aerotaxis_insights = [
            ins for ins in report.insights
            if ins.category == "Spontaneous O2 Gradient"
            and "hypoxia-driven" in ins.headline.lower()
        ]
        assert aerotaxis_insights, (
            "Expected 'hypoxia-driven migration' insight for a thick hypoxic construct."
        )


# ── 4. Before/after regression guard ──────────────────────────────────


class TestUnitFixRegression:
    """
    Regression guard encoding the exact bug that was fixed.

    Before fix:
      c0_mol = o2_pct / 100.0 * 0.21e-3  =>  4.2e-5  mol/cm^3  (200x too high)
      denom  = q_val * density * 1e6      =>  2e-5    mol/(cm^3*s)  (1e6x too high)
      net l_crit_cm = sqrt(2 * 2.5e-5 * 4.2e-5 / 2e-5) = sqrt(1.05e-4) ~= 0.01025 cm
      l_crit_mm ~ 0.10 mm  (way less than any real half-thickness -> false SEVERE HYPOXIA)

    After fix:
      l_crit_mm ~ 7.07 mm  (correct, passes 1 mm threshold easily)
    """

    def test_buggy_formula_would_give_wrong_result(self):
        """Document the pre-fix formula so the regression is self-explaining if reintroduced."""
        # Replicate the old (wrong) calculation explicitly:
        d_val = 2.5e-5
        q_val = 2e-17
        density = 1e6
        o2_pct = 21.0

        c0_mol_wrong = o2_pct / 100.0 * 0.21e-3       # 4.2e-5 mol/cm^3 (was ~200x too high)
        denom_wrong = q_val * density * 1e6            # 2e-5  (was ~1e6x too high)
        l_crit_wrong_mm = math.sqrt(2 * d_val * c0_mol_wrong / denom_wrong) * 10.0

        # The net error was ~200/1e6 = 1/5000 relative factor inside the sqrt
        # => l_crit_wrong ~= 7.07 * sqrt(1/5000) ~= 0.10 mm — clearly sub-mm -> false alarm
        assert l_crit_wrong_mm < 0.5, (
            f"Pre-fix formula should give sub-0.5 mm (false-alarm territory), "
            f"got {l_crit_wrong_mm:.4f} mm."
        )

    def test_corrected_formula_gives_right_result(self):
        """The corrected helper must give ~7.07 mm for the same standard inputs."""
        c0_correct = (21.0 / 21.0) * 2.0e-7  # 2.0e-7 mol/cm^3
        result = _krogh_penetration_mm(2.5e-5, c0_correct, 2e-17, 1e6)
        assert result > 5.0, (
            f"Corrected formula must give > 5 mm for standard dilute construct, "
            f"got {result:.3f} mm."
        )
        assert abs(result - 7.071) < 0.4, (
            f"Corrected formula should give ~7.07 mm, got {result:.3f} mm."
        )
