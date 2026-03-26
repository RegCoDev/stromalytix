"""
All data sources produce ProcessEvent objects.
ProcessEvents feed the process mining engine and process graph.
This is the normalization layer that makes cross-source analysis
possible — the same object whether it came from Benchling,
HubSpot, or a bioprinter export.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class DataSourceType(Enum):
    CRM = "crm"
    ERP = "erp"
    ELN = "eln"
    LIMS = "lims"
    INSTRUMENT = "instrument"
    DOCUMENT = "document"


@dataclass
class ProcessEvent:
    """
    Atomic unit of process intelligence.
    PM4Py event log format:
      case:concept:name = case_id
      concept:name      = activity
      time:timestamp    = timestamp
    """
    event_id: str
    case_id: str           # batch_id, experiment_id, order_id
    activity: str          # "cell_seeding", "deal_closed", etc.
    timestamp: datetime
    source_type: DataSourceType
    source_name: str

    # Scientific
    parameter_values: Optional[Dict[str, float]] = None
    outcome_values: Optional[Dict[str, float]] = None
    operator: Optional[str] = None
    batch_id: Optional[str] = None
    protocol_version: Optional[str] = None
    deviation_note: Optional[str] = None
    biofab_method: Optional[str] = None  # bioprinting|ooc|organoid|acoustic|scaffold_free

    # Business
    customer_id: Optional[str] = None
    deal_value: Optional[float] = None
    raw: Optional[Dict[str, Any]] = None


class BaseConnector:
    source_type: DataSourceType
    source_name: str

    def connect(self, credentials: dict) -> bool:
        raise NotImplementedError

    def extract(self, since=None) -> list:
        raise NotImplementedError

    def to_event_log(self, events: list):
        """Convert ProcessEvents to DataFrame with standard PM columns."""
        import pandas as pd
        records = [{
            "case:concept:name": e.case_id,
            "concept:name": e.activity,
            "time:timestamp": e.timestamp,
            "org:resource": e.operator or "unknown",
            "source": e.source_name,
            **(e.parameter_values or {}),
            **(e.outcome_values or {})
        } for e in events]
        df = pd.DataFrame(records)
        if df.empty:
            return df
        df["time:timestamp"] = pd.to_datetime(df["time:timestamp"])
        return df.sort_values("time:timestamp")
