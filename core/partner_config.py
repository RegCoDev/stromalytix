"""
core/partner_config.py

Partner configuration loader.
Reads from partners/{partner_id}/config.json.

Usage:
    config = load_partner_config("demo")
    config = load_partner_config("cytoink")

Set STROMALYTIX_PARTNER env var to control which config loads.
Default: "demo"
"""

import json
import os
from pathlib import Path
from typing import Optional

PARTNERS_DIR = Path("partners")


def load_partner_config(partner_id: str = None) -> dict:
    """
    Load partner config from partners/{partner_id}/config.json.
    Falls back to demo config if partner_id not found.
    """
    if partner_id is None:
        partner_id = os.environ.get("STROMALYTIX_PARTNER", "demo")

    config_path = PARTNERS_DIR / partner_id / "config.json"

    if not config_path.exists():
        config_path = PARTNERS_DIR / "demo" / "config.json"

    with open(config_path) as f:
        config = json.load(f)

    config["_partner_id"] = partner_id
    config["_config_path"] = str(config_path)
    return config


def get_product_by_id(config: dict, product_id: str) -> Optional[dict]:
    """Get a product from config by its product_id."""
    products = config.get("products", [])
    if isinstance(products, list):
        return next((p for p in products if p["product_id"] == product_id), None)
    return None


def get_application_by_id(config: dict, app_id: str) -> Optional[dict]:
    """Get an application from config by its app_id."""
    apps = config.get("featured_applications", [])
    if isinstance(apps, list):
        return next((a for a in apps if a["app_id"] == app_id), None)
    return None
