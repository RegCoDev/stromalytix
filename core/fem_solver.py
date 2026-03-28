"""
Scaffold mechanics — linear-elastic sketches only.

Most biofabrication matrices are viscoelastic (stress relaxation, creep, rate dependence).
These helpers use **Hookean / elastic heuristics** for order-of-magnitude intuition, not
cell-scale mechanotransduction maps or polymer rupture criteria.

**Not modeled (any path in this module):** solvent **swelling** / deswelling; **hydrolytic**
degradation; **enzymolytic** erosion (e.g. MMPs); mass loss or **porosity evolving in time**;
pH / ionic / Donnan effects; or coupled chemo-mechanical **pore collapse**. Mentions of
pore collapse in user-facing text are **qualitative integrity hints** under a fixed-geometry
elastic snapshot—not a simulation of degradation kinetics.

- predict_scaffold_deformation: toy bulk strain under assumed contractile loading
  → interpret as **construct integrity / gross deformation**, not mechanoreceptor signaling.
- predict_stress_distribution: porosity-based elastic stress-hotspot index
  → **load path / structural heterogeneity** intuition; not nucleus-scale sensing.
- solve_compression / render_fea_results: coarse scikit-fem linear elastic compression.

scikit-fem: MIT licensed. Safe for commercial use.
"""

import numpy as np
import plotly.graph_objects as go

# Shown in Streamlit next to mechanics readouts — single source of truth.
FEM_EXCLUDED_PHYSICS_SUMMARY = (
    "**Not modeled:** matrix **swelling** or syneresis; **hydrolytic** or **enzymolytic** "
    "(e.g. MMP) degradation and mass loss; **time-dependent** porosity or modulus; "
    "chemo-mechanical **pore collapse** kinetics; pH/ionic coupling. "
    "All plots use **instant linear elasticity** on your **nominal** geometry and stiffness."
)


def predict_scaffold_deformation(
    stiffness_kpa: float,
    cell_density_per_ml: float,
    construct_height_mm: float = 3.0,
) -> dict:
    """
    Simple compression model: estimate scaffold deformation
    under collective cell contractile force.

    Cell contractile stress: ~1-10 nN/cell (use 5 nN typical).

    Does not include swelling, degradation, or evolving porosity — see FEM_EXCLUDED_PHYSICS_SUMMARY.
    """
    # Collective contractile force
    # Volume: 1cm x 1cm cross section * height
    cell_volume_ml = 1.0 * 1.0 * (construct_height_mm / 10.0)  # cm^3 = mL
    n_cells = cell_density_per_ml * cell_volume_ml
    contractile_force_nN = n_cells * 5.0  # 5 nN/cell typical

    # Convert to stress (assume 1cm x 1cm cross section)
    area_m2 = 1e-4
    stress_pa = (contractile_force_nN * 1e-9) / area_m2
    stress_kpa_val = stress_pa / 1000

    # Deformation from Hooke's law: delta = F*L/(E*A)
    E_pa = stiffness_kpa * 1000
    height_m = construct_height_mm * 1e-3
    deformation_m = (contractile_force_nN * 1e-9 * height_m) / (E_pa * area_m2)
    deformation_um = deformation_m * 1e6
    strain_pct = (deformation_m / height_m) * 100

    # Tiered readout: bulk construct strain / integrity (NOT biological "cell failure")
    if strain_pct > 15:
        risk = "high"
        rec = (
            f"**Bulk strain ~{strain_pct:.1f}%** in this simplified elastic slab model: high risk of "
            f"**macroscopic construct issues** (tear, delamination, pore collapse, loss of shape)—not a diagnosis "
            f"of apoptosis or mechanoreceptor overload. Consider higher modulus, lower cell density in the model, "
            f"or a thinner construct for the assumed footprint."
        )
    elif strain_pct > 5:
        risk = "medium"
        rec = (
            f"Moderate **bulk strain ({strain_pct:.1f}%)**: monitor **mechanical integrity** (buckling, necking, "
            f"**pore collapse** under sustained load in soft lattices—named here only qualitatively; not simulated). "
            f"Viscoelastic matrices often relax stress over time; swelling or enzyme-driven softening can worsen "
            f"collapse but are **outside** this model."
        )
    else:
        risk = "low"
        rec = (
            f"Low bulk strain ({strain_pct:.1f}%) in this toy model: **construct shape** likely stable under the "
            f"assumed collective traction. Does not rule out local defects or time-dependent flow."
        )

    return {
        "max_deformation_um": round(deformation_um, 2),
        "strain_percent": round(strain_pct, 2),
        "stress_kpa": round(stress_kpa_val, 4),
        "failure_risk": risk,
        "failure_risk_explainer": (
            "“Failure” here means **gross scaffold / construct integrity** under this crude elastic estimate—not "
            "material rupture prediction and not single-cell mechanosensing. "
            "**Pore collapse** is a real failure mode but is **not** computed here beyond qualitative mention."
        ),
        "excluded_physics_summary": FEM_EXCLUDED_PHYSICS_SUMMARY,
        "recommendation": rec,
        "n_cells_estimated": int(n_cells),
        "collective_force_nN": round(contractile_force_nN, 1),
    }


