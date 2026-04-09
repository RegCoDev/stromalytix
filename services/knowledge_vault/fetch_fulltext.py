#!/usr/bin/env python3
"""Fetch PMC Open Access full-text XML and ingest into the Knowledge Vault.

Reads the PMID->PMCID mapping, fetches JATS XML from PMC via E-utilities,
parses sections (intro, methods, results, discussion), and creates new
chunks alongside the existing abstract chunks.
"""

import json
import os
import re
import sqlite3
import struct
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from db import init_db
from embedder import Embedder
from ingest import extract_entities, _load_entity_dict, _float_list_to_blob

PMID_PMC_MAP = "/tmp/pmid_to_pmc.json"
DB_PATH = str(Path(__file__).parent / "vault.db")
BATCH_SIZE = 5  # PMC IDs per efetch call (keep small to avoid timeouts)
SLEEP_INTERVAL = 0.5  # NCBI rate limit
NCBI_EMAIL = os.environ.get("NCBI_EMAIL", "reg@kdense.com")
NCBI_TOOL = "stromalytix"

# Section type mapping (JATS sec-type attribute -> normalized name)
SEC_TYPE_MAP = {
    "intro": "background",
    "introduction": "background",
    "background": "background",
    "methods": "methods",
    "materials": "methods",
    "materials|methods": "methods",
    "results": "results",
    "findings": "results",
    "discussion": "conclusions",
    "conclusions": "conclusions",
    "conclusion": "conclusions",
    "supplementary-material": "supplementary",
}


def _sec_type_from_title(title: str) -> str:
    """Infer section type from title text when sec-type attribute is missing."""
    t = title.lower().strip().rstrip(".:0123456789 ")
    if any(k in t for k in ("introduction", "background", "overview")):
        return "background"
    if any(k in t for k in ("method", "material", "experimental", "procedure")):
        return "methods"
    if any(k in t for k in ("result", "finding", "observation")):
        return "results"
    if any(k in t for k in ("discussion", "conclusion", "summary", "limitation")):
        return "conclusions"
    return "other"


def parse_jats_xml(xml_text: str) -> dict:
    """Parse JATS XML into structured sections.

    Returns: {
        "sections": [{"type": str, "title": str, "text": str, "word_count": int}, ...],
        "tables": [{"caption": str, "content": str}, ...],
        "has_body": bool,
    }
    """
    root = ET.fromstring(xml_text)
    body = root.find(".//body")

    result = {"sections": [], "tables": [], "has_body": body is not None}

    if body is None:
        return result

    # Extract top-level sections (try both ./sec and .//sec for nested)
    top_secs = body.findall("./sec")
    if not top_secs:
        # Some articles have sections nested differently
        top_secs = body.findall(".//sec")
    # If still no sections, treat entire body as one chunk
    if not top_secs:
        body_text = ET.tostring(body, method="text", encoding="unicode").strip()
        body_text = re.sub(r"\s+", " ", body_text).strip()
        if len(body_text) > 100:
            result["sections"].append({
                "type": "methods",  # Best guess for unsectioned full text
                "title": "Full Text",
                "text": body_text,
                "word_count": len(body_text.split()),
            })
        return result

    for sec in top_secs:
        sec_type = sec.get("sec-type", "")
        title_el = sec.find("title")
        title = title_el.text.strip() if title_el is not None and title_el.text else ""

        # Normalize section type
        if sec_type:
            normalized = SEC_TYPE_MAP.get(sec_type.lower(), "other")
        elif title:
            normalized = _sec_type_from_title(title)
        else:
            normalized = "other"

        # Extract all text from section (including subsections)
        text = ET.tostring(sec, method="text", encoding="unicode").strip()
        # Clean up whitespace
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) > 50:  # Skip tiny sections
            result["sections"].append({
                "type": normalized,
                "title": title,
                "text": text,
                "word_count": len(text.split()),
            })

    # Extract tables
    for table_wrap in root.findall(".//table-wrap"):
        caption_el = table_wrap.find(".//caption")
        caption = ""
        if caption_el is not None:
            caption = ET.tostring(caption_el, method="text", encoding="unicode").strip()

        table_text = ET.tostring(table_wrap, method="text", encoding="unicode").strip()
        table_text = re.sub(r"\s+", " ", table_text).strip()

        if len(table_text) > 30:
            result["tables"].append({
                "caption": caption,
                "content": table_text[:2000],  # Cap table text
            })

    return result


