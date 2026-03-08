"""
PDF Export for Stromalytix

Generates PDF variance reports from VarianceReport objects.
"""

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from core.models import VarianceReport


def generate_pdf_report(report: VarianceReport) -> str:
    """Generate a PDF report from a VarianceReport.

    Args:
        report: VarianceReport with analysis results

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
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "Stromalytix Variance Report", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(8)

    # Construct Profile
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Construct Profile", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)

    profile = report.construct_profile
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
        # Use multi_cell for wrapping
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

    pdf.output(str(filepath))
    return str(filepath)
