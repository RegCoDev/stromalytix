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


\## Vision — Read STRATEGY.md First

Stromalytix is Biological Process Intelligence for precision medicine.
NOT a lab tool. NOT analytics.

Three-layer architecture:
Layer 1 (Ingestion): CRM/ERP/ELN/LIMS/instruments → ProcessEvents
Layer 2 (Process Mining): PM4Py + biological extensions → KPIs
Layer 3 (Simulation): scikit-fem/CC3D/OpenMM/ProDy → predictions

Novel technical claim: business process signals (ERP batch variance,
CRM win rate) feed simulation parameter reweighting. No other
platform makes this connection.

Simulation stack build order:
Arc 1: CC3D brief → Arc 2: scikit-fem + CC3D live →
Arc 3: OpenMM → Arc 4: ProDy/AlphaFold

NEVER import cc3d in FastAPI or Streamlit.
Always subprocess: C:\CompuCell3D\Miniconda3\python.exe
Neo4j in Arc 2: AsyncGraphDatabase v5.28+, parameterized Cypher only.


\## Current Arc: Arc 1 — BioSim MVP + PI Foundation

Gate: Close 3 Tier 0 audits ($2,900 Protocol Stress Tests)

Done: RAG variance, CC3D sim brief, confidence tagging, PDF export, demo mode,
connectors, process mining, process graph, KPI dashboard, protocol ingestion,
CC3D runner, deployment prep


\## Build Rules

\- Arc 1 stack: Streamlit + Python only, no FastAPI yet (that's Arc 2)
\- Process mining: PM4Py for discovery/conformance, networkx for graph layer
\- Simulation: CC3D brief generation only (live CC3D execution is Arc 2)
\- Connectors: abstract base class + CSV import first, live API connectors in Arc 2
\- Always embed after scraping: run scripts/embed\_and\_index.py after adding to data/raw\_abstracts/

