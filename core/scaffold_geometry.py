"""
Parametric scaffold geometry generation, STL import, voxelisation,
and thin-shell extraction for CC3D lattice initialisation.

Supports:
- TPMS scaffolds (gyroid, schwarz-P, diamond, lidinoid)
- Filament lattice scaffolds (woodpile, grid, offset grid)
- Arbitrary STL/OBJ import
- Voxelisation to 3D numpy array
- Thin-shell extraction for CC3D frozen-cell boundaries
- CC3D PIF file export
- Plotly 3D preview rendering
"""

from __future__ import annotations

import io
from typing import Literal, Optional

import numpy as np
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# TPMS implicit surface equations
# ---------------------------------------------------------------------------

_TPMS_FUNCTIONS = {
    "gyroid": lambda x, y, z: (
        np.sin(x) * np.cos(y) + np.sin(y) * np.cos(z) + np.sin(z) * np.cos(x)
    ),
    "schwarz_p": lambda x, y, z: (
        np.cos(x) + np.cos(y) + np.cos(z)
    ),
    "diamond": lambda x, y, z: (
        np.sin(x) * np.sin(y) * np.sin(z)
        + np.sin(x) * np.cos(y) * np.cos(z)
        + np.cos(x) * np.sin(y) * np.cos(z)
        + np.cos(x) * np.cos(y) * np.sin(z)
    ),
    "lidinoid": lambda x, y, z: (
        0.5 * (
            np.sin(2 * x) * np.cos(y) * np.sin(z)
            + np.sin(2 * y) * np.cos(z) * np.sin(x)
            + np.sin(2 * z) * np.cos(x) * np.sin(y)
        )
        - 0.5 * (
            np.cos(2 * x) * np.cos(2 * y)
            + np.cos(2 * y) * np.cos(2 * z)
            + np.cos(2 * z) * np.cos(2 * x)
        )
        + 0.15
    ),
}


def generate_tpms(
    topology: str = "gyroid",
    pore_size_um: float = 300.0,
    porosity_pct: float = 70.0,
    unit_cell_mm: float = 1.0,
    outer_dims_mm: tuple[float, float, float] = (4.0, 4.0, 4.0),
    resolution: int = 80,
) -> dict:
    """Generate a TPMS scaffold as a triangle mesh.

    Returns dict with 'vertices', 'faces' (numpy arrays) and metadata.
    """
    from skimage.measure import marching_cubes

    if topology not in _TPMS_FUNCTIONS:
        raise ValueError(f"Unknown TPMS topology: {topology}. "
                         f"Choose from {list(_TPMS_FUNCTIONS)}")

    func = _TPMS_FUNCTIONS[topology]

    lx, ly, lz = outer_dims_mm
    n_cells_x = max(1, round(lx / unit_cell_mm))
    n_cells_y = max(1, round(ly / unit_cell_mm))
    n_cells_z = max(1, round(lz / unit_cell_mm))

    nx = resolution * n_cells_x
    ny = resolution * n_cells_y
    nz = resolution * n_cells_z

    lin_x = np.linspace(0, 2 * np.pi * n_cells_x, nx)
    lin_y = np.linspace(0, 2 * np.pi * n_cells_y, ny)
    lin_z = np.linspace(0, 2 * np.pi * n_cells_z, nz)
    X, Y, Z = np.meshgrid(lin_x, lin_y, lin_z, indexing="ij")

    field = func(X, Y, Z)

    # Isovalue controls porosity: higher magnitude = thicker walls = lower porosity
    # Binary search for the isovalue that gives target porosity
    target_solid_frac = 1.0 - porosity_pct / 100.0
    lo, hi = float(field.min()), float(field.max())
    for _ in range(30):
        mid = (lo + hi) / 2.0
        solid_frac = float(np.mean(field > mid))
        if solid_frac > target_solid_frac:
            lo = mid
        else:
            hi = mid
    isovalue = (lo + hi) / 2.0

    verts, faces, normals, _ = marching_cubes(field, level=isovalue)

    # Scale vertices from grid indices to mm
    verts[:, 0] *= lx / nx
    verts[:, 1] *= ly / ny
    verts[:, 2] *= lz / nz

    actual_porosity = 1.0 - float(np.mean(field > isovalue))

    return {
        "vertices": verts,
        "faces": faces,
        "normals": normals,
        "topology": topology,
        "unit_cell_mm": unit_cell_mm,
        "outer_dims_mm": (lx, ly, lz),
        "pore_size_um": pore_size_um,
        "porosity_actual": round(actual_porosity * 100, 1),
        "n_vertices": len(verts),
        "n_faces": len(faces),
    }


