# Stromalytix Protocol Graph — Design Document

*April 2026*

---

## 1. Vision

Tissue engineering and cellular agriculture share a knowledge problem. Thousands of published papers describe protocols for fabricating scaffolds, seeding cells, crosslinking hydrogels, culturing constructs, and scaling bioreactor production — but the data is locked in prose. A researcher designing a GelMA-based cartilage construct, or an engineer optimizing a cultivated meat scaffold for myofiber maturation, has no structured way to ask: "What cell seeding densities have been used with this material for this cell type, and what outcomes resulted?"

Stromalytix builds the **protocol graph**: a structured, searchable, queryable representation of bioengineering protocols extracted from published literature. This spans both **tissue engineering** (regenerative medicine, organ-on-chip, disease modeling) and **cellular agriculture** (cultivated meat, cell-based protein, scalable biofabrication for food). Think BioNumbers for bioengineering, but at the protocol level rather than the parameter level.

The Knowledge Vault already indexes 1,204 papers with 10,306 chunks (2,359 from methods sections) and 117 curated biophysical parameters. The protocol graph adds a new layer on top: decomposing each paper's methods into a directed sequence of typed steps, with materials, cell populations, quantitative parameters, and measured outcomes attached to each step.

This is not another ontology project. It is a populated, queryable database with extraction pipelines that run against real papers and produce real structured data.

---

## 2. Strategic Model

**The Ginkgo Bioworks comparison.** Ginkgo's moat is not their foundry — it is their codebase of engineered organisms, which grows with every project. Stromalytix follows the same logic: published literature is the seed, not the moat. The moat is the structured protocol graph that grows through use.

**The flywheel:**

```
Published papers (seed)
        |
        v
Extraction pipeline  --->  Structured protocol graph
        ^                          |
        |                          v
User submissions  <---  Novelty scoring + predictions
        ^                          |
        |                          v
Outcome data  <----  Users run protocols + report results
```

**Phase 1 — Literature seed.** Extract protocols from the 1,204 indexed papers using regex/heuristic extraction (Tier 1) and optional LLM extraction (Tier 2). Build the initial graph with hundreds of structured protocols.

**Phase 2 — User submissions.** Researchers input their own protocols through the Streamlit interface. Each submission enriches the graph. The system learns which parameter combinations co-occur, which materials pair with which cell types, and which fabrication methods produce which outcomes.

**Phase 3 — Predictive models.** With enough structured protocols and outcome data, train models that predict: "Given this material, cell type, crosslinking method, and seeding density, what compressive modulus and cell viability should you expect at day 14?" Link prediction on the protocol graph becomes hypothesis generation.

The critical insight: Phase 1 data is freely available to anyone willing to read papers. Phase 2+ data is proprietary to the platform. Every user who submits a protocol makes the system more valuable for every other user.

---

## 3. Protocol Graph Architecture

### Node Types

| Node | Description | Key Fields |
|------|-------------|------------|
| **Protocol** | A complete fabrication workflow from a single paper | tissue, biofab_method, confidence |
| **ProtocolStep** | One action in the sequence | seq, action_type, duration, temperature |
| **StepMaterial** | A material used in a step | name, type, concentration, volume |
| **StepCell** | A cell population acted on in a step | type, source, passage, density |
| **StepParameter** | A quantitative measurement or setting | name, value, unit, confidence |
| **StepOutcome** | A measured result from an assay step | assay_type, timepoint, value, threshold |

### Edge Types

| Edge | From | To | Semantics |
|------|------|----|-----------|
| CONTAINS | Protocol | ProtocolStep | Protocol has ordered steps |
| FOLLOWS | ProtocolStep | ProtocolStep | Temporal ordering (seq N -> seq N+1) |
| USES | ProtocolStep | StepMaterial | Step consumes a material |
| ACTS_ON | ProtocolStep | StepCell | Step operates on a cell population |
| HAS_PARAMETER | ProtocolStep | StepParameter | Quantitative parameter attached to step |
| YIELDS | ProtocolStep | StepOutcome | Step produces a measurable outcome |

### Action Types (8 categories)

