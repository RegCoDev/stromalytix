"""
Process Intelligence UI for Stromalytix.

Renders the PI dashboard tab in the Streamlit app.
All PI sections are defined here to keep app.py clean.
"""
import streamlit as st


def render_connector_section():
    """Data connector upload section — ELN/CRM/instrument CSV."""
    st.markdown("### 📥 Data Ingestion")
    st.markdown(
        "Connect your lab and business data sources. "
        "Upload CSV exports to begin process analysis."
    )

    sub_tab1, sub_tab2, sub_tab3 = st.tabs(
        ["🧪 ELN / Lab Data", "💼 CRM / Deals", "🔬 Instrument Data"]
    )

    with sub_tab1:
        eln_file = st.file_uploader(
            "Drop Benchling/LabArchives/SciNote CSV here",
            type=["csv"],
            key="eln_upload",
        )
        if eln_file is not None:
            _process_eln_upload(eln_file)
        else:
            st.info(
                "Export your ELN data as CSV. Supported: Benchling, "
                "LabArchives, SciNote, or any CSV with experiment_id, "
                "step, timestamp columns."
            )

    with sub_tab2:
        crm_file = st.file_uploader(
            "Drop HubSpot/Salesforce deal CSV here",
            type=["csv"],
            key="crm_upload",
        )
        if crm_file is not None:
            _process_crm_upload(crm_file)
        else:
            st.info(
                "Export your CRM deals as CSV. Supported: HubSpot, "
                "Salesforce. Include deal stage, amount, and notes columns."
            )

    with sub_tab3:
        inst_file = st.file_uploader(
            "Drop bioprinter/plate reader/rheometer CSV here",
            type=["csv"],
            key="instrument_upload",
        )
        if inst_file is not None:
            _process_instrument_upload(inst_file)
        else:
            st.info(
                "Export your instrument data as CSV. Supported: Cellink, "
                "Allevi, SpectraMax, Synergy, and generic CSV formats."
            )

    # Show loaded event summary
    events = st.session_state.get("pi_events", [])
    if events:
        st.success(f"{len(events)} events loaded")
        case_ids = set(e.case_id for e in events)
        st.caption(f"{len(case_ids)} cases | {len(events)} events")
    else:
        st.warning("No data yet — upload CSV files above to begin process analysis.")


def _process_eln_upload(file):
    """Process an ELN CSV upload."""
    import pandas as pd
    from connectors.eln_csv import ELNCSVConnector

    try:
        df = pd.read_csv(file)
        connector = ELNCSVConnector()
        events = connector.extract(df)
        _merge_events(events, "eln_events")
        st.success(f"Detected {len(events)} experiment events from ELN data")
    except Exception as e:
        st.error(f"Error processing ELN file: {e}")


def _process_crm_upload(file):
    """Process a CRM CSV upload."""
    import pandas as pd
    from connectors.crm_csv import CRMCSVConnector

    try:
        df = pd.read_csv(file)
        connector = CRMCSVConnector()
        events = connector.extract(df)
        _merge_events(events, "crm_events")
        st.success(f"Detected {len(events)} deal events from CRM data")
    except Exception as e:
        st.error(f"Error processing CRM file: {e}")


def _process_instrument_upload(file):
    """Process an instrument CSV upload."""
    import pandas as pd
    from connectors.instrument_csv import InstrumentCSVConnector

    try:
        df = pd.read_csv(file)
        connector = InstrumentCSVConnector()
        events = connector.extract(df)
        _merge_events(events, "instrument_events")
        st.success(f"Detected {len(events)} instrument events")
    except Exception as e:
        st.error(f"Error processing instrument file: {e}")


def _merge_events(new_events, source_key):
    """Merge new events into session state."""
    if source_key not in st.session_state:
        st.session_state[source_key] = []
    st.session_state[source_key] = new_events

    # Merge all event sources into pi_events
    all_events = []
    for key in ["eln_events", "crm_events", "instrument_events"]:
        all_events.extend(st.session_state.get(key, []))
    st.session_state["pi_events"] = all_events


