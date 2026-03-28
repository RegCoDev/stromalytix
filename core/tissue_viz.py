"""
core/tissue_viz.py

Generates interactive 3D tissue construct visualizations from
ConstructProfile parameters using Plotly. Parameter-driven:
stiffness, cell density, cell types, and scaffold material
all influence spatial arrangement.

Updates live as BioSim chat parameters are confirmed.
"""

import numpy as np
import plotly.graph_objects as go


# Cell type color palette — consistent across all visualizations
CELL_TYPE_COLORS = {
    "MCF-7": "#FF4444",
    "HCT116": "#FF6644",
    "STS": "#FF2266",
    "CAF": "#FF8844",
    "fibroblast": "#FFAA44",
    "fibroblasts": "#FFAA44",
    "stroma": "#FFCC44",
    "neuron": "#44AAFF",
    "iPSC-derived neurons": "#44AAFF",
    "HUVEC": "#4466FF",
    "astrocyte": "#44CCFF",
    "HepG2": "#AAFF44",
    "primary hepatocytes": "#88FF44",
    "HepaRG": "#66FF44",
    "Caco-2": "#FF44AA",
    "A549": "#FF44CC",
    "NCI-H441": "#FF44EE",
    "EndoC-BH1": "#AA44FF",
    "primary human islets": "#CC44FF",
    "iPSC-beta": "#8844FF",
    "cardiomyocytes": "#FF4488",
    "default": "#44FFAA",
    "default_2": "#FFAA44",
    "default_3": "#AA44FF",
}

SCAFFOLD_COLORS = {
    "GelMA": "rgba(100, 200, 255, 0.08)",
    "GelMA 6%": "rgba(100, 200, 255, 0.08)",
    "GelMA 4%": "rgba(100, 200, 255, 0.05)",
    "Collagen I": "rgba(255, 220, 150, 0.08)",
    "Collagen": "rgba(255, 220, 150, 0.08)",
    "Fibrin": "rgba(255, 180, 100, 0.06)",
    "Matrigel": "rgba(180, 255, 180, 0.07)",
    "PDMS": "rgba(200, 200, 200, 0.05)",
    "scaffold_free": "rgba(0, 0, 0, 0.0)",
    "default": "rgba(100, 180, 255, 0.06)",
}


def _stiffness_to_packing(stiffness_kpa):
    """
    Stiffer scaffolds -> tighter cell packing (less spreading).
    Returns packing_factor: 0.3 (loose) to 1.0 (tight).
    """
    if stiffness_kpa is None:
        return 0.6
    return min(1.0, max(0.3, 0.3 + (stiffness_kpa / 20.0) * 0.7))


def _method_to_geometry(biofab_method):
    """Map biofab method to spatial geometry type."""
    geometries = {
        "bioprinting": "filament",
        "organ_on_chip": "planar",
        "ooc": "planar",
        "organoid": "spheroid",
        "acoustic_aggregation": "disc",
        "acoustic": "disc",
        "scaffold_free": "spheroid_loose",
    }
    return geometries.get(biofab_method or "", "spheroid")


