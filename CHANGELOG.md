# Changelog

## v0.2.0 — Cell-ECM Interaction Modeling Pivot (2026-03-25)

Narrowed Stromalytix from a four-module platform to a single-focus product:
**cell-ECM interaction modeling** for predicting cell adhesion and proliferation
on extracellular matrix / scaffold substrates.

### Rationale

Insights from a customer discovery call with Jordan Jones (2026-03-25) identified
that commercial clients in Cell Ag and tissue engineering want bioreactor digital
twins focused on cell-scaffold interactions — specifically predicting how cells
adhere and proliferate based on substrate properties. Process intelligence,
transplant scoring, materials lot QC, and partner white-labeling are distractions
at this stage. The path to early adopters runs through well-characterized cell
lines (C2C12, fibroblasts) and compelling simulation demos, not broad platform
features.

### What changed

- **Removed tabs**: Materials Intelligence, Process Intelligence, and Transplant PI
  tabs removed from `app.py`. The app is now a single-page BioSim Copilot.
- **Archived modules**: 17 core modules, 4 connectors, ~20 test files, partner app,
  and supporting data moved to `archive/v0.1.0-pre-pivot/`. Nothing was deleted.
- **Simplified scripts**: `embed_public_data.py` no longer embeds transplant data.
  `fetch_public_data.py` no longer creates hepatic/DILIrank stubs.
- **Updated README**: Rewritten for cell-ECM interaction modeling focus.

### What stays

- BioSim Copilot: chat-driven construct assessment, PubMed RAG, variance analysis
- CC3D simulation: script generation, local/cloud execution, VTK visualization
- FEA solver: scikit-fem scaffold deformation and stress prediction
- 3D tissue visualization: Plotly-based construct rendering
- PDF export: variance report generation
- Knowledge base pipeline: PubMed scraping, embedding, ChromaDB

---

## v0.1.0 — Full Platform (2026-02-15 through 2026-03-08)

The original four-module Biological Process Intelligence platform. 251 tests,
~8,100 PubMed abstracts in ChromaDB, CC3D simulation pipeline, partner
white-label app, and proprietary process mining engine.

### Modules

**BioSim Copilot** (`app.py`, `core/chat.py`, `core/rag.py`, `core/models.py`)
Chat-driven construct assessment. Users describe their 3D cell culture protocol
through a guided conversation. The system extracts a ConstructProfile, queries
a PubMed-derived ChromaDB knowledge base, and synthesizes a variance report with
PMID-cited risk analysis. Includes radar charts, risk scorecards, parameter
scatter plots, and a CC3D simulation brief.

**Process Intelligence** (`core/bio_process_miner.py`, `core/pi_ui.py`, and 8 supporting modules)
Proprietary process mining engine built without pm4py. Included InductiveMiner,
HeuristicsMiner, ConformanceChecker, and BiologicalExtensions for batch effect
detection, critical control point identification, and CRM/deal correlation.
Featured a full Streamlit dashboard with data connectors (ELN, CRM, instrument CSV),
KPI dashboard, process graph visualization, company context persistence, and a
simulation-to-process bridge that translated organizational KPIs into biological
simulation parameters. APQC PCF framework mapping for business best practices.

**Materials Intelligence** (`core/materials_intelligence.py`)
Bioink lot QC predictions. Flory-Rehner stiffness estimation from rheology data,
Herschel-Bulkley extrusion printability scoring, and calibrated mechanotransduction
viability curves. RELEASE/CONDITIONAL/HOLD lot decisions with uncertainty
quantification. Cell type mappings for hepatocytes, HUVECs, and neurons.

**Transplant PI** (`core/transplant_intelligence.py`)
Liver transplant early allograft dysfunction (EAD) risk scoring. Conformance-based
approach treating the transplant workflow as a process. NMP perfusion trace analysis
with VITTAL and PILOT trial calibration. Donor/recipient risk factor scoring.

### Additional modules

- `core/hepatic_intelligence.py` — DILI detection scoring for hepatic constructs,
  DILIrank benchmark sensitivity/specificity
- `core/dlp_physics.py` — DLP bioprinting: Beer-Lambert cure depth, UV dose
  viability heuristics, layer bonding predictions
- `core/ooc_physics.py` — Organ-on-chip wall shear stress and TEER vs shear curves
- `core/reading_engine.py` — APQC PCF business reading + scientific literature
  recommendations, context-driven from PI signals
- `core/sim_process_bridge.py` — Convergent/divergent signal detection between
  simulation predictions and operational data
- `core/synthetic_log_generator.py` — Sparse event log augmentation for process mining
- `partner_app.py` + `core/partner_config.py` — White-label Streamlit app for
  partners (CytoInk demo), branded PDF report generation

### Data assets

- `data/raw_abstracts/` — 5 PubMed corpus JSONs (~8,100 abstracts total)
- `data/public/transplant/` — VITTAL and PILOT NMP trial criteria
- `data/public/hepatic/` — DILIrank download stub
- `data/public/biofab/` — Literature benchmarks with DOIs
- `data/public/process_mining/` — BPI Challenge 2017 stub
- `data/knowledge/` — APQC PCF biofab mapping, TE/biofab reading lists
- `data/company_contexts/` — Persistent org context (Centara demo, test_co)
- `data/demo/` — Centara CRM + ELN synthetic CSVs
- `partners/` — CytoInk and demo partner configs

### Infrastructure

- CC3D cloud sidecar (`services/cc3d_runner_api/`) — FastAPI service for remote
  CompuCell3D execution on VPS
- PubMed scraping pipeline (`scripts/scrape_pubmed.py`, `scrape_cc3d_params.py`)
- ChromaDB embedding pipeline (`scripts/embed_and_index.py`, `embed_public_data.py`)
- Gallery generator, demo data generator, dev loop scripts

### Git history (key commits)

```
33750b3 fix: correct DOIs and improve calibration data provenance
7ca43a3 fix: support Streamlit Cloud secrets for API keys
eee1771 feat: protocol ingestion + deployment cleanup
240dacc fix: add honest provenance annotations to mechanotransduction curves
3bde8c7 chore: add reportlab dependency
3b60525 feat: partner platform — config system, intake form, branded PDF export
489d51b feat: DLP physics model (Beer-Lambert) + OoC shear/TEER + modality guards
cb3a6ac pre-ralph arc5 checkpoint
19f268a feat: embed public data into ChromaDB (transplant_intelligence + calibration_benchmarks)
97c9ba6 feat: transplant PI + grounded materials intelligence + NMP data + VPS setup
2bad2f9 feat: materials intelligence module + UI tab for bioink lot QC (P5)
8836b2e feat: public data benchmarks + synthetic event log augmentation
4ee4eae feat: CC3D cloud sidecar + hepatic DILI detection intelligence
0137c2f feat: pre-generated render gallery for Streamlit Cloud fallback
68d435d feat: visualization export (PNG/SVG via kaleido) + download buttons
779dad4 feat: PI Chat reading integration — context-driven citations
dbe6413 feat: Further Reading UI in BioSim and PI tabs
e9cd06e feat: APQC PCF + TE/biofab reading knowledge bases and ReadingEngine
92f9870 feat: live construct visualization + partial profile extraction
```
