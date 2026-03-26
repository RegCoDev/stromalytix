"""Tests for Streamlit Cloud deployment readiness."""
from pathlib import Path


def test_requirements_txt_exists():
    assert Path("requirements.txt").exists()


def test_streamlit_config_exists():
    assert Path(".streamlit/config.toml").exists()


def test_readme_exists():
    p = Path("README.md")
    assert p.exists()
    assert p.read_text().strip() != ""


def test_gitignore_has_secrets():
    text = Path(".gitignore").read_text()
    assert "secrets.toml" in text


def test_rag_importable():
    from core.rag import load_vectorstore, retrieve_benchmarks
    assert callable(load_vectorstore)
    assert callable(retrieve_benchmarks)


def test_fem_solver_importable():
    from core.fem_solver import predict_scaffold_deformation, predict_stress_distribution
    assert callable(predict_scaffold_deformation)
    assert callable(predict_stress_distribution)
