"""
Knowledge Vault — Ingestion pipeline.

Loads papers (with entity extraction and chunking), parameter library entries,
and literature benchmarks into the SQLite vault.
"""

import json
import re
import struct
import sqlite3
from pathlib import Path
from typing import Optional

from chunker import chunk_abstract

ENTITY_DICT_PATH = Path(__file__).parent / "entity_dict.json"
_entity_dict_cache: Optional[dict] = None


def _load_entity_dict() -> dict:
    """Load and cache the entity dictionary."""
    global _entity_dict_cache
    if _entity_dict_cache is None:
        with open(ENTITY_DICT_PATH) as f:
            _entity_dict_cache = json.load(f)
        # Pre-compile biofab patterns
        _entity_dict_cache["_biofab_compiled"] = [
            re.compile(pat, re.IGNORECASE)
            for pat in _entity_dict_cache["biofab_patterns"]
        ]
    return _entity_dict_cache


def extract_entities(text: str, entity_dict: dict) -> dict:
    """Extract materials, cell_types, biofab_method, tissue_type from text.

    Returns: {
        "materials": [...],
        "cell_types": [...],
        "biofab_method": str | None,
        "tissue_type": str | None,
    }
    """
    text_lower = text.lower()

    # Materials: case-insensitive substring match, store canonical form
    materials = []
    for mat in entity_dict["materials"]:
        if mat.lower() in text_lower:
            materials.append(mat)

    # Cell types: case-insensitive substring match, store canonical form
    cell_types = []
    for ct in entity_dict["cell_types"]:
        if ct.lower() in text_lower:
            cell_types.append(ct)

    # Biofab method: first regex match
    biofab_method = None
    for pattern in entity_dict.get("_biofab_compiled", []):
        m = pattern.search(text)
        if m:
            biofab_method = m.group(0).lower()
            break

    # Tissue type: first substring match
    tissue_type = None
    for tt in entity_dict["tissue_types"]:
        if tt.lower() in text_lower:
            tissue_type = tt
            break

    return {
        "materials": materials,
        "cell_types": cell_types,
        "biofab_method": biofab_method,
        "tissue_type": tissue_type,
    }


def _float_list_to_blob(floats: list[float]) -> bytes:
    """Pack a list of floats into a bytes blob (float32)."""
    return struct.pack(f'{len(floats)}f', *floats)


