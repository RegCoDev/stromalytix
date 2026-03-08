"""Tests for white-label PDF export."""
from pathlib import Path
from core.models import ConstructProfile, VarianceReport


def _make_report():
    profile = ConstructProfile(
        target_tissue="cardiac",
        cell_types=["cardiomyocytes"],
        stiffness_kpa=10.0,
        experimental_goal="disease_modeling",
    )
    return VarianceReport(
        construct_profile=profile,
        benchmark_ranges={"stiffness_kpa": {"min": 8, "max": 12, "unit": "kPa"}},
        deviation_scores={"stiffness_kpa": 0.0},
        risk_flags={"stiffness_kpa": "green"},
        ai_narrative="Test narrative for cardiac construct.",
        supporting_pmids=["12345678"],
        key_references=[{"pmid": "12345678", "title": "Test Paper", "year": "2023", "relevance_note": "Test"}],
    )


def test_pdf_has_cover_page():
    """PDF should have at least 2 pages (cover + content)."""
    from core.export import generate_pdf_report
    import fitz
    path = generate_pdf_report(_make_report())
    doc = fitz.open(path)
    assert doc.page_count >= 2
    doc.close()
    Path(path).unlink(missing_ok=True)


def test_pdf_has_executive_summary():
    """PDF should contain 'Executive Summary' text."""
    from core.export import generate_pdf_report
    import fitz
    path = generate_pdf_report(_make_report())
    doc = fitz.open(path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()
    assert "Executive Summary" in full_text
    Path(path).unlink(missing_ok=True)


def test_pdf_client_name():
    """Client name should appear in PDF when provided."""
    from core.export import generate_pdf_report
    import fitz
    path = generate_pdf_report(_make_report(), client_name="Cytoink")
    doc = fitz.open(path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()
    assert "Cytoink" in full_text
    Path(path).unlink(missing_ok=True)


def test_pdf_signature():
    """'stromalytix.com' should appear in the PDF."""
    from core.export import generate_pdf_report
    import fitz
    path = generate_pdf_report(_make_report())
    doc = fitz.open(path)
    last_page_text = doc[-1].get_text()
    doc.close()
    assert "stromalytix.com" in last_page_text
    Path(path).unlink(missing_ok=True)