def render_process_mining_section():
    """Process mining dashboard — KPIs, CCPs, batch effects."""
    st.markdown("### ⚙️ Process Intelligence")

    events = st.session_state.get("pi_events", [])
    if not events:
        st.info("No data loaded — upload CSV files above to begin process analysis.")
        return

    from core.process_mining import BiologicalProcessMiner

    miner = BiologicalProcessMiner()
    miner.add_event_log(events, "uploaded")

    # KPI metrics
    kpis = miner.get_kpis("uploaded")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        rate = kpis.get("protocol_conformance_rate", 0)
        st.metric("Protocol Conformance", f"{rate:.0%}" if isinstance(rate, float) else str(rate))
    with col2:
        rate = kpis.get("batch_success_rate", 0)
        st.metric("Batch Success Rate", f"{rate:.0%}" if isinstance(rate, float) else str(rate))
    with col3:
        st.metric("Mean Time to Result", f"{kpis.get('mean_time_to_result', 'N/A')}")
    with col4:
        rate = kpis.get("critical_deviation_rate", 0)
        st.metric("Critical Deviation Rate", f"{rate:.0%}" if isinstance(rate, float) else str(rate))

    # Critical control points
    try:
        ccps = miner.find_critical_control_points("uploaded", "viability")
        if ccps:
            st.markdown("**Critical Control Points:**")
            for i, ccp in enumerate(ccps, 1):
                activity = ccp.get("activity", "unknown")
                corr = ccp.get("outcome_correlation", 0)
                rec = ccp.get("recommendation", "")
                color = "#ff4444" if corr > 0.6 else "#ffd700" if corr > 0.3 else "#00ff88"
                st.markdown(
                    f'<p style="color: {color};">{i}. {activity} — '
                    f'{corr:.2f} correlation | {rec}</p>',
                    unsafe_allow_html=True,
                )
    except Exception:
        pass

    # Batch effects
    try:
        batch_results = miner.detect_batch_effects(events, "batch_id", "viability")
        flagged = {k: v for k, v in batch_results.items() if isinstance(v, dict) and v.get("flagged")}
        if flagged:
            st.markdown("**Batch Effects Detected:**")
            for batch_id, info in flagged.items():
                cv = info.get("cv", 0)
                affected = len(info.get("affected_cases", []))
                st.markdown(
                    f'<p style="color: #ffd700;">Batch {batch_id}: '
                    f'CV = {cv:.0%} | Affects {affected} runs</p>',
                    unsafe_allow_html=True,
                )
    except Exception:
        pass


def render_cross_layer_section():
    """Cross-layer intelligence — business x experimental correlations."""
    st.markdown("### 🔗 Cross-Layer Intelligence")
    st.markdown("Business x Experimental Correlations")

    crm_events = st.session_state.get("crm_events", [])
    eln_events = st.session_state.get("eln_events", [])

    if not crm_events or not eln_events:
        st.info(
            "Upload both CRM and ELN data to unlock cross-layer intelligence. "
            "This is where Stromalytix connects experimental parameters to "
            "business outcomes — which stiffness ranges close deals vs. cause churn."
        )
        return

    from core.process_mining import BiologicalProcessMiner

    miner = BiologicalProcessMiner()
    try:
        correlations = miner.correlate_business_outcomes(eln_events, crm_events)

        # Parameter win rates
        param_win = correlations.get("parameter_win_rates", {})
        if param_win:
            st.markdown("**Parameter Win Rates:**")
            import plotly.graph_objects as go

            params = list(param_win.keys())
            rates = [param_win[p] for p in params]
            fig = go.Figure(go.Bar(
                x=rates, y=params, orientation="h",
                marker_color="#00ff88",
            ))
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#0a0a0a",
                plot_bgcolor="#0a0a0a",
                xaxis_title="Win Rate",
                height=300,
            )
            st.plotly_chart(fig, use_container_width=True)

        # Batch business impact
        batch_impact = correlations.get("batch_business_impact", {})
        if batch_impact:
            st.markdown("**Batch Business Impact:**")
            for batch_id, impact in batch_impact.items():
                st.markdown(f"- Batch {batch_id}: {impact}")

    except Exception as e:
        st.warning(f"Cross-layer analysis error: {e}")


