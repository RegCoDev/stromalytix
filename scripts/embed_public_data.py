"""
scripts/embed_public_data.py

Embeds public dataset summaries into ChromaDB collections:
- transplant_intelligence: NMP trial criteria and parameters
- calibration_benchmarks: literature benchmark entries with DOIs

Uses same embedding model as main KB (text-embedding-3-small).
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY not found in .env file")

CHROMA_DIR = Path("data/chroma_db")
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")


def embed_transplant_intelligence():
    """Embed NMP trial data into transplant_intelligence collection."""
    docs = []

    # --- VITTAL trial ---
    vittal_path = Path("data/public/transplant/nmp_vittal_summary.json")
    vittal = json.loads(vittal_path.read_text())

    # Trial overview
    docs.append(Document(
        page_content=(
            f"VITTAL trial (Nasralla et al. Nature 2018, n={vittal['n']}). "
            f"NMP reduced peak AST by 50% vs cold storage. "
            f"EAD rate NMP: {vittal['nmp_arm_summary']['ead_rate_nmp']:.0%} vs "
            f"cold storage: {vittal['nmp_arm_summary']['ead_rate_cold_storage']:.0%}. "
            f"Viability criterion: lactate <2.5 mmol/L at 2h."
        ),
        metadata={
            "source_doi": vittal["doi"],
            "trial_name": "VITTAL",
            "parameter_type": "trial_overview",
        },
    ))

    # Individual NMP parameters from VITTAL
    summary = vittal["nmp_arm_summary"]
    nmp_params = [
        ("lactate_clearance", f"Lactate clearance median {summary['lactate_clearance_median_h']}h "
         f"(IQR {summary['lactate_clearance_iqr']}). "
         f"Viability threshold: <2.5 mmol/L by 2h of NMP perfusion."),
        ("bile_ph", f"Bile pH median {summary['bile_ph_median']}. "
         f"Viability threshold: >7.2 (cholangiocyte function marker)."),
        ("arterial_flow", f"Arterial flow median {summary['arterial_flow_median_ml_min']} mL/min. "
         f"Viability threshold: >150 mL/min (hepatic artery compliance)."),
        ("portal_flow", f"Portal flow median {summary['portal_flow_median_ml_min']} mL/min. "
         f"Viability threshold: >500 mL/min (portal vein compliance)."),
        ("o2_consumption", f"O2 consumption median {summary['o2_consumption_median_mmol_h']} mmol/h. "
         f"Viability threshold: >28 mmol/h (metabolic activity)."),
        ("ead_rate", f"EAD rate NMP arm: {summary['ead_rate_nmp']:.1%}. "
         f"EAD rate cold storage arm: {summary['ead_rate_cold_storage']:.1%}. "
         f"Absolute risk reduction: {summary['ead_rate_cold_storage'] - summary['ead_rate_nmp']:.1%}."),
        ("discard_rate", f"Organ discard rate NMP: {summary['discard_rate_nmp']:.1%}. "
         f"Discard rate cold storage: {summary['discard_rate_cold_storage']:.1%}."),
    ]

    for param_type, content in nmp_params:
        docs.append(Document(
            page_content=content,
            metadata={
                "source_doi": vittal["doi"],
                "trial_name": "VITTAL",
                "parameter_type": param_type,
            },
        ))

    # --- PILOT trial ---
    pilot_path = Path("data/public/transplant/nmp_pilot_criteria.json")
    pilot = json.loads(pilot_path.read_text())

    # Trial overview
    docs.append(Document(
        page_content=(
            f"PILOT study (Mergental et al. Nat Med 2020, n={pilot['n']}). "
            f"NMP viability assessment enabled transplantation of "
            f"{pilot['outcomes']['grafts_transplanted']} declined livers with "
            f"{pilot['outcomes']['one_year_graft_survival']:.0%} 1-year survival. "
            f"EAD rate: {pilot['outcomes']['ead_rate']:.1%}."
        ),
        metadata={
            "source_doi": pilot["doi"],
            "trial_name": "PILOT",
            "parameter_type": "trial_overview",
        },
    ))

    # Mandatory viability criteria
    for criterion in pilot["viability_criteria"]["mandatory"]:
        readable = criterion.replace("_", " ").replace("lt", "<").replace("gt", ">")
        docs.append(Document(
            page_content=(
                f"PILOT mandatory viability criterion: {readable}. "
                f"All mandatory criteria must be met for transplantation."
            ),
            metadata={
                "source_doi": pilot["doi"],
                "trial_name": "PILOT",
                "parameter_type": "mandatory_criterion",
            },
        ))

    # Supporting viability criteria
    for criterion in pilot["viability_criteria"]["supporting"]:
        readable = criterion.replace("_", " ").replace("lt", "<").replace("gt", ">")
        docs.append(Document(
            page_content=(
                f"PILOT supporting viability criterion: {readable}. "
                f"At least 2 of 3 supporting criteria required."
            ),
            metadata={
                "source_doi": pilot["doi"],
                "trial_name": "PILOT",
                "parameter_type": "supporting_criterion",
            },
        ))

    # Decision rule
    docs.append(Document(
        page_content=(
            f"PILOT viability decision: {pilot['viability_criteria']['decision']}. "
            f"Organ is viable if ALL mandatory criteria met PLUS at least 2 "
            f"of 3 supporting criteria."
        ),
        metadata={
            "source_doi": pilot["doi"],
            "trial_name": "PILOT",
            "parameter_type": "decision_rule",
        },
    ))

    # Create collection
    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name="transplant_intelligence",
        persist_directory=str(CHROMA_DIR),
    )

    print(f"transplant_intelligence: {len(docs)} documents embedded")
    return len(docs)


def embed_calibration_benchmarks():
    """Embed literature benchmarks into calibration_benchmarks collection."""
    benchmarks_path = Path("data/public/biofab/literature_benchmarks.json")
    data = json.loads(benchmarks_path.read_text())

    docs = []

    # GelMA viability benchmarks
    for entry in data.get("gelma_viability_benchmarks", []):
        viab_key = "viability_day3_mean" if "viability_day3_mean" in entry else "viability_day7_mean"
        sd_key = viab_key.replace("mean", "sd")
        day = "day 3" if "day3" in viab_key else "day 7"

        docs.append(Document(
            page_content=(
                f"{entry['material']} at {entry['stiffness_kpa']} kPa with "
                f"{entry['cell_type']} cells: {day} viability "
                f"{entry[viab_key]}% (SD {entry[sd_key]}%)."
            ),
            metadata={
                "source_doi": entry["source_doi"],
                "material": entry["material"],
                "cell_type": entry["cell_type"],
                "category": "gelma_viability",
                "stiffness_kpa": str(entry["stiffness_kpa"]),
            },
        ))

    # OoC TEER benchmarks
    for entry in data.get("ooc_teer_benchmarks", []):
        docs.append(Document(
            page_content=(
                f"{entry['model']} organ-on-chip with {entry['cell_type']} cells: "
                f"TEER {entry['teer_ohm_cm2_mean']} ohm*cm2 (SD {entry['teer_ohm_cm2_sd']}). "
                f"Flow rate {entry['flow_rate_ulmin']} uL/min, "
                f"shear {entry['shear_dyncm2']} dyn/cm2."
            ),
            metadata={
                "source_doi": entry["source_doi"],
                "material": entry.get("model", ""),
                "cell_type": entry["cell_type"],
                "category": "ooc_teer",
            },
        ))

    # Spheroid benchmarks
    for entry in data.get("spheroid_benchmarks", []):
        cell_types_str = ", ".join(entry["cell_types"])
        docs.append(Document(
            page_content=(
                f"{entry['model']} spheroid ({cell_types_str}) via {entry['method']}: "
                f"diameter at day 7 = {entry['diameter_day7_um_mean']} um "
                f"(SD {entry['diameter_day7_um_sd']}). "
                f"Initial density: {entry['initial_density']} cells."
            ),
            metadata={
                "source_doi": entry["source_doi"],
                "material": entry.get("method", ""),
                "cell_type": cell_types_str,
                "category": "spheroid",
            },
        ))

    # Bioprinting benchmarks
    for entry in data.get("bioprinting_benchmarks", []):
        docs.append(Document(
            page_content=(
                f"{entry['material']} {entry['method']} bioprinting: "
                f"nozzle {entry['nozzle_mm']} mm, speed {entry['speed_mms']} mm/s, "
                f"print fidelity score {entry['print_fidelity_score']}."
            ),
            metadata={
                "source_doi": entry["source_doi"],
                "material": entry["material"],
                "cell_type": "",
                "category": "bioprinting",
            },
        ))

    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name="calibration_benchmarks",
        persist_directory=str(CHROMA_DIR),
    )

    print(f"calibration_benchmarks: {len(docs)} documents embedded")
    return len(docs)


if __name__ == "__main__":
    print("Embedding public data into ChromaDB...")
    n_transplant = embed_transplant_intelligence()
    n_benchmarks = embed_calibration_benchmarks()

    # Verify
    import chromadb
    client = chromadb.PersistentClient(str(CHROMA_DIR))
    print("\n--- Collections ---")
    for col in client.list_collections():
        print(f"  {col.name}: {col.count()} documents")
    print(f"\nTotal new documents: {n_transplant + n_benchmarks}")
