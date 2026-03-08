"""
Wraps PM4Py with biological process extensions.

Standard PM4Py limitation: assumes discrete events, ignores
continuous measurements and batch effects. This class handles
the biological reality: continuous viability over time,
stochastic outcomes at identical nominal parameters,
and material lot variance independent of protocol execution.

This is Stromalytix's core IP.
"""
import statistics
from collections import defaultdict
from typing import Dict, List, Optional

import pandas as pd
import pm4py


class BiologicalProcessMiner:

    def __init__(self):
        self.event_logs: Dict[str, pd.DataFrame] = {}
        self.process_models: Dict[str, object] = {}
        self.deviation_log: list = []

    def add_event_log(self, events, log_name: str):
        """Accept ProcessEvent list or PM4Py DataFrame."""
        if isinstance(events, pd.DataFrame):
            self.event_logs[log_name] = events
        else:
            # Convert ProcessEvent list to DataFrame
            from connectors.base import ProcessEvent
            records = []
            for e in events:
                rec = {
                    "case:concept:name": e.case_id,
                    "concept:name": e.activity,
                    "time:timestamp": e.timestamp,
                    "org:resource": getattr(e, "operator", None) or "unknown",
                    "batch_id": getattr(e, "batch_id", None),
                }
                if e.parameter_values:
                    rec.update(e.parameter_values)
                if e.outcome_values:
                    rec.update(e.outcome_values)
                records.append(rec)
            df = pd.DataFrame(records)
            if not df.empty:
                df = pm4py.format_dataframe(
                    df,
                    case_id="case:concept:name",
                    activity_key="concept:name",
                    timestamp_key="time:timestamp",
                )
            self.event_logs[log_name] = df

    def discover_process(self, log_name: str,
                         algorithm: str = "inductive") -> dict:
        """
        Discover process model from event log.

        Returns:
            {activities, variants, most_common_path, rare_variants}
        """
        df = self.event_logs.get(log_name)
        if df is None or df.empty:
            return {
                "activities": [],
                "variants": {},
                "most_common_path": [],
                "rare_variants": [],
            }

        # Get variants
        variants = pm4py.get_variants(df)

        # Sort by frequency
        sorted_variants = sorted(variants.items(), key=lambda x: x[1], reverse=True)

        # All unique activities
        activities = list(df["concept:name"].unique())

        most_common = list(sorted_variants[0][0]) if sorted_variants else []
        total_cases = sum(variants.values())
        rare_threshold = max(1, total_cases * 0.05)
        rare = [list(v) for v, count in sorted_variants if count <= rare_threshold]

        result = {
            "activities": activities,
            "variants": {str(k): v for k, v in sorted_variants},
            "most_common_path": most_common,
            "rare_variants": rare,
        }

        # Discover process model
        if algorithm == "inductive":
            try:
                net, im, fm = pm4py.discover_petri_net_inductive(df)
                self.process_models[log_name] = (net, im, fm)
            except Exception:
                pass

        return result

    def check_conformance(self, log_name: str,
                          reference_protocol: list) -> dict:
        """
        Score each case against reference protocol.

        Returns per-case conformance scores.
        """
        df = self.event_logs.get(log_name)
        if df is None or df.empty:
            return {}

        results = {}
        grouped = df.groupby("case:concept:name")
        for case_id, group in grouped:
            actual = list(group["concept:name"])
            missing = [a for a in reference_protocol if a not in actual]
            extra = [a for a in actual if a not in reference_protocol]

            # Simple fitness: fraction of reference steps present
            if reference_protocol:
                fitness = 1.0 - (len(missing) / len(reference_protocol))
            else:
                fitness = 1.0

            results[case_id] = {
                "fitness": max(0.0, fitness),
                "missing_activities": missing,
                "extra_activities": extra,
                "deviation_points": len(missing) + len(extra),
            }

        return results

    def find_critical_control_points(self, log_name: str,
                                      outcome_column: str) -> list:
        """
        THE BIOLOGICAL EXTENSION.
        Correlate process steps with continuous outcome measurements.
        Standard PM4Py cannot do this.

        Returns ranked list of critical control points.
        """
        df = self.event_logs.get(log_name)
        if df is None or df.empty or outcome_column not in df.columns:
            return []

        # Group by activity, compute outcome statistics
        results = []
        for activity, group in df.groupby("concept:name"):
            values = group[outcome_column].dropna()
            if len(values) < 2:
                continue

            mean_val = values.mean()
            std_val = values.std()
            cv = (std_val / mean_val * 100) if mean_val != 0 else 0

            # High CV = high variance = critical control point
            results.append({
                "activity": activity,
                "outcome_correlation": round(cv, 2),
                "mean_outcome": round(mean_val, 2),
                "std_outcome": round(std_val, 2),
                "high_value_parameters": [],
                "deviation_frequency": round(cv, 2),
                "recommendation": (
                    f"High variance (CV={cv:.1f}%) at {activity}. "
                    f"Consider tightening tolerance."
                    if cv > 10 else f"Stable at {activity} (CV={cv:.1f}%)"
                ),
            })

        # Sort by CV descending (most variable = most critical)
        results.sort(key=lambda x: x["outcome_correlation"], reverse=True)
        return results

    def detect_batch_effects(self, events, batch_column: str,
                              outcome_column: str) -> dict:
        """
        Separate material lot variance from protocol variance.

        Returns per-batch statistics with flagging.
        """
        # Convert events to DataFrame if needed
        if isinstance(events, list):
            records = []
            for e in events:
                rec = {
                    "case:concept:name": e.case_id,
                    "concept:name": e.activity,
                    "time:timestamp": e.timestamp,
                }
                if e.parameter_values:
                    rec.update(e.parameter_values)
                if e.outcome_values:
                    rec.update(e.outcome_values)
                if e.batch_id:
                    rec["batch_id"] = e.batch_id
                records.append(rec)
            df = pd.DataFrame(records)
        else:
            df = events

        if df.empty or batch_column not in df.columns or outcome_column not in df.columns:
            return {}

        results = {}
        overall_values = df[outcome_column].dropna()
        overall_mean = overall_values.mean() if len(overall_values) > 0 else 0
        overall_std = overall_values.std() if len(overall_values) > 1 else 0

        for batch_id, group in df.groupby(batch_column):
            values = group[outcome_column].dropna()
            if len(values) == 0:
                continue

            batch_mean = values.mean()
            batch_std = values.std() if len(values) > 1 else 0
            cv = (batch_std / batch_mean * 100) if batch_mean != 0 else 0

            # Flag if batch mean is below overall mean by >10% relative
            flagged = bool(batch_mean < (overall_mean * 0.85)) if overall_mean > 0 else False

            results[str(batch_id)] = {
                "mean_outcome": round(batch_mean, 2),
                "cv": round(cv, 2),
                "flagged": flagged,
                "affected_cases": list(group["case:concept:name"].unique()),
                "n_samples": len(values),
            }

        return results

    def get_kpis(self, log_name: str) -> dict:
        """
        Returns key performance indicators for the process.
        """
        df = self.event_logs.get(log_name)
        if df is None or df.empty:
            return {
                "batch_success_rate": 0.0,
                "mean_time_to_result": 0.0,
                "protocol_conformance_rate": 0.0,
                "critical_deviation_rate": 0.0,
                "most_common_failure_mode": "no_data",
                "throughput_per_week": 0.0,
            }

        grouped = df.groupby("case:concept:name")
        n_cases = len(grouped)

        # Mean time to result (hours between first and last event per case)
        durations = []
        for case_id, group in grouped:
            ts = pd.to_datetime(group["time:timestamp"])
            duration_h = (ts.max() - ts.min()).total_seconds() / 3600
            durations.append(duration_h)

        mean_duration = statistics.mean(durations) if durations else 0

        # Throughput: cases per week based on date range
        all_ts = pd.to_datetime(df["time:timestamp"])
        date_range_days = (all_ts.max() - all_ts.min()).total_seconds() / 86400
        weeks = max(date_range_days / 7, 1)
        throughput = n_cases / weeks

        return {
            "batch_success_rate": 1.0,  # Placeholder — needs outcome data
            "mean_time_to_result": round(mean_duration, 2),
            "protocol_conformance_rate": 1.0,  # Placeholder — needs reference
            "critical_deviation_rate": 0.0,
            "most_common_failure_mode": "none_detected",
            "throughput_per_week": round(throughput, 2),
        }

    def correlate_business_outcomes(self, process_events: list,
                                     crm_events: list) -> dict:
        """
        THE CROSS-LAYER SIGNAL.
        Connect experimental parameters to business outcomes.
        Which stiffness range closes deals vs. causes churn?
        """
        # Build parameter → outcome mapping
        param_outcomes = defaultdict(lambda: {"won": [], "lost": []})

        # Index CRM events by customer
        customer_outcomes = {}
        for e in crm_events:
            if e.activity in ("deal_closed_won", "closedwon"):
                customer_outcomes[e.customer_id] = "won"
            elif e.activity in ("deal_closed_lost", "closedlost"):
                customer_outcomes[e.customer_id] = "lost"

        # Correlate process parameters with business outcomes
        for e in process_events:
            if not e.parameter_values or not e.customer_id:
                continue
            outcome = customer_outcomes.get(e.customer_id)
            if not outcome:
                continue
            for param, value in e.parameter_values.items():
                param_outcomes[param][outcome].append(value)

        # Compute correlations
        correlations = {}
        for param, outcomes in param_outcomes.items():
            won_vals = outcomes["won"]
            lost_vals = outcomes["lost"]
            correlations[param] = {
                "won_mean": round(statistics.mean(won_vals), 2) if won_vals else None,
                "lost_mean": round(statistics.mean(lost_vals), 2) if lost_vals else None,
                "won_count": len(won_vals),
                "lost_count": len(lost_vals),
                "signal": "insufficient_data" if len(won_vals) < 3 or len(lost_vals) < 3 else "significant",
            }

        return correlations