def generate_filament_lattice(
    strand_diameter_um: float = 400.0,
    strand_spacing_um: float = 800.0,
    layer_height_um: float = 400.0,
    n_layers: int = 8,
    pattern: Literal["woodpile", "grid", "offset"] = "woodpile",
    outer_dims_mm: tuple[float, float, float] = (4.0, 4.0, 3.2),
) -> dict:
    """Generate a filament lattice scaffold as a triangle mesh.

    Uses trimesh to construct cylinders and merge them.
    """
    import trimesh

    d_mm = strand_diameter_um / 1000.0
    spacing_mm = strand_spacing_um / 1000.0
    lh_mm = layer_height_um / 1000.0
    lx, ly, lz = outer_dims_mm
    radius = d_mm / 2.0

    meshes = []
    for layer_idx in range(n_layers):
        z_center = layer_idx * lh_mm + radius
        if z_center > lz:
            break

        is_x_aligned = (layer_idx % 2 == 0)

        offset = (spacing_mm / 2.0) if (pattern == "offset" and layer_idx % 4 >= 2) else 0.0

        if is_x_aligned:
            n_strands = int(ly / spacing_mm) + 1
            for i in range(n_strands):
                y_pos = i * spacing_mm + offset
                if y_pos > ly:
                    break
                cyl = trimesh.creation.cylinder(
                    radius=radius, height=lx,
                    sections=12,
                )
                cyl.apply_translation([lx / 2, y_pos, z_center])
                rot = trimesh.transformations.rotation_matrix(
                    np.pi / 2, [0, 1, 0], point=[lx / 2, y_pos, z_center]
                )
                cyl.apply_transform(rot)
                meshes.append(cyl)
        else:
            n_strands = int(lx / spacing_mm) + 1
            for i in range(n_strands):
                x_pos = i * spacing_mm + offset
                if x_pos > lx:
                    break
                cyl = trimesh.creation.cylinder(
                    radius=radius, height=ly,
                    sections=12,
                )
                cyl.apply_translation([x_pos, ly / 2, z_center])
                rot = trimesh.transformations.rotation_matrix(
                    np.pi / 2, [1, 0, 0], point=[x_pos, ly / 2, z_center]
                )
                cyl.apply_transform(rot)
                meshes.append(cyl)

    if not meshes:
        raise ValueError("No strands generated — check dimensions vs. spacing")

    combined = trimesh.util.concatenate(meshes)

    return {
        "vertices": np.array(combined.vertices),
        "faces": np.array(combined.faces),
        "normals": np.array(combined.face_normals),
        "topology": f"filament_{pattern}",
        "strand_diameter_um": strand_diameter_um,
        "strand_spacing_um": strand_spacing_um,
        "n_layers": n_layers,
        "outer_dims_mm": outer_dims_mm,
        "n_vertices": len(combined.vertices),
        "n_faces": len(combined.faces),
    }


def import_stl(file_bytes: bytes) -> dict:
    """Load an STL or OBJ mesh from raw bytes."""
    import trimesh

    mesh = trimesh.load(io.BytesIO(file_bytes), file_type="stl")
    if hasattr(mesh, "geometry"):
        mesh = trimesh.util.concatenate(list(mesh.geometry.values()))

    return {
        "vertices": np.array(mesh.vertices),
        "faces": np.array(mesh.faces),
        "normals": np.array(mesh.face_normals) if hasattr(mesh, "face_normals") else np.array([]),
        "topology": "custom_stl",
        "outer_dims_mm": tuple(float(v) for v in (mesh.bounds[1] - mesh.bounds[0])),
        "n_vertices": len(mesh.vertices),
        "n_faces": len(mesh.faces),
    }


def voxelise(
    scaffold_mesh: dict,
    resolution_um: float = 5.0,
    lattice_dims: Optional[tuple[int, int, int]] = None,
) -> np.ndarray:
    """Convert a triangle mesh to a 3D boolean voxel grid.

    Returns ndarray of shape (nx, ny, nz) where True = scaffold solid.
    """
    import trimesh

    verts = scaffold_mesh["vertices"]
    faces = scaffold_mesh["faces"]
    mesh = trimesh.Trimesh(vertices=verts, faces=faces)

    if lattice_dims is not None:
        nx, ny, nz = lattice_dims
    else:
        dims_mm = scaffold_mesh.get("outer_dims_mm", tuple(mesh.bounds[1] - mesh.bounds[0]))
        res_mm = resolution_um / 1000.0
        nx = max(10, int(round(dims_mm[0] / res_mm)))
        ny = max(10, int(round(dims_mm[1] / res_mm)))
        nz = max(10, int(round(dims_mm[2] / res_mm)))

    pitch = max(
        (mesh.bounds[1][0] - mesh.bounds[0][0]) / nx,
        (mesh.bounds[1][1] - mesh.bounds[0][1]) / ny,
        (mesh.bounds[1][2] - mesh.bounds[0][2]) / nz,
    )
    vox = mesh.voxelized(pitch=max(pitch, 1e-6))
    grid = vox.matrix

    # Resize to target dimensions if needed
    if grid.shape != (nx, ny, nz):
        from skimage.transform import resize
        grid = resize(grid.astype(float), (nx, ny, nz), order=0, anti_aliasing=False) > 0.5

    return grid.astype(bool)


