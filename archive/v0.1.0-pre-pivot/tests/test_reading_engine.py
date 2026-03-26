"""Tests for ReadingEngine — context-driven reading recommendations."""
from types import SimpleNamespace

from core.reading_engine import ReadingEngine


def test_reading_engine_importable():
    from core.reading_engine import ReadingEngine
    assert ReadingEngine is not None


def test_loads_apqc_and_te_data():
    engine = ReadingEngine()
    assert len(engine.apqc.get("categories", [])) > 0
    assert len(engine.te_reading.get("collections", [])) > 0


def test_signal_index_built():
    engine = ReadingEngine()
    assert len(engine._signal_index) > 0
    assert "parameter_out_of_range" in engine._signal_index


def test_topic_index_built():
    engine = ReadingEngine()
    assert len(engine._topic_index) > 0
    assert "bioprinting" in engine._topic_index


def test_business_track_returns_results_for_known_signal():
    engine = ReadingEngine()
    results = engine.get_business_reading(["parameter_out_of_range"])
    assert len(results) > 0
    assert results[0]["pcf_id"] == "4.1.1"
    assert "triggered_by" in results[0]
    assert "parameter_out_of_range" in results[0]["triggered_by"]


def test_business_track_multiple_signals_boost_relevance():
    engine = ReadingEngine()
    # protocol_deviation and conformance_failure both map to 5.4.1
    results = engine.get_business_reading(["protocol_deviation", "conformance_failure"])
    hit = [r for r in results if r["pcf_id"] == "5.4.1"]
    assert len(hit) == 1
    assert hit[0]["relevance_score"] > 1.0  # boosted by second signal


def test_scientific_track_returns_bioprinting_for_bioprinting_method():
    engine = ReadingEngine()
    profile = SimpleNamespace(biofab_method="bioprinting", target_tissue="", scaffold_material="")
    results = engine.get_scientific_reading(profile=profile)
    assert len(results) > 0
    collections = {r["collection"] for r in results}
    assert "Bioprinting" in collections


def test_scientific_track_includes_foundations():
    engine = ReadingEngine()
    profile = SimpleNamespace(biofab_method="organoid", target_tissue="", scaffold_material="")
    results = engine.get_scientific_reading(profile=profile)
    collections = {r["collection"] for r in results}
    assert "Tissue Engineering Foundations" in collections


def test_scientific_track_keyword_matching():
    engine = ReadingEngine()
    profile = SimpleNamespace(biofab_method=None, target_tissue="vascular", scaffold_material="GelMA")
    results = engine.get_scientific_reading(profile=profile)
    assert len(results) > 0
    all_reasons = []
    for r in results:
        all_reasons.extend(r["match_reasons"])
    assert any("vascular" in reason for reason in all_reasons)
    assert any("gelma" in reason for reason in all_reasons)


def test_scientific_track_level_filter():
    engine = ReadingEngine()
    profile = SimpleNamespace(biofab_method="bioprinting", target_tissue="", scaffold_material="")
    results = engine.get_scientific_reading(profile=profile, level_filter=["foundational"])
    for r in results:
        assert r["entry"].get("level") == "foundational"


def test_contextual_reading_returns_both_tracks():
    engine = ReadingEngine()
    profile = SimpleNamespace(biofab_method="bioprinting", target_tissue="cardiac", scaffold_material="GelMA")
    result = engine.get_contextual_reading(
        profile=profile,
        pi_signals=["parameter_out_of_range", "high_cv"],
    )
    assert "business_track" in result
    assert "scientific_track" in result
    assert "context_summary" in result
    assert result["total_results"] > 0
    assert len(result["business_track"]) > 0
    assert len(result["scientific_track"]) > 0


def test_search_returns_results_for_keyword():
    engine = ReadingEngine()
    results = engine.search("bioprinting")
    assert len(results) > 0
    tracks = {r["track"] for r in results}
    assert "scientific" in tracks


def test_search_finds_business_track():
    engine = ReadingEngine()
    results = engine.search("quality")
    biz = [r for r in results if r["track"] == "business"]
    assert len(biz) > 0


def test_empty_signals_returns_gracefully():
    engine = ReadingEngine()
    biz = engine.get_business_reading([])
    assert biz == []
    biz2 = engine.get_business_reading(None)
    assert biz2 == []


def test_empty_profile_returns_foundations():
    engine = ReadingEngine()
    results = engine.get_scientific_reading()
    assert len(results) > 0
    # Should still get foundations
    collections = {r["collection"] for r in results}
    assert "Tissue Engineering Foundations" in collections
