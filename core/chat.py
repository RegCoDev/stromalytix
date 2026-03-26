"""
Conversation Chain Logic for Stromalytix

Handles interactive chat assessment to collect construct parameters.
"""

import json
import os
import re
from typing import Optional

from dotenv import load_dotenv
from langchain_classic.chains import ConversationChain
from langchain_classic.memory import ConversationBufferMemory
from langchain_anthropic import ChatAnthropic

from core.models import ConstructProfile

# Load environment variables
load_dotenv()

# Verify Anthropic API key — check env vars and Streamlit secrets
_api_key = os.getenv("ANTHROPIC_API_KEY")
if not _api_key:
    try:
        import streamlit as st
        _api_key = st.secrets.get("ANTHROPIC_API_KEY")
        if _api_key:
            os.environ["ANTHROPIC_API_KEY"] = _api_key
    except Exception:
        pass
if not _api_key:
    import warnings
    warnings.warn("ANTHROPIC_API_KEY not set — chat features will be unavailable")

# System prompt for construct assessment
SYSTEM_PROMPT = """You are a Tissue Engineering Protocol Analyst for Stromalytix. Assess a researcher's 3D cell culture construct through a calm, professional conversation. Ask ONE question at a time, grouping related questions naturally.

FORMATTING RULES — follow these strictly:
- Do NOT use markdown headers (# or ##). Use plain text or bold (**text**) for emphasis.
- Do NOT use emojis.
- Keep a professional, measured tone. No hype, no exclamation marks, no cheerleading.
- Write in short paragraphs. Use numbered lists only when listing options.

Collect these parameters (in roughly this order):

1. Target tissue and experimental goal
2. Cell types (primary, support)
3. Scaffold material and type (degradable / rigid / hybrid)
4. Scaffold stiffness (kPa) and porosity (%)
5. Culture format (wellplate, transwell, bioreactor, bioprinter) and construct dimensions (mm)
6. Cell seeding density
7. Culture duration (days), media change interval (hours), medium volume (mL), O2 tension (%)
8. Primary readout

If the user doesn't know a value, suggest a reasonable default from literature and confirm.

IMPORTANT: When you have all parameters, output a JSON block wrapped in <construct_profile> tags. Use this EXACT format with SINGLE NUMERIC VALUES (not ranges):

<construct_profile>
{
  "target_tissue": "string",
  "cell_types": ["string1", "string2"],
  "scaffold_material": "string",
  "stiffness_kpa": 10.0,
  "porosity_percent": 75.0,
  "cell_density_per_ml": 5000000.0,
  "experimental_goal": "string",
  "primary_readout": "string",
  "scaffold_type": "degradable",
  "biofab_method": "bioprinting",
  "scaffold_dimensions_mm": [4.0, 4.0, 2.0],
  "pore_size_um": 300.0,
  "culture_duration_days": 14,
  "media_change_interval_hours": 48.0,
  "medium_volume_ml": 2.0,
  "oxygen_tension_percent": 20.0,
  "culture_format": "wellplate"
}
</construct_profile>

For numeric fields, output ONLY single numbers (e.g., 75.0, not "70-80%"). If given a range, output the midpoint.
scaffold_type must be one of: "degradable", "rigid", "hybrid".
culture_format should be one of: "wellplate", "transwell", "bioreactor", "bioprinter", "microfluidic", "other"."""

