"""Tests for synthetic event log generation."""
from datetime import datetime
from unittest.mock import patch

from connectors.base import ProcessEvent, DataSourceType
from core.synthetic_log_generator import (
    _compute_event_statistics,
    _parse_and_validate_events,
    _matches_condition,
    augment_sparse_log,
)


def _make_events(n=5):
    """Create n dummy events."""
    events = []
    for i in range(n):
        events.append(ProcessEvent(
            event_id=f"evt_{i:03d}",
            case_id=f"EXP-{i:03d}",
            activity="cell_seeding",
            timestamp=datetime(2026, 1, 1 + i).isoformat(),
            source_type=DataSourceType.ELN,
            source_name="test",
            outcome_values={"viability": 85.0 + i},
            operator="operator_A",
            batch_id="LOT-2024-A1",
            biofab_method="bioprinting",
        ))
    return events


def test_compute_statistics_returns_required_keys():
    events = _make_events(5)
    stats = _compute_event_statistics(events)
    assert "n_events" in stats
    assert "n_cases" in stats
    assert "outcome_mean" in stats
    assert "outcome_sd" in stats
    assert "lots" in stats
    assert stats["n_cases"] == 5


def test_compute_statistics_empty_events():
    stats = _compute_event_statistics([])
    assert stats["n_events"] == 0
    assert stats["outcome_mean"] is None


def test_parse_validates_viability_range():
    raw = '[{"case_id":"SYN-001","activity":"assay","timestamp":"2026-01-01","viability_percent":150}]'
    events = _parse_and_validate_events(raw)
    assert len(events) == 1
    assert events[0].outcome_values["viability"] == 99  # clamped to max


def test_parse_validates_viability_minimum():
    raw = '[{"case_id":"SYN-001","activity":"assay","timestamp":"2026-01-01","viability_percent":5}]'
    events = _parse_and_validate_events(raw)
    assert len(events) == 1
    assert events[0].outcome_values["viability"] == 20  # clamped to min


def test_parse_handles_malformed_json_gracefully():
    events = _parse_and_validate_events("not json at all {{{")
    assert events == []


def test_parse_handles_markdown_fences():
    raw = '```json\n[{"case_id":"SYN-001","activity":"test","timestamp":"2026-01-01","outcome_value":80}]\n```'
    events = _parse_and_validate_events(raw)
    assert len(events) == 1


def test_matches_condition_lot_b2():
    event_b2 = ProcessEvent(
        event_id="e1", case_id="E1", activity="x", timestamp="2026-01-01",
        source_type=DataSourceType.ELN, source_name="test",
        batch_id="LOT-2024-B2",
    )
    event_a1 = ProcessEvent(
        event_id="e2", case_id="E2", activity="x", timestamp="2026-01-01",
        source_type=DataSourceType.ELN, source_name="test",
        batch_id="LOT-2024-A1",
    )
    assert _matches_condition(event_b2, "without_lot_B2") is True
    assert _matches_condition(event_a1, "without_lot_B2") is False


def test_synthetic_events_tagged_correctly():
    raw = '[{"case_id":"SYN-001","activity":"test","timestamp":"2026-01-01","outcome_value":85}]'
    events = _parse_and_validate_events(raw)
    assert len(events) == 1
    assert events[0].source_name == "synthetic_llm"


def test_augment_returns_same_when_enough_cases():
    events = _make_events(30)
    result = augment_sparse_log(events, target_n_cases=30)
    assert len(result) == len(events)


def test_augment_needs_api_for_sparse_log():
    """Augmentation with too few cases calls the API."""
    events = _make_events(3)

    mock_response = '[{"case_id":"SYN-004","activity":"test","timestamp":"2026-01-10","outcome_value":82}]'
    with patch("core.synthetic_log_generator._call_claude_api", return_value=mock_response):
        result = augment_sparse_log(events, target_n_cases=5)
        assert len(result) > len(events)
        synthetic = [e for e in result if e.source_name == "synthetic_llm"]
        assert len(synthetic) > 0
