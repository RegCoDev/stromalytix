# Ralph Loop: Arc 1 Remaining + Process Intelligence Foundation
# File: .ralph/arc2_pi_sprint.md

**Read STRATEGY.md before writing a single line of code.**
This is not a tissue engineering tool. It is a Biological Process
Intelligence platform. Every architectural decision must reflect
the three-layer architecture: data ingestion → process mining →
biophysical simulation.

**Completion Promise**:
Output "DONE: PI foundation sprint complete" when checklist passes.

---

## PRE-FLIGHT (Do this before anything else)

```bash
git add -A && git commit -m "pre-ralph PI-foundation checkpoint"
uv run pytest tests/ -v --tb=short 2>&1 | tail -10
```

Record the exact pass count. If anything fails that was passing
before, fix it before proceeding. Do not start new work on a
broken baseline.

Install dependencies if missing:
```bash
uv add pymupdf python-docx fpdf2 scikit-fem networkx pm4py
```

---

## PRIORITY 1: Embed CC3D Knowledge Base

**Status**: Scraped (407 records), never embedded. Known RAG gap.

Run embed_and_index.py. If it doesn't handle cc3d_parameters.json
automatically, update it to embed ALL JSON files in
data/raw_abstracts/ using cluster label == filename stem.

Verify:
```bash
python -c "
from core.rag import load_vectorstore
db = load_vectorstore()
print('Count:', db._collection.count())
assert db._collection.count() > 3500, 'FAIL: CC3D not embedded'
print('PASS')
"
```

Write test: tests/test_kb.py::test_cc3d_kb_embedded
  assert load_vectorstore()._collection.count() > 3500

Commit: "feat: embed CC3D parameters KB — vectorstore now >3500 chunks"

---

## PRIORITY 2: Data Connector Architecture

This is the ingestion layer for CRM, ERP, ELN, and instruments.
These connectors are what make Stromalytix a platform, not a tool.
Build the architecture now. Live API connections come in Arc 2.
All connectors today are CSV-first.

Create connectors/__init__.py (empty)

Create connectors/base.py:

```python
"""
All data sources produce ProcessEvent objects.
ProcessEvents feed the process mining engine and process graph.
This is the normalization layer that makes cross-source analysis
possible — the same object whether it came from Benchling,
HubSpot, or a bioprinter export.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

class DataSourceType(Enum):
    CRM = "crm"
    ERP = "erp"
    ELN = "eln"
    LIMS = "lims"
    INSTRUMENT = "instrument"
    DOCUMENT = "document"

@dataclass
class ProcessEvent:
    """
    Atomic unit of process intelligence.
    PM4Py event log format:
      case:concept:name = case_id
      concept:name      = activity
      time:timestamp    = timestamp
    """
    event_id: str
    case_id: str           # batch_id, experiment_id, order_id
    activity: str          # "cell_seeding", "deal_closed", etc.
    timestamp: datetime
    source_type: DataSourceType
    source_name: str

    # Scientific
    parameter_values: Optional[Dict[str, float]] = None
    outcome_values: Optional[Dict[str, float]] = None
    operator: Optional[str] = None
    batch_id: Optional[str] = None
    protocol_version: Optional[str] = None
    deviation_note: Optional[str] = None

    # Business
    customer_id: Optional[str] = None
    deal_value: Optional[float] = None
    raw: Optional[Dict[str, Any]] = None

class BaseConnector:
    source_type: DataSourceType
    source_name: str

    def connect(self, credentials: dict) -> bool:
        raise NotImplementedError

    def extract(self, since=None) -> list:
        raise NotImplementedError

    def to_event_log(self, events: list):
        """Convert ProcessEvents to PM4Py DataFrame."""
        import pandas as pd
        import pm4py
        records = [{
            "case:concept:name": e.case_id,
            "concept:name": e.activity,
            "time:timestamp": e.timestamp,
            "org:resource": e.operator or "unknown",
            "source": e.source_name,
            **(e.parameter_values or {}),
            **(e.outcome_values or {})
        } for e in events]
        df = pd.DataFrame(records)
        if df.empty:
            return df
        return pm4py.format_dataframe(
            df,
            case_id="case:concept:name",
            activity_key="concept:name",
            timestamp_key="time:timestamp"
        )
```

Create connectors/eln_csv.py — ELNCSVConnector:
- Accepts CSV exports from Benchling, LabArchives, SciNote
- Auto-detects column mapping from header names
- Maps: experiment_id→case_id, step→activity, timestamp,
  operator, value+unit→parameter_values, deviation_note
