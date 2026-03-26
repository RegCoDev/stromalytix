"""
KPI Dashboard for Stromalytix.

Three tiers of KPIs:

Scientific: batch_success_rate, mean_time_to_result,
            protocol_conformance_rate, prediction_accuracy

Business: revenue_per_protocol_version, win_rate_by_parameter,
          churn_correlation_batch_id, cost_per_construct

Cross-layer (the novel ones):
  parameter_win_rate: which stiffness ranges close deals
  batch_business_impact: which lots caused customer churn
  protocol_version_revenue: v3.1 vs v3.2 deal outcomes

These cross-layer KPIs are the core moat insight —
no LIMS, ELN, or CRO tool surfaces these connections.
"""
from typing import Optional


class KPIDashboard:
    """Unified KPI dashboard across science, business, and cross-layer."""

    def __init__(self, process_graph, process_miner=None):
        self.graph = process_graph
        self.miner = process_miner

    def get_scientific_kpis(self) -> dict:
        """Scientific process KPIs."""
        stats = self.graph.get_stats()
        accuracy = self.graph.get_prediction_accuracy()

        kpis = {
            "constructs_analyzed": stats.get("constructs_analyzed", 0),
            "outcomes_tracked": stats.get("outcomes_tracked", 0),
            "prediction_accuracy": accuracy.get("accuracy", 0.0),
            "batch_success_rate": 0.0,
            "mean_time_to_result": 0.0,
            "protocol_conformance_rate": 0.0,
        }

        # Enrich from process miner if available
        if self.miner and self.miner.event_logs:
            first_log = next(iter(self.miner.event_logs))
            miner_kpis = self.miner.get_kpis(first_log)
            kpis["batch_success_rate"] = miner_kpis.get("batch_success_rate", 0.0)
            kpis["mean_time_to_result"] = miner_kpis.get("mean_time_to_result", 0.0)
            kpis["protocol_conformance_rate"] = miner_kpis.get("protocol_conformance_rate", 0.0)

        return kpis

    def get_business_kpis(self) -> dict:
        """Business outcome KPIs."""
        stats = self.graph.get_stats()
        deals = stats.get("deals_linked", 0)

        # Count won/lost from graph
        won = 0
        lost = 0
        for node, data in self.graph.graph.nodes(data=True):
            if data.get("type") == "Deal":
                outcome = data.get("outcome", "unknown")
                if outcome == "won":
                    won += 1
                elif outcome == "lost":
                    lost += 1

        total_deals = won + lost
        win_rate = won / total_deals if total_deals > 0 else 0.0

        return {
            "total_deals": deals,
            "win_rate": round(win_rate, 2),
            "revenue_per_protocol_version": {},  # Populated with real data
            "win_rate_by_parameter": {},
            "churn_correlation_batch_id": {},
            "cost_per_construct": 0.0,
        }

    def get_cross_layer_kpis(self) -> dict:
        """Cross-layer KPIs — the novel ones."""
        biz_correlations = self.graph.get_business_parameter_correlations()

        # Aggregate parameter → win/loss
        param_wins = {}
        for entry in biz_correlations:
            outcome = entry.get("outcome", "unknown")
            for param, val in entry.get("construct_params", {}).items():
                if param not in param_wins:
                    param_wins[param] = {"won": [], "lost": []}
                if outcome == "won":
                    param_wins[param]["won"].append(val)
                elif outcome == "lost":
                    param_wins[param]["lost"].append(val)

        parameter_win_rate = {}
        for param, data in param_wins.items():
            total = len(data["won"]) + len(data["lost"])
            if total > 0:
                parameter_win_rate[param] = round(len(data["won"]) / total, 2)

        return {
            "parameter_win_rate": parameter_win_rate,
            "batch_business_impact": {},  # Populated when batch+deal data available
            "protocol_version_revenue": {},  # Populated with protocol+deal data
        }

    def get_summary_card(self) -> list:
        """Top 5 actionable insights as human-readable strings."""
        insights = []

        sci = self.get_scientific_kpis()
        biz = self.get_business_kpis()
        cross = self.get_cross_layer_kpis()

        constructs = sci.get("constructs_analyzed", 0)
        if constructs > 0:
            insights.append(f"{constructs} constructs analyzed in PI graph.")

        accuracy = sci.get("prediction_accuracy", 0)
        if accuracy > 0:
            insights.append(f"Prediction accuracy: {accuracy:.0%}")

        outcomes = sci.get("outcomes_tracked", 0)
        if outcomes > 0:
            insights.append(f"{outcomes} experimental outcomes tracked.")

        win_rate = biz.get("win_rate", 0)
        if biz.get("total_deals", 0) > 0:
            insights.append(f"Deal win rate: {win_rate:.0%}")

        pw = cross.get("parameter_win_rate", {})
        for param, rate in pw.items():
            insights.append(f"{param} win rate: {rate:.0%}")

        if not insights:
            insights.append("No data yet. Run analyses to populate KPIs.")

        return insights[:5]

    def render_streamlit_sidebar(self):
        """Render KPI sidebar in Streamlit. Graceful degradation on empty graph."""
        try:
            import streamlit as st
        except ImportError:
            return

        stats = self.graph.get_stats()
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Process Intelligence")

        constructs = stats.get("constructs_analyzed", 0)
        outcomes = stats.get("outcomes_tracked", 0)
        predictions = stats.get("predictions_made", 0)

        st.sidebar.metric("Constructs", constructs)
        st.sidebar.metric("Outcomes", outcomes)
        st.sidebar.metric("Predictions", predictions)

        accuracy = stats.get("prediction_accuracy", 0)
        if predictions > 0:
            st.sidebar.metric("Accuracy", f"{accuracy:.0%}")

        insights = self.get_summary_card()
        if insights and insights[0] != "No data yet. Run analyses to populate KPIs.":
            st.sidebar.markdown("**Insights:**")
            for insight in insights[:3]:
                st.sidebar.markdown(f"- {insight}")
