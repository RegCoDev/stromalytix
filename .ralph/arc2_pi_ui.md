# Ralph Loop: Sim Brief Fix + Process Intelligence UI
# File: .ralph/arc2_pi_ui.md

**Read STRATEGY.md before writing a single line of code.**
This sprint exposes the PI platform to users. The Streamlit app
currently shows only the BioSim chat flow. Everything built in
the last sprint (connectors, process mining, process graph, KPI
dashboard) needs a frontend. This sprint builds it.

**Completion Promise**:
Output "DONE: PI UI sprint complete" when checklist passes.

---

## PRE-FLIGHT

```bash
git add -A && git commit -m "pre-ralph PI-UI checkpoint"
uv run pytest tests/ -v --tb=short 2>&1 | tail -5
```

Must be 59/59 before proceeding. Fix any regressions first.

---

## PRIORITY 1: Fix Simulation Brief Not Firing

The simulation brief panel exists in app.py results phase but
the checklist item for it never checks off. Diagnose and fix.

Steps:
1. Read app.py results phase carefully. Find where
   generate_simulation_brief() is called and where the
   checklist item "Simulation brief ready" is set.
2. The bug is likely one of:
   - generate_simulation_brief() is called but its return
     value isn't stored in st.session_state
   - The checklist checks the wrong session_state key
   - The function is only called conditionally and the
     condition is never met
3. Fix the root cause. Do not patch around it.
4. Also verify: if generate_simulation_brief() throws an
   exception (e.g. API timeout), the app should show a
   graceful error in the simulation brief panel, not a
   blank panel and a broken checklist.

Write test: tests/test_sim_brief.py::test_sim_brief_fires
  - Mock generate_simulation_brief() to return a valid dict
  - Verify session_state["simulation_brief"] is set after
    the results phase logic runs
  - Verify session_state["sim_brief_ready"] == True

Commit: "fix: simulation brief fires and checklist updates correctly"

---

## PRIORITY 2: Multi-Tab App Architecture

The app currently has one flow. Add a second tab for the
Process Intelligence dashboard. Keep the existing BioSim flow
exactly as-is — do not break it.

In app.py, wrap existing content in tabs:

```python
tab1, tab2 = st.tabs(["🔬 BioSim Copilot", "📊 Process Intelligence"])

with tab1:
    # ALL existing app logic goes here unchanged

with tab2:
    # New PI dashboard (built in P3-P7)
    render_pi_dashboard()
```

Create core/pi_ui.py with render_pi_dashboard() function.
This keeps app.py clean.

Write test: tests/test_pi_ui.py::test_pi_ui_module_importable
  - from core.pi_ui import render_pi_dashboard
  - assert callable(render_pi_dashboard)

Commit: "feat: multi-tab app — BioSim + Process Intelligence tabs"

---

## PRIORITY 3: Data Connector Upload UI

The first section of the PI dashboard.
Users upload CSV exports from their ELN, CRM, or instruments.

In core/pi_ui.py, add render_connector_section():

```
┌─────────────────────────────────────────────────────┐
│  📥 Data Ingestion                                   │
│                                                      │
│  Connect your lab and business data sources.         │
│  Upload CSV exports to begin process analysis.       │
│                                                      │
│  [ELN / Lab Data]  [CRM / Deals]  [Instrument Data] │
│                                                      │
│  ELN Upload:                                         │
│  ┌──────────────────────────────────────────────┐   │
│  │  Drop Benchling/LabArchives CSV here         │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  Detected: 23 experiments, 4 protocol versions      │
│  Date range: Jan 2024 – Mar 2026                    │
│  ✅ 23 events loaded                                │
└─────────────────────────────────────────────────────┘
```

Implementation:
1. Three st.file_uploader widgets (ELN, CRM, Instrument)
   each accepting CSV
2. On upload: run the appropriate connector
   (ELNCSVConnector, CRMCSVConnector, InstrumentCSVConnector)