def predict_stress_distribution(
    stiffness_kpa: float,
    porosity_percent: float = 80.0,
) -> dict:
    """
    Porosity-based **elastic** stress-hotspot index (Kt) and effective-modulus proxy.

    Kt is a textbook-style concentration heuristic for **porous linear solids** under load:
    useful for thinking about **strut overload and uneven load paths**, not for mapping
    integrin–nucleus mechanotransduction (which depends on matrix viscoelasticity, adhesion,
    cell traction, and time). Real hydrogels redistribute stress via relaxation and fluid flow.
    """
    relative_density = 1 - (porosity_percent / 100)
    if relative_density > 0:
        Kt = 1 + 2 * (1 - relative_density) / relative_density
    else:
        Kt = 10.0

    effective_stiffness = stiffness_kpa * (relative_density ** 2)

    if Kt > 3:
        het_risk = "high"
    elif Kt > 2:
        het_risk = "medium"
    else:
        het_risk = "low"

    return {
        "stress_concentration_factor": round(Kt, 2),
        "effective_local_stiffness_kpa": round(effective_stiffness, 2),
        "heterogeneity_risk": het_risk,
        "elastic_hotspot_tier": het_risk,
        "recommendation": (
            f"Elastic hotspot index Kt ≈ {Kt:.1f}× (porosity {porosity_percent:.0f}%): **stiffer load paths** "
            f"are expected near pore walls in a **linear elastic** solid. Treat this as **structural / material "
            f"failure intuition** (strut stress, crack initiation, uneven remodeling substrate)—**not** as the "
            f"local stiffness a nucleus “feels,” and **not** viscoelastic. Order-of-magnitude effective modulus "
            f"proxy ~{effective_stiffness:.1f} kPa (highly simplified)."
        ),
        "model_limits": (
            "No creep, relaxation, poroelasticity, swelling, hydrolysis, enzymatic erosion, or damage evolution. "
            "Mechanoreceptor biology is not inferred from Kt."
        ),
    }


# =============================================================================
# scikit-fem FEA — real finite element analysis
# =============================================================================

def _method_to_mesh_geometry(method):
    """Map biofab method to mesh geometry."""
    _planar_methods = {
        "organ_on_chip", "ooc",
        "sla", "dlp", "stereolithography", "two_photon", "2pp",
        "microfluidic",
    }
    if (method or "") in _planar_methods:
        return "channel"
    return "cube"


def material_properties_from_profile(profile) -> dict:
    """
    Extract elastic material properties from ConstructProfile.
    Young's modulus from stiffness_kpa, Poisson's ratio for hydrogels.
    """
    material_defaults = {
        "GelMA": 8.0, "GelMA 6%": 8.0, "GelMA 4%": 4.0,
        "Collagen I": 2.0, "Collagen": 2.0, "Fibrin": 1.5,
        "Matrigel": 0.4, "PDMS": 1000.0,
    }
    stiffness = getattr(profile, "stiffness_kpa", None)
    scaffold = getattr(profile, "scaffold_material", None)
    E = stiffness or material_defaults.get(scaffold or "", 5.0)

    return {
        "E": E * 1000,  # Pa (from kPa)
        "nu": 0.47,     # nearly incompressible hydrogel
    }