def render_process_graph_section():
    """Process graph visualization with Plotly network view."""
    st.markdown("### 🕸️ Process Intelligence Graph")

    from core.process_graph import ProcessGraph

    graph = ProcessGraph()
    graph_path = "data/process_graph.json"
    try:
        graph.load_from_json(graph_path)
    except Exception:
        pass

    stats = graph.get_stats()

    # Metrics row
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Constructs", stats.get("constructs_analyzed", 0))
    with col2:
        st.metric("Outcomes", stats.get("outcomes_tracked", 0))
    with col3:
        st.metric("Predictions", stats.get("predictions_made", 0))
    with col4:
        st.metric("Deals", stats.get("deals_linked", 0))
    with col5:
        st.metric("Batches", stats.get("batches_tracked", 0))

    # Plotly network graph
    if stats.get("constructs_analyzed", 0) > 0:
        _render_network_graph(graph)
    else:
        st.info(
            "Graph is empty — complete a BioSim analysis to add "
            "your first construct."
        )

    # Manual outcome entry form
    with st.expander("Log an experimental outcome"):
        with st.form("outcome_form"):
            construct_id = st.text_input("Construct ID")
            outcome_type = st.selectbox(
                "Outcome Type",
                ["viability", "stiffness", "cell_count", "gene_expression", "other"],
            )
            value = st.number_input("Value", value=0.0)
            unit = st.text_input("Unit", value="%")
            submitted = st.form_submit_button("Add Outcome")
            if submitted and construct_id:
                graph.add_outcome(construct_id, outcome_type, value, unit)
                graph.export_to_json(graph_path)
                st.success(f"Outcome added: {outcome_type} = {value} {unit}")
                st.rerun()


