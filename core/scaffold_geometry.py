"""
Parametric scaffold geometry generation, STL import, voxelisation,
and thin-shell extraction for CC3D lattice initialisation.

Supports:
- TPMS scaffolds (gyroid, schwarz-P, diamond, lidinoid)
- Filament lattice scaffolds (woodpile, grid, offset grid)
- Simple primitives: solid/hollow cylinder, torus ring, spherical droplet,
  droplet-in-droplet / core–shell (multimaterial preview)
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


def _fit_mesh_to_box(tm, outer_dims_mm: tuple[float, float, float]):
    """Translate mesh: min z = 0, centered in x,y within lx, ly."""
    import trimesh

    lx, ly, _ = outer_dims_mm
    m = tm.copy()
    b = m.bounds
    center_xy = (b[0][:2] + b[1][:2]) / 2.0
    m.apply_translation([lx / 2 - center_xy[0], ly / 2 - center_xy[1], -b[0][2]])
    return m


def _mesh_dict_single(
    tm,
    topology: str,
    outer_dims_mm: tuple[float, float, float],
    **extra,
) -> dict:
    import trimesh

    m = _fit_mesh_to_box(tm, outer_dims_mm)
    ext = m.bounds[1] - m.bounds[0]
    dims = (float(ext[0]), float(ext[1]), float(ext[2]))
    out = {
        "vertices": np.array(m.vertices),
        "faces": np.array(m.faces),
        "normals": np.array(m.face_normals),
        "topology": topology,
        "outer_dims_mm": dims,
        "n_vertices": len(m.vertices),
        "n_faces": len(m.faces),
    }
    out.update(extra)
    return out


def _boolean_difference(a, b, label: str):
    """Try mesh boolean engines; return None on failure."""
    import trimesh

    for engine in ("manifold", "blender", "scad"):
        try:
            return trimesh.boolean.difference([a, b], engine=engine)
        except Exception:
            continue
    return None


def generate_cylinder_solid(
    radius_mm: float = 1.5,
    height_mm: float = 4.0,
    outer_dims_mm: tuple[float, float, float] = (4.0, 4.0, 4.0),
    sections: int = 48,
) -> dict:
    """Right circular cylinder (solid), axis vertical (Z)."""
    import trimesh

    cyl = trimesh.creation.cylinder(radius=radius_mm, height=height_mm, sections=sections)
    return _mesh_dict_single(cyl, "cylinder_solid", outer_dims_mm, radius_mm=radius_mm, height_mm=height_mm)


def generate_cylinder_hollow(
    outer_radius_mm: float = 1.8,
    inner_radius_mm: float = 1.2,
    height_mm: float = 4.0,
    outer_dims_mm: tuple[float, float, float] = (4.0, 4.0, 4.0),
    sections: int = 48,
) -> dict:
    """Hollow tube: outer cylinder minus inner (open ends)."""
    import trimesh

    outer = trimesh.creation.cylinder(radius=outer_radius_mm, height=height_mm, sections=sections)
    inner = trimesh.creation.cylinder(
        radius=inner_radius_mm, height=height_mm + 0.05, sections=max(sections // 2, 16)
    )
    diff = _boolean_difference(outer, inner, "hollow_cylinder")
    if diff is None or diff.is_empty:
        # Fallback: solid outer so preview still works without manifold/blender
        return _mesh_dict_single(
            outer,
            "cylinder_hollow_fallback_solid",
            outer_dims_mm,
            hollow_note=(
                "Hollow tube needs a mesh boolean engine (e.g. manifold) on the server — "
                "showing solid outer cylinder only."
            ),
            outer_radius_mm=outer_radius_mm,
            inner_radius_mm=inner_radius_mm,
            height_mm=height_mm,
        )
    return _mesh_dict_single(
        diff,
        "cylinder_hollow",
        outer_dims_mm,
        outer_radius_mm=outer_radius_mm,
        inner_radius_mm=inner_radius_mm,
        height_mm=height_mm,
    )


def _torus_trimesh(
    major_radius_mm: float,
    minor_radius_mm: float,
    major_sections: int = 48,
    minor_sections: int = 24,
):
    """Parametric torus centered at origin, major circle in XY plane."""
    import trimesh

    u = np.linspace(0, 2 * np.pi, major_sections, endpoint=False)
    v = np.linspace(0, 2 * np.pi, minor_sections, endpoint=False)
    verts = []
    for ui in u:
        for vj in v:
            x = (major_radius_mm + minor_radius_mm * np.cos(vj)) * np.cos(ui)
            y = (major_radius_mm + minor_radius_mm * np.cos(vj)) * np.sin(ui)
            z = minor_radius_mm * np.sin(vj)
            verts.append([x, y, z])
    verts = np.array(verts, dtype=np.float64)
    faces = []
    nu, nv = major_sections, minor_sections
    for i in range(nu):
        for j in range(nv):
            i1 = (i + 1) % nu
            j1 = (j + 1) % nv
            a = i * nv + j
            b = i1 * nv + j
            c = i1 * nv + j1
            d = i * nv + j1
            faces.append([a, b, c])
            faces.append([a, c, d])
    faces = np.array(faces, dtype=np.int64)
    return trimesh.Trimesh(vertices=verts, faces=faces, process=False)


def generate_ring_torus(
    major_radius_mm: float = 1.8,
    minor_radius_mm: float = 0.35,
    outer_dims_mm: tuple[float, float, float] = (4.0, 4.0, 2.5),
    major_sections: int = 48,
    minor_sections: int = 20,
) -> dict:
    """Ring / donut torus (hollow tube bent into a circle)."""
    tor = _torus_trimesh(major_radius_mm, minor_radius_mm, major_sections, minor_sections)
    return _mesh_dict_single(
        tor,
        "ring_torus",
        outer_dims_mm,
        major_radius_mm=major_radius_mm,
        minor_radius_mm=minor_radius_mm,
    )


def generate_sphere_droplet(
    radius_mm: float = 1.5,
    outer_dims_mm: tuple[float, float, float] = (4.0, 4.0, 4.0),
    subdivisions: int = 3,
) -> dict:
    """Spherical droplet / bead (icosphere)."""
    import trimesh

    sph = trimesh.creation.icosphere(subdivisions=subdivisions, radius=radius_mm)
    return _mesh_dict_single(sph, "sphere_droplet", outer_dims_mm, radius_mm=radius_mm)


def generate_droplet_in_droplet(
    outer_radius_mm: float = 2.0,
    core_radius_mm: float = 1.0,
    outer_dims_mm: tuple[float, float, float] = (4.5, 4.5, 4.5),
    subdivisions: int = 3,
) -> dict:
    """Core–shell: inner solid droplet + outer shell (multimaterial-style preview).

    Outer region is hollow ball minus inner ball; inner ball is separate mesh.
    """
    import trimesh

    outer_sph = trimesh.creation.icosphere(subdivisions=subdivisions, radius=outer_radius_mm)
    inner_sph = trimesh.creation.icosphere(subdivisions=max(subdivisions - 1, 2), radius=core_radius_mm)
    shell = _boolean_difference(outer_sph, inner_sph, "shell")
    core = inner_sph.copy()

    if shell is None or shell.is_empty:
        # Fallback: show two concentric spheres (slightly scaled core for visibility)
        core = trimesh.creation.icosphere(subdivisions=max(subdivisions - 1, 2), radius=core_radius_mm * 0.95)
        shell = outer_sph
        note = "Boolean unavailable — outer shown solid; core shown slightly inset."
    else:
        note = ""

    shell_f = _fit_mesh_to_box(shell, outer_dims_mm)
    core_f = _fit_mesh_to_box(core, outer_dims_mm)
    combined = trimesh.util.concatenate([shell_f, core_f])
    ext = shell_f.bounds[1] - shell_f.bounds[0]
    dims = (float(ext[0]), float(ext[1]), float(ext[2]))

    return {
        "vertices": np.array(combined.vertices),
        "faces": np.array(combined.faces),
        "normals": np.array(combined.face_normals),
        "topology": "droplet_in_droplet",
        "outer_dims_mm": dims,
        "n_vertices": len(combined.vertices),
        "n_faces": len(combined.faces),
        "multimaterial": True,
        "components": [
            {
                "name": "Outer shell / matrix",
                "vertices": np.array(shell_f.vertices),
                "faces": np.array(shell_f.faces),
                "color": "#3d7a9e",
            },
            {
                "name": "Inner droplet / core",
                "vertices": np.array(core_f.vertices),
                "faces": np.array(core_f.faces),
                "color": "#c9a227",
            },
        ],
        "outer_radius_mm": outer_radius_mm,
        "core_radius_mm": core_radius_mm,
        "hollow_note": note,
    }


def generate_line_filament(
    radius_mm: float = 0.3,
    length_mm: float = 6.0,
    outer_dims_mm: tuple[float, float, float] = (7.0, 2.0, 2.0),
    sections: int = 24,
) -> dict:
    """Single filament / rod / line along the X axis."""
    import trimesh

    cyl = trimesh.creation.cylinder(radius=radius_mm, height=length_mm, sections=sections)
    # Rotate so axis is along X instead of Z
    rot = trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0])
    cyl.apply_transform(rot)
    return _mesh_dict_single(cyl, "line_filament", outer_dims_mm, radius_mm=radius_mm, length_mm=length_mm)


def generate_disc(
    radius_mm: float = 2.0,
    thickness_mm: float = 0.5,
    outer_dims_mm: tuple[float, float, float] = (5.0, 5.0, 2.0),
    sections: int = 48,
) -> dict:
    """Flat disc / disk (short cylinder)."""
    import trimesh

    cyl = trimesh.creation.cylinder(radius=radius_mm, height=thickness_mm, sections=sections)
    return _mesh_dict_single(cyl, "disc", outer_dims_mm, radius_mm=radius_mm, thickness_mm=thickness_mm)


def generate_tube(
    outer_radius_mm: float = 1.5,
    inner_radius_mm: float = 1.0,
    length_mm: float = 6.0,
    outer_dims_mm: tuple[float, float, float] = (7.0, 4.0, 4.0),
    sections: int = 48,
) -> dict:
    """Hollow tube / cannula along the X axis (open ends)."""
    import trimesh

    outer = trimesh.creation.cylinder(radius=outer_radius_mm, height=length_mm, sections=sections)
    inner = trimesh.creation.cylinder(
        radius=inner_radius_mm, height=length_mm + 0.05, sections=max(sections // 2, 16)
    )
    diff = _boolean_difference(outer, inner, "tube")
    # Rotate so axis is along X
    rot = trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0])
    if diff is None or diff.is_empty:
        outer.apply_transform(rot)
        return _mesh_dict_single(
            outer, "tube_fallback_solid", outer_dims_mm,
            hollow_note="Boolean engine unavailable — showing solid cylinder.",
            outer_radius_mm=outer_radius_mm, inner_radius_mm=inner_radius_mm, length_mm=length_mm,
        )
    diff.apply_transform(rot)
    return _mesh_dict_single(
        diff, "tube", outer_dims_mm,
        outer_radius_mm=outer_radius_mm, inner_radius_mm=inner_radius_mm, length_mm=length_mm,
    )


def generate_multimaterial_bilayer_cylinder(
    outer_radius_mm: float = 2.0,
    inner_radius_mm: float = 1.4,
    height_mm: float = 3.0,
    outer_dims_mm: tuple[float, float, float] = (4.5, 4.5, 4.0),
    sections: int = 40,
) -> dict:
    """Two coaxial solid cylinders (outer ring + inner core), different materials in preview."""
    import trimesh

    outer = trimesh.creation.cylinder(radius=outer_radius_mm, height=height_mm, sections=sections)
    inner = trimesh.creation.cylinder(radius=inner_radius_mm, height=height_mm * 1.01, sections=sections)
    outer_f = _fit_mesh_to_box(outer, outer_dims_mm)
    inner_f = _fit_mesh_to_box(inner, outer_dims_mm)
    combined = trimesh.util.concatenate([outer_f, inner_f])
    ext = outer_f.bounds[1] - outer_f.bounds[0]
    dims = (float(ext[0]), float(ext[1]), float(ext[2]))
    return {
        "vertices": np.array(combined.vertices),
        "faces": np.array(combined.faces),
        "normals": np.array(combined.face_normals),
        "topology": "multimaterial_bilayer_cylinder",
        "outer_dims_mm": dims,
        "n_vertices": len(combined.vertices),
        "n_faces": len(combined.faces),
        "multimaterial": True,
        "components": [
            {
                "name": "Outer material",
                "vertices": np.array(outer_f.vertices),
                "faces": np.array(outer_f.faces),
                "color": "#2e8b57",
            },
            {
                "name": "Inner material",
                "vertices": np.array(inner_f.vertices),
                "faces": np.array(inner_f.faces),
                "color": "#8b4513",
            },
        ],
        "outer_radius_mm": outer_radius_mm,
        "inner_radius_mm": inner_radius_mm,
        "height_mm": height_mm,
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

    comps = scaffold_mesh.get("components")
    if comps:
        parts = [
            trimesh.Trimesh(np.asarray(c["vertices"]), np.asarray(c["faces"]), process=False)
            for c in comps
        ]
        mesh = trimesh.util.concatenate(parts)
    else:
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
    if any(k in desc for k in ("torus", "ring", "donut")):
        return {"method": "simple", "kwargs": {"kind": "ring_torus"}}
    if any(k in desc for k in ("tube", "cannula", "hollow tube")):
        return {"method": "simple", "kwargs": {"kind": "tube"}}
    if "hollow" in desc and "cylind" in desc:
        return {"method": "simple", "kwargs": {"kind": "cylinder_hollow"}}
    if any(k in desc for k in ("disc", "disk", "wafer", "flat")):
        return {"method": "simple", "kwargs": {"kind": "disc"}}
    if any(k in desc for k in ("line", "filament", "fiber", "fibre", "strand")):
        return {"method": "simple", "kwargs": {"kind": "line_filament"}}
    if "cylind" in desc or "rod" in desc:
        return {"method": "simple", "kwargs": {"kind": "cylinder_solid"}}
    if any(k in desc for k in ("droplet", "bead", "microsphere", "sphere")) and "shell" in desc:
        return {"method": "simple", "kwargs": {"kind": "droplet_in_droplet"}}
    if "droplet" in desc or "bead" in desc or "microsphere" in desc:
        return {"method": "simple", "kwargs": {"kind": "sphere_droplet"}}
    if "bilayer" in desc or "core-shell" in desc or "coaxial" in desc:
        return {"method": "simple", "kwargs": {"kind": "multimaterial_bilayer_cylinder"}}

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
    fig = go.Figure()

    components = scaffold_mesh.get("components")
    if components:
        for comp in components:
            v = np.asarray(comp["vertices"])
            f = np.asarray(comp["faces"])
            fig.add_trace(
                go.Mesh3d(
                    x=v[:, 0],
                    y=v[:, 1],
                    z=v[:, 2],
                    i=f[:, 0],
                    j=f[:, 1],
                    k=f[:, 2],
                    opacity=0.62,
                    color=comp.get("color", "#446688"),
                    name=comp.get("name", "part"),
                    hovertemplate="x: %{x:.2f}<br>y: %{y:.2f}<br>z: %{z:.2f}<extra></extra>",
                )
            )
    else:
        verts = scaffold_mesh["vertices"]
        faces = scaffold_mesh["faces"]
        fig.add_trace(
            go.Mesh3d(
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
            )
        )

    topo = scaffold_mesh.get("topology", "custom")
    porosity = scaffold_mesh.get("porosity_actual", "?")
    mm = "multimaterial" if scaffold_mesh.get("multimaterial") else None
    hn = scaffold_mesh.get("hollow_note")
    subtitle = f"{topo} | porosity: {porosity}%"
    if mm:
        subtitle = f"{topo} | {mm}"
    if hn:
        subtitle = f"{subtitle} | {hn}"

    fig.update_layout(
        title=dict(
            text=f"{title}<br><sub>{subtitle}</sub>",
            font=dict(color="#34d399", size=14, family="Inter, system-ui, sans-serif"),
        ),
        paper_bgcolor="#1a1a1f",
        scene=dict(
            bgcolor="#252529",
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
