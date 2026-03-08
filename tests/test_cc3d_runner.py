"""Tests for CC3D live execution runner."""


def test_cc3d_runner_importable():
    from core.cc3d_runner import verify_cc3d_installation, generate_cc3d_script, run_cc3d_simulation
    assert callable(verify_cc3d_installation)
    assert callable(generate_cc3d_script)
    assert callable(run_cc3d_simulation)


def test_verify_cc3d_returns_required_keys():
    from core.cc3d_runner import verify_cc3d_installation
    result = verify_cc3d_installation()
    assert "installed" in result
    assert "python_path" in result
    assert "version" in result
    assert "error" in result


def test_generate_script_handles_confidence_tagged_adhesion():
    """Confidence-tagged adhesion: {"value": 10, "confidence": "medium"} → script contains "10"."""
    from core.cc3d_runner import generate_cc3d_script
    brief = {
        "key_parameters": {
            "cell_types": ["cardiomyocyte", "fibroblast"],
            "adhesion_energies": {
                "cardiomyocyte-cardiomyocyte": {"value": 10, "confidence": "medium", "source_pmids": []},
                "cardiomyocyte-fibroblast": {"value": 15, "confidence": "low", "source_pmids": []},
            },
            "volume_constraints": {"target_volume": 100, "lambda_volume": 2},
            "simulation_steps": 1000,
        }
    }
    script = generate_cc3d_script(brief)
    assert "10" in script
    assert "15" in script
    assert "cardiomyocyte" in script


def test_run_cc3d_returns_required_keys():
    from core.cc3d_runner import run_cc3d_simulation
    brief = {
        "key_parameters": {
            "cell_types": ["cell_A"],
            "adhesion_energies": {"cell_A-cell_A": 10},
            "simulation_steps": 100,
        }
    }
    result = run_cc3d_simulation(brief, timeout=30)
    assert "success" in result
    assert "ran" in result
    assert "output" in result
    assert "error" in result
    assert "mcs_completed" in result
    assert "duration_seconds" in result
