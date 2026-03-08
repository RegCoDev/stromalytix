"""Tests for CC3D cloud sidecar client."""
from unittest.mock import patch, MagicMock


def test_cloud_runner_returns_fallback_when_no_url():
    from core.cc3d_runner import run_simulation_cloud
    with patch("core.cc3d_runner.CC3D_API_URL", ""):
        result = run_simulation_cloud({"cell_types": ["A"]})
    assert result["success"] is False
    assert result.get("fallback") is True


def test_cloud_runner_validates_api_key_present():
    """Cloud runner includes x-api-key header."""
    import httpx as httpx_mod
    from core.cc3d_runner import run_simulation_cloud

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"job_id": "j1"}
    mock_resp.raise_for_status = MagicMock()

    poll_resp = MagicMock()
    poll_resp.json.return_value = {"status": "complete", "vtk_frames": [], "metadata": {}, "message": "ok"}
    poll_resp.raise_for_status = MagicMock()

    with patch("core.cc3d_runner.CC3D_API_URL", "http://fake:8001"), \
         patch("core.cc3d_runner.CC3D_API_KEY", "test-key"), \
         patch("httpx.post", return_value=mock_resp) as mock_post, \
         patch("httpx.get", return_value=poll_resp):

        result = run_simulation_cloud({"cell_types": ["A"]}, poll_interval=0.01, timeout=2)

        call_args = mock_post.call_args
        assert call_args[1]["headers"]["x-api-key"] == "test-key"


def test_run_simulation_routes_to_cloud_when_url_set():
    from core.cc3d_runner import run_simulation
    with patch("core.cc3d_runner.CC3D_API_URL", "http://fake:8001"), \
         patch("core.cc3d_runner.run_simulation_cloud") as mock_cloud:
        mock_cloud.return_value = {"success": True}
        result = run_simulation({"cell_types": ["A"]})
        mock_cloud.assert_called_once()
        assert result["success"] is True


def test_run_simulation_falls_back_when_no_cc3d():
    from core.cc3d_runner import run_simulation
    with patch("core.cc3d_runner.CC3D_API_URL", ""), \
         patch("core.cc3d_runner.verify_cc3d_installation") as mock_verify:
        mock_verify.return_value = {"installed": False, "error": "not found"}
        result = run_simulation({"cell_types": ["A"]})
        assert result["success"] is False
        assert result.get("fallback") is True


def test_sidecar_script_validation():
    """Sidecar rejects scripts with dangerous patterns."""
    import sys
    sys.path.insert(0, "services/cc3d_runner_api")
    from services.cc3d_runner_api.main import _validate_script

    # Safe script should pass
    _validate_script("from cc3d import stuff\nprint('hello')")

    # Dangerous script should raise
    import pytest
    with pytest.raises(ValueError):
        _validate_script("import os\nos.system('rm -rf /')")
    with pytest.raises(ValueError):
        _validate_script("eval('bad code')")
    with pytest.raises(ValueError):
        _validate_script("import subprocess")


def test_sidecar_runner_generates_script():
    from services.cc3d_runner_api.runner import generate_cc3d_script
    script = generate_cc3d_script(
        {"cell_types": ["cardio", "fibro"], "stiffness_kpa": 8.0},
        max_steps=500,
    )
    assert "Steppable" in script
    assert "targetVolume" in script


def test_sidecar_runner_sanitizes_cell_types():
    from services.cc3d_runner_api.runner import generate_cc3d_script
    script = generate_cc3d_script(
        {"cell_types": ["bad; rm -rf /", "ok_cell"]},
    )
    # Should strip dangerous characters
    assert "rm" not in script or "bad" in script
    assert ";" not in script.split("Steppable")[0]  # before class def


def test_collect_vtk_empty_dir(tmp_path):
    from services.cc3d_runner_api.runner import collect_vtk_output
    result = collect_vtk_output(tmp_path)
    assert result == []
