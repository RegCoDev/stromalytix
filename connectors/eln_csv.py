"""
ELN CSV Connector for Stromalytix.

Accepts CSV exports from Benchling, LabArchives, SciNote.
Maps experimental records to ProcessEvent objects.
"""
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from connectors.base import BaseConnector, DataSourceType, ProcessEvent


# Common column name mappings across ELN platforms
COLUMN_MAPPINGS = {
    "case_id": ["experiment_id", "experiment id", "exp_id", "run_id", "sample_id", "entry_id"],
    "activity": ["step", "step_name", "activity", "action", "procedure", "task"],
    "timestamp": ["timestamp", "date", "datetime", "time", "created_at", "modified_at"],
    "operator": ["operator", "user", "author", "researcher", "performed_by", "created_by"],
    "deviation_note": ["deviation", "deviation_note", "notes", "comment", "observation"],
    "protocol_version": ["protocol", "protocol_version", "sop", "version"],
    "batch_id": ["batch", "batch_id", "lot", "lot_number"],
    "biofab_method": ["biofab_method", "method", "fabrication_method", "biofabrication_method"],
}

BIOFAB_METHODS = {"bioprinting", "ooc", "organoid", "acoustic", "scaffold_free"}


def _find_column(headers: List[str], candidates: List[str]) -> Optional[str]:
    """Find first matching column name (case-insensitive)."""
    lower_headers = {h.lower().strip(): h for h in headers}
    for candidate in candidates:
        if candidate.lower() in lower_headers:
            return lower_headers[candidate.lower()]
    return None


def extract_parameters(text: str) -> Dict[str, float]:
    """Parse parameter values from text like '4 kPa stiffness', '70% porosity'."""
    params = {}
    patterns = [
        (r"(\d+\.?\d*)\s*kPa\s*(?:stiffness)?", "stiffness_kpa"),
        (r"(\d+\.?\d*)\s*%\s*(?:porosity)?", "porosity_percent"),
        (r"(?:stiffness)\s*(?:of|:|\s)\s*(\d+\.?\d*)", "stiffness_kpa"),
        (r"(?:porosity)\s*(?:of|:|\s)\s*(\d+\.?\d*)", "porosity_percent"),
        (r"(\d+\.?\d*)\s*(?:cells?/mL|cells?/ml)", "cell_density_per_ml"),
        (r"(\d+\.?\d*)\s*°?C\s*(?:temp|temperature)?", "temperature_c"),
        (r"(\d+\.?\d*)\s*(?:Pa\s*pressure|kPa\s*pressure)", "pressure_kpa"),
    ]
    for pattern, key in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            params[key] = float(match.group(1))
    return params


class ELNCSVConnector(BaseConnector):
    """Connector for ELN CSV exports (Benchling, LabArchives, SciNote)."""

    source_type = DataSourceType.ELN
    source_name = "eln_csv"

    def __init__(self, filepath: str = ""):
        self.filepath = filepath
        self._column_map = {}

    def connect(self, credentials: dict) -> bool:
        path = credentials.get("filepath", self.filepath)
        if path and Path(path).exists():
            self.filepath = path
            return True
        return False

    def _auto_detect_columns(self, headers: List[str]):
        """Auto-detect column mapping from header names."""
        self._column_map = {}
        for field, candidates in COLUMN_MAPPINGS.items():
            col = _find_column(headers, candidates)
            if col:
                self._column_map[field] = col

    def extract(self, since=None) -> List[ProcessEvent]:
        """Extract ProcessEvents from CSV file."""
        if not self.filepath or not Path(self.filepath).exists():
            return []

        events = []
        with open(self.filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            self._auto_detect_columns(headers)

            for i, row in enumerate(reader):
                case_col = self._column_map.get("case_id")
                activity_col = self._column_map.get("activity")
                ts_col = self._column_map.get("timestamp")

                case_id = row.get(case_col, f"case_{i}") if case_col else f"case_{i}"
                activity = row.get(activity_col, "unknown") if activity_col else "unknown"

                timestamp = datetime.now()
                if ts_col and row.get(ts_col):
                    try:
                        timestamp = datetime.fromisoformat(row[ts_col])
                    except ValueError:
                        try:
                            timestamp = datetime.strptime(row[ts_col], "%Y-%m-%d")
                        except ValueError:
                            pass

                # Extract parameter values from all value-like columns
                param_values = {}
                for key, val in row.items():
                    if val:
                        extracted = extract_parameters(val)
                        param_values.update(extracted)

                operator_col = self._column_map.get("operator")
                deviation_col = self._column_map.get("deviation_note")
                protocol_col = self._column_map.get("protocol_version")
                batch_col = self._column_map.get("batch_id")
                biofab_col = self._column_map.get("biofab_method")

                event = ProcessEvent(
                    event_id=f"eln_{i}",
                    case_id=case_id,
                    activity=activity,
                    timestamp=timestamp,
                    source_type=DataSourceType.ELN,
                    source_name=self.source_name,
                    parameter_values=param_values or None,
                    operator=row.get(operator_col) if operator_col else None,
                    deviation_note=row.get(deviation_col) if deviation_col else None,
                    protocol_version=row.get(protocol_col) if protocol_col else None,
                    batch_id=row.get(batch_col) if batch_col else None,
                    biofab_method=row.get(biofab_col) if biofab_col else None,
                    raw=dict(row),
                )
                events.append(event)

        return events
