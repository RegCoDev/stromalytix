"""Tests for partner_app.py — partner intake form."""

from core.partner_config import load_partner_config, get_product_by_id
from core.materials_intelligence import BioinkLotCharacterization, predict_lot_performance


def test_partner_app_imports():
    """partner_app.py can be imported without error."""
    import partner_app
    assert hasattr(partner_app, "main")


def test_demo_product_lot_prediction():
    """Predict lot performance using demo GelMA 6% defaults."""
    config = load_partner_config("demo")
    product = get_product_by_id(config, "gelma_6pct")
    assert product is not None

    rheology = product["default_rheology"]
    char = BioinkLotCharacterization(
        lot_id="gelma_6pct_test",
        material_name=product["display_name"],
        storage_modulus_pa=rheology["storage_modulus_pa"],
        viscosity_pas_at_37c=rheology["viscosity_pas_at_37c"],
        gelation_time_s=rheology["gelation_time_s"],
        swelling_ratio=rheology["swelling_ratio"],
        uv_dose_mwcm2_s=rheology["uv_dose_mwcm2_s"],
        degradation_rate_day=rheology["degradation_rate_day"],
        cell_types=["hepg2"],
    )
    report = predict_lot_performance(char)

    assert report.predicted_stiffness_kpa > 0
    assert report.predicted_printability_score > 0
    assert report.predicted_cell_viability_day3_pct > 0
    assert report.release_recommendation in ("RELEASE", "CONDITIONAL", "HOLD")
    assert report.confidence in ("high", "medium", "low")


def test_cytoink_product_lot_prediction():
    """Predict lot performance using cytoink porcine 6%."""
    config = load_partner_config("cytoink")
    product = get_product_by_id(config, "gelma_porcine_6pct")
    assert product is not None

    rheology = product["default_rheology"]
    char = BioinkLotCharacterization(
        lot_id="gelma_porcine_6pct_test",
        material_name=product["display_name"],
        storage_modulus_pa=rheology["storage_modulus_pa"],
        viscosity_pas_at_37c=rheology["viscosity_pas_at_37c"],
        gelation_time_s=rheology["gelation_time_s"],
        swelling_ratio=rheology["swelling_ratio"],
        cell_types=["default"],
    )
    report = predict_lot_performance(char)

    assert report.predicted_stiffness_kpa > 0
    assert report.release_recommendation in ("RELEASE", "CONDITIONAL", "HOLD")


def test_available_products_filter():
    """Filtering out training-only and unavailable products works."""
    config = load_partner_config("cytoink")
    products = config.get("products", [])
    available = [
        p for p in products
        if not p.get("training_only") and p.get("available", True)
    ]
    # Cytoink has 10 products, 2 training + 1 unavailable = 7 available
    assert len(available) == 7
    # Training products excluded
    for p in available:
        assert not p.get("training_only")
    # Unavailable products excluded
    for p in available:
        assert p.get("available", True) is not False
