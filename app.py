"""
Stromalytix — BioSim Copilot

Main Streamlit application for 3D cell culture variance analysis.
"""

import base64
import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path

import streamlit as st


def ensure_vectorstore():
    """Build ChromaDB on first deploy if it doesn't exist."""
    if not Path("data/chroma_db").exists():
        with st.spinner("🔬 Building knowledge base — first load only, ~2 minutes..."):
            from scripts.embed_and_index import main as build_index
            build_index()


from core.chat import extract_construct_profile, initialize_chat, send_message
from core.models import ConstructProfile, VarianceReport
from core.rag import retrieve_benchmarks, synthesize_variance_report
from core.viz import build_parameter_scatter, build_radar_chart, build_risk_scorecard

# Page configuration
st.set_page_config(
    page_title="Stromalytix | BioSim Copilot",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

ensure_vectorstore()

# CSS injection for dark theme
st.markdown(
    """
    <style>
    /* Dark theme */
    body {
        background-color: #0a0a0a;
        color: #e0e0e0;
    }

    .stApp {
        background-color: #0a0a0a;
    }

    /* Chat messages */
    .stChatMessage {
        background-color: #111111 !important;
        border: 1px solid #222222;
    }

    /* Buttons */
    .stButton>button {
        border: 1px solid #00ff88;
        color: #00ff88;
        background: transparent;
        font-weight: 500;
        transition: all 0.3s ease;
    }

    .stButton>button:hover {
        background: #00ff88;
        color: #000000;
    }

    /* Metric cards */
    [data-testid="stMetricValue"] {
        background-color: #111111;
        border: 1px solid #222222;
        padding: 1rem;
        border-radius: 0.5rem;
    }

    /* Containers */
    .narrative-container {
        background-color: #111111;
        border: 1px solid #222222;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }

    /* Headers */
    h1, h2, h3 {
        color: #e0e0e0;
    }

    /* Accent color for brand */
    .brand-text {
        color: #00ff88;
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "chain" not in st.session_state:
    st.session_state.chain = None

if "construct_profile" not in st.session_state:
    st.session_state.construct_profile = None

if "variance_report" not in st.session_state:
    st.session_state.variance_report = None

if "docs" not in st.session_state:
    st.session_state.docs = []

if "simulation_brief" not in st.session_state:
    st.session_state.simulation_brief = None

if "phase" not in st.session_state:
    st.session_state.phase = "onboarding"

if "persona" not in st.session_state:
    st.session_state.persona = None

if "application_domain" not in st.session_state:
    st.session_state.application_domain = None


def reset_analysis():
    """Reset all session state and start over."""
    st.session_state.messages = []
    st.session_state.chain = None
    st.session_state.construct_profile = None
    st.session_state.variance_report = None
    st.session_state.simulation_brief = None
    st.session_state.docs = []
    st.session_state.phase = "onboarding"
    st.session_state.persona = None
    st.session_state.application_domain = None
    st.rerun()


def save_signup(email: str):
    """Save email signup to CSV."""
    csv_path = Path("signups.csv")
    timestamp = datetime.now().isoformat()

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, email])


def is_profile_complete(profile: ConstructProfile) -> bool:
    """
    Check if ConstructProfile has enough fields populated to proceed.

    Requires at least 4 of these 5 key fields to be non-None:
    - target_tissue
    - cell_types
    - scaffold_material
    - experimental_goal
    - primary_readout

    Args:
        profile: ConstructProfile to validate

    Returns:
        True if profile is sufficiently complete, False otherwise
    """
    key_fields = [
        profile.target_tissue,
        profile.cell_types,
        profile.scaffold_material,
        profile.experimental_goal,
        profile.primary_readout
    ]

    # Count non-None fields
    populated_count = sum(1 for field in key_fields if field is not None)

    # Require at least 4 of 5 fields
    return populated_count >= 4


def analyze_conversation_progress() -> dict:
    """
    Analyze conversation messages to determine what topics have been discussed.

    Returns dict with boolean flags for each topic area.
    """
    if not st.session_state.messages:
        return {
            "tissue_discussed": False,
            "cells_discussed": False,
            "scaffold_discussed": False,
            "goals_discussed": False,
            "readout_discussed": False,
            "parameters_discussed": False
        }

    # Combine all conversation text
    conversation_text = " ".join([msg["content"].lower() for msg in st.session_state.messages])

    # Tissue keywords
    tissue_keywords = ["tissue", "organ", "brain", "cardiac", "liver", "bone", "cartilage", "skin", "muscle", "bbb", "blood-brain barrier"]
    tissue_discussed = any(kw in conversation_text for kw in tissue_keywords)

    # Cell type keywords
    cell_keywords = ["cell", "cells", "endothelial", "astrocyte", "neuron", "fibroblast", "cardiomyocyte", "hepatocyte", "bmec", "cmec"]
    cells_discussed = any(kw in conversation_text for kw in cell_keywords)

    # Scaffold keywords
    scaffold_keywords = ["scaffold", "matrix", "matrigel", "collagen", "gelma", "hydrogel", "ecm", "polymer", "material"]
    scaffold_discussed = any(kw in conversation_text for kw in scaffold_keywords)

    # Goals keywords
    goal_keywords = ["goal", "purpose", "disease model", "drug screen", "compare", "benchmark", "test", "validate", "application"]
    goals_discussed = any(kw in conversation_text for kw in goal_keywords)

    # Readout keywords
    readout_keywords = ["readout", "measure", "assay", "viability", "permeability", "teer", "barrier", "contractility", "imaging", "expression"]
    readout_discussed = any(kw in conversation_text for kw in readout_keywords)

    # Parameter keywords (stiffness, porosity, density)
    param_keywords = ["stiffness", "kpa", "porosity", "density", "concentration", "ratio", "thickness"]
    parameters_discussed = any(kw in conversation_text for kw in param_keywords)

    return {
        "tissue_discussed": tissue_discussed,
        "cells_discussed": cells_discussed,
        "scaffold_discussed": scaffold_discussed,
        "goals_discussed": goals_discussed,
        "readout_discussed": readout_discussed,
        "parameters_discussed": parameters_discussed
    }


# ============================================================================
# SIDEBAR
# ============================================================================

with st.sidebar:
    st.markdown('<h1 class="brand-text">🧬 Stromalytix</h1>', unsafe_allow_html=True)
    st.markdown("**Cell-ECM Interaction Modeling**")
    st.divider()

    # Show selected domain & persona if available
    domain = st.session_state.get("application_domain")
    if domain:
        domain_label = "🥩 Cellular Agriculture" if domain == "cellular_agriculture" else "🧬 Tissue Engineering"
        st.markdown(f'<p style="color: #4a9eff; font-size: 0.9em;"><strong>Domain:</strong> {domain_label}</p>', unsafe_allow_html=True)
    if st.session_state.persona:
        persona_labels = {
            "academic": "🎓 Academic / Research",
            "pharma_biotech": "💊 Pharma / Biotech",
            "hardware_service": "🔬 Hardware / Service Provider",
            "cellag_startup": "🏭 Cell Ag Startup",
        }
        st.markdown(f'<p style="color: #00ff88; font-size: 0.9em;"><strong>Role:</strong> {persona_labels.get(st.session_state.persona, "Unknown")}</p>', unsafe_allow_html=True)
    if domain or st.session_state.persona:
        st.divider()

    # Progress Checklist (Task 4)
    st.markdown("### Progress")

    # Analyze conversation for incremental progress
    conv_progress = analyze_conversation_progress()

    # Calculate progress with real-time conversation tracking
    steps = [
        ("Persona selected", st.session_state.persona is not None),
        ("Tissue type discussed", conv_progress["tissue_discussed"]),
        ("Goals defined", conv_progress["goals_discussed"]),
        ("Protocol details gathered", conv_progress["cells_discussed"] or conv_progress["scaffold_discussed"] or conv_progress["parameters_discussed"]),
        ("Knowledge base queried", len(st.session_state.docs) > 0),
        ("Variance report generated", st.session_state.variance_report is not None),
        ("Simulation brief ready", st.session_state.simulation_brief is not None)
    ]

    completed_count = sum(1 for _, completed in steps if completed)
    total_count = len(steps)
    progress_pct = completed_count / total_count

    # Progress bar
    st.progress(progress_pct)
    st.caption(f"{completed_count}/{total_count} steps complete")

    # Checklist
    for step_name, completed in steps:
        icon = "[OK]" if completed else "[ ]"
        color = "#00ff88" if completed else "#666666"
        st.markdown(f'<p style="color: {color}; font-size: 0.85em; margin: 0.2rem 0;">{icon} {step_name}</p>', unsafe_allow_html=True)

    # Debug info
    with st.expander("Debug Info", expanded=False):
        st.caption(f"Phase: {st.session_state.phase}")
        st.caption(f"Docs in session: {len(st.session_state.docs)}")
        st.caption(f"Profile exists: {st.session_state.construct_profile is not None}")
        st.caption(f"Report exists: {st.session_state.variance_report is not None}")
        st.caption(f"Sim brief exists: {st.session_state.simulation_brief is not None}")
        st.caption(f"Messages: {len(st.session_state.messages)}")

    st.divider()

    # Show construct profile if available
    if st.session_state.construct_profile:
        st.subheader("Your Construct")
        profile = st.session_state.construct_profile

        if profile.target_tissue:
            st.metric("Target Tissue", profile.target_tissue)

        if profile.scaffold_material:
            st.metric("Scaffold Material", profile.scaffold_material)

        if profile.stiffness_kpa is not None:
            st.metric("Stiffness", f"{profile.stiffness_kpa} kPa")

        if profile.porosity_percent is not None:
            st.metric("Porosity", f"{profile.porosity_percent}%")

        if profile.experimental_goal:
            st.metric("Experimental Goal", profile.experimental_goal)

        st.divider()

        # Culture protocol inputs
        with st.expander("Culture Protocol", expanded=False):
            format_options = ["wellplate", "transwell", "bioreactor", "bioprinter", "microfluidic", "other"]
            fmt_idx = format_options.index(profile.culture_format) if profile.culture_format in format_options else 0
            profile.culture_format = st.selectbox(
                "Culture format", options=format_options,
                index=fmt_idx, key="sb_culture_format",
            )

            st.markdown("**Construct dimensions (mm)**")
            dim_cols = st.columns(3)
            dims = profile.scaffold_dimensions_mm or [4.0, 4.0, 2.0]
            with dim_cols[0]:
                dx = st.number_input("X", min_value=0.1, max_value=100.0, value=float(dims[0]), step=0.5, key="sb_dim_x")
            with dim_cols[1]:
                dy = st.number_input("Y", min_value=0.1, max_value=100.0, value=float(dims[1]), step=0.5, key="sb_dim_y")
            with dim_cols[2]:
                dz = st.number_input("Z", min_value=0.1, max_value=100.0, value=float(dims[2]), step=0.5, key="sb_dim_z")
            profile.scaffold_dimensions_mm = [dx, dy, dz]

            profile.culture_duration_days = st.number_input(
                "Culture duration (days)", min_value=1, max_value=90,
                value=profile.culture_duration_days or 14,
                key="sb_culture_days",
            )
            profile.media_change_interval_hours = st.number_input(
                "Media change interval (hours)", min_value=0.0, max_value=168.0,
                value=profile.media_change_interval_hours or 48.0,
                step=12.0, key="sb_media_interval",
            )
            profile.medium_volume_ml = st.number_input(
                "Medium volume (mL)", min_value=0.1, max_value=50.0,
                value=profile.medium_volume_ml or 2.0,
                step=0.5, key="sb_medium_vol",
            )
            profile.oxygen_tension_percent = st.number_input(
                "O2 tension (%)", min_value=0.1, max_value=100.0,
                value=profile.oxygen_tension_percent or 20.0,
                step=1.0, key="sb_o2_tension",
            )
            profile.perfusion_rate_ul_min = st.number_input(
                "Perfusion rate (uL/min, 0=static)", min_value=0.0, max_value=1000.0,
                value=profile.perfusion_rate_ul_min or 0.0,
                step=10.0, key="sb_perfusion",
            )
            media_options = ["DMEM", "RPMI", "MEM", "DMEM/F12", "Custom"]
            idx = media_options.index(profile.media_type) if profile.media_type in media_options else 0
            profile.media_type = st.selectbox(
                "Media type", options=media_options,
                index=idx, key="sb_media_type",
            )

        st.divider()

    # Reset button
    if st.button("🔄 Reset Analysis", use_container_width=True):
        reset_analysis()

    # Debug: Force analysis button
    if st.session_state.phase == "assessment" and len(st.session_state.messages) > 0:
        st.divider()
        st.caption("🔧 Debug Tools")
        if st.button("⚡ Force Analysis →", use_container_width=True, type="secondary"):
            # Create a minimal profile from conversation
            full_conversation = "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in st.session_state.messages
            ])

            # Try to extract existing profile first
            profile = extract_construct_profile(full_conversation)

            # If no profile, create a minimal one
            if not profile:
                profile = ConstructProfile(
                    target_tissue="debug_tissue",
                    raw_responses={"conversation": full_conversation[:500]}
                )

            print("\n[DEBUG] Force Analysis Triggered")
            print(f"Profile target_tissue: {profile.target_tissue}")
            print(f"Profile fields populated: {sum(1 for f in [profile.target_tissue, profile.cell_types, profile.scaffold_material] if f is not None)}")

            st.session_state.construct_profile = profile
            st.session_state.phase = "analyzing"
            st.rerun()

    # About section
    with st.expander("ℹ️ About"):
        st.markdown(
            """
            **Stromalytix** predicts how cells adhere and proliferate on
            extracellular matrix and scaffold substrates.

            Literature-grounded simulation for cell-ECM interactions.
            """
        )


# ============================================================================
# MAIN AREA
# ============================================================================


def _render_biosim_tab():
    """Render the BioSim Copilot tab — all existing app logic."""
    if st.session_state.phase == "onboarding":
        # ========================================================================
        # PHASE: ONBOARDING (Welcome Screen + Persona Selection)
        # ========================================================================

        st.title("Welcome to Stromalytix")
        st.markdown("### Cell-ECM Interaction Modeling")

        st.markdown("""
        **Stromalytix** predicts how cells adhere and proliferate on extracellular matrix
        and scaffold substrates, grounded in published literature.

        #### How It Works

        1. **Chat Assessment** - Answer questions about your construct parameters
        2. **Literature Query** - We search 798 PubMed abstracts in our knowledge base
        3. **Variance Analysis** - Get AI-powered insights with PMID citations
        4. **Risk Scoring** - See how your protocol compares to published benchmarks
        5. **Simulation Preview** - Preview what CC3D simulation would predict

        #### What You'll Get

        - **Radar Chart** showing protocol deviation across key parameters
        - **Risk Scorecard** with color-coded risk flags (green/yellow/red)
        - **AI Narrative** citing specific PMIDs from the literature
        - **Parameter Scatter Plot** comparing your construct to published ranges
        - **CC3D Simulation Brief** (preview - full integration coming Q3 2026)
        """)

        st.divider()

        # Protocol Upload (optional)
        st.markdown("### Upload Your Protocol (Optional)")
        uploaded_file = st.file_uploader(
            "Upload your protocol document",
            type=["pdf", "docx", "txt"],
            help="We'll extract construct parameters automatically from your protocol.",
        )
        if uploaded_file is not None:
            try:
                from core.ingest import (
                    extract_text_from_pdf, extract_text_from_docx,
                    extract_text_from_txt, parse_protocol_to_profile,
                )
                file_bytes = uploaded_file.read()
                fname = uploaded_file.name.lower()
                if fname.endswith(".pdf"):
                    text = extract_text_from_pdf(file_bytes)
                elif fname.endswith(".txt"):
                    text = extract_text_from_txt(file_bytes)
                else:
                    text = extract_text_from_docx(file_bytes)

                with st.spinner("Extracting parameters..."):
                    detected = parse_protocol_to_profile(text)

                # Show extracted parameters
                non_null = {k: v for k, v in detected.items() if v is not None}
                if non_null:
                    st.success(f"Extracted {len(non_null)} parameters from protocol:")
                    cols = st.columns(2)
                    for i, (k, v) in enumerate(non_null.items()):
                        label = k.replace("_", " ").title()
                        cols[i % 2].markdown(f"**{label}**: {v}")
                    # Pre-populate session state
                    for k, v in detected.items():
                        if v is not None and k in ConstructProfile.model_fields:
                            setattr(st.session_state.construct_profile, k, v)
                else:
                    st.info("No construct parameters detected. The chat will help collect them.")

                # Show extracted text in expander
                with st.expander("View extracted text"):
                    st.text(text[:3000] + ("..." if len(text) > 3000 else ""))

            except Exception as e:
                st.warning(f"Could not parse protocol: {e}")

        st.divider()

        # Application Domain
        st.markdown("### What are you building?")

        domain_col1, domain_col2 = st.columns(2)
        with domain_col1:
            if st.button("🧬 Tissue Engineering", use_container_width=True, type="secondary"):
                st.session_state.application_domain = "tissue_engineering"
                if st.session_state.construct_profile:
                    st.session_state.construct_profile.application_domain = "tissue_engineering"
                st.rerun()
            st.caption("Regenerative medicine, disease models, drug screening")
        with domain_col2:
            if st.button("🥩 Cellular Agriculture", use_container_width=True, type="secondary"):
                st.session_state.application_domain = "cellular_agriculture"
                if st.session_state.construct_profile:
                    st.session_state.construct_profile.application_domain = "cellular_agriculture"
                st.rerun()
            st.caption("Cultivated meat, structured protein, fat tissue")

        if not st.session_state.get("application_domain"):
            st.stop()

        st.divider()

        # Persona Selection
        st.markdown("### 👤 Select Your Role")
        st.markdown("Help us tailor the experience to your workflow:")

        if st.session_state.application_domain == "cellular_agriculture":
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("🎓 Academic / Research", use_container_width=True, type="secondary"):
                    st.session_state.persona = "academic"
                    st.session_state.phase = "assessment"
                    st.rerun()
                st.caption("University labs, food science research")
            with col2:
                if st.button("🏭 Cell Ag Startup", use_container_width=True, type="secondary"):
                    st.session_state.persona = "cellag_startup"
                    st.session_state.phase = "assessment"
                    st.rerun()
                st.caption("Cultivated meat, scale-up, product development")
            with col3:
                if st.button("🔬 Ingredient / Equipment", use_container_width=True, type="secondary"):
                    st.session_state.persona = "hardware_service"
                    st.session_state.phase = "assessment"
                    st.rerun()
                st.caption("Media, scaffolds, bioreactors for cell ag")
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("🎓 Academic Researcher", use_container_width=True, type="secondary"):
                    st.session_state.persona = "academic"
                    st.session_state.phase = "assessment"
                    st.rerun()
                st.caption("University labs, research institutes")
            with col2:
                if st.button("💊 Pharma / Biotech", use_container_width=True, type="secondary"):
                    st.session_state.persona = "pharma_biotech"
                    st.session_state.phase = "assessment"
                    st.rerun()
                st.caption("Drug discovery, therapeutic development")
            with col3:
                if st.button("🔬 Hardware / Service Provider", use_container_width=True, type="secondary"):
                    st.session_state.persona = "hardware_service"
                    st.session_state.phase = "assessment"
                    st.rerun()
                st.caption("Equipment, bioinks, CRO services")

    elif st.session_state.phase == "assessment":
        # ========================================================================
        # PHASE: ASSESSMENT (Chat Interface)
        # ========================================================================

        st.title("BioSim Copilot")
        st.subheader("Answer a few questions. Get a literature-grounded variance analysis of your 3D construct.")

        # Initialize chat chain on first load
        if st.session_state.chain is None:
            with st.spinner("Initializing BioSim Copilot..."):
                st.session_state.chain = initialize_chat(
                    domain=st.session_state.get("application_domain", "tissue_engineering")
                )
                # Get the initial greeting
                if len(st.session_state.messages) == 0:
                    from core.chat import _clean_response
                    memory_vars = st.session_state.chain.memory.load_memory_variables({})
                    if "history" in memory_vars and len(memory_vars["history"]) > 0:
                        initial_response = _clean_response(memory_vars["history"][-1])
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": initial_response
                        })

        # Render chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                _chat_text = message["content"]
                # Strip markdown heading markers so LLM responses don't render as giant titles
                _chat_text = re.sub(r"^#{1,4}\s+", "**", _chat_text, flags=re.MULTILINE)
                st.markdown(_chat_text)

        # Chat input
        if user_input := st.chat_input("Describe your construct or answer the question..."):
            # Add user message to chat
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            # Get assistant response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    assistant_response = send_message(st.session_state.chain, user_input)
                    _display = re.sub(r"^#{1,4}\s+", "**", assistant_response, flags=re.MULTILINE)
                    st.markdown(_display)

            st.session_state.messages.append({
                "role": "assistant",
                "content": assistant_response
            })

            # Try to extract construct profile - with validation
            # CONDITION 1: Minimum message count (at least 8 messages = 4 exchanges)
            msg_count = len(st.session_state.messages)
            min_messages_met = msg_count >= 8

            print("\n" + "="*60)
            print("DEBUG: Phase Transition Check")
            print("="*60)
            print(f"Message count: {msg_count}")
            print(f"Min messages met (>= 8): {min_messages_met}")

            if min_messages_met:
                full_conversation = "\n".join([
                    f"{msg['role']}: {msg['content']}"
                    for msg in st.session_state.messages
                ])

                # Check for <construct_profile> tag
                has_tag = "<construct_profile>" in full_conversation
                print(f"<construct_profile> tag found: {has_tag}")

                profile = extract_construct_profile(full_conversation)

                print(f"Profile extracted: {profile is not None}")

                if profile:
                    print("\nExtracted Profile Fields:")
                    print(f"  target_tissue: {profile.target_tissue}")
                    print(f"  cell_types: {profile.cell_types}")
                    print(f"  scaffold_material: {profile.scaffold_material}")
                    print(f"  stiffness_kpa: {profile.stiffness_kpa}")
                    print(f"  porosity_percent: {profile.porosity_percent}")
                    print(f"  cell_density_per_ml: {profile.cell_density_per_ml}")
                    print(f"  experimental_goal: {profile.experimental_goal}")
                    print(f"  primary_readout: {profile.primary_readout}")

                    is_complete = is_profile_complete(profile)
                    print(f"\nProfile complete (4+ key fields): {is_complete}")

                    # CONDITION 2: Profile must be complete (4+ key fields populated)
                    if is_complete:
                        print("\n[OK] ALL CONDITIONS MET - TRANSITIONING TO ANALYZING")
                        st.session_state.construct_profile = profile
                        st.session_state.phase = "analyzing"
                        st.rerun()
                    else:
                        print("\n[X] Profile incomplete - staying in assessment")
                else:
                    print("\n[X] No profile extracted - staying in assessment")
            else:
                print(f"\n[X] Need {8 - msg_count} more messages - staying in assessment")

            print("="*60 + "\n")

    elif st.session_state.phase == "analyzing":
        # ========================================================================
        # PHASE: ANALYZING (RAG Processing)
        # ========================================================================

        # Check if we already have a variance report (avoid re-running)
        if st.session_state.variance_report is not None:
            st.session_state.phase = "results"
            st.rerun()

        with st.spinner("Querying PubMed knowledge base... Synthesizing variance report..."):
            # Handle None construct_profile (from force analysis with no data)
            if st.session_state.construct_profile is None:
                print("[ANALYZING] No construct_profile found - creating minimal profile from chat")
                # Create minimal profile using Haiku to extract from messages
                from langchain_anthropic import ChatAnthropic

                try:
                    _api_key = st.secrets.get("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY"))
                except Exception:
                    _api_key = os.getenv("ANTHROPIC_API_KEY")

                llm = ChatAnthropic(
                    model="claude-haiku-4-5-20251001",
                    temperature=0,
                    max_tokens=1024,
                    api_key=_api_key
                )

                conversation_text = "\n".join([
                    f"{msg['role']}: {msg['content']}"
                    for msg in st.session_state.messages
                ]) if st.session_state.messages else "No conversation data"

                extraction_prompt = f"""Extract tissue engineering construct parameters from this conversation. Return JSON with any fields you can identify (use null for unknown):
    {{
      "target_tissue": "string or null",
      "cell_types": ["list"] or null,
      "scaffold_material": "string or null",
      "stiffness_kpa": "number or null",
      "porosity_percent": "number or null",
      "cell_density_per_ml": "number or null",
      "experimental_goal": "string or null",
      "primary_readout": "string or null",
      "scaffold_type": "degradable | rigid | hybrid or null",
      "biofab_method": "string or null",
      "scaffold_dimensions_mm": "[x, y, z] or null",
      "pore_size_um": "number or null",
      "culture_format": "wellplate | bioreactor | transwell | bioprinter | microfluidic or null",
      "culture_duration_days": "number or null",
      "media_change_interval_hours": "number or null",
      "medium_volume_ml": "number or null",
      "oxygen_tension_percent": "number or null"
    }}

    Conversation:
    {conversation_text[:2000]}

    Return ONLY the JSON, no other text."""

                try:
                    response = llm.invoke(extraction_prompt)
                    json_str = response.content.strip()
                    json_str = re.sub(r"^```json\s*", "", json_str)
                    json_str = re.sub(r"\s*```$", "", json_str)
                    profile_dict = json.loads(json_str)
                    st.session_state.construct_profile = ConstructProfile(**profile_dict)
                except Exception as e:
                    print(f"[ANALYZING] Failed to extract profile: {e}")
                    # Fallback to minimal profile
                    st.session_state.construct_profile = ConstructProfile(
                        target_tissue="unknown",
                        experimental_goal="basic_research"
                    )

            # Retrieve benchmarks (k=12 for Task 3)
            print(f"[ANALYZING] Retrieving benchmarks for profile: {st.session_state.construct_profile.target_tissue}")
            docs = retrieve_benchmarks(st.session_state.construct_profile, k=12)
            st.session_state.docs = docs
            print(f"[ANALYZING] Retrieved {len(docs)} documents from knowledge base")

            # Synthesize report
            print(f"[ANALYZING] Synthesizing variance report with {len(docs)} docs")
            variance_report = synthesize_variance_report(
                st.session_state.construct_profile,
                docs
            )
            st.session_state.variance_report = variance_report
            print(f"[ANALYZING] Variance report generated successfully")

            # Always move to results
            print(f"[ANALYZING] Transitioning to results phase")
            st.session_state.phase = "results"
            st.rerun()

    elif st.session_state.phase == "results":
        # ========================================================================
        # PHASE: RESULTS (Visualization & Analysis)
        # ========================================================================

        profile = st.session_state.construct_profile
        report = st.session_state.variance_report

        # Header
        st.title(f"Analysis: {profile.target_tissue or 'Your Construct'}")

        # ── Feasibility Analysis (top of results) ──
        st.markdown("### Feasibility Analysis")
        st.caption("Cross-referencing your protocol against the literature parameter library.")
        try:
            from core.feasibility import analyse as feasibility_analyse
            feas = feasibility_analyse(profile, report)

            tier_color = {
                "feasible": "#00ff88",
                "marginal": "#ffd700",
                "aspirational": "#ff4444",
            }

            overall_color = tier_color.get(feas.overall, "#888")
            st.markdown(
                f'<p style="font-size:1.1em;">Overall assessment: '
                f'<strong style="color:{overall_color};">{feas.overall.upper()}</strong></p>',
                unsafe_allow_html=True,
            )

            for tier_name, items, color in [
                ("Feasible — literature-backed", feas.feasible, tier_color["feasible"]),
                ("Marginal — partial data", feas.marginal, tier_color["marginal"]),
                ("Aspirational — limited / no data", feas.aspirational, tier_color["aspirational"]),
            ]:
                if not items:
                    continue
                st.markdown(
                    f'<p style="color:{color}; font-weight:600; margin-top:0.8rem;">{tier_name} '
                    f'({len(items)})</p>',
                    unsafe_allow_html=True,
                )
                for it in items:
                    detail_html = f'<span style="color:#e0e0e0;">{it.detail}</span>'
                    if it.suggestion:
                        detail_html += (
                            f'<br><span style="color:#aaa; font-style:italic;">'
                            f'Suggestion: {it.suggestion}</span>'
                        )
                    st.markdown(
                        f'<div style="border-left:3px solid {color}; padding:0.4rem 0.8rem; '
                        f'margin:0.3rem 0; background:#111;">'
                        f'<strong style="color:{color};">{it.axis}</strong><br>'
                        f'{detail_html}</div>',
                        unsafe_allow_html=True,
                    )
        except Exception as e:
            st.warning(f"Feasibility analysis unavailable: {e}")

        # ── Migration & Gradient Insights ──
        st.markdown("### Migration & Gradient Hypotheses")
        st.caption(
            "How fabricated and spontaneous gradients are expected to "
            "influence cell migration in this construct."
        )
        try:
            from core.migration_insights import analyse as migration_analyse
            mig_rpt = migration_analyse(profile)

            category_icons = {
                "Spontaneous O2 Gradient": "🫁",
                "Nutrient / Waste Gradients": "🧪",
                "Fabricated / Emergent Stiffness Gradient": "🔧",
                "Contact Guidance (Geometric)": "📐",
                "Migration Kinetics": "🏃",
                "Degradation-Driven Migration": "♻️",
            }
            conf_badge = {
                "high": ("🟢", "#00ff88"),
                "medium": ("🟡", "#ffd700"),
                "low": ("🔴", "#ff4444"),
            }

            for cat, insights in mig_rpt.by_category.items():
                icon = category_icons.get(cat, "🔬")
                st.markdown(
                    f'<p style="font-weight:600; font-size:1.05em; margin-top:1rem;">'
                    f'{icon} {cat}</p>',
                    unsafe_allow_html=True,
                )
                for ins in insights:
                    badge_char, badge_color = conf_badge.get(ins.confidence, ("⚪", "#888"))
                    source_html = ""
                    if ins.sources:
                        links = ", ".join(
                            f'<a href="https://doi.org/{d}" style="color:#4a9eff;">{d}</a>'
                            for d in ins.sources if d
                        )
                        if links:
                            source_html = f'<br><span style="color:#666; font-size:0.85em;">Sources: {links}</span>'
                    st.markdown(
                        f'<div style="border-left:3px solid #333; padding:0.5rem 0.8rem; '
                        f'margin:0.3rem 0; background:#0d0d0d;">'
                        f'<strong style="color:#e0e0e0;">{ins.headline}</strong> '
                        f'<span style="color:{badge_color}; font-size:0.85em;">{badge_char} {ins.confidence}</span>'
                        f'<br><span style="color:#aaa; font-size:0.92em;">{ins.detail}</span>'
                        f'{source_html}</div>',
                        unsafe_allow_html=True,
                    )

            if not mig_rpt.insights:
                st.info("Insufficient data to generate migration hypotheses. "
                        "Specify cell types, scaffold material, and dimensions.")
        except Exception as e:
            st.warning(f"Migration analysis unavailable: {e}")

        st.divider()

        # Row 1: Radar chart + Risk scorecard
        col1, col2 = st.columns([60, 40])

        with col1:
            st.plotly_chart(
                build_radar_chart(report),
                use_container_width=True
            )

        with col2:
            st.plotly_chart(
                build_risk_scorecard(report),
                use_container_width=True
            )

        # Row 2: AI Narrative
        st.markdown('<div class="narrative-container">', unsafe_allow_html=True)
        st.markdown("### 📊 Analysis Summary")
        st.markdown(report.ai_narrative)

        if report.supporting_pmids:
            pmid_links = ", ".join([
                f"[{pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)"
                for pmid in report.supporting_pmids
            ])
            st.markdown(
                f'<p style="color: #888; font-size: 0.9em; margin-top: 1rem;">'
                f'<strong>Supporting Literature:</strong> {pmid_links}</p>',
                unsafe_allow_html=True
            )
        st.markdown('</div>', unsafe_allow_html=True)

        # Key References (Task 3)
        if report.key_references:
            with st.expander("📚 Source Literature"):
                for ref in report.key_references:
                    st.markdown(f"""
                    **{ref.get('title', 'Untitled')}** ({ref.get('year', 'N/A')})
                    PMID: [{ref.get('pmid', 'N/A')}](https://pubmed.ncbi.nlm.nih.gov/{ref.get('pmid')})
                    *{ref.get('relevance_note', 'No note provided')}*
                    """)
                    st.divider()

        # Row 3: Parameter scatter
        st.plotly_chart(
            build_parameter_scatter(report),
            use_container_width=True
        )

        # Scaffold Geometry Preview
        st.markdown("### 🏗️ Scaffold Geometry")

        scaf_col1, scaf_col2 = st.columns([2, 1])
        with scaf_col2:
            scaffold_arch = st.selectbox(
                "Architecture",
                ["gyroid", "schwarz_p", "diamond", "lidinoid", "woodpile", "grid", "custom_stl"],
                index=0,
                key="scaf_arch",
            )
            scaf_pore = st.slider("Pore size (um)", 100, 800, 300, key="scaf_pore")
            scaf_porosity = st.slider("Porosity (%)", 30, 90, 70, key="scaf_porosity")

            stl_file = st.file_uploader("Upload STL", type=["stl", "obj"], key="stl_upload")

            if scaffold_arch != "custom_stl" or stl_file is not None:
                generate_scaffold = st.button("Generate Preview", key="gen_scaffold", use_container_width=True)
            else:
                generate_scaffold = False

        with scaf_col1:
            if generate_scaffold:
                try:
                    from core.scaffold_geometry import (
                        generate_tpms, generate_filament_lattice,
                        import_stl, preview_scaffold,
                    )
                    if stl_file is not None:
                        mesh = import_stl(stl_file.read())
                    elif scaffold_arch in ("woodpile", "grid"):
                        mesh = generate_filament_lattice(
                            strand_diameter_um=scaf_pore * 0.5,
                            strand_spacing_um=scaf_pore,
                            pattern=scaffold_arch,
                        )
                    else:
                        mesh = generate_tpms(
                            topology=scaffold_arch,
                            pore_size_um=scaf_pore,
                            porosity_pct=scaf_porosity,
                        )
                    st.session_state["scaffold_mesh"] = mesh
                    fig_scaf = preview_scaffold(mesh)
                    st.plotly_chart(fig_scaf, use_container_width=True)

                    # Update profile
                    profile.scaffold_architecture = scaffold_arch
                    profile.pore_size_um = scaf_pore
                    profile.porosity_percent = scaf_porosity
                except Exception as e:
                    st.warning(f"Scaffold generation error: {e}")
            elif "scaffold_mesh" in st.session_state:
                from core.scaffold_geometry import preview_scaffold
                fig_scaf = preview_scaffold(st.session_state["scaffold_mesh"])
                st.plotly_chart(fig_scaf, use_container_width=True)
            else:
                st.info("Select scaffold parameters and click Generate Preview.")

        # Row 3.75: Scaffold Mechanics (FEA)
        if profile.stiffness_kpa and profile.cell_density_per_ml:
            from core.fem_solver import predict_scaffold_deformation, predict_stress_distribution

            st.markdown("### 🏗️ Scaffold Mechanics (FEA)")

            fea_result = predict_scaffold_deformation(
                stiffness_kpa=profile.stiffness_kpa,
                cell_density_per_ml=profile.cell_density_per_ml,
            )

            fea_col1, fea_col2, fea_col3 = st.columns(3)
            with fea_col1:
                st.metric("Max Deformation", f"{fea_result['max_deformation_um']:.1f} um")
            with fea_col2:
                st.metric("Strain", f"{fea_result['strain_percent']:.2f}%")
            with fea_col3:
                risk = fea_result["failure_risk"]
                risk_color = {"low": "#00ff88", "medium": "#ffd700", "high": "#ff4444"}.get(risk, "#888")
                st.markdown(
                    f'<p style="font-size: 0.85em; color: #888;">Failure Risk</p>'
                    f'<p style="font-size: 1.5em; font-weight: bold; color: {risk_color};">{risk.upper()}</p>',
                    unsafe_allow_html=True,
                )

            st.markdown(
                f'<div style="border: 1px solid #444; padding: 0.8rem; border-radius: 0.5rem; '
                f'background: #1a1a1a; margin: 0.5rem 0;">'
                f'<span style="color: #aaa;">{fea_result["recommendation"]}</span></div>',
                unsafe_allow_html=True,
            )

            if profile.porosity_percent:
                stress_result = predict_stress_distribution(
                    stiffness_kpa=profile.stiffness_kpa,
                    porosity_percent=profile.porosity_percent,
                )
                st.markdown(
                    f'<div style="border: 1px solid #444; padding: 0.8rem; border-radius: 0.5rem; '
                    f'background: #1a1a1a; margin: 0.5rem 0;">'
                    f'<span style="color: #aaa;">{stress_result["recommendation"]}</span></div>',
                    unsafe_allow_html=True,
                )

        # Row 4: CC3D Simulation Brief (Task 6)
        st.markdown("### 🔬 Simulation Brief — What CC3D Would Predict")

        # Generate simulation brief (cache in session state)
        if st.session_state.simulation_brief is None:
            try:
                from core.rag import generate_simulation_brief
                st.session_state.simulation_brief = generate_simulation_brief(profile, report)
            except Exception as e:
                st.error(f"Could not generate simulation brief: {e}")
                st.session_state.simulation_brief = None

        sim_brief = st.session_state.simulation_brief

        if sim_brief is not None:
            # Simulation question
            st.markdown(f'<p style="font-size: 1.2em; font-weight: 500; margin: 1rem 0;">{sim_brief["simulation_question"]}</p>', unsafe_allow_html=True)

            # Key parameters as code block
            st.markdown("**Key CC3D Parameters:**")
            st.code(json.dumps(sim_brief["key_parameters"], indent=2), language="json")

            # Parameter source table
            param_sources = sim_brief.get("parameter_sources", {})
            if param_sources:
                st.markdown("**Parameter Provenance:**")
                source_rows = []
                for pname, info in param_sources.items():
                    src = info.get("source", "unknown")
                    conf = info.get("confidence", "?")
                    doi = info.get("doi") or ""
                    if conf == "high":
                        conf_display = "🟢 high"
                    elif conf == "medium":
                        conf_display = "🟡 medium"
                    else:
                        conf_display = "🔴 low"
                    source_rows.append({
                        "Parameter": pname.replace("_", " ").title(),
                        "Source": src,
                        "Confidence": conf_display,
                        "DOI": doi,
                    })
                if source_rows:
                    import pandas as pd
                    st.dataframe(
                        pd.DataFrame(source_rows),
                        use_container_width=True,
                        hide_index=True,
                    )

            # Predicted outcomes
            st.markdown("**Predicted Observations:**")
            for i, outcome in enumerate(sim_brief["predicted_outcomes"], 1):
                st.markdown(f"{i}. {outcome}")

            # Risk prediction (red border)
            st.markdown(
                f'<div style="border: 2px solid #ff4444; padding: 1rem; border-radius: 0.5rem; background: #1a0a0a; margin: 1rem 0;">'
                f'<strong style="color: #ff4444;">⚠ Risk Prediction:</strong><br>{sim_brief["risk_prediction"]}'
                f'</div>',
                unsafe_allow_html=True
            )

            # Validation experiment (green border)
            st.markdown(
                f'<div style="border: 2px solid #00ff88; padding: 1rem; border-radius: 0.5rem; background: #0a1a0a; margin: 1rem 0;">'
                f'<strong style="color: #00ff88;">✓ Validation Experiment:</strong><br>{sim_brief["validation_experiment"]}'
                f'</div>',
                unsafe_allow_html=True
            )

            # CC3D Cloud Execution
            from core.cc3d_runner import run_simulation, CC3D_API_URL

            if CC3D_API_URL:
                if st.button("⚡ Run CC3D Simulation (Cloud)", use_container_width=True):
                    with st.spinner("Running CC3D simulation on cloud..."):
                        cc3d_result = run_simulation(sim_brief)
                        if cc3d_result["success"]:
                            st.success(f"CC3D completed: {cc3d_result['mcs_completed']} MCS in {cc3d_result['duration_seconds']}s")
                            if cc3d_result.get("output"):
                                st.code(cc3d_result["output"], language="text")

                            vtk_frames = cc3d_result.get("vtk_frames", [])
                            if vtk_frames:
                                from core.cc3d_viz import (
                                    parse_vtk_from_bytes, parse_vtk_scalar_field,
                                    get_default_type_map, render_unified_scene,
                                )

                                type_map = get_default_type_map(sim_brief.get("key_parameters", sim_brief))

                                cell_frames = [f for f in vtk_frames if f.get("field_type") == "cell"]
                                o2_frames = [f for f in vtk_frames if f.get("field_type") == "o2"]

                                display_frames = cell_frames if cell_frames else vtk_frames
                                frame_idx = len(display_frames) - 1
                                if len(display_frames) > 1:
                                    frame_idx = st.slider(
                                        "Simulation frame",
                                        0, len(display_frames) - 1,
                                        value=len(display_frames) - 1,
                                        key="cc3d_frame_slider",
                                    )

                                frame = display_frames[frame_idx]
                                vtk_bytes = base64.b64decode(frame["data_b64"])
                                lattice = parse_vtk_from_bytes(vtk_bytes)

                                # Find matching O2 frame
                                o2_field = None
                                if o2_frames and frame_idx < len(o2_frames):
                                    o2_bytes = base64.b64decode(o2_frames[frame_idx]["data_b64"])
                                    o2_field = parse_vtk_scalar_field(o2_bytes)

                                scaffold_mesh = st.session_state.get("scaffold_mesh")

                                fig_cc3d = render_unified_scene(
                                    cell_lattice=lattice,
                                    type_map=type_map,
                                    o2_field=o2_field,
                                    scaffold_mesh=scaffold_mesh,
                                    title="CC3D Simulation Result",
                                    timestep=frame_idx,
                                )
                                st.plotly_chart(fig_cc3d, use_container_width=True)

                                if o2_field is not None:
                                    st.caption("Red markers indicate hypoxic zones (O2 < 5%)")
                        else:
                            st.warning(f"CC3D: {cc3d_result.get('error', 'Unknown error')}")
            else:
                st.button(
                    "⚡ Run CC3D Simulation (Cloud)",
                    disabled=True,
                    use_container_width=True,
                    help="Set CC3D_API_URL environment variable to your VPS sidecar address.",
                )
        else:
            st.warning("Simulation brief could not be generated. Check your API key and try again.")

        # Row 5: Export & Download
        st.divider()
        export_col1, export_col2 = st.columns(2)
        with export_col1:
            try:
                from core.export import generate_pdf_report
                pdf_path = generate_pdf_report(report, client_name="")
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "Download PDF Report",
                        data=f.read(),
                        file_name=Path(pdf_path).name,
                        mime="application/pdf",
                        use_container_width=True,
                    )
            except Exception as e:
                st.button("Download PDF Report", disabled=True, use_container_width=True,
                          help=f"PDF export unavailable: {e}")

        with export_col2:
            try:
                scaffold_mesh = st.session_state.get("scaffold_mesh")
                if scaffold_mesh:
                    from core.export import export_figure_png
                    from core.scaffold_geometry import preview_scaffold
                    viz_fig = preview_scaffold(scaffold_mesh)
                    png_bytes = export_figure_png(viz_fig)
                    st.download_button(
                        "Download Scaffold Preview (PNG)",
                        data=png_bytes,
                        file_name=f"stromalytix_{profile.target_tissue or 'construct'}_scaffold.png",
                        mime="image/png",
                        use_container_width=True,
                    )
                else:
                    st.button("Download Scaffold Preview (PNG)", disabled=True,
                              use_container_width=True, help="Generate a scaffold preview first.")
            except Exception as e:
                st.button("Download Scaffold (PNG)", disabled=True, use_container_width=True,
                          help=f"PNG export unavailable: {e}")

        # Row 6: Signup CTA
        st.divider()
        st.markdown("### 💾 Save this analysis + get early access to the full platform")

        col1, col2 = st.columns([3, 1])

        with col1:
            email = st.text_input(
                "Email address",
                placeholder="your.email@institution.edu",
                label_visibility="collapsed"
            )

        with col2:
            if st.button("Sign Up", use_container_width=True):
                if email and "@" in email:
                    save_signup(email)
                    st.success("You're on the list. We'll be in touch.")
                else:
                    st.error("Please enter a valid email address.")


# ============================================================================
# Render
# ============================================================================

_render_biosim_tab()
