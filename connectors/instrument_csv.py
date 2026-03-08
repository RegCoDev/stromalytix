"""
Instrument CSV Connector for Stromalytix.

Handles bioprinter logs (Cellink, Allevi, Aspect),
plate reader exports (SpectraMax, Synergy),
and rheometer exports.
"""
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from connectors.base import BaseConnector, DataSourceType, ProcessEvent


# Instrument detection patterns in headers or filenames
INSTRUMENT_SIGNATURES = {
    "cellink": ["print_speed", "nozzle_temp", "pressure_kpa", "cellink", "bioprinter"],
    "allevi": ["allevi", "well_plate", "print_pressure"],
    "aspect": ["aspect", "rvo", "print_head"],
    "spectramax": ["spectramax", "absorbance", "od_", "wavelength"],
    "synergy": ["synergy", "biotek", "fluorescence", "luminescence"],
    "rheometer": ["storage_modulus", "loss_modulus", "viscosity", "shear_rate", "rheolog"],
}


def detect_instrument(filepath: str) -> str:
    """Detect instrument type from filename and headers."""
    path = Path(filepath)
    fname = path.name.lower()

    # Check filename first
    for instrument, signatures in INSTRUMENT_SIGNATURES.items():
        for sig in signatures:
            if sig in fname:
                return instrument

    # Check CSV headers
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader, [])
            header_str = " ".join(h.lower() for h in headers)
            for instrument, signatures in INSTRUMENT_SIGNATURES.items():
                for sig in signatures:
                    if sig in header_str:
                        return instrument
    except Exception:
        pass

    return "unknown"


def extract_print_parameters(df: pd.DataFrame) -> Dict[str, float]:
    """Extract bioprinter parameters from DataFrame."""
    params = {}
    col_map = {
        "nozzle_temp": ["nozzle_temp", "nozzle_temperature", "temperature"],
        "pressure_kpa": ["pressure_kpa", "pressure", "print_pressure"],
        "print_speed": ["print_speed", "speed", "velocity"],
        "layer_height": ["layer_height", "z_step", "layer_thickness"],
        "nozzle_diameter": ["nozzle_diameter", "nozzle_size", "needle_gauge"],
    }
    lower_cols = {c.lower(): c for c in df.columns}
    for param, candidates in col_map.items():
        for candidate in candidates:
            if candidate in lower_cols:
                col = lower_cols[candidate]
                try:
                    params[param] = float(df[col].mean())
                except (ValueError, TypeError):
                    pass
                break
    return params


def extract_outcome_values(df: pd.DataFrame) -> Dict[str, float]:
    """Extract outcome measurements from DataFrame."""
    outcomes = {}
    col_map = {
        "viability_percent": ["viability", "viability_percent", "cell_viability", "live_dead"],
        "absorbance": ["absorbance", "od", "optical_density"],
        "fluorescence": ["fluorescence", "rfu", "fluorescence_intensity"],
        "ic50": ["ic50", "ec50"],
        "teer": ["teer", "resistance"],
        "contractility": ["contractility", "beating_rate", "contraction"],
        "storage_modulus": ["storage_modulus", "g_prime", "elastic_modulus"],
        "viscosity": ["viscosity", "dynamic_viscosity"],
    }
    lower_cols = {c.lower(): c for c in df.columns}
    for outcome, candidates in col_map.items():
        for candidate in candidates:
            if candidate in lower_cols:
                col = lower_cols[candidate]
                try:
                    outcomes[outcome] = float(df[col].mean())
                except (ValueError, TypeError):
                    pass
                break
    return outcomes


class InstrumentCSVConnector(BaseConnector):
    """Connector for instrument CSV exports."""

    source_type = DataSourceType.INSTRUMENT
    source_name = "instrument_csv"

    def __init__(self, filepath: str = ""):
        self.filepath = filepath
        self.instrument_type = "unknown"

    def connect(self, credentials: dict) -> bool:
        path = credentials.get("filepath", self.filepath)
        if path and Path(path).exists():
            self.filepath = path
            self.instrument_type = detect_instrument(path)
            return True
        return False

    def extract(self, since=None) -> List[ProcessEvent]:
        if not self.filepath or not Path(self.filepath).exists():
            return []

        try:
            df = pd.read_csv(self.filepath, encoding="utf-8")
        except Exception:
            return []

        print_params = extract_print_parameters(df)
        outcome_vals = extract_outcome_values(df)

        events = []
        for i, row in df.iterrows():
            timestamp = datetime.now()
            # Try to find a timestamp column
            for col in df.columns:
                if col.lower() in ("timestamp", "date", "datetime", "time"):
                    try:
                        timestamp = pd.to_datetime(row[col]).to_pydatetime()
                    except Exception:
                        pass
                    break

            event = ProcessEvent(
                event_id=f"inst_{i}",
                case_id=f"run_{i}",
                activity=f"{self.instrument_type}_measurement",
                timestamp=timestamp,
                source_type=DataSourceType.INSTRUMENT,
                source_name=self.source_name,
                parameter_values=print_params or None,
                outcome_values=outcome_vals or None,
                raw=row.to_dict(),
            )
            events.append(event)

        return events
