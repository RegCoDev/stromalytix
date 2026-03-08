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


\## Strategic Context

Full strategy doc: see STRATEGY.md

\- Category: Biological Process Intelligence (not LIMS, not ELN, not CRO)

\- Three layers: Data Ingestion → Process Intelligence (PM4Py) → Prediction (CC3D/scikit-fem/OpenMM)

\- Novel IP: cross-layer signal detection (business process → simulation reweighting)

\- North star metric: prediction accuracy (% sim risk predictions confirmed by wet lab)


\## Current Arc: Arc 1 — BioSim MVP + PI Foundation

Gate: Close 3 Tier 0 audits ($2,900 Protocol Stress Tests)

Done: RAG variance, CC3D sim brief, confidence tagging, PDF export, demo mode

Remaining Arc 1 items:
\- Protocol document ingestion (PDF/DOCX → ConstructProfile)
\- ProcessGraph data layer (networkx, Neo4j in Arc 2)
\- Connector interfaces (abstract base + CSV import)
\- PM4Py foundation (event log schema + basic discovery)
\- KPI dashboard skeleton
\- Streamlit Cloud deployment


\## Build Rules

\- Arc 1 stack: Streamlit + Python only, no FastAPI yet (that's Arc 2)
\- Process mining: PM4Py for discovery/conformance, networkx for graph layer
\- Simulation: CC3D brief generation only (live CC3D execution is Arc 2)
\- Connectors: abstract base class + CSV import first, live API connectors in Arc 2
\- Always embed after scraping: run scripts/embed\_and\_index.py after adding to data/raw\_abstracts/