def ingest_papers(conn: sqlite3.Connection, embedder, records: list[dict],
                  cluster_name: str) -> dict:
    """Ingest a batch of paper records into the vault.

    Args:
        conn: SQLite connection
        embedder: Embedder instance with embed_batch()
        records: list of dicts with keys: pmid, title, abstract, year, authors
        cluster_name: name of the PubMed search cluster

    Returns: {"ingested": int, "skipped_duplicate": int, "chunks_created": int, "errors": list}
    """
    entity_dict = _load_entity_dict()

    stats = {"ingested": 0, "skipped_duplicate": 0, "chunks_created": 0, "errors": []}

    # First pass: separate new records from duplicates, collect chunks for embedding
    new_records = []  # (record, entities, chunks)
    all_chunk_texts = []  # flat list of texts for batch embedding
    chunk_index_map = []  # (record_idx_in_new_records, chunk_idx_in_record_chunks)

    for record in records:
        pmid = str(record.get("pmid", "")).strip()
        if not pmid:
            stats["errors"].append("Record missing pmid, skipped")
            continue

        try:
            # Check for existing paper
            existing = conn.execute(
                "SELECT id, clusters FROM papers WHERE pmid = ?", (pmid,)
            ).fetchone()

            if existing:
                # Append cluster name to clusters array (dedup)
                clusters = json.loads(existing["clusters"])
                if cluster_name not in clusters:
                    clusters.append(cluster_name)
                    conn.execute(
                        "UPDATE papers SET clusters = ? WHERE id = ?",
                        (json.dumps(clusters), existing["id"])
                    )
                stats["skipped_duplicate"] += 1
                continue

            # Extract entities from title + abstract
            title = record.get("title", "")
            abstract = record.get("abstract", "")
            combined_text = f"{title} {abstract}"
            entities = extract_entities(combined_text, entity_dict)

            # Chunk the abstract
            chunks = chunk_abstract(abstract)
            if not chunks:
                # Even if abstract is too short, still insert the paper with a title chunk
                chunks = [{
                    "section": "full",
                    "text": title,
                    "token_count": len(title.split()),
                }]

            rec_idx = len(new_records)
            new_records.append((record, entities, chunks))

            for chunk_idx, chunk in enumerate(chunks):
                all_chunk_texts.append(chunk["text"])
                chunk_index_map.append((rec_idx, chunk_idx))

        except Exception as e:
            stats["errors"].append(f"PMID {pmid}: {e}")

    # Batch embed all chunk texts
    if all_chunk_texts:
        try:
            all_embeddings = embedder.embed_batch(all_chunk_texts)
        except Exception as e:
            stats["errors"].append(f"Batch embedding failed: {e}")
            return stats
    else:
        all_embeddings = []

    # Build a mapping from (rec_idx, chunk_idx) -> embedding
    embedding_lookup = {}
    for i, (rec_idx, chunk_idx) in enumerate(chunk_index_map):
        embedding_lookup[(rec_idx, chunk_idx)] = all_embeddings[i]

    # Second pass: insert papers and chunks with embeddings
    for rec_idx, (record, entities, chunks) in enumerate(new_records):
        pmid = str(record["pmid"]).strip()
        try:
            authors = record.get("authors", [])
            if isinstance(authors, str):
                authors = [authors]

            cursor = conn.execute(
                """INSERT INTO papers
                   (pmid, doi, title, year, journal, authors, clusters,
                    biofab_method, tissue_type, materials, cell_types, full_abstract)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pmid,
                    record.get("doi"),
                    record.get("title", ""),
                    record.get("year"),
                    record.get("journal"),
                    json.dumps(authors),
                    json.dumps([cluster_name]),
                    entities["biofab_method"],
                    entities["tissue_type"],
                    json.dumps(entities["materials"]),
                    json.dumps(entities["cell_types"]),
                    record.get("abstract", ""),
                )
            )
            paper_id = cursor.lastrowid

            # Insert chunks
            for chunk_idx, chunk in enumerate(chunks):
                embedding = embedding_lookup.get((rec_idx, chunk_idx))
                if embedding is None:
                    continue

                embedding_blob = _float_list_to_blob(embedding)

                cursor = conn.execute(
                    """INSERT INTO chunks (paper_id, section, text, embedding, token_count)
                       VALUES (?, ?, ?, ?, ?)""",
                    (paper_id, chunk["section"], chunk["text"],
                     embedding_blob, chunk["token_count"])
                )
                chunk_id = cursor.lastrowid

                # Insert into VSS index using JSON array format
                conn.execute(
                    "INSERT INTO chunks_vss(rowid, embedding) VALUES (?, ?)",
                    (chunk_id, json.dumps(embedding))
                )

                stats["chunks_created"] += 1

            stats["ingested"] += 1

        except Exception as e:
            stats["errors"].append(f"PMID {pmid}: insert failed: {e}")

    conn.commit()
    return stats


def ingest_parameters(conn: sqlite3.Connection, table_name: str,
                      entries: list[dict]) -> int:
    """Load parameter library entries into the parameters table.

    Core fields: id, parameter, value, unit, material, cell_type,
                 conditions, confidence, doi, pmid, notes
    Extra fields (varies by table): stored as JSON in 'extra' column.

    Returns number of entries loaded.
    """
    CORE_FIELDS = {
        'id', 'parameter', 'value', 'unit', 'material', 'cell_type',
        'conditions', 'confidence', 'doi', 'pmid', 'notes'
    }

    count = 0
    for entry in entries:
        try:
            # Separate core fields from extra fields
            extra = {k: v for k, v in entry.items() if k not in CORE_FIELDS}

            # Coerce value to float if possible
            raw_value = entry.get("value")
            value = None
            if raw_value is not None:
                try:
                    value = float(raw_value)
                except (ValueError, TypeError):
                    # Store non-numeric values in extra
                    extra["value_raw"] = raw_value

            conn.execute(
                """INSERT OR REPLACE INTO parameters
                   (id, table_name, parameter, value, unit, material, cell_type,
                    conditions, confidence, doi, pmid, notes, source, extra)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'curated', ?)""",
                (
                    entry.get("id", f"{table_name}_{count}"),
                    table_name,
                    entry.get("parameter", ""),
                    value,
                    entry.get("unit"),
                    entry.get("material"),
                    entry.get("cell_type"),
                    entry.get("conditions"),
                    entry.get("confidence"),
                    entry.get("doi"),
                    entry.get("pmid"),
                    entry.get("notes"),
                    json.dumps(extra) if extra else "{}",
                )
            )
            count += 1

        except Exception as e:
            print(f"  WARNING: parameter entry {entry.get('id', '?')}: {e}")

    conn.commit()
    return count


def ingest_benchmarks(conn: sqlite3.Connection, data: dict) -> int:
    """Load literature benchmarks into benchmarks table.

    data is the full JSON from literature_benchmarks.json.
    Structure: {"source": "...", "gelma_viability_benchmarks": [...], ...}
    Each entry becomes a row with category, material, cell_type extracted,
    data=json.dumps(entry).
    """
    count = 0
    for key, value in data.items():
        # Skip non-list entries (e.g., "source" string)
        if not isinstance(value, list):
            continue

        # Derive category name: strip "_benchmarks" suffix if present
        category = key.replace("_benchmarks", "")

        for entry in value:
            try:
                material = entry.get("material")
                # cell_type can be a string or list
                cell_type_raw = entry.get("cell_type") or entry.get("cell_types")
                if isinstance(cell_type_raw, list):
                    cell_type = ", ".join(cell_type_raw)
                else:
                    cell_type = cell_type_raw

                source_doi = entry.get("source_doi")

                conn.execute(
                    """INSERT INTO benchmarks (category, material, cell_type, data, source_doi)
                       VALUES (?, ?, ?, ?, ?)""",
                    (category, material, cell_type, json.dumps(entry), source_doi)
                )
                count += 1

            except Exception as e:
                print(f"  WARNING: benchmark in {key}: {e}")

    conn.commit()
    return count
