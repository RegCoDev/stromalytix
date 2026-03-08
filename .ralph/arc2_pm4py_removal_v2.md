# Ralph Loop: PM4Py Removal + Algorithm Router + PI Chat + Company Context
# File: .ralph/arc2_pm4py_removal_v2.md
# Date: 2026-03-08

**Read STRATEGY.md and IP_SEEDS.md before writing a single line of code.**

This sprint has four mandates:
1. ELIMINATE pm4py (GPL v3 — commercial survival requirement)
2. Build a SOUND proprietary process mining engine with an
   algorithm router that selects the correct miner based on
   data characteristics and guards against known pitfalls
3. Add a PI CHAT interface grounded in full process + simulation context
4. Build COMPANY CONTEXT persistence that bridges process data,
   simulation predictions, and business signals across sessions

**Completion Promise**:
Output "DONE: Sound PI engine with chat and company context live"
when checklist passes.

---

## PRE-FLIGHT

```bash
git add -A && git commit -m "pre-ralph pm4py-v2 checkpoint"
uv run pytest tests/ -v --tb=short 2>&1 | tail -5
uv add networkx numpy pandas scipy
```

Fix any regressions before proceeding.

---

## PRIORITY 1: Proprietary Process Mining Engine — Sound by Construction

**Commercial survival requirement. Zero GPL code.**

Create core/bio_process_miner.py with these components:

### DirectlyFollowsGraph

From: van der Aalst, Process Mining textbook (2016). Published, unpatented.

```python
class DirectlyFollowsGraph:
    """
    Directly-follows graph: foundation of all process discovery.
    edges[(a,b)] = count of times b directly follows a in same case.
    """
    def build(self, df, case_col, activity_col, timestamp_col): ...
    def get_variants(self) -> dict:
        """All unique activity sequences -> frequency."""
    def get_edge_density(self) -> float:
        """edges / max_possible_edges. >0.7 = spaghetti risk."""
    def filter_by_frequency(self, min_freq=0.05) -> 'DirectlyFollowsGraph':
        """Remove edges appearing in <min_freq of cases."""
```

### AlgorithmRouter

This is Stromalytix IP — the routing logic itself is novel applied to
biological data, even though the underlying algorithms are published.

```python
class AlgorithmRouter:
    """
    Selects appropriate discovery algorithm and noise threshold
    based on event log characteristics.

    Guards against:
    - Flower model (high variant ratio -> aggressive filtering)
    - Unsound Petri nets from loops (-> force InductiveMiner)
    - Artificial parallelism from date-only timestamps
    - Heterogeneous case notions (OoC + bioprinting in same log)
    - Single-activity dominance
    - Invisible transitions from Alpha miner
    """

    def characterize(self, df, case_col, activity_col,
                     timestamp_col) -> dict:
        """
        Returns data quality report:
        {
          case_count: int,
          variant_count: int,
          variant_ratio: float,          # unique variants / cases
          has_loops: bool,               # any activity > once/case
          timestamp_precision: str,      # "datetime"|"date_only"
          dominant_start_activity: str,
          edge_density: float,
          heterogeneous_methods: bool,   # mixed biofab methods
          outcome_type: str,             # "binary"|"continuous"|"multivariate"
          recommendation: str,           # human-readable routing decision
          warnings: list,                # detected pitfalls
        }
        """

    def select_algorithm(self, characterization: dict) -> dict:
        """
        Returns:
        {
          algorithm: "inductive"|"heuristics"|"dfg_only"|"alpha",
          noise_threshold: float,
          variant_filter_k: int,         # keep top-k variants
          inject_start_end: bool,
          split_by_method: bool,
          rationale: str,
        }

        Decision logic:
        case_count < 10   -> dfg_only (no model discovery)
        case_count < 30   -> heuristics, threshold=0.3
        loops detected    -> inductive (alpha FORBIDDEN -- unsound)
        variant_ratio>0.8 -> inductive IMf with aggressive noise filter
        variant_ratio<0.3 -> heuristics or alpha (simple log)
        default           -> inductive IMf, threshold=0.2
        """
```

### InductiveMiner (Simplified -- guarantees sound process trees)

From: Leemans et al., "Discovering Block-Structured Process Models
from Event Logs" ICPM 2013. Published, unpatented.

Key guarantee: output is always a sound process tree (no deadlocks,
no livelocks). Achieved by recursive log splitting using:
- Sequence (->): A always before B across all cases
- Exclusive choice (x): A and B never in same case
- Parallel (and): A and B both present, no consistent ordering
- Loop (loop): activity appears multiple times in cases