3. Store loaded ProcessEvents in st.session_state["pi_events"]
4. Show summary: event count, case count, date range,
   detected activities
5. Show "⚠️ No data yet" placeholder when empty with
   instructions for exporting from Benchling/HubSpot/Cellink
6. Dark theme matching BioSim — #0a0a0a bg, #00ff88 accents

Write tests/test_pi_ui.py::test_connector_section_renders:
  - render_connector_section() callable, no import errors

Commit: "feat: data connector upload UI — ELN/CRM/instrument CSV"

---

## PRIORITY 4: Process Mining Dashboard

Second section of the PI dashboard.
Shows process discovery, conformance, and KPI results.
Only active when events are loaded (P3).

In core/pi_ui.py, add render_process_mining_section():

```
┌─────────────────────────────────────────────────────┐
│  ⚙️ Process Intelligence                             │
│                                                      │
│  Protocol Conformance Rate    Batch Success Rate     │
│  ████████████░░░░  78%        ████████░░░░░░  65%   │
│                                                      │
│  Mean Time to Result: 4.2 days                      │
│  Critical Deviation Rate: 12%                       │
│                                                      │
│  🔴 Critical Control Points                         │
│  ┌──────────────────────────────────────────────┐  │
│  │ 1. cell_seeding — 0.73 correlation w/        │  │
│  │    viability. Deviation freq: 34%            │  │
│  │    → Tighten cell density tolerance          │  │
│  │ 2. scaffold_gelation — 0.61 correlation...   │  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
│  🟡 Batch Effects Detected                          │
│  Batch lot_47: viability CV = 18% (threshold: 10%) │
│  Affects 4 experimental runs                        │
└─────────────────────────────────────────────────────┘
```

Implementation:
1. Load events from st.session_state["pi_events"]
2. Instantiate BiologicalProcessMiner, add events
3. Run get_kpis() — display as metric cards
4. Run find_critical_control_points() — display as ranked list
   with colored risk indicators
5. Run detect_batch_effects() — display flagged batches
6. "No data loaded — upload CSV files above" if no events
7. All dark theme, #00ff88 for good metrics, #ff4444 for flags

Write tests/test_pi_ui.py::test_process_mining_section_renders

Commit: "feat: process mining dashboard — KPIs, CCPs, batch effects"

---

## PRIORITY 5: Cross-Layer Intelligence Panel

Third section. The novel insight — business outcomes connected
to experimental parameters. This is what no LIMS or ELN shows.

In core/pi_ui.py, add render_cross_layer_section():

```
┌─────────────────────────────────────────────────────┐
│  🔗 Cross-Layer Intelligence                        │
│                                                      │
│  Business × Experimental Correlations               │
│                                                      │
│  Parameter Win Rate (requires CRM + ELN data)       │
│  stiffness_kpa 6–12: 78% deal win rate              │
│  stiffness_kpa <4:   23% deal win rate              │
│                                                      │
│  Batch Business Impact                               │
│  lot_47 → 2 churned customers (viability CV 18%)   │
│  lot_23-41 → 4 closed deals (viability CV 4%)      │
│                                                      │
│  Protocol Version Revenue                           │
│  v3.1: $48K closed deals | v3.2: $12K (3 churns)  │
│                                                      │
│  ⚠️ Requires both CRM and ELN data to activate     │
└─────────────────────────────────────────────────────┘
```

Implementation:
1. Only show full panel when BOTH crm_events AND eln_events
   are in session_state
2. Call process_miner.correlate_business_outcomes()
3. Display parameter win rates as horizontal bar chart
   (Plotly, dark theme)
4. Display batch business impact table
5. Show "Upload both CRM and ELN data to unlock cross-layer
   intelligence" when only one source is loaded

Write tests/test_pi_ui.py::test_cross_layer_section_renders

Commit: "feat: cross-layer intelligence panel — business × experimental"

---

## PRIORITY 6: Process Graph Visualization

Fourth section. Visual representation of the PI graph.

