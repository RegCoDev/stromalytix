"""
core/cc3d_viz.py

Parses CC3D simulation VTK output and renders as interactive
3D Plotly visualization.

CC3D output structure:
- {run_dir}/LatticeData/CellField_*.vtk — cell lattice at each timestep
- VTK contains integer cell IDs per voxel
- Cell type map from simulation XML

Falls back gracefully if VTK files not found (e.g., Streamlit Cloud).
"""

import re
from pathlib import Path

import numpy as np
import plotly.graph_objects as go

from core.tissue_viz import CELL_TYPE_COLORS


def find_vtk_outputs(run_dir: str) -> list:
    """Find VTK output files sorted by timestep."""
    run_path = Path(run_dir)
    patterns = [
        "LatticeData/CellField_*.vtk",
        "CellField_*.vtk",
        "*.vtk",
    ]
    for pattern in patterns:
        files = sorted(run_path.glob(pattern))
        if files:
            return [str(f) for f in files]
    return []


def parse_vtk_lattice(vtk_path: str) -> dict:
    """
    Parse CC3D VTK ASCII structured points file.
    Minimal parser — no vtk library dependency.

    Returns:
    {
      dimensions: (nx, ny, nz),
      cell_ids: ndarray (flat),
      spacing: (dx, dy, dz),
    }
    """
    path = Path(vtk_path)
    if not path.exists():
        return {"dimensions": (0, 0, 0), "cell_ids": np.array([]), "spacing": (1, 1, 1)}

    dimensions = (1, 1, 1)
    spacing = (1.0, 1.0, 1.0)
    data = []
    reading_data = False

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DIMENSIONS"):
                parts = line.split()
                dimensions = (int(parts[1]), int(parts[2]), int(parts[3]))
            elif line.startswith("SPACING") or line.startswith("ASPECT_RATIO"):
                parts = line.split()
                spacing = (float(parts[1]), float(parts[2]), float(parts[3]))
            elif line.startswith("LOOKUP_TABLE"):
                reading_data = True
                continue
            elif reading_data:
                for val in line.split():
                    try:
                        data.append(int(float(val)))
                    except ValueError:
                        pass

    cell_ids = np.array(data, dtype=np.int32) if data else np.array([], dtype=np.int32)

    return {
        "dimensions": dimensions,
        "cell_ids": cell_ids,
        "spacing": spacing,
    }


def cc3d_ids_to_types(cell_ids, type_map):
    """Map integer CC3D cell IDs to type names."""
    result = np.array(["empty"] * len(cell_ids), dtype=object)
    for int_id, type_name in type_map.items():
        mask = cell_ids == int_id
        result[mask] = type_name
    return result


def render_cc3d_lattice(
    lattice,
    type_map,
    title="CC3D Simulation",
    timestep=None,
    threshold_empty=0,
):
    """
    Render CC3D voxel lattice as 3D Plotly scatter.
    Downsamples for browser performance (max 2000 voxels).
    """
    cell_ids = lattice["cell_ids"]
    dims = lattice["dimensions"]
    dx, dy, dz = lattice["spacing"]

    if len(cell_ids) == 0:
        fig = go.Figure()
        fig.add_annotation(text="No VTK data available", xref="paper",
                           yref="paper", x=0.5, y=0.5, showarrow=False,
                           font=dict(color="#888", size=16))
        fig.update_layout(paper_bgcolor="#0a0a0a", height=300)
        return fig

    # Reshape to 3D if possible
    nx, ny, nz = dims
    if len(cell_ids) == nx * ny * nz:
        grid = cell_ids.reshape((nx, ny, nz))
    else:
        # Flat array — create synthetic 3D positions
        n = len(cell_ids)
        side = int(np.ceil(n ** (1 / 3)))
        grid = np.zeros((side, side, side), dtype=np.int32)
        grid.flat[:n] = cell_ids
        nx, ny, nz = side, side, side

    # Find occupied voxels
    ix, iy, iz = np.where(grid > threshold_empty)

    # Downsample if needed
    max_display = 2000
    if len(ix) > max_display:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(ix), max_display, replace=False)
        ix, iy, iz = ix[idx], iy[idx], iz[idx]

    types = cc3d_ids_to_types(grid[ix, iy, iz], type_map)

    fig = go.Figure()

    for cell_type in np.unique(types):
        if cell_type == "empty":
            continue
        mask = types == cell_type
        color = CELL_TYPE_COLORS.get(cell_type, CELL_TYPE_COLORS["default"])

        fig.add_trace(go.Scatter3d(
            x=ix[mask] * dx,
            y=iy[mask] * dy,
            z=iz[mask] * dz,
            mode="markers",
            name=str(cell_type),
            marker=dict(size=3, color=color, opacity=0.7),
        ))

    ts_label = f" — t={timestep}" if timestep is not None else ""
    fig.update_layout(
        title=dict(
            text=f"{title}{ts_label}",
            font=dict(color="#00ff88", size=14, family="JetBrains Mono"),
        ),
        paper_bgcolor="#0a0a0a",
        scene=dict(
            bgcolor="#111111",
            xaxis=dict(backgroundcolor="#111111", gridcolor="#222222",
                       showbackground=True),
            yaxis=dict(backgroundcolor="#111111", gridcolor="#222222",
                       showbackground=True),
            zaxis=dict(backgroundcolor="#111111", gridcolor="#222222",
                       showbackground=True),
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        height=450,
    )
    return fig


def get_default_type_map(brief):
    """Extract cell type -> integer ID mapping from CC3D brief."""
    cell_types = brief.get("cell_types", []) if isinstance(brief, dict) else []
    return {i + 1: ct for i, ct in enumerate(cell_types)}
