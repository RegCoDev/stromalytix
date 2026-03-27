# Stromalytix Overnight Test Suite — Baseline Results

**Date**: 2026-03-07
**Time**: Pre-overnight run
**Command**: `uv run pytest tests/test_overnight.py -v --tb=short`

## Overall Results

```
================= 7 passed, 10 skipped, 3 warnings in 33.59s ==================
```

## Test-by-Test Breakdown

### ✅ TEST 1 — Session defaults (2/2 PASSED)

- **test_session_state_defaults**: PASSED ✓
  - Verified app.py initializes with `phase = "assessment"` (chat-first)
  - Verified session state initializes `construct_profile`

- **test_construct_profile_fields**: PASSED ✓
  - All required fields exist: target_tissue, cell_types, scaffold_material, stiffness_kpa, porosity_percent, cell_density_per_ml, experimental_goal, primary_readout
  - Model can be instantiated with full data

### ✅ TEST 2 — RAG Pipeline (3/3 PASSED)

- **test_vectorstore_loads_with_documents**: PASSED ✓
  - ChromaDB vectorstore loads successfully
  - Contains **3,192 documents** (> 3000 threshold)

- **test_retrieve_benchmarks_returns_documents**: PASSED ✓
  - Mock cardiac profile retrieves **12 documents**
  - Exceeds minimum 5 document threshold

- **test_retrieved_docs_have_pmid_metadata**: PASSED ✓
  - All 12 retrieved documents have PMID metadata
  - No missing or empty PMIDs

### ⏭️ TEST 3 — Simulation Brief Confidence Tagging (0/3 PASSED, 3 SKIPPED)

- **test_simulation_brief_has_confidence_tags**: SKIPPED
  - Reason: Confidence tagging not yet implemented
  - **ACTION NEEDED**: Add confidence keys to adhesion_energies in simulation brief

- **test_confidence_values_are_valid**: SKIPPED
  - Reason: Placeholder for future validation
  - **ACTION NEEDED**: Validate confidence values are "high", "medium", or "low"

- **test_simulation_brief_has_supporting_pmids**: PASSED ✓
  - Simulation brief generates successfully
  - Contains valid JSON structure

### ⏭️ TEST 4 — CC3D Parameters KB (0/3 PASSED, 3 SKIPPED)

- **test_cc3d_params_kb_exists**: SKIPPED
  - Reason: `data/raw_abstracts/cc3d_parameters.json` does not exist
  - **ACTION NEEDED**: Create CC3D parameters knowledge base

- **test_cc3d_params_kb_has_records**: SKIPPED
  - Reason: KB file not found
  - **ACTION NEEDED**: Populate with >= 50 records

- **test_cc3d_params_kb_record_structure**: SKIPPED
  - Reason: KB file not found
  - **ACTION NEEDED**: Ensure each record has pmid, title, abstract fields

### ⏭️ TEST 5 — PDF Export (1/3 PASSED, 2 SKIPPED)

- **test_outputs_directory_exists**: PASSED ✓
  - `outputs/` directory exists and is a directory

- **test_pdf_export_function_exists**: SKIPPED
  - Reason: `generate_pdf_report()` not found in core.rag or core.export
  - **ACTION NEEDED**: Implement PDF export function

- **test_pdf_generation_creates_file**: SKIPPED
  - Reason: Function not implemented
  - **ACTION NEEDED**: Verify PDF generation creates .pdf file

### ⏭️ TEST 6 — Demo Mode (0/3 PASSED, 3 SKIPPED)

- **test_demo_script_exists**: SKIPPED
  - Reason: `scripts/generate_demo_data.py` does not exist
  - **ACTION NEEDED**: Create demo data generation script

- **test_demo_script_returns_variance_report**: SKIPPED
  - Reason: Demo script not found
  - **ACTION NEEDED**: Implement `generate_demo_report()` function

- **test_demo_report_has_cardiac_tissue**: SKIPPED
  - Reason: Demo script not found
  - **ACTION NEEDED**: Ensure demo returns cardiac tissue profile

## Warnings

1. **Pydantic Deprecation** (core/models.py lines 12, 48):
   - Support for class-based `config` is deprecated
   - **RECOMMENDATION**: Migrate to `ConfigDict` before Pydantic V3.0

2. **LangChain Deprecation** (core/rag.py:113):
   - `Chroma` class deprecated in LangChain 0.2.9
   - **RECOMMENDATION**: Migrate to `langchain-chroma` package

## Success Criteria for Overnight Run

To achieve 100% test pass rate, the following must be implemented:

### High Priority (Core Functionality)
1. **CC3D Parameters KB**: Create knowledge base with 50+ records
2. **Confidence Tagging**: Add confidence scores to simulation brief parameters
3. **Demo Mode**: Create generate_demo_data.py script

### Medium Priority (Export Features)
4. **PDF Export**: Implement generate_pdf_report() function

### Low Priority (Code Hygiene)
5. **Pydantic Migration**: Update to ConfigDict
6. **LangChain Migration**: Switch to langchain-chroma

## How to Re-Run Tests

```bash
# Full test suite with verbose output
uv run pytest tests/test_overnight.py -v --tb=short

# Run specific test category
uv run pytest tests/test_overnight.py::test_cc3d_params_kb_exists -v

# Run with coverage
uv run pytest tests/test_overnight.py --cov=core --cov-report=term-missing
```

## Next Steps for Ralph Loop

The Ralph Loop should focus on implementing the skipped tests in this order:

1. **TEST 4**: Build CC3D parameters knowledge base (highest impact)
2. **TEST 3**: Add confidence tagging to simulation briefs (medium impact)
3. **TEST 6**: Create demo mode for quick testing (high utility)
4. **TEST 5**: Implement PDF export (user-facing feature)

All tests should PASS (not SKIP) before deploying to production.