- extract_parameters(row): parse "4 kPa stiffness" → {"stiffness_kpa": 4.0}

Create connectors/crm_csv.py — CRMCSVConnector:
- Accepts HubSpot/Salesforce CSV deal exports
- Maps deal stages to process activities
- extract_construct_requirements(row): LLM parse of deal notes
  for construct parameter requirements → partial ConstructProfile dict
- Connects customer requirements to construct outcomes

Create connectors/instrument_csv.py — InstrumentCSVConnector:
- Bioprinter logs (Cellink, Allevi, Aspect)
- Plate reader exports (SpectraMax, Synergy)
- Rheometer exports
- detect_instrument(filepath) → instrument type
- extract_print_parameters(df) → {"nozzle_temp": 37.0, ...}
- extract_outcome_values(df) → {"viability_percent": 85.0, ...}

Write tests/test_connectors.py:
- test_process_event_dataclass_valid: create one, no errors
- test_base_connector_importable
- test_eln_csv_connector_importable
- test_crm_csv_connector_importable
- test_instrument_csv_connector_importable
- test_to_event_log_produces_pm4py_columns:
  create 3 mock ProcessEvents → to_event_log() →
  df columns include "case:concept:name", "concept:name",
  "time:timestamp"

Commit: "feat: data connector architecture — base + ELN/CRM/instrument CSV"

---

## PRIORITY 3: Process Mining Engine

Create core/process_mining.py — BiologicalProcessMiner:

```python
"""
Wraps PM4Py with biological process extensions.

Standard PM4Py limitation: assumes discrete events, ignores
continuous measurements and batch effects. This class handles
the biological reality: continuous viability over time,
stochastic outcomes at identical nominal parameters,
and material lot variance independent of protocol execution.

This is Stromalytix's core IP.
"""
import pm4py
import pandas as pd
import networkx as nx

class BiologicalProcessMiner:

    def __init__(self):
        self.event_logs = {}
        self.process_models = {}
        self.deviation_log = []

    def add_event_log(self, events: list, log_name: str):
        """Accept ProcessEvent list or PM4Py DataFrame."""

    def discover_process(self, log_name: str,
                         algorithm="inductive") -> dict:
        """
        Returns:
        {
          "activities": list,
          "variants": dict,  # variant → frequency
          "most_common_path": list,
          "rare_variants": list  # potential deviations
        }
        Algorithms: inductive (noise-tolerant), alpha, heuristic
        """

    def check_conformance(self, log_name: str,
                          reference_protocol: list) -> dict:
        """
        Score each case against reference protocol.
        Returns per-case: {fitness, missing_activities,
                           extra_activities, deviation_points}
        """

    def find_critical_control_points(self, log_name: str,
                                      outcome_column: str) -> list:
        """
        THE BIOLOGICAL EXTENSION.
        Correlate process steps with continuous outcome measurements.
        Standard PM4Py cannot do this.

        Returns ranked list:
        [{activity, outcome_correlation, high_value_parameters,
          deviation_frequency, recommendation}]
        """

    def detect_batch_effects(self, events: list,
                              batch_column: str,
                              outcome_column: str) -> dict:
        """
        Separate material lot variance from protocol variance.
        Returns per-batch: {mean_outcome, cv, flagged, affected_cases}
        """

    def get_kpis(self, log_name: str) -> dict:
        """
        Returns: batch_success_rate, mean_time_to_result,
        protocol_conformance_rate, critical_deviation_rate,
        most_common_failure_mode, throughput_per_week
        """

    def correlate_business_outcomes(self,
                                     process_events: list,
                                     crm_events: list) -> dict:
        """
        THE CROSS-LAYER SIGNAL.
        Connect experimental parameters to business outcomes.
        Which stiffness range closes deals vs. causes churn?
        """
```

Write tests/test_process_mining.py:
- test_process_miner_importable
- test_add_event_log_accepts_list
- test_get_kpis_returns_dict_with_required_keys:
  keys include batch_success_rate, mean_time_to_result,
  protocol_conformance_rate
- test_find_critical_control_points_returns_list
- test_detect_batch_effects_with_two_batches:
  create mock events: batch_A viability=85, batch_B viability=60
  → detect_batch_effects flags batch_B (lower mean_outcome)
- test_correlate_business_outcomes_returns_dict

Commit: "feat: biological process mining engine (PM4Py + extensions)"

---

