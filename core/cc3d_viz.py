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


def parse_vtk_from_bytes(vtk_bytes: bytes) -> dict:
    """Parse CC3D VTK ASCII structured points from raw bytes.

    Same output format as parse_vtk_lattice but works on in-memory
    bytes (e.g. base64-decoded cloud VTK frames).
    """
    dimensions = (1, 1, 1)
    spacing = (1.0, 1.0, 1.0)
    data = []
    reading_data = False

    text = vtk_bytes.decode("utf-8", errors="replace")
    for line in text.splitlines():
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
    """Extract cell type -> integer ID mapping from CC3D brief.

    Type ID 0 = Medium, 1 = Scaffold, 2+ = cell types.
    """
    cell_types = brief.get("cell_types", []) if isinstance(brief, dict) else []
    tmap = {0: "Medium", 1: "Scaffold"}
    for i, ct in enumerate(cell_types):
        tmap[i + 2] = ct
    return tmap


def parse_vtk_scalar_field(vtk_bytes: bytes) -> dict:
    """Parse a VTK structured points file containing a continuous scalar field.

    Returns:
        {
            "dimensions": (nx, ny, nz),
            "values": ndarray of float64 (flat),
            "spacing": (dx, dy, dz),
            "field_name": str,
        }
    """
    dimensions = (1, 1, 1)
    spacing = (1.0, 1.0, 1.0)
    data: list[float] = []
    reading_data = False
    field_name = "unknown"

    text = vtk_bytes.decode("utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("DIMENSIONS"):
            parts = line.split()
            dimensions = (int(parts[1]), int(parts[2]), int(parts[3]))
        elif line.startswith("SPACING") or line.startswith("ASPECT_RATIO"):
            parts = line.split()
            spacing = (float(parts[1]), float(parts[2]), float(parts[3]))
        elif line.startswith("SCALARS"):
            parts = line.split()
            if len(parts) >= 2:
                field_name = parts[1]
        elif line.startswith("LOOKUP_TABLE"):
            reading_data = True
            continue
        elif reading_data:
            for val in line.split():
                try:
                    data.append(float(val))
                except ValueError:
                    pass

    values = np.array(data, dtype=np.float64) if data else np.array([], dtype=np.float64)

    return {
        "dimensions": dimensions,
        "values": values,
        "spacing": spacing,
        "field_name": field_name,
    }


def render_o2_overlay(
    o2_field: dict,
    threshold: float = 0.02,
    title: str = "O2 Concentration",
) -> go.Figure:
    """Render O2 concentration field as a Plotly isosurface / 3D scatter.

    Low-O2 regions (hypoxic) are highlighted in red; high-O2 in blue.
    """
    dims = o2_field["dimensions"]
    values = o2_field["values"]
    dx, dy, dz = o2_field["spacing"]

    nx, ny, nz = dims
    if len(values) != nx * ny * nz:
        fig = go.Figure()
        fig.add_annotation(text="O2 field data size mismatch",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font=dict(color="#888", size=14))
        fig.update_layout(paper_bgcolor="#0a0a0a", height=300)
        return fig

    grid = values.reshape((nx, ny, nz))

    # Sample points for visualization (cap at 3000 for performance)
    ix, iy, iz = np.where(np.ones_like(grid, dtype=bool))
    max_pts = 3000
    if len(ix) > max_pts:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(ix), max_pts, replace=False)
        ix, iy, iz = ix[idx], iy[idx], iz[idx]

    o2_vals = grid[ix, iy, iz]

    fig = go.Figure()

    fig.add_trace(go.Scatter3d(
        x=ix * dx, y=iy * dy, z=iz * dz,
        mode="markers",
        marker=dict(
            size=2,
            color=o2_vals,
            colorscale="RdBu",
            cmin=0,
            cmax=max(0.21, float(o2_vals.max())),
            colorbar=dict(
                title="O2",
                tickfont=dict(color="#aaa"),
                titlefont=dict(color="#aaa"),
            ),
            opacity=0.4,
        ),
        name="O2",
        hovertemplate="O2: %{marker.color:.4f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text=title, font=dict(color="#00ff88", size=14, family="JetBrains Mono")),
        paper_bgcolor="#0a0a0a",
        scene=dict(
            bgcolor="#111111",
            xaxis=dict(backgroundcolor="#111111", gridcolor="#222222", showbackground=True),
            yaxis=dict(backgroundcolor="#111111", gridcolor="#222222", showbackground=True),
            zaxis=dict(backgroundcolor="#111111", gridcolor="#222222", showbackground=True),
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        height=450,
    )
    return fig


def render_unified_scene(
    cell_lattice: dict | None,
    type_map: dict | None,
    o2_field: dict | None = None,
    scaffold_mesh: dict | None = None,
    title: str = "Unified Simulation View",
    timestep: int | None = None,
) -> go.Figure:
    """Combine scaffold mesh, cell lattice, and O2 field into one Plotly figure."""
    fig = go.Figure()

    # Scaffold mesh (semi-transparent surface)
    if scaffold_mesh is not None:
        verts = scaffold_mesh.get("vertices")
        faces = scaffold_mesh.get("faces")
        if verts is not None and faces is not None and len(verts) > 0:
            fig.add_trace(go.Mesh3d(
                x=verts[:, 0], y=verts[:, 1], z=verts[:, 2],
                i=faces[:, 0], j=faces[:, 1], k=faces[:, 2],
                opacity=0.15,
                color="#446688",
                name="Scaffold",
            ))

    # Cell lattice
    if cell_lattice is not None and type_map is not None:
        cell_ids = cell_lattice["cell_ids"]
        dims = cell_lattice["dimensions"]
        dx, dy, dz = cell_lattice["spacing"]

        nx, ny, nz = dims
        if len(cell_ids) == nx * ny * nz:
            grid = cell_ids.reshape((nx, ny, nz))
        else:
            n = len(cell_ids)
            side = max(1, int(np.ceil(n ** (1 / 3))))
            grid = np.zeros((side, side, side), dtype=np.int32)
            grid.flat[:n] = cell_ids
            nx, ny, nz = side, side, side

        # Skip medium (0) and optionally scaffold (1) for cell display
        ix, iy, iz = np.where(grid > 1)
        max_display = 2000
        if len(ix) > max_display:
            rng = np.random.default_rng(42)
            idx = rng.choice(len(ix), max_display, replace=False)
            ix, iy, iz = ix[idx], iy[idx], iz[idx]

        types = cc3d_ids_to_types(grid[ix, iy, iz], type_map)

        for cell_type in np.unique(types):
            if cell_type in ("empty", "Medium", "Scaffold"):
                continue
            mask = types == cell_type
            color = CELL_TYPE_COLORS.get(cell_type, CELL_TYPE_COLORS["default"])
            fig.add_trace(go.Scatter3d(
                x=ix[mask] * dx, y=iy[mask] * dy, z=iz[mask] * dz,
                mode="markers",
                name=str(cell_type),
                marker=dict(size=3, color=color, opacity=0.8),
            ))

    # O2 field overlay
    if o2_field is not None:
        o2_dims = o2_field["dimensions"]
        o2_vals = o2_field["values"]
        o2_dx, o2_dy, o2_dz = o2_field["spacing"]
        o2_nx, o2_ny, o2_nz = o2_dims

        if len(o2_vals) == o2_nx * o2_ny * o2_nz:
            o2_grid = o2_vals.reshape((o2_nx, o2_ny, o2_nz))
            # Only show hypoxic regions (O2 < 5% ≈ 0.05)
            ix_o2, iy_o2, iz_o2 = np.where(o2_grid < 0.05)

            max_pts = 1500
            if len(ix_o2) > max_pts:
                rng = np.random.default_rng(7)
                idx = rng.choice(len(ix_o2), max_pts, replace=False)
                ix_o2, iy_o2, iz_o2 = ix_o2[idx], iy_o2[idx], iz_o2[idx]

            if len(ix_o2) > 0:
                fig.add_trace(go.Scatter3d(
                    x=ix_o2 * o2_dx, y=iy_o2 * o2_dy, z=iz_o2 * o2_dz,
                    mode="markers",
                    name="Hypoxic zone",
                    marker=dict(size=2, color="#ff4444", opacity=0.25),
                    hovertemplate="Hypoxic<extra></extra>",
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
                       showbackground=True, title="X"),
            yaxis=dict(backgroundcolor="#111111", gridcolor="#222222",
                       showbackground=True, title="Y"),
            zaxis=dict(backgroundcolor="#111111", gridcolor="#222222",
                       showbackground=True, title="Z"),
            aspectmode="data",
        ),
        margin=dict(l=0, r=0, t=50, b=0),
        height=500,
        legend=dict(font=dict(color="#aaa")),
    )

    if not fig.data:
        fig.add_annotation(
            text="No simulation data to display",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(color="#888", size=16),
        )

    return fig
