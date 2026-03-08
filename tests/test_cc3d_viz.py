"""Tests for CC3D VTK output capture and rendering."""
import numpy as np
import plotly.graph_objects as go


def test_cc3d_viz_importable():
    from core.cc3d_viz import (
        find_vtk_outputs, parse_vtk_lattice, cc3d_ids_to_types,
        render_cc3d_lattice, get_default_type_map,
    )
    assert find_vtk_outputs is not None


def test_vtk_parser_handles_missing_file_gracefully():
    from core.cc3d_viz import parse_vtk_lattice
    result = parse_vtk_lattice("/nonexistent/path/foo.vtk")
    assert result["dimensions"] == (0, 0, 0)
    assert len(result["cell_ids"]) == 0


def test_cc3d_ids_to_types_maps_correctly():
    from core.cc3d_viz import cc3d_ids_to_types
    ids = np.array([0, 1, 2, 1, 0, 3])
    type_map = {1: "cardiomyocytes", 2: "fibroblasts", 3: "HUVEC"}
    types = cc3d_ids_to_types(ids, type_map)
    assert types[0] == "empty"
    assert types[1] == "cardiomyocytes"
    assert types[2] == "fibroblasts"
    assert types[5] == "HUVEC"


def test_render_cc3d_lattice_returns_figure():
    from core.cc3d_viz import render_cc3d_lattice
    lattice = {
        "dimensions": (5, 5, 5),
        "cell_ids": np.zeros(125, dtype=np.int32),
        "spacing": (1, 1, 1),
    }
    # Set some cells
    lattice["cell_ids"][10] = 1
    lattice["cell_ids"][20] = 2
    lattice["cell_ids"][30] = 1

    type_map = {1: "typeA", 2: "typeB"}
    fig = render_cc3d_lattice(lattice, type_map, title="Test CC3D")
    assert isinstance(fig, go.Figure)


def test_downsample_large_lattice():
    from core.cc3d_viz import render_cc3d_lattice
    # Large lattice with many occupied voxels
    n = 50
    cell_ids = np.ones(n * n * n, dtype=np.int32)
    lattice = {
        "dimensions": (n, n, n),
        "cell_ids": cell_ids,
        "spacing": (1, 1, 1),
    }
    type_map = {1: "cells"}
    fig = render_cc3d_lattice(lattice, type_map)
    assert isinstance(fig, go.Figure)
    # Should have downsampled — trace has <= 2000 points
    total_points = sum(len(t.x) for t in fig.data if hasattr(t, 'x') and t.x is not None)
    assert total_points <= 2000


def test_fallback_when_no_vtk_output():
    from core.cc3d_viz import render_cc3d_lattice
    lattice = {
        "dimensions": (0, 0, 0),
        "cell_ids": np.array([], dtype=np.int32),
        "spacing": (1, 1, 1),
    }
    fig = render_cc3d_lattice(lattice, {})
    assert isinstance(fig, go.Figure)


def test_get_default_type_map():
    from core.cc3d_viz import get_default_type_map
    brief = {"cell_types": ["cardiomyocytes", "fibroblasts", "HUVEC"]}
    tmap = get_default_type_map(brief)
    assert tmap[1] == "cardiomyocytes"
    assert tmap[2] == "fibroblasts"
    assert tmap[3] == "HUVEC"


def test_find_vtk_outputs_empty_dir():
    from core.cc3d_viz import find_vtk_outputs
    result = find_vtk_outputs("/nonexistent/dir")
    assert result == []
