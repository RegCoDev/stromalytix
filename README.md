# Stromalytix

Biological Process Intelligence platform for precision medicine — connecting CRM/ERP/ELN/LIMS data with biophysical simulation to predict outcomes before experiments run.

## Quick Start (Local)

```bash
# Install uv (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/RegCoDev/stromalytix.git
cd stromalytix
uv sync

# Set up environment
cp .env.example .env  # Add your ANTHROPIC_API_KEY and OPENAI_API_KEY

# Scrape and embed knowledge base
uv run python scripts/scrape_pubmed.py
uv run python scripts/embed_and_index.py

# Run the app
uv run streamlit run app.py
```

## Deploy to Streamlit Cloud

1. Fork this repo
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your fork, set `app.py` as main file
4. Add secrets: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`

## Architecture

```
Layer 1 (Ingestion): CRM/ERP/ELN/LIMS/instruments → ProcessEvents
Layer 2 (Process Mining): PM4Py + biological extensions → KPIs
Layer 3 (Simulation): CC3D/scikit-fem → predictions
```

## Tests

```bash
uv run pytest tests/ -v --tb=short
```
