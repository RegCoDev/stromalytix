"""
Knowledge Vault API Client for Stromalytix.

Hybrid BM25+vector search over PubMed abstracts and curated simulation
parameters, served by the Knowledge Vault sidecar (VAULT_API_URL).
"""

import os

VAULT_API_URL = os.environ.get("VAULT_API_URL", "").rstrip("/")
VAULT_API_KEY = os.environ.get("VAULT_API_KEY", "")


def _headers() -> dict:
    return {"X-API-Key": VAULT_API_KEY, "Content-Type": "application/json"}


def health() -> dict | None:
    """GET /health — public endpoint, no auth required."""
    if not VAULT_API_URL:
        return None
    import httpx
    try:
        resp = httpx.get(f"{VAULT_API_URL}/health", timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[knowledge_vault] health check failed: {e}")
        return None


def query(
    text: str,
    filters: dict | None = None,
    k: int = 10,
    include_parameters: bool = True,
    rerank: bool = False,
) -> dict | None:
    """POST /query — hybrid search over the vault."""
    if not VAULT_API_URL:
        return None
    import httpx
    try:
        payload: dict = {"text": text, "k": k, "include_parameters": include_parameters, "rerank": rerank}
        if filters:
            payload["filters"] = filters
        resp = httpx.post(f"{VAULT_API_URL}/query", json=payload, headers=_headers(), timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[knowledge_vault] query failed: {e}")
        return None


def get_paper(pmid: str) -> dict | None:
    """GET /paper/{pmid} — fetch a single paper by PMID."""
    if not VAULT_API_URL:
        return None
    import httpx
    try:
        resp = httpx.get(f"{VAULT_API_URL}/paper/{pmid}", headers=_headers(), timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[knowledge_vault] get_paper({pmid}) failed: {e}")
        return None


def explain(text: str, k: int = 15, rerank: bool = True) -> dict | None:
    """POST /explain — synthesis context with reranking."""
    if not VAULT_API_URL:
        return None
    import httpx
    try:
        payload = {"text": text, "k": k, "rerank": rerank}
        resp = httpx.post(f"{VAULT_API_URL}/explain", json=payload, headers=_headers(), timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[knowledge_vault] explain failed: {e}")
        return None
