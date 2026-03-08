"""
Embed and Index Abstracts into ChromaDB

Loads scraped PubMed abstracts, chunks them, and indexes into ChromaDB.
"""

import json
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

# Load environment variables
load_dotenv()

# Verify OpenAI API key
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY not found in .env file")

# Paths
INPUT_DIR = Path("data/raw_abstracts")
CHROMA_DIR = Path("data/chroma_db")
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# Collection name
COLLECTION_NAME = "stromalytix_kb"

# Text splitter configuration
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def load_cluster_documents(cluster_file: Path) -> List[Document]:
    """Load JSON file and create LangChain Documents."""
    cluster_name = cluster_file.stem  # Extract filename without extension

    print(f"\n  Loading {cluster_file.name}...")

    with open(cluster_file, "r", encoding="utf-8") as f:
        records = json.load(f)

    documents = []
    for record in records:
        # Create page_content: "{title}. {abstract}"
        page_content = f"{record['title']} {record['abstract']}"

        # Create metadata
        metadata = {
            "pmid": record["pmid"],
            "year": record["year"],
            "cluster": cluster_name,
            "title": record["title"]
        }

        doc = Document(page_content=page_content, metadata=metadata)
        documents.append(doc)

    print(f"  Loaded {len(documents)} documents from {cluster_name}")
    return documents


def main():
    """Main embedding and indexing pipeline."""
    print("=" * 60)
    print("Stromalytix Embedding & Indexing Pipeline")
    print("=" * 60)
    print(f"Input Directory: {INPUT_DIR.absolute()}")
    print(f"ChromaDB Directory: {CHROMA_DIR.absolute()}")
    print(f"Collection Name: {COLLECTION_NAME}")
    print(f"Chunk Size: {CHUNK_SIZE}, Overlap: {CHUNK_OVERLAP}")

    # Initialize text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
    )

    # Initialize embeddings
    print("\n  Initializing OpenAI embeddings (text-embedding-3-small)...")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    # Load all cluster files
    cluster_files = sorted(INPUT_DIR.glob("*.json"))
    print(f"\n  Found {len(cluster_files)} cluster files")

    all_documents = []

    # Load documents from each cluster
    print("\n" + "=" * 60)
    print("Loading Documents")
    print("=" * 60)

    for cluster_file in cluster_files:
        docs = load_cluster_documents(cluster_file)
        all_documents.extend(docs)

    print(f"\n  Total documents loaded: {len(all_documents)}")

    # Split documents into chunks
    print("\n" + "=" * 60)
    print("Splitting Documents")
    print("=" * 60)

    print(f"  Splitting {len(all_documents)} documents into chunks...")
    chunks = text_splitter.split_documents(all_documents)
    print(f"  Created {len(chunks)} chunks")

    # Create ChromaDB vector store
    print("\n" + "=" * 60)
    print("Embedding & Indexing into ChromaDB")
    print("=" * 60)

    print(f"  Creating ChromaDB collection '{COLLECTION_NAME}'...")
    print(f"  Embedding {len(chunks)} chunks (this may take a few minutes)...")

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=str(CHROMA_DIR)
    )

    print(f"  Successfully indexed {len(chunks)} chunks")
    print(f"  ChromaDB persisted to: {CHROMA_DIR.absolute()}")

    # Print summary by cluster
    print("\n" + "=" * 60)
    print("Summary by Cluster")
    print("=" * 60)

    cluster_counts = {}
    for chunk in chunks:
        cluster = chunk.metadata.get("cluster", "unknown")
        cluster_counts[cluster] = cluster_counts.get(cluster, 0) + 1

    for cluster, count in sorted(cluster_counts.items()):
        print(f"  {cluster}: {count} chunks")

    print("\n" + "=" * 60)
    print("INDEXING COMPLETE")
    print("=" * 60)
    print(f"Total chunks indexed: {len(chunks)}")
    print(f"Collection name: {COLLECTION_NAME}")
    print(f"Persist directory: {CHROMA_DIR.absolute()}")


if __name__ == "__main__":
    main()
