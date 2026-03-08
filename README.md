# Stromalytix

Biological Process Intelligence platform for precision medicine. Connects business operations, experimental workflows, and biophysical simulation to predict outcomes before experiments run.

## What It Does

Four integrated modules in a single Streamlit app:

| Tab | Purpose |
|-----|---------|
| **BioSim Copilot** | Chat-driven construct assessment, PubMed RAG variance analysis, CC3D simulation briefs, FEA scaffold mechanics, 3D tissue visualization |
| **Process Intelligence** | Proprietary process mining engine (no pm4py), conformance checking, batch effect detection, cross-layer signal detection, company context |
| **Materials Intelligence** | Bioink lot QC — Flory-Rehner stiffness, Herschel-Bulkley printability, calibrated mechanotransduction viability curves. RELEASE/CONDITIONAL/HOLD decisions |
| **Transplant PI** | Liver transplant EAD risk from NMP perfusion traces + donor/recipient parameters. Conformance-based scoring with VITTAL/PILOT trial calibration |

## Quick Start

```bash
# Install uv (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/RegCoDev/stromalytix.git
cd stromalytix
uv sync

# Set up environment
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY and OPENAI_API_KEY

# Build knowledge base
uv run python scripts/scrape_pubmed.py
uv run python scripts/embed_and_index.py
uv run python scripts/embed_public_data.py    # transplant + calibration benchmarks
uv run python scripts/fetch_public_data.py     # literature benchmarks + data stubs

# Run the app
uv run streamlit run app.py
```

## Tests

```bash
uv run pytest tests/ -v --tb=short
# 251 tests as of 2026-03-08
```

## Architecture

```
Layer 3 — Prediction
  scikit-fem (FEA)  |  CC3D (cell simulation)  |  Flory-Rehner / Herschel-Bulkley

Layer 2 — Process Intelligence
  Proprietary process mining engine (InductiveMiner, ConformanceChecker)
  Process graph (NetworkX)  |  Company context  |  Cross-layer signals

Layer 1 — Data Ingestion
  CRM / ERP / ELN / LIMS / Instruments → ProcessEvent schema
```

## ChromaDB Collections

| Collection | Docs | Content |
|-----------|------|---------|
| `stromalytix_kb` | ~8,100 | PubMed abstracts for RAG |
| `transplant_intelligence` | 16 | NMP trial criteria (VITTAL + PILOT) |
| `calibration_benchmarks` | 13 | Literature benchmarks with DOIs |

Rebuilt by running `scripts/embed_and_index.py` and `scripts/embed_public_data.py`.

## CC3D Cloud Sidecar (Optional)

For remote CC3D execution on a VPS:

```bash
# On VPS (Ubuntu 20.04+, 4GB+ RAM)
bash services/cc3d_runner_api/vps_setup.sh
# Edit /etc/systemd/system/cc3d-runner.service — set STROMALYTIX_API_KEY
systemctl start cc3d-runner
```

Then set in `.env` or Streamlit secrets:
```
CC3D_API_URL=http://YOUR_VPS_IP:8001
CC3D_API_KEY=your-secret-key
```

Without these, CC3D falls back to local installation or returns simulation briefs only.

## Deploy to Streamlit Cloud

1. Fork this repo
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your fork, set `app.py` as main file
4. Add secrets:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   OPENAI_API_KEY = "sk-..."
   # Optional — CC3D cloud
   CC3D_API_URL = "http://YOUR_VPS_IP:8001"
   CC3D_API_KEY = "your-secret-key"
   ```

## Key References

- Nichol et al. Biomaterials 2010 — GelMA stiffness calibration (Flory-Rehner)
- Ouyang et al. Adv Mater 2016 — printability window (Herschel-Bulkley)
- Nasralla et al. Nature 2018 — VITTAL NMP trial
- Mergental et al. Nat Med 2020 — PILOT viability criteria
- Olthoff et al. Liver Transplantation 2010 — EAD definition

## Stack

- Python 3.13, uv
- Streamlit (UI), LangChain + Anthropic (chat/RAG), ChromaDB (vectors)
- OpenAI text-embedding-3-small (embeddings)
- scikit-fem (FEA), Plotly (charts), kaleido (export)
