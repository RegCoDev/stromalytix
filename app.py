"""
Stromalytix — BioSim Copilot

Main Streamlit application for 3D cell culture variance analysis.
"""

import csv
import json
import os
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
    st.markdown("**The Operating System for Human Tissue Engineering**")
    st.divider()

    # Show selected persona if available
    if st.session_state.persona:
        persona_labels = {
            "academic": "🎓 Academic Researcher",
            "pharma_biotech": "💊 Pharma / Biotech",
            "hardware_service": "🔬 Hardware / Service Provider"
        }
        st.markdown(f'<p style="color: #00ff88; font-size: 0.9em;"><strong>Role:</strong> {persona_labels.get(st.session_state.persona, "Unknown")}</p>', unsafe_allow_html=True)
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
            **Stromalytix** is a decision intelligence platform for tissue engineers.

            We help you de-risk 3D cell culture protocols by benchmarking your
            construct parameters against published literature.

            Think Palantir Foundry for bioengineering.
            """
        )


# ============================================================================
# MAIN AREA — Two-tab layout
# ============================================================================

from core.pi_ui import render_pi_dashboard


def _render_biosim_tab():
    """Render the BioSim Copilot tab — all existing app logic."""
    if st.session_state.phase == "onboarding":
        # ========================================================================
        # PHASE: ONBOARDING (Welcome Screen + Persona Selection)
        # ========================================================================

        st.title("Welcome to Stromalytix")
        st.markdown("### The Operating System for Human Tissue Engineering")

        st.markdown("""
        **Stromalytix** is a decision intelligence platform that helps tissue engineers de-risk
        3D cell culture protocols by benchmarking against published literature.

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
        st.markdown("### 📄 Upload Your Protocol (Optional)")
        uploaded_file = st.file_uploader(
            "Upload your protocol (optional)",
            type=["pdf", "docx"],
            help="We'll extract construct parameters automatically.",
        )
        if uploaded_file is not None:
            try:
                from core.ingest import extract_text_from_pdf, extract_text_from_docx, parse_protocol_to_profile
                file_bytes = uploaded_file.read()
                if uploaded_file.name.lower().endswith(".pdf"):
                    text = extract_text_from_pdf(file_bytes)
                else:
                    text = extract_text_from_docx(file_bytes)
                detected = parse_protocol_to_profile(text)
                st.success("Detected from protocol:")
                cols = st.columns(2)
                for i, (k, v) in enumerate(detected.items()):
                    if v is not None:
                        cols[i % 2].markdown(f"**{k}**: {v}")
                # Pre-populate session state
                for k, v in detected.items():
                    if v is not None and k in ConstructProfile.model_fields:
                        setattr(st.session_state.construct_profile, k, v)
            except Exception as e:
                st.warning(f"Could not parse protocol: {e}")

        st.divider()

        # Persona Selection
        st.markdown("### 👤 Select Your Role")
        st.markdown("Help us tailor the experience to your workflow:")

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
                st.session_state.chain = initialize_chat()
                # Get the initial greeting
                if len(st.session_state.messages) == 0:
                    # The chain already has the first exchange, get it from memory
                    memory_vars = st.session_state.chain.memory.load_memory_variables({})
                    if "history" in memory_vars and len(memory_vars["history"]) > 0:
                        # Get the assistant's greeting
                        initial_response = memory_vars["history"][-1].content
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": initial_response
                        })

        # Render chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

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
                    st.markdown(assistant_response)

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
                import os

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
      "experimental_goal": "disease_modeling | drug_screening | basic_research or null"
    }}

    Conversation:
    {conversation_text[:1000]}

    Return ONLY the JSON, no other text."""

                try:
                    response = llm.invoke(extraction_prompt)
                    import json
                    import re
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

        # Row 3.5: 3D Construct Visualization
        st.markdown("### 🧬 Construct Visualization")
        st.caption("Parameter-driven 3D cell arrangement. Reflects your confirmed profile.")

        viz_col1, viz_col2 = st.columns([3, 1])
        with viz_col2:
            show_scaffold = st.toggle("Show scaffold", value=True, key="viz_scaffold")

        try:
            from core.tissue_viz import render_construct_3d
            viz_title = f"{profile.target_tissue or 'Construct'}"
            fig_3d = render_construct_3d(
                profile=profile,
                title=viz_title,
                show_scaffold=show_scaffold,
            )
            st.plotly_chart(fig_3d, use_container_width=True)

            stat_cols = st.columns(4)
            stat_cols[0].metric("Cell Types", len(profile.cell_types or []))
            density = profile.cell_density_per_ml or 0
            stat_cols[1].metric("Density", f"{density/1e6:.1f}M/mL" if density else "—")
            stat_cols[2].metric("Stiffness", f"{profile.stiffness_kpa} kPa" if profile.stiffness_kpa else "—")
            stat_cols[3].metric("Scaffold", profile.scaffold_material or "—")
        except Exception as e:
            st.warning(f"Visualization error: {e}")

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

        # Row 3.8: Hepatic DILI Detection Intelligence (if hepatic tissue)
        tissue_lower = (profile.target_tissue or "").lower()
        cell_str_lower = " ".join(profile.cell_types or []).lower()
        hepatic_keywords = ["hepat", "liver", "hepg", "hepar", "heparg", "albumin"]
        if any(kw in tissue_lower or kw in cell_str_lower for kw in hepatic_keywords):
            try:
                from core.hepatic_intelligence import predict_hepatic_quality
                st.markdown("### 🫀 Hepatic DILI Detection Intelligence")
                hq = predict_hepatic_quality(profile)

                h1, h2, h3 = st.columns(3)
                h1.metric(
                    "DILI Sensitivity",
                    f"{hq.predicted_dilirank_sensitivity:.0%}",
                    help="Predicted % of DILIrank high-concern compounds detected",
                )
                h2.metric("Specificity", f"{hq.predicted_specificity:.0%}")
                h3.metric(
                    "F1 Score", f"{hq.f1_score:.2f}",
                    help="Balanced DILI detection performance",
                )

                st.caption(hq.benchmark_comparison)

                if hq.optimization_recommendations:
                    with st.expander("Optimization Recommendations"):
                        for rec in hq.optimization_recommendations:
                            st.markdown(f"- {rec}")

                if hq.key_drivers:
                    with st.expander("Performance Drivers"):
                        for d in hq.key_drivers:
                            st.markdown(f"- {d}")

                st.session_state["hepatic_quality_score"] = hq
            except Exception as e:
                st.warning(f"Hepatic intelligence unavailable: {e}")

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

            # Parameter confidence note (subtle gray info box)
            st.markdown(
                '<div style="border: 1px solid #444444; padding: 0.8rem; border-radius: 0.5rem; background: #1a1a1a; margin: 1rem 0;">'
                '<strong style="color: #888888;">⚗️ Parameter Confidence Note:</strong> '
                '<span style="color: #aaaaaa;">CC3D parameters are estimated from published in vivo and in vitro models. '
                'Absolute values should be treated as starting points requiring experimental calibration. '
                'Qualitative predictions (cell organization patterns, failure modes, relative comparisons) are well-grounded in literature. '
                'Quantitative predictions (exact timing, specific percentages) require validation against your specific bioink and cell line. '
                'Join the waitlist to contribute calibration data to the Stromalytix parameter database.</span>'
                '</div>',
                unsafe_allow_html=True
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

            # CC3D Live Execution
            from core.cc3d_runner import verify_cc3d_installation, run_cc3d_simulation
            cc3d_status = verify_cc3d_installation()
            if cc3d_status["installed"]:
                if st.button("⚡ Run CC3D Preview (Beta)", use_container_width=True):
                    with st.spinner("Running CC3D simulation..."):
                        cc3d_result = run_cc3d_simulation(sim_brief, timeout=120)
                        if cc3d_result["success"]:
                            st.success(f"CC3D completed: {cc3d_result['mcs_completed']} MCS in {cc3d_result['duration_seconds']}s")
                            if cc3d_result["output"]:
                                st.code(cc3d_result["output"], language="text")
                        else:
                            st.warning(f"CC3D: {cc3d_result.get('error', 'Unknown error')}")
            else:
                st.button(
                    "⚡ Run CC3D Preview (Beta)",
                    disabled=True,
                    use_container_width=True,
                    help="CC3D not configured — install at compucell3d.org to enable live simulation."
                )
        else:
            st.warning("Simulation brief could not be generated. Check your API key and try again.")

        # Row 4.5: Further Reading (context-driven)
        st.divider()
        st.markdown("### 📚 Further Reading")
        st.caption("Context-driven recommendations based on your construct profile.")

        try:
            from core.reading_engine import ReadingEngine
            _reading_engine = ReadingEngine()

            reading_tab_biz, reading_tab_sci, reading_tab_search = st.tabs(
                ["Business Best Practices", "Scientific Literature", "Search"]
            )

            with reading_tab_biz:
                # Use PI signals from variance report if available
                pi_signals = []
                if report and report.risk_flags:
                    signal_map = {
                        "stiffness": "parameter_out_of_range",
                        "porosity": "parameter_out_of_range",
                        "density": "parameter_out_of_range",
                        "viability": "viability_below_threshold",
                        "variance": "high_cv",
                        "batch": "batch_effect",
                    }
                    for flag in report.risk_flags:
                        flag_lower = flag.get("parameter", "").lower() if isinstance(flag, dict) else str(flag).lower()
                        for kw, signal in signal_map.items():
                            if kw in flag_lower and signal not in pi_signals:
                                pi_signals.append(signal)
                if not pi_signals:
                    pi_signals = ["parameter_out_of_range"]

                biz_results = _reading_engine.get_business_reading(pi_signals)
                if biz_results:
                    for item in biz_results:
                        with st.expander(f"**{item['pcf_id']}** — {item['pcf_name']}", expanded=False):
                            st.markdown(f"**Category:** {item['pcf_category']} > {item['pcf_subcategory']}")
                            st.markdown(f"**Triggered by:** {', '.join(item['triggered_by'])}")
                            st.markdown(item["best_practice_summary"])
                            if item.get("key_metrics"):
                                st.markdown("**Key Metrics:** " + ", ".join(item["key_metrics"]))
                            if item.get("reading"):
                                st.markdown("**References:**")
                                for ref in item["reading"]:
                                    title = ref.get("title", "Untitled")
                                    doi = ref.get("doi")
                                    if doi:
                                        st.markdown(f"- [{title}](https://doi.org/{doi})")
                                    else:
                                        st.markdown(f"- {title}")
                else:
                    st.info("No business track matches for current signals.")

            with reading_tab_sci:
                sci_results = _reading_engine.get_scientific_reading(profile=profile)
                if sci_results:
                    for item in sci_results:
                        entry = item["entry"]
                        with st.expander(f"**{entry['title']}**", expanded=False):
                            st.markdown(f"**Collection:** {item['collection']}")
                            if entry.get("authors"):
                                st.markdown(f"**Authors:** {entry['authors']}")
                            if entry.get("journal"):
                                st.markdown(f"**Journal:** {entry['journal']} ({entry.get('year', '')})")
                            if entry.get("doi"):
                                st.markdown(f"**DOI:** [https://doi.org/{entry['doi']}](https://doi.org/{entry['doi']})")
                            if entry.get("note"):
                                st.markdown(f"*{entry['note']}*")
                            st.markdown(f"**Match reasons:** {', '.join(item['match_reasons'])}")
                            st.markdown(f"**Level:** {entry.get('level', 'N/A')}")
                else:
                    st.info("No scientific reading matches for current profile.")

            with reading_tab_search:
                search_query = st.text_input(
                    "Search reading databases",
                    placeholder="e.g. bioprinting, GelMA, process control...",
                    key="reading_search"
                )
                if search_query:
                    search_results = _reading_engine.search(search_query)
                    if search_results:
                        for item in search_results:
                            if item["track"] == "scientific":
                                entry = item["entry"]
                                st.markdown(
                                    f"**[SCI]** {entry['title']} "
                                    f"({item['collection']})"
                                )
                            else:
                                st.markdown(
                                    f"**[BIZ]** {item.get('pcf_id', '')} — {item.get('name', '')}"
                                )
                    else:
                        st.info("No results found.")
        except Exception as e:
            st.warning(f"Further reading unavailable: {e}")

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
                from core.export import export_figure_png
                from core.tissue_viz import render_construct_3d
                viz_fig = render_construct_3d(profile=profile, title=profile.target_tissue or "Construct")
                png_bytes = export_figure_png(viz_fig)
                st.download_button(
                    "Download 3D Visualization (PNG)",
                    data=png_bytes,
                    file_name=f"stromalytix_{profile.target_tissue or 'construct'}_3d.png",
                    mime="image/png",
                    use_container_width=True,
                )
            except Exception as e:
                st.button("Download 3D Viz (PNG)", disabled=True, use_container_width=True,
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


def _render_materials_tab():
    """Materials Intelligence tab — bioink lot QC predictions."""
    st.header("Materials Intelligence")
    st.caption("Predict customer outcomes from bioink lot characterization data")

    with st.form("lot_characterization"):
        col1, col2 = st.columns(2)
        with col1:
            lot_id = st.text_input("Lot ID", value="LOT-2024-001")
            material_name = st.selectbox(
                "Material",
                ["GelMA 6%", "GelMA 4%", "Fibrin 10mg/mL", "Collagen I",
                 "Alginate 2%", "PEGDA", "Other"],
            )
            storage_modulus = st.number_input(
                "Storage Modulus G' (Pa)", min_value=0.0, value=0.0, step=100.0,
                help="Leave 0 to use material defaults",
            )
            loss_modulus = st.number_input(
                "Loss Modulus G'' (Pa)", min_value=0.0, value=0.0, step=100.0,
            )
            viscosity = st.number_input(
                "Viscosity at 37°C (Pa·s)", min_value=0.0, value=0.0, step=10.0,
            )
        with col2:
            gelation_time = st.number_input(
                "Gelation Time (s)", min_value=0.0, value=0.0, step=5.0,
            )
            swelling_ratio = st.number_input(
                "Swelling Ratio", min_value=0.0, value=0.0, step=0.1,
            )
            degradation_rate = st.number_input(
                "Degradation Rate (day⁻¹)", min_value=0.0, value=0.0, step=0.5,
            )
            uv_dose = st.number_input(
                "UV Dose (mW/cm²·s)", min_value=0.0, value=0.0, step=5.0,
            )
            crosslink_density = st.number_input(
                "Crosslink Density", min_value=0.0, value=0.0, step=0.01,
            )
        submitted = st.form_submit_button("Predict Lot Performance")

    if submitted:
        from core.materials_intelligence import (
            BioinkLotCharacterization,
            predict_lot_performance,
        )

        char = BioinkLotCharacterization(
            lot_id=lot_id,
            material_name=material_name,
            storage_modulus_pa=storage_modulus or None,
            loss_modulus_pa=loss_modulus or None,
            viscosity_pas_at_37c=viscosity or None,
            gelation_time_s=gelation_time or None,
            swelling_ratio=swelling_ratio or None,
            degradation_rate_day=degradation_rate or None,
            uv_dose_mwcm2_s=uv_dose or None,
            crosslink_density=crosslink_density or None,
        )
        report = predict_lot_performance(char)

        # Release decision banner
        color_map = {"RELEASE": "green", "CONDITIONAL": "orange", "HOLD": "red"}
        icon_map = {"RELEASE": "✅", "CONDITIONAL": "⚠️", "HOLD": "🛑"}
        st.markdown(
            f"### {icon_map[report.release_recommendation]} "
            f"Lot {report.lot_id}: **{report.release_recommendation}**"
        )
        st.info(report.release_rationale)

        # Key metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Predicted Stiffness", f"{report.predicted_stiffness_kpa} kPa",
                   delta=f"± {report.stiffness_uncertainty_kpa}")
        m2.metric("Printability Score", f"{report.predicted_printability_score:.2f}")
        m3.metric("Day-3 Viability", f"{report.predicted_cell_viability_day3_pct:.0f}%")
        m4.metric("Day-7 Viability", f"{report.predicted_cell_viability_day7_pct:.0f}%")

        # Process recommendations
        st.subheader("Process Recommendations")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Nozzle Diameter", f"{report.recommended_nozzle_diameter_mm} mm")
        r2.metric("Print Speed", f"{report.recommended_print_speed_mms} mm/s")
        r3.metric("Crosslink Time", f"{report.recommended_crosslink_time_s:.0f} s")
        r4.metric("Cell Density", f"{report.recommended_cell_density_per_ml:,.0f} /mL")

        # Confidence and data gaps
        st.subheader("Confidence Assessment")
        st.write(f"**Confidence:** {report.confidence.upper()}")
        if report.data_gaps:
            st.warning("**Data gaps:**")
            for gap in report.data_gaps:
                st.write(f"- {gap}")
        else:
            st.success("Full characterization data provided — high confidence predictions.")


# ============================================================================
# Render tabs
# ============================================================================

tab_biosim, tab_pi, tab_materials = st.tabs(
    ["🔬 BioSim Copilot", "📊 Process Intelligence", "🧪 Materials Intelligence"]
)

with tab_biosim:
    _render_biosim_tab()

with tab_pi:
    render_pi_dashboard()

with tab_materials:
    _render_materials_tab()
