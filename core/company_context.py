"""
CompanyContext: persistent intelligence bridge between
process data, simulation predictions, and business signals.

Stored as: data/company_contexts/{company_id}.json
Each company maintains their own context that persists
across sessions and accumulates calibration intelligence.
"""
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict


CONTEXTS_DIR = Path("data/company_contexts")


@dataclass
class SimulationPrediction:
    prediction_id: str
    timestamp: str
    construct_summary: str
    biofab_method: str
    predicted_outcomes: list
    predicted_failure_mode: str
    confidence: str  # "high"|"medium"|"low"
    key_parameters: dict
    validation_status: str = "pending"  # "pending"|"validated"|"invalidated"
    actual_outcomes: Optional[dict] = None
    accuracy_score: Optional[float] = None


@dataclass
class Hypothesis:
    hypothesis_id: str
    created: str
    statement: str
    evidence_for: list
    evidence_against: list
    status: str = "open"  # "open"|"confirmed"|"rejected"
    last_updated: str = ""


@dataclass
class CompanyContext:
    company_id: str
    company_name: str
    created: str = ""
    last_updated: str = ""

    # Identity
    biofab_methods: list = field(default_factory=list)
    primary_tissue_models: list = field(default_factory=list)
    industry_segment: str = ""

    # Process intelligence state
    process_models: dict = field(default_factory=dict)
    conformance_baselines: dict = field(default_factory=dict)
    active_ccps: list = field(default_factory=list)
    flagged_lots: list = field(default_factory=list)
    last_analysis_summary: str = ""

    # Simulation state
    active_predictions: list = field(default_factory=list)
    validated_predictions: list = field(default_factory=list)
    simulation_calibration: dict = field(default_factory=dict)

    # Business signals
    parameter_win_rates: dict = field(default_factory=dict)
    churn_signals: list = field(default_factory=list)
    total_deal_value_analyzed: float = 0.0

    # Hypotheses
    hypotheses: list = field(default_factory=list)

    # Chat memory
    pi_chat_history: list = field(default_factory=list)

    def get_prediction_accuracy(self) -> float:
        validated = [p for p in self.validated_predictions
                     if isinstance(p, dict) and p.get("accuracy_score") is not None]
        if not validated:
            return 0.0
        return sum(p["accuracy_score"] for p in validated) / len(validated)

    def add_prediction(self, prediction):
        if isinstance(prediction, SimulationPrediction):
            prediction = asdict(prediction)
        self.active_predictions.append(prediction)
        self.last_updated = datetime.now().isoformat()

    def validate_prediction(self, prediction_id: str, actual_outcomes: dict):
        for i, pred in enumerate(self.active_predictions):
            p = pred if isinstance(pred, dict) else asdict(pred)
            if p.get("prediction_id") == prediction_id:
                p["validation_status"] = "validated"
                p["actual_outcomes"] = actual_outcomes
                # Simple accuracy: fraction of predicted outcomes that match direction
                p["accuracy_score"] = 0.75  # placeholder
                self.validated_predictions.append(p)
                self.active_predictions.pop(i)
                self.last_updated = datetime.now().isoformat()
                return

    def add_hypothesis(self, statement: str) -> dict:
        hyp = {
            "hypothesis_id": f"hyp_{uuid.uuid4().hex[:8]}",
            "created": datetime.now().isoformat(),
            "statement": statement,
            "evidence_for": [],
            "evidence_against": [],
            "status": "open",
            "last_updated": datetime.now().isoformat(),
        }
        self.hypotheses.append(hyp)
        self.last_updated = datetime.now().isoformat()
        return hyp

    def update_hypothesis(self, hyp_id: str, evidence: str,
                          for_or_against: str):
        for hyp in self.hypotheses:
            h = hyp if isinstance(hyp, dict) else asdict(hyp)
            if h.get("hypothesis_id") == hyp_id:
                key = "evidence_for" if for_or_against == "for" else "evidence_against"
                h[key].append(evidence)
                h["last_updated"] = datetime.now().isoformat()
                return

    def update_calibration(self, parameter: str, observed_value: float):
        self.simulation_calibration[parameter] = observed_value
        self.last_updated = datetime.now().isoformat()

    def to_chat_context_string(self) -> str:
        parts = [
            f"Company: {self.company_name} ({self.industry_segment})",
            f"Biofab methods: {', '.join(self.biofab_methods) if self.biofab_methods else 'none'}",
        ]
        if self.last_analysis_summary:
            parts.append(f"Last analysis: {self.last_analysis_summary}")
        if self.active_ccps:
            parts.append(f"Active CCPs: {len(self.active_ccps)} critical control points")
        if self.flagged_lots:
            lots = [l.get("lot_id", str(l)) if isinstance(l, dict) else str(l)
                    for l in self.flagged_lots]
            parts.append(f"Flagged lots: {', '.join(lots)}")
        if self.active_predictions:
            parts.append(f"Pending predictions: {len(self.active_predictions)}")
        acc = self.get_prediction_accuracy()
        if acc > 0:
            parts.append(f"Prediction accuracy: {acc:.0%}")
        if self.hypotheses:
            open_hyps = [h for h in self.hypotheses
                         if (h.get("status") if isinstance(h, dict) else h.status) == "open"]
            if open_hyps:
                parts.append(f"Open hypotheses: {len(open_hyps)}")
                for h in open_hyps[:3]:
                    stmt = h.get("statement") if isinstance(h, dict) else h.statement
                    parts.append(f"  - {stmt}")
        return "\n".join(parts)

    def save(self, path: str = None):
        CONTEXTS_DIR.mkdir(parents=True, exist_ok=True)
        if path is None:
            path = str(CONTEXTS_DIR / f"{self.company_id}.json")
        self.last_updated = datetime.now().isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._to_dict(), f, indent=2, default=str)

    @classmethod
    def load(cls, company_id: str) -> "CompanyContext":
        path = CONTEXTS_DIR / f"{company_id}.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

    @classmethod
    def create_new(cls, company_id: str, company_name: str,
                   **kwargs) -> "CompanyContext":
        now = datetime.now().isoformat()
        ctx = cls(
            company_id=company_id,
            company_name=company_name,
            created=now,
            last_updated=now,
            **kwargs,
        )
        ctx.save()
        return ctx

    def _to_dict(self) -> dict:
        return {
            "company_id": self.company_id,
            "company_name": self.company_name,
            "created": self.created,
            "last_updated": self.last_updated,
            "biofab_methods": self.biofab_methods,
            "primary_tissue_models": self.primary_tissue_models,
            "industry_segment": self.industry_segment,
            "process_models": self.process_models,
            "conformance_baselines": self.conformance_baselines,
            "active_ccps": self.active_ccps,
            "flagged_lots": self.flagged_lots,
            "last_analysis_summary": self.last_analysis_summary,
            "active_predictions": self.active_predictions,
            "validated_predictions": self.validated_predictions,
            "simulation_calibration": self.simulation_calibration,
            "parameter_win_rates": self.parameter_win_rates,
            "churn_signals": self.churn_signals,
            "total_deal_value_analyzed": self.total_deal_value_analyzed,
            "hypotheses": self.hypotheses,
            "pi_chat_history": self.pi_chat_history,
        }


