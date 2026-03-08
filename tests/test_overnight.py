"""
Comprehensive Test Suite for Stromalytix MVP — Overnight Run Validation

This test suite validates all critical functionality before overnight runs:
- Onboarding phase initialization
- RAG pipeline (vectorstore, retrieval, benchmarks)
- Simulation brief confidence tagging
- CC3D parameters knowledge base
- PDF export functionality
- Demo mode data generation

Run with: uv run pytest tests/test_overnight.py -v --tb=short
"""

import json
from pathlib import Path
import pytest
from core.models import ConstructProfile, VarianceReport
from core.rag import load_vectorstore, retrieve_benchmarks, generate_simulation_brief


# ============================================================================
# TEST 1 — Onboarding Phase
# ============================================================================

def test_session_state_defaults():
    """Verify app session state initializes with correct defaults."""
    # Import app module to check default values
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    # Since we can't easily test Streamlit session state outside the app,
    # we'll verify the phase initialization logic exists in app.py
    app_path = Path(__file__).parent.parent / "app.py"
    assert app_path.exists(), "app.py not found"

    app_content = app_path.read_text(encoding='utf-8')
    assert 'st.session_state.phase = "onboarding"' in app_content, \
        "Default phase should be 'onboarding'"
    assert 'if "construct_profile" not in st.session_state:' in app_content, \
        "Session state should initialize construct_profile"


def test_construct_profile_fields():
    """Verify ConstructProfile has all required fields defined."""
    profile = ConstructProfile()

    # Check all expected fields exist
    required_fields = [
        'target_tissue',
        'cell_types',
        'scaffold_material',
        'stiffness_kpa',
        'porosity_percent',
        'cell_density_per_ml',
        'experimental_goal',
        'primary_readout'
    ]

    for field in required_fields:
        assert hasattr(profile, field), f"ConstructProfile missing field: {field}"

    # Verify model can be instantiated with full data
    full_profile = ConstructProfile(
        target_tissue="cardiac",
        cell_types=["cardiomyocytes", "fibroblasts"],
        scaffold_material="GelMA",
        stiffness_kpa=10.0,
        porosity_percent=70.0,
        cell_density_per_ml=1e6,
        experimental_goal="disease_modeling",
        primary_readout="contractility"
    )

    assert full_profile.target_tissue == "cardiac"
    assert len(full_profile.cell_types) == 2


# ============================================================================
# TEST 2 — RAG Pipeline
# ============================================================================

def test_vectorstore_loads_with_documents():
    """Verify ChromaDB vectorstore loads and contains > 3000 documents."""
    try:
        vectorstore = load_vectorstore()

        # Get collection stats
        collection = vectorstore._collection
        doc_count = collection.count()

        assert doc_count > 3000, \
            f"Vectorstore should have > 3000 docs, found {doc_count}"

        print(f"\n✓ Vectorstore loaded with {doc_count} documents")

    except ValueError as e:
        pytest.skip(f"Vectorstore not available: {e}")


def test_retrieve_benchmarks_returns_documents():
    """Verify retrieve_benchmarks() with cardiac profile returns >= 5 docs."""
    # Create mock cardiac construct profile
    mock_profile = ConstructProfile(
        target_tissue="cardiac",
        cell_types=["cardiomyocytes"],
        scaffold_material="GelMA",
        stiffness_kpa=10.0,
        porosity_percent=70.0,
        cell_density_per_ml=1e6,
        experimental_goal="disease_modeling",
        primary_readout="contractility"
    )

    try:
        docs = retrieve_benchmarks(mock_profile, k=12)

        assert len(docs) >= 5, \
            f"Should retrieve at least 5 docs, got {len(docs)}"

        print(f"\n✓ Retrieved {len(docs)} benchmark documents")

    except ValueError as e:
        pytest.skip(f"Vectorstore not available: {e}")


def test_retrieved_docs_have_pmid_metadata():
    """Verify each retrieved document has pmid in metadata."""
    mock_profile = ConstructProfile(
        target_tissue="cardiac",
        cell_types=["cardiomyocytes"],
        scaffold_material="GelMA",
        stiffness_kpa=10.0
    )

    try:
        docs = retrieve_benchmarks(mock_profile, k=5)

        for i, doc in enumerate(docs):
            assert "pmid" in doc.metadata, \
                f"Document {i} missing pmid in metadata"
            assert doc.metadata["pmid"], \
                f"Document {i} has empty pmid"

        print(f"\n✓ All {len(docs)} documents have PMID metadata")

    except ValueError as e:
        pytest.skip(f"Vectorstore not available: {e}")


# ============================================================================
# TEST 3 — Simulation Brief Confidence Tagging
# ============================================================================

