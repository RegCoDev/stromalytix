# Ralph Loop Prompt: Stromalytix Overnight Implementation

**Objective**: Implement all skipped features in tests/test_overnight.py until all tests PASS.

**Completion Promise**: Output "DONE: All overnight tests passing" when `uv run pytest tests/test_overnight.py -v --tb=short` shows 17 PASSED, 0 SKIPPED, 0 FAILED.

---

## Pre-Flight (Do These FIRST, Before Any Implementation)

1. **Git checkpoint**:
   ```bash
   git add -A && git commit -m "pre-ralph checkpoint — 7 passing baseline"
   ```

2. **Install dependencies**:
   ```bash
   uv add fpdf2
   ```

3. **Load environment variables**: If any LLM call fails with an authentication error, ensure dotenv is loaded:
   ```python
   from dotenv import load_dotenv; load_dotenv()
   ```

---

## Your Task

You are working on Stromalytix, a tissue engineering decision intelligence platform. The test suite in `tests/test_overnight.py` defines success criteria. Your job is to implement features until all tests pass.

### Current Baseline (Start)
- ✅ 7 PASSED (onboarding, RAG pipeline, outputs dir, simulation brief)
- ⏭️ 10 SKIPPED (confidence tagging, CC3D KB, PDF export, demo mode)
- ❌ 0 FAILED

### Target State (Done)
- ✅ 17 PASSED
- ⏭️ 0 SKIPPED
- ❌ 0 FAILED

---

## Implementation Priorities

### PRIORITY 1: CC3D Parameters Knowledge Base (TEST 4)
**Tests**: `test_cc3d_params_kb_*`

**Requirements**:
1. Create `data/raw_abstracts/cc3d_parameters.json`
2. Populate with >= 50 records from PubMed
3. Each record must have: `pmid`, `title`, `abstract`
4. Focus on CompuCell3D parameters: adhesion energies, volume constraints, lambda values

**Search Terms**:
- "CompuCell3D" OR "CC3D"
- "cell adhesion energy" + "computational model"
- "Cellular Potts Model" + "parameters"
- "agent based model" + "tissue engineering" + "parameters"

**Action**:
```bash
# Create scraper or manually curate records
# Save to data/raw_abstracts/cc3d_parameters.json

# CRITICAL: After creating the JSON, embed it into ChromaDB:
uv run python scripts/embed_and_index.py
# Verify the collection count grew beyond the baseline (3,192).

# Run: uv run pytest tests/test_overnight.py::test_cc3d_params_kb_exists -v
```

---

### PRIORITY 2: Confidence Tagging (TEST 3)
**Tests**: `test_simulation_brief_has_confidence_tags`, `test_confidence_values_are_valid`

**Requirements**:
1. Modify `core/rag.py::generate_simulation_brief()`
2. Add `"confidence"` key to each parameter in `adhesion_energies`
3. Confidence values must be: `"high"`, `"medium"`, or `"low"`
4. Base confidence on:
   - **high**: Parameter directly cited in retrieved PMIDs
   - **medium**: Parameter inferred from similar tissue types
   - **low**: Parameter estimated from general physics

**Example Output**:
```json
{
  "key_parameters": {
    "adhesion_energies": {
      "cardiomyocyte-cardiomyocyte": {
        "value": 10,
        "confidence": "high",
        "source_pmids": ["12345678"]
      },
      "cardiomyocyte-medium": {
        "value": 15,
        "confidence": "medium",
        "source_pmids": []
      }
    }
  }
}
```

**Action**:
```bash
# Update generate_simulation_brief() prompt and response parsing
# Run: uv run pytest tests/test_overnight.py::test_simulation_brief_has_confidence_tags -v
```

---

### PRIORITY 3: Demo Mode (TEST 6)
**Tests**: `test_demo_script_*`

