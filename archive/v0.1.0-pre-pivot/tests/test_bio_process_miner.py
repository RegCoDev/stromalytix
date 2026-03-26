"""Tests for proprietary biological process mining engine."""
import subprocess
from datetime import datetime, timedelta

import pandas as pd

from connectors.base import ProcessEvent, DataSourceType


def _make_event(case_id, activity, hour_offset=0, batch_id=None,
                params=None, outcomes=None, customer_id=None):
    return ProcessEvent(
        event_id=f"e_{case_id}_{activity}",
        case_id=case_id,
        activity=activity,
        timestamp=datetime(2026, 3, 1, 10, 0) + timedelta(hours=hour_offset),
        source_type=DataSourceType.ELN,
        source_name="test",
        batch_id=batch_id,
        parameter_values=params,
        outcome_values=outcomes,
        customer_id=customer_id,
    )


def _make_df(rows):
    df = pd.DataFrame(rows)
    df["time:timestamp"] = pd.to_datetime(df["time:timestamp"])
    return df


# --- AlgorithmRouter tests ---

def test_algorithm_router_selects_dfg_for_small_log():
    from core.bio_process_miner import AlgorithmRouter
    router = AlgorithmRouter()
    df = _make_df([
        {"case:concept:name": f"c{i}", "concept:name": "step_a",
         "time:timestamp": datetime(2026, 3, 1, 10 + i)}
        for i in range(5)
    ])
    char = router.characterize(df, "case:concept:name", "concept:name", "time:timestamp")
    result = router.select_algorithm(char)
    assert result["algorithm"] == "dfg_only"


def test_algorithm_router_forces_inductive_on_loops():
    from core.bio_process_miner import AlgorithmRouter
    router = AlgorithmRouter()
    rows = []
    for i in range(40):
        rows.append({"case:concept:name": f"c{i}", "concept:name": "step_a",
                      "time:timestamp": datetime(2026, 3, 1, 10)})
        rows.append({"case:concept:name": f"c{i}", "concept:name": "step_b",
                      "time:timestamp": datetime(2026, 3, 1, 11)})
        rows.append({"case:concept:name": f"c{i}", "concept:name": "step_a",
                      "time:timestamp": datetime(2026, 3, 1, 12)})  # loop
    df = _make_df(rows)
    char = router.characterize(df, "case:concept:name", "concept:name", "time:timestamp")
    assert char["has_loops"] is True
    result = router.select_algorithm(char)
    assert result["algorithm"] == "inductive"


def test_algorithm_router_warns_on_high_variant_ratio():
    from core.bio_process_miner import AlgorithmRouter
    router = AlgorithmRouter()
    # Each case has a unique trace
    rows = []
    for i in range(40):
        rows.append({"case:concept:name": f"c{i}", "concept:name": f"step_{i}",
                      "time:timestamp": datetime(2026, 3, 1, 10) + timedelta(hours=i)})
    df = _make_df(rows)
    char = router.characterize(df, "case:concept:name", "concept:name", "time:timestamp")
    assert char["variant_ratio"] > 0.8
    assert any("variant ratio" in w.lower() for w in char["warnings"])


def test_algorithm_router_detects_date_only_timestamps():
    from core.bio_process_miner import AlgorithmRouter
    router = AlgorithmRouter()
    rows = []
    for i in range(15):
        rows.append({"case:concept:name": f"c{i}", "concept:name": "step_a",
                      "time:timestamp": datetime(2026, 3, 1 + i)})
    df = _make_df(rows)
    char = router.characterize(df, "case:concept:name", "concept:name", "time:timestamp")
    assert char["timestamp_precision"] == "date_only"
    assert any("date-only" in w.lower() for w in char["warnings"])


