# Stromalytix — Full Code Review

**Date:** 2026-05-28 · **Branch:** `mas-opportunity-engine` (worktree, queued for approval)
**Reviewer:** Claude Code (3 parallel read-only audits + synthesis)
**Charter:** `/opt/stromalytix/AGENT_BUILD_CHARTER.md` · **Baseline:** `tests/BASELINE.md`

> Scope: app shell, chat/RAG, FEA solver, CC3D sidecar, knowledge vault, parameter
> library, exports, tests, CI, security, dependency health. Every module scored
> against the three pillars (**reproducibility / explainability / observability**)
> and the two avatars (**academic PI / pharma preclinical scientist**). Feature
> preservation respected — findings flag, they do not propose deletion.

---

## TL;DR

The codebase has a **genuinely strong scientific foundation** — a DOI-anchored
deterministic fallback, a peer-review-grade parameter-derivation schema (39
documented estimates), PMID-cited variance reports, honest "what this does NOT
model" disclosures, and no "AI" language anywhere. That foundation is undermined
by a small number of **trust-fatal defects** that a skeptical reviewer hits in the
first read:

1. **A calculation error** (Krogh O2 diffusion) that produces *systematically
   wrong* hypoxia predictions for standard constructs — the single worst trust
   failure, because the tool's whole value is being right about exactly this.
2. **Non-reproducible runs** — the CC3D Potts simulation has no random seed (every
   run differs), and no artifact carries a model/version/seed/run-id stamp, so no
   output is re-derivable from its own record. This fails pillar 1 categorically.
3. **Unvalidated LLM citations** — LLM-generated PMIDs in the most prominent report
   section are never cross-checked against retrieved documents (hallucination risk).
4. **Operational-security hygiene** — a live API key sits in a filesystem `.env`,
   157 MB of runtime DBs + user PII are git-tracked.

None require gutting features. All are targeted fixes. The **T0 trust-spine** in
the charter falls directly out of items 1–3 below. **Overall posture: strong bones,
not yet at the trust bar — closeable with the ranked T0 work.**

### Pillar scorecard (module × pillar, /5)

| Module | Repro | Explain | Observe | Worst finding |
|---|:--:|:--:|:--:|---|
| `core/migration_insights.py` | 4* | 2 | 2 | **CRITICAL** Krogh O2 unit error → false-severe hypoxia |
| `services/cc3d_runner_api/runner.py` | **1** | 2 | 3 | **CRITICAL** Potts RNG unseeded → non-deterministic |
| `core/rag.py` | 2 | 4 | 2 | **HIGH** LLM PMIDs not validated; wrong neural citation |
| `core/models.py` | 2 | 4 | **1** | no run-id / version / path fields on `VarianceReport` |
| `core/fem_solver.py` | 3 | 2 | 3 | SCF hard-coded 1.5× (FEA solution discarded); ungrounded constants |
| `core/expand_action_plan.py` | **1** | 3 | **1** | LLM methods narrative, hallucinated-PMID risk |
| `core/chat.py` | 2 | 3 | 2 | non-deterministic elicitation (temp 0.7), no confirm step |
| `core/doe.py` | 4 | **1** | 2 | composite weights 0.6/0.4 uncited; "PB" mislabeled |
| `core/feasibility.py` | 5 | 3 | 3 | O2 timescale vs Krogh framing; material ranges uncited |
| `core/parameter_library.py` | 5 | 5 | 3 | fuzzy-match leakage (untested) |
| `core/cc3d_viz.py` | 4 | 2 | 4 | O2 units/threshold unlabeled |
| `core/scaffold_geometry.py` | 5 | 3 | 3 | TPMS eqns uncited; voxel-res effects silent |
| `core/cc3d_runner.py` | 3 | 3 | 3 | hard-coded `sessionId/hypothesisId` pollute the audit log |
| `core/export.py` | 3 | 4 | 2 | LLM-vs-deterministic path not flagged in PDF |
| App shell / CI / deps | 3 | 4 | **2** | no coverage gate; secret-gated flaky CI; bare `print()` logging |

