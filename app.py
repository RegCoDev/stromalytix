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
from results_tab_renderers import (
    render_results_action_plan_tab,
    render_results_feasibility_tab,
    render_results_simulation_tab,
)

# Page configuration
st.set_page_config(
    page_title="Stromalytix | Biofabrication Cell-ECM",
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

if "action_plan_narrative" not in st.session_state:
    st.session_state.action_plan_narrative = ""

if "phase" not in st.session_state:
    st.session_state.phase = "onboarding"

if "persona" not in st.session_state:
    st.session_state.persona = None

if "application_domain" not in st.session_state:
    st.session_state.application_domain = None

if "onboarding_slide" not in st.session_state:
    st.session_state.onboarding_slide = 0


def reset_analysis():
    """Reset all session state and start over."""
    st.session_state.messages = []
    st.session_state.chain = None
    st.session_state.construct_profile = None
    st.session_state.variance_report = None
    st.session_state.simulation_brief = None
    st.session_state.action_plan_narrative = ""
    st.session_state.docs = []
    st.session_state.phase = "onboarding"
    st.session_state.persona = None
    st.session_state.application_domain = None
    st.session_state.onboarding_slide = 0
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
    st.markdown("**Cell-ECM for biofabrication**")
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
            **Stromalytix** models cell-ECM behavior for **biofabrication**:
            bioinks, scaffolds, and culture protocols. Literature-grounded benchmarks,
            optional CompuCell3D cloud runs, and scaffold geometry preview.
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

        st.title("Stromalytix")
        st.caption("Cell-ECM modeling for biofabrication")
        st.markdown(
            '<p style="font-size:1.2rem; line-height:1.5; color:#d4d4d4; margin:0 0 1rem 0;">'
            "Short chat. Literature-backed benchmarks. Optional cloud simulation."
            "</p>",
            unsafe_allow_html=True,
        )

        _slides = [
            {
                "title": "Built for biofabrication",
                "body": (
                    "Relate **bioinks, scaffolds, porosity, and culture setup** to how cells "
                    "**adhere**, **migrate**, and **proliferate** in engineered matrices."
                ),
            },
            {
                "title": "How it works",
                "body": (
                    "**1.** Describe your construct in chat. **2.** We search thousands of "
                    "PubMed-indexed abstracts. **3.** You get benchmarks, feasibility, and "
                    "migration or gradient hypotheses. **4.** Optional CC3D run on your sidecar."
                ),
            },
            {
                "title": "What you get",
                "body": (
                    "Charts vs. literature, risk flags, parameter provenance, scaffold geometry "
                    "preview, and a simulation brief you can execute in the cloud when configured."
                ),
            },
        ]
        _n = len(_slides)
        _idx = max(0, min(int(st.session_state.onboarding_slide), _n - 1))
        st.session_state.onboarding_slide = _idx

        st.markdown("##### Explainer")
        _cur = _slides[_idx]
        st.markdown(f"**{_cur['title']}**")
        st.markdown(_cur["body"])

        _c1, _c2, _c3 = st.columns([1, 2, 1])
        with _c1:
            if st.button("Back", key="onb_prev", disabled=_idx <= 0):
                st.session_state.onboarding_slide = _idx - 1
                st.rerun()
        with _c3:
            if st.button("Next", key="onb_next", disabled=_idx >= _n - 1):
                st.session_state.onboarding_slide = _idx + 1
                st.rerun()
        with _c2:
            st.caption(f"Step {_idx + 1} of {_n}")

        st.divider()

        # Protocol upload (collapsed for shorter landing page)
        with st.expander("Optional: upload a protocol (PDF, DOCX, TXT)", expanded=False):
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
        st.subheader("Answer a few questions. Literature-grounded analysis of your biofabrication construct.")

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
            st.session_state.action_plan_narrative = ""
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

        st.title(f"Analysis: {profile.target_tissue or 'Your Construct'}")
        st.caption(
            "Three pillars: feasibility evidence, simulation views, and a methods & materials plan."
        )

        tab_feas, tab_sim, tab_plan = st.tabs(
            ["Feasibility", "Simulation", "Methods & materials plan"]
        )
        with tab_feas:
            render_results_feasibility_tab(profile, report)
        with tab_sim:
            render_results_simulation_tab(profile, report)
        with tab_plan:
            render_results_action_plan_tab(profile, report, save_signup)


# ============================================================================
# Render
# ============================================================================

_render_biosim_tab()