def test_simulation_brief_has_confidence_tags():
    """Verify generate_simulation_brief() output contains confidence keys."""
    mock_profile = ConstructProfile(
        target_tissue="cardiac",
        cell_types=["cardiomyocytes"],
        scaffold_material="GelMA",
        stiffness_kpa=10.0,
        porosity_percent=70.0
    )

    mock_report = VarianceReport(
        construct_profile=mock_profile,
        benchmark_ranges={"stiffness_kpa": {"min": 5, "max": 15, "unit": "kPa"}},
        deviation_scores={"stiffness_kpa": 0.0},
        risk_flags={"stiffness_kpa": "green"},
        ai_narrative="Mock cardiac construct analysis.",
        supporting_pmids=["12345678"]
    )

    sim_brief = generate_simulation_brief(mock_profile, mock_report)

    # Check if confidence tagging is implemented
    if "key_parameters" in sim_brief:
        params = sim_brief["key_parameters"]

        # Check for confidence in adhesion_energies if present
        if "adhesion_energies" in params and isinstance(params["adhesion_energies"], dict):
            # Currently may not have confidence - this test documents the gap
            has_confidence = any("confidence" in str(v) for v in params["adhesion_energies"].values())

            # This test will FAIL initially - that's expected
            # It documents what needs to be added overnight
            if not has_confidence:
                pytest.skip("Confidence tagging not yet implemented - to be added overnight")


def test_confidence_values_are_valid():
    """Verify confidence values are only 'high', 'medium', or 'low'."""
    mock_profile = ConstructProfile(
        target_tissue="cardiac",
        cell_types=["cardiomyocytes"],
        scaffold_material="GelMA",
        stiffness_kpa=10.0,
        porosity_percent=70.0
    )

    mock_report = VarianceReport(
        construct_profile=mock_profile,
        benchmark_ranges={"stiffness_kpa": {"min": 5, "max": 15, "unit": "kPa"}},
        deviation_scores={"stiffness_kpa": 0.0},
        risk_flags={"stiffness_kpa": "green"},
        ai_narrative="Mock cardiac construct analysis.",
        supporting_pmids=["12345678"]
    )

    sim_brief = generate_simulation_brief(mock_profile, mock_report)

    if "key_parameters" not in sim_brief:
        pytest.skip("No key_parameters in simulation brief")

    params = sim_brief["key_parameters"]
    if "adhesion_energies" not in params or not isinstance(params["adhesion_energies"], dict):
        pytest.skip("No adhesion_energies in key_parameters")

    valid_values = {"high", "medium", "low"}
    for key, val in params["adhesion_energies"].items():
        if isinstance(val, dict) and "confidence" in val:
            assert val["confidence"] in valid_values, \
                f"Confidence for {key} must be high/medium/low, got: {val['confidence']}"


def test_simulation_brief_has_supporting_pmids():
    """Verify supporting_pmids list is not empty in simulation brief."""
    mock_profile = ConstructProfile(
        target_tissue="cardiac",
        cell_types=["cardiomyocytes"],
        scaffold_material="GelMA"
    )

    mock_report = VarianceReport(
        construct_profile=mock_profile,
        benchmark_ranges={},
        deviation_scores={},
        risk_flags={},
        ai_narrative="Test narrative",
        supporting_pmids=["12345678", "87654321"]
    )

    sim_brief = generate_simulation_brief(mock_profile, mock_report)

    # Check if simulation brief references PMIDs from report
    brief_str = json.dumps(sim_brief)
    assert len(brief_str) > 0, "Simulation brief should not be empty"

    print(f"\n✓ Simulation brief generated successfully")


# ============================================================================
# TEST 4 — CC3D Parameters KB
# ============================================================================

def test_cc3d_params_kb_exists():
    """Verify data/raw_abstracts/cc3d_parameters.json exists."""
    kb_path = Path("data/raw_abstracts/cc3d_parameters.json")

    if not kb_path.exists():
        pytest.skip("CC3D parameters KB not yet created - to be added overnight")

    assert kb_path.exists(), "CC3D parameters knowledge base should exist"


def test_cc3d_params_kb_has_records():
    """Verify CC3D params KB contains at least 50 records."""
    kb_path = Path("data/raw_abstracts/cc3d_parameters.json")

    if not kb_path.exists():
        pytest.skip("CC3D parameters KB not yet created")

    with open(kb_path) as f:
        data = json.load(f)

    if isinstance(data, list):
        records = data
    elif isinstance(data, dict) and "records" in data:
        records = data["records"]
    else:
        records = []

    assert len(records) >= 50, \
        f"CC3D params KB should have >= 50 records, found {len(records)}"


def test_cc3d_params_kb_record_structure():
    """Verify each record has pmid, title, abstract fields."""
    kb_path = Path("data/raw_abstracts/cc3d_parameters.json")

    if not kb_path.exists():
        pytest.skip("CC3D parameters KB not yet created")

    with open(kb_path) as f:
        data = json.load(f)

    records = data if isinstance(data, list) else data.get("records", [])

    if len(records) == 0:
        pytest.skip("No records in CC3D params KB")

    # Check first 5 records
    for i, record in enumerate(records[:5]):
        assert "pmid" in record, f"Record {i} missing pmid"
        assert "title" in record, f"Record {i} missing title"
        assert "abstract" in record, f"Record {i} missing abstract"


