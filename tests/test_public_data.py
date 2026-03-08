"""Tests for public data stubs and literature benchmarks."""
import json
from pathlib import Path


def test_literature_benchmarks_json_exists():
    p = Path("data/public/biofab/literature_benchmarks.json")
    assert p.exists()


def test_benchmarks_have_required_fields():
    data = json.loads(
        Path("data/public/biofab/literature_benchmarks.json").read_text()
    )
    assert "gelma_viability_benchmarks" in data
    for entry in data["gelma_viability_benchmarks"]:
        assert "material" in entry
        assert "cell_type" in entry
        assert "source_doi" in entry


def test_benchmarks_have_doi_provenance():
    data = json.loads(
        Path("data/public/biofab/literature_benchmarks.json").read_text()
    )
    for category in ["gelma_viability_benchmarks", "ooc_teer_benchmarks",
                      "spheroid_benchmarks", "bioprinting_benchmarks"]:
        for entry in data.get(category, []):
            assert "source_doi" in entry, f"Missing DOI in {category}"
            assert entry["source_doi"].startswith("10."), f"Invalid DOI: {entry['source_doi']}"


def test_minimum_benchmark_count():
    data = json.loads(
        Path("data/public/biofab/literature_benchmarks.json").read_text()
    )
    total = sum(len(v) for v in data.values() if isinstance(v, list))
    assert total >= 10


def test_dilirank_readme_exists():
    p = Path("data/public/hepatic/dilirank_README.txt")
    assert p.exists()
    content = p.read_text()
    assert "DILIrank" in content


def test_bpi_readme_exists():
    p = Path("data/public/process_mining/bpi2017_README.txt")
    assert p.exists()
    content = p.read_text()
    assert "BPI" in content
