"""Tests for TE/biofab reading database structure."""
import json
from pathlib import Path


def test_te_reading_json_loads():
    p = Path("data/knowledge/te_biofab_reading.json")
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert "collections" in data
    assert len(data["collections"]) > 0


def test_collections_have_required_fields():
    data = json.loads(Path("data/knowledge/te_biofab_reading.json").read_text(encoding="utf-8"))
    for coll in data["collections"]:
        assert "id" in coll
        assert "name" in coll
        assert "entries" in coll
        assert len(coll["entries"]) > 0


def test_entries_have_required_fields():
    data = json.loads(Path("data/knowledge/te_biofab_reading.json").read_text(encoding="utf-8"))
    for coll in data["collections"]:
        for entry in coll["entries"]:
            assert "id" in entry
            assert "type" in entry
            assert "title" in entry
            assert "topics" in entry
            assert isinstance(entry["topics"], list)
            assert len(entry["topics"]) > 0


def test_all_entries_have_unique_ids():
    data = json.loads(Path("data/knowledge/te_biofab_reading.json").read_text(encoding="utf-8"))
    ids = []
    for coll in data["collections"]:
        for entry in coll["entries"]:
            ids.append(entry["id"])
    assert len(ids) == len(set(ids)), "Duplicate entry IDs found"


def test_covers_key_collections():
    data = json.loads(Path("data/knowledge/te_biofab_reading.json").read_text(encoding="utf-8"))
    coll_ids = {c["id"] for c in data["collections"]}
    assert "foundations" in coll_ids
    assert "bioprinting" in coll_ids
    assert "organ_on_chip" in coll_ids
    assert "organoids" in coll_ids


def test_entries_have_valid_levels():
    data = json.loads(Path("data/knowledge/te_biofab_reading.json").read_text(encoding="utf-8"))
    valid_levels = {"foundational", "advanced", "cutting_edge"}
    for coll in data["collections"]:
        for entry in coll["entries"]:
            if "level" in entry:
                assert entry["level"] in valid_levels, f"Invalid level: {entry['level']}"


def test_minimum_entry_count():
    data = json.loads(Path("data/knowledge/te_biofab_reading.json").read_text(encoding="utf-8"))
    total = sum(len(c["entries"]) for c in data["collections"])
    assert total >= 20, f"Expected at least 20 entries, got {total}"
