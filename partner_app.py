"""
Stromalytix — Partner Application Intelligence

Separate Streamlit entry point for partner-facing workflow.
Form-based (not chat-based) — faster for sales rep demos.

Usage:
    STROMALYTIX_PARTNER=cytoink uv run streamlit run partner_app.py
"""

import os
from datetime import datetime

import streamlit as st

from core.partner_config import (
    load_partner_config,
    get_product_by_id,
    get_application_by_id,
)
from core.materials_intelligence import (
    BioinkLotCharacterization,
    predict_lot_performance,
)


def main():
    config = load_partner_config()
    partner_name = config.get("partner_name", "Application Intelligence")
    colors = config.get("brand_colors", {})
    primary = colors.get("primary", "#00ff88")

    st.set_page_config(
        page_title=f"{partner_name}",
        page_icon="🧬",
        layout="wide",
    )

    # Brand CSS
    st.markdown(f"""
    <style>
    .stApp {{ background-color: {colors.get('background', '#0a0a0a')}; }}
    h1, h2, h3 {{ color: {colors.get('text', '#ffffff')}; }}
    .brand-accent {{ color: {primary}; font-weight: bold; }}
    .stButton>button {{
        border: 1px solid {primary};
        color: {primary};
        background: transparent;
    }}
    .stButton>button:hover {{
        background: {primary};
        color: #000000;
    }}
    </style>
    """, unsafe_allow_html=True)

    # Header
    st.markdown(f"# {partner_name}")
    tagline = config.get("partner_tagline", "")
    if tagline:
        st.caption(tagline)

    powered_by = config.get("powered_by", "")
    if powered_by:
        st.sidebar.markdown(f"*{powered_by}*")

    # --- Sidebar: product + application selectors ---
    st.sidebar.markdown("## Configuration")

    products = config.get("products", [])
    # Filter out training-only and unavailable products
    available_products = [
        p for p in products
        if not p.get("training_only") and p.get("available", True)
    ]

    product_names = [p["display_name"] for p in available_products]
    selected_product_idx = st.sidebar.selectbox(
        "Product",
        range(len(product_names)),
        format_func=lambda i: product_names[i],
    )
    product = available_products[selected_product_idx] if available_products else None

    applications = config.get("featured_applications", [])
    app_names = [a["display_name"] for a in applications]
    selected_app_idx = st.sidebar.selectbox(
        "Application",
        range(len(app_names)),
        format_func=lambda i: app_names[i],
    )
    application = applications[selected_app_idx] if applications else None

    # --- Main form ---
    if product is None:
        st.warning("No products configured for this partner.")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Product Details")
        st.markdown(f"**{product['display_name']}**")
        st.caption(product.get("description", ""))

        if product.get("handling_warning"):
            st.warning(product["handling_warning"])

        if product.get("viability_note"):
            st.info(product["viability_note"])

        rheology = product.get("default_rheology", {})
        st.markdown("#### Default Rheology")
        r_col1, r_col2, r_col3 = st.columns(3)
        r_col1.metric("Storage Modulus", f"{rheology.get('storage_modulus_pa', 0)} Pa")
        r_col2.metric("Viscosity (37°C)", f"{rheology.get('viscosity_pas_at_37c', 0)} Pa·s")
        r_col3.metric("Gelation Time", f"{rheology.get('gelation_time_s', 0)} s")

    with col2:
        st.markdown("### Application Target")
        if application:
            st.markdown(f"**{application['display_name']}**")
            cell_types = application.get("default_cell_types", [])
            if cell_types:
                st.markdown(f"Default cell types: {', '.join(cell_types)}")
            stiffness_range = application.get("target_stiffness_kpa", [])
            if len(stiffness_range) == 2:
                st.markdown(f"Target stiffness: {stiffness_range[0]}–{stiffness_range[1]} kPa")
            culture_days = application.get("culture_duration_days")
            if culture_days:
                st.markdown(f"Culture duration: {culture_days} days")

    st.markdown("---")

    # --- Override rheology form ---
    st.markdown("### Lot-Specific Rheology (Optional Overrides)")
    st.caption("Leave blank to use product defaults. Enter measured QC values for lot-specific predictions.")

    o_col1, o_col2, o_col3 = st.columns(3)
    with o_col1:
        override_modulus = st.number_input(
            "Storage Modulus (Pa)",
            min_value=0.0,
            value=float(rheology.get("storage_modulus_pa", 0)),
            step=100.0,
        )
        override_swelling = st.number_input(
            "Swelling Ratio",
            min_value=0.1,
            value=float(rheology.get("swelling_ratio", 4.0)),
            step=0.1,
        )
    with o_col2:
        override_viscosity = st.number_input(
            "Viscosity at 37°C (Pa·s)",
            min_value=0.0,
            value=float(rheology.get("viscosity_pas_at_37c", 0)),
            step=5.0,
        )
        override_gelation = st.number_input(
            "Gelation Time (s)",
            min_value=0.0,
            value=float(rheology.get("gelation_time_s", 0)),
            step=5.0,
        )
    with o_col3:
        override_uv = st.number_input(
            "UV Dose (mW·cm⁻²·s)",
            min_value=0.0,
            value=float(rheology.get("uv_dose_mwcm2_s", 0) or 0),
            step=50.0,
        )
        override_degradation = st.number_input(
            "Degradation Rate (/day)",
            min_value=0.0,
            value=float(rheology.get("degradation_rate_day", 0)),
            step=0.1,
        )

    # Cell type selector from application defaults
    cell_type_options = application.get("default_cell_types", ["HepG2"]) if application else ["HepG2"]
    selected_cell_type = st.selectbox("Primary Cell Type", cell_type_options)

    # --- Run prediction ---
    if st.button("Generate Application Intelligence Report", type="primary"):
        with st.spinner("Running materials intelligence pipeline..."):
            try:
                # Map cell type to internal key
                cell_key = selected_cell_type.lower().replace(" ", "_").replace("-", "")
                char = BioinkLotCharacterization(
                    lot_id=f"{product['product_id']}_demo",
                    material_name=product.get("display_name", "Unknown"),
                    storage_modulus_pa=override_modulus if override_modulus > 0 else None,
                    viscosity_pas_at_37c=override_viscosity if override_viscosity > 0 else None,
                    gelation_time_s=override_gelation if override_gelation > 0 else None,
                    swelling_ratio=override_swelling if override_swelling > 0 else None,
                    uv_dose_mwcm2_s=override_uv if override_uv > 0 else None,
                    degradation_rate_day=override_degradation if override_degradation > 0 else None,
                    cell_types=[cell_key],
                )
                report = predict_lot_performance(char)

                st.session_state["partner_report"] = report
                st.session_state["partner_product"] = product
                st.session_state["partner_application"] = application
                st.session_state["partner_cell_type"] = selected_cell_type
            except Exception as e:
                st.error(f"Prediction failed: {e}")

    # --- Display results ---
    if "partner_report" in st.session_state:
        report = st.session_state["partner_report"]
        product_ctx = st.session_state["partner_product"]
        app_ctx = st.session_state["partner_application"]

        st.markdown("---")
        st.markdown("## Application Intelligence Results")

        # Release decision banner
        decision = report.release_recommendation
        if decision == "RELEASE":
            st.success(f"**{decision}** — This lot is predicted to perform well for {app_ctx['display_name']}.")
        elif decision == "CONDITIONAL":
            st.warning(f"**{decision}** — This lot may perform with caveats. Review details below.")
        else:
            st.error(f"**{decision}** — This lot is not recommended for {app_ctx['display_name']}.")

        # Key metrics
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric(
            "Predicted Stiffness",
            f"{report.predicted_stiffness_kpa:.1f} kPa",
            help=f"±{report.stiffness_uncertainty_kpa:.1f} kPa (12% uncertainty)",
        )
        m_col2.metric(
            "Printability",
            f"{report.predicted_printability_score:.0%}",
        )
        m_col3.metric(
            "Cell Viability (Day 3)",
            f"{report.predicted_cell_viability_day3_pct:.0f}%",
            help=f"±{report.viability_sd_pct:.1f}%",
        )
        m_col4.metric(
            "Confidence",
            report.confidence.title(),
        )

        # Rationale
        if report.release_rationale:
            st.markdown("### Assessment Details")
            st.markdown(report.release_rationale)

        # Process recommendations
        st.markdown("### Recommended Process Parameters")
        p_col1, p_col2, p_col3, p_col4 = st.columns(4)
        p_col1.metric("Nozzle Diameter", f"{report.recommended_nozzle_diameter_mm} mm")
        p_col2.metric("Print Speed", f"{report.recommended_print_speed_mms} mm/s")
        p_col3.metric("Crosslink Time", f"{report.recommended_crosslink_time_s:.0f} s")
        p_col4.metric("Day 7 Viability", f"{report.predicted_cell_viability_day7_pct:.0f}%")

        # Data gaps
        if report.data_gaps:
            st.markdown("### Data Gaps")
            for gap in report.data_gaps:
                st.markdown(f"- {gap}")

        # References
        if report.references:
            with st.expander("Calibration References"):
                for ref in report.references:
                    st.caption(ref)

        # PDF download
        st.markdown("---")
        if st.button("Download PDF Report"):
            with st.spinner("Generating PDF..."):
                try:
                    from core.export import generate_partner_report_pdf
                    pdf_path = generate_partner_report_pdf(
                        report=report,
                        config=config,
                        product=product_ctx,
                        application=app_ctx,
                        cell_type=st.session_state.get("partner_cell_type", ""),
                    )
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            label="Download PDF",
                            data=f.read(),
                            file_name=os.path.basename(pdf_path),
                            mime="application/pdf",
                        )
                except Exception as e:
                    st.error(f"PDF generation failed: {e}")


if __name__ == "__main__":
    main()