## PRIORITY 4: Process Intelligence Graph

Create core/process_graph.py — ProcessGraph:

Node types: Construct, Parameter, Outcome, Mechanism,
Protocol, Batch, Customer, Deal

Edge types: HAS_PARAMETER, PRODUCES, MEDIATES, FOLLOWS,
USES_BATCH, REQUESTED_BY, ASSOCIATED_WITH, SIMILAR_TO,
CITES, PREDICTS, VALIDATES

```python
class ProcessGraph:
    """
    Arc 1: networkx (local, no infrastructure needed)
    Arc 2: Neo4j AsyncGraphDatabase driver v5.28+
           Parameterized Cypher ONLY — never string concatenate.

    The novel edges are PREDICTS and VALIDATES:
    PREDICTS: SimulationBrief → Outcome (with confidence)
    VALIDATES: actual Outcome → SimulationBrief (post-experiment)
    These two edges are how prediction accuracy is tracked.
    """

    def add_construct(self, profile, run_id=None) -> str: ...
    def add_outcome(self, construct_id, outcome_type,
                    value, unit, pmid=None): ...
    def add_batch(self, batch_id, material_type,
                  lot_number, parameters=None): ...
    def add_deal(self, deal_id, customer_id,
                  construct_requirements=None,
                  outcome="unknown"): ...
    def link_construct_to_deal(self, construct_id, deal_id): ...
    def link_construct_to_batch(self, construct_id, batch_id): ...
    def add_simulation_prediction(self, construct_id,
                                   brief_dict,
                                   predicted_outcomes): ...
    def validate_prediction(self, construct_id,
                             actual_outcomes): ...
    def get_prediction_accuracy(self) -> dict: ...
    def get_parameter_outcome_correlations(self, param) -> dict: ...
    def get_business_parameter_correlations(self) -> list: ...
    def get_stats(self) -> dict:
        # Returns for sidebar:
        # constructs_analyzed, outcomes_tracked, predictions_made,
        # prediction_accuracy, deals_linked, batches_tracked
    def export_to_json(self, path): ...
    def load_from_json(self, path): ...
```

Create data/process_graph.json:
```json
{
  "nodes": [],
  "edges": [],
  "metadata": {
    "version": "1.0",
    "description": "Stromalytix PI Graph — Arc 1 (networkx)",
    "arc2_migration": "Neo4j AsyncGraphDatabase v5.28+",
    "neo4j_note": "Parameterized Cypher only"
  }
}
```

Wire into app.py results phase:
- After variance report: process_graph.add_construct(profile)
- Sidebar: "🔬 PI Graph: X constructs | Y outcomes | Z predictions"

Write tests/test_process_graph.py:
- test_process_graph_importable
- test_add_construct_returns_string_id
- test_add_outcome_links_to_construct
- test_add_deal_and_link
- test_get_stats_has_required_keys
- test_graph_export_and_reload: add node → export → reload → node still present
- test_data_graph_json_exists

Commit: "feat: PI graph with business + science nodes (networkx Arc1)"

---

## PRIORITY 5: KPI Dashboard

Create core/kpi_dashboard.py — KPIDashboard:

```python
"""
Three tiers of KPIs:

Scientific: batch_success_rate, mean_time_to_result,
            protocol_conformance_rate, prediction_accuracy

Business: revenue_per_protocol_version, win_rate_by_parameter,
          churn_correlation_batch_id, cost_per_construct

Cross-layer (the novel ones):
  parameter_win_rate: which stiffness ranges close deals
  batch_business_impact: which lots caused customer churn
  protocol_version_revenue: v3.1 vs v3.2 deal outcomes

These cross-layer KPIs are the core moat insight —
no LIMS, ELN, or CRO tool surfaces these connections.
"""

class KPIDashboard:
    def __init__(self, process_graph, process_miner=None): ...
    def get_scientific_kpis(self) -> dict: ...
    def get_business_kpis(self) -> dict: ...
    def get_cross_layer_kpis(self) -> dict: ...
    def get_summary_card(self) -> list:
        """Top 5 actionable insights as human-readable strings."""
    def render_streamlit_sidebar(self):
        """Graceful degradation — shows stats even with empty graph."""
```

Write tests/test_kpi_dashboard.py:
- test_kpi_dashboard_importable
- test_scientific_kpis_returns_dict
- test_business_kpis_returns_dict
- test_cross_layer_kpis_returns_dict
- test_summary_card_returns_list
- test_render_sidebar_does_not_crash_on_empty_graph