\* deterministic but *systematically wrong* — determinism without correctness is not reproducibility.

**Pillar averages:** Reproducibility ≈ 3.0 · Explainability ≈ 3.0 · Observability ≈ 2.3.
Observability is the weakest pillar (no structured logging, no run-id propagation,
no per-run provenance) and is the cheapest to lift.

---

## Severity-ranked findings

### CRITICAL

- **C1 — Krogh O2 diffusion is ~30× wrong** (`core/migration_insights.py:97-101`).
  `c0_mol = o2_pct/100 * 0.21e-3` overstates dissolved O2 ~1050×; `denom = q*density*1e6`
  double-scales density. Net: `l_crit ≈ 0.03×` the correct value → a standard 4×4×2 mm
  construct at 10⁶ cells/mL is flagged **SEVERE HYPOXIA** when the correct critical depth
  is ~3.2 mm (no hypoxia). Drives systematic false-positive necrosis/gradient warnings.
  *No test exists for this module — a single `l_crit > 1 mm` assertion would have caught it.*
- **C2 — CC3D Potts simulation is non-deterministic** (`services/cc3d_runner_api/runner.py:128`).
  No `<RandomSeed>` in the generated Potts XML → CC3D uses a clock seed; identical inputs
  → different VTK outputs. Compounded by unseeded mitosis orientation (`runner.py:305`).
  Violates the charter's "same inputs → bounded repeatable outputs" axiom. A pharma group
  cannot put an unseeded stochastic sim in a submission.

### HIGH

- **H1 — LLM-generated PMIDs not validated** (`core/rag.py:540`; `core/expand_action_plan.py:65`).
  Narrative PMIDs are passed straight through; the "do not invent PMIDs" prompt rule is
  not enforced by any cross-check against retrieved docs. Hallucinated citations in the
  most-read section = paper-retraction-class risk for the academic avatar.
- **H2 — No run provenance / version stamp** (`core/models.py:94`; `core/export.py:200`).
  `VarianceReport` has no `run_id`, `generated_at`, `llm_model`, `llm_temperature`,
  `parameter_library_version`, `kb_snapshot_id`, or `path` (llm|deterministic). The PDF
  carries only a wall-clock timestamp. The artifact is not self-describing or re-derivable.
- **H3 — Wrong neural/brain stiffness citation** (`core/rag.py:59-60`). `neural` and `brain`
  both cite the cardiac/muscle DOI `10.1242/jcs.029678`. Neural stiffness (0.1–1 kPa) needs
  its own source (e.g. Saha 2008, PMID 18391959). A neuroscience reviewer catches this in 30s.
- **H4 — Ungrounded numerical constants in compute** — 5 nN contractile force
  (`fem_solver.py:52`), Kt heuristic (`fem_solver.py:121`), **SCF hard-coded 1.5×** with the
  actual FEA displacement field computed then discarded (`fem_solver.py:276`), material table
  (`fem_solver.py:184`), O2 K_m=0.02 + diffusion defaults (`runner.py:242,424`), chemotaxis
  "1–3%/mm" + ~70% persistence factor (`migration_insights.py:147,295`), DOE composite
  weights 0.6/0.4 (`doe.py:187`). Each appears in user-facing output without source/uncertainty.
- **H5 — 8 core modules have ZERO tests** (~2,500 LOC): `chat`, `feasibility`, `doe`,
  `action_plan`, `scaffold_geometry`, `parameter_library`, `migration_insights`,
  `expand_action_plan`, plus `rag.py` synthesis paths. The deterministic scientific spine
  is untested — C1 lived here undetected.
- **H6 (security) — live `OPENROUTER_API_KEY` in `/opt/stromalytix/.env`** (filesystem,
  `.gitignore`-excluded but one `git add .` from exposure). Rotate + inject at deploy.