def test_heterogeneous_methods_triggers_split_warning():
    from core.bio_process_miner import AlgorithmRouter
    router = AlgorithmRouter()
    rows = []
    for i in range(15):
        rows.append({"case:concept:name": f"c{i}", "concept:name": "bioprinting",
                      "time:timestamp": datetime(2026, 3, 1, 10) + timedelta(hours=i)})
        rows.append({"case:concept:name": f"c{i}", "concept:name": "ooc",
                      "time:timestamp": datetime(2026, 3, 1, 11) + timedelta(hours=i)})
    df = _make_df(rows)
    char = router.characterize(df, "case:concept:name", "concept:name", "time:timestamp")
    assert char["heterogeneous_methods"] is True
    assert any("mixed" in w.lower() for w in char["warnings"])


# --- InductiveMiner tests ---

def test_inductive_miner_soundness():
    from core.bio_process_miner import InductiveMiner
    miner = InductiveMiner()
    rows = []
    for i in range(20):
        rows.append({"case:concept:name": f"c{i}", "concept:name": "step_a",
                      "time:timestamp": datetime(2026, 3, 1, 10)})
        rows.append({"case:concept:name": f"c{i}", "concept:name": "step_b",
                      "time:timestamp": datetime(2026, 3, 1, 11)})
    df = _make_df(rows)
    result = miner.discover(df, "case:concept:name", "concept:name", "time:timestamp")
    assert result["soundness_verified"] is True


def test_inductive_miner_handles_loops():
    from core.bio_process_miner import InductiveMiner
    miner = InductiveMiner()
    rows = []
    for i in range(20):
        rows.append({"case:concept:name": f"c{i}", "concept:name": "prep",
                      "time:timestamp": datetime(2026, 3, 1, 10)})
        rows.append({"case:concept:name": f"c{i}", "concept:name": "measure",
                      "time:timestamp": datetime(2026, 3, 1, 11)})
        rows.append({"case:concept:name": f"c{i}", "concept:name": "prep",
                      "time:timestamp": datetime(2026, 3, 1, 12)})
    df = _make_df(rows)
    result = miner.discover(df, "case:concept:name", "concept:name", "time:timestamp")
    assert result["soundness_verified"] is True
    assert "prep" in result["activities"]


def test_inductive_miner_handles_xor():
    from core.bio_process_miner import InductiveMiner
    miner = InductiveMiner()
    rows = []
    # Half cases do path A, half do path B — never both
    for i in range(10):
        rows.append({"case:concept:name": f"c{i}", "concept:name": "path_a",
                      "time:timestamp": datetime(2026, 3, 1, 10) + timedelta(hours=i)})
    for i in range(10, 20):
        rows.append({"case:concept:name": f"c{i}", "concept:name": "path_b",
                      "time:timestamp": datetime(2026, 3, 1, 10) + timedelta(hours=i)})
    df = _make_df(rows)
    result = miner.discover(df, "case:concept:name", "concept:name", "time:timestamp")
    assert result["soundness_verified"] is True


# --- HeuristicsMiner tests ---

def test_heuristics_miner_returns_compatible_structure():
    from core.bio_process_miner import HeuristicsMiner
    miner = HeuristicsMiner()
    rows = []
    for i in range(20):
        rows.append({"case:concept:name": f"c{i}", "concept:name": "step_a",
                      "time:timestamp": datetime(2026, 3, 1, 10)})
        rows.append({"case:concept:name": f"c{i}", "concept:name": "step_b",
                      "time:timestamp": datetime(2026, 3, 1, 11)})
    df = _make_df(rows)
    result = miner.discover(df, "case:concept:name", "concept:name", "time:timestamp")
    assert "activities" in result
    assert "variants" in result
    assert "most_common_path" in result
    assert result["soundness_verified"] is False


# --- ConformanceChecker tests ---

def test_conformance_perfect_trace():
    from core.bio_process_miner import ConformanceChecker
    checker = ConformanceChecker()
    result = checker.check_case_token_replay(
        ["a", "b", "c"], ["a", "b", "c"]
    )
    assert result["fitness"] == 1.0
    assert result["conformant"] is True