In core/pi_ui.py, add render_process_graph_section():

```
┌─────────────────────────────────────────────────────┐
│  🕸️ Process Intelligence Graph                      │
│                                                      │
│  Constructs: 12  Outcomes: 34  Predictions: 8       │
│  Deals linked: 6  Batches tracked: 4                │
│  Prediction accuracy: 71% (8 validated)             │
│                                                      │
│  [Plotly network graph visualization]               │
│  Nodes: Construct (green), Outcome (blue),          │
│         Deal (gold), Batch (gray)                   │
│  Edges: colored by relationship type                │
│                                                      │
│  Recently added:                                     │
│  • Construct c_001 → Outcome: viability 87%        │
│  • Construct c_001 → Deal: Cytoink POC ($2,900)    │
└─────────────────────────────────────────────────────┘
```

Implementation:
1. Load ProcessGraph from data/process_graph.json
2. Get stats via graph.get_stats() — display as metrics
3. Render network graph using Plotly (not networkx draw —
   Plotly is already imported and dark-theme compatible)
   - Nodes sized by connection count
   - Color by node type
   - Hover shows node details
4. Show "Graph is empty — complete a BioSim analysis to
   add your first construct" when empty
5. Add a manual entry form:
   "Log an experimental outcome" — construct_id, outcome_type,
   value, unit → calls graph.add_outcome() → saves to JSON

Write tests/test_pi_ui.py::test_process_graph_section_renders

Commit: "feat: process graph visualization with Plotly network view"

---

## PRIORITY 7: Simulation Stack Status Panel

Fifth section. Shows the simulation stack build status.
Makes the roadmap visible and the platform claim credible.

In core/pi_ui.py, add render_simulation_stack_section():

```
┌─────────────────────────────────────────────────────┐
│  ⚡ Simulation Stack                                 │
│                                                      │
│  ✅ CC3D (Cellular Potts Model)                     │
│     Emergent cell behavior · Brief generation live  │
│     Live execution: Beta                            │
│                                                      │
│  🔧 scikit-fem (FEA)                    Arc 2       │
│     Scaffold mechanics · Stiffness prediction       │
│     Status: Planned Q2 2026                         │
│                                                      │
│  🔧 OpenMM (Molecular Dynamics)         Arc 3       │
│     ECM dynamics · RGD accessibility               │
│     Status: Planned Q3 2026                         │
│                                                      │
│  🔧 ProDy NMA (Protein Flexibility)     Arc 3       │
│     Protein conformation under load                 │
│     Status: Planned Q3 2026                         │
│                                                      │
│  🔧 AlphaFold (Druggability)            Arc 4       │
│     Cryptic binding site prediction                 │
│     Status: Planned Q4 2026                         │
│                                                      │
│  [Join waitlist for early access →]                 │
└─────────────────────────────────────────────────────┘
```

Implementation:
1. Static display — this is a roadmap panel, not dynamic
2. CC3D shows live status — call verify_cc3d_installation()
   to confirm it's actually installed, show green if yes
3. All others show arc + timeline
4. "Join waitlist" button links to signups.csv capture
   (same mechanism as existing waitlist if present)
5. Dark theme, #00ff88 for live, #ffd700 for beta,
   #666666 for planned

Write tests/test_pi_ui.py::test_simulation_stack_section_renders

Commit: "feat: simulation stack status panel with live CC3D detection"

---

## PRIORITY 8: Wire render_pi_dashboard()

Connect all sections in core/pi_ui.py:

```python
def render_pi_dashboard():
    st.markdown("## 📊 Process Intelligence Platform")
    st.markdown(
        "Connect your lab and business data to surface "
        "process deviations, predict experimental outcomes, "
        "and correlate protocol parameters with business results."
    )

    render_connector_section()
    st.divider()
    render_process_mining_section()
    st.divider()
    render_cross_layer_section()
    st.divider()
    render_process_graph_section()
    st.divider()
    render_simulation_stack_section()
```