**Requirements**:
1. Create `scripts/generate_demo_data.py`
2. Implement `generate_demo_report()` function
3. Returns a `VarianceReport` with `target_tissue = "cardiac"`
4. Use realistic demo values (don't call actual LLMs)
5. Include 3-5 fake PMIDs for testing

**IMPORTANT**: Before implementing, read `core/models.py` carefully and match ALL field names exactly to the actual VarianceReport and ConstructProfile Pydantic definitions. Do not use the field names from this prompt as ground truth — use the model source code.

**Example Implementation**:
```python
def generate_demo_report() -> VarianceReport:
    """Generate demo cardiac tissue report for testing."""
    profile = ConstructProfile(
        target_tissue="cardiac",
        cell_types=["cardiomyocytes", "fibroblasts"],
        scaffold_material="GelMA",
        stiffness_kpa=10.0,
        porosity_percent=70.0,
        cell_density_per_ml=1e6,
        experimental_goal="disease_modeling",
        primary_readout="contractility"
    )

    return VarianceReport(
        construct_profile=profile,
        benchmark_ranges={
            "stiffness_kpa": {"min": 8, "max": 12, "unit": "kPa", "source_pmids": ["12345678"]}
        },
        deviation_scores={"stiffness_kpa": 0.0},
        risk_flags={"stiffness_kpa": "green"},
        ai_narrative="Demo cardiac construct with optimal stiffness (PMID: 12345678).",
        supporting_pmids=["12345678", "87654321"],
        key_references=[
            {"pmid": "12345678", "title": "Demo Paper 1", "year": "2023", "relevance_note": "Cardiac stiffness"}
        ]
    )
```

**Action**:
```bash
# Create scripts/generate_demo_data.py
# Run: uv run pytest tests/test_overnight.py::test_demo_script_exists -v
```

---

### PRIORITY 4: PDF Export (TEST 5)
**Tests**: `test_pdf_export_function_exists`, `test_pdf_generation_creates_file`

**Requirements**:
1. Create function in `core/rag.py` or new `core/export.py`
2. Function signature: `generate_pdf_report(report: VarianceReport) -> str`
3. Returns path to generated PDF file
4. PDF should include:
   - Construct profile summary
   - Benchmark ranges table
   - Deviation scores visualization
   - AI narrative
   - Key references with PMIDs

**Suggested Libraries**:
- `reportlab` (low-level, full control)
- `fpdf2` (simple, lightweight)
- `weasyprint` (HTML to PDF, requires system dependencies)

**Action**:
```bash
# Install: uv add reportlab  # or fpdf2
# Implement generate_pdf_report()
# Run: uv run pytest tests/test_overnight.py::test_pdf_export_function_exists -v
```

---

## Iterative Development Protocol

### On Each Iteration:

1. **Run Tests First**:
   ```bash
   uv run pytest tests/test_overnight.py -v --tb=short
   ```

2. **Identify Next Failure**:
   - Pick the highest priority SKIPPED test
   - Read the test code to understand requirements
   - Check skip reason message

3. **Implement Feature**:
   - Make minimal changes to pass the test
   - Follow existing code patterns in the codebase
   - Preserve all existing functionality

4. **Verify**:
   - Re-run specific test: `uv run pytest tests/test_overnight.py::test_name -v`
   - Ensure it changes from SKIPPED to PASSED
   - Run full suite to check for regressions

5. **Document Progress**:
   - Update tests/BASELINE.md with new results
   - Commit changes: `git add . && git commit -m "feat: implement [feature]"`

6. **Check Completion**:
   - If all 17 tests PASS → Output "DONE: All overnight tests passing"
   - If tests still SKIP/FAIL → Continue to next iteration

---

## Common Pitfalls to Avoid

1. **Don't modify test files** - Tests are the success criteria, not the implementation
2. **Don't skip proper validation** - Confidence values must be exactly "high", "medium", or "low"
3. **Don't call LLM APIs in demo mode** - Demo should work offline
4. **Don't break existing features** - 7 tests already pass, keep them passing
5. **Use consistent file structure** - Follow existing patterns (core/, scripts/, data/)
6. **Always embed after scraping** - After adding any new documents to `data/raw_abstracts/`, run `uv run python scripts/embed_and_index.py` to update ChromaDB
7. **Load API keys** - If any LLM call fails with authentication errors, add `from dotenv import load_dotenv; load_dotenv()` at the top of the module
8. **Read models.py before implementing** - Always verify field names against `core/models.py` source, not prompt examples

---

## Success Criteria Checklist

Before outputting "DONE", verify:

- [ ] `data/raw_abstracts/cc3d_parameters.json` exists with 50+ records
- [ ] Each record has pmid, title, abstract fields
- [ ] `generate_simulation_brief()` returns confidence tags for all parameters
- [ ] Confidence values are only "high", "medium", or "low"
- [ ] `scripts/generate_demo_data.py` exists
- [ ] `generate_demo_report()` returns VarianceReport with target_tissue="cardiac"
- [ ] `generate_pdf_report()` function exists in core/rag.py or core/export.py
- [ ] Calling `generate_pdf_report()` creates a .pdf file in outputs/
- [ ] All 17 tests in `tests/test_overnight.py` show PASSED
- [ ] Zero SKIPPED tests
- [ ] Zero FAILED tests

---

## Final Verification Command

```bash
uv run pytest tests/test_overnight.py -v --tb=short
```

If output shows:
```
================= 17 passed in X.XXs ==================
```

Then output: **DONE: All overnight tests passing**

Otherwise, continue iterating.

---

## Quick Reference

**Run all tests**: `uv run pytest tests/test_overnight.py -v --tb=short`
**Run specific test**: `uv run pytest tests/test_overnight.py::test_name -v`
**Check baseline**: `cat tests/BASELINE.md`
**See what changed**: `git diff`
**Current directory**: C:\dev\stromalytix

Good luck! Focus on making tests pass, one at a time. The tests define success.