Commit: "feat: KPI dashboard — scientific + business + cross-layer"

---

## PRIORITY 6: Protocol Document Ingestion

Create core/ingest.py:

```python
def extract_text_from_pdf(file_bytes: bytes) -> str:
    """fitz (pymupdf)"""

def extract_text_from_docx(file_bytes: bytes) -> str:
    """python-docx"""

def parse_protocol_to_profile(text: str) -> dict:
    """
    claude-haiku-4-5-20251001.
    Extract: target_tissue, cell_types, scaffold_material,
    stiffness_kpa, porosity_percent, cell_density_per_ml,
    experimental_goal, primary_readout.
    Return JSON only. None for missing fields.
    """
```

Update app.py onboarding:
- st.file_uploader("Upload your protocol (optional)",
  type=["pdf","docx"]) above persona selection
- On upload: extract → parse → show "Detected from protocol:"
  summary card with extracted fields
- Pre-populate session_state, user confirms before chat

Write tests/test_ingest.py:
- test_ingest_importable
- test_parse_finds_tissue_type: "cardiac tissue" → target_tissue=="cardiac"
- test_parse_finds_stiffness: "4 kPa stiffness" → stiffness_kpa==4.0
- test_extract_functions_callable

Commit: "feat: protocol document ingestion PDF/DOCX → ConstructProfile"

---

## PRIORITY 7: White-Label PDF Report

Update core/export.py generate_pdf_report(report, client_name=""):

Page 1 — Cover:
- "PROTOCOL INTELLIGENCE REPORT"
- client_name (if provided)
- Tissue type + experimental goal + date
- "Prepared by Stromalytix | stromalytix.com"
- CONFIDENTIAL notice

Page 2 — Executive Summary:
- 3 sentences via claude-haiku for non-scientist reader
- Prompt: "3 sentences. Lead with biggest risk. End with key
  recommendation. Plain language. No jargon."
- Input: ai_narrative + top risk_flags

Pages 3+ — Existing technical content

Final page — Signature + disclaimer

Write tests/test_export.py:
- test_pdf_has_cover_page: page_count >= 2
- test_pdf_has_executive_summary: "Executive Summary" in text
- test_pdf_client_name: "Cytoink" appears when passed as client_name
- test_pdf_signature: "stromalytix.com" in last page

Commit: "feat: white-label PDF — cover + exec summary + signature"

---

## PRIORITY 8: CC3D Live Execution Runner

Create core/cc3d_runner.py:

```python
CC3D_PYTHON = r"C:\CompuCell3D\Miniconda3\python.exe"

def verify_cc3d_installation() -> dict:
    # {installed: bool, python_path: str, version: str, error: str}

def generate_cc3d_script(brief: dict) -> str:
    # Confidence-tagged adhesion format:
    # {"value": 10, "confidence": "medium"} → extract value=10
    # Output: runnable CC3D Python script, 1000 MCS,
    # save screenshot to outputs/cc3d_{timestamp}.png
    # NEVER import cc3d in main process

def run_cc3d_simulation(brief: dict, timeout=120) -> dict:
    # Windows: asyncio.to_thread(subprocess.run(...))
    # NEVER asyncio.create_subprocess_exec on Windows
    # Returns: {success, ran, output, error,
    #           screenshot_path, mcs_completed, duration_seconds}
```

App.py results phase:
- "⚡ Run CC3D Preview (Beta)" button
- Show screenshot or mcs_completed stats
- Graceful fallback: "CC3D not configured — install at
  compucell3d.org to enable live simulation"

Write tests/test_cc3d_runner.py:
- test_cc3d_runner_importable
- test_verify_cc3d_returns_required_keys
- test_generate_script_handles_confidence_tagged_adhesion:
  {"value": 10, "confidence": "medium"} → script contains "10"
- test_run_cc3d_returns_required_keys

Commit: "feat: CC3D live execution runner with confidence-tag support"

---

## PRIORITY 9: Streamlit Cloud Deployment Prep

1. Generate requirements.txt:
   uv pip compile pyproject.toml -o requirements.txt
   Remove any Windows-only packages.

2. Create .streamlit/config.toml:
   ```toml
   [theme]
   base = "dark"
   backgroundColor = "#0a0a0a"
   secondaryBackgroundColor = "#1a1a1a"
   primaryColor = "#00ff88"
   font = "monospace"
   [server]
   maxUploadSize = 10
   ```