def test_conformance_missing_step():
    from core.bio_process_miner import ConformanceChecker
    checker = ConformanceChecker()
    result = checker.check_case_token_replay(
        ["a", "c"], ["a", "b", "c"]
    )
    assert result["fitness"] < 1.0
    assert "b" in result["missing_activities"]


def test_conformance_extra_step():
    from core.bio_process_miner import ConformanceChecker
    checker = ConformanceChecker()
    result = checker.check_case_token_replay(
        ["a", "b", "c", "d"], ["a", "b", "c"]
    )
    assert result["fitness"] < 1.0
    assert "d" in result["extra_activities"]


# --- BiologicalExtensions tests ---

def test_bio_ext_correlates_steps_with_outcomes():
    from core.bio_process_miner import BiologicalExtensions
    bio = BiologicalExtensions()
    events = [
        _make_event("c1", "seeding", 0, outcomes={"viability": 90}),
        _make_event("c2", "seeding", 1, outcomes={"viability": 50}),
        _make_event("c3", "seeding", 2, outcomes={"viability": 85}),
        _make_event("c1", "measurement", 3, outcomes={"viability": 88}),
        _make_event("c2", "measurement", 4, outcomes={"viability": 55}),
        _make_event("c3", "measurement", 5, outcomes={"viability": 90}),
    ]
    result = bio.correlate_steps_with_outcomes(events, "viability")
    assert isinstance(result, list)
    assert len(result) > 0
    assert "activity" in result[0]
    assert "outcome_correlation" in result[0]
    assert "ccp_score" in result[0]


def test_bio_ext_batch_flags_low_performing_lot():
    from core.bio_process_miner import BiologicalExtensions
    bio = BiologicalExtensions()
    events = [
        _make_event("c1", "m", 0, batch_id="A", outcomes={"viability": 85}),
        _make_event("c2", "m", 1, batch_id="A", outcomes={"viability": 90}),
        _make_event("c3", "m", 2, batch_id="A", outcomes={"viability": 88}),
        _make_event("c4", "m", 3, batch_id="B", outcomes={"viability": 55}),
        _make_event("c5", "m", 4, batch_id="B", outcomes={"viability": 60}),
        _make_event("c6", "m", 5, batch_id="B", outcomes={"viability": 58}),
    ]
    result = bio.separate_batch_effects(events, "batch_id", "viability")
    assert result["B"]["flagged"] is True
    assert result["A"]["flagged"] is False


# --- No PM4Py test ---

def test_no_pm4py_import():
    """Verify zero pm4py imports in production code."""
    import os
    prod_dirs = ["core", "connectors", "scripts"]
    violations = []
    for d in prod_dirs:
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if f.endswith(".py"):
                    path = os.path.join(root, f)
                    with open(path, encoding="utf-8") as fh:
                        for lineno, line in enumerate(fh, 1):
                            if "import pm4py" in line or "from pm4py" in line:
                                violations.append(f"{path}:{lineno}: {line.strip()}")
    assert violations == [], f"pm4py still imported:\n" + "\n".join(violations)


# --- Full pipeline test ---

def test_full_analyze_pipeline_returns_required_keys():
    from core.bio_process_miner import BiologicalProcessMiner
    miner = BiologicalProcessMiner()
    events = [
        _make_event("c1", "seeding", 0, batch_id="A", outcomes={"viability": 85}),
        _make_event("c1", "incubation", 1, batch_id="A", outcomes={"viability": 87}),
        _make_event("c1", "measurement", 2, batch_id="A", outcomes={"viability": 90}),
        _make_event("c2", "seeding", 3, batch_id="A", outcomes={"viability": 80}),
        _make_event("c2", "incubation", 4, batch_id="A", outcomes={"viability": 82}),
        _make_event("c2", "measurement", 5, batch_id="A", outcomes={"viability": 85}),
    ] * 5  # 30 events = 10 cases
    miner.add_event_log(events, "test")
    result = miner.analyze("test", outcome_column="viability",
                           reference_protocol=["seeding", "incubation", "measurement"])
    assert "characterization" in result
    assert "routing" in result
    assert "model" in result
    assert "conformance" in result
