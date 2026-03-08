"""
PDF Export for Stromalytix

Generates white-label PDF variance reports from VarianceReport objects.
Includes Plotly figure PNG/SVG export via kaleido.
"""

import io
import os
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from core.materials_intelligence import LotIntelligenceReport
from core.models import VarianceReport


def _sanitize_text(text: str) -> str:
    """Replace Unicode characters unsupported by Helvetica with ASCII equivalents."""
    replacements = {
        "\u2014": "--",  # em dash
        "\u2013": "-",   # en dash
        "\u2018": "'",   # left single quote
        "\u2019": "'",   # right single quote
        "\u201c": '"',   # left double quote
        "\u201d": '"',   # right double quote
        "\u2026": "...", # ellipsis
        "\u00b1": "+/-", # plus-minus
        "\u00b7": ".",   # middle dot
        "\u2265": ">=",  # greater than or equal
        "\u2264": "<=",  # less than or equal
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


def export_figure_png(fig, width: int = 1200, height: int = 800) -> bytes:
    """Export a Plotly figure to PNG bytes via kaleido."""
    return fig.to_image(format="png", width=width, height=height, scale=2)


def export_figure_svg(fig, width: int = 1200, height: int = 800) -> bytes:
    """Export a Plotly figure to SVG bytes via kaleido."""
    return fig.to_image(format="svg", width=width, height=height)


def generate_pdf_report(report: VarianceReport, client_name: str = "") -> str:
    """Generate a white-label PDF report from a VarianceReport.

    Args:
        report: VarianceReport with analysis results
        client_name: Optional client name for white-labeling

    Returns:
        Path to generated PDF file in outputs/
    """
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)

    tissue = report.construct_profile.target_tissue or "unknown"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"stromalytix_report_{tissue}_{timestamp}.pdf"
    filepath = outputs_dir / filename

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ---- PAGE 1: Cover ----
    pdf.add_page()
    pdf.ln(40)

    pdf.set_font("Helvetica", "B", 24)
    pdf.cell(0, 14, "PROTOCOL INTELLIGENCE REPORT", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)

    if client_name:
        pdf.set_font("Helvetica", "", 16)
        pdf.cell(0, 10, f"Prepared for: {client_name}", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(5)

    pdf.set_font("Helvetica", "", 14)
    profile = report.construct_profile
    tissue_label = profile.target_tissue or "Unknown"
    goal_label = profile.experimental_goal or ""
    pdf.cell(0, 8, f"Tissue: {tissue_label.title()}", new_x="LMARGIN", new_y="NEXT", align="C")
    if goal_label:
        pdf.cell(0, 8, f"Goal: {goal_label.replace('_', ' ').title()}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.cell(0, 8, f"Date: {datetime.now().strftime('%B %d, %Y')}", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.ln(30)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "Prepared by Stromalytix | stromalytix.com", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 6, "CONFIDENTIAL - For intended recipient only", new_x="LMARGIN", new_y="NEXT", align="C")

    # ---- PAGE 2: Executive Summary ----
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "Executive Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    exec_summary = _generate_executive_summary(report)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, exec_summary)
    pdf.ln(8)

    # ---- Construct Profile ----
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Construct Profile", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)

    profile_items = [
        ("Target Tissue", profile.target_tissue),
        ("Cell Types", ", ".join(profile.cell_types) if profile.cell_types else None),
        ("Scaffold Material", profile.scaffold_material),
        ("Stiffness", f"{profile.stiffness_kpa} kPa" if profile.stiffness_kpa else None),
        ("Porosity", f"{profile.porosity_percent}%" if profile.porosity_percent else None),
        ("Cell Density", f"{profile.cell_density_per_ml:.0e} cells/mL" if profile.cell_density_per_ml else None),
        ("Goal", profile.experimental_goal),
        ("Readout", profile.primary_readout),
    ]

    for label, value in profile_items:
        if value:
            pdf.cell(0, 6, f"  {label}: {value}", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)

    # Benchmark Ranges
    if report.benchmark_ranges:
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Benchmark Ranges", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)

        for param, ranges in report.benchmark_ranges.items():
            min_val = ranges.get("min", "?")
            max_val = ranges.get("max", "?")
            unit = ranges.get("unit", "")
            pdf.cell(0, 6, f"  {param}: {min_val} - {max_val} {unit}", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(4)

    # Deviation Scores & Risk Flags
    if report.deviation_scores:
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Deviation Scores & Risk Assessment", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)

        for param, score in report.deviation_scores.items():
            risk = report.risk_flags.get(param, "unknown")
            pdf.cell(0, 6, f"  {param}: deviation={score:.2f}, risk={risk}", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(4)

    # AI Narrative
    if report.ai_narrative:
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Analysis", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, f"  {report.ai_narrative}")
        pdf.ln(4)

    # Key References
    if report.key_references:
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Key References", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)

        for ref in report.key_references:
            pmid = ref.get("pmid", "")
            title = ref.get("title", "")
            year = ref.get("year", "")
            note = ref.get("relevance_note", "")
            pdf.multi_cell(0, 5, f"  PMID {pmid} ({year}): {title}")
            if note:
                pdf.set_font("Helvetica", "I", 8)
                pdf.cell(0, 4, f"    {note}", new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", "", 9)

    # ---- FINAL PAGE: Signature + Disclaimer ----
    pdf.add_page()
    pdf.ln(20)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Disclaimer & Authorization", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, (
        "This report was generated by Stromalytix, a Biological Process Intelligence platform. "
        "Results are based on computational analysis of published literature and should be "
        "validated with experimental data before making critical decisions. The analysis "
        "references PubMed abstracts and does not constitute medical or regulatory advice."
    ))
    pdf.ln(10)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "Prepared by Stromalytix | stromalytix.com", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", new_x="LMARGIN", new_y="NEXT")

    pdf.output(str(filepath))
    return str(filepath)


def generate_partner_report_pdf(
    report: LotIntelligenceReport,
    config: dict,
    product: dict,
    application: dict,
    cell_type: str = "",
) -> str:
    """Generate a partner-branded Application Intelligence PDF.

    Args:
        report: LotIntelligenceReport from materials intelligence
        config: Partner config dict
        product: Selected product dict
        application: Selected application dict
        cell_type: Primary cell type string

    Returns:
        Path to generated PDF file in outputs/
    """
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)

    partner_id = config.get("partner_id", "unknown")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{partner_id}_report_{product.get('product_id', 'lot')}_{timestamp}.pdf"
    filepath = outputs_dir / filename

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    partner_name = config.get("partner_name", "Application Intelligence")
    header_text = config.get("pdf_header", "Application Intelligence Report")
    footer_text = config.get("pdf_footer", f"Generated by {partner_name}")
    powered_by = config.get("powered_by", "")

    # ---- PAGE 1: Cover ----
    pdf.add_page()
    pdf.ln(40)

    pdf.set_font("Helvetica", "B", 24)
    pdf.cell(0, 14, header_text, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)

    pdf.set_font("Helvetica", "", 16)
    pdf.cell(0, 10, product.get("display_name", ""), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 14)
    pdf.cell(0, 8, f"Application: {application.get('display_name', '')}", new_x="LMARGIN", new_y="NEXT", align="C")
    if cell_type:
        pdf.cell(0, 8, f"Cell Type: {cell_type}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.cell(0, 8, f"Date: {datetime.now().strftime('%B %d, %Y')}", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.ln(30)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, footer_text, new_x="LMARGIN", new_y="NEXT", align="C")
    if powered_by:
        pdf.cell(0, 6, powered_by, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 6, "CONFIDENTIAL - For intended recipient only", new_x="LMARGIN", new_y="NEXT", align="C")

    # ---- PAGE 2: Release Decision + Key Metrics ----
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "Release Decision", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    decision = report.release_recommendation
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"Decision: {decision}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, _sanitize_text(report.release_rationale))
    pdf.ln(6)

    # Key metrics table
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Predicted Performance", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)

    metrics = [
        ("Predicted Stiffness", f"{report.predicted_stiffness_kpa:.1f} kPa (+/- {report.stiffness_uncertainty_kpa:.1f})"),
        ("Printability Score", f"{report.predicted_printability_score:.0%} (+/- {report.printability_uncertainty:.0%})"),
        ("Cell Viability Day 3", f"{report.predicted_cell_viability_day3_pct:.1f}% (+/- {report.viability_sd_pct:.1f}%)"),
        ("Cell Viability Day 7", f"{report.predicted_cell_viability_day7_pct:.1f}% (+/- {report.viability_sd_pct:.1f}%)"),
        ("Confidence", report.confidence.title()),
    ]
    for label, value in metrics:
        pdf.cell(90, 7, f"  {label}:", new_x="RIGHT", new_y="TOP")
        pdf.cell(0, 7, value, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Process recommendations
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Recommended Process Parameters", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)

    process_params = [
        ("Nozzle Diameter", f"{report.recommended_nozzle_diameter_mm} mm"),
        ("Print Speed", f"{report.recommended_print_speed_mms} mm/s"),
        ("Crosslink Time", f"{report.recommended_crosslink_time_s:.0f} s"),
        ("Cell Density", f"{report.recommended_cell_density_per_ml:.0e} cells/mL"),
    ]
    for label, value in process_params:
        pdf.cell(90, 7, f"  {label}:", new_x="RIGHT", new_y="TOP")
        pdf.cell(0, 7, value, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Data gaps
    if report.data_gaps:
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Data Gaps", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for gap in report.data_gaps:
            pdf.multi_cell(0, 6, _sanitize_text(f"  - {gap}"))
        pdf.ln(4)

    # References
    if report.references:
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Calibration References", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8)
        for ref in report.references:
            # Truncate long references to fit page width
            ref_text = _sanitize_text(f"  {ref}")
            if len(ref_text) > 120:
                ref_text = ref_text[:117] + "..."
            pdf.cell(0, 5, ref_text, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # ---- FINAL PAGE: Disclaimer ----
    pdf.add_page()
    pdf.ln(20)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Disclaimer", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, (
        "This report was generated by an Application Intelligence platform. "
        "Predictions are based on physics-grounded models calibrated against "
        "published literature. Results should be validated with experimental "
        "data before making production or clinical decisions. "
        "This analysis does not constitute medical or regulatory advice."
    ))
    pdf.ln(10)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, footer_text, new_x="LMARGIN", new_y="NEXT")
    if powered_by:
        pdf.cell(0, 6, powered_by, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", new_x="LMARGIN", new_y="NEXT")

    pdf.output(str(filepath))
    return str(filepath)


def _generate_executive_summary(report: VarianceReport) -> str:
    """Generate executive summary — LLM if available, otherwise template."""
    # Identify top risks
    red_flags = [p for p, r in report.risk_flags.items() if r == "red"]
    yellow_flags = [p for p, r in report.risk_flags.items() if r == "yellow"]

    tissue = report.construct_profile.target_tissue or "tissue"

    if red_flags:
        risk_text = f"Critical risks identified in: {', '.join(red_flags)}."
    elif yellow_flags:
        risk_text = f"Moderate risks identified in: {', '.join(yellow_flags)}."
    else:
        risk_text = "No critical risks identified."

    summary = (
        f"This {tissue} construct was analyzed against published literature benchmarks. "
        f"{risk_text} "
        f"The analysis is grounded in {len(report.supporting_pmids)} PubMed-cited sources. "
        f"See the detailed analysis section for parameter-specific recommendations."
    )

    # Try LLM summary if API key available
    try:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key and report.ai_narrative:
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(
                model="claude-haiku-4-5-20251001",
                temperature=0.2,
                max_tokens=256,
                api_key=api_key,
            )
            prompt = (
                "Write exactly 3 sentences summarizing this tissue engineering analysis "
                "for a non-scientist reader. Lead with the biggest risk. End with the key "
                "recommendation. Plain language. No jargon.\n\n"
                f"Analysis: {report.ai_narrative}\n"
                f"Risk flags: {report.risk_flags}"
            )
            response = llm.invoke(prompt)
            return response.content.strip()
    except Exception:
        pass

    return summary