3. Update app.py API key loading to support st.secrets:
   ```python
   try:
       ANTHROPIC_API_KEY = st.secrets.get(
           "ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY"))
   except:
       ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
   ```

4. Add to .gitignore:
   .streamlit/secrets.toml
   data/chroma_db/
   outputs/*.pdf

5. Create README.md with: one-sentence description,
   deploy button, local setup instructions.

6. Create .github/workflows/test.yml:
   ```yaml
   name: Tests
   on: [push, pull_request]
   jobs:
     test:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: astral-sh/setup-uv@v2
         - run: uv sync
         - run: uv run pytest tests/ -v --tb=short
           env:
             ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
   ```

Write tests/test_deployment.py:
- test_requirements_txt_exists
- test_streamlit_config_exists
- test_readme_exists
- test_gitignore_has_secrets

Commit: "feat: Streamlit Cloud deployment configuration"

---

## PRIORITY 10: STRATEGY.md + CLAUDE.md

1. Write STRATEGY.md to project root. Full content:
   Read this session for the complete vision. Key points:
   - Three-layer architecture: Ingestion → Process Mining → Simulation
   - Not LIMS/ELN/CRO — prediction before the experiment runs
   - Cross-layer insight: ERP batch variance reweights simulation confidence
   - Data sources: CRM, ERP, ELN, LIMS, instruments, documents
   - PM4Py biological extensions are core IP
   - The moat is calibration data, not software

2. Update CLAUDE.md. Add or replace the vision section:
   ```
   ## Vision — Read STRATEGY.md First

   Stromalytix is Biological Process Intelligence for precision medicine.
   NOT a lab tool. NOT analytics.

   Three-layer architecture:
   Layer 1 (Ingestion): CRM/ERP/ELN/LIMS/instruments → ProcessEvents
   Layer 2 (Process Mining): PM4Py + biological extensions → KPIs
   Layer 3 (Simulation): scikit-fem/CC3D/OpenMM/ProDy → predictions

   Novel technical claim: business process signals (ERP batch variance,
   CRM win rate) feed simulation parameter reweighting. No other
   platform makes this connection.

   Simulation stack build order:
   Arc 1: CC3D brief → Arc 2: scikit-fem + CC3D live →
   Arc 3: OpenMM → Arc 4: ProDy/AlphaFold

   NEVER import cc3d in FastAPI or Streamlit.
   Always subprocess: C:\CompuCell3D\Miniconda3\python.exe
   Neo4j in Arc 2: AsyncGraphDatabase v5.28+, parameterized Cypher only.
   ```

Commit: "docs: STRATEGY.md + CLAUDE.md full PI vision"

---

## SUCCESS CRITERIA CHECKLIST

Run this before outputting the completion promise:

- [ ] ChromaDB count > 3,500
- [ ] connectors/base.py exists, ProcessEvent importable
- [ ] connectors/eln_csv.py, crm_csv.py, instrument_csv.py exist
- [ ] core/process_mining.py, BiologicalProcessMiner importable
- [ ] core/process_graph.py, all node types including Deal + Customer
- [ ] data/process_graph.json exists
- [ ] core/kpi_dashboard.py, cross-layer KPIs implemented
- [ ] core/ingest.py, parses tissue type and stiffness from text
- [ ] File uploader in app.py onboarding phase
- [ ] PDF has cover page + executive summary + client_name
- [ ] core/cc3d_runner.py handles confidence-tagged adhesion
- [ ] CC3D button in results phase
- [ ] requirements.txt exists
- [ ] .streamlit/config.toml exists
- [ ] README.md exists
- [ ] STRATEGY.md in project root
- [ ] CLAUDE.md updated
- [ ] uv run pytest tests/ -v --tb=short → ALL PASS
- [ ] Zero regressions in existing 17 tests

---

## ITERATIVE PROTOCOL

After EACH priority:
1. uv run pytest tests/ -v --tb=short
2. Fix regressions before moving on
3. git commit
4. Log in PROGRESS.md: what passed, what failed

If blocked after 3 attempts: document in PROGRESS.md, skip,
continue. Come back at the end.

---

## LAUNCH COMMAND (copy exactly)

```
/ralph-wiggum:ralph-loop "Read STRATEGY.md first. Then work through .ralph/arc2_pi_sprint.md priority by priority. Run tests after each priority. Commit after each passing priority. Log progress in PROGRESS.md. If blocked after 3 attempts on any priority, document it and continue." --max-iterations 40 --completion-promise "DONE: PI foundation sprint complete"
```