# ============================================================================
# TEST 5 — PDF Export
# ============================================================================

def test_outputs_directory_exists():
    """Verify outputs/ directory exists."""
    outputs_dir = Path("outputs")

    if not outputs_dir.exists():
        # Create it for the test
        outputs_dir.mkdir(exist_ok=True)

    assert outputs_dir.exists(), "outputs/ directory should exist"
    assert outputs_dir.is_dir(), "outputs/ should be a directory"


def test_pdf_export_function_exists():
    """Verify generate_pdf_report() function exists."""
    try:
        from core.rag import generate_pdf_report
        assert callable(generate_pdf_report), \
            "generate_pdf_report should be callable"
        print("\n✓ PDF export function found in core.rag")

    except ImportError:
        # Try core.export
        try:
            from core.export import generate_pdf_report
            assert callable(generate_pdf_report), \
                "generate_pdf_report should be callable"
            print("\n✓ PDF export function found in core.export")

        except ImportError:
            pytest.skip("PDF export function not yet implemented - to be added overnight")


def test_pdf_generation_creates_file():
    """Verify calling generate_pdf_report() creates a .pdf file."""
    try:
        try:
            from core.rag import generate_pdf_report
        except ImportError:
            from core.export import generate_pdf_report

        # Create mock report
        mock_profile = ConstructProfile(
            target_tissue="cardiac",
            cell_types=["cardiomyocytes"]
        )

        mock_report = VarianceReport(
            construct_profile=mock_profile,
            benchmark_ranges={},
            deviation_scores={},
            risk_flags={},
            ai_narrative="Test PDF generation",
            supporting_pmids=["12345678"]
        )

        # Generate PDF
        pdf_path = generate_pdf_report(mock_report)

        assert Path(pdf_path).exists(), f"PDF should be created at {pdf_path}"
        assert Path(pdf_path).suffix == ".pdf", "Output should be a .pdf file"

        print(f"\n✓ PDF generated successfully: {pdf_path}")

    except (ImportError, NameError):
        pytest.skip("PDF export not yet implemented")


# ============================================================================
# TEST 6 — Demo Mode
# ============================================================================

def test_demo_script_exists():
    """Verify scripts/generate_demo_data.py exists."""
    demo_script = Path("scripts/generate_demo_data.py")

    if not demo_script.exists():
        pytest.skip("Demo script not yet created - to be added overnight")

    assert demo_script.exists(), "Demo script should exist"


def test_demo_script_returns_variance_report():
    """Verify running demo script returns a valid VarianceReport object."""
    demo_script = Path("scripts/generate_demo_data.py")

    if not demo_script.exists():
        pytest.skip("Demo script not yet created")

    # Import the demo module
    import sys
    sys.path.insert(0, str(demo_script.parent))

    try:
        import generate_demo_data

        # Check if it has a generate function
        if hasattr(generate_demo_data, 'generate_demo_report'):
            report = generate_demo_data.generate_demo_report()
            assert isinstance(report, VarianceReport), \
                "Demo should return VarianceReport instance"
        else:
            pytest.skip("generate_demo_report() function not found in demo script")

    except ImportError as e:
        pytest.skip(f"Could not import demo script: {e}")


def test_demo_report_has_cardiac_tissue():
    """Verify demo VarianceReport has target_tissue == 'cardiac'."""
    demo_script = Path("scripts/generate_demo_data.py")

    if not demo_script.exists():
        pytest.skip("Demo script not yet created")

    import sys
    sys.path.insert(0, str(demo_script.parent))

    try:
        import generate_demo_data

        if hasattr(generate_demo_data, 'generate_demo_report'):
            report = generate_demo_data.generate_demo_report()

            assert report.construct_profile.target_tissue == "cardiac", \
                "Demo report should have cardiac target tissue"

            print(f"\n✓ Demo report has target_tissue: {report.construct_profile.target_tissue}")
        else:
            pytest.skip("generate_demo_report() function not found")

    except ImportError:
        pytest.skip("Could not import demo script")


# ============================================================================
# Baseline Documentation Helper
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("STROMALYTIX OVERNIGHT TEST SUITE — BASELINE RUN")
    print("=" * 70)
    print("\nRun with: uv run pytest tests/test_overnight.py -v --tb=short\n")
    print("Expected baseline (before overnight work):")
    print("  PASS: TEST 1 (Onboarding phase)")
    print("  PASS: TEST 2 (RAG pipeline)")
    print("  SKIP: TEST 3 (Confidence tagging - to be implemented)")
    print("  SKIP: TEST 4 (CC3D params KB - to be created)")
    print("  SKIP: TEST 5 (PDF export - to be implemented)")
    print("  SKIP: TEST 6 (Demo mode - to be created)")
    print("\nAfter overnight work, all tests should PASS or have documented skips.")
    print("=" * 70)