Run the full app locally to verify both tabs load without errors:
```bash
uv run streamlit run app.py
```

Check:
- Tab 1 (BioSim Copilot): existing flow unchanged
- Tab 2 (Process Intelligence): all 5 sections render
- No errors on cold start with empty data
- Dark theme consistent across both tabs

Write tests/test_pi_ui.py::test_render_pi_dashboard_callable

Commit: "feat: wire PI dashboard — all sections connected"

---

## PRIORITY 9: scikit-fem Scaffold Mechanics (Arc 2 Foundation)

This is the first real simulation beyond CC3D briefs.
scikit-fem is already installed. Build the foundation now.

Create core/fem_solver.py:

```python
"""
Scaffold mechanics solver using scikit-fem.

Answers: Will this scaffold deform under cell contractile forces?
What stress distribution does this geometry produce?

Arc 1: Simple 1D beam/compression model (fast, sync-safe)
Arc 2: Full 3D FEA with geometry from construct profile
Arc 3: Coupled with CC3D cell forces

Why scikit-fem before OpenMM:
- Directly relevant to bioink companies (stiffness claims)
- Fast enough for synchronous Streamlit execution
- First calibration win against rheometer measurements
"""
import numpy as np

def predict_scaffold_deformation(
    stiffness_kpa: float,
    cell_density_per_ml: float,
    construct_height_mm: float = 3.0
) -> dict:
    """
    Simple compression model: estimate scaffold deformation
    under collective cell contractile force.

    Cell contractile stress: ~1-10 nN/cell (use 5 nN typical)
    Returns:
    {
      "max_deformation_um": float,
      "strain_percent": float,
      "stress_kpa": float,
      "failure_risk": "low"|"medium"|"high",
      "recommendation": str
    }
    """
    # Collective contractile force
    cell_volume_ml = construct_height_mm * 1e-3  # rough
    n_cells = cell_density_per_ml * cell_volume_ml
    contractile_force_nN = n_cells * 5.0  # 5 nN/cell typical

    # Convert to stress (assume 1cm x 1cm cross section)
    area_m2 = 1e-4
    stress_pa = (contractile_force_nN * 1e-9) / area_m2
    stress_kpa_val = stress_pa / 1000

    # Deformation from Hooke's law: delta = F*L/(E*A)
    E_pa = stiffness_kpa * 1000
    height_m = construct_height_mm * 1e-3
    deformation_m = (contractile_force_nN * 1e-9 * height_m) / (E_pa * area_m2)
    deformation_um = deformation_m * 1e6
    strain_pct = (deformation_m / height_m) * 100

    # Risk thresholds from literature
    if strain_pct > 15:
        risk = "high"
        rec = f"Scaffold at {stiffness_kpa} kPa will deform >{strain_pct:.1f}% under cell load. Increase stiffness to >10 kPa or reduce cell density."
    elif strain_pct > 5:
        risk = "medium"
        rec = f"Moderate deformation predicted ({strain_pct:.1f}%). Monitor construct integrity at day 3-5."
    else:
        risk = "low"
        rec = f"Scaffold mechanics stable. Predicted strain {strain_pct:.1f}% within acceptable range."

    return {
        "max_deformation_um": round(deformation_um, 2),
        "strain_percent": round(strain_pct, 2),
        "stress_kpa": round(stress_kpa_val, 4),
        "failure_risk": risk,
        "recommendation": rec,
        "n_cells_estimated": int(n_cells),
        "collective_force_nN": round(contractile_force_nN, 1)
    }

def predict_stress_distribution(
    stiffness_kpa: float,
    porosity_percent: float = 80.0
) -> dict:
    """
    Estimate stress concentration factor from porosity.
    High porosity → stress concentrations at pore walls.
    Relevant for: will cells experience heterogeneous mechanics?
    """
    # Stress concentration factor for porous scaffolds
    # Approximation: Kt increases with porosity
    relative_density = 1 - (porosity_percent / 100)
    Kt = 1 + 2 * (1 - relative_density) / relative_density if relative_density > 0 else 10

    effective_stiffness = stiffness_kpa * (relative_density ** 2)

    return {
        "stress_concentration_factor": round(Kt, 2),
        "effective_local_stiffness_kpa": round(effective_stiffness, 2),
        "heterogeneity_risk": "high" if Kt > 3 else "medium" if Kt > 2 else "low",
        "recommendation": f"Stress concentration factor {Kt:.1f}x at pore walls. Cells near pores experience {effective_stiffness:.1f} kPa locally."
    }
```