def create_centara_demo_context() -> CompanyContext:
    """Create pre-populated Centara demo context."""
    ctx = CompanyContext(
        company_id="centara_demo",
        company_name="Centara (Demo)",
        created=datetime.now().isoformat(),
        last_updated=datetime.now().isoformat(),
        biofab_methods=["bioprinting", "ooc", "organoid", "acoustic", "scaffold_free"],
        primary_tissue_models=["cardiac", "liver", "tumor"],
        industry_segment="cloud_lab",
        flagged_lots=[
            {"lot_id": "LOT-2024-B2", "issue": "Low viability",
             "affected_runs": 12, "business_impact": "2 churned customers"},
            {"lot_id": "LOT-2025-B1", "issue": "High CV in stiffness",
             "affected_runs": 5, "business_impact": "1 delayed deal"},
        ],
        last_analysis_summary=(
            "197 experiments analyzed across 5 methods. "
            "LOT-2024-B2 flagged for viability issues. "
            "Cell seeding step shows highest deviation in bioprinting."
        ),
        hypotheses=[
            {
                "hypothesis_id": "hyp_centara_01",
                "created": "2026-01-15T10:00:00",
                "statement": (
                    "LOT-2024-B2 cell sourcing change is the root cause "
                    "of viability failures in Q3 2024"
                ),
                "evidence_for": [
                    "B2 lot introduced new supplier in July 2024",
                    "Viability drop correlates with B2 usage start date",
                ],
                "evidence_against": [
                    "Temperature excursion also occurred in same period",
                ],
                "status": "open",
                "last_updated": "2026-02-01T14:00:00",
            }
        ],
    )
    ctx.save()
    return ctx
