"""Tests for KPI Dashboard."""
import tempfile
from core.models import ConstructProfile
from core.process_graph import ProcessGraph


def _make_graph():
    pg = ProcessGraph(graph_path=tempfile.mktemp(suffix=".json"))
    profile = ConstructProfile(target_tissue="cardiac", stiffness_kpa=10.0)
    cid = pg.add_construct(profile)
    pg.add_outcome(cid, "viability", 85.0, "%")
    pg.add_deal("deal_1", "cust_1", outcome="won")
    pg.link_construct_to_deal(cid, "deal_1")
    return pg


def test_kpi_dashboard_importable():
    from core.kpi_dashboard import KPIDashboard
    pg = _make_graph()
    dash = KPIDashboard(pg)
    assert dash is not None


def test_scientific_kpis_returns_dict():
    from core.kpi_dashboard import KPIDashboard
    dash = KPIDashboard(_make_graph())
    kpis = dash.get_scientific_kpis()
    assert isinstance(kpis, dict)
    assert "constructs_analyzed" in kpis
    assert "prediction_accuracy" in kpis


def test_business_kpis_returns_dict():
    from core.kpi_dashboard import KPIDashboard
    dash = KPIDashboard(_make_graph())
    kpis = dash.get_business_kpis()
    assert isinstance(kpis, dict)
    assert "total_deals" in kpis
    assert "win_rate" in kpis


def test_cross_layer_kpis_returns_dict():
    from core.kpi_dashboard import KPIDashboard
    dash = KPIDashboard(_make_graph())
    kpis = dash.get_cross_layer_kpis()
    assert isinstance(kpis, dict)
    assert "parameter_win_rate" in kpis


def test_summary_card_returns_list():
    from core.kpi_dashboard import KPIDashboard
    dash = KPIDashboard(_make_graph())
    card = dash.get_summary_card()
    assert isinstance(card, list)
    assert len(card) > 0


def test_render_sidebar_does_not_crash_on_empty_graph():
    from core.kpi_dashboard import KPIDashboard
    pg = ProcessGraph(graph_path=tempfile.mktemp(suffix=".json"))
    dash = KPIDashboard(pg)
    # Should not raise even without streamlit
    dash.render_streamlit_sidebar()
