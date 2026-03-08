"""Tests for biological process mining engine."""
from datetime import datetime, timedelta

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


def test_process_miner_importable():
    from core.process_mining import BiologicalProcessMiner
    miner = BiologicalProcessMiner()
    assert miner is not None


def test_add_event_log_accepts_list():
    from core.process_mining import BiologicalProcessMiner
    miner = BiologicalProcessMiner()
    events = [
        _make_event("c1", "seeding", 0),
        _make_event("c1", "incubation", 1),
        _make_event("c1", "measurement", 2),
    ]
    miner.add_event_log(events, "test_log")
    assert "test_log" in miner.event_logs
    assert len(miner.event_logs["test_log"]) == 3


def test_get_kpis_returns_dict_with_required_keys():
    from core.process_mining import BiologicalProcessMiner
    miner = BiologicalProcessMiner()
    events = [
        _make_event("c1", "seeding", 0),
        _make_event("c1", "measurement", 2),
        _make_event("c2", "seeding", 3),
        _make_event("c2", "measurement", 5),
    ]
    miner.add_event_log(events, "kpi_log")
    kpis = miner.get_kpis("kpi_log")
    assert isinstance(kpis, dict)
    assert "batch_success_rate" in kpis
    assert "mean_time_to_result" in kpis
    assert "protocol_conformance_rate" in kpis


def test_find_critical_control_points_returns_list():
    from core.process_mining import BiologicalProcessMiner
    import pandas as pd
    miner = BiologicalProcessMiner()

    # Create DataFrame with outcome column directly
    df = pd.DataFrame([
        {"case:concept:name": "c1", "concept:name": "seeding", "time:timestamp": datetime(2026,3,1,10), "viability": 90},
        {"case:concept:name": "c1", "concept:name": "measurement", "time:timestamp": datetime(2026,3,1,12), "viability": 85},
        {"case:concept:name": "c2", "concept:name": "seeding", "time:timestamp": datetime(2026,3,1,13), "viability": 50},
        {"case:concept:name": "c2", "concept:name": "measurement", "time:timestamp": datetime(2026,3,1,15), "viability": 88},
    ])
    import pm4py
    df = pm4py.format_dataframe(df, case_id="case:concept:name",
                                 activity_key="concept:name",
                                 timestamp_key="time:timestamp")
    miner.event_logs["ccp_log"] = df
    ccps = miner.find_critical_control_points("ccp_log", "viability")
    assert isinstance(ccps, list)


def test_detect_batch_effects_with_two_batches():
    from core.process_mining import BiologicalProcessMiner
    miner = BiologicalProcessMiner()

    events = [
        _make_event("c1", "measurement", 0, batch_id="A", outcomes={"viability": 85}),
        _make_event("c2", "measurement", 1, batch_id="A", outcomes={"viability": 90}),
        _make_event("c3", "measurement", 2, batch_id="A", outcomes={"viability": 88}),
        _make_event("c4", "measurement", 3, batch_id="B", outcomes={"viability": 55}),
        _make_event("c5", "measurement", 4, batch_id="B", outcomes={"viability": 60}),
        _make_event("c6", "measurement", 5, batch_id="B", outcomes={"viability": 58}),
    ]
    result = miner.detect_batch_effects(events, "batch_id", "viability")
    assert isinstance(result, dict)
    assert "A" in result
    assert "B" in result
    # Batch B should be flagged (lower mean)
    assert result["B"]["flagged"] is True
    assert result["A"]["flagged"] is False


def test_correlate_business_outcomes_returns_dict():
    from core.process_mining import BiologicalProcessMiner
    miner = BiologicalProcessMiner()

    process_events = [
        _make_event("c1", "seeding", params={"stiffness_kpa": 10}, customer_id="cust1"),
        _make_event("c2", "seeding", params={"stiffness_kpa": 5}, customer_id="cust2"),
    ]
    crm_events = [
        _make_event("d1", "deal_closed_won", customer_id="cust1"),
        _make_event("d2", "deal_closed_lost", customer_id="cust2"),
    ]
    result = miner.correlate_business_outcomes(process_events, crm_events)
    assert isinstance(result, dict)
