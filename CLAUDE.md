\# Stromalytix — BioSim Copilot



\## What This Is

A tissue engineering decision intelligence platform. Phase 1 MVP: 

chat assessment → PubMed RAG → process variance visualization.

Think Palantir Foundry for 3D cell culture protocols.



\## Stack (Phase 1 — Streamlit MVP)

\- Python 3.13 via uv

\- Streamlit (UI)

\- LangChain + Anthropic (chat + RAG)

\- ChromaDB (local vector store)

\- OpenAI text-embedding-3-small (embeddings)

\- Plotly (charts)

\- Biopython Entrez (PubMed scraper)



\## Commands

\- Run app: uv run streamlit run app.py

\- Scrape KB: uv run python scripts/scrape\_pubmed.py

\- Embed KB: uv run python scripts/embed\_and\_index.py

\- Install deps: uv sync



\## Critical Rules

\- CC3D Python lives at C:\\CompuCell3D\\Miniconda3\\python.exe — NEVER import cc3d in this project

\- All API keys in .env — never hardcode

\- ChromaDB persisted at data/chroma\_db/



\## Architecture

User Chat (Streamlit) → ConversationChain (Haiku) 

→ ConstructProfile (Pydantic) → RAG (ChromaDB + Sonnet) 

→ VarianceReport → Plotly Charts



\## Key Domain Context

\- Users: tissue engineers designing 3D cell culture constructs

\- Axes of variance: physiological relevance, disease phenotype fidelity, druggability

\- Primary parameters: scaffold stiffness (kPa), porosity (%), cell density, bioink material

\- Literature grounding: PubMed abstracts via Biopython Entrez API

