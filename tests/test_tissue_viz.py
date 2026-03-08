"""Tests for 3D tissue construct visualization."""
from types import SimpleNamespace

import plotly.graph_objects as go


def _make_profile(**kwargs):
    defaults = {
        "cell_types": ["default"],
        "stiffness_kpa": 5.0,
        "cell_density_per_ml": 1_000_000,
        "biofab_method": "scaffold_free",
        "scaffold_material": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_generate_cell_positions_returns_dict():
    from core.tissue_viz import generate_cell_positions

    result = generate_cell_positions(
        ["typeA", "typeB"], 1e6, 5.0, "bioprinting"
    )
    assert isinstance(result, dict)
    assert "typeA" in result
    assert "typeB" in result
    for ct, (x, y, z) in result.items():
        assert len(x) > 0
        assert len(x) == len(y) == len(z)


def test_all_biofab_methods_produce_positions():
    from core.tissue_viz import generate_cell_positions

    methods = ["bioprinting", "organ_on_chip", "organoid",
               "acoustic_aggregation", "scaffold_free"]
    for method in methods:
        result = generate_cell_positions(
            ["default"], 1e6, 5.0, method, n_cells_display=50
        )
        assert len(result) == 1, f"Failed for method: {method}"
        x, y, z = result["default"]
        assert len(x) > 0, f"No positions for {method}"


def test_render_construct_3d_returns_figure():
    from core.tissue_viz import render_construct_3d

    profile = _make_profile(cell_types=["cardiomyocytes", "fibroblasts"])
    fig = render_construct_3d(profile, title="Test Construct")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 2  # at least 2 cell types


def test_stiffness_affects_packing():
    from core.tissue_viz import generate_cell_positions
    import numpy as np

    soft = generate_cell_positions(["default"], 1e6, 1.0, "spheroid", seed=42)
    stiff = generate_cell_positions(["default"], 1e6, 20.0, "spheroid", seed=42)

    soft_spread = np.std(soft["default"][0])
    stiff_spread = np.std(stiff["default"][0])
    # Stiffer scaffold -> tighter packing -> smaller spread
    assert stiff_spread < soft_spread


def test_multi_cell_type_all_present_in_output():
    from core.tissue_viz import generate_cell_positions

    types = ["cardiomyocytes", "fibroblasts", "HUVEC"]
    result = generate_cell_positions(types, 1e6, 5.0, "bioprinting")
    for t in types:
        assert t in result


def test_dark_theme_applied():
    from core.tissue_viz import render_construct_3d

    profile = _make_profile()
    fig = render_construct_3d(profile)
    assert fig.layout.paper_bgcolor == "#0a0a0a"
    assert fig.layout.scene.bgcolor == "#111111"


def test_scaffold_mesh_added_when_material_present():
    from core.tissue_viz import render_construct_3d

    profile = _make_profile(scaffold_material="GelMA")
    fig = render_construct_3d(profile, show_scaffold=True)
    # Should have cell trace + scaffold mesh
    trace_names = [t.name for t in fig.data]
    assert "scaffold" in trace_names


def test_no_scaffold_mesh_for_scaffold_free():
    from core.tissue_viz import render_construct_3d

    profile = _make_profile(scaffold_material="scaffold_free")
    fig = render_construct_3d(profile, show_scaffold=True)
    trace_names = [t.name for t in fig.data]
    assert "scaffold" not in trace_names
