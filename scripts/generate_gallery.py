"""
Generate pre-rendered visualization gallery for Streamlit Cloud fallback.

Creates static PNG renders of demo constructs so the app can display
example visualizations even when heavy dependencies aren't available.
"""
import json
import sys
sys.path.insert(0, ".")

from pathlib import Path
from core.models import ConstructProfile
from core.tissue_viz import render_construct_3d
from core.export import export_figure_png

GALLERY_DIR = Path("data/gallery")
GALLERY_DIR.mkdir(parents=True, exist_ok=True)

DEMO_CONSTRUCTS = [
    {
        "name": "cardiac_bioprint",
        "method": "bioprinting",
        "profile": ConstructProfile(
            target_tissue="cardiac",
            cell_types=["cardiomyocytes", "fibroblasts", "HUVEC"],
            scaffold_material="GelMA",
            stiffness_kpa=12.0,
            porosity_percent=80.0,
            cell_density_per_ml=5e6,
            experimental_goal="disease_modeling",
        ),
        "title": "Cardiac — Bioprinted GelMA",
    },
    {
        "name": "bbb_ooc",
        "method": "organ_on_chip",
        "profile": ConstructProfile(
            target_tissue="blood-brain barrier",
            cell_types=["HUVEC", "astrocytes"],
            scaffold_material="PDMS",
            stiffness_kpa=3.0,
            cell_density_per_ml=2e6,
            experimental_goal="drug_screening",
        ),
        "title": "BBB — Organ-on-Chip",
    },
    {
        "name": "tumor_spheroid",
        "method": "scaffold_free",
        "profile": ConstructProfile(
            target_tissue="tumor",
            cell_types=["MCF-7", "fibroblasts"],
            scaffold_material="Matrigel",
            stiffness_kpa=0.5,
            cell_density_per_ml=10e6,
            experimental_goal="drug_screening",
        ),
        "title": "Tumor Spheroid — Scaffold-Free",
    },
    {
        "name": "liver_organoid",
        "method": "organoid",
        "profile": ConstructProfile(
            target_tissue="liver",
            cell_types=["HepG2"],
            scaffold_material="Matrigel",
            stiffness_kpa=1.0,
            cell_density_per_ml=8e6,
            experimental_goal="disease_modeling",
        ),
        "title": "Liver Organoid",
    },
    {
        "name": "muscle_acoustic",
        "method": "acoustic_aggregation",
        "profile": ConstructProfile(
            target_tissue="muscle",
            cell_types=["myoblasts"],
            scaffold_material="collagen",
            stiffness_kpa=15.0,
            cell_density_per_ml=3e6,
            experimental_goal="basic_research",
        ),
        "title": "Muscle — Acoustic Aggregation",
    },
]


def main():
    print(f"Generating gallery renders in {GALLERY_DIR}/")
    for item in DEMO_CONSTRUCTS:
        name = item["name"]
        profile = item["profile"]
        title = item["title"]

        fig = render_construct_3d(profile=profile, title=title)
        png_bytes = export_figure_png(fig, width=1200, height=800)

        out_path = GALLERY_DIR / f"{name}.png"
        out_path.write_bytes(png_bytes)
        print(f"  {out_path} ({len(png_bytes):,} bytes)")

    # Write gallery index
    index = {
        "generated": "2026-03-08",
        "constructs": [
            {
                "name": item["name"],
                "title": item["title"],
                "tissue": item["profile"].target_tissue,
                "method": item.get("method", "unknown"),
                "file": f"{item['name']}.png",
            }
            for item in DEMO_CONSTRUCTS
        ],
    }
    (GALLERY_DIR / "index.json").write_text(
        json.dumps(index, indent=2), encoding="utf-8"
    )
    print(f"\nGallery index written. {len(DEMO_CONSTRUCTS)} renders generated.")


if __name__ == "__main__":
    main()
