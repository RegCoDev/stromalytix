"""
Scrape PubMed for CompuCell3D / Cellular Potts Model parameter abstracts.

Creates data/raw_abstracts/cc3d_parameters.json with 50+ records.
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List

from Bio import Entrez
from dotenv import load_dotenv

load_dotenv()

Entrez.email = os.getenv("NCBI_EMAIL")
if not Entrez.email:
    raise ValueError("NCBI_EMAIL not found in .env file")

OUTPUT_DIR = Path("data/raw_abstracts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "cc3d_parameters.json"

SLEEP_INTERVAL = 0.4

# Multiple search queries to maximize coverage
SEARCH_QUERIES = [
    '("CompuCell3D" OR "CC3D") AND (simulation OR model)',
    '("Cellular Potts Model" OR "Cellular Potts") AND (parameters OR adhesion OR energy)',
    '("Glazier Graner Hogeweg" OR "GGH model") AND (cell OR tissue)',
    '("agent based model" OR "agent-based model") AND ("tissue engineering" OR "cell culture") AND (parameters OR simulation)',
    '("cell adhesion energy" OR "contact energy") AND ("computational model" OR simulation) AND (tissue OR cell)',
    '("volume constraint" OR "lambda volume") AND (cell simulation OR computational)',
    '("Potts model" OR "lattice model") AND (morphogenesis OR cell sorting OR tissue)',
]


def search_pubmed(query: str, retmax: int = 100) -> List[str]:
    """Search PubMed and return PMIDs."""
    print(f"  Query: {query[:80]}...")
    handle = Entrez.esearch(db="pubmed", term=query, retmax=retmax, sort="relevance")
    results = Entrez.read(handle)
    handle.close()
    pmids = results["IdList"]
    print(f"  Found {len(pmids)} PMIDs")
    return pmids


def fetch_abstracts(pmids: List[str]) -> List[Dict]:
    """Fetch abstract records for given PMIDs."""
    if not pmids:
        return []

    handle = Entrez.efetch(db="pubmed", id=",".join(pmids), rettype="medline", retmode="xml")
    records = Entrez.read(handle)
    handle.close()

    parsed = []
    for record in records["PubmedArticle"]:
        try:
            medline = record["MedlineCitation"]
            article = medline["Article"]

            abstract_text = ""
            if "Abstract" in article and "AbstractText" in article["Abstract"]:
                parts = article["Abstract"]["AbstractText"]
                abstract_text = " ".join(str(p) for p in parts) if isinstance(parts, list) else str(parts)

            if not abstract_text.strip():
                continue

            year = ""
            if "DateCompleted" in medline:
                year = str(medline["DateCompleted"].get("Year", ""))
            elif "PubDate" in article["Journal"]["JournalIssue"]:
                year = str(article["Journal"]["JournalIssue"]["PubDate"].get("Year", ""))

            authors = []
            if "AuthorList" in article:
                for author in article["AuthorList"]:
                    if "LastName" in author and "Initials" in author:
                        authors.append(f"{author['LastName']} {author['Initials']}")

            parsed.append({
                "pmid": str(medline["PMID"]),
                "title": str(article.get("ArticleTitle", "")),
                "abstract": abstract_text,
                "year": year,
                "authors": authors,
            })
        except Exception as e:
            print(f"  Warning: {e}")
            continue

    return parsed


def main():
    print("=" * 60)
    print("CC3D Parameters PubMed Scraper")
    print("=" * 60)

    seen_pmids = set()
    all_records = []

    for query in SEARCH_QUERIES:
        pmids = search_pubmed(query)
        time.sleep(SLEEP_INTERVAL)

        # Deduplicate
        new_pmids = [p for p in pmids if p not in seen_pmids]
        seen_pmids.update(new_pmids)

        if new_pmids:
            records = fetch_abstracts(new_pmids)
            all_records.extend(records)
            print(f"  Added {len(records)} new records (total: {len(all_records)})")
            time.sleep(SLEEP_INTERVAL)

    # Save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(all_records)} records to {OUTPUT_FILE}")
    print(f"Target: >= 50 records. {'PASS' if len(all_records) >= 50 else 'NEED MORE'}")


if __name__ == "__main__":
    main()
