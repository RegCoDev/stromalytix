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
