"""Tests for partner PDF report generation."""

import os
from pathlib import Path

from core.export import generate_partner_report_pdf
from core.materials_intelligence import BioinkLotCharacterization, predict_lot_performance
from core.partner_config import load_partner_config, get_product_by_id, get_application_by_id


def _make_demo_report():
    """Helper: generate a LotIntelligenceReport from demo config."""
    config = load_partner_config("demo")
    product = get_product_by_id(config, "gelma_6pct")
    rheology = product["default_rheology"]
    char = BioinkLotCharacterization(
        lot_id="gelma_6pct_pdf_test",
        material_name=product["display_name"],
        storage_modulus_pa=rheology["storage_modulus_pa"],
        viscosity_pas_at_37c=rheology["viscosity_pas_at_37c"],
        gelation_time_s=rheology["gelation_time_s"],
        swelling_ratio=rheology["swelling_ratio"],
        uv_dose_mwcm2_s=rheology["uv_dose_mwcm2_s"],
        cell_types=["hepg2"],
    )
    return predict_lot_performance(char), config, product


def test_generate_partner_pdf_creates_file():
    report, config, product = _make_demo_report()
    app = get_application_by_id(config, "hepatic")
    pdf_path = generate_partner_report_pdf(
        report=report,
        config=config,
        product=product,
        application=app,
        cell_type="HepG2",
    )
    assert Path(pdf_path).exists()
    assert pdf_path.endswith(".pdf")
    assert "demo" in pdf_path
    # Cleanup
    os.remove(pdf_path)


def test_partner_pdf_contains_partner_branding():
    """PDF filename includes partner_id."""
    report, config, product = _make_demo_report()
    app = get_application_by_id(config, "hepatic")
    pdf_path = generate_partner_report_pdf(
        report=report,
        config=config,
        product=product,
        application=app,
    )
    assert "demo_report_gelma_6pct" in pdf_path
    os.remove(pdf_path)


def test_cytoink_pdf_generation():
    """Generate a PDF for cytoink partner."""
    config = load_partner_config("cytoink")
    product = get_product_by_id(config, "gelma_porcine_6pct")
    app = get_application_by_id(config, "hepatic")
    rheology = product["default_rheology"]
    char = BioinkLotCharacterization(
        lot_id="cytoink_pdf_test",
        material_name=product["display_name"],
        storage_modulus_pa=rheology["storage_modulus_pa"],
        viscosity_pas_at_37c=rheology["viscosity_pas_at_37c"],
        gelation_time_s=rheology["gelation_time_s"],
        swelling_ratio=rheology["swelling_ratio"],
        cell_types=["default"],
    )
    report = predict_lot_performance(char)
    pdf_path = generate_partner_report_pdf(
        report=report,
        config=config,
        product=product,
        application=app,
        cell_type="HepG2",
    )
    assert Path(pdf_path).exists()
    assert "cytoink" in pdf_path
    os.remove(pdf_path)