1. **cell_sourcing** — Obtaining cells (isolation from tissue, thawing from bank, iPSC differentiation)
2. **cell_expansion** — Growing cells to target quantity (passaging, media changes, confluence checks)
3. **material_prep** — Preparing scaffold materials (dissolving polymers, functionalizing surfaces, mixing bioinks)
4. **crosslinking** — Solidifying the scaffold (UV, thermal, ionic, enzymatic crosslinking)
5. **fabrication** — Forming the construct (3D printing, electrospinning, casting, molding)
6. **cell_seeding** — Introducing cells into/onto the scaffold
7. **culture** — Maintaining the construct in vitro (static, perfusion, mechanical stimulation)
8. **assay** — Measuring outcomes (viability, mechanical testing, histology, gene expression)

### Why SQLite in Phase 1

The protocol graph is a tree with fixed depth (protocol -> steps -> materials/cells/params/outcomes), not an arbitrary graph. SQLite handles this with straightforward JOINs across 6 tables. Benefits:

- **Zero infrastructure.** Same process, same file, same backup as the existing Knowledge Vault.
- **Sufficient scale.** Phase 1 targets hundreds to low thousands of protocols. SQLite handles millions of rows without issue.
- **Atomic with existing data.** Protocol extraction references `papers.id` and `chunks.id` — foreign keys in the same database.
- **WAL mode.** Concurrent reads from the Streamlit app while the extraction pipeline writes.

Phase 2+ may warrant Neo4j or a property graph layer when cross-protocol queries become the primary use case (e.g., "find all protocols that share at least 3 materials with this protocol but use a different crosslinking method"). The SQLite schema is designed so migration is a straightforward export.

---

## 4. Data Pipeline

```
PubMed search (TE keywords)
        |
        v
1,204 papers indexed (abstracts, metadata, clusters)
        |
        v
PMC full-text fetch (Open Access subset)
        |
        v
10,306 chunks (2,359 methods sections)
        |
        v
Tier 1: Regex/heuristic extraction (~60% coverage, <15s per paper)
        |
        v
Tier 2: LLM extraction (optional, ~90% coverage, ~$1.50 per paper)
        |
        v
Protocol graph (protocols + steps + materials + cells + parameters + outcomes)
        |
        v
Novelty scoring / hypothesis generation
```

### Data flow details

**PubMed abstracts.** The initial corpus of 1,204 papers was built from PubMed searches targeting tissue engineering, bioprinting, scaffold fabrication, hydrogel crosslinking, and related terms. Each paper is stored with PMID, DOI, title, year, journal, authors, and cluster labels.

**PMC full text.** For papers in the PMC Open Access subset, full text is fetched and chunked by section. The chunker produces section-labeled chunks (abstract, introduction, methods, results, discussion). The 2,359 methods chunks are the primary extraction targets.

**Embedding and indexing.** Each chunk gets a 384-dimensional embedding (sentence-transformers, all-MiniLM-L6-v2) stored in sqlite-vss for vector similarity search. FTS5 provides BM25 keyword search. Retrieval uses reciprocal rank fusion (RRF) across both.

**Extraction.** Tier 1 regex runs against methods chunks, classifying sentences by action type and extracting materials, cell types, concentrations, temperatures, durations, and other parameters. Tier 2 LLM extraction (optional) uses a structured prompt to produce a complete Protocol object from the combined methods text of a paper.

**Protocol insertion.** The `insert_protocol()` function writes the full graph atomically — protocol row, all steps, and all step-level entities — in a single transaction.

---

## 5. Extraction Engine

### Tier 1: Regex/Heuristic (free, deterministic)

The first tier uses pattern matching against methods-section sentences. Each sentence is:

1. **Classified by action type** using keyword dictionaries (e.g., "dissolved", "prepared", "mixed" -> material_prep; "crosslinked", "photopolymerized", "gelled" -> crosslinking; "seeded", "encapsulated" -> cell_seeding).

2. **Parsed for entities** using regex patterns:
   - Materials: known material names from the entity dictionary (GelMA, alginate, PCL, PLGA, collagen, fibrin, etc.)
   - Cell types: pattern matching for common formats (hMSCs, chondrocytes, HUVECs, C2C12, etc.)
   - Concentrations: `\d+\.?\d*\s*(%|mg/mL|w/v|mM|µM)`
   - Temperatures: `\d+\s*°C`
   - Durations: `\d+\s*(min|h|hours|days|weeks)`
   - Cell densities: `\d+\.?\d*\s*[×x]\s*10\^?\d+\s*(cells/mL|cells/cm²)`

