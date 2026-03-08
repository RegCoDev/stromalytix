"""Tests for visualization export (PNG/SVG via kaleido)."""
import plotly.graph_objects as go


def test_export_figure_png():
    from core.export import export_figure_png
    fig = go.Figure(go.Scatter(x=[1, 2, 3], y=[1, 2, 3]))
    png_bytes = export_figure_png(fig, width=400, height=300)
    assert isinstance(png_bytes, bytes)
    assert len(png_bytes) > 100
    # PNG magic bytes
    assert png_bytes[:4] == b"\x89PNG"


def test_export_figure_svg():
    from core.export import export_figure_svg
    fig = go.Figure(go.Scatter(x=[1, 2, 3], y=[1, 2, 3]))
    svg_bytes = export_figure_svg(fig, width=400, height=300)
    assert isinstance(svg_bytes, bytes)
    assert b"<svg" in svg_bytes


def test_export_tissue_viz_png():
    from core.tissue_viz import render_construct_3d
    from core.export import export_figure_png
    from core.models import ConstructProfile

    profile = ConstructProfile(
        target_tissue="cardiac",
        cell_types=["cardiomyocytes", "fibroblasts"],
        scaffold_material="GelMA",
        stiffness_kpa=10.0,
        cell_density_per_ml=5e6,
    )
    fig = render_construct_3d(profile)
    png_bytes = export_figure_png(fig)
    assert len(png_bytes) > 1000
    assert png_bytes[:4] == b"\x89PNG"