def build_scaffold_mesh(geometry="cube", resolution=8, dimensions=(4.0, 4.0, 4.0)):
    """
    Build tetrahedral mesh for scaffold geometry using scikit-fem.
    resolution=8 gives sub-second solve time for Streamlit.
    """
    from skfem import MeshTet1

    lx, ly, lz = dimensions

    if geometry == "channel":
        mesh = MeshTet1.init_tensor(
            np.linspace(0, lx * 2, resolution * 2),
            np.linspace(0, ly * 2, resolution * 2),
            np.linspace(0, lz * 0.3, max(3, resolution // 3)),
        )
    else:
        mesh = MeshTet1.init_tensor(
            np.linspace(0, lx, resolution),
            np.linspace(0, ly, resolution),
            np.linspace(0, lz, resolution),
        )
    return mesh


def solve_compression(profile, compressive_strain=0.10, resolution=8, dimensions=None) -> dict:
    """
    Solve linear elastic compression using scikit-fem.

    Bottom face fixed, top face displaced by compressive_strain * height.
    Returns displacement field, stress metrics, and interpretation.

    Parameters
    ----------
    dimensions : tuple[float, float, float] | None
        (lx, ly, lz) in mm.  When supplied (e.g. from the user's scaffold
        mesh bounding box) these override the default 4x4x4 cube so the
        FEA mesh matches the construct the user actually generated.
    """
    from skfem import MeshTet1, ElementTetP1, Basis, condense, solve as sksolve
    from skfem.assembly import BilinearForm
    from skfem.helpers import grad, transpose, eye

    props = material_properties_from_profile(profile)
    method = getattr(profile, "biofab_method", "bioprinting")
    geom = _method_to_mesh_geometry(method)

    mesh = build_scaffold_mesh(geometry=geom, resolution=resolution,
                               dimensions=dimensions or (4.0, 4.0, 4.0))

    # Scalar P1 element — solve z-displacement only (1D compression approx)
    e = ElementTetP1()
    basis = Basis(mesh, e)

    E, nu = props["E"], props["nu"]
    lam = E * nu / ((1 + nu) * (1 - 2 * nu))
    mu = E / (2 * (1 + nu))

    @BilinearForm
    def stiffness(u, v, w):
        return (lam + 2 * mu) * (grad(u)[2] * grad(v)[2]) + \
               mu * (grad(u)[0] * grad(v)[0] + grad(u)[1] * grad(v)[1])

    K = stiffness.assemble(basis)
    f = np.zeros(K.shape[0])

    # Boundary conditions
    z_coords = mesh.p[2]
    z_max = z_coords.max()
    z_min = z_coords.min()

    bottom_dofs = basis.get_dofs(lambda x: np.isclose(x[2], z_min))
    top_dofs = basis.get_dofs(lambda x: np.isclose(x[2], z_max))

    displacement_val = compressive_strain * (z_max - z_min)

    u = np.zeros(K.shape[0])
    u[top_dofs.nodal["u"]] = -displacement_val

    all_bc_dofs = np.concatenate([bottom_dofs.nodal["u"], top_dofs.nodal["u"]])
    u = sksolve(*condense(K, f, x=u, D=all_bc_dofs))

    # Post-process
    u_range = u.max() - u.min()
    max_disp_mm = abs(u.min()) if abs(u.min()) > abs(u.max()) else abs(u.max())

    # Stress estimates from strain
    strain_field = np.gradient(u[mesh.t[0]], z_coords[mesh.t[0]], axis=0) if len(mesh.t[0]) > 1 else np.array([compressive_strain])
    max_stress_pa = E * compressive_strain * 1.5  # corner concentration
    mean_stress_pa = E * compressive_strain
    scf = max_stress_pa / max(mean_stress_pa, 1e-10)
    high_stress_frac = max(0, scf - 1) / 3

    # Interpretation — coarse linear model; avoid cell-fate claims
    if scf > 3.0:
        interp = (
            f"High **elastic** stress heterogeneity (model SCF≈{scf:.1f}×): suggests **localized load carrying** "
            f"in this simplified mesh—not a prediction of fibrosis or apoptosis. For real matrices, check "
            f"relaxation, damage, and perfusion."
        )
    elif scf > 1.5:
        interp = (
            f"Moderate elastic heterogeneity (SCF≈{scf:.1f}×): **uneven macroscopic stress paths** in the solid "
            f"scaffold; may matter for **mechanical failure or remodeling patterns**, not as a direct map of "
            f"mechanoreceptor activation."
        )
    else:
        interp = (
            f"Relatively uniform elastic response (SCF≈{scf:.1f}×) in this toy compression model—still not "
            f"viscoelastic and not cell-resolved."
        )

    return {
        "mesh": mesh,
        "displacement_field": u,
        "max_displacement_mm": round(float(max_disp_mm), 4),
        "max_stress_kpa": round(max_stress_pa / 1000, 2),
        "mean_stress_kpa": round(mean_stress_pa / 1000, 2),
        "stress_concentration_factor": round(scf, 2),
        "high_stress_fraction": round(high_stress_frac, 3),
        "interpretation": interp,
        "E_kpa": round(E / 1000, 1),
        "compressive_strain": compressive_strain,
        "n_nodes": mesh.p.shape[1],
        "n_elements": mesh.t.shape[1],
    }


def render_fea_results(fea_result: dict) -> go.Figure:
    """
    Render FEA results as interactive 3D Plotly figure.
    Shows mesh colored by displacement magnitude.
    """
    mesh = fea_result["mesh"]
    u = fea_result["displacement_field"]

    # Displacement magnitude at each node
    disp_mag = np.abs(u)
    disp_norm = disp_mag / (disp_mag.max() + 1e-10)

    # Deformed z coordinates (exaggerate 20x for visibility)
    deformed_z = mesh.p[2] + u * 20

    # Get boundary facets for surface rendering
    bf = mesh.boundary_facets()
    faces = mesh.facets[:, bf].T

    fig = go.Figure()

    fig.add_trace(go.Mesh3d(
        x=mesh.p[0], y=mesh.p[1], z=deformed_z,
        i=faces[:, 0], j=faces[:, 1], k=faces[:, 2],
        intensity=disp_norm,
        colorscale=[
            [0.0, "#003333"],
            [0.3, "#00AA88"],
            [0.7, "#FFAA00"],
            [1.0, "#FF3333"],
        ],
        colorbar=dict(
            title="Displacement",
            tickfont=dict(color="#888888"),
        ),
        opacity=0.85,
        name="Deformed scaffold",
        hovertemplate="Displacement: %{intensity:.3f}<extra></extra>",
    ))

    scf = fea_result["stress_concentration_factor"]
    fig.add_annotation(
        text=f"Elastic SCF (toy): {scf:.1f}x | σ_max≈{fea_result['max_stress_kpa']:.1f} kPa",
        xref="paper", yref="paper",
        x=0.02, y=0.98,
        font=dict(color="#34d399", family="Inter, system-ui, sans-serif", size=12),
        bgcolor="rgba(0,0,0,0.5)",
        bordercolor="#333333",
        showarrow=False,
    )

    fig.update_layout(
        title=dict(
            text=(
                f"Linear elastic compression sketch — E≈{fea_result['E_kpa']:.0f} kPa, "
                f"{fea_result['compressive_strain']*100:.0f}% nominal strain "
                f"(disp. 20× exaggerated; not viscoelastic)"
            ),
            font=dict(color="#34d399", size=14, family="Inter, system-ui, sans-serif"),
        ),
        paper_bgcolor="#1a1a1f",
        scene=dict(
            bgcolor="#252529",
            xaxis=dict(backgroundcolor="#111111", gridcolor="#222222",
                       showbackground=True, tickfont=dict(color="#555555")),
            yaxis=dict(backgroundcolor="#111111", gridcolor="#222222",
                       showbackground=True, tickfont=dict(color="#555555")),
            zaxis=dict(backgroundcolor="#111111", gridcolor="#222222",
                       showbackground=True, tickfont=dict(color="#555555")),
        ),
        margin=dict(l=0, r=0, t=50, b=0),
        height=450,
    )

    return fig
