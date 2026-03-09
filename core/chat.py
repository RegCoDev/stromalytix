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
    raise ValueError("ANTHROPIC_API_KEY not found in environment or Streamlit secrets")

# System prompt for construct assessment
SYSTEM_PROMPT = """You are a Tissue Engineering Protocol Analyst for Stromalytix. Assess a researcher's 3D cell culture construct through a friendly expert conversation. Ask ONE question at a time. Collect: target tissue, cell types, scaffold material, stiffness (kPa), porosity (%), cell density, experimental goal, primary readout.

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
  "primary_readout": "string"
}
</construct_profile>

For numeric fields (stiffness_kpa, porosity_percent, cell_density_per_ml), output ONLY single numbers (e.g., 75.0, not "70-80%"). If given a range, output the midpoint."""


def initialize_chat() -> ConversationChain:
    """
    Initialize a conversation chain with Haiku and buffer memory.

    Returns:
        ConversationChain configured for construct assessment
    """
    # Initialize Haiku model
    llm = ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        temperature=0.7,
        max_tokens=2048,  # Increased to allow full JSON output + conversation
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )

    # Initialize conversation memory
    memory = ConversationBufferMemory(
        return_messages=True,
        memory_key="history"
    )

    # Create conversation chain with system prompt
    chain = ConversationChain(
        llm=llm,
        memory=memory,
        verbose=False
    )

    # Inject system prompt via first exchange
    chain.predict(input=f"SYSTEM: {SYSTEM_PROMPT}\n\nRespond with a friendly greeting and ask the first question to begin the construct assessment.")

    return chain


def send_message(chain: ConversationChain, user_input: str) -> str:
    """
    Send a user message to the conversation chain and get response.

    Sanitizes input to prevent prompt injection before sending to LLM.

    Args:
        chain: ConversationChain instance
        user_input: User's message

    Returns:
        AI assistant's response
    """
    # Import sanitization function
    from core.rag import sanitize_input

    # Sanitize user input
    sanitized_input = sanitize_input(user_input)

    # If sanitization detected malicious content, return safe response directly
    if sanitized_input == "I can only help with tissue engineering protocol analysis.":
        print("[SANITIZED] Blocked malicious input in send_message")
        return sanitized_input

    response = chain.predict(input=sanitized_input)
    return response


def clean_numeric_fields(profile_dict: dict) -> dict:
    """
    Clean numeric fields that might contain string ranges like '80-95%' or '5-10'.
    Converts to midpoint float.
    """
    for field in ['stiffness_kpa', 'porosity_percent', 'cell_density_per_ml']:
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

    # Tissue type patterns
    tissue_patterns = [
        "cardiac", "liver", "hepatic", "neural", "brain", "lung",
        "kidney", "intestinal", "bone", "cartilage", "skin",
        "tumor", "vascular", "pancreatic",
    ]
    text_lower = conversation_history.lower()
    for tissue in tissue_patterns:
        if tissue in text_lower:
            params["target_tissue"] = tissue
            break

    # Scaffold material
    materials = ["GelMA", "collagen", "alginate", "fibrin", "PEGDA",
                 "hyaluronic acid", "Matrigel", "silk", "PDMS"]
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

    # Cell types
    cell_patterns = [
        "cardiomyocytes", "fibroblasts", "HUVEC", "HepG2", "MCF-7",
        "iPSC", "neurons", "astrocytes", "Caco-2", "A549",
    ]
    found_cells = [c for c in cell_patterns if c.lower() in text_lower]
    if found_cells:
        params["cell_types"] = found_cells

    if not params:
        return None

    return ConstructProfile(**params)