```python
class InductiveMiner:
    def discover(self, df, case_col, activity_col, timestamp_col,
                 noise_threshold=0.2) -> dict:
        """
        Returns process tree as nested dict (not pm4py object):
        {
          "type": "sequence"|"xor"|"parallel"|"loop"|"leaf",
          "children": [...] or "activity": str,
          "activities": list,          # all activities in subtree
          "variants": dict,            # variant -> frequency
          "most_common_path": list,
          "rare_paths": list,
          "soundness_verified": True,  # always True for InductiveMiner
          "model_type": "process_tree"
        }

        IMf (Infrequent) variant: filter activities/edges below
        noise_threshold before splitting. Handles biological noise.
        """
```

### HeuristicsMiner (for small/noisy logs)

From: Weijters & van der Aalst (2003). Published, unpatented.

```python
class HeuristicsMiner:
    def discover(self, df, case_col, activity_col, timestamp_col,
                 dependency_threshold=0.5,
                 positive_observations=3) -> dict:
        """
        Dependency measure: dep(a,b) = (|a>b| - |b>a|) / (|a>b| + |b>a| + 1)
        Edge included if dep(a,b) > dependency_threshold AND |a>b| > positive_observations

        Returns same dict structure as InductiveMiner for
        interface compatibility.
        Note: soundness_verified = False (heuristics nets
        may have soundness issues).
        """
```

### ConformanceChecker

From: van der Aalst, token-based replay (2012). Published, unpatented.

```python
class ConformanceChecker:
    def check_case_token_replay(self, trace: list,
                                 reference_path: list) -> dict:
        """
        Fast approximate conformance via token replay.
        Missing tokens created (penalty), remaining tokens consumed (penalty).
        fitness = 1 - (missing + remaining) / (consumed + produced)

        Returns:
        {fitness, missing_activities, extra_activities,
         deviation_points, conformant (fitness > 0.8)}
        """

    def check_case_alignment(self, trace: list,
                              process_tree: dict) -> dict:
        """
        Precise alignment-based conformance.
        Optimal edit distance: move_on_log | move_on_model | synchronous_move
        Use for detailed deviation analysis (slower than token replay).
        """

    def check_log(self, df, case_col, activity_col, timestamp_col,
                  reference_path: list, method="token_replay") -> dict:
        """
        Per-case conformance + aggregate stats.
        Returns:
        {
          per_case: {case_id: conformance_dict},
          aggregate: {
            mean_fitness, conformance_rate,
            most_common_deviation,
            deviation_frequency_by_step
          }
        }
        """
```

### BiologicalExtensions (Stromalytix IP -- novel)

```python
class BiologicalExtensions:
    """
    These methods are NOT in any published process mining library.
    They constitute Stromalytix trade secret IP.
    See IP_SEEDS.md SEED 002.
    """

    def correlate_steps_with_outcomes(self,
                                       events: list,
                                       outcome_column: str) -> list:
        """
        Pearson correlation of step execution / deviation with
        continuous outcome values. Biological extension: standard
        process mining assumes binary pass/fail, not continuous viability %.

        Returns ranked list:
        [{activity, outcome_correlation, deviation_frequency,
          high_deviation_mean_outcome, low_deviation_mean_outcome,
          ccp_score (correlation x deviation_freq), recommendation}]
        """

    def separate_batch_effects(self, events: list,
                                batch_column: str,
                                outcome_column: str) -> dict:
        """
        Within-lot CV vs across-lot CV decomposition.
        Flags lots where mean_outcome < 0.85 x overall_mean.
        Biological extension: separates material variance from
        protocol execution variance -- not in any PM library.
        """

    def correlate_business_outcomes(self, process_events: list,
                                     crm_events: list) -> dict:
        """
        Cross-layer signal: which parameter ranges close deals?
        Which lots caused churn? Parameter -> win_rate mapping.
        See IP_SEEDS.md SEED 001.
        """
```

### BiologicalProcessMiner (orchestrator)

```python
class BiologicalProcessMiner:
    """
    Top-level orchestrator. Uses AlgorithmRouter to select
    appropriate algorithm, then runs discovery, conformance,
    and biological extensions.
    """
    def __init__(self):
        self.router = AlgorithmRouter()
        self.inductive = InductiveMiner()
        self.heuristics = HeuristicsMiner()
        self.checker = ConformanceChecker()
        self.bio_ext = BiologicalExtensions()
        self.event_logs = {}
        self.characterizations = {}  # cached data quality reports
        self.process_models = {}     # cached discovered models

    def add_event_log(self, events, log_name: str): ...

    def analyze(self, log_name: str,
                outcome_column: str = None,
                reference_protocol: list = None) -> dict:
        """
        Full analysis pipeline:
        1. Characterize data
        2. Route to algorithm
        3. Discover process model
        4. Check conformance (if reference provided)
        5. Find CCPs (if outcome_column provided)
        6. Detect batch effects
        7. Return unified results dict
        """

    def get_data_quality_report(self, log_name: str) -> dict:
        """Return characterization with warnings and recommendations."""

    def get_kpis(self, log_name: str) -> dict: ...
```

