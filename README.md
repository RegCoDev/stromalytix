# Stromalytix

Software and robots for designing, simulating and manufacturing engineered tissues, in development. The broader goal spans tissues and biomaterials; liver is the first demonstration. Biofab Box is the planned hardware component.

[Watch the prototype and inspect its evidence](https://regco.tech/stromalytix) · [Open the public reference library](https://stromalytix.streamlit.app)

## What It Does

The public `app.py` entry point is a research prototype:

| Surface | Availability |
| --- | --- |
| Parameter Library | Bundled reference entries, search, source links and model-estimate derivations; no model account required. Counts are calculated from the bundled snapshot. |
| Protocol Explorer | Requires a connected Knowledge Vault service. When unavailable, the app links to the recorded evidence workflow. |
| Construct Assessment | Starts only when requested and needs a supported model provider. Outputs are literature-based hypotheses, not experimental validation. |
| Simulation & exports | CC3D and FEA execution are not exposed by this public entry point. Repository modules and optional service code do not establish deployed capabilities. |
| Current recorded proof | A source-linked liver-study workflow, a separate saved oxygen-transport calculation, proposed lab verification and a clearly labeled hardware concept, available at the demo link above. |

The oxygen calculation is a computational prediction. Printer conversion, physical measurements, cell viability and tissue-function validation remain next steps.

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
  Literature benchmarks  |  ChromaDB vector search
  Protocol ingestion (PDF/DOCX/TXT)  |  Literature benchmarks
```

## ChromaDB Collections

| Collection | Content |
|-----------|---------|
| `stromalytix_kb` | Literature corpus for retrieval, when configured |
| `calibration_benchmarks` | Literature benchmarks with DOIs |

Counts depend on the deployment's indexed snapshot. Rebuild with `scripts/embed_and_index.py` and `scripts/embed_public_data.py`; repository code alone does not establish a live corpus size.

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

These settings configure the optional service integration. The current public `app.py` does not expose a working CC3D execution button; its simulation tab links to the separate saved oxygen calculation and verification plan.

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
