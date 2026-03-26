"""Tests for Process Intelligence Graph."""
import json
import tempfile
from pathlib import Path

from core.models import ConstructProfile


def test_process_graph_importable():
    from core.process_graph import ProcessGraph
    pg = ProcessGraph(graph_path="data/process_graph.json")
    assert pg is not None


def test_add_construct_returns_string_id():
    from core.process_graph import ProcessGraph
    pg = ProcessGraph(graph_path=tempfile.mktemp(suffix=".json"))
    profile = ConstructProfile(target_tissue="cardiac", stiffness_kpa=10.0)
    node_id = pg.add_construct(profile)
    assert isinstance(node_id, str)
    assert len(node_id) > 0


def test_add_outcome_links_to_construct():
    from core.process_graph import ProcessGraph
    pg = ProcessGraph(graph_path=tempfile.mktemp(suffix=".json"))
    profile = ConstructProfile(target_tissue="cardiac")
    cid = pg.add_construct(profile)
    oid = pg.add_outcome(cid, "viability", 85.0, "%")
    assert pg.graph.has_edge(cid, oid)


def test_add_deal_and_link():
    from core.process_graph import ProcessGraph
    pg = ProcessGraph(graph_path=tempfile.mktemp(suffix=".json"))
    profile = ConstructProfile(target_tissue="cardiac")
    cid = pg.add_construct(profile)
    pg.add_deal("deal_1", "cust_1", outcome="won")
    pg.link_construct_to_deal(cid, "deal_1")
    assert pg.graph.has_node("deal_1")
    assert pg.graph.nodes["deal_1"]["type"] == "Deal"
    assert pg.graph.has_node("cust_1")
    assert pg.graph.nodes["cust_1"]["type"] == "Customer"


def test_get_stats_has_required_keys():
    from core.process_graph import ProcessGraph
    pg = ProcessGraph(graph_path=tempfile.mktemp(suffix=".json"))
    profile = ConstructProfile(target_tissue="cardiac")
    pg.add_construct(profile)
    stats = pg.get_stats()
    assert "constructs_analyzed" in stats
    assert "outcomes_tracked" in stats
    assert "predictions_made" in stats
    assert "prediction_accuracy" in stats
    assert "deals_linked" in stats
    assert "batches_tracked" in stats


def test_graph_export_and_reload():
    from core.process_graph import ProcessGraph
    tmp = tempfile.mktemp(suffix=".json")
    pg = ProcessGraph(graph_path=tmp)
    profile = ConstructProfile(target_tissue="cardiac", stiffness_kpa=10.0)
    cid = pg.add_construct(profile, run_id="test_construct_1")
    pg.add_outcome(cid, "viability", 90.0, "%")
    pg.export_to_json(tmp)

    pg2 = ProcessGraph(graph_path=tmp)
    assert pg2.graph.has_node("test_construct_1")
    stats = pg2.get_stats()
    assert stats["constructs_analyzed"] >= 1
    # Clean up
    Path(tmp).unlink(missing_ok=True)


def test_data_graph_json_exists():
    assert Path("data/process_graph.json").exists()
