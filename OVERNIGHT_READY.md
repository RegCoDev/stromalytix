# Stromalytix Overnight Run — Ready for Ralph Loop

**Status**: ✅ Test suite created, baseline established, Ralph Loop prompt configured

**Date**: 2026-03-07
**Current State**: 7/17 tests passing, 10 skipped (ready for implementation)

---

## Launch Command

**Note**: Ralph Loop plugin is not available in Claude Code marketplace. Use one of these alternatives:

### Option 1: Manual Test-Driven Development (Recommended)
```bash
uv run python scripts/dev_loop.py
```

This script:
- Runs tests automatically
- Shows which tests are failing/skipped
- Waits for you to implement fixes
- Iterates up to 20 times
- Stops when all 17 tests pass

### Option 2: Direct Test-Driven Workflow
```bash
# 1. Run tests to see what's failing
uv run pytest tests/test_overnight.py -v

# 2. Read the implementation guide
cat .ralph/overnight_implementation.md

# 3. Implement features to fix skipped tests
# 4. Repeat until all pass
```

### Option 3: Continuous Watch Mode (if pytest-watch installed)
```bash
uv add --dev pytest-watch
uv run ptw tests/test_overnight.py -- -v --tb=short
```

---

## What Will Happen

Ralph Loop will autonomously:

1. **Read its prompt** from `.ralph/overnight_implementation.md`
2. **Run tests** via `uv run pytest tests/test_overnight.py -v`
3. **Implement features** to make skipped tests pass
4. **Iterate** up to 20 times, reading its own work each cycle
5. **Stop** when all 17 tests pass or max iterations reached
6. **Output** "DONE: All overnight tests passing" upon completion

---

## Current Baseline (Before Run)

```
================= 7 passed, 10 skipped in 33.59s ==================
```

**PASSING (7)**:
- ✅ Onboarding phase initialization
- ✅ ConstructProfile field validation
- ✅ ChromaDB vectorstore (3,192 documents)
- ✅ Benchmark retrieval (12 docs with PMIDs)
- ✅ PMID metadata validation
- ✅ Simulation brief generation
- ✅ outputs/ directory exists

**SKIPPED (10)** — These will be implemented overnight:
- ⏭️ Confidence tagging for simulation parameters
- ⏭️ CC3D parameters knowledge base (50+ records)
- ⏭️ PDF export functionality
- ⏭️ Demo mode script

---

## Target State (After Run)

```
================= 17 passed in X.XXs ==================
```

All features implemented:
- ✅ `data/raw_abstracts/cc3d_parameters.json` created (50+ records)
- ✅ Confidence tags added to simulation brief parameters
- ✅ `scripts/generate_demo_data.py` created
- ✅ PDF export function implemented
- ✅ All tests passing

---

## Implementation Priorities (Auto-followed by Ralph Loop)

1. **PRIORITY 1**: CC3D Parameters KB (TEST 4)
   - Create knowledge base with 50+ CompuCell3D parameter records
   - Source from PubMed: "CompuCell3D", "Cellular Potts Model", "cell adhesion energy"

2. **PRIORITY 2**: Confidence Tagging (TEST 3)
   - Add confidence scores ("high", "medium", "low") to simulation parameters
   - Based on PMID citation strength

3. **PRIORITY 3**: Demo Mode (TEST 6)
   - Create `generate_demo_data.py` for quick testing
   - Returns realistic cardiac tissue VarianceReport

4. **PRIORITY 4**: PDF Export (TEST 5)
   - Implement `generate_pdf_report()` function
   - Exports variance reports as formatted PDFs

---

## Files That Will Be Created/Modified

**Created**:
- `data/raw_abstracts/cc3d_parameters.json`
- `scripts/generate_demo_data.py`
- `core/export.py` (or modified `core/rag.py`)

**Modified**:
- `core/rag.py` (confidence tagging in `generate_simulation_brief()`)
- `tests/BASELINE.md` (updated with new results)
- `pyproject.toml` / `uv.lock` (if PDF library added: reportlab or fpdf2)