- **H7 (security) — 157 MB runtime state git-tracked**: `services/cc3d_runner_api/jobs.db`
  (70 MB, contains user briefs + scripts), `services/knowledge_vault/vault.db` (87 MB),
  root `jobs.db`; plus **`signups.csv` (user emails / PII)** and `streamlit_debug.log` and
  5 historical PDFs in `outputs/`. `.gitignore` has no `*.db` rule.
- **H8 — confidence over-calibration** (`data/parameters/proliferation.json`): 20/25 entries
  lack peer-reviewed DOI/PMID (ATCC sheets, one "ResearchGate user reports") yet are tagged
  `high`. False precision a QA reviewer will escalate.

### MEDIUM (selected)

- **M1** — silent vault→ChromaDB fallback with no artifact flag (`core/knowledge_vault.py:27`):
  two reports for the same inputs can disagree with no recorded reason.
- **M2** — `_generate_executive_summary` may silently swap LLM text for the template with no
  PDF flag (`core/export.py:206`).
- **M3** — CI has **no coverage gate** and is hard-gated on `ANTHROPIC_API_KEY`; LLM-path tests
  *skip-not-fail* in CI → false green. No timeout, no Python-version pin (declares `>=3.13`,
  `.python-version` says `3.12`).
- **M4** — bare `print()` logging throughout `core/`; `[SANITIZED]`/`[SECURITY]` events have no
  real audit trail. No `run_id` correlation.
- **M5** — `migration_insights` chemotaxis threshold, glucose D, degradation first-order model
  uncited/undisclosed-as-approximation.
- **M6** — lattice silently clamped to (80,80,40) (`runner.py:460`); user gets different geometry
  than specified with no warning.
- **M7** — prompt-injection sanitizer is shallow (literal patterns only); CC3D script validator
  is per-line regex, not a reliable boundary.
- **M8** — deprecated libs: `langchain_community...Chroma` (→ `langchain_chroma`), Pydantic
  `class Config` (→ `ConfigDict`). `trimesh`/`reportlab` appear unused (verify before removal).

### LOW
Dead `core/viz.py.tmp` (0 bytes); `.ralph/` cruft; duplicate test assertions; weak/tautological
tests (`test_sim_brief.py` patches the function under test; `test_overnight` string-greps `app.py`);
`test_public_data` references `data/public/hepatic|transplant/` dirs that don't exist → fail on
clean checkout; viz seed inconsistency (42 vs 7); `ai_narrative` field name (internal "AI" usage).

---

## Avatar fit

- **Academic PI** — the deterministic fallback, parameter derivations, and PMID-cited variance
  report are trustworthy and peer-review-shaped. Trust breaks on: C1 (wrong physics), H1
  (hallucinated PMIDs), H3 (wrong citation), and the absence of a confirm-your-inputs step.
- **Pharma preclinical scientist** — blocked today by C2 (unseeded stochastic run) + H2 (no
  audit-trail/provenance) + M1 (invisible retrieval-path divergence). These are exactly the
  QA/regulatory checkboxes; none are far off.

---

## Ranked opportunity backlog

