"""Tests for protocol document ingestion."""


def test_ingest_importable():
    from core.ingest import extract_text_from_pdf, extract_text_from_docx, parse_protocol_to_profile
    assert callable(extract_text_from_pdf)
    assert callable(extract_text_from_docx)
    assert callable(parse_protocol_to_profile)


def test_parse_finds_tissue_type():
    from core.ingest import _regex_extract
    result = _regex_extract("This protocol describes cardiac tissue engineering using GelMA scaffolds.")
    assert result["target_tissue"] == "cardiac"


def test_parse_finds_stiffness():
    from core.ingest import _regex_extract
    result = _regex_extract("The scaffold stiffness was measured at 4 kPa.")
    assert result["stiffness_kpa"] == 4.0


def test_extract_functions_callable():
    from core.ingest import extract_text_from_pdf, extract_text_from_docx
    assert callable(extract_text_from_pdf)
    assert callable(extract_text_from_docx)