Add FEA results to BioSim results phase in app.py:
- After variance report, before simulation brief
- New panel: "🏗️ Scaffold Mechanics (FEA)"
- Call predict_scaffold_deformation() with profile values
- Display: deformation estimate, strain %, failure risk badge
- Call predict_stress_distribution() if porosity available
- Dark theme callout box matching existing style

Write tests/test_fem_solver.py:
- test_fem_solver_importable
- test_predict_deformation_returns_required_keys:
  stiffness=4.0, density=2e6 → dict has all required keys
- test_high_stiffness_lower_deformation:
  stiffness=1 kPa → higher strain than stiffness=10 kPa
- test_failure_risk_high_for_soft_scaffold:
  stiffness=0.5, density=10e6 → failure_risk == "high"
- test_stress_distribution_returns_keys

Commit: "feat: scikit-fem scaffold mechanics — FEA prediction in BioSim"

---

## PRIORITY 10: Push and Deploy

```bash
uv run pytest tests/ -v --tb=short
git add -A && git commit -m "feat: PI UI complete — all sections live"
git push origin main
```

Streamlit Cloud will auto-redeploy on push.

Write tests/test_deployment.py additions:
- test_pi_ui_importable
- test_fem_solver_importable

Commit: "chore: final push — PI UI + FEA live on Streamlit Cloud"

---

## SUCCESS CRITERIA CHECKLIST

Before outputting completion promise, verify ALL:

- [ ] Sim brief fires and checklist item checks off
- [ ] App has two tabs: BioSim Copilot + Process Intelligence
- [ ] Tab 1 (BioSim) unchanged — all existing functionality works
- [ ] Tab 2 shows 5 sections: connector upload, process mining,
      cross-layer intelligence, process graph, simulation stack
- [ ] CSV upload works for ELN, CRM, instrument files
- [ ] Process mining KPIs display when events loaded
- [ ] Cross-layer panel activates when both CRM + ELN loaded
- [ ] Process graph shows stats and Plotly visualization
- [ ] Simulation stack panel shows CC3D as live, others as roadmap
- [ ] FEA panel appears in BioSim results with deformation estimate
- [ ] All sections show graceful empty states (no crashes)
- [ ] Dark theme consistent across both tabs
- [ ] uv run pytest tests/ -v --tb=short → ALL PASS (target: 80+)
- [ ] Zero regressions in existing 59 tests
- [ ] Pushed to GitHub → Streamlit Cloud redeployed

---

## ITERATIVE PROTOCOL

After EACH priority:
1. uv run pytest tests/ -v --tb=short
2. Fix regressions before moving on
3. git commit
4. Update PROGRESS.md

If blocked after 3 attempts: document in PROGRESS.md, skip,
continue. Do NOT break existing BioSim functionality.

Critical constraint: Tab 1 must remain fully functional at
every step. Test it after every priority that touches app.py.

---

## LAUNCH COMMAND

```
git add -A && git commit -m "pre-ralph PI-UI checkpoint"
```

Then in Claude Code:
```
/ralph-wiggum:ralph-loop "Read STRATEGY.md first. Then work through .ralph/arc2_pi_ui.md priority by priority. Run tests after each priority. Do NOT break existing BioSim tab functionality. Commit after each passing priority. Update PROGRESS.md after each." --max-iterations 40 --completion-promise "DONE: PI UI sprint complete"
```
