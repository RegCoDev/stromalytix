# Stromalytix — Strategic Vision
*Last updated: March 2026*

---

## The One Sentence

Stromalytix is the **Biological Process Intelligence platform** — the unified
intelligence layer connecting business operations, experimental workflows, and
biophysical simulation for precision medicine companies.

---

## The Full Vision

Most precision medicine startups, bioink companies, and regenerative medicine
manufacturers are running on chaos. Their business data lives in a CRM. Their
manufacturing data lives in an ERP or spreadsheets. Their experimental data
lives in an ELN, LIMS, or worse — email threads and shared drives. Their
instrument data lives on local lab computers. None of it talks to each other.

No one has connected:
- **Why a deal closed or churned** to the experimental parameters that produced
  the construct the customer received
- **Why batch 47 had lower viability** to the CRM record showing the customer
  who received it filed a complaint
- **Why Protocol v3.2 deviates 3x more than v3.1** to the specific step where
  operator variance is highest
- **Why IC50 values don't translate in vivo** to the scaffold parameter
  combination that was used for that assay

Stromalytix connects all of it — and adds a layer no one else has:
**biophysical simulation that predicts outcomes before the experiment runs.**

---

## The Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 3: PREDICTION                          │
│  scikit-fem → CC3D → OpenMM → ProDy → AlphaFold                │
│  "What will happen before you run the experiment?"              │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                    feeds predictions into
                              │
┌─────────────────────────────────────────────────────────────────┐
│                 LAYER 2: PROCESS INTELLIGENCE                   │
│  Process Mining (PM4Py/Petri nets) + Process Graph (Neo4j)     │
│  "What actually happens vs. what should happen?"               │
│                                                                 │
│  Event logs → Process discovery → Conformance checking →       │
│  Bottleneck analysis → Deviation detection → KPI tracking      │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                    structured from
                              │
┌─────────────────────────────────────────────────────────────────┐
│                   LAYER 1: DATA INGESTION                       │
│  CRM | ERP | ELN | LIMS | Instruments | Documents              │
│  "Where their data actually lives"                              │
│                                                                 │
│  Salesforce/HubSpot → deals, orders, customer requirements     │
│  SAP/NetSuite/Odoo  → batches, inventory, QC records           │
│  Benchling/LabArchives → protocols, results, deviations        │
│  Instrument exports → bioprinter logs, plate readers, etc.     │
│  PDFs/Excel/email   → the chaos layer (most of them)           │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Category

**Biological Process Intelligence.**

Not LIMS. Not ELN. Not a CRO. Not analytics. Not just simulation.
The unified layer above all of them.

Celonis mines SAP event logs and tells you where your business process
deviates from the ideal. Stromalytix does that — and then runs a
biophysical simulation to tell you why the deviation happened at the
molecular level, and what to change in experimental parameters to fix it.

That connection — business process signal → experimental prediction —
does not exist anywhere else in the market.

---

## The Cross-Layer Insight (The Novel Thing)

**CRM → Experimental:**
A new customer needs cardiac tissue at 8 kPa for HCM disease modeling.
Before they send their protocol, BioSim pre-runs the variance analysis
and flags that their likely cell density will produce a hypoxic core.
You arrive at the first call already knowing their failure mode.

**ERP → RAG Calibration:**
ERP shows bioink batch 47 had higher viscosity variance (3.2% vs 1.8% CV).
Process graph flags all constructs from batch 47. Their simulation brief
confidence tags automatically drop from "medium" to "low" for
stiffness-dependent parameters. The platform self-corrects.

**ELN → Process Mining:**
ELN records show Protocol v3.2 generates 3x more deviation notes at
Step 7 (cell seeding density adjustment) than v3.1. PM4Py Petri net
discovery surfaces Step 7 as the critical control point. BioSim runs
a cell density sensitivity sweep. Result: ±15% density variance at
Step 7 is the primary viability driver, not scaffold stiffness.
Recommendation: tighten tolerance or add pre-seeding viability check.

**Business outcome → Model calibration:**
CRM shows constructs from Protocol v3.1, batches 23-41 closed 4 deals.
Batches 42-51 produced 2 churned customers. Process graph queries the
parameter delta between those batches. The difference: porosity was 3%
lower due to a nozzle diameter change. That signal calibrates the
simulation parameter database. Every future porosity prediction is
now more accurate.

None of this exists in the current market.

---

## Data Sources — Full Ingestion Map

### Business Layer
| Source | Data | Signal |
|--------|------|--------|
| Salesforce / HubSpot | Deals, contacts, orders, requirements | Customer construct specs, revenue per protocol |
| SAP / NetSuite / Odoo | Batch records, inventory, QC | Material lot tracking, production variance |
| QuickBooks / Xero | COGS, margins | Cost per construct, protocol profitability |
| Email / Slack | Customer feedback, support | Qualitative outcome signals |

### Scientific Layer
| Source | Data | Signal |
|--------|------|--------|
| Benchling | Protocols, results, deviations | ELN ground truth |
| LabArchives / SciNote | Experimental notebooks | Protocol version history |
| LabWare / StarLIMS | Sample tracking, QC results | Quality control baseline |
| Bioprinter logs (Cellink, Allevi, Aspect) | Print params, nozzle, pressure | Process parameter ground truth |
| Plate reader exports | Viability, IC50, TEER, contractility | Outcome ground truth |
| Rheometer exports | Viscosity, storage modulus | Bioink lot characterization |