def chunk_fulltext(parsed: dict, max_chunk_words: int = 400) -> list[dict]:
    """Convert parsed full-text into chunks suitable for embedding.

    Splits long sections into ~400 word chunks at sentence boundaries.
    Returns list of {"section": str, "text": str, "token_count": int}
    """
    chunks = []

    for sec in parsed["sections"]:
        if sec["type"] == "other":
            continue  # Skip acknowledgments, author contributions, etc.

        text = sec["text"]
        words = text.split()

        if len(words) <= max_chunk_words:
            chunks.append({
                "section": sec["type"],
                "text": text,
                "token_count": len(words),
            })
        else:
            # Split at sentence boundaries
            sentences = re.split(r"(?<=[.!?])\s+", text)
            current_chunk = []
            current_words = 0

            for sentence in sentences:
                s_words = len(sentence.split())
                if current_words + s_words > max_chunk_words and current_chunk:
                    chunk_text = " ".join(current_chunk)
                    chunks.append({
                        "section": sec["type"],
                        "text": chunk_text,
                        "token_count": len(chunk_text.split()),
                    })
                    current_chunk = [sentence]
                    current_words = s_words
                else:
                    current_chunk.append(sentence)
                    current_words += s_words

            if current_chunk:
                chunk_text = " ".join(current_chunk)
                chunks.append({
                    "section": sec["type"],
                    "text": chunk_text,
                    "token_count": len(chunk_text.split()),
                })

    # Add table chunks
    for table in parsed["tables"]:
        text = f"Table: {table['caption']} {table['content']}"
        chunks.append({
            "section": "results",  # Tables are usually results
            "text": text[:1500],
            "token_count": len(text.split()),
        })

    return chunks


def fetch_pmc_xml(pmc_ids: list[str]) -> dict[str, str]:
    """Fetch JATS XML for a batch of PMC IDs from E-utilities.

    Returns: {pmcid: xml_string, ...}
    """
    numeric_ids = [p.replace("PMC", "") for p in pmc_ids]
    ids_param = ",".join(numeric_ids)
    url = (
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        f"?db=pmc&id={ids_param}&rettype=xml"
        f"&tool={NCBI_TOOL}&email={NCBI_EMAIL}"
    )

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=60) as resp:
        content = resp.read().decode("utf-8", errors="replace")

    # Parse the response - it contains multiple articles in <pmc-articleset>
    results = {}
    try:
        root = ET.fromstring(content)
        for article in root.findall(".//article"):
            # Find PMCID in article-id elements
            pmcid = None
            for aid in article.findall(".//article-id"):
                id_type = aid.get("pub-id-type", "")
                if id_type in ("pmcid", "pmc"):
                    text = aid.text or ""
                    pmcid = text if text.startswith("PMC") else f"PMC{text}"
                    break

            if pmcid:
                results[pmcid] = ET.tostring(article, encoding="unicode")
    except ET.ParseError:
        # Try individual parsing if batch fails
        pass

    return results