3. **Scored for completeness.** A protocol with all 8 action types covered gets completeness = 1.0. Missing action types reduce the score proportionally. Confidence is set based on completeness: high (>0.8), medium (0.5-0.8), low (<0.5).

**Expected coverage:** ~60% of extractable information from well-structured methods sections. Fast (<15 seconds per paper), free, deterministic, debuggable.

### Tier 2: LLM Extraction (optional, high-quality)

For papers where Tier 1 produces low-confidence results, or on demand, an LLM extracts the full protocol. The prompt provides the Protocol schema and asks the model to:

1. Identify all protocol steps in order.
2. Classify each step by action type.
3. Extract all materials, cells, parameters, and outcomes per step.
4. Flag uncertain extractions with low confidence.

**Expected coverage:** ~90% of extractable information. Cost: ~$1.50 per paper (Claude Sonnet with a ~4K token methods section). The LLM tier is optional — the system functions on Tier 1 alone.

### Sentence-level extraction rationale

Methods sections in biomedical papers are sentence-structured by convention. Each sentence typically describes one action with its parameters. This makes sentence-level classification and extraction natural. Paragraph-level extraction loses the sequential structure; section-level extraction conflates too many actions.

---

## 6. Parameter Library Strategy

### Current state: 117 curated entries

The Knowledge Vault contains 117 manually curated biophysical parameters across tables covering scaffold mechanics, degradation rates, cell viability benchmarks, crosslinking conditions, and bioink rheology. Each entry has a value, unit, material context, cell type context, confidence level, and DOI.

### Growth path

**Auto-extraction (Phase 1):** The protocol graph extraction pipeline pulls quantitative parameters from methods sections and attaches them to steps. Each extracted parameter carries confidence, extraction method, and source sentence for traceability. This is expected to expand the library to 500-2,000 entries from the existing 1,204-paper corpus.

**Community curation (Phase 2):** Users review auto-extracted parameters, confirm or correct values, and submit new entries from their own work. A curation interface shows parameter, source sentence, and context, and lets users set confidence to "curated" with one click.

**Publication target (Phase 3):** When the library reaches 1,000+ curated entries with DOIs, publish a "BioNumbers for Tissue Engineering" paper in Nucleic Acids Research (Database issue) or similar. The parameter library becomes a citable resource. NAR Database issue papers are high-impact, high-citation, and establish the platform as a reference.

### Parameter schema

Each parameter lives at the step level in the protocol graph (`step_parameters` table) with:
- `parameter_name`: standardized name (e.g., "compressive_modulus", "cell_viability", "degradation_rate")
- `value`: numeric value
- `unit`: standardized unit string
- `confidence`: low / medium / high / curated
- `extraction_method`: regex / llm / manual
- `source_sentence`: the exact sentence the value was extracted from

This dual existence — parameters in the flat `parameters` table (curated library) and in `step_parameters` (protocol context) — is intentional. The flat table is the searchable reference library. The step-level table preserves protocol context (what material, what cell type, what fabrication method produced this value).

---

## 7. Novelty Scoring

Novelty scoring answers: "How much of this proposed protocol is covered by existing literature, and where are the gaps?"

### Algorithm

1. **Decompose** the user's protocol into steps, each with an action type and key entities (materials, cells, parameters).

2. **Match each step** against the protocol graph:
   - Find all existing steps with the same action_type.
   - Score material overlap (Jaccard on material names).
   - Score cell type overlap.
   - Score parameter proximity (are the proposed values within the range seen in literature?).

3. **Compute per-step novelty:**
   - `novelty = 1.0 - (matching_protocols / total_protocols_with_action_type)`
   - Weighted by entity-level overlap. A step using GelMA + chondrocytes for cartilage is low-novelty if 50 protocols do the same. A step using a novel material combination scores high.

4. **Identify gaps:** Steps where novelty > 0.8 are flagged as gaps — these are protocol elements with little or no literature precedent.

5. **Overall novelty:** Weighted average of per-step novelty scores, weighted by step importance (fabrication and crosslinking steps weighted higher than culture steps, since they determine construct properties).

### Link prediction formalization

In graph terms, novelty scoring is the inverse of link prediction. A "novel" protocol is one whose edges (material-action, cell-action, parameter-value combinations) are not predicted by the existing graph. This formalizes hypothesis generation: high-novelty, high-plausibility combinations are research hypotheses worth testing.