def extract_thin_shell(voxel_grid: np.ndarray, thickness: int = 2) -> np.ndarray:
    """Extract only the surface voxels of the scaffold (thin shell).

    Erodes the solid interior, keeping a shell of `thickness` voxels.
    """
    from scipy.ndimage import binary_erosion

    if thickness < 1:
        return voxel_grid.copy()

    eroded = binary_erosion(voxel_grid, iterations=thickness)
    shell = voxel_grid & ~eroded
    return shell


def to_pif(
    voxel_grid: np.ndarray,
    cell_type_id: int = 1,
    cell_type_name: str = "Scaffold",
) -> str:
    """Convert a boolean voxel grid to CC3D PIF (Pixel Initialization File).

    Each contiguous scaffold region becomes one "cell" in the PIF. For
    simplicity, each scaffold voxel is its own 1x1x1 cell entry.
    """
    lines = []
    cell_id = 0
    coords = np.argwhere(voxel_grid)
    for x, y, z in coords:
        lines.append(f"{cell_id} {cell_type_name} {x} {x} {y} {y} {z} {z}")
        cell_id += 1
    return "\n".join(lines)


def to_ecm_field(voxel_grid: np.ndarray, density: float = 1.0) -> np.ndarray:
    """Convert a boolean voxel grid to a continuous ECM density field.

    Scaffold voxels get the specified density value; void voxels get 0.
    Used for degradable/gel scaffolds in CC3D's DiffusionSolverFE.
    """
    return voxel_grid.astype(np.float64) * density


def to_stl_bytes(scaffold_mesh: dict) -> bytes:
    """Export a scaffold mesh dict to binary STL bytes for download."""
    import trimesh

    mesh = trimesh.Trimesh(
        vertices=scaffold_mesh["vertices"],
        faces=scaffold_mesh["faces"],
    )
    buffer = io.BytesIO()
    mesh.export(buffer, file_type="stl")
    return buffer.getvalue()


def scaffold_from_text(description: str) -> dict:
    """Parse natural-language scaffold description into generation kwargs.

    Returns a dict with keys 'method' ('tpms' or 'filament') and the
    kwargs to pass to the corresponding generator function.
    Handles common descriptions without requiring an LLM call.
    """
    desc = description.lower()

    tpms_keywords = {
        "gyroid": "gyroid",
        "schwarz": "schwarz_p",
        "schwarz-p": "schwarz_p",
        "diamond": "diamond",
        "lidinoid": "lidinoid",
    }
    filament_keywords = ["woodpile", "filament", "grid", "lattice", "printed", "extru"]

    for keyword, topology in tpms_keywords.items():
        if keyword in desc:
            return {
                "method": "tpms",
                "kwargs": {"topology": topology},
            }

    for keyword in filament_keywords:
        if keyword in desc:
            pattern = "woodpile"
            if "offset" in desc:
                pattern = "offset"
            elif "grid" in desc:
                pattern = "grid"
            return {
                "method": "filament",
                "kwargs": {"pattern": pattern},
            }

    return {"method": "tpms", "kwargs": {"topology": "gyroid"}}


def preview_scaffold(scaffold_mesh: dict, title: str = "Scaffold Preview") -> go.Figure:
    """Render a scaffold mesh as an interactive Plotly Mesh3d figure."""
    verts = scaffold_mesh["vertices"]
    faces = scaffold_mesh["faces"]

    fig = go.Figure()

    fig.add_trace(go.Mesh3d(
        x=verts[:, 0],
        y=verts[:, 1],
        z=verts[:, 2],
        i=faces[:, 0],
        j=faces[:, 1],
        k=faces[:, 2],
        opacity=0.6,
        color="#446688",
        name="Scaffold",
        hovertemplate="x: %{x:.2f}<br>y: %{y:.2f}<br>z: %{z:.2f}<extra></extra>",
    ))

    topo = scaffold_mesh.get("topology", "custom")
    porosity = scaffold_mesh.get("porosity_actual", "?")
    subtitle = f"{topo} | porosity: {porosity}%"

    fig.update_layout(
        title=dict(
            text=f"{title}<br><sub>{subtitle}</sub>",
            font=dict(color="#00ff88", size=14, family="JetBrains Mono"),
        ),
        paper_bgcolor="#0a0a0a",
        scene=dict(
            bgcolor="#111111",
            xaxis=dict(backgroundcolor="#111111", gridcolor="#222222",
                       showbackground=True, title="X (mm)"),
            yaxis=dict(backgroundcolor="#111111", gridcolor="#222222",
                       showbackground=True, title="Y (mm)"),
            zaxis=dict(backgroundcolor="#111111", gridcolor="#222222",
                       showbackground=True, title="Z (mm)"),
            aspectmode="data",
        ),
        margin=dict(l=0, r=0, t=60, b=0),
        height=500,
    )
    return fig
