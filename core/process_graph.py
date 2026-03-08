"""
Process Intelligence Graph for Stromalytix.

Arc 1: networkx (local, no infrastructure needed)
Arc 2: Neo4j AsyncGraphDatabase driver v5.28+
       Parameterized Cypher ONLY — never string concatenate.

The novel edges are PREDICTS and VALIDATES:
PREDICTS: SimulationBrief → Outcome (with confidence)
VALIDATES: actual Outcome → SimulationBrief (post-experiment)
These two edges are how prediction accuracy is tracked.
"""
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import networkx as nx


class ProcessGraph:
    """Knowledge graph connecting constructs, outcomes, batches, and deals."""

    def __init__(self, graph_path: str = "data/process_graph.json"):
        self.graph = nx.DiGraph()
        self.graph_path = graph_path
        self._load_if_exists()

    def _load_if_exists(self):
        path = Path(self.graph_path)
        if path.exists():
            try:
                self.load_from_json(str(path))
            except Exception:
                pass

    def _node_id(self, prefix: str = "node") -> str:
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    def add_construct(self, profile, run_id: Optional[str] = None) -> str:
        """Add a construct node from a ConstructProfile."""
        node_id = run_id or self._node_id("construct")
        attrs = {"type": "Construct"}
        if hasattr(profile, "model_dump"):
            data = profile.model_dump()
        elif isinstance(profile, dict):
            data = profile
        else:
            data = {}
        attrs.update({k: v for k, v in data.items() if v is not None and k != "raw_responses"})
        self.graph.add_node(node_id, **attrs)

        # Add parameter nodes and link
        for param in ["stiffness_kpa", "porosity_percent", "cell_density_per_ml"]:
            val = data.get(param)
            if val is not None:
                param_id = f"{node_id}_{param}"
                self.graph.add_node(param_id, type="Parameter", name=param, value=val)
                self.graph.add_edge(node_id, param_id, relation="HAS_PARAMETER")

        return node_id

    def add_outcome(self, construct_id: str, outcome_type: str,
                    value: float, unit: str, pmid: Optional[str] = None):
        """Add an outcome node linked to a construct."""
        outcome_id = self._node_id("outcome")
        attrs = {
            "type": "Outcome",
            "outcome_type": outcome_type,
            "value": value,
            "unit": unit,
        }
        if pmid:
            attrs["pmid"] = pmid
        self.graph.add_node(outcome_id, **attrs)
        self.graph.add_edge(construct_id, outcome_id, relation="PRODUCES")
        return outcome_id

    def add_batch(self, batch_id: str, material_type: str,
                  lot_number: str, parameters: Optional[Dict] = None):
        """Add a batch/material lot node."""
        attrs = {
            "type": "Batch",
            "material_type": material_type,
            "lot_number": lot_number,
        }
        if parameters:
            attrs.update(parameters)
        self.graph.add_node(batch_id, **attrs)
        return batch_id

    def add_deal(self, deal_id: str, customer_id: str,
                 construct_requirements: Optional[Dict] = None,
                 outcome: str = "unknown"):
        """Add a deal node with customer link."""
        self.graph.add_node(deal_id, type="Deal", outcome=outcome)

        # Add or update customer node
        if not self.graph.has_node(customer_id):
            self.graph.add_node(customer_id, type="Customer")
        self.graph.add_edge(deal_id, customer_id, relation="REQUESTED_BY")

        if construct_requirements:
            self.graph.nodes[deal_id].update(construct_requirements)

        return deal_id

    def link_construct_to_deal(self, construct_id: str, deal_id: str):
        self.graph.add_edge(construct_id, deal_id, relation="ASSOCIATED_WITH")

    def link_construct_to_batch(self, construct_id: str, batch_id: str):
        self.graph.add_edge(construct_id, batch_id, relation="USES_BATCH")

    def add_simulation_prediction(self, construct_id: str,
                                   brief_dict: Dict,
                                   predicted_outcomes: List[str]):
        """Add simulation prediction node linked to construct."""
        pred_id = self._node_id("prediction")
        self.graph.add_node(pred_id, type="Prediction",
                           brief=json.dumps(brief_dict) if isinstance(brief_dict, dict) else str(brief_dict),
                           predicted_outcomes=predicted_outcomes,
                           validated=False)
        self.graph.add_edge(pred_id, construct_id, relation="PREDICTS")
        return pred_id

    def validate_prediction(self, construct_id: str,
                             actual_outcomes: Dict):
        """Validate predictions against actual outcomes."""
        # Find prediction nodes for this construct
        for pred, _, data in self.graph.in_edges(construct_id, data=True):
            if data.get("relation") == "PREDICTS":
                node_data = self.graph.nodes[pred]
                node_data["validated"] = True
                node_data["actual_outcomes"] = json.dumps(actual_outcomes)
                self.graph.add_edge(construct_id, pred, relation="VALIDATES")

    def get_prediction_accuracy(self) -> dict:
        """Calculate prediction accuracy across all validated predictions."""
        predictions = [n for n, d in self.graph.nodes(data=True)
                      if d.get("type") == "Prediction"]
        total = len(predictions)
        validated = sum(1 for n in predictions
                       if self.graph.nodes[n].get("validated", False))
        return {
            "total_predictions": total,
            "validated_predictions": validated,
            "accuracy": validated / total if total > 0 else 0.0,
        }

    def get_parameter_outcome_correlations(self, param: str) -> dict:
        """Get correlations between a parameter and outcomes."""
        param_nodes = [n for n, d in self.graph.nodes(data=True)
                      if d.get("type") == "Parameter" and d.get("name") == param]
        correlations = {"param": param, "data_points": []}
        for pn in param_nodes:
            val = self.graph.nodes[pn].get("value")
            # Find parent construct
            for pred in self.graph.predecessors(pn):
                # Find outcomes of that construct
                for succ in self.graph.successors(pred):
                    if self.graph.nodes.get(succ, {}).get("type") == "Outcome":
                        correlations["data_points"].append({
                            "param_value": val,
                            "outcome_type": self.graph.nodes[succ].get("outcome_type"),
                            "outcome_value": self.graph.nodes[succ].get("value"),
                        })
        return correlations

    def get_business_parameter_correlations(self) -> list:
        """Which parameters correlate with deal outcomes?"""
        results = []
        deals = [n for n, d in self.graph.nodes(data=True) if d.get("type") == "Deal"]
        for deal_id in deals:
            deal_data = self.graph.nodes[deal_id]
            outcome = deal_data.get("outcome", "unknown")
            # Find linked constructs
            for pred in self.graph.predecessors(deal_id):
                if self.graph.nodes.get(pred, {}).get("type") == "Construct":
                    construct_data = self.graph.nodes[pred]
                    results.append({
                        "deal_id": deal_id,
                        "outcome": outcome,
                        "construct_params": {
                            k: v for k, v in construct_data.items()
                            if k not in ("type",) and isinstance(v, (int, float))
                        },
                    })
        return results

    def get_stats(self) -> dict:
        """Returns stats for sidebar display."""
        nodes = dict(self.graph.nodes(data=True))
        type_counts = {}
        for _, data in nodes.items():
            t = data.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        accuracy = self.get_prediction_accuracy()
        return {
            "constructs_analyzed": type_counts.get("Construct", 0),
            "outcomes_tracked": type_counts.get("Outcome", 0),
            "predictions_made": type_counts.get("Prediction", 0),
            "prediction_accuracy": accuracy["accuracy"],
            "deals_linked": type_counts.get("Deal", 0),
            "batches_tracked": type_counts.get("Batch", 0),
        }

    def export_to_json(self, path: str):
        """Export graph to JSON."""
        data = {
            "nodes": [
                {"id": n, **{k: v for k, v in d.items() if _is_serializable(v)}}
                for n, d in self.graph.nodes(data=True)
            ],
            "edges": [
                {"source": u, "target": v, **{k: val for k, val in d.items() if _is_serializable(val)}}
                for u, v, d in self.graph.edges(data=True)
            ],
            "metadata": {
                "version": "1.0",
                "description": "Stromalytix PI Graph — Arc 1 (networkx)",
                "arc2_migration": "Neo4j AsyncGraphDatabase v5.28+",
                "neo4j_note": "Parameterized Cypher only",
            },
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def load_from_json(self, path: str):
        """Load graph from JSON."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.graph = nx.DiGraph()
        for node in data.get("nodes", []):
            node_id = node.pop("id")
            self.graph.add_node(node_id, **node)
        for edge in data.get("edges", []):
            src = edge.pop("source")
            tgt = edge.pop("target")
            self.graph.add_edge(src, tgt, **edge)


def _is_serializable(val):
    """Check if value is JSON-serializable."""
    return isinstance(val, (str, int, float, bool, list, type(None)))
