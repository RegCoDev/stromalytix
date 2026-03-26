"""Tests for data connector architecture."""
from datetime import datetime


def test_process_event_dataclass_valid():
    """Create a ProcessEvent with no errors."""
    from connectors.base import ProcessEvent, DataSourceType
    event = ProcessEvent(
        event_id="e1",
        case_id="batch_001",
        activity="cell_seeding",
        timestamp=datetime(2026, 3, 1, 10, 0),
        source_type=DataSourceType.ELN,
        source_name="benchling",
        parameter_values={"stiffness_kpa": 10.0},
    )
    assert event.case_id == "batch_001"
    assert event.source_type == DataSourceType.ELN


def test_base_connector_importable():
    from connectors.base import BaseConnector
    assert BaseConnector is not None


def test_eln_csv_connector_importable():
    from connectors.eln_csv import ELNCSVConnector
    conn = ELNCSVConnector()
    assert conn.source_name == "eln_csv"


def test_crm_csv_connector_importable():
    from connectors.crm_csv import CRMCSVConnector
    conn = CRMCSVConnector()
    assert conn.source_name == "crm_csv"


def test_instrument_csv_connector_importable():
    from connectors.instrument_csv import InstrumentCSVConnector
    conn = InstrumentCSVConnector()
    assert conn.source_name == "instrument_csv"


def test_to_event_log_produces_pm4py_columns():
    """Convert 3 mock ProcessEvents to PM4Py DataFrame."""
    from connectors.base import BaseConnector, ProcessEvent, DataSourceType

    events = [
        ProcessEvent(
            event_id=f"e{i}",
            case_id="batch_001",
            activity=act,
            timestamp=datetime(2026, 3, 1, 10 + i, 0),
            source_type=DataSourceType.ELN,
            source_name="test",
        )
        for i, act in enumerate(["cell_seeding", "incubation", "measurement"])
    ]

    connector = BaseConnector()
    df = connector.to_event_log(events)
    assert "case:concept:name" in df.columns
    assert "concept:name" in df.columns
    assert "time:timestamp" in df.columns
    assert len(df) == 3
