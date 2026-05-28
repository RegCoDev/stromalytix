# Queued for your approval — MAS Opportunity Engine, cycle 002 addendum

**2026-05-28 — cycle 002 added one commit to this branch:**

| Commit | What |
|---|---|
| `ab6a1a7` | **fix(cc3d): seed Potts RNG for deterministic runs (C2, CRITICAL)** — `services/cc3d_runner_api/runner.py`. Adds `resolve_random_seed(brief)` + `DEFAULT_RANDOM_SEED`, emits `<RandomSeed>` in the Potts block, wires the seed through `generate_cc3d_project`. Also makes mitosis deterministic (same global RNG). +5 tests (the module had 0 — how C2 survived). Self-describing: the seed is visible in the emitted XML. |

This closes backlog item **#2** (the second T0 trust-spine item, after cycle-001's
Krogh fix #1). Verified by an independent `verifier` agent — PASS on all 6 checks
(tests pass, `<RandomSeed>` correctly inside `<Potts>`, 3-tuple return unchanged so
no caller breaks, no secrets, only 2 files touched, `/opt/stromalytix` untouched).
**Decision: merge `ab6a1a7`?** Recommend yes — correctness + reproducibility, fully tested.

Next T0 autonomous items still open (ranked): #3 per-run provenance (H2), #4 LLM-PMID
cross-validation (H1), #6 scientific-spine tests, then #5 literature-validation suite.

---

# Queued for your approval — MAS Opportunity Engine, cycle 001

**Branch:** `mas-opportunity-engine` (git worktree at `/root/worktrees/stromalytix-mas`)
**Date:** 2026-05-28 · **Nothing merged, shipped, or cron-activated.** Review the branch, then merge what you want.

You asked to wake to **queued work + a short escalation list, not a goal to fire.** Here it is.

---

## What landed (4 commits, all on the branch)

| Commit | What |
|---|---|
| `5e899bf` | **The Opportunity Engine** — the standing habit. `opportunity_engine/` (ingest→rank→partition→execute→escalate). 71 tests, 98% coverage. |
| `14722bb` | **`REVIEW.md`** — full Stromalytix code review (3 audits) + ranked T0–T3 backlog. |
| `bd17131` | Phase-1-review ingest adapter + **first live cycle** output (`opportunity_engine/cycles/`). |
| `2ca260a` | **Executed autonomous item:** fixed a CRITICAL Stromalytix bug + added the module's first 13 tests. |

---

## The autonomous work I did (review, then merge)

**Fixed: Krogh O2-diffusion unit error** (`core/migration_insights.py`) — CRITICAL, from the review.
A unit bug (mol/L treated as mol/cm³, plus a spurious ×1e6) made the tool flag **false-severe hypoxia**
for *standard* constructs. A 4×4×2 mm construct at 10⁶ cells/mL went from a wrong "~0.10 mm penetration →
SEVERE HYPOXIA" to the correct "~7.07 mm → no central hypoxia." Added `tests/test_migration_insights.py`
(13 tests incl. physics-validation + a regression test pinning the old-vs-new result). The module had
**zero tests before** — that's how this survived. Advances **reproducibility + explainability**.
→ This was the top *code-shaped* autonomous item in the live cycle. Verified: 13/13 pass; only 2 files touched.

The other top-ranked autonomous items (per-run provenance, reproducible run artifact, CC3D RandomSeed,
LLM-PMID cross-validation, literature-validation suite, scientific-spine tests) are **staged, not executed**
this cycle (RECORD-mode safety + a per-cycle cap of 5). They sit at the top of the next cycle.

---

## Escalations — needs you (2 genuine blockers)

1. **`FASTMAIL_API_TOKEN` missing from `/root/.hermes/.env`** — drift census flagged it; a key/decision, not something I should invent.
2. **`STRIPE_SECRET_KEY` missing from `/root/.hermes/.env`** — same.

*(The live cycle also found paused/failing crons — `re-leads-cron`, `agent-activity-log`, `affiliate-sync` — ranked as autonomous-fixable infra; not touched this cycle.)*

---

## Decisions waiting on you

1. **Merge the Krogh fix?** It's a correctness fix with tests — recommend yes.
2. **Merge the Opportunity Engine + REVIEW.md?** On merge, the engine's production home is
   `/root/.openclaw/workspace/canonical/opportunity_engine/` (systemd unit paths already point there).
3. **Activate the cadence?** The timer (`cadence/opportunity-engine.timer`) ships **disabled** in RECORD mode.
   Activation is your call — recommend watching a few RECORD cycles first, then flipping `OPP_ENGINE_MODE=live`.
4. **Two secret-handling items** above.
5. From the review (separate, your sign-off): rotate the live `OPENROUTER_API_KEY` in `/opt/stromalytix/.env`;
   `git rm --cached` the 157 MB of committed DBs + `signups.csv` (PII). I did **not** touch the main tree.

---

## Run it yourself

```bash
cd /root/worktrees/stromalytix-mas
python3 -m opportunity_engine.cli run --mock                       # offline demo
python3 -m pytest opportunity_engine/tests/ --cov=opportunity_engine  # 71 tests, 98%
cat REVIEW.md                                                      # the review + backlog
cat opportunity_engine/cycles/cycle-*.md                           # the live cycle
```

— Full design rationale in `opportunity_engine/WHY.md`; how it works in `opportunity_engine/README.md`.
