"""
CRM CSV Connector for Stromalytix.

Accepts HubSpot/Salesforce CSV deal exports.
Maps deal stages to ProcessEvent objects.
"""
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from connectors.base import BaseConnector, DataSourceType, ProcessEvent


# HubSpot/Salesforce common column names
DEAL_STAGE_MAP = {
    "appointmentscheduled": "initial_contact",
    "qualifiedtobuy": "qualified",
    "presentationscheduled": "presentation",
    "decisionmakerboughtin": "decision_maker_approval",
    "contractsent": "contract_sent",
    "closedwon": "deal_closed_won",
    "closedlost": "deal_closed_lost",
    # Salesforce stages
    "prospecting": "initial_contact",
    "qualification": "qualified",
    "needs analysis": "needs_analysis",
    "proposal/price quote": "proposal",
    "negotiation/review": "negotiation",
    "closed won": "deal_closed_won",
    "closed lost": "deal_closed_lost",
}

CRM_COLUMN_MAPPINGS = {
    "deal_id": ["deal id", "deal_id", "opportunity id", "opportunity_id", "id"],
    "deal_name": ["deal name", "deal_name", "opportunity name", "name"],
    "stage": ["deal stage", "stage", "dealstage", "stage name"],
    "amount": ["amount", "deal amount", "value", "revenue"],
    "close_date": ["close date", "closedate", "close_date", "expected close date"],
    "create_date": ["create date", "createdate", "created date", "created_at"],
    "customer": ["company", "company name", "account", "account name", "contact"],
    "customer_id": ["company id", "account id", "contact id", "customer_id"],
    "notes": ["notes", "description", "deal description", "next steps"],
}


def _find_column(headers: List[str], candidates: List[str]) -> Optional[str]:
    lower_headers = {h.lower().strip(): h for h in headers}
    for candidate in candidates:
        if candidate.lower() in lower_headers:
            return lower_headers[candidate.lower()]
    return None


def extract_construct_requirements(notes: str) -> Dict:
    """Parse deal notes for construct parameter requirements."""
    requirements = {}
    text = notes.lower()

    # Tissue type
    tissue_patterns = ["cardiac", "liver", "neural", "bone", "cartilage",
                       "skin", "lung", "kidney", "tumor", "vascular"]
    for tissue in tissue_patterns:
        if tissue in text:
            requirements["target_tissue"] = tissue
            break

    # Stiffness
    match = re.search(r"(\d+\.?\d*)\s*kPa", notes, re.IGNORECASE)
    if match:
        requirements["stiffness_kpa"] = float(match.group(1))

    # Scaffold material
    materials = ["GelMA", "collagen", "alginate", "fibrin", "PEGDA",
                 "hyaluronic acid", "Matrigel", "silk"]
    for mat in materials:
        if mat.lower() in text:
            requirements["scaffold_material"] = mat
            break

    return requirements


class CRMCSVConnector(BaseConnector):
    """Connector for CRM CSV deal exports (HubSpot, Salesforce)."""

    source_type = DataSourceType.CRM
    source_name = "crm_csv"

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
        self._column_map = {}
        for field, candidates in CRM_COLUMN_MAPPINGS.items():
            col = _find_column(headers, candidates)
            if col:
                self._column_map[field] = col

    def extract(self, since=None) -> List[ProcessEvent]:
        if not self.filepath or not Path(self.filepath).exists():
            return []

        events = []
        with open(self.filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            self._auto_detect_columns(headers)

            for i, row in enumerate(reader):
                deal_col = self._column_map.get("deal_id")
                stage_col = self._column_map.get("stage")
                date_col = self._column_map.get("close_date") or self._column_map.get("create_date")
                amount_col = self._column_map.get("amount")
                customer_col = self._column_map.get("customer")
                customer_id_col = self._column_map.get("customer_id")
                notes_col = self._column_map.get("notes")

                deal_id = row.get(deal_col, f"deal_{i}") if deal_col else f"deal_{i}"
                raw_stage = row.get(stage_col, "unknown") if stage_col else "unknown"
                activity = DEAL_STAGE_MAP.get(raw_stage.lower().strip(), raw_stage)

                timestamp = datetime.now()
                if date_col and row.get(date_col):
                    try:
                        timestamp = datetime.fromisoformat(row[date_col])
                    except ValueError:
                        try:
                            timestamp = datetime.strptime(row[date_col], "%Y-%m-%d")
                        except ValueError:
                            pass

                deal_value = None
                if amount_col and row.get(amount_col):
                    try:
                        deal_value = float(row[amount_col].replace(",", "").replace("$", ""))
                    except ValueError:
                        pass

                # Extract construct requirements from notes
                notes_text = row.get(notes_col, "") if notes_col else ""
                construct_reqs = extract_construct_requirements(notes_text) if notes_text else {}

                event = ProcessEvent(
                    event_id=f"crm_{i}",
                    case_id=deal_id,
                    activity=activity,
                    timestamp=timestamp,
                    source_type=DataSourceType.CRM,
                    source_name=self.source_name,
                    parameter_values={k: v for k, v in construct_reqs.items() if isinstance(v, (int, float))} or None,
                    customer_id=row.get(customer_id_col) if customer_id_col else row.get(customer_col),
                    deal_value=deal_value,
                    raw=dict(row),
                )
                events.append(event)

        return events
