"""
Stromalytix — Bioengineering Protocol Intelligence

Public-facing Streamlit app with four tabs:
  1. Parameter Library (default) — works without any API key
  2. Protocol Explorer — needs vault API
  3. Assessment — needs vault API + LLM key
  4. About
"""

import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Stromalytix | Bioengineering Protocol Intelligence",
    page_icon="\U0001f9ec",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS — dark theme with emerald accent
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Dark theme */
    body {
        background-color: #0a0a0a;
        color: #e0e0e0;
    }

    .stApp {
        background-color: #0a0a0a;
    }

    /* Chat messages */
    .stChatMessage {
        background-color: #111111 !important;
        border: 1px solid #222222;
    }

    /* Buttons */
    .stButton>button {
        border: 1px solid #34d399;
        color: #34d399;
        background: transparent;
        font-weight: 500;
        transition: all 0.3s ease;
    }

    .stButton>button:hover {
        background: #34d399;
        color: #000000;
    }

    /* Metric cards */
    [data-testid="stMetricValue"] {
        background-color: #111111;
        border: 1px solid #222222;
        padding: 1rem;
        border-radius: 0.5rem;
    }

    /* Containers */
    .narrative-container {
        background-color: #111111;
        border: 1px solid #222222;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }

    /* Headers */
    h1, h2, h3 {
        color: #e0e0e0;
    }

    /* Accent color for brand */
    .brand-text {
        color: #34d399;
        font-weight: bold;
    }

    /* Hero stat cards */
    .stat-card {
        background: #111111;
        border: 1px solid #222222;
        border-radius: 0.75rem;
        padding: 1.25rem;
        text-align: center;
    }
    .stat-card .stat-num {
        font-size: 2rem;
        font-weight: 700;
        color: #34d399;
    }
    .stat-card .stat-label {
        font-size: 0.85rem;
        color: #888;
        margin-top: 0.25rem;
    }

    /* Protocol card */
    .protocol-card {
        background: #111111;
        border: 1px solid #222222;
        border-radius: 0.5rem;
        padding: 1rem 1.25rem;
        margin-bottom: 0.5rem;
    }
    .protocol-card .proto-title {
        color: #34d399;
        font-weight: 600;
    }

    /* DOI link styling */
    a.doi-link {
        color: #34d399 !important;
        text-decoration: none;
    }
    a.doi-link:hover {
        text-decoration: underline;
    }

    /* Badge */
    .badge-pro {
        display: inline-block;
        background: linear-gradient(135deg, #34d399, #059669);
        color: #000;
        font-size: 0.7rem;
        font-weight: 700;
        padding: 0.2rem 0.6rem;
        border-radius: 1rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Vault status dot */
    .vault-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 6px;
    }
    .vault-dot.on  { background: #34d399; }
    .vault-dot.off { background: #ef4444; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Vault API helpers
# ---------------------------------------------------------------------------

def _secret(name: str, default: str = "") -> str:
    """Read from Streamlit secrets first, then env, then default."""
    try:
        return st.secrets[name]
    except Exception:
        return os.getenv(name, default)


def get_vault_url() -> str:
    return _secret("VAULT_API_URL", "").rstrip("/")


def get_vault_key() -> str:
    return _secret("VAULT_API_KEY", "")


def _vault_headers() -> dict:
    key = get_vault_key()
    h = {"Content-Type": "application/json"}
    if key:
        h["X-API-Key"] = key
    return h


def vault_get(path: str, params: dict | None = None, timeout: float = 15.0):
    """GET request to vault API. Returns parsed JSON or None on failure."""
    url = get_vault_url()
    if not url:
        return None
    try:
        resp = httpx.get(f"{url}{path}", headers=_vault_headers(), params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def vault_post(path: str, payload: dict, timeout: float = 15.0):
    """POST request to vault API. Returns parsed JSON or None on failure."""
    url = get_vault_url()
    if not url:
        return None
    try:
        resp = httpx.post(f"{url}{path}", headers=_vault_headers(), json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


@st.cache_data(ttl=60)
def check_vault_health() -> bool:
    url = get_vault_url()
    if not url:
        return False
    try:
        resp = httpx.get(f"{url}/health", timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

@st.cache_data
def load_parameters() -> list[dict]:
    """Load the static parameter export (works without any API key)."""
    p = Path(__file__).parent / "data" / "parameters_export.json"
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return []


@st.cache_data(ttl=300)
def fetch_protocols(
    tissue_type: str | None = None,
    biofab_method: str | None = None,
    material: str | None = None,
    cell_type: str | None = None,
    confidence: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict | None:
    params = {"limit": limit, "offset": offset}
    if tissue_type:
        params["tissue_type"] = tissue_type
    if biofab_method:
        params["biofab_method"] = biofab_method
    if material:
        params["material"] = material
    if cell_type:
        params["cell_type"] = cell_type
    if confidence:
        params["confidence"] = confidence
    return vault_get("/protocols", params=params)


@st.cache_data(ttl=300)
@st.cache_data(ttl=600)
def fetch_protocol_detail(protocol_id: int) -> dict | None:
    return vault_get(f"/protocols/{protocol_id}")


@st.cache_data(ttl=3600)
def fetch_protocol_stats() -> dict | None:
    return vault_get("/protocols/stats")


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def save_signup(email: str):
    """Save email signup to CSV."""
    csv_path = Path("signups.csv")
    timestamp = datetime.now().isoformat()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, email])


def _doi_url(doi: str) -> str:
    """Convert a DOI string to a full URL."""
    if not doi:
        return ""
    doi = doi.strip()
    if doi.startswith("http"):
        return doi
    return f"https://doi.org/{doi}"


def _source_url(p: dict) -> str:
    """Get the best available source URL — DOI first, then PMID link."""
    doi = p.get("doi") or ""
    if doi:
        return _doi_url(doi)
    pmid = p.get("pmid") or ""
    if pmid:
        return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    return ""


def _source_label(source: str) -> str:
    """Clean up source display text."""
    labels = {
        "literature": "Literature",
        "model_estimate": "Model Estimate",
        "curated": "Literature",
        "auto_extracted": "Literature",
    }
    return labels.get(source, source.replace("_", " ").title() if source else "-")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<h2 style="margin-bottom:0"><span style="color:#34d399">&#x1F9EC;</span> Stromalytix</h2>',
        unsafe_allow_html=True,
    )
    st.caption("Bioengineering Protocol Intelligence")
    st.divider()

    # Vault connection status
    vault_ok = check_vault_health()
    dot_cls = "on" if vault_ok else "off"
    dot_label = "Connected" if vault_ok else "Offline"
    st.markdown(
        f'<span class="vault-dot {dot_cls}"></span> Knowledge Vault: **{dot_label}**',
        unsafe_allow_html=True,
    )

    # Quick stats
    params_data = load_parameters()
    lit_count = sum(1 for p in params_data if p.get("source") == "literature")
    est_count = sum(1 for p in params_data if p.get("source") == "model_estimate")
    st.caption(f"{len(params_data)} parameters ({lit_count} literature-backed, {est_count} model estimates)")
    if vault_ok:
        stats = fetch_protocol_stats()
        if stats:
            st.caption(f"{stats.get('total_protocols', 0)} extracted protocols")

    st.divider()
    st.markdown(
        '<p style="color:#555;font-size:0.75rem;">Built by <strong>K-Dense</strong></p>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main content — four tabs
# ---------------------------------------------------------------------------

tab_params, tab_protocols, tab_assessment, tab_about = st.tabs(
    ["Parameter Library", "Protocol Explorer", "Assessment", "About"]
)


# =====================================================================
# TAB 1 - Parameter Library (landing page, works without API key)
# Redesigned 2026-04-29: progressive disclosure (index -> category -> row).
# First-time visitor lands on category cards, not a 261-row table dump.
# =====================================================================

@st.cache_data
def load_derivations() -> dict:
    p = Path(__file__).parent / "data" / "parameter_derivations.json"
    if p.exists():
        with open(p) as f:
            d = json.load(f)
        return {k: v for k, v in d.items() if not k.startswith("_")}
    return {}


_PARAM_CAT_LABELS = {
    "adhesion": "Cell Adhesion",
    "culture_conditions": "Culture Conditions",
    "fabrication": "Fabrication",
    "gel_penetration": "Migration & Gel Penetration",
    "o2_transport": "Oxygen Transport",
    "proliferation": "Proliferation",
    "scaffold_materials": "Scaffold Materials",
}

_PARAM_CAT_BLURBS = {
    "adhesion": "Homotypic and heterotypic adhesion energies for CC3D-style cellular Potts simulations and lab calibration.",
    "culture_conditions": "Standard medium, supplement, and incubation parameters used as defaults across protocols.",
    "fabrication": "Crosslinking, photopolymerization, and post-print curing parameters.",
    "gel_penetration": "Cell migration speeds, persistence, and gel-penetration depths under varying matrix stiffness.",
    "o2_transport": "Oxygen consumption rates, diffusion coefficients, and tissue-scale transport limits.",
    "proliferation": "Doubling times, growth rates, and cell-cycle parameters across the most-cited cell lines.",
    "scaffold_materials": "Mechanical, swelling, degradation, and porosity parameters for hydrogels and ECM analogs.",
}


def _render_paramlib_header(all_params: list, derivations: dict) -> None:
    lit = sum(1 for p in all_params if p.get("source") == "literature")
    est = sum(1 for p in all_params if p.get("source") == "model_estimate")
    high_conf = sum(1 for p in all_params if (p.get("confidence") or "").lower() == "high")
    st.markdown("### Parameter Library")
    st.caption(
        "An open, citable reference of bioengineering constants for tissue-engineering, "
        "organ-on-chip, and microphysiological-system models. Contributed to the field; "
        "feedback and corrections welcome."
    )
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Parameters", f"{len(all_params)}")
    mc2.metric("Literature-backed", f"{lit}")
    mc3.metric(
        "Model estimates",
        f"{est}",
        help="Each model-estimate entry has a structured derivation: method, basis, assumptions, uncertainty range, invalidating conditions.",
    )
    mc4.metric("High confidence", f"{high_conf}")


def _render_category_cards(all_params: list) -> None:
    cats = {}
    for p in all_params:
        k = p.get("table_name") or "other"
        c = cats.setdefault(k, {"total": 0, "high": 0, "est": 0})
        c["total"] += 1
        if (p.get("confidence") or "").lower() == "high":
            c["high"] += 1
        if p.get("source") == "model_estimate":
            c["est"] += 1

    ordered = sorted(cats.items(), key=lambda kv: -kv[1]["total"])
    st.markdown("#### Browse by category")
    for row_start in range(0, len(ordered), 3):
        row = ordered[row_start:row_start + 3]
        cols = st.columns(3)
        for col, (key, stats) in zip(cols, row):
            with col:
                label = _PARAM_CAT_LABELS.get(key, key.replace("_", " ").title())
                blurb = _PARAM_CAT_BLURBS.get(key, "")
                t = stats["total"]
                h = stats["high"]
                e = stats["est"]
                meta_bits = [f"{t} parameters", f"{h} high-confidence"]
                if e:
                    meta_bits.append(f"{e} model estimates")
                meta_html = " &middot; ".join(meta_bits)
                card_html = (
                    f'<div style="background:#111111;border:1px solid #222222;border-radius:0.5rem;'
                    f'padding:1rem 1.1rem;margin-bottom:0.5rem;min-height:150px;">'
                    f'<div style="color:#34d399;font-weight:600;font-size:1.05rem;margin-bottom:0.35rem;">{label}</div>'
                    f'<div style="color:#888;font-size:0.78rem;margin-bottom:0.5rem;'
                    f"font-family:'JetBrains Mono',monospace;\">{meta_html}</div>"
                    f'<div style="color:#bbb;font-size:0.85rem;line-height:1.35;">{blurb}</div>'
                    f'</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)
                if st.button(f"Browse {label}", key=f"paramlib_open_{key}", use_container_width=True):
                    st.session_state["paramlib_view"] = f"category:{key}"
                    st.session_state.pop("paramlib_selected_id", None)
                    st.rerun()


def _render_param_table(rows: list, key_prefix: str) -> None:
    if not rows:
        st.info("No parameters match your current filters. Try broadening your search.")
        return
    df_rows = []
    for p in rows:
        df_rows.append({
            "ID": p.get("id", ""),
            "Parameter": p.get("parameter", ""),
            "Value": p.get("value", ""),
            "Unit": p.get("unit", ""),
            "Material": p.get("material") or "-",
            "Cell Type": p.get("cell_type") or "-",
            "Conditions": p.get("conditions") or "-",
            "Confidence": (p.get("confidence") or "").title(),
            "Reference": _source_url(p),
            "Source": _source_label(p.get("source", "")),
        })
    df = pd.DataFrame(df_rows)
    st.dataframe(
        df,
        column_config={
            "ID": st.column_config.TextColumn("ID", width="small"),
            "Reference": st.column_config.LinkColumn(
                "Reference",
                display_text=r"https://(?:doi\.org/|pubmed\.ncbi\.nlm\.nih\.gov/)(.+?)/?$",
                help="Open publication (DOI or PubMed)",
            ),
            "Value": st.column_config.NumberColumn("Value", format="%.4g"),
            "Confidence": st.column_config.TextColumn("Confidence", width="small"),
            "Source": st.column_config.TextColumn("Source", width="small"),
        },
        use_container_width=True,
        hide_index=True,
        height=min(560, 80 + 35 * max(1, len(rows))),
    )

    est_rows = [p for p in rows if p.get("source") == "model_estimate"]
    if est_rows:
        st.markdown("##### Inspect a model-estimate derivation")
        st.caption(
            "Each model estimate has a structured derivation: method, basis, assumptions, "
            "uncertainty range, and conditions that would invalidate it."
        )
        opts = ["(select an entry)"]
        for p in est_rows:
            tag = p.get("material") or p.get("cell_type") or "-"
            opts.append(f"{p['id']} - {p.get('parameter','')} ({tag})")
        chosen = st.selectbox(
            "Model-estimate entry",
            opts,
            key=f"{key_prefix}_est_picker",
            label_visibility="collapsed",
        )
        if chosen and not chosen.startswith("("):
            sel_id = chosen.split(" - ", 1)[0].strip()
            _render_derivation_panel(sel_id, est_rows)


def _render_derivation_panel(sel_id: str, est_rows: list) -> None:
    derivations = load_derivations()
    deriv = derivations.get(sel_id)
    entry = next((p for p in est_rows if p.get("id") == sel_id), None)
    e_param = (entry or {}).get("parameter", "")
    e_value = (entry or {}).get("value", "")
    e_unit = (entry or {}).get("unit", "")
    panel_html = (
        '<div style="background:#0e1a14;border:1px solid #1f3a2c;border-left:3px solid #34d399;'
        'border-radius:0.5rem;padding:1rem 1.25rem;margin-top:0.75rem;">'
        '<div style="color:#34d399;font-weight:600;font-size:0.95rem;margin-bottom:0.25rem;'
        "font-family:'JetBrains Mono',monospace;\">"
        f'{sel_id}</div>'
        '<div style="color:#e0e0e0;font-size:1.05rem;font-weight:500;">'
        f'{e_param} = <span style="color:#34d399">{e_value} {e_unit}</span></div>'
        '</div>'
    )
    st.markdown(panel_html, unsafe_allow_html=True)

    if not deriv:
        st.caption("No structured derivation on file for this entry.")
        return

    method = (deriv.get("method") or "").replace("_", " ").title()
    st.markdown(f"**Method.** {method}")
    if deriv.get("basis"):
        st.markdown(f"**Basis.** {deriv['basis']}")
    if deriv.get("uncertainty_range"):
        st.markdown(f"**Uncertainty range.** {deriv['uncertainty_range']}")
    for label, key in [("Assumptions", "assumptions"),
                       ("Invalidating conditions", "invalidating_conditions"),
                       ("Supporting literature", "supporting_lit")]:
        items = deriv.get(key) or []
        if items:
            st.markdown(f"**{label}.**")
            for a in items:
                st.markdown(f"- {a}")


with tab_params:
    all_params = load_parameters()
    if not all_params:
        st.markdown("### Parameter Library")
        st.warning(
            "Parameter data not found. Ensure `data/parameters_export.json` is present in the repository."
        )
    else:
        derivations = load_derivations()
        if "paramlib_view" not in st.session_state:
            st.session_state["paramlib_view"] = "index"

        _render_paramlib_header(all_params, derivations)

        prev_search = st.session_state.get("paramlib_search_prev", "")
        search_text = st.text_input(
            "Search across name / material / cell type / conditions / DOI",
            placeholder="e.g. collagen stiffness, GelMA porosity, HUVEC O2 uptake ...",
            key="param_search",
        )
        if search_text and search_text != prev_search:
            st.session_state["paramlib_view"] = "search"
        st.session_state["paramlib_search_prev"] = search_text

        nav_cols = st.columns([1, 1, 4])
        with nav_cols[0]:
            if st.session_state["paramlib_view"] != "index":
                if st.button("All categories", key="paramlib_back_to_index"):
                    st.session_state["paramlib_view"] = "index"
                    st.session_state.pop("paramlib_selected_id", None)
                    st.rerun()
        with nav_cols[1]:
            if st.session_state["paramlib_view"] != "all":
                if st.button("View full table", key="paramlib_view_all"):
                    st.session_state["paramlib_view"] = "all"
                    st.rerun()

        st.divider()
        view = st.session_state["paramlib_view"]

        def _apply_search(rows: list, q: str) -> list:
            if not q:
                return rows
            ql = q.lower()
            return [
                p for p in rows
                if ql in (p.get("parameter") or "").lower()
                or ql in (p.get("material") or "").lower()
                or ql in (p.get("cell_type") or "").lower()
                or ql in (p.get("conditions") or "").lower()
                or ql in (p.get("notes") or "").lower()
                or ql in (p.get("table_name") or "").lower()
                or ql in (p.get("doi") or "").lower()
            ]

        if view == "index":
            _render_category_cards(all_params)
            with st.expander("How this library is built"):
                st.markdown(
                    "- **Literature parameters** (222) are extracted from primary "
                    "publications. Each entry links to its DOI or PubMed identifier."
                )
                st.markdown(
                    "- **Model estimates** (39) are derived where direct measurements "
                    "are unavailable. Every estimate carries a structured derivation: "
                    "method, basis, assumptions, uncertainty range, and conditions that "
                    "would invalidate the estimate."
                )
                st.markdown(
                    "- **Confidence labels** are assigned during curation. High = direct "
                    "measurement under standard conditions in the cited paper. Medium = "
                    "supported by the cited source but with notable extrapolation. Low = "
                    "preliminary or single-study."
                )
                st.markdown(
                    "- **Coverage gaps and corrections welcome.** This is a contribution "
                    "to the field; the goal is to be useful, not comprehensive on day one."
                )

            with st.expander("Cite this resource"):
                bib = (
                    "@misc{stromalytix2026params,\n"
                    "  title   = {Stromalytix Parameter Library: Curated Bioengineering Constants},\n"
                    "  year    = {2026},\n"
                    "  note    = {261 parameters with DOI provenance across scaffold materials,\n"
                    "             cell adhesion, proliferation, oxygen transport, migration, fabrication},\n"
                    "  url     = {https://stromalytix.streamlit.app}\n"
                    "}"
                )
                st.code(bib, language="bibtex")

        elif view == "search":
            results = _apply_search(all_params, search_text)
            st.markdown(f"**{len(results)}** parameters match \"{search_text}\"")
            _render_param_table(results, key_prefix="paramlib_search")

        elif view.startswith("category:"):
            cat_key = view.split(":", 1)[1]
            cat_label = _PARAM_CAT_LABELS.get(cat_key, cat_key.replace("_", " ").title())
            cat_rows = [p for p in all_params if p.get("table_name") == cat_key]
            if search_text:
                cat_rows = _apply_search(cat_rows, search_text)
            high = sum(1 for p in cat_rows if (p.get("confidence") or "").lower() == "high")
            med = sum(1 for p in cat_rows if (p.get("confidence") or "").lower() == "medium")
            low = sum(1 for p in cat_rows if (p.get("confidence") or "").lower() == "low")
            est = sum(1 for p in cat_rows if p.get("source") == "model_estimate")

            st.markdown(f"#### {cat_label}")
            st.caption(_PARAM_CAT_BLURBS.get(cat_key, ""))
            stat_html = (
                "<div style=\"color:#888;font-size:0.85rem;"
                "font-family:'JetBrains Mono',monospace;\">"
                f"{len(cat_rows)} parameters &middot; {high} high &middot; {med} medium &middot; "
                f"{low} low &middot; {est} model estimates"
                "</div>"
            )
            st.markdown(stat_html, unsafe_allow_html=True)

            mats = sorted({p.get("material") for p in cat_rows if p.get("material")})
            cells = sorted({p.get("cell_type") for p in cat_rows if p.get("cell_type")})
            confs = ["High", "Medium", "Low"]

            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                sel_mat = st.selectbox("Material", ["All"] + mats, key=f"paramlib_cat_mat_{cat_key}")
            with fc2:
                sel_cell = st.selectbox("Cell Type", ["All"] + cells, key=f"paramlib_cat_cell_{cat_key}")
            with fc3:
                sel_conf = st.selectbox("Confidence", ["All"] + confs, key=f"paramlib_cat_conf_{cat_key}")

            filt = cat_rows
            if sel_mat != "All":
                filt = [p for p in filt if p.get("material") == sel_mat]
            if sel_cell != "All":
                filt = [p for p in filt if p.get("cell_type") == sel_cell]
            if sel_conf != "All":
                filt = [p for p in filt if (p.get("confidence") or "").lower() == sel_conf.lower()]

            _render_param_table(filt, key_prefix=f"paramlib_cat_{cat_key}")

        elif view == "all":
            rows = _apply_search(all_params, search_text)
            st.markdown(f"#### Full table - {len(rows)} parameters")
            st.caption(
                "All parameters in one view. Use the search box above or the category cards "
                "on the index for a guided entry."
            )

            mats = sorted({p.get("material") for p in rows if p.get("material")})
            cells = sorted({p.get("cell_type") for p in rows if p.get("cell_type")})
            cats = sorted({p.get("table_name") for p in rows if p.get("table_name")})
            confs = ["High", "Medium", "Low"]

            fc1, fc2, fc3, fc4 = st.columns(4)
            with fc1:
                sel_cat_label = st.selectbox(
                    "Category",
                    ["All"] + [_PARAM_CAT_LABELS.get(c, c.replace("_", " ").title()) for c in cats],
                    key="paramlib_all_cat",
                )
            with fc2:
                sel_mat = st.selectbox("Material", ["All"] + mats, key="paramlib_all_mat")
            with fc3:
                sel_cell = st.selectbox("Cell Type", ["All"] + cells, key="paramlib_all_cell")
            with fc4:
                sel_conf = st.selectbox("Confidence", ["All"] + confs, key="paramlib_all_conf")

            if sel_cat_label != "All":
                rev = {v: k for k, v in _PARAM_CAT_LABELS.items()}
                cat_key = rev.get(sel_cat_label, sel_cat_label.lower().replace(" ", "_"))
                rows = [p for p in rows if p.get("table_name") == cat_key]
            if sel_mat != "All":
                rows = [p for p in rows if p.get("material") == sel_mat]
            if sel_cell != "All":
                rows = [p for p in rows if p.get("cell_type") == sel_cell]
            if sel_conf != "All":
                rows = [p for p in rows if (p.get("confidence") or "").lower() == sel_conf.lower()]

            _render_param_table(rows, key_prefix="paramlib_all")


# TAB 2 — Protocol Explorer
# =====================================================================

with tab_protocols:
    st.markdown("### Protocol Explorer")
    st.caption("Search and browse extracted tissue engineering protocols")

    if not vault_ok:
        st.warning(
            "Protocol Explorer requires the Knowledge Vault service. "
            "Configure `VAULT_API_URL` and `VAULT_API_KEY` in your environment or Streamlit secrets."
        )
        st.info("The Knowledge Vault indexes 396 protocols extracted from PubMed full-text articles, "
                "each decomposed into structured steps with materials, cell types, parameters, and outcomes.")
    else:
        # Stats row — show Protocols + Tissue Types (steps + parameters are noisy for buyers)
        stats = fetch_protocol_stats()
        if stats:
            sc1, sc2 = st.columns(2)
            with sc1:
                st.metric("Protocols", stats.get("total_protocols", 0))
            with sc2:
                tissues = stats.get("by_tissue", {})
                st.metric("Tissue Types", len(tissues))

        st.divider()

        # Filters
        fc1, fc2, fc3 = st.columns(3)

        tissue_options = ["All"]
        biofab_options = ["All"]
        conf_options = ["All", "High", "Medium", "Low"]

        # Merge "bioprinted" / "bioprinting" / "extrusion_bioprinting" into a single
        # "bioprinting" category — they're the same protocol family. Same for any
        # variants the vault returns separately.
        _BIOFAB_MERGE = {
            "bioprinted": "bioprinting",
            "bioprinting": "bioprinting",
            "extrusion_bioprinting": "bioprinting",
            "dlp_bioprinting": "bioprinting",
            "extrusion bioprinting": "bioprinting",
            "dlp bioprinting": "bioprinting",
        }

        def _normalize_biofab(name: str) -> str:
            n = (name or "").strip().lower()
            return _BIOFAB_MERGE.get(n, n)

        if stats:
            tissue_options += sorted(stats.get("by_tissue", {}).keys())
            # De-dup biofab keys via the merge map
            raw_biofab = list((stats.get("by_biofab") or {}).keys())
            biofab_options += sorted({_normalize_biofab(b) for b in raw_biofab if b})

        with fc1:
            sel_tissue = st.selectbox("Tissue Type", tissue_options, key="proto_tissue")
        with fc2:
            sel_biofab = st.selectbox("Biofabrication Method", biofab_options, key="proto_biofab")
        with fc3:
            sel_conf = st.selectbox("Confidence", conf_options, key="proto_conf")

        # Fetch protocols
        tissue_arg = sel_tissue if sel_tissue != "All" else None
        biofab_arg = sel_biofab if sel_biofab != "All" else None
        conf_arg = sel_conf.lower() if sel_conf != "All" else None

        # If the user picks the merged "bioprinting" category, we need to fetch
        # all underlying variants. Run the request once per variant and combine.
        if biofab_arg == "bioprinting":
            variants = ["bioprinting", "bioprinted", "extrusion_bioprinting", "dlp_bioprinting"]
            combined = []
            seen_ids = set()
            for v in variants:
                r = fetch_protocols(tissue_type=tissue_arg, biofab_method=v,
                                    confidence=conf_arg, limit=50)
                for p in (r or {}).get("protocols", []) or []:
                    if p.get("id") not in seen_ids:
                        seen_ids.add(p.get("id"))
                        combined.append(p)
            result = {"protocols": combined[:50], "total": len(combined)}
        else:
            result = fetch_protocols(
                tissue_type=tissue_arg,
                biofab_method=biofab_arg,
                confidence=conf_arg,
                limit=50,
            )

        if result and result.get("protocols"):
            protocols = result["protocols"]
            total = result.get("total", len(protocols))
            st.markdown(f"Showing **{len(protocols)}** of **{total}** protocols")

            for proto in protocols:
                pid = proto.get("id", "?")
                pmid = proto.get("source_pmid", "N/A")
                title = proto.get("paper_title") or f"Protocol {pid}"
                tissue = proto.get("target_tissue") or "-"
                biofab = _normalize_biofab(proto.get("biofab_method") or "-") or "-"
                conf = (proto.get("confidence") or "low").title()
                extr = proto.get("extraction_method") or "regex"

                pmid_link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid and pmid != "N/A" else ""
                with st.expander(
                    f"**{title[:80]}** | {tissue} | {biofab} | {conf}"
                ):
                    mc1, mc2, mc3, mc4 = st.columns(4)
                    mc1.markdown(f"**PMID:** [{pmid}]({pmid_link})" if pmid_link else f"**PMID:** {pmid}")
                    mc2.markdown(f"**Tissue:** {tissue}")
                    mc3.markdown(f"**Method:** {biofab}")
                    mc4.markdown(f"**Extraction:** {extr}")

                    # Load protocol detail directly (cached)
                    detail = fetch_protocol_detail(pid)
                    if detail and detail.get("steps"):
                        # Section-header prefixes that PubMed full-text extraction often
                        # leaves attached to the first step's description — strip them.
                        _SECTION_PREFIX_RE = re.compile(
                            r"^\s*(materials\s+and\s+methods?|methods?|materials|"
                            r"experimental\s+(procedures?|methods?|section)|"
                            r"procedure|protocol)\s*[:\.\-]?\s*",
                            re.IGNORECASE,
                        )

                        def _clean_desc(text: str) -> str:
                            if not text:
                                return ""
                            t = text.strip()
                            # Strip section header up to 3x (catches "Methods Materials and Methods Procedure")
                            for _ in range(3):
                                t2 = _SECTION_PREFIX_RE.sub("", t).lstrip()
                                if t2 == t:
                                    break
                                t = t2
                            # Collapse internal whitespace
                            t = re.sub(r"\s+", " ", t)
                            return t

                        for step in detail["steps"]:
                            seq = step.get("seq", "?")
                            action = step.get("action_type") or ""
                            desc = _clean_desc(step.get("description", ""))
                            dur = step.get("duration") or ""
                            temp = step.get("temperature") or ""

                            # Skip steps that are pure-unknown noise (no action, no description)
                            if (action == "" or action.lower() == "unknown") and not desc:
                                continue

                            # "Unknown" action_type → render as generic "Procedure step"
                            if not action or action.lower() == "unknown":
                                action_label = "Procedure step"
                            else:
                                action_label = action.replace("_", " ").title()

                            step_header = f"**Step {seq}: {action_label}**"
                            if dur:
                                step_header += f" ({dur})"
                            if temp:
                                step_header += f" @ {temp}"
                            st.markdown(step_header)
                            if desc:
                                st.markdown(desc[:300] + ("…" if len(desc) > 300 else ""))

                            # Materials
                            mats = step.get("materials", [])
                            if mats:
                                mat_strs = []
                                for m in mats:
                                    s = m.get("material_name", "")
                                    if m.get("concentration"):
                                        s += f" ({m['concentration']})"
                                    mat_strs.append(s)
                                st.caption(f"Materials: {', '.join(mat_strs)}")

                            # Cells
                            cells = step.get("cells", [])
                            if cells:
                                cell_strs = []
                                for c in cells:
                                    s = c.get("cell_type", "")
                                    if c.get("density"):
                                        s += f" @ {c['density']}"
                                    cell_strs.append(s)
                                st.caption(f"Cells: {', '.join(cell_strs)}")

                            # Parameters
                            step_params = step.get("parameters", [])
                            if step_params:
                                for sp in step_params:
                                    name = sp.get("parameter_name", "")
                                    val = sp.get("value", "")
                                    unit = sp.get("unit", "")
                                    st.caption(f"  {name}: {val} {unit}")

                            st.markdown("---")
                    elif detail:
                        st.info("Protocol loaded but contains no steps.")
                    else:
                        st.warning("Expand to load protocol details.")

        elif result is not None:
            st.info("No protocols match the current filters.")
        else:
            st.error("Failed to fetch protocols from the vault.")


# =====================================================================
# TAB 3 — Assessment
# =====================================================================

with tab_assessment:
    st.markdown("### Construct Assessment")
    st.caption("AI-powered analysis of your 3D culture protocol")

    # Check for LLM key (any working provider — OpenRouter primary, Anthropic legacy)
    anthropic_key = _secret("ANTHROPIC_API_KEY", "")
    openrouter_key = _secret("OPENROUTER_API_KEY", "")
    litellm_key = _secret("LITELLM_MASTER_KEY", "")
    has_llm = bool(anthropic_key or openrouter_key or litellm_key)

    if not has_llm:
        st.markdown(
            """
            The Assessment module uses AI to analyze your tissue engineering construct against
            published protocols, generating:

            - **Feasibility scoring** with literature-backed risk flags
            - **Parameter benchmarking** against curated ranges
            - **Methods & materials plan** with specific recommendations

            ---
            """
        )

        st.info("Assessment requires an AI model. Contact us for access or configure your API key.")

        st.markdown("#### Get notified when public access launches")
        with st.form("assessment_signup"):
            email = st.text_input("Email address", placeholder="you@university.edu")
            submitted = st.form_submit_button("Notify me")
            if submitted and email:
                save_signup(email)
                st.success("You're on the list. We'll reach out when public assessment is live.")

        st.divider()

        # Show what Pro features look like
        st.markdown("#### Pro Features Preview")
        pc1, pc2 = st.columns(2)
        with pc1:
            st.markdown(
                '<div class="narrative-container">'
                '<strong>CompuCell3D Simulation</strong> '
                '<span class="badge-pro">Pro -- Coming Soon</span>'
                '<br><br>Run agent-based 3D cell simulations of your construct. '
                'Predict cell migration, proliferation dynamics, and mechanical behavior.'
                '</div>',
                unsafe_allow_html=True,
            )
        with pc2:
            st.markdown(
                '<div class="narrative-container">'
                '<strong>Finite Element Analysis</strong> '
                '<span class="badge-pro">Pro -- Coming Soon</span>'
                '<br><br>Mechanical stress/strain analysis of scaffold geometry. '
                'Optimize pore architecture for load-bearing applications.'
                '</div>',
                unsafe_allow_html=True,
            )

    else:
        # Full assessment flow
        # Initialize session state for assessment
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "chain" not in st.session_state:
            st.session_state.chain = None
        if "construct_profile" not in st.session_state:
            st.session_state.construct_profile = None
        if "variance_report" not in st.session_state:
            st.session_state.variance_report = None
        if "docs" not in st.session_state:
            st.session_state.docs = []
        if "simulation_brief" not in st.session_state:
            st.session_state.simulation_brief = None
        if "cc3d_result" not in st.session_state:
            st.session_state.cc3d_result = None
        if "action_plan_narrative" not in st.session_state:
            st.session_state.action_plan_narrative = ""
        if "user_email" not in st.session_state:
            st.session_state.user_email = None
        if "doe_results" not in st.session_state:
            st.session_state.doe_results = None
        if "doe_factors" not in st.session_state:
            st.session_state.doe_factors = None
        if "assess_phase" not in st.session_state:
            st.session_state.assess_phase = "chat"
        if "application_domain" not in st.session_state:
            # Inferred from chat content + downstream cue detection — no manual selector
            st.session_state.application_domain = None

        def reset_assessment():
            st.session_state.messages = []
            st.session_state.chain = None
            st.session_state.construct_profile = None
            st.session_state.variance_report = None
            st.session_state.simulation_brief = None
            st.session_state.cc3d_result = None
            st.session_state.action_plan_narrative = ""
            st.session_state.user_email = None
            st.session_state.doe_results = None
            st.session_state.doe_factors = None
            st.session_state.docs = []
            st.session_state.assess_phase = "chat"
            st.rerun()

        # Try to import assessment modules
        try:
            from core.chat import extract_construct_profile, initialize_chat, send_message
            from core.models import ConstructProfile, VarianceReport
            from core.rag import retrieve_benchmarks, synthesize_variance_report
            from results_tab_renderers import (
                render_results_action_plan_tab,
                render_results_feasibility_tab,
                render_results_simulation_tab,
            )
            _assessment_available = True
        except ImportError as e:
            _assessment_available = False
            st.error(f"Assessment modules not available: {e}")

        if _assessment_available:
            # Reset button
            if st.session_state.assess_phase != "chat" or len(st.session_state.messages) > 0:
                if st.button("Reset Assessment", key="reset_assess"):
                    reset_assessment()

            if st.session_state.assess_phase == "chat":
                # Chat phase
                st.markdown(
                    "Describe your construct — tissue-engineering or cellular-agriculture. "
                    "After enough detail is gathered, the system will automatically benchmark "
                    "it against published protocols."
                )

                # Progress indicator
                n = len(st.session_state.messages)
                st.progress(min(1.0, n / 8.0) if n else 0.0)
                st.caption(f"**{n}/8 messages** -- analysis starts automatically when enough detail is gathered.")

                # Initialize chat session — unified prompt handles both domains
                if st.session_state.chain is None:
                    with st.spinner("Starting up..."):
                        st.session_state.chain = initialize_chat()
                        if len(st.session_state.messages) == 0:
                            # Get greeting from session's last assistant message
                            for m in reversed(st.session_state.chain.messages):
                                if m["role"] == "assistant":
                                    st.session_state.messages.append({
                                        "role": "assistant",
                                        "content": m["content"],
                                    })
                                    break

                # Render chat history
                for message in st.session_state.messages:
                    with st.chat_message(message["role"]):
                        _chat_text = message["content"]
                        _chat_text = re.sub(r"^#{1,4}\s+", "**", _chat_text, flags=re.MULTILINE)
                        st.markdown(_chat_text)

                # Force-run button
                if len(st.session_state.messages) > 0:
                    if st.button("Run analysis now", key="force_analyze", help="Analyze with current info"):
                        full_conversation = "\n".join(
                            f"{m['role']}: {m['content']}" for m in st.session_state.messages
                        )
                        profile = extract_construct_profile(full_conversation)
                        if not profile:
                            profile = ConstructProfile(
                                target_tissue="unknown",
                                raw_responses={"conversation": full_conversation[:500]},
                            )
                        if profile.application_domain is None:
                            profile = profile.model_copy(
                                update={"application_domain": st.session_state.application_domain}
                            )
                        st.session_state.construct_profile = profile
                        st.session_state.assess_phase = "analyzing"
                        st.rerun()

                # Chat input
                if user_input := st.chat_input("Describe your construct or answer the question..."):
                    st.session_state.messages.append({"role": "user", "content": user_input})
                    with st.chat_message("user"):
                        st.markdown(user_input)

                    with st.chat_message("assistant"):
                        with st.spinner("Thinking..."):
                            assistant_response = send_message(st.session_state.chain, user_input)
                            _display = re.sub(r"^#{1,4}\s+", "**", assistant_response, flags=re.MULTILINE)
                            st.markdown(_display)

                    st.session_state.messages.append({"role": "assistant", "content": assistant_response})

                    # Auto-transition after 8 messages with complete profile
                    msg_count = len(st.session_state.messages)
                    if msg_count >= 8:
                        full_conversation = "\n".join(
                            f"{m['role']}: {m['content']}" for m in st.session_state.messages
                        )
                        profile = extract_construct_profile(full_conversation)
                        if profile:
                            key_fields = [
                                profile.target_tissue, profile.cell_types,
                                profile.scaffold_material, profile.experimental_goal,
                                profile.primary_readout,
                            ]
                            if sum(1 for f in key_fields if f is not None) >= 4:
                                if profile.application_domain is None:
                                    profile = profile.model_copy(
                                        update={"application_domain": st.session_state.application_domain}
                                    )
                                st.session_state.construct_profile = profile
                                st.session_state.assess_phase = "analyzing"
                                st.rerun()

            elif st.session_state.assess_phase == "analyzing":
                # Analyzing phase
                if st.session_state.variance_report is not None:
                    st.session_state.assess_phase = "results"
                    st.rerun()

                with st.spinner("Searching literature and building your report..."):
                    profile = st.session_state.construct_profile
                    if profile is None:
                        profile = ConstructProfile(
                            target_tissue="unknown",
                            experimental_goal="basic_research",
                            application_domain=st.session_state.get("application_domain"),
                        )
                        st.session_state.construct_profile = profile

                    docs = retrieve_benchmarks(profile, k=12)
                    st.session_state.docs = docs

                    variance_report = synthesize_variance_report(profile, docs)
                    st.session_state.variance_report = variance_report
                    st.session_state.action_plan_narrative = ""
                    st.session_state.assess_phase = "results"
                    st.rerun()

            elif st.session_state.assess_phase == "results":
                # Results phase
                profile = st.session_state.construct_profile
                report = st.session_state.variance_report

                st.markdown(f"#### Analysis: {profile.target_tissue or 'Your Construct'}")

                # Hero summary
                col_a, col_b = st.columns([1, 2])
                with col_a:
                    try:
                        from core.feasibility import analyse as feasibility_analyse
                        feas = feasibility_analyse(profile, report)
                        st.metric("Literature match", feas.overall.replace("_", " ").title())
                    except Exception:
                        st.caption("Feasibility snapshot unavailable.")
                with col_b:
                    reds = [k for k, v in (report.risk_flags or {}).items() if v == "red"]
                    if reds:
                        shown = ", ".join(k.replace("_", " ") for k in reds[:4])
                        more = f" (+{len(reds) - 4} more)" if len(reds) > 4 else ""
                        st.markdown(f"**Red benchmark flags:** {shown}{more}")
                    else:
                        st.markdown("**Red flags:** none. Check Feasibility for fine-tuning.")

                st.divider()

                # Result sub-tabs
                rtab_feas, rtab_sim, rtab_methods = st.tabs(
                    ["Feasibility & migration", "Simulation & exports", "Methods & materials plan"]
                )
                with rtab_feas:
                    render_results_feasibility_tab(profile, report)
                with rtab_sim:
                    # Show pro badges for CC3D and FEA
                    st.markdown(
                        '<strong>CompuCell3D Simulation</strong> '
                        '<span class="badge-pro">Pro -- Coming Soon</span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        "Agent-based 3D cell simulation of your construct. "
                        "Predict migration, proliferation, and mechanical behavior."
                    )
                    st.divider()
                    st.markdown(
                        '<strong>Finite Element Analysis</strong> '
                        '<span class="badge-pro">Pro -- Coming Soon</span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        "Mechanical stress/strain analysis of scaffold geometry."
                    )
                with rtab_methods:
                    render_results_action_plan_tab(profile, report, save_signup)


# =====================================================================
# TAB 4 — About
# =====================================================================

with tab_about:
    st.markdown("### About Stromalytix")

    st.markdown(
        """
        **Stromalytix** is protocol intelligence for bioengineering. It combines a curated
        parameter library, structured protocol extraction from PubMed literature, and
        AI-driven construct assessment to help researchers make better decisions about
        3D cell culture design.
        """
    )

    st.divider()

    st.markdown("#### Parameter Library")
    st.markdown(
        """
        The parameter library contains **261 bioengineering constants** from two sources:

        **Literature** (222 entries) -- extracted from published papers, each linked to a
        DOI or PubMed ID. Values are traceable to specific experimental conditions
        (temperature, concentration, crosslinking method, measurement technique).

        **Model Estimate** (39 entries) -- derived from biophysical reasoning for
        computational simulation (e.g., CC3D adhesion energies). Clearly labeled and
        not presented as experimental measurements.

        Categories:
        - **Scaffold Materials** -- stiffness, porosity, degradation, swelling
        - **Cell Adhesion** -- cell-cell and cell-matrix contact energies
        - **Proliferation** -- doubling times, contact inhibition thresholds
        - **O2 Transport** -- diffusion coefficients, consumption rates
        - **Fabrication** -- print speeds, pressures, nozzle diameters
        - **Gel Penetration** -- migration speeds, MMP secretion, critical pore sizes

        Confidence levels:
        - **High** -- directly measured, multiple concordant studies
        - **Medium** -- single source or inferred from similar systems
        - **Low** -- estimated or limited experimental support
        """
    )

    st.divider()

    st.markdown("#### Protocol Graph")
    st.markdown(
        """
        Protocols are automatically extracted from PubMed full-text articles using a
        combination of regex patterns and LLM-based extraction. Each protocol is decomposed
        into structured steps:

        **Protocol** &rarr; **Steps** (cell sourcing, material prep, crosslinking, fabrication,
        cell seeding, culture, assay) &rarr; **Materials**, **Cells**, **Parameters**, **Outcomes**

        This structured representation enables similarity matching, novelty scoring, and
        gap analysis across the published tissue engineering literature.
        """
    )

    st.divider()

    st.markdown("#### How to Cite")
    st.code(
        """@misc{stromalytix2026,
  title   = {Stromalytix: Bioengineering Protocol Intelligence},
  author  = {K-Dense},
  year    = {2026},
  note    = {Parameter library (560 entries), protocol graph (396 protocols),
             and AI-driven construct assessment for tissue engineering
             and cellular agriculture},
  url     = {https://stromalytix.streamlit.app}
}""",
        language="bibtex",
    )

    st.divider()

    st.markdown("#### Links")
    st.markdown(
        """
        - [GitHub Repository](https://github.com/RegCoDev/stromalytix)
        - [Knowledge Vault API Documentation](https://github.com/RegCoDev/stromalytix/tree/main/services/knowledge_vault)
        """
    )

    st.divider()

    st.markdown("#### Contact & Feedback")
    with st.form("about_contact"):
        contact_email = st.text_input("Email address", placeholder="you@university.edu")
        contact_msg = st.text_area("Message (optional)", placeholder="Feature request, bug report, collaboration...")
        contact_submit = st.form_submit_button("Send")
        if contact_submit and contact_email:
            # Save to CSV
            csv_path = Path("feedback.csv")
            timestamp = datetime.now().isoformat()
            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, contact_email, contact_msg])
            st.success("Thank you for your feedback.")
