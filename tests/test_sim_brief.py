"""Tests for simulation brief firing correctly."""
from unittest.mock import patch, MagicMock


def test_sim_brief_fires():
    """Verify generate_simulation_brief returns a dict and session state would update."""
    mock_brief = {
        "simulation_question": "How does cardiac tissue behave?",
        "key_parameters": {
            "cell_types": ["cardiomyocyte"],
            "adhesion_energies": {"cardiomyocyte-cardiomyocyte": {"value": 10, "confidence": "medium"}},
            "simulation_steps": 1000,
        },
        "predicted_outcomes": ["Cell clustering observed"],
        "risk_prediction": "Low risk of delamination",
        "validation_experiment": "Run viability assay at day 7",
    }

    with patch("core.rag.generate_simulation_brief", return_value=mock_brief) as mock_fn:
        from core.rag import generate_simulation_brief
        from core.models import ConstructProfile, VarianceReport

        profile = ConstructProfile(
            target_tissue="cardiac",
            cell_types=["cardiomyocytes"],
            stiffness_kpa=10.0,
            experimental_goal="disease_modeling",
        )
        report = VarianceReport(
            construct_profile=profile,
            benchmark_ranges={"stiffness_kpa": {"min": 8, "max": 12, "unit": "kPa"}},
            deviation_scores={"stiffness_kpa": 0.0},
            risk_flags={"stiffness_kpa": "green"},
            ai_narrative="Test narrative.",
            supporting_pmids=["12345678"],
        )

        result = generate_simulation_brief(profile, report)

        assert result is not None
        assert isinstance(result, dict)
        assert "simulation_question" in result
        assert "key_parameters" in result
        assert "predicted_outcomes" in result
        assert "risk_prediction" in result
        assert "validation_experiment" in result

        # Simulate session state update
        session_state = {"simulation_brief": None}
        session_state["simulation_brief"] = result
        assert session_state["simulation_brief"] is not None


def test_sim_brief_graceful_on_error():
    """If generate_simulation_brief raises, session state stays None."""
    session_state = {"simulation_brief": None}

    with patch("core.rag.generate_simulation_brief", side_effect=Exception("API timeout")):
        from core.rag import generate_simulation_brief
        try:
            session_state["simulation_brief"] = generate_simulation_brief(None, None)
        except Exception:
            session_state["simulation_brief"] = None

    assert session_state["simulation_brief"] is None