def main():
    print("=" * 60)
    print("Knowledge Vault — PMC Full-Text Ingestion")
    print("=" * 60)

    # Load mapping
    with open(PMID_PMC_MAP) as f:
        pmid_to_pmc = json.load(f)

    pmc_to_pmid = {v: k for k, v in pmid_to_pmc.items()}
    pmcids = list(pmid_to_pmc.values())
    print(f"PMC articles to fetch: {len(pmcids)}")

    # Init
    conn = init_db(DB_PATH)
    embedder = Embedder()
    print("Loading embedding model...")
    embedder.embed_text("warmup")
    print("Ready.\n")

    # Check which papers already have fulltext chunks
    already_done = set()
    for row in conn.execute(
        "SELECT DISTINCT p.pmid FROM papers p "
        "JOIN chunks c ON c.paper_id = p.id "
        "WHERE c.section != 'full'"
    ).fetchall():
        already_done.add(row[0])
    print(f"Already have fulltext chunks for {len(already_done)} papers, skipping those.\n")

    # Filter out already-done
    todo_pmcids = [p for p in pmcids if pmc_to_pmid.get(p) not in already_done]
    print(f"Fetching {len(todo_pmcids)} new articles...\n")

    stats = {
        "fetched": 0,
        "parsed": 0,
        "no_body": 0,
        "chunks_created": 0,
        "errors": 0,
    }

    for i in range(0, len(todo_pmcids), BATCH_SIZE):
        batch = todo_pmcids[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(todo_pmcids) - 1) // BATCH_SIZE + 1

        try:
            xml_map = fetch_pmc_xml(batch)
            stats["fetched"] += len(xml_map)

            # Process each article
            all_chunk_texts = []
            chunk_meta = []  # (pmid, chunk_dict)

            for pmcid, xml_text in xml_map.items():
                pmid = pmc_to_pmid.get(pmcid)
                if not pmid:
                    continue

                parsed = parse_jats_xml(xml_text)
                if not parsed["has_body"]:
                    stats["no_body"] += 1
                    continue

                chunks = chunk_fulltext(parsed)
                if not chunks:
                    continue

                stats["parsed"] += 1

                for chunk in chunks:
                    all_chunk_texts.append(chunk["text"])
                    chunk_meta.append((pmid, chunk))

            # Batch embed
            if all_chunk_texts:
                embeddings = embedder.embed_batch(all_chunk_texts)

                # Insert chunks
                for idx, (pmid, chunk) in enumerate(chunk_meta):
                    paper_row = conn.execute(
                        "SELECT id FROM papers WHERE pmid = ?", (pmid,)
                    ).fetchone()
                    if paper_row is None:
                        continue

                    paper_id = paper_row[0]
                    embedding = embeddings[idx]
                    embedding_blob = _float_list_to_blob(embedding)

                    cursor = conn.execute(
                        "INSERT INTO chunks (paper_id, section, text, embedding, token_count) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (paper_id, chunk["section"], chunk["text"],
                         embedding_blob, chunk["token_count"])
                    )
                    chunk_id = cursor.lastrowid

                    # Insert into VSS
                    conn.execute(
                        "INSERT INTO chunks_vss(rowid, embedding) VALUES (?, ?)",
                        (chunk_id, json.dumps(embedding))
                    )

                    stats["chunks_created"] += 1

                conn.commit()

        except Exception as e:
            stats["errors"] += 1
            print(f"  Batch {batch_num} error: {e}")

        if batch_num % 10 == 0 or batch_num == total_batches:
            print(f"  Batch {batch_num}/{total_batches}: "
                  f"fetched={stats['fetched']}, parsed={stats['parsed']}, "
                  f"chunks={stats['chunks_created']}, no_body={stats['no_body']}")

        time.sleep(SLEEP_INTERVAL)

    # Final summary
    print("\n" + "=" * 60)
    print("INGESTION COMPLETE")
    print("=" * 60)
    total_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    fulltext_chunks = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE section != 'full'"
    ).fetchone()[0]
    db_size = os.path.getsize(DB_PATH) / (1024 * 1024)

    print(f"  Articles fetched:     {stats['fetched']}")
    print(f"  Articles with body:   {stats['parsed']}")
    print(f"  Articles no body:     {stats['no_body']}")
    print(f"  New fulltext chunks:  {stats['chunks_created']}")
    print(f"  Errors:               {stats['errors']}")
    print(f"  Total chunks in DB:   {total_chunks} (abstract: {total_chunks - fulltext_chunks}, fulltext: {fulltext_chunks})")
    print(f"  DB size:              {db_size:.1f} MB")

    conn.close()


if __name__ == "__main__":
    main()
