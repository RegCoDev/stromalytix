"""
Load Centara demo data and run full PI analysis pipeline.

Usage: uv run python scripts/load_centara_demo.py
"""
from pathlib import Path

from connectors.eln_csv import ELNCSVConnector
from connectors.crm_csv import CRMCSVConnector
from core.bio_process_miner import BiologicalProcessMiner
from core.company_context import create_centara_demo_context


def main():
    print("Loading Centara demo data...")

    # Load ELN data
    eln = ELNCSVConnector(filepath="data/demo/centara_eln.csv")
    eln_events = eln.extract()
    print(f"  ELN events: {len(eln_events)}")

    # Load CRM data
    crm = CRMCSVConnector(filepath="data/demo/centara_crm.csv")
    crm_events = crm.extract()
    print(f"  CRM events: {len(crm_events)}")

    # Run process mining
    miner = BiologicalProcessMiner()
    miner.add_event_log(eln_events, "centara_eln")

    result = miner.analyze(
        "centara_eln",
        outcome_column="viability",
        reference_protocol=["cell_seeding", "bioprinting", "crosslinking", "incubation", "measurement"],
    )

    print(f"\nAnalysis results:")
    print(f"  Algorithm: {result['routing']['algorithm']}")
    print(f"  Cases: {result['characterization']['case_count']}")
    print(f"  Variants: {result['characterization']['variant_count']}")
    print(f"  Warnings: {result['characterization'].get('warnings', [])}")

    if result.get("conformance"):
        agg = result["conformance"].get("aggregate", {})
        print(f"  Mean fitness: {agg.get('mean_fitness', 'N/A')}")
        print(f"  Conformance rate: {agg.get('conformance_rate', 'N/A')}")

    # Batch effects
    batch_results = miner.bio_ext.separate_batch_effects(
        eln_events, "batch_id", "viability"
    )
    flagged = [k for k, v in batch_results.items() if isinstance(v, dict) and v.get("flagged")]
    print(f"  Flagged batches: {flagged}")

    # Business correlation
    biz = miner.bio_ext.correlate_business_outcomes(eln_events, crm_events)
    print(f"  Business correlations: {list(biz.keys())}")

    # Create/update company context
    ctx = create_centara_demo_context()
    ctx.last_analysis_summary = (
        f"{len(eln_events)} events across {result['characterization']['case_count']} cases. "
        f"Algorithm: {result['routing']['algorithm']}. "
        f"Flagged batches: {', '.join(flagged) if flagged else 'none'}."
    )
    ctx.save()

    print(f"\nCentara demo loaded successfully!")
    print(f"  Context saved to: data/company_contexts/centara_demo.json")


if __name__ == "__main__":
    main()