Future work: train a GNN or factorization model on the protocol graph to predict missing edges. "Papers that used GelMA with MSCs for bone also used BMP-2 at step 7 — your protocol doesn't include a growth factor step. Consider adding one."

---

## 8. Comparison to Prior Art

| System | What it does | Gap Stromalytix fills |
|--------|-------------|----------------------|
| **EXACT2** | Protocol ontology (XML schema for experimental actions) | Ontology only — not populated for TE. No extraction pipeline, no parameter library. |
| **OBI / OBI-OSCI** | Broad biomedical investigation ontology | Too general. No TE-specific terms, no fabrication action types, no scaffold parameters. |
| **BioKGrapher / AutoBioKG** | Automated biomedical knowledge graph construction | General biomedical entities (genes, diseases, drugs). No protocol structure, no fabrication steps, no mechanical properties. |
| **BioNumbers** | Curated biological numbers database | Parameter-level only. No protocol context — you get "E. coli doubling time = 20 min" but not "in step 3 of this protocol, at 37C in LB media." |
| **BRENDA** | Enzyme kinetics database | Enzyme-specific. No scaffold mechanics, no cell viability, no construct-level parameters. |
| **Protocols.io** | Protocol sharing platform | User-submitted free text. No structured extraction, no parameter library, no novelty scoring, no graph queries. |
| **MatWeb / CES EduPack** | Materials property databases | Bulk material properties, not biological context. "PCL tensile strength = 23 MPa" but not "PCL scaffold with 300 µm pores seeded with MSCs at passage 4." |

**What Stromalytix adds that none of these have:**

1. A TE-specific protocol schema with 8 action types and 6 entity tables.
2. An extraction pipeline that converts published prose into structured graph data.
3. A parameter library with protocol-level context (not just isolated values).
4. Novelty scoring that quantifies how much of a proposed protocol is covered by literature.
5. A growth flywheel from literature seed to user submissions to predictive models.

---

## 9. Product Tiers

### Free Tier
- **Parameter library.** Browse and search the curated parameter database. Filter by material, cell type, tissue, parameter name.
- **Protocol assessment.** Describe your protocol in natural language; get a structured breakdown with completeness scoring.
- **Protocol search.** Query the protocol graph by tissue type, biofabrication method, material, or cell type. View step sequences from published papers.
- **Basic novelty check.** See which parts of your protocol have literature precedent and which are novel.

### Pro Tier
- **CC3D simulation.** Run CompuCell3D cellular Potts model simulations parameterized from the knowledge vault.
- **FEA analysis.** Finite element analysis of scaffold mechanics using scikit-fem with literature-derived material properties.
- **Full assessment reports.** PDF reports with parameter comparisons, literature citations, simulation results, and novelty analysis.
- **Protocol graph queries.** Advanced graph queries: "Find all protocols that produced >90% viability at day 7 using GelMA."
- **LLM extraction.** On-demand Tier 2 extraction for papers not yet in the graph.

### Enterprise Tier
- **API access.** REST API for programmatic access to the protocol graph, parameter library, and novelty scoring.
- **Custom extraction.** Bulk extraction from proprietary paper collections or internal protocols.
- **Private vaults.** Isolated protocol graphs for proprietary data, not shared with the public graph.
- **Integration.** Connect to ELN/LIMS systems for automatic protocol ingestion.

---

## 10. Roadmap

### Phase 1 — Extraction + Graph DB + API (current)

- [x] Knowledge Vault with 1,204 papers, 10,306 chunks, 117 parameters
- [x] Hybrid search (BM25 + vector + RRF) via sqlite-vss
- [x] CC3D simulation sidecar (running, verified end-to-end)
- [x] Streamlit app with chat, assessment, simulation tabs
- [ ] Protocol graph schema (6 tables, this document)
- [ ] Tier 1 regex extraction pipeline
- [ ] Protocol graph API endpoints (CRUD + query + match + stats)
- [ ] Streamlit protocol browser tab

### Phase 2 — Novelty Scoring + User Submissions + Embeddings

- [ ] Per-step novelty scoring algorithm
- [ ] Protocol submission form in Streamlit
- [ ] Protocol-level embeddings (sentence-transformers on concatenated step descriptions)
- [ ] Embedding-based protocol similarity (complement field-matching with vector similarity)
- [ ] Parameter curation interface
- [ ] Tier 2 LLM extraction (optional, on-demand)

### Phase 3 — Hypothesis Generation + Predictive Models

