"""Tests for APQC PCF biofabrication knowledge base structure."""
import json
from pathlib import Path


def test_apqc_json_loads():
    p = Path("data/knowledge/apqc_pcf_biofab.json")
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert "categories" in data
    assert len(data["categories"]) > 0


def test_apqc_categories_have_required_fields():
    data = json.loads(Path("data/knowledge/apqc_pcf_biofab.json").read_text(encoding="utf-8"))
    for cat in data["categories"]:
        assert "category_id" in cat
        assert "name" in cat
        assert "subcategories" in cat
        assert len(cat["subcategories"]) > 0


def test_apqc_process_elements_have_required_fields():
    data = json.loads(Path("data/knowledge/apqc_pcf_biofab.json").read_text(encoding="utf-8"))
    for cat in data["categories"]:
        for subcat in cat["subcategories"]:
            assert "id" in subcat
            assert "name" in subcat
            assert "process_elements" in subcat
            for pe in subcat["process_elements"]:
                assert "id" in pe
                assert "name" in pe
                assert "stromalytix_mapping" in pe
                assert "pi_signals" in pe
                assert isinstance(pe["pi_signals"], list)
                assert "best_practice_summary" in pe
                assert "key_metrics" in pe


def test_apqc_all_signals_are_strings():
    data = json.loads(Path("data/knowledge/apqc_pcf_biofab.json").read_text(encoding="utf-8"))
    for cat in data["categories"]:
        for subcat in cat["subcategories"]:
            for pe in subcat["process_elements"]:
                for signal in pe["pi_signals"]:
                    assert isinstance(signal, str)
                    assert len(signal) > 0


def test_apqc_covers_key_categories():
    data = json.loads(Path("data/knowledge/apqc_pcf_biofab.json").read_text(encoding="utf-8"))
    cat_ids = {c["category_id"] for c in data["categories"]}
    # Must have product dev, production, and quality
    assert "4.0" in cat_ids
    assert "5.0" in cat_ids


def test_apqc_no_duplicate_pe_ids():
    data = json.loads(Path("data/knowledge/apqc_pcf_biofab.json").read_text(encoding="utf-8"))
    pe_ids = []
    for cat in data["categories"]:
        for subcat in cat["subcategories"]:
            for pe in subcat["process_elements"]:
                pe_ids.append(pe["id"])
    assert len(pe_ids) == len(set(pe_ids)), "Duplicate process element IDs found"