CELLAG_SYSTEM_PROMPT = """You are a Cellular Agriculture Protocol Analyst for Stromalytix. Assess a researcher's cultivated meat / structured protein construct through a calm, professional conversation. Ask ONE question at a time, grouping related questions naturally.

FORMATTING RULES — follow these strictly:
- Do NOT use markdown headers (# or ##). Use plain text or bold (**text**) for emphasis.
- Do NOT use emojis.
- Keep a professional, measured tone. No hype, no exclamation marks, no cheerleading.
- Write in short paragraphs. Use numbered lists only when listing options.

You are working in the context of cellular agriculture — growing animal-derived cells (muscle, fat, connective tissue) on edible scaffolds for food production, NOT for therapeutic use.

Collect these parameters (in roughly this order):

1. Target product (cultivated beef, chicken, pork, fish, fat tissue, hybrid) and production goal (structured whole-cut, minced, fat marbling, proof-of-concept)
2. Cell types — species and lineage (e.g. bovine satellite cells, chicken myoblasts, porcine adipocytes, C2C12 as model line)
3. Scaffold material — must be food-grade/edible (e.g. textured soy protein, cellulose, chitosan, starch, plant-derived protein, decellularized plant tissue, edible GelMA, alginate, konjac). Note whether it is edible.
4. Scaffold stiffness (kPa), porosity (%), and whether the scaffold is designed for surface seeding or bulk infiltration
5. Culture format (spinner flask, packed-bed bioreactor, hollow-fibre, perfusion bioreactor, wellplate for R&D) and construct dimensions (mm)
6. Cell seeding density
7. Culture duration (days), media change interval (hours), medium volume (mL), O2 tension (%), and whether the medium is serum-free
8. Primary readout (myotube alignment, protein content per gram, lipid accumulation, texture analysis, cell viability)

Cell-ag-specific considerations to probe:
- Serum-free medium composition (growth factors: FGF-2, IGF-1, TGF-beta for differentiation)
- Differentiation protocol (proliferation phase, then differentiation phase, then maturation)
- Whether the user plans to co-culture muscle + fat cells
- Scale-up path (from wellplate to bioreactor)

If the user doesn't know a value, suggest a reasonable default from literature and confirm.

IMPORTANT: When you have all parameters, output a JSON block wrapped in <construct_profile> tags. Use this EXACT format with SINGLE NUMERIC VALUES (not ranges):

<construct_profile>
{
  "application_domain": "cellular_agriculture",
  "target_tissue": "string (e.g. bovine_muscle, chicken_breast, pork_fat)",
  "cell_types": ["bovine satellite cells", "preadipocytes"],
  "scaffold_material": "string",
  "stiffness_kpa": 10.0,
  "porosity_percent": 75.0,
  "cell_density_per_ml": 5000000.0,
  "experimental_goal": "string (e.g. structured_whole_cut, minced_product, fat_marbling, proof_of_concept)",
  "primary_readout": "string",
  "scaffold_type": "degradable",
  "biofab_method": "bioprinting",
  "scaffold_dimensions_mm": [10.0, 10.0, 5.0],
  "pore_size_um": 200.0,
  "culture_duration_days": 21,
  "media_change_interval_hours": 48.0,
  "medium_volume_ml": 5.0,
  "oxygen_tension_percent": 20.0,
  "culture_format": "bioreactor"
}
</construct_profile>

For numeric fields, output ONLY single numbers (e.g., 75.0, not "70-80%"). If given a range, output the midpoint.
scaffold_type must be one of: "degradable", "rigid", "hybrid".
culture_format should be one of: "wellplate", "transwell", "bioreactor", "bioprinter", "microfluidic", "other"."""


def initialize_chat(domain: str = "tissue_engineering") -> ConversationChain:
    """
    Initialize a conversation chain with Haiku and buffer memory.

    Args:
        domain: "tissue_engineering" or "cellular_agriculture"

    Returns:
        ConversationChain configured for construct assessment
    """
    prompt = CELLAG_SYSTEM_PROMPT if domain == "cellular_agriculture" else SYSTEM_PROMPT

    llm = ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        temperature=0.7,
        max_tokens=2048,
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )

    memory = ConversationBufferMemory(
        return_messages=True,
        memory_key="history"
    )

    chain = ConversationChain(
        llm=llm,
        memory=memory,
        verbose=False
    )

    greeting_cue = (
        "Introduce yourself briefly (one sentence) and ask the first question. "
        "No emojis, no markdown headers, no hype. Plain professional tone."
    )
    chain.predict(input=f"SYSTEM: {prompt}\n\n{greeting_cue}")

    return chain


