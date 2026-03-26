# Stromalytix

Cell-ECM modeling for **biofabrication**: how cells adhere, migrate, and proliferate on bioinks, scaffolds, and engineered matrices. Literature-grounded benchmarks, optional CompuCell3D cloud runs, and scaffold geometry preview. Covers tissue engineering and cellular agriculture use cases.

## What It Does

Chat-driven construct assessment for biofabrication workflows: PubMed RAG, FEA scaffold mechanics, optional CC3D cloud simulation, and scaffold preview. Describe your 3D cell culture protocol through a guided conversation. Stromalytix queries ~8,100 PubMed abstracts, synthesizes a variance report with PMID-cited risk analysis, and generates a CC3D simulation brief for your construct.

**You get:**
- Radar chart showing protocol deviation across key parameters
- Risk scorecard with color-coded risk flags
- AI narrative citing specific PMIDs from the literature
- Parameter scatter plot comparing your construct to published ranges
- CC3D simulation brief predicting cell organization and failure modes
- FEA scaffold mechanics (deformation, strain, failure risk)
- Scaffold geometry preview and CC3D VTK output (when cloud sidecar is configured)
- PDF variance report

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
uv run python scripts/embed_public_data.py    # calibration benchmarks

# Run the app
uv run streamlit run app.py
```

## Tests

```bash
uv run pytest tests/ -v --tb=short
```

## Architecture

```
Layer 2 — Simulation & Prediction
  CC3D (cell-ECM interaction simulation)  |  scikit-fem (FEA scaffold mechanics)
  Simulation brief generation  |  Scaffold preview + CC3D visualization

Layer 1 — Knowledge & Data
  PubMed RAG (~8,100 abstracts)  |  ChromaDB vector search
  Protocol ingestion (PDF/DOCX/TXT)  |  Literature benchmarks
```

## ChromaDB Collections

| Collection | Docs | Content |
|-----------|------|---------|
| `stromalytix_kb` | ~8,100 | PubMed abstracts for RAG |
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

Without `CC3D_API_URL` / `CC3D_API_KEY`, the app still generates simulation briefs; the **Run CC3D** button stays disabled until the sidecar is configured.

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

## Archive

Previous modules (Process Intelligence, Materials Intelligence, Transplant PI,
partner white-label, and supporting modules) are preserved in `archive/v0.1.0-pre-pivot/`.
See `CHANGELOG.md` for the full history.

## Stack

- Python 3.13, uv
- Streamlit (UI), LangChain + Anthropic (chat/RAG), ChromaDB (vectors)
- OpenAI text-embedding-3-small (embeddings)
- scikit-fem (FEA), Plotly (charts), kaleido (export)

## Full deployment guide

See [DEPLOY.md](DEPLOY.md) for Hostinger VPS, Docker, firewall, and TLS.
