#!/usr/bin/env python3
"""Initial ingestion of all existing Stromalytix data into the Knowledge Vault."""

import json
import sys
import time
from pathlib import Path

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent))

from db import init_db
from embedder import Embedder
from ingest import ingest_papers, ingest_parameters, ingest_benchmarks

ABSTRACTS_DIR = Path("/opt/stromalytix/data/raw_abstracts")
PARAMS_DIR = Path("/opt/stromalytix/data/parameters")
BENCHMARKS_FILE = Path("/opt/stromalytix/data/public/biofab/literature_benchmarks.json")
DB_PATH = Path(__file__).parent / "vault.db"


def main():
    print("=" * 60)
    print("Stromalytix Knowledge Vault — Initial Ingestion")
    print("=" * 60)

    # Init
    conn = init_db(str(DB_PATH))
    embedder = Embedder()

    # Pre-warm embedder
    print("\nLoading embedding model...")
    t0 = time.time()
    embedder.embed_text("warmup")
    print(f"  Model loaded in {time.time()-t0:.1f}s")

    # 1. Ingest abstracts
    print("\n--- Ingesting Abstracts ---")
    total_stats = {"ingested": 0, "skipped_duplicate": 0, "chunks_created": 0}
    for json_file in sorted(ABSTRACTS_DIR.glob("*.json")):
        cluster_name = json_file.stem
        print(f"\n  Cluster: {cluster_name}")
        with open(json_file) as f:
            records = json.load(f)
        print(f"  Records: {len(records)}")
        t0 = time.time()
        stats = ingest_papers(conn, embedder, records, cluster_name)
        elapsed = time.time() - t0
        print(f"  Ingested: {stats['ingested']}, Skipped: {stats['skipped_duplicate']}, Chunks: {stats['chunks_created']}")
        if stats["errors"]:
            print(f"  Errors: {len(stats['errors'])}")
            for err in stats["errors"][:5]:
                print(f"    - {err}")
        print(f"  Time: {elapsed:.1f}s")
        for k in total_stats:
            total_stats[k] += stats[k]

    print(f"\n  TOTAL: {total_stats}")

    # 2. Ingest parameters
    print("\n--- Ingesting Parameters ---")
    total_params = 0
    for json_file in sorted(PARAMS_DIR.glob("*.json")):
        table_name = json_file.stem
        print(f"  Table: {table_name}")
        with open(json_file) as f:
            entries = json.load(f)
        count = ingest_parameters(conn, table_name, entries)
        print(f"  Loaded: {count} entries")
        total_params += count
    print(f"  TOTAL parameters: {total_params}")

    # 3. Ingest benchmarks
    print("\n--- Ingesting Benchmarks ---")
    if BENCHMARKS_FILE.exists():
        with open(BENCHMARKS_FILE) as f:
            benchmarks = json.load(f)
        count = ingest_benchmarks(conn, benchmarks)
        print(f"  Loaded: {count} benchmarks")
    else:
        print("  Benchmarks file not found, skipping")

    # Summary
    print("\n" + "=" * 60)
    print("INGESTION COMPLETE")
    print("=" * 60)
    paper_count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    param_count = conn.execute("SELECT COUNT(*) FROM parameters").fetchone()[0]
    bench_count = conn.execute("SELECT COUNT(*) FROM benchmarks").fetchone()[0]
    db_size = DB_PATH.stat().st_size / (1024 * 1024)
    print(f"  Papers:     {paper_count}")
    print(f"  Chunks:     {chunk_count}")
    print(f"  Parameters: {param_count}")
    print(f"  Benchmarks: {bench_count}")
    print(f"  DB size:    {db_size:.1f} MB")

    conn.close()


if __name__ == "__main__":
    main()
