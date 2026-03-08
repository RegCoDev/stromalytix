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


def test_nmp_vittal_json_exists_and_valid():
    p = Path("data/public/transplant/nmp_vittal_summary.json")
    assert p.exists()
    data = json.loads(p.read_text())
    assert data["doi"] == "10.1038/s41586-018-0047-9"
    assert "nmp_arm_summary" in data
    assert data["nmp_arm_summary"]["ead_rate_nmp"] < data["nmp_arm_summary"]["ead_rate_cold_storage"]


def test_nmp_pilot_criteria_json_exists_and_valid():
    p = Path("data/public/transplant/nmp_pilot_criteria.json")
    assert p.exists()
    data = json.loads(p.read_text())
    assert data["doi"] == "10.1038/s41591-020-1134-x"
    assert "viability_criteria" in data
    assert len(data["viability_criteria"]["mandatory"]) >= 3
    assert len(data["viability_criteria"]["supporting"]) >= 2


def test_transplant_datasets_readme_exists():
    p = Path("data/public/transplant/DATASETS_README.txt")
    assert p.exists()
    content = p.read_text()
    assert "UNOS" in content or "SRTR" in content