Ranked by *trust-leverage* (does a skeptic's first read survive it?). Charter tiers in brackets.
**The T0 trust-spine is items 1–6** — they fall straight out of the CRITICAL/HIGH findings.

| # | Item | Tier | Why it's ranked here |
|---|---|:--:|---|
| **1** | **Fix the Krogh O2 formula + add a unit-correct test** (`migration_insights.py:97`) | T0 | Correctness gate. A wrong core prediction destroys trust instantly; cheap, localized fix; testable against a hand-calc. |
| **2** | **Pin CC3D `<RandomSeed>` + seed mitosis; expose+stamp the seed** (`runner.py:128,305`) | T0 | Categorical reproducibility fix; one XML element + plumb the seed into job metadata. |
| **3** | **Per-run provenance**: add `run_id/generated_at/llm_model/temp/lib_version/kb_id/path` to `VarianceReport` + job metadata + stamp into outputs | T0 | Makes every artifact self-describing & re-derivable — pillars 1+3. Unblocks the citable bundle (#7). |
| **4** | **Cross-validate LLM PMIDs** against retrieved docs; flag/strip unmatched (`rag.py:540`, `expand_action_plan.py`) | T0 | Removes hallucinated-citation risk in the most-read section. |
| **5** | **Literature-validation suite** — encode ~5 published constructs (incl. GelMA 6%≈7.2 kPa → cirrhotic-hepatic, PMID 30265900) as CI benchmarks asserting expected tier/flag | T0 | The charter's non-negotiable "validate against known data"; also the public credibility surface. |
| **6** | **Tests for the scientific spine** — `migration_insights`, `feasibility`, `parameter_library`, `doe`, `rag` synthesis (≥90% touched) | T0 | Extends the ratchet floor to the compute paths; would have caught C1. |
| 7 | **Citable run bundle export** — ZIP of brief + XML + metadata(versions,seed) + VTK + methods-prose README | T1 | The artifact a PI pastes into a supplement; depends on #2,#3. |
| 8 | Fix neural stiffness citation (H3); cite porosity 60–85%, chemotaxis, persistence, DOE weights (H4/M5) | T1 | Each is one citation or an "estimated" downgrade; removes ungrounded-number flags. |
| 9 | Compute SCF from the FEA field or document it as a fixed analytical approximation (`fem_solver.py:276`) | T1 | Stops presenting a constant as a computed value. |
| 10 | Recalibrate `proliferation.json` confidence (ATCC→medium, ResearchGate→low) (H8) | T1 | Honest confidence is itself a trust signal. |
| 11 | Surface `parameter_derivations.json` in `gap_report()`/UI; flag LLM-vs-deterministic path in PDF (M2) | T1 | Converts an excellent hidden asset into a visible one; discloses methodology. |
| 12 | Structured logging + `run_id` propagation; emit retrieval path (vault/Chroma) as a field (M1/M4) | T1/obs | Cheapest observability lift; enables audit + post-hoc query. |
| 13 | Document O2 units (lattice²/MCS, fraction 0–1); surface lattice clamp + mesh-convergence note | T2 | Removes unit ambiguity for the skeptic. |
| 14 | Confirm-your-inputs step after chat elicitation; lower elicitation non-determinism | T2 | Avatar needs to verify the system understood them before trusting output. |
| 15 | Academic methods-section export + pharma audit-trail export | T2 | Avatar-fit deliverables (depend on T0). |
| 16 | Public validation-case gallery; Cytoink/WFIRM flagship validated run | T3 | Viral/credibility surface — only after T0–T2 hold. |

### Hygiene / CI / security track (do alongside, mostly independent)
Rotate the OpenRouter key + inject at deploy (H6). `git rm --cached` the DBs / `signups.csv` /
`streamlit_debug.log` / tracked PDFs and add `*.db`,`*.db-wal`,`*.db-shm` to `.gitignore` (H7).
Add `--cov=core --cov-fail-under=60` + `timeout-minutes` to CI; reconcile Python version; make
LLM-path tests fail-not-skip with a deterministic mock; create the missing `data/public/*` stubs
so `test_public_data` passes on clean checkout (M3). Enforce `STROMALYTIX_ENFORCE_API_KEY` in the
vault service. Migrate Chroma + Pydantic deprecations; verify+drop unused `trimesh`/`reportlab`;
delete `core/viz.py.tmp`.

---

## Notes on method & limits
Three independent read-only audits (RAG/claims, simulation core, app/CI/security) cross-checked
against the charter; findings cite `file:line`. The full suite was **not executed live** (needs
LLM keys + CC3D conda env); coverage gaps are assessed statically. Numeric pillar scores are
reviewer judgment, not a measured metric — they rank attention, not certify quality. **No files
were modified by the audit.** Remediation lands as separate, ratchet-compliant changes on this
branch, queued for approval (see Phase-3 cycle output).