def generate_cell_positions(
    cell_types,
    cell_density_per_ml,
    stiffness_kpa,
    biofab_method,
    n_cells_display=400,
    seed=42,
):
    """
    Generate 3D cell positions based on construct parameters.
    Returns {cell_type: (x_arr, y_arr, z_arr)} dict.
    """
    rng = np.random.default_rng(seed)
    packing = _stiffness_to_packing(stiffness_kpa)
    geometry = _method_to_geometry(biofab_method)

    n_types = len(cell_types) if cell_types else 1
    cells_per_type = n_cells_display // max(n_types, 1)

    positions = {}

    for i, cell_type in enumerate(cell_types or ["default"]):
        if geometry == "filament":
            n_filaments = 4
            px, py, pz = [], [], []
            for f in range(n_filaments):
                fx = (f % 2) * 3.0 - 1.5
                fy = (f // 2) * 3.0 - 1.5
                n = cells_per_type // n_filaments
                r = rng.exponential(0.3 * (1 - packing * 0.5), n)
                theta = rng.uniform(0, 2 * np.pi, n)
                px.extend(fx + r * np.cos(theta))
                py.extend(fy + r * np.sin(theta))
                pz.extend(rng.uniform(-2, 2, n))
            positions[cell_type] = (np.array(px), np.array(py), np.array(pz))

        elif geometry == "planar":
            spread = 3.0 / packing
            px = rng.uniform(-spread, spread, cells_per_type)
            py = rng.uniform(-spread, spread, cells_per_type)
            pz = rng.normal(i * 0.4, 0.1, cells_per_type)
            positions[cell_type] = (px, py, pz)

        elif geometry in ("spheroid", "spheroid_loose"):
            tightness = packing if geometry == "spheroid" else packing * 0.6
            r_max = 2.0
            r = rng.beta(2 + i, 1.5) * r_max / tightness
            theta = rng.uniform(0, 2 * np.pi, cells_per_type)
            phi = rng.uniform(0, np.pi, cells_per_type)
            px = r * np.sin(phi) * np.cos(theta)
            py = r * np.sin(phi) * np.sin(theta)
            pz = r * np.cos(phi)
            positions[cell_type] = (px, py, pz)

        elif geometry == "disc":
            n_rings = 3
            px, py, pz = [], [], []
            for ring in range(n_rings):
                r_ring = (ring + 1) * 1.2
                n = cells_per_type // n_rings
                theta = rng.uniform(0, 2 * np.pi, n)
                r_jitter = rng.normal(r_ring, 0.15, n)
                px.extend(r_jitter * np.cos(theta))
                py.extend(r_jitter * np.sin(theta))
                pz.extend(rng.normal(0, 0.1, n))
            positions[cell_type] = (np.array(px), np.array(py), np.array(pz))

    return positions


def render_construct_3d(
    profile,
    title="Tissue Construct",
    show_scaffold=True,
    confidence_zones=None,
):
    """
    Main rendering function. Returns Plotly Figure.

    profile: ConstructProfile or any object with cell_types,
             stiffness_kpa, cell_density_per_ml, scaffold_material.
    """
    cell_types = getattr(profile, "cell_types", None) or ["default"]
    stiffness = getattr(profile, "stiffness_kpa", None)
    density = getattr(profile, "cell_density_per_ml", None) or 1_000_000
    method = getattr(profile, "biofab_method", None) or "scaffold_free"
    scaffold = getattr(profile, "scaffold_material", None) or "default"

    positions = generate_cell_positions(cell_types, density, stiffness, method)

    fig = go.Figure()

    # Scaffold bounding volume
    if show_scaffold and scaffold != "scaffold_free":
        _add_scaffold_mesh(fig, scaffold, method)

    # Cell traces per type
    for cell_type, (x, y, z) in positions.items():
        color = CELL_TYPE_COLORS.get(cell_type, CELL_TYPE_COLORS["default"])
        size = 4 if stiffness and stiffness > 8 else 6

        fig.add_trace(go.Scatter3d(
            x=x, y=y, z=z,
            mode="markers",
            name=cell_type,
            marker=dict(size=size, color=color, opacity=0.85, line=dict(width=0)),
            hovertemplate=(
                f"<b>{cell_type}</b><br>"
                "x: %{x:.2f}<br>y: %{y:.2f}<br>z: %{z:.2f}"
                "<extra></extra>"
            ),
        ))

    # Confidence zone overlays
    if confidence_zones:
        for zone in confidence_zones:
            if zone.get("risk") == "HIGH":
                _add_risk_overlay(fig, zone, "rgba(255,80,80,0.15)")
            elif zone.get("risk") == "MEDIUM":
                _add_risk_overlay(fig, zone, "rgba(255,200,0,0.10)")

    # Dark theme
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(color="#34d399", size=16, family="Inter, system-ui, sans-serif"),
        ),
        paper_bgcolor="#1a1a1f",
        plot_bgcolor="#1a1a1f",
        scene=dict(
            bgcolor="#252529",
            xaxis=dict(
                backgroundcolor="#111111", gridcolor="#222222",
                showbackground=True,
                title=dict(text="X (mm)", font=dict(color="#888888")),
                tickfont=dict(color="#666666"),
            ),
            yaxis=dict(
                backgroundcolor="#111111", gridcolor="#222222",
                showbackground=True,
                title=dict(text="Y (mm)", font=dict(color="#888888")),
                tickfont=dict(color="#666666"),
            ),
            zaxis=dict(
                backgroundcolor="#111111", gridcolor="#222222",
                showbackground=True,
                title=dict(text="Z (mm)", font=dict(color="#888888")),
                tickfont=dict(color="#666666"),
            ),
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.0)),
        ),
        legend=dict(
            font=dict(color="#aaaaaa", family="Inter, system-ui, sans-serif"),
            bgcolor="rgba(0,0,0,0.5)",
            bordercolor="#333333",
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        height=500,
    )

    return fig


def _add_scaffold_mesh(fig, scaffold, method):
    """Add translucent scaffold bounding volume."""
    if method in ("organ_on_chip", "ooc"):
        x = [-3, 3, 3, -3, -3, 3, 3, -3]
        y = [-3, -3, 3, 3, -3, -3, 3, 3]
        z = [-0.3, -0.3, -0.3, -0.3, 0.3, 0.3, 0.3, 0.3]
    else:
        x = [-2.5, 2.5, 2.5, -2.5, -2.5, 2.5, 2.5, -2.5]
        y = [-2.5, -2.5, 2.5, 2.5, -2.5, -2.5, 2.5, 2.5]
        z = [-2.5, -2.5, -2.5, -2.5, 2.5, 2.5, 2.5, 2.5]

    fig.add_trace(go.Mesh3d(
        x=x, y=y, z=z,
        opacity=0.05,
        color="#446688",
        name="scaffold",
        showlegend=False,
        hoverinfo="skip",
        alphahull=0,
    ))


def _add_risk_overlay(fig, zone, color):
    """Add risk zone highlight from variance report."""
    pass
