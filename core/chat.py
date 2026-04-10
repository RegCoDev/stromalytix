"""
Conversation logic for Stromalytix construct assessment.

Uses OpenRouter (OpenAI-compatible API) with free-tier models.
Falls back to Anthropic if ANTHROPIC_API_KEY is set.
No LangChain dependency — direct httpx calls.
"""

import json
import os
import re
from typing import Optional

import httpx
from dotenv import load_dotenv

from core.models import ConstructProfile

load_dotenv()

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

_OPENROUTER_MODELS = [
    "qwen/qwen3.6-plus-preview:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "qwen/qwen3-coder:free",
    "minimax/minimax-m2.5:free",
]


def _get_llm_config() -> dict:
    """Return config for the best available LLM."""
    def _secret(name):
        try:
            import streamlit as st
            return st.secrets.get(name)
        except Exception:
            return None

    anthropic_key = _secret("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        return {"api_key": anthropic_key, "model": "claude-haiku-4-5-20251001", "provider": "anthropic"}

    or_key = _secret("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if or_key:
        return {"api_key": or_key, "model": _OPENROUTER_MODELS[0], "provider": "openrouter"}

    return {}


def _chat_completion(messages: list[dict], max_tokens: int = 1024) -> str:
    """Call LLM via OpenAI-compatible API. Returns assistant text."""
    config = _get_llm_config()
    if not config:
        return "Chat unavailable — no LLM API key configured."

    if config["provider"] == "anthropic":
        return _anthropic_call(messages, config, max_tokens)

    # OpenRouter
    headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"}
    body = {"messages": messages, "max_tokens": max_tokens, "temperature": 0.7}

    for model in [config["model"]] + [m for m in _OPENROUTER_MODELS if m != config["model"]]:
        body["model"] = model
        try:
            resp = httpx.post("https://openrouter.ai/api/v1/chat/completions",
                              headers=headers, json=body, timeout=30.0)
            if resp.status_code == 429:
                continue
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception:
            continue

    return "All models are currently rate-limited. Please try again shortly."


def _anthropic_call(messages: list[dict], config: dict, max_tokens: int) -> str:
    """Direct Anthropic Messages API call."""
    system_text = ""
    api_messages = []
    for m in messages:
        if m["role"] == "system":
            system_text = m["content"]
        else:
            api_messages.append(m)

    body = {"model": config["model"], "max_tokens": max_tokens, "messages": api_messages}
    if system_text:
        body["system"] = system_text

    try:
        resp = httpx.post("https://api.anthropic.com/v1/messages",
                          headers={"x-api-key": config["api_key"],
                                   "anthropic-version": "2023-06-01",
                                   "content-type": "application/json"},
                          json=body, timeout=30.0)
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]
    except Exception as e:
        return f"LLM call failed: {e}"


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a Tissue Engineering Protocol Analyst for Stromalytix. Assess a researcher's 3D cell culture construct through a calm, professional conversation. Ask ONE question at a time.

RULES: No markdown headers, no emojis, no hype. Short paragraphs. Numbered lists only for options.

Collect: 1) Target tissue + goal 2) Cell types 3) Scaffold material + type 4) Stiffness + porosity 5) Culture format + dimensions 6) Cell density 7) Culture duration, media changes, O2 8) Primary readout

Suggest literature defaults when user is unsure. When complete, output JSON in <construct_profile> tags:
<construct_profile>
{"target_tissue":"string","cell_types":["string"],"scaffold_material":"string","stiffness_kpa":10.0,"porosity_percent":75.0,"cell_density_per_ml":5e6,"experimental_goal":"string","primary_readout":"string","scaffold_type":"degradable","biofab_method":"bioprinting","scaffold_dimensions_mm":[4,4,2],"pore_size_um":300,"culture_duration_days":14,"media_change_interval_hours":48,"medium_volume_ml":2,"oxygen_tension_percent":20,"culture_format":"wellplate"}
</construct_profile>
Single numbers only (midpoint if range). scaffold_type: degradable/rigid/hybrid."""

CELLAG_SYSTEM_PROMPT = """You are a Cellular Agriculture Protocol Analyst for Stromalytix. Assess a cultivated meat / structured protein construct. Ask ONE question at a time.

RULES: No markdown headers, no emojis, no hype. Plain professional tone.

CRITICAL: Cell ag uses animal cells (bovine, porcine, avian, piscine) where literature is thinner than human cell biology. When suggesting parameters:
- State when extrapolating from human data to animal systems
- Note species-specific differences (e.g. bovine satellite cell proliferation kinetics differ from human myoblasts)
- Reference veterinary and animal science literature where available
- Flag parameters well-characterized in human TE but unvalidated in the target species

Collect: 1) Target product + goal 2) Cell types (species + lineage) 3) Scaffold (food-grade/edible) 4) Stiffness, porosity, seeding method 5) Culture format + dimensions 6) Cell density 7) Duration, media, O2, serum-free status 8) Readout (myotube alignment, protein/g, texture)

Also probe: serum-free medium, differentiation protocol, muscle+fat co-culture, scale-up path.