def _render_network_graph(graph):
    """Render a Plotly network visualization of the process graph."""
    import plotly.graph_objects as go
    import networkx as nx

    G = graph.graph

    pos = nx.spring_layout(G, seed=42)

    # Node type colors
    type_colors = {
        "Construct": "#00ff88",
        "Outcome": "#4488ff",
        "Deal": "#ffd700",
        "Batch": "#888888",
        "Parameter": "#ff8844",
        "Customer": "#ff44ff",
        "Prediction": "#44ffff",
    }

    edge_x, edge_y = [], []
    for u, v in G.edges():
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y, mode="lines",
        line=dict(width=1, color="#444444"),
        hoverinfo="none",
    )

    node_x, node_y, node_text, node_color, node_size = [], [], [], [], []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        data = G.nodes[node]
        ntype = data.get("type", "unknown")
        node_text.append(f"{node}<br>Type: {ntype}")
        node_color.append(type_colors.get(ntype, "#ffffff"))
        node_size.append(max(10, G.degree(node) * 5))

    node_trace = go.Scatter(
        x=node_x, y=node_y, mode="markers+text",
        marker=dict(size=node_size, color=node_color, line=dict(width=1, color="#222")),
        text=[n for n in G.nodes()],
        textposition="top center",
        textfont=dict(size=8, color="#aaaaaa"),
        hovertext=node_text,
        hoverinfo="text",
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0a0a0a",
        plot_bgcolor="#0a0a0a",
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=400,
        margin=dict(l=0, r=0, t=0, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_simulation_stack_section():
    """Simulation stack status panel with live CC3D detection."""
    st.markdown("### ⚡ Simulation Stack")

    from core.cc3d_runner import verify_cc3d_installation

    cc3d_status = verify_cc3d_installation()

    stack = [
        {
            "name": "CC3D (Cellular Potts Model)",
            "desc": "Emergent cell behavior — brief generation live",
            "arc": "Arc 1",
            "live": cc3d_status["installed"],
            "beta": not cc3d_status["installed"],
            "status": "Live" if cc3d_status["installed"] else "Brief generation live, execution requires CC3D install",
        },
        {
            "name": "scikit-fem (FEA)",
            "desc": "Scaffold mechanics — stiffness prediction",
            "arc": "Arc 2",
            "live": True,
            "beta": False,
            "status": "Live — scaffold deformation prediction",
        },
        {
            "name": "OpenMM (Molecular Dynamics)",
            "desc": "ECM dynamics — RGD accessibility",
            "arc": "Arc 3",
            "live": False,
            "beta": False,
            "status": "Planned Q3 2026",
        },
        {
            "name": "ProDy NMA (Protein Flexibility)",
            "desc": "Protein conformation under load",
            "arc": "Arc 3",
            "live": False,
            "beta": False,
            "status": "Planned Q3 2026",
        },
        {
            "name": "AlphaFold (Druggability)",
            "desc": "Cryptic binding site prediction",
            "arc": "Arc 4",
            "live": False,
            "beta": False,
            "status": "Planned Q4 2026",
        },
    ]

    for item in stack:
        if item["live"]:
            icon = "✅"
            color = "#00ff88"
        elif item["beta"]:
            icon = "🔶"
            color = "#ffd700"
        else:
            icon = "🔧"
            color = "#666666"

        st.markdown(
            f'<div style="border: 1px solid {color}; padding: 0.8rem; border-radius: 0.5rem; '
            f'background: #111; margin: 0.5rem 0;">'
            f'<strong style="color: {color};">{icon} {item["name"]}</strong> '
            f'<span style="color: #888; float: right;">{item["arc"]}</span><br>'
            f'<span style="color: #aaa;">{item["desc"]}</span><br>'
            f'<span style="color: {color}; font-size: 0.85em;">{item["status"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


def render_algorithm_router_section():
    """Algorithm Router — data quality report and routing decision."""
    st.markdown("### 🧭 Algorithm Router")

    events = st.session_state.get("pi_events", [])
    if not events:
        st.info("Upload data above to see algorithm routing analysis.")
        return

    from core.bio_process_miner import BiologicalProcessMiner

    miner = BiologicalProcessMiner()
    miner.add_event_log(events, "uploaded")

    try:
        report = miner.get_data_quality_report("uploaded")
    except Exception as e:
        st.warning(f"Could not generate data quality report: {e}")
        return

    char = report.get("characterization", {})
    routing = report.get("routing", {})

    # Data quality metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Cases", char.get("case_count", 0))
    with col2:
        st.metric("Variants", char.get("variant_count", 0))
    with col3:
        vr = char.get("variant_ratio", 0)
        st.metric("Variant Ratio", f"{vr:.2f}" if isinstance(vr, float) else str(vr))
    with col4:
        st.metric("Precision", char.get("timestamp_precision", "unknown"))

    # Algorithm selection
    algo = routing.get("algorithm", "unknown")
    rationale = routing.get("rationale", "")
    st.markdown(f"**Selected algorithm:** `{algo}` — {rationale}")

    # Warnings
    warnings = char.get("warnings", [])
    if warnings:
        st.markdown("**Data Quality Warnings:**")
        for w in warnings:
            st.markdown(f"- ⚠️ {w}")

    # Characteristics
    with st.expander("Full characterization"):
        st.json(char)


def render_convergent_signals_section():
    """Convergent signals — simulation x empirical overlap."""
    st.markdown("### 🎯 Convergent Signals")

    # Load active company context
    company = st.session_state.get("pi_company_select")
    if not company:
        st.info("Select a company context above to see convergent signals.")
        return

    from core.company_context import CompanyContext
    from core.sim_process_bridge import detect_convergent_signals, get_p1_alerts

    try:
        ctx = CompanyContext.load(company)
    except Exception:
        st.info("No company context loaded.")
        return

    signals = detect_convergent_signals(ctx)
    p1_alerts = get_p1_alerts(ctx)

    if p1_alerts:
        for alert in p1_alerts:
            st.error(f"🚨 **P1 ALERT:** {alert['summary']}")
            for ev in alert.get("evidence", []):
                st.markdown(f"  - {ev}")

    if signals:
        for sig in signals:
            if sig in p1_alerts:
                continue  # already shown
            color = {"high": "#ff4444", "medium": "#ffd700", "low": "#888888"}.get(
                sig["confidence"], "#888888"
            )
            st.markdown(
                f'<p style="color: {color};">● {sig["signal_type"]}: '
                f'{sig["summary"]}</p>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No convergent signals detected yet. Add predictions and outcomes to generate.")


def render_pi_chat_section():
    """PI Chat — context-grounded conversational analyst."""
    st.markdown("### 💬 Process Intelligence Chat")

    from core.pi_chat import get_available_companies, build_pi_system_prompt

    # Company selector
    companies = get_available_companies()
    if not companies:
        # Create centara demo if nothing exists
        from core.company_context import create_centara_demo_context
        create_centara_demo_context()
        companies = get_available_companies()

    selected = st.selectbox(
        "Company Context",
        companies,
        key="pi_company_select",
    )

    if not selected:
        st.info("No company context available.")
        return

    # Load context
    from core.company_context import CompanyContext
    try:
        ctx = CompanyContext.load(selected)
    except Exception as e:
        st.error(f"Failed to load context: {e}")
        return

    # Show context summary
    with st.expander("Current Context", expanded=False):
        st.text(ctx.to_chat_context_string())

    # Chat history in session state
    history_key = f"pi_chat_{selected}"
    if history_key not in st.session_state:
        st.session_state[history_key] = []

    # Display chat history
    for msg in st.session_state[history_key]:
        role = msg["role"]
        with st.chat_message(role):
            st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input(
        "Ask about process data, lot issues, hypotheses...",
        key="pi_chat_input",
    )

    if user_input:
        # Display user message
        st.session_state[history_key].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Get PI response
        try:
            import os
            api_key = None
            try:
                api_key = st.secrets.get("ANTHROPIC_API_KEY")
            except Exception:
                api_key = os.getenv("ANTHROPIC_API_KEY")

            from core.pi_chat import send_pi_message
            result = send_pi_message(
                context=ctx,
                user_message=user_input,
                chat_history=st.session_state[history_key][:-1],
                api_key=api_key,
            )

            response = result["response"]
            st.session_state[history_key].append({"role": "assistant", "content": response})
            with st.chat_message("assistant"):
                st.markdown(response)

            # Show hypothesis/evidence notifications
            if result["new_hypotheses"]:
                for h in result["new_hypotheses"]:
                    st.toast(f"New hypothesis created: {h[:60]}...")
            if result["evidence_updates"]:
                for ev in result["evidence_updates"]:
                    st.toast(f"Evidence logged ({ev['direction']}): {ev['evidence'][:60]}...")

        except Exception as e:
            st.error(f"PI Chat error: {e}")


def render_pi_further_reading_section():
    """Further Reading in PI context — APQC signals from loaded data."""
    st.markdown("### 📚 Further Reading")

    from core.reading_engine import ReadingEngine

    engine = ReadingEngine()

    # Collect PI signals from loaded events
    events = st.session_state.get("pi_events", [])
    pi_signals = set()

    if events:
        from core.process_mining import BiologicalProcessMiner
        miner = BiologicalProcessMiner()
        miner.add_event_log(events, "uploaded")
        kpis = miner.get_kpis("uploaded")

        # Map KPIs to signals
        if kpis.get("critical_deviation_rate", 0) > 0.1:
            pi_signals.add("protocol_deviation")
            pi_signals.add("conformance_failure")
        if kpis.get("batch_success_rate", 1) < 0.8:
            pi_signals.add("batch_effect")
            pi_signals.add("high_cv")
        if kpis.get("protocol_conformance_rate", 1) < 0.9:
            pi_signals.add("conformance_failure")

        # Check for batch effects
        try:
            batch_results = miner.detect_batch_effects(events, "batch_id", "viability")
            flagged = {k: v for k, v in batch_results.items() if isinstance(v, dict) and v.get("flagged")}
            if flagged:
                pi_signals.add("batch_effect")
                pi_signals.add("high_cv")
        except Exception:
            pass

    if not pi_signals:
        pi_signals = {"parameter_out_of_range"}

    biz_results = engine.get_business_reading(list(pi_signals))

    if biz_results:
        for item in biz_results:
            with st.expander(f"**{item['pcf_id']}** — {item['pcf_name']}", expanded=False):
                st.markdown(f"**Signals:** {', '.join(item['triggered_by'])}")
                st.markdown(item["best_practice_summary"])
                if item.get("key_metrics"):
                    st.markdown("**Key Metrics:** " + ", ".join(item["key_metrics"]))
                if item.get("reading"):
                    for ref in item["reading"]:
                        title = ref.get("title", "Untitled")
                        doi = ref.get("doi")
                        if doi:
                            st.markdown(f"  - [{title}](https://doi.org/{doi})")
                        else:
                            st.markdown(f"  - {title}")
    else:
        st.info("Upload process data above to get signal-driven reading recommendations.")


def render_pi_dashboard():
    """Main PI dashboard — all sections connected."""
    st.markdown("## 📊 Process Intelligence Platform")
    st.markdown(
        "Connect your lab and business data to surface "
        "process deviations, predict experimental outcomes, "
        "and correlate protocol parameters with business results."
    )

    render_pi_chat_section()
    st.divider()
    render_connector_section()
    st.divider()
    render_algorithm_router_section()
    st.divider()
    render_process_mining_section()
    st.divider()
    render_convergent_signals_section()
    st.divider()
    render_pi_further_reading_section()
    st.divider()
    render_cross_layer_section()
    st.divider()
    render_process_graph_section()
    st.divider()
    render_simulation_stack_section()