- [ ] Link prediction on protocol graph (predict missing steps, materials, parameters)
- [ ] Outcome prediction models (given protocol, predict viability/mechanics/etc.)
- [ ] Cross-protocol analysis ("protocols for cartilage that use GelMA tend to add TGF-beta3 at step 5")
- [ ] Automated literature monitoring (new PubMed papers -> extraction -> graph update)

### Phase 4 — Community Portal + Publication

- [ ] Web portal for protocol browsing and submission (beyond Streamlit)
- [ ] Community curation workflow (propose edits, review queue, provenance tracking)
- [ ] NAR Database issue paper: "Stromalytix: A Structured Protocol Graph for Tissue Engineering"
- [ ] Public API with rate limiting and API keys
- [ ] DOI assignment for curated parameter entries

---

## 11. Technical Decisions

### SQLite over Neo4j (Phase 1)

The protocol graph has fixed depth (protocol -> step -> entities) and the primary query patterns are:
- Filter protocols by metadata (tissue, biofab method)
- Filter by step-level entities (materials, cell types) via JOINs
- Load a full protocol with all nested data (6-table JOIN)
- Aggregate statistics (GROUP BY queries)

All of these are straightforward SQL. Neo4j adds operational complexity (separate process, separate backup, JVM memory management) for no query-expressiveness benefit at this scale. The break-even point is when cross-protocol graph traversals become frequent — estimated at Phase 2+, when the graph exceeds ~10,000 protocols and users need queries like "find the shortest path between this material combination and this outcome."

SQLite specifics:
- WAL mode for concurrent read/write (Streamlit reads, extraction pipeline writes)
- Foreign keys ON for referential integrity
- Same `vault.db` file as papers, chunks, and parameters — single backup target
- Row factory set to `sqlite3.Row` for dict-like access throughout

### Regex before LLM

Tier 1 regex extraction is:
- **Free.** No API costs. Runs on the server CPU.
- **Deterministic.** Same input always produces same output. No temperature, no sampling variance.
- **Debuggable.** When extraction is wrong, you can trace exactly which regex matched which substring.
- **Fast.** <15 seconds per paper vs. ~30 seconds + API latency for LLM.

The 60% coverage ceiling is acceptable for Phase 1. The remaining 40% is typically: complex multi-sentence parameter descriptions, implicit protocol steps, and non-standard terminology. LLM extraction (Tier 2) addresses these, but is optional and additive — it never replaces Tier 1, it fills gaps.

### Sentence-level extraction

Methods sections in biomedical literature follow a consistent pattern: one action per sentence, with parameters inline. Example:

> "GelMA (5% w/v) was dissolved in PBS at 60C for 30 minutes."

This single sentence yields:
- action_type: material_prep
- material: GelMA, concentration: 5% w/v
- material: PBS
- temperature: 60C
- duration: 30 minutes

Sentence boundaries are natural extraction units. Paragraph-level extraction loses step ordering. Section-level extraction conflates dozens of steps. The sentence-level approach maps directly to the ProtocolStep model.

### Local embeddings

The Knowledge Vault uses `all-MiniLM-L6-v2` (384 dimensions) via sentence-transformers for chunk embeddings. This model:
- Runs locally — no API cost, no rate limits, no latency.
- Produces 384-dim vectors — compact enough for sqlite-vss without dimensionality reduction.
- Performs well on biomedical text despite being trained on general English (validated against BioSentVec; difference is <3% on our retrieval benchmarks).

For protocol-level embeddings (Phase 2), the same model will encode concatenated step descriptions. Protocol similarity will combine field-matching (from `match_protocols()`) with cosine similarity on embeddings via reciprocal rank fusion.

### Hybrid search (BM25 + Vector + RRF)

The retrieval pipeline combines:
1. **BM25** via FTS5 — exact keyword matching, handles technical terms (specific material names, gene names, catalog numbers).
2. **Vector similarity** via sqlite-vss — semantic matching, handles paraphrases and conceptual queries.
3. **Reciprocal Rank Fusion (RRF)** — merges ranked lists with `score = sum(1 / (k + rank))` across both sources.

This hybrid approach outperforms either method alone on our query set. BM25 catches specific terms the embedding model may not distinguish ("GelMA" vs. "gelatin methacryloyl"). Vector search catches conceptual matches ("scaffold stiffness" matching "compressive modulus of the construct").
