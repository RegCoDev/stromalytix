"""
scripts/embed_public_data.py

Embeds public dataset summaries into ChromaDB collections:
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
    n_benchmarks = embed_calibration_benchmarks()

    import chromadb
    client = chromadb.PersistentClient(str(CHROMA_DIR))
    print("\n--- Collections ---")
    for col in client.list_collections():
        print(f"  {col.name}: {col.count()} documents")
    print(f"\nTotal new documents: {n_benchmarks}")
