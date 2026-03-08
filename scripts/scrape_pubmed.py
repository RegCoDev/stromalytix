"""
PubMed Abstract Scraper for Stromalytix Knowledge Base

Scrapes PubMed abstracts across 4 clusters related to tissue engineering.
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List

from Bio import Entrez
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Entrez
Entrez.email = os.getenv("NCBI_EMAIL")
if not Entrez.email:
    raise ValueError("NCBI_EMAIL not found in .env file")

# Search clusters - 200 abstracts each
SEARCH_CLUSTERS = {
    "physiological_relevance": "(3D cell culture) AND (physiological relevance OR organotypic OR tissue function OR in vivo correlation)",
    "disease_phenotype": "(disease model OR 3D scaffold) AND (fibrosis OR tumor microenvironment OR iPSC OR cardiac disease phenotype)",
    "druggability": "(drug response OR 3D model) AND (IC50 OR ECM stiffness OR drug resistance OR bioink OR screening)",
    "process_parameters": "(GelMA OR stiffness OR bioink) AND (cell viability OR rheology OR scaffold porosity OR oxygen diffusion OR 3D bioprinting)"
}

# Output directory
OUTPUT_DIR = Path("data/raw_abstracts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# NCBI rate limit compliance
SLEEP_INTERVAL = 0.4


def search_pubmed(query: str, retmax: int = 200) -> List[str]:
    """Search PubMed and return list of PMIDs."""
    print(f"  Searching PubMed...")
    handle = Entrez.esearch(
        db="pubmed",
        term=query,
        retmax=retmax,
        sort="relevance"
    )
    results = Entrez.read(handle)
    handle.close()
    pmids = results["IdList"]
    print(f"  Found {len(pmids)} PMIDs")
    return pmids


def fetch_abstracts(pmids: List[str]) -> List[Dict]:
    """Fetch full abstract records for given PMIDs."""
    if not pmids:
        return []

    print(f"  Fetching {len(pmids)} abstracts...")
    handle = Entrez.efetch(
        db="pubmed",
        id=",".join(pmids),
        rettype="medline",
        retmode="xml"
    )
    records = Entrez.read(handle)
    handle.close()

    parsed_records = []
    skipped = 0

    for record in records["PubmedArticle"]:
        try:
            medline = record["MedlineCitation"]
            article = medline["Article"]

            # Extract abstract text
            abstract_text = ""
            if "Abstract" in article and "AbstractText" in article["Abstract"]:
                abstract_parts = article["Abstract"]["AbstractText"]
                if isinstance(abstract_parts, list):
                    abstract_text = " ".join(str(part) for part in abstract_parts)
                else:
                    abstract_text = str(abstract_parts)

            # Skip if no abstract
            if not abstract_text.strip():
                skipped += 1
                continue

            # Extract year
            year = ""
            if "DateCompleted" in medline:
                year = str(medline["DateCompleted"].get("Year", ""))
            elif "PubDate" in article["Journal"]["JournalIssue"]:
                pub_date = article["Journal"]["JournalIssue"]["PubDate"]
                year = str(pub_date.get("Year", ""))

            # Extract authors
            authors = []
            if "AuthorList" in article:
                for author in article["AuthorList"]:
                    if "LastName" in author and "Initials" in author:
                        authors.append(f"{author['LastName']} {author['Initials']}")

            parsed_records.append({
                "pmid": str(medline["PMID"]),
                "title": str(article.get("ArticleTitle", "")),
                "abstract": abstract_text,
                "year": year,
                "authors": authors
            })

        except Exception as e:
            print(f"  Warning: Error parsing record - {e}")
            skipped += 1
            continue

    print(f"  Parsed {len(parsed_records)} abstracts ({skipped} skipped - no abstract)")
    return parsed_records


def scrape_cluster(cluster_name: str, query: str) -> int:
    """Scrape one cluster and save to JSON."""
    print(f"\n{'='*60}")
    print(f"Cluster: {cluster_name}")
    print(f"{'='*60}")

    # Search
    pmids = search_pubmed(query, retmax=200)
    time.sleep(SLEEP_INTERVAL)

    if not pmids:
        print("  No results found")
        return 0

    # Fetch
    abstracts = fetch_abstracts(pmids)
    time.sleep(SLEEP_INTERVAL)

    # Save
    output_file = OUTPUT_DIR / f"{cluster_name}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(abstracts, f, indent=2, ensure_ascii=False)

    print(f"  Saved to {output_file}")
    print(f"  Total abstracts saved: {len(abstracts)}")

    return len(abstracts)


def main():
    """Main scraping pipeline."""
    print("="*60)
    print("Stromalytix PubMed Scraper")
    print("="*60)
    print(f"NCBI Email: {Entrez.email}")
    print(f"Output Directory: {OUTPUT_DIR.absolute()}")
    print(f"Clusters: {len(SEARCH_CLUSTERS)}")

    total_abstracts = 0

    for cluster_name, query in SEARCH_CLUSTERS.items():
        count = scrape_cluster(cluster_name, query)
        total_abstracts += count

    print(f"\n{'='*60}")
    print(f"SCRAPING COMPLETE")
    print(f"{'='*60}")
    print(f"Total abstracts saved across all clusters: {total_abstracts}")
    print(f"Files saved to: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    main()
