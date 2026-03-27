"""
Streamlit renderers for the three results tabs (Feasibility, Simulation, Methods & materials).
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Callable

import streamlit as st

from core.action_plan import build_action_checklist, checklist_to_prompt_text
from core.expand_action_plan import expand_action_plan_narrative
from core.models import ConstructProfile, VarianceReport
from core.viz import build_parameter_scatter, build_radar_chart, build_risk_scorecard


def _anthropic_configured() -> bool:
    if os.getenv("ANTHROPIC_API_KEY"):
        return True
    try:
        return bool(st.secrets.get("ANTHROPIC_API_KEY"))
    except Exception:
        return False


def render_results_feasibility_tab(profile: ConstructProfile, report: VarianceReport) -> None:
    st.markdown("### Feasibility Analysis")
    st.caption("Cross-referencing your protocol against the literature parameter library.")
    try:
        from core.feasibility import analyse as feasibility_analyse

        feas = feasibility_analyse(profile, report)

        tier_color = {
            "feasible": "#00ff88",
            "marginal": "#ffd700",
            "aspirational": "#ff4444",
        }

        overall_color = tier_color.get(feas.overall, "#888")
        st.markdown(
            f'<p style="font-size:1.1em;">Overall assessment: '
            f'<strong style="color:{overall_color};">{feas.overall.upper()}</strong></p>',
            unsafe_allow_html=True,
        )

        for tier_name, items, color in [
            ("Feasible — literature-backed", feas.feasible, tier_color["feasible"]),
            ("Marginal — partial data", feas.marginal, tier_color["marginal"]),
            ("Aspirational — limited / no data", feas.aspirational, tier_color["aspirational"]),
        ]:
            if not items:
                continue
            st.markdown(
                f'<p style="color:{color}; font-weight:600; margin-top:0.8rem;">{tier_name} '
                f'({len(items)})</p>',
                unsafe_allow_html=True,
            )
            for it in items:
                detail_html = f'<span style="color:#e0e0e0;">{it.detail}</span>'
                if it.suggestion:
                    detail_html += (
                        f'<br><span style="color:#aaa; font-style:italic;">'
                        f'Suggestion: {it.suggestion}</span>'
                    )
                st.markdown(
                    f'<div style="border-left:3px solid {color}; padding:0.4rem 0.8rem; '
                    f'margin:0.3rem 0; background:#111;">'
                    f'<strong style="color:{color};">{it.axis}</strong><br>'
                    f'{detail_html}</div>',
                    unsafe_allow_html=True,
                )
    except Exception as e:
        st.warning(f"Feasibility analysis unavailable: {e}")

    st.markdown("### Migration & Gradient Hypotheses")
    st.caption(
        "How fabricated and spontaneous gradients are expected to "
        "influence cell migration in this construct."
    )
    try:
        from core.migration_insights import analyse as migration_analyse

        mig_rpt = migration_analyse(profile)

        category_icons = {
            "Spontaneous O2 Gradient": "🫁",
            "Nutrient / Waste Gradients": "🧪",
            "Fabricated / Emergent Stiffness Gradient": "🔧",
            "Contact Guidance (Geometric)": "📐",
            "Migration Kinetics": "🏃",
            "Degradation-Driven Migration": "♻️",
        }
        conf_badge = {
            "high": ("🟢", "#00ff88"),
            "medium": ("🟡", "#ffd700"),
            "low": ("🔴", "#ff4444"),
        }

        for cat, insights in mig_rpt.by_category.items():
            icon = category_icons.get(cat, "🔬")
            st.markdown(
                f'<p style="font-weight:600; font-size:1.05em; margin-top:1rem;">'
                f'{icon} {cat}</p>',
                unsafe_allow_html=True,
            )
            for ins in insights:
                badge_char, badge_color = conf_badge.get(ins.confidence, ("⚪", "#888"))
                source_html = ""
                if ins.sources:
                    links = ", ".join(
                        f'<a href="https://doi.org/{d}" style="color:#4a9eff;">{d}</a>'
                        for d in ins.sources
                        if d
                    )
                    if links:
                        source_html = f'<br><span style="color:#666; font-size:0.85em;">Sources: {links}</span>'
                st.markdown(
                    f'<div style="border-left:3px solid #333; padding:0.5rem 0.8rem; '
                    f'margin:0.3rem 0; background:#0d0d0d;">'
                    f'<strong style="color:#e0e0e0;">{ins.headline}</strong> '
                    f'<span style="color:{badge_color}; font-size:0.85em;">{badge_char} {ins.confidence}</span>'
                    f'<br><span style="color:#aaa; font-size:0.92em;">{ins.detail}</span>'
                    f'{source_html}</div>',
                    unsafe_allow_html=True,
                )

        if not mig_rpt.insights:
            st.info(
                "Insufficient data to generate migration hypotheses. "
                "Specify cell types, scaffold material, and dimensions."
            )
    except Exception as e:
        st.warning(f"Migration analysis unavailable: {e}")


def render_results_simulation_tab(profile: ConstructProfile, report: VarianceReport) -> None:
    with st.expander("Benchmarks & narrative", expanded=True):
        col1, col2 = st.columns([60, 40])
        with col1:
            st.plotly_chart(build_radar_chart(report), use_container_width=True)
        with col2:
            st.plotly_chart(build_risk_scorecard(report), use_container_width=True)

        st.markdown('<div class="narrative-container">', unsafe_allow_html=True)
        st.markdown("### Analysis summary")
        st.markdown(report.ai_narrative)

        if report.supporting_pmids:
            pmid_links = ", ".join(
                [f"[{pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)" for pmid in report.supporting_pmids]
            )
            st.markdown(
                f'<p style="color: #888; font-size: 0.9em; margin-top: 1rem;">'
                f'<strong>Supporting literature:</strong> {pmid_links}</p>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

        if report.key_references:
            with st.expander("Source literature"):
                for ref in report.key_references:
                    st.markdown(
                        f"""
                        **{ref.get('title', 'Untitled')}** ({ref.get('year', 'N/A')})
                        PMID: [{ref.get('pmid', 'N/A')}](https://pubmed.ncbi.nlm.nih.gov/{ref.get('pmid')})
                        *{ref.get('relevance_note', 'No note provided')}*
                        """
                    )
                    st.divider()

        st.plotly_chart(build_parameter_scatter(report), use_container_width=True)

    with st.expander("Scaffold geometry", expanded=False):
        scaf_col1, scaf_col2 = st.columns([2, 1])
        _simple_archs = frozenset(
            {
                "cylinder_solid",
                "cylinder_hollow",
                "ring_torus",
                "sphere_droplet",
                "droplet_in_droplet",
                "multimaterial_bilayer_cylinder",
            }
        )

        with scaf_col2:
            scaffold_arch = st.selectbox(
                "Architecture",
                [
                    "gyroid",
                    "schwarz_p",
                    "diamond",
                    "lidinoid",
                    "woodpile",
                    "grid",
                    "cylinder_solid",
                    "cylinder_hollow",
                    "ring_torus",
                    "sphere_droplet",
                    "droplet_in_droplet",
                    "multimaterial_bilayer_cylinder",
                    "custom_stl",
                ],
                index=0,
                key="scaf_arch_sim",
                help="Primitives: solid/hollow cylinders, torus ring, droplet spheres, core–shell and bilayer multimaterial.",
            )

            stl_file = st.file_uploader("Upload STL", type=["stl", "obj"], key="stl_upload_sim")

            if scaffold_arch in _simple_archs:
                scaf_pore = 300
                scaf_porosity = 70
                s_r = s_h = s_inner = s_major = s_minor = 1.5
                if scaffold_arch in (
                    "cylinder_solid",
                    "cylinder_hollow",
                    "sphere_droplet",
                    "droplet_in_droplet",
                    "multimaterial_bilayer_cylinder",
                ):
                    s_r = st.slider("Outer / droplet radius (mm)", 0.35, 2.8, 1.5, key="scaf_simple_r_sim")
                if scaffold_arch in (
                    "cylinder_solid",
                    "cylinder_hollow",
                    "multimaterial_bilayer_cylinder",
                ):
                    s_h = st.slider("Height (mm)", 0.8, 6.0, 3.5, key="scaf_simple_h_sim")
                if scaffold_arch in ("cylinder_hollow", "multimaterial_bilayer_cylinder", "droplet_in_droplet"):
                    default_in = min(0.95, s_r * 0.52) if scaffold_arch != "droplet_in_droplet" else min(0.85, s_r * 0.45)
                    s_inner = st.slider(
                        "Inner / core radius (mm)",
                        0.15,
                        max(0.2, s_r - 0.2),
                        default_in,
                        key="scaf_simple_inner_sim",
                    )
                if scaffold_arch == "ring_torus":
                    s_major = st.slider("Ring major radius (mm)", 0.8, 2.5, 1.7, key="scaf_torus_major_sim")
                    s_minor = st.slider("Ring tube radius (mm)", 0.15, 0.8, 0.35, key="scaf_torus_minor_sim")
                box_l = max(
                    4.0,
                    s_r * 2.8,
                    (s_h + 0.5) if scaffold_arch in ("cylinder_solid", "cylinder_hollow", "multimaterial_bilayer_cylinder") else 0,
                    (s_major * 2 + s_minor * 2 + 0.5) if scaffold_arch == "ring_torus" else 0,
                )
                zh = max(box_l, s_h + 0.5) if scaffold_arch in ("cylinder_solid", "cylinder_hollow", "multimaterial_bilayer_cylinder") else box_l
                if scaffold_arch == "ring_torus":
                    zh = max(box_l, (s_minor * 2 + 0.2))
                outer_box = (box_l, box_l, zh)
            else:
                scaf_pore = st.slider("Pore size (um)", 100, 800, 300, key="scaf_pore_sim")
                scaf_porosity = st.slider("Porosity (%)", 30, 90, 70, key="scaf_porosity_sim")
                s_r = s_h = s_inner = s_major = s_minor = 0.0
                outer_box = (4.0, 4.0, 4.0)

            if scaffold_arch != "custom_stl" or stl_file is not None:
                generate_scaffold = st.button("Generate Preview", key="gen_scaffold_sim", use_container_width=True)
            else:
                generate_scaffold = False

        with scaf_col1:
            if generate_scaffold:
                try:
                    from core.scaffold_geometry import (
                        generate_cylinder_hollow,
                        generate_cylinder_solid,
                        generate_droplet_in_droplet,
                        generate_filament_lattice,
                        generate_multimaterial_bilayer_cylinder,
                        generate_ring_torus,
                        generate_sphere_droplet,
                        generate_tpms,
                        import_stl,
                        preview_scaffold,
                    )

                    if stl_file is not None:
                        mesh = import_stl(stl_file.read())
                    elif scaffold_arch == "cylinder_solid":
                        mesh = generate_cylinder_solid(
                            radius_mm=s_r, height_mm=s_h, outer_dims_mm=outer_box
                        )
                    elif scaffold_arch == "cylinder_hollow":
                        ir = min(s_inner, s_r - 0.15)
                        mesh = generate_cylinder_hollow(
                            outer_radius_mm=s_r,
                            inner_radius_mm=max(0.15, ir),
                            height_mm=s_h,
                            outer_dims_mm=outer_box,
                        )
                    elif scaffold_arch == "ring_torus":
                        mesh = generate_ring_torus(
                            major_radius_mm=s_major,
                            minor_radius_mm=s_minor,
                            outer_dims_mm=outer_box,
                        )
                    elif scaffold_arch == "sphere_droplet":
                        mesh = generate_sphere_droplet(radius_mm=s_r, outer_dims_mm=outer_box)
                    elif scaffold_arch == "droplet_in_droplet":
                        cr = min(s_inner, s_r - 0.2)
                        mesh = generate_droplet_in_droplet(
                            outer_radius_mm=s_r,
                            core_radius_mm=max(0.2, cr),
                            outer_dims_mm=outer_box,
                        )
                    elif scaffold_arch == "multimaterial_bilayer_cylinder":
                        ir = min(s_inner, s_r - 0.15)
                        mesh = generate_multimaterial_bilayer_cylinder(
                            outer_radius_mm=s_r,
                            inner_radius_mm=max(0.15, ir),
                            height_mm=s_h,
                            outer_dims_mm=outer_box,
                        )
                    elif scaffold_arch in ("woodpile", "grid"):
                        mesh = generate_filament_lattice(
                            strand_diameter_um=scaf_pore * 0.5,
                            strand_spacing_um=scaf_pore,
                            pattern=scaffold_arch,
                        )
                    else:
                        mesh = generate_tpms(
                            topology=scaffold_arch,
                            pore_size_um=scaf_pore,
                            porosity_pct=scaf_porosity,
                        )
                    st.session_state["scaffold_mesh"] = mesh
                    fig_scaf = preview_scaffold(mesh)
                    st.plotly_chart(fig_scaf, use_container_width=True)
                    if mesh.get("hollow_note"):
                        st.caption(mesh["hollow_note"])

                    profile.scaffold_architecture = scaffold_arch
                    profile.pore_size_um = scaf_pore
                    profile.porosity_percent = scaf_porosity
                except Exception as e:
                    st.warning(f"Scaffold generation error: {e}")
            elif "scaffold_mesh" in st.session_state:
                from core.scaffold_geometry import preview_scaffold

                fig_scaf = preview_scaffold(st.session_state["scaffold_mesh"])
                st.plotly_chart(fig_scaf, use_container_width=True)
            else:
                st.info("Select scaffold parameters and click Generate Preview.")

    if profile.stiffness_kpa and profile.cell_density_per_ml:
        from core.fem_solver import (
            FEM_EXCLUDED_PHYSICS_SUMMARY,
            predict_scaffold_deformation,
            predict_stress_distribution,
        )

        with st.expander("Scaffold mechanics (linear elastic sketch)", expanded=False):
            st.caption(
                "**Not viscoelastic:** no creep, relaxation, or poroelastic flow. "
                "Readouts are coarse order-of-magnitude sketches for **bulk construct mechanics**, "
                "not mechanoreceptor maps or matrix rupture criteria."
            )
            st.caption(FEM_EXCLUDED_PHYSICS_SUMMARY)
            fea_result = predict_scaffold_deformation(
                stiffness_kpa=profile.stiffness_kpa,
                cell_density_per_ml=profile.cell_density_per_ml,
            )

            fea_col1, fea_col2, fea_col3 = st.columns(3)
            with fea_col1:
                st.metric("Max deformation (model)", f"{fea_result['max_deformation_um']:.1f} μm")
            with fea_col2:
                st.metric("Bulk strain (model)", f"{fea_result['strain_percent']:.2f}%")
            with fea_col3:
                risk = fea_result["failure_risk"]
                risk_color = {"low": "#00ff88", "medium": "#ffd700", "high": "#ff4444"}.get(risk, "#888")
                st.markdown(
                    f'<p style="font-size: 0.85em; color: #888;">Construct integrity band</p>'
                    f'<p style="font-size: 1.5em; font-weight: bold; color: {risk_color};">{risk.upper()}</p>',
                    unsafe_allow_html=True,
                )

            st.caption(fea_result.get("failure_risk_explainer", ""))
            st.markdown(
                f'<div style="border: 1px solid #444; padding: 0.8rem; border-radius: 0.5rem; '
                f'background: #1a1a1a; margin: 0.5rem 0;">'
                f'<span style="color: #aaa;">{fea_result["recommendation"]}</span></div>',
                unsafe_allow_html=True,
            )

            if profile.porosity_percent:
                stress_result = predict_stress_distribution(
                    stiffness_kpa=profile.stiffness_kpa,
                    porosity_percent=profile.porosity_percent,
                )
                st.markdown("##### Porous solid: elastic load-path hotspot index")
                st.caption(stress_result.get("model_limits", ""))
                st.markdown(
                    f'<div style="border: 1px solid #444; padding: 0.8rem; border-radius: 0.5rem; '
                    f'background: #1a1a1a; margin: 0.5rem 0;">'
                    f'<span style="color: #aaa;">{stress_result["recommendation"]}</span></div>',
                    unsafe_allow_html=True,
                )

    if st.session_state.simulation_brief is None:
        try:
            from core.rag import generate_simulation_brief

            st.session_state.simulation_brief = generate_simulation_brief(profile, report)
        except Exception as e:
            st.error(f"Could not generate simulation brief: {e}")
            st.session_state.simulation_brief = None

    sim_brief = st.session_state.simulation_brief

    if sim_brief is not None:
        st.markdown("### CC3D simulation brief")
        st.caption("What a CompuCell3D run would target—plus optional cloud execution on your sidecar.")
        st.markdown(
            f'<p style="font-size: 1.2em; font-weight: 500; margin: 1rem 0;">'
            f'{sim_brief["simulation_question"]}</p>',
            unsafe_allow_html=True,
        )

        st.markdown("**Key CC3D parameters:**")
        st.code(json.dumps(sim_brief["key_parameters"], indent=2), language="json")

        param_sources = sim_brief.get("parameter_sources", {})
        if param_sources:
            st.markdown("**Parameter Provenance:**")
            source_rows = []
            for pname, info in param_sources.items():
                src = info.get("source", "unknown")
                conf = info.get("confidence", "?")
                doi = info.get("doi") or ""
                if conf == "high":
                    conf_display = "🟢 high"
                elif conf == "medium":
                    conf_display = "🟡 medium"
                else:
                    conf_display = "🔴 low"
                source_rows.append(
                    {
                        "Parameter": pname.replace("_", " ").title(),
                        "Source": src,
                        "Confidence": conf_display,
                        "DOI": doi,
                    }
                )
            if source_rows:
                import pandas as pd

                st.dataframe(
                    pd.DataFrame(source_rows),
                    use_container_width=True,
                    hide_index=True,
                )

        st.markdown("**Predicted Observations:**")
        for i, outcome in enumerate(sim_brief["predicted_outcomes"], 1):
            st.markdown(f"{i}. {outcome}")

        st.markdown(
            f'<div style="border: 2px solid #ff4444; padding: 1rem; border-radius: 0.5rem; background: #1a0a0a; margin: 1rem 0;">'
            f'<strong style="color: #ff4444;">⚠ Risk Prediction:</strong><br>{sim_brief["risk_prediction"]}'
            f"</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div style="border: 2px solid #00ff88; padding: 1rem; border-radius: 0.5rem; background: #0a1a0a; margin: 1rem 0;">'
            f'<strong style="color: #00ff88;">✓ Validation Experiment:</strong><br>{sim_brief["validation_experiment"]}'
            f"</div>",
            unsafe_allow_html=True,
        )

        from core.cc3d_runner import CC3D_API_URL, run_simulation

        if CC3D_API_URL:
            if st.button("⚡ Run CC3D Simulation (Cloud)", key="btn_run_cc3d_cloud_sim", use_container_width=True):
                with st.spinner("Running CC3D simulation on cloud..."):
                    cc3d_result = run_simulation(sim_brief)
                    if cc3d_result["success"]:
                        st.success(
                            f"CC3D completed: {cc3d_result['mcs_completed']} MCS in "
                            f"{cc3d_result['duration_seconds']}s"
                        )
                        if cc3d_result.get("output"):
                            st.code(cc3d_result["output"], language="text")

                        vtk_frames = cc3d_result.get("vtk_frames", [])
                        if vtk_frames:
                            from core.cc3d_viz import (
                                get_default_type_map,
                                parse_vtk_from_bytes,
                                parse_vtk_scalar_field,
                                render_unified_scene,
                            )

                            type_map = get_default_type_map(sim_brief.get("key_parameters", sim_brief))

                            cell_frames = [f for f in vtk_frames if f.get("field_type") == "cell"]
                            o2_frames = [f for f in vtk_frames if f.get("field_type") == "o2"]

                            display_frames = cell_frames if cell_frames else vtk_frames
                            frame_idx = len(display_frames) - 1
                            if len(display_frames) > 1:
                                frame_idx = st.slider(
                                    "Simulation frame",
                                    0,
                                    len(display_frames) - 1,
                                    value=len(display_frames) - 1,
                                    key="cc3d_frame_slider",
                                )

                            frame = display_frames[frame_idx]
                            vtk_bytes = base64.b64decode(frame["data_b64"])
                            lattice = parse_vtk_from_bytes(vtk_bytes)

                            o2_field = None
                            if o2_frames and frame_idx < len(o2_frames):
                                o2_bytes = base64.b64decode(o2_frames[frame_idx]["data_b64"])
                                o2_field = parse_vtk_scalar_field(o2_bytes)

                            scaffold_mesh = st.session_state.get("scaffold_mesh")

                            fig_cc3d = render_unified_scene(
                                cell_lattice=lattice,
                                type_map=type_map,
                                o2_field=o2_field,
                                scaffold_mesh=scaffold_mesh,
                                title="CC3D Simulation Result",
                                timestep=frame_idx,
                            )
                            st.plotly_chart(fig_cc3d, use_container_width=True)

                            if o2_field is not None:
                                st.caption("Red markers indicate hypoxic zones (O2 < 5%)")
                    else:
                        st.warning(f"CC3D: {cc3d_result.get('error', 'Unknown error')}")
        else:
            st.button(
                "⚡ Run CC3D Simulation (Cloud)",
                disabled=True,
                key="btn_run_cc3d_cloud_disabled",
                use_container_width=True,
                help="Set CC3D_API_URL environment variable to your VPS sidecar address.",
            )
            st.caption(
                "Cloud CC3D is optional. You can still use **Exports** below for the PDF report "
                "and a scaffold PNG after you generate a preview."
            )
    else:
        st.warning("Simulation brief could not be generated. Check your API key and try again.")

    with st.expander("Exports (PDF & PNG)", expanded=False):
        export_col1, export_col2 = st.columns(2)
        with export_col1:
            try:
                from core.export import generate_pdf_report

                pdf_path = generate_pdf_report(report, client_name="")
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "Download PDF Report",
                        data=f.read(),
                        file_name=Path(pdf_path).name,
                        mime="application/pdf",
                        use_container_width=True,
                        key="download_pdf_sim_tab",
                    )
            except Exception as e:
                st.button(
                    "Download PDF Report",
                    disabled=True,
                    use_container_width=True,
                    key="download_pdf_sim_disabled",
                    help=f"PDF export unavailable: {e}",
                )

        with export_col2:
            try:
                scaffold_mesh = st.session_state.get("scaffold_mesh")
                if scaffold_mesh:
                    from core.export import export_figure_png
                    from core.scaffold_geometry import preview_scaffold

                    viz_fig = preview_scaffold(scaffold_mesh)
                    png_bytes = export_figure_png(viz_fig)
                    st.download_button(
                        "Download Scaffold Preview (PNG)",
                        data=png_bytes,
                        file_name=f"stromalytix_{profile.target_tissue or 'construct'}_scaffold.png",
                        mime="image/png",
                        use_container_width=True,
                        key="download_png_sim_tab",
                    )
                else:
                    st.button(
                        "Download Scaffold Preview (PNG)",
                        disabled=True,
                        use_container_width=True,
                        key="download_png_sim_disabled",
                        help="Generate a scaffold preview first.",
                    )
            except Exception as e:
                st.button(
                    "Download Scaffold (PNG)",
                    disabled=True,
                    use_container_width=True,
                    key="download_png_sim_err",
                    help=f"PNG export unavailable: {e}",
                )


def render_results_action_plan_tab(
    profile: ConstructProfile,
    report: VarianceReport,
    save_signup: Callable[[str], None],
) -> None:
    st.markdown("### Methods & materials plan")
    st.caption(
        "Checklist merges **library gaps** with **bench-ready** items: supplies and reagents, follow-on "
        "modeling, and who to pull in (cores, CROs, collaborators). "
        "**Expand with AI** drafts a narrative for experimentalists—sourcing, assays, modeling, people, "
        "and further reading from your report’s references (no fake PMIDs)."
    )

    rows = build_action_checklist(profile, report)
    if rows:
        import pandas as pd

        st.markdown("**Top priorities (first five)**")
        for i, row in enumerate(rows[:5], start=1):
            pr = row.get("priority", "")
            st.markdown(
                f"{i}. **{row.get('parameter', '')}** ({pr}) — {row.get('what_to_do', '')}  \n"
                f"_Why:_ {row.get('why', '')[:220]}{'…' if len(row.get('why', '')) > 220 else ''}"
            )
        with st.expander("Full checklist (table)", expanded=False):
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info(
            "No structured checklist items — your profile aligns well with the curated library. "
            "You can still generate a narrative plan below."
        )

    checklist_txt = checklist_to_prompt_text(rows)
    has_key = _anthropic_configured()

    expand_kwargs = {
        "label": "Expand for lab execution (AI)",
        "disabled": not has_key,
        "key": "expand_plan_ai",
        "use_container_width": True,
    }
    if not has_key:
        expand_kwargs["help"] = (
            "Set ANTHROPIC_API_KEY in the environment or Streamlit secrets to enable expansion."
        )
    if st.button(**expand_kwargs):
        with st.spinner("Expanding methods & materials plan…"):
            try:
                st.session_state.action_plan_narrative = expand_action_plan_narrative(
                    profile, report, checklist_txt
                )
            except Exception as e:
                st.error(f"Could not expand plan: {e}")

    narrative = st.session_state.get("action_plan_narrative") or ""
    if narrative:
        st.markdown(narrative)

    st.divider()
    st.markdown("### 💾 Save this analysis + get early access to the full platform")

    col1, col2 = st.columns([3, 1])
    with col1:
        email = st.text_input(
            "Email address",
            placeholder="your.email@institution.edu",
            label_visibility="collapsed",
            key="email_plan_cta",
        )
    with col2:
        if st.button("Sign Up", use_container_width=True, key="signup_plan_cta"):
            if email and "@" in email:
                save_signup(email)
                st.success("You're on the list. We'll be in touch.")
            else:
                st.error("Please enter a valid email address.")

    st.caption("Tip: download the PDF report from the **Simulation** tab.")
