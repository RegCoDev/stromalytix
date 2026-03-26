"""Tests for partner config system."""
from unittest.mock import patch

from core.partner_config import (
    load_partner_config,
    get_product_by_id,
    get_application_by_id,
)


def test_load_demo_config_returns_dict():
    config = load_partner_config("demo")
    assert isinstance(config, dict)
    assert config["partner_id"] == "demo"


def test_load_cytoink_config_returns_dict():
    config = load_partner_config("cytoink")
    assert isinstance(config, dict)
    assert config["partner_id"] == "cytoink"


def test_fallback_to_demo_when_unknown_partner():
    config = load_partner_config("nonexistent_partner_xyz")
    assert config["partner_id"] == "demo"


def test_get_product_by_id_returns_correct_product():
    config = load_partner_config("demo")
    product = get_product_by_id(config, "gelma_6pct")
    assert product is not None
    assert product["display_name"] == "GelMA 6%"
    assert product["default_rheology"]["storage_modulus_pa"] == 7500


def test_get_product_by_id_returns_none_for_missing():
    config = load_partner_config("demo")
    assert get_product_by_id(config, "nonexistent") is None


def test_get_application_by_id_returns_correct_app():
    config = load_partner_config("demo")
    app = get_application_by_id(config, "hepatic")
    assert app is not None
    assert "HepG2" in app["default_cell_types"]


def test_demo_config_has_required_fields():
    config = load_partner_config("demo")
    assert "partner_name" in config
    assert "products" in config
    assert "featured_applications" in config
    assert "brand_colors" in config
    assert "powered_by" in config
    assert len(config["products"]) >= 5
    assert len(config["featured_applications"]) >= 5


def test_cytoink_config_has_required_fields():
    config = load_partner_config("cytoink")
    assert "partner_name" in config
    assert len(config["products"]) >= 8
    assert "dlp" in config.get("supported_modalities", [])


def test_env_var_controls_partner_selection():
    with patch.dict("os.environ", {"STROMALYTIX_PARTNER": "cytoink"}):
        config = load_partner_config()
        assert config["partner_id"] == "cytoink"


def test_cytoink_has_training_products():
    config = load_partner_config("cytoink")
    training = [p for p in config["products"] if p.get("training_only")]
    assert len(training) >= 2


def test_cytoink_fish_gelma_is_dlp_only():
    config = load_partner_config("cytoink")
    fish = get_product_by_id(config, "gelma_fish_4pct")
    assert fish is not None
    assert fish.get("modalities") == ["dlp"]