**Preserved**:
- All existing functionality (7 passing tests must stay passing)
- app.py (no changes needed)
- core/models.py (structure is correct)
- core/chat.py (working correctly)

---

## Monitoring Progress

While Ralph Loop runs, you can:

**Watch test progress**:
```bash
uv run pytest tests/test_overnight.py -v --tb=short
```

**View git commits** (each iteration creates commits):
```bash
git log --oneline
```

**Check what changed**:
```bash
git diff HEAD~5 HEAD
```

**Read updated baseline**:
```bash
cat tests/BASELINE.md
```

---

## Expected Timeline

- **Iterations 1-3**: CC3D KB creation
- **Iterations 4-6**: Confidence tagging
- **Iterations 7-9**: Demo mode
- **Iterations 10-15**: PDF export
- **Iterations 16-20**: Debugging/polish

**Estimated Total**: 10-15 iterations (~2-4 hours on fast machine with API access)

---

## Success Detection

Ralph Loop stops automatically when Claude outputs:

```
DONE: All overnight tests passing
```

This happens after:
```bash
uv run pytest tests/test_overnight.py -v --tb=short
```

Shows:
```
================= 17 passed in X.XXs ==================
```

---

## Manual Verification After Completion

Once loop completes, verify:

1. **Run full test suite**:
   ```bash
   uv run pytest tests/test_overnight.py -v
   ```

2. **Test the UI** (ensure nothing broke):
   ```bash
   uv run streamlit run app.py
   ```

3. **Review git history**:
   ```bash
   git log --oneline -20
   ```

4. **Check all files exist**:
   ```bash
   ls data/raw_abstracts/cc3d_parameters.json
   ls scripts/generate_demo_data.py
   ```

5. **Test demo mode**:
   ```bash
   uv run python -c "from scripts.generate_demo_data import generate_demo_report; print(generate_demo_report())"
   ```

6. **Test PDF export**:
   ```bash
   uv run python -c "from core.export import generate_pdf_report; from scripts.generate_demo_data import generate_demo_report; print(generate_pdf_report(generate_demo_report()))"
   ```

---

## If Loop Stops Early

**Max iterations reached**:
- Review `git log` to see progress
- Check which tests still skip: `uv run pytest tests/test_overnight.py -v`
- Manually complete remaining work or re-launch Ralph Loop

**Completion promise not output**:
- Tests may still be failing
- Check test output for errors
- Review Ralph Loop logs

**External dependencies needed**:
- API keys might be required for PubMed scraping
- Ensure `.env` has `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`

---

## Cancellation

To stop the loop manually:

```bash
/cancel-ralph
```

All work up to that point is preserved in git history.

---

## Post-Loop Next Steps

After successful completion:

1. **Create summary commit**:
   ```bash
   git add .
   git commit -m "feat: overnight implementation complete - all 17 tests passing"
   ```

2. **Push to remote** (if using git remote):
   ```bash
   git push
   ```

3. **Test end-to-end flow**:
   - Launch app: `uv run streamlit run app.py`
   - Run through complete assessment
   - Verify variance report generates
   - Test PDF export from UI (if hooked up)
   - Verify demo mode works

4. **Deploy or continue development**:
   - All core features implemented
   - Ready for user testing
   - Can add more features incrementally

---

## Documentation

- **Prompt**: `.ralph/overnight_implementation.md` (detailed instructions for Ralph Loop)
- **Ralph README**: `.ralph/README.md` (how to use Ralph Loop)
- **Test Suite**: `tests/test_overnight.py` (17 tests defining success)
- **Baseline**: `tests/BASELINE.md` (current state documentation)

---

## Ready to Launch

Everything is configured. When you're ready:

```bash
/ralph-loop "$(cat .ralph/overnight_implementation.md)" --max-iterations 20 --completion-promise "DONE: All overnight tests passing"
```

Then check back in a few hours (or morning) to see:
```
DONE: All overnight tests passing
================= 17 passed in X.XXs ==================
```

Good luck! 🚀
