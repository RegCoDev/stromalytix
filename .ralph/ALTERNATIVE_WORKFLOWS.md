# Alternative Workflows (Ralph Loop Not Available)

**Status**: Ralph Loop plugin does not exist in Claude Code marketplace

The autonomous iterative development workflow described for "Ralph Loop" is a great concept, but we need alternative approaches. Here are practical solutions:

---

## Option 1: Semi-Automated Dev Loop (Best for Overnight)

Use the included Python script for guided iteration:

```bash
uv run python scripts/dev_loop.py
```

**What it does**:
1. Runs `pytest tests/test_overnight.py -v`
2. Shows test results (7/17 passed, 10 skipped)
3. Waits for you to implement fixes
4. Press Enter → runs tests again
5. Repeats until all 17 tests pass

**Benefits**:
- Automatic test running and result tracking
- Logs all iterations to `logs/dev_loop_*.log`
- Stops automatically when all tests pass
- You control the implementation pace

**Workflow**:
1. Run `uv run python scripts/dev_loop.py`
2. See which test is failing/skipped
3. Read `.ralph/overnight_implementation.md` for that test
4. Implement the feature
5. Press Enter to re-run tests
6. Repeat

---

## Option 2: Manual Test-Driven Development (Simplest)

Classic TDD approach with our test suite:

```bash
# Step 1: See what needs work
uv run pytest tests/test_overnight.py -v --tb=short

# Step 2: Read implementation guide
cat .ralph/overnight_implementation.md

# Step 3: Pick a SKIPPED test (prioritize TEST 4 → TEST 3 → TEST 6 → TEST 5)

# Step 4: Implement feature for that test

# Step 5: Verify
uv run pytest tests/test_overnight.py::test_name -v

# Step 6: Repeat until all pass
```

**Best for**: Focused work sessions, learning the codebase

---

## Option 3: Watch Mode (Continuous Testing)

Install pytest-watch for automatic re-running:

```bash
uv add --dev pytest-watch
uv run ptw tests/test_overnight.py -- -v --tb=short
```

**What it does**:
- Watches for file changes
- Automatically re-runs tests when you save
- Shows results in real-time

**Benefits**:
- Instant feedback
- No manual test running
- Great for rapid iteration

**Best for**: Active development sessions

---

## Option 4: IDE Integration

If using VS Code with Python extension:

1. Open Testing panel (beaker icon)
2. Configure to use pytest
3. Run/debug individual tests
4. See results inline

**Benefits**:
- Visual test explorer
- Debugging support
- Inline failure messages

---

## Option 5: GitHub Actions / CI (True Autonomous)

For actual overnight autonomous development, use CI/CD:

**Create `.github/workflows/overnight_dev.yml`**:

```yaml
name: Overnight Development

on:
  workflow_dispatch:  # Manual trigger

jobs:
  iterative_dev:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python & uv
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          uv sync

      - name: Run Dev Loop
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          # This would require a fully autonomous agent
          # Currently, human implementation is needed
          uv run pytest tests/test_overnight.py -v

      - name: Commit changes
        run: |
          git config user.name "CI Bot"
          git config user.email "ci@stromalytix.dev"
          git add .
          git commit -m "ci: overnight development iteration" || true
          git push
```

**Limitations**: Still requires human to write the actual implementation code

---

## Recommended Approach for This Project

**For active work**: Use **Option 1** (dev_loop.py)

```bash
uv run python scripts/dev_loop.py
```

Then work through tests in priority order:

1. **TEST 4** (CC3D KB): Create `data/raw_abstracts/cc3d_parameters.json`
   - Use existing `scripts/scrape_pubmed.py` as template
   - Search for "CompuCell3D" + "Cellular Potts Model"
   - Need 50+ records with pmid, title, abstract

2. **TEST 3** (Confidence Tagging): Modify `core/rag.py`
   - Update `generate_simulation_brief()` prompt
   - Parse confidence from LLM response
   - Validate values are "high"/"medium"/"low"

3. **TEST 6** (Demo Mode): Create `scripts/generate_demo_data.py`
   - Implement `generate_demo_report()` function
   - Return hardcoded cardiac VarianceReport
   - No LLM calls

4. **TEST 5** (PDF Export): Create `core/export.py`
   - Install reportlab: `uv add reportlab`
   - Implement `generate_pdf_report(report: VarianceReport) -> str`
   - Return path to generated PDF

---

## Success Verification

Regardless of which option you use, success is:

```bash
uv run pytest tests/test_overnight.py -v --tb=short
```

Shows:

```
================= 17 passed in X.XXs ==================
```

---

## Why Ralph Loop Concept Is Still Valuable

Even though the plugin doesn't exist, the concept of:
- Clear success criteria (test suite)
- Iterative refinement (dev loop)
- Completion promise ("17 passed")
- Self-referential improvement (reading own code)

...is excellent software engineering practice. We've achieved it through:
- `tests/test_overnight.py` (success criteria)
- `scripts/dev_loop.py` (iteration automation)
- `.ralph/overnight_implementation.md` (detailed guide)
- Git history (tracking progress)

The workflow is sound, just without full autonomy.
