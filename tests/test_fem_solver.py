"""Tests for scikit-fem scaffold mechanics solver."""


def test_fem_solver_importable():
    from core.fem_solver import predict_scaffold_deformation, predict_stress_distribution
    assert callable(predict_scaffold_deformation)
    assert callable(predict_stress_distribution)


def test_predict_deformation_returns_required_keys():
    from core.fem_solver import predict_scaffold_deformation
    result = predict_scaffold_deformation(stiffness_kpa=4.0, cell_density_per_ml=2e6)
    assert "max_deformation_um" in result
    assert "strain_percent" in result
    assert "stress_kpa" in result
    assert "failure_risk" in result
    assert "recommendation" in result
    assert "n_cells_estimated" in result
    assert "collective_force_nN" in result


def test_high_stiffness_lower_deformation():
    from core.fem_solver import predict_scaffold_deformation
    soft = predict_scaffold_deformation(stiffness_kpa=1.0, cell_density_per_ml=1e6)
    stiff = predict_scaffold_deformation(stiffness_kpa=10.0, cell_density_per_ml=1e6)
    assert soft["strain_percent"] > stiff["strain_percent"]


def test_failure_risk_high_for_soft_scaffold():
    from core.fem_solver import predict_scaffold_deformation
    result = predict_scaffold_deformation(stiffness_kpa=0.5, cell_density_per_ml=10e6)
    assert result["failure_risk"] == "high"


def test_stress_distribution_returns_keys():
    from core.fem_solver import predict_stress_distribution
    result = predict_stress_distribution(stiffness_kpa=10.0, porosity_percent=80.0)
    assert "stress_concentration_factor" in result
    assert "effective_local_stiffness_kpa" in result
    assert "heterogeneity_risk" in result
    assert "recommendation" in result


# --- scikit-fem FEA tests ---

def test_build_scaffold_mesh_returns_tet_mesh():
    from core.fem_solver import build_scaffold_mesh
    mesh = build_scaffold_mesh(geometry="cube", resolution=4)
    assert mesh.p.shape[0] == 3  # 3D coordinates
    assert mesh.t.shape[0] == 4  # tetrahedra have 4 vertices
    assert mesh.p.shape[1] > 0   # has nodes
    assert mesh.t.shape[1] > 0   # has elements


def test_material_properties_from_gelma():
    from types import SimpleNamespace
    from core.fem_solver import material_properties_from_profile
    profile = SimpleNamespace(stiffness_kpa=8.0, scaffold_material="GelMA")
    props = material_properties_from_profile(profile)
    assert props["E"] == 8000.0  # 8 kPa -> 8000 Pa
    assert 0.4 < props["nu"] < 0.5


def test_solve_compression_returns_required_keys():
    from types import SimpleNamespace
    from core.fem_solver import solve_compression
    profile = SimpleNamespace(stiffness_kpa=5.0, scaffold_material="GelMA",
                              biofab_method="bioprinting")
    result = solve_compression(profile, compressive_strain=0.10, resolution=4)
    assert "mesh" in result
    assert "displacement_field" in result
    assert "max_displacement_mm" in result
    assert "max_stress_kpa" in result
    assert "stress_concentration_factor" in result
    assert "interpretation" in result
    assert "n_nodes" in result
    assert "n_elements" in result


def test_solve_compression_stiffer_lower_displacement():
    from types import SimpleNamespace
    from core.fem_solver import solve_compression
    soft = solve_compression(
        SimpleNamespace(stiffness_kpa=1.0, scaffold_material=None, biofab_method=None),
        compressive_strain=0.10, resolution=4
    )
    stiff = solve_compression(
        SimpleNamespace(stiffness_kpa=20.0, scaffold_material=None, biofab_method=None),
        compressive_strain=0.10, resolution=4
    )
    # Same strain applied -> same relative displacement
    # But absolute stress should differ
    assert stiff["max_stress_kpa"] > soft["max_stress_kpa"]


def test_render_fea_results_returns_figure():
    from types import SimpleNamespace
    from core.fem_solver import solve_compression, render_fea_results
    import plotly.graph_objects as go
    profile = SimpleNamespace(stiffness_kpa=5.0, scaffold_material=None,
                              biofab_method=None)
    fea = solve_compression(profile, resolution=4)
    fig = render_fea_results(fea)
    assert isinstance(fig, go.Figure)
    assert fig.layout.paper_bgcolor == "#0a0a0a"


def test_fea_runs_under_5_seconds():
    import time
    from types import SimpleNamespace
    from core.fem_solver import solve_compression
    profile = SimpleNamespace(stiffness_kpa=5.0, scaffold_material=None,
                              biofab_method=None)
    start = time.time()
    solve_compression(profile, resolution=8)
    elapsed = time.time() - start
    assert elapsed < 5.0, f"FEA took {elapsed:.1f}s — too slow"