### Document Layer (The Chaos Layer)
| Source | Approach |
|--------|----------|
| Protocol PDFs | LLM extraction → ConstructProfile |
| Batch records (paper/PDF) | OCR + LLM → event log |
| SOPs | Process map extraction → Petri net |
| COAs | Material spec extraction → Parameter node |

---

## The Process Mining Engine

Built on PM4Py (open source, van der Aalst group) + biological extensions.

**Process Discovery:** Given an event log, infer the actual process as a
Petri net. Compare to documented SOP. Surface deviations.

**Conformance Checking:** Score each experimental run against the protocol.
Flag critical deviations. Identify which deviations correlate with failures.

**Performance Analysis:** Bottleneck detection, waiting time, resource
utilization. Where is time and material being lost?

**Predictive Process Monitoring:** Given a partially completed run, predict
success or failure based on historical patterns — weighted by simulation
predictions.

**Biological Extensions (custom IP):**
Standard process mining assumes discrete events. Biological processes have
continuous measurements, fuzzy step boundaries, stochastic outcomes at
identical nominal parameters, and batch effects. The biological process
mining extensions that handle these are Stromalytix's core IP.

---

## The Simulation Stack (Prediction Layer)

```
scikit-fem   → scaffold mechanics (Arc 2)
               Stiffness, deformation, stress distribution

CC3D         → emergent cell behavior (Arc 1 brief → Arc 2 live)
               Cell organization, immune exclusion, necrotic core

OpenMM       → molecular ECM dynamics (Arc 3)
               RGD accessibility, crosslink density effects

ProDy NMA    → protein flexibility (Arc 2/3)
               ECM protein conformation under strain

AlphaFold    → druggability layer (Arc 4)
               Cryptic binding site exposure
```

---

## Primary Target Segments

### Segment 1 — Bioink & Tissue Model Companies (Immediate)
*Axolotl Biosciences, Cytoink, AsterBioFab*

Their consulting service advises on bioprinter optimization. We power
that service with PI reports that make their reproducibility claim
mechanistically defensible. White-labeled. Channel play.

### Segment 2 — Precision Oncology CROs (Near-term)
Construct variance is the #1 source of IC50 irreproducibility between
labs. We identify the specific protocol steps driving that variance.

### Segment 3 — Cell Therapy Manufacturers (Medium-term)
Process variance = patient risk. FDA requires process characterization.
We provide the three-layer platform that makes that characterization
mechanistically grounded, not just statistical.

### Segment 4 — Hospital Precision Medicine Programs (Long-term)
Patient-derived organoid programs. The prediction layer matters most
here — using simulation rather than historical data for novel patient
profiles.

---

## Engagement Tiers

| Tier | Name | Price | Scope |
|------|------|-------|-------|
| 0 | Protocol Stress Test | $2,900 | Variance report + simulation brief, 1 week |
| 1 | Process Intelligence Baseline | $8–15K | Full bioprocess mapping, Current State Report, 2 weeks |
| 2 | Ongoing PI | $2.5–5K/mo | Continuous monitoring, cross-run correlation |
| 3 | Full Platform License | $25–75K/yr | All connectors live, process mining, simulation stack |

---

## Build Arcs

### Arc 1 — BioSim MVP + PI Foundation (Now → Month 1)
**Gate:** Close 3 Tier 0 audits

- ✅ RAG variance analysis
- ✅ CC3D simulation brief with confidence tagging
- ✅ PDF export + white-label
- 🔧 Protocol document ingestion (PDF/DOCX → ConstructProfile)
- 🔧 ProcessGraph data layer (networkx → Neo4j in Arc 2)
- 🔧 Connector interfaces (abstract base + CSV import)
- 🔧 PM4Py foundation (event log schema + basic discovery)
- 🔧 KPI dashboard skeleton
- 🔧 Streamlit Cloud deployment

### Arc 2 — Full Process Intelligence (Months 2–4)
**Gate:** NDA/paid POC with Cytoink or Axolotl

- FastAPI + Blueprint.js
- Live API connectors: Benchling, HubSpot, Salesforce CSV
- PM4Py full integration: discovery, conformance, performance
- scikit-fem scaffold mechanics
- Neo4j process graph
- Cross-layer signal detection
- CC3D live execution

### Arc 3 — Prediction Engine + Business Layer (Months 5–8)
**Gate:** Full loop demo for IndieBio / institutional contract

- OpenMM molecular dynamics
- ERP connectors
- Predictive process monitoring
- Business outcome → calibration feedback loop
- Self-service platform

### Arc 4 — Clinical + Druggability (Months 9–12)
**Gate:** First hospital system / pharma subscription

- AlphaFold druggability integration
- Patient-derived construct profiling
- Regulatory submission support

---

## The Moat

1. **Biological process mining IP** — PM4Py extensions for continuous
   measurements, batch effects, stochastic biological outcomes
2. **Cross-layer signal detection** — business process → simulation
   reweighting, no one else has this connection
3. **Calibration database** — every experimental outcome fed back
   makes predictions more accurate. Compounds with use.
4. **Network effects** — anonymized cross-company parameter benchmarks
   improve with every connected company

The moat is not the software. The moat is the biological process mining
IP plus the calibration data plus the cross-layer connections.

---

## North Star Metric

**Prediction accuracy:** % of simulation risk predictions confirmed
by subsequent wet lab outcomes.

Current: 0 calibration data points. First 3 audits are the seed.
Arc 2 gate: 70% qualitative accuracy, 10+ real experimental outcomes.
Arc 3 gate: 80% accuracy with business outcome correlation.