After implementation:
```bash
uv remove pm4py
grep -r "import pm4py" . --include="*.py"  # must return 0 lines
grep -r "from pm4py" . --include="*.py"    # must return 0 lines
uv run pytest tests/ -v --tb=short
```

Write tests/test_bio_process_miner.py:
- test_algorithm_router_selects_dfg_for_small_log (n<10)
- test_algorithm_router_forces_inductive_on_loops
- test_algorithm_router_warns_on_high_variant_ratio
- test_algorithm_router_detects_date_only_timestamps
- test_inductive_miner_soundness: output always soundness_verified=True
- test_inductive_miner_handles_loops
- test_inductive_miner_handles_xor
- test_heuristics_miner_returns_compatible_structure
- test_conformance_perfect_trace: fitness == 1.0
- test_conformance_missing_step: fitness < 1.0
- test_conformance_extra_step: fitness < 1.0
- test_bio_ext_correlates_steps_with_outcomes
- test_bio_ext_batch_flags_low_performing_lot
- test_no_pm4py_import (grep check)
- test_full_analyze_pipeline_returns_required_keys
- test_heterogeneous_methods_triggers_split_warning

Commit: "feat: sound proprietary process mining engine -- zero GPL, algorithm router"

---

## PRIORITY 2: Company Context -- Persistent Intelligence Layer

Create core/company_context.py with CompanyContext, SimulationPrediction,
and Hypothesis dataclasses. Full persistence to data/company_contexts/.

Create Centara demo context pre-populated.

Write tests/test_company_context.py.

Commit: "feat: CompanyContext -- persistent intelligence bridge"

---

## PRIORITY 3: PI Chat Interface

Create core/pi_chat.py with context-grounded conversational analyst.
Wire into PI tab.

Write tests/test_pi_chat.py.

Commit: "feat: PI chat -- context-grounded conversational analyst"

---

## PRIORITY 4: Simulation-Process Bridge

Create core/sim_process_bridge.py. Wire into BioSim results and PI chat.

Write tests/test_sim_process_bridge.py.

Commit: "feat: simulation-process bridge -- convergent signal synthesis"

---

## PRIORITY 5: Algorithm Router UI in PI Tab

Expose data quality report and routing decision in PI dashboard.

Write tests.

Commit: "feat: algorithm router UI -- transparent mining decisions"

---

## PRIORITY 6: Multi-Modality + KB Expansion

Update connectors, models, scraper for 5 biofab methods.
Target: >10,000 ChromaDB chunks.

Commit: "feat: multi-modality support + expanded KB"

---

## PRIORITY 7: Centara Demo Data Integration

Load demo CSVs through connectors, run full analysis pipeline.

Commit: "feat: Centara demo integration -- full PI platform demo"

---

## PRIORITY 8: Remove PM4Py and Push

```bash
uv remove pm4py
grep -r "import pm4py" . --include="*.py"  # MUST be zero
grep -r "from pm4py" . --include="*.py"    # MUST be zero
uv run pytest tests/ -v --tb=short
git push origin main
```

Commit: "BREAKING: remove pm4py GPL dependency"

---

## SUCCESS CRITERIA CHECKLIST

- [ ] grep pm4py returns ZERO lines
- [ ] BiologicalProcessMiner importable from core/bio_process_miner
- [ ] AlgorithmRouter routes correctly for 5 test scenarios
- [ ] InductiveMiner output always has soundness_verified=True
- [ ] ConformanceChecker token replay and alignment both work
- [ ] BiologicalExtensions CCP correlation returns ranked list
- [ ] CompanyContext saves and loads correctly
- [ ] Centara demo context exists with pre-populated state
- [ ] PI chat grounded in company context
- [ ] PI chat auto-creates hypotheses from user statements
- [ ] SimProcessBridge detects convergent signals
- [ ] P1 alert shown when simulation + empirical signal overlap
- [ ] Calibration updates when actual outcome logged
- [ ] Algorithm router UI shows data quality report + warnings
- [ ] Mixed method logs auto-split before mining
- [ ] All 5 biofab methods supported in ProcessEvent
- [ ] Centara demo loads and populates full PI dashboard
- [ ] LOT-2024-B2 shows as flagged in demo
- [ ] Cross-layer signal: B2 -> churn correlation visible
- [ ] ChromaDB > 10,000 chunks
- [ ] uv run pytest tests/ -v -> ALL PASS (target: 100+)
- [ ] Zero regressions
- [ ] git push origin main

---

## ITERATIVE PROTOCOL

After P1: STOP and run grep check. If any pm4py import remains,
fix before moving to P2. This is non-negotiable.

After each subsequent priority:
1. uv run pytest tests/ -v --tb=short
2. Fix regressions
3. git commit
4. Update PROGRESS.md

Do NOT break existing BioSim tab at any step.