When complete, output JSON in <construct_profile> tags:
<construct_profile>
{"application_domain":"cellular_agriculture","target_tissue":"bovine_muscle","cell_types":["bovine satellite cells"],"scaffold_material":"string","stiffness_kpa":10.0,"porosity_percent":75.0,"cell_density_per_ml":5e6,"experimental_goal":"structured_whole_cut","primary_readout":"string","scaffold_type":"degradable","biofab_method":"bioreactor","scaffold_dimensions_mm":[10,10,5],"pore_size_um":200,"culture_duration_days":21,"media_change_interval_hours":48,"medium_volume_ml":5,"oxygen_tension_percent":20,"culture_format":"bioreactor"}
</construct_profile>
Single numbers only. scaffold_type: degradable/rigid/hybrid."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ChatSession:
    """Lightweight chat session holding message history."""

    def __init__(self, domain: str = "tissue_engineering"):
        prompt = CELLAG_SYSTEM_PROMPT if domain == "cellular_agriculture" else SYSTEM_PROMPT
        self.messages: list[dict] = [{"role": "system", "content": prompt}]

    def send(self, user_input: str) -> str:
        from core.rag import sanitize_input
        sanitized = sanitize_input(user_input)
        if sanitized == "I can only help with tissue engineering protocol analysis.":
            return sanitized
        self.messages.append({"role": "user", "content": sanitized})
        response = _chat_completion(self.messages, max_tokens=1024)
        self.messages.append({"role": "assistant", "content": response})
        return response

    def get_history_text(self) -> str:
        return "\n".join(f"{m['role'].upper()}: {m['content']}" for m in self.messages if m["role"] != "system")


def initialize_chat(domain: str = "tissue_engineering") -> ChatSession:
    session = ChatSession(domain)
    greeting = _chat_completion(
        session.messages + [{"role": "user", "content": "Introduce yourself in one sentence and ask the first question."}],
        max_tokens=256,
    )
    session.messages.append({"role": "user", "content": "(start)"})
    session.messages.append({"role": "assistant", "content": greeting})
    return session


def send_message(session, user_input: str) -> str:
    return session.send(user_input)


# ---------------------------------------------------------------------------
# Profile extraction
# ---------------------------------------------------------------------------

def clean_numeric_fields(d: dict) -> dict:
    for field in ['stiffness_kpa', 'porosity_percent', 'cell_density_per_ml',
                  'pore_size_um', 'culture_duration_days', 'media_change_interval_hours',
                  'medium_volume_ml', 'oxygen_tension_percent']:
        if field in d and isinstance(d[field], str):
            v = d[field].strip().replace('%', '')
            if '-' in v:
                try:
                    parts = v.split('-')
                    d[field] = (float(parts[0]) + float(parts[1])) / 2
                except ValueError:
                    pass
            else:
                try:
                    d[field] = float(v)
                except ValueError:
                    pass
    return d


def extract_construct_profile(conversation_history: str) -> Optional[ConstructProfile]:
    match = re.search(r"<construct_profile>(.*?)</construct_profile>", conversation_history, re.DOTALL)
    if not match:
        return None
    try:
        return ConstructProfile(**clean_numeric_fields(json.loads(match.group(1).strip())))
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Warning: profile parse failed: {e}")
        return None


def extract_partial_profile(conversation_history: str) -> Optional[ConstructProfile]:
    params = {}
    text_lower = conversation_history.lower()

    for tissue in ["cardiac", "liver", "hepatic", "neural", "brain", "lung", "kidney",
                   "intestinal", "bone", "cartilage", "skin", "tumor", "vascular",
                   "pancreatic", "bovine_muscle", "chicken_breast", "pork", "fish",
                   "cultivated meat", "cultured meat"]:
        if tissue in text_lower:
            params["target_tissue"] = tissue
            break

    if any(cue in text_lower for cue in ["cultivated meat", "cultured meat", "cellular agriculture",
                                          "cell ag", "satellite cell", "myoblast", "bovine satellite"]):
        params["application_domain"] = "cellular_agriculture"

    for mat in ["GelMA", "collagen", "alginate", "fibrin", "PEGDA", "hyaluronic acid",
                "Matrigel", "silk", "PDMS", "textured soy protein", "cellulose",
                "chitosan", "starch", "zein", "konjac", "plant protein"]:
        if mat.lower() in text_lower:
            params["scaffold_material"] = mat
            break

    m = re.search(r"(\d+\.?\d*)\s*kPa", conversation_history)
    if m:
        params["stiffness_kpa"] = float(m.group(1))

    m = re.search(r"(\d+\.?\d*)\s*(?:x\s*10\^?6|million|M)\s*(?:cells?)?(?:/mL)?", conversation_history, re.I)
    if m:
        params["cell_density_per_ml"] = float(m.group(1)) * 1e6

    found = [c for c in ["cardiomyocytes", "fibroblasts", "HUVEC", "HepG2", "iPSC", "MSC",
                          "chondrocytes", "osteoblasts", "C2C12", "satellite cells", "myoblasts",
                          "bovine satellite cells", "chicken myoblasts", "preadipocytes"]
             if c.lower() in text_lower]
    if found:
        params["cell_types"] = found

    return ConstructProfile(**params) if params else None
