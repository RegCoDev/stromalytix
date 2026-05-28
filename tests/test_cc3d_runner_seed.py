"""Reproducibility tests for the CC3D sidecar generator (C2 fix).

Before this fix the generated Potts XML carried no <RandomSeed>, so CC3D used a
clock seed and identical briefs produced different runs — fatal for the
reproducibility pillar (charter: "same inputs -> bounded repeatable outputs").
These tests pin the seed into the XML and assert determinism. Pattern:
[[agent-complexity-ratchet]] — this module had no seed test, which is how C2
survived.
"""

import sys
from pathlib import Path

_SVC = Path(__file__).parent.parent / "services" / "cc3d_runner_api"
sys.path.insert(0, str(_SVC))

import runner  # noqa: E402

_BRIEF = {
    "key_parameters": {
        "cell_types": ["cardiomyocyte", "fibroblast"],
        "volume_constraints": {"target_volume": 100, "lambda_volume": 2},
    }
}


def test_potts_xml_contains_random_seed():
    _, project_xml, _ = runner.generate_cc3d_project(_BRIEF)
    assert "<RandomSeed>" in project_xml, "Potts XML must declare a RandomSeed"
    assert f"<RandomSeed>{runner.DEFAULT_RANDOM_SEED}</RandomSeed>" in project_xml


def test_runs_are_deterministic_for_identical_briefs():
    a_py, a_xml, _ = runner.generate_cc3d_project(_BRIEF)
    b_py, b_xml, _ = runner.generate_cc3d_project(_BRIEF)
    assert a_xml == b_xml, "identical briefs must produce byte-identical XML"
    assert a_py == b_py, "identical briefs must produce byte-identical steppable"


def test_brief_can_override_seed():
    brief = {"key_parameters": {**_BRIEF["key_parameters"], "random_seed": 777}}
    _, project_xml, _ = runner.generate_cc3d_project(brief)
    assert "<RandomSeed>777</RandomSeed>" in project_xml


def test_resolve_random_seed_precedence():
    assert runner.resolve_random_seed({}) == runner.DEFAULT_RANDOM_SEED
    assert runner.resolve_random_seed({"random_seed": 5}) == 5
    # key_parameters takes precedence over top level
    assert runner.resolve_random_seed({"key_parameters": {"random_seed": 9}, "random_seed": 5}) == 9
    # negative coerced to non-negative; bad values fall back to default
    assert runner.resolve_random_seed({"random_seed": -3}) == 3
    assert runner.resolve_random_seed({"random_seed": "nope"}) == runner.DEFAULT_RANDOM_SEED


def test_generate_project_xml_honors_explicit_seed():
    xml = runner._generate_project_xml(
        dims=(80, 80, 40),
        cell_types=["cardiomyocyte"],
        adhesion_matrix={"Medium_cardiomyocyte": 16},
        mcs_steps=1000,
        pbc_axes=[],
        has_o2=False,
        o2_diffusion=2.0e-5,
        o2_decay=0.0,
        o2_boundary=0.2,
        has_ecm_field=False,
        seed=42,
    )
    assert "<RandomSeed>42</RandomSeed>" in xml