def _clean_response(response) -> str:
    """Extract clean text from an LLM response, stripping AIMessage metadata."""
    # AIMessage object
    if hasattr(response, "content"):
        text = response.content
    else:
        text = str(response)

    # If str() of an AIMessage leaked metadata, extract just the content
    if "additional_kwargs=" in text or "response_metadata=" in text:
        match = re.search(r"content=['\"](.+?)['\"](?:\s+additional_kwargs=)", text, re.DOTALL)
        if match:
            text = match.group(1)
        else:
            # Fallback: strip everything after "additional_kwargs="
            idx = text.find("additional_kwargs=")
            if idx > 0:
                text = text[:idx].strip()
            # Remove leading "content=" wrapper if present
            if text.startswith("content='") or text.startswith('content="'):
                text = text[9:]
                if text.endswith("'") or text.endswith('"'):
                    text = text[:-1]

    # Fix escaped newlines that came from repr()
    text = text.replace("\\n", "\n")

    return text.strip()


def send_message(chain: ConversationChain, user_input: str) -> str:
    """
    Send a user message to the conversation chain and get response.

    Sanitizes input to prevent prompt injection before sending to LLM.
    """
    from core.rag import sanitize_input

    sanitized_input = sanitize_input(user_input)

    if sanitized_input == "I can only help with tissue engineering protocol analysis.":
        return sanitized_input

    response = chain.predict(input=sanitized_input)
    return _clean_response(response)


def clean_numeric_fields(profile_dict: dict) -> dict:
    """
    Clean numeric fields that might contain string ranges like '80-95%' or '5-10'.
    Converts to midpoint float.
    """
    numeric_fields = [
        'stiffness_kpa', 'porosity_percent', 'cell_density_per_ml',
        'pore_size_um', 'culture_duration_days', 'media_change_interval_hours',
        'medium_volume_ml', 'oxygen_tension_percent',
    ]
    for field in numeric_fields:
        if field in profile_dict and isinstance(profile_dict[field], str):
            value_str = profile_dict[field].strip()
            # Remove % symbol
            value_str = value_str.replace('%', '').strip()

            # Check if it's a range like "5-10" or "80-95"
            if '-' in value_str:
                try:
                    parts = value_str.split('-')
                    if len(parts) == 2:
                        low = float(parts[0].strip())
                        high = float(parts[1].strip())
                        profile_dict[field] = (low + high) / 2  # Use midpoint
                        print(f"[CLEAN] Converted {field} range '{value_str}' to midpoint: {profile_dict[field]}")
                except ValueError:
                    pass  # Leave as-is if can't parse
            else:
                # Try to convert single value
                try:
                    profile_dict[field] = float(value_str)
                    print(f"[CLEAN] Converted {field} string '{value_str}' to float: {profile_dict[field]}")
                except ValueError:
                    pass  # Leave as-is if can't parse

    return profile_dict


def extract_construct_profile(conversation_history: str) -> Optional[ConstructProfile]:
    """
    Extract ConstructProfile from conversation history.

    ONLY extracts when the <construct_profile> tag is explicitly present.
    This ensures the assistant has completed the assessment before extraction.

    Args:
        conversation_history: Full conversation text

    Returns:
        ConstructProfile if <construct_profile> tag found and valid, None otherwise
    """
    # Try to find <construct_profile> tags - REQUIRED for extraction
    pattern = r"<construct_profile>(.*?)</construct_profile>"
    match = re.search(pattern, conversation_history, re.DOTALL)

    if not match:
        # No explicit completion signal - return None
        return None

    # Parse the tagged JSON
    try:
        json_str = match.group(1).strip()
        profile_dict = json.loads(json_str)

        # Clean numeric fields that might be string ranges
        profile_dict = clean_numeric_fields(profile_dict)

        return ConstructProfile(**profile_dict)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Warning: Failed to parse construct_profile JSON: {e}")
        return None


