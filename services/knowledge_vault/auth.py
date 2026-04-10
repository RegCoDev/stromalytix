"""
Knowledge Vault — shared API key authentication dependency.

Extracted into its own module to avoid circular imports between
main.py and API routers.
"""

import os

from fastapi import Header, HTTPException

STROMALYTIX_API_KEY = os.environ.get("STROMALYTIX_API_KEY", "dev-key-change-me")


def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != STROMALYTIX_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key