def extract_partial_profile(conversation_history: str) -> Optional[ConstructProfile]:
    """
    Extract partially confirmed parameters from chat history.
    Scans conversation for confirmed parameter values before
    the full profile is complete.

    Used for live visualization preview during BioSim chat.
    """
    params = {}

    # Tissue type patterns (includes cell-ag targets)
    tissue_patterns = [
        "cardiac", "liver", "hepatic", "neural", "brain", "lung",
        "kidney", "intestinal", "bone", "cartilage", "skin",
        "tumor", "vascular", "pancreatic",
        "bovine_muscle", "chicken_breast", "pork", "fish",
        "cultivated meat", "cultured meat",
    ]
    text_lower = conversation_history.lower()
    for tissue in tissue_patterns:
        if tissue in text_lower:
            params["target_tissue"] = tissue
            break

    # Cell-ag domain detection
    cellag_cues = ["cultivated meat", "cultured meat", "cellular agriculture",
                   "cell ag", "satellite cell", "myoblast", "myotube",
                   "bovine satellite", "chicken myoblast"]
    if any(cue in text_lower for cue in cellag_cues):
        params["application_domain"] = "cellular_agriculture"

    # Scaffold material (includes cell-ag edible scaffolds)
    materials = [
        "GelMA", "collagen", "alginate", "fibrin", "PEGDA",
        "hyaluronic acid", "Matrigel", "silk", "PDMS",
        "textured soy protein", "cellulose", "chitosan", "starch",
        "zein", "konjac", "plant protein", "decellularized plant",
    ]
    for mat in materials:
        if mat.lower() in text_lower:
            params["scaffold_material"] = mat
            break

    # Stiffness
    stiffness_match = re.search(r"(\d+\.?\d*)\s*kPa", conversation_history)
    if stiffness_match:
        params["stiffness_kpa"] = float(stiffness_match.group(1))

    # Cell density
    density_match = re.search(
        r"(\d+\.?\d*)\s*(?:x\s*10\^?6|million|M)\s*(?:cells?)?(?:/mL|/ml)?",
        conversation_history, re.IGNORECASE
    )
    if density_match:
        params["cell_density_per_ml"] = float(density_match.group(1)) * 1e6

    # Cell types (includes cell-ag lineages)
    cell_patterns = [
        "cardiomyocytes", "fibroblasts", "HUVEC", "HepG2", "MCF-7",
        "iPSC", "neurons", "astrocytes", "Caco-2", "A549",
        "MSC", "chondrocytes", "osteoblasts", "keratinocytes",
        "C2C12", "satellite cells", "myoblasts", "myotubes",
        "preadipocytes", "adipocytes", "bovine satellite cells",
        "chicken myoblasts", "porcine satellite cells",
    ]
    found_cells = [c for c in cell_patterns if c.lower() in text_lower]
    if found_cells:
        params["cell_types"] = found_cells

    # Culture format
    format_patterns = {
        "wellplate": ["wellplate", "well plate", "well-plate", "96-well", "24-well", "6-well"],
        "bioreactor": ["bioreactor", "spinner flask", "perfusion"],
        "transwell": ["transwell", "trans-well", "insert"],
        "bioprinter": ["bioprint", "bio-print", "extrusion"],
        "microfluidic": ["microfluidic", "organ-on-chip", "organ on chip"],
    }
    for fmt, keywords in format_patterns.items():
        if any(kw in text_lower for kw in keywords):
            params["biofab_method"] = fmt
            break

    # Scaffold type
    for st in ("degradable", "rigid", "hybrid"):
        if st in text_lower:
            params["scaffold_type"] = st
            break

    # Construct dimensions (e.g. "4x4x2 mm" or "4 x 4 x 2")
    dim_match = re.search(
        r"(\d+\.?\d*)\s*[x×]\s*(\d+\.?\d*)\s*[x×]\s*(\d+\.?\d*)\s*mm",
        conversation_history, re.IGNORECASE,
    )
    if dim_match:
        params["scaffold_dimensions_mm"] = [
            float(dim_match.group(1)),
            float(dim_match.group(2)),
            float(dim_match.group(3)),
        ]

    # Culture duration
    dur_match = re.search(r"(\d+)\s*(?:day|d)\b", conversation_history, re.IGNORECASE)
    if dur_match:
        params["culture_duration_days"] = int(dur_match.group(1))

    # Pore size
    pore_match = re.search(r"(\d+\.?\d*)\s*(?:um|µm|micron)", conversation_history, re.IGNORECASE)
    if pore_match:
        params["pore_size_um"] = float(pore_match.group(1))

    if not params:
        return None

    return ConstructProfile(**params)
