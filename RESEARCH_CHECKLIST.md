# Stromalytix Parameter Library — Research Checklist

This document lists every parameter table that must be populated from published
literature to ground the CC3D simulation engine. Each section describes the
table, its JSON schema, target entry count, and seed papers to start from.

All curated data goes into `data/parameters/<table>.json`.

---

## How to Use This Checklist

1. Pick a table below.
2. Open the seed papers listed — read the **methods** and **supplementary tables**.
3. For each relevant data point, create a JSON entry matching the schema.
4. Record the DOI and (if available) PMID. Note measurement method and conditions.
5. Mark the entry as `"confidence": "high"` if the value was directly measured and
   reported, `"medium"` if inferred from a closely analogous system, or `"low"`
   if back-calculated or estimated.
6. Commit entries to the corresponding JSON file in `data/parameters/`.

**Priority order:** O2 Transport > Proliferation > Scaffold Materials > Adhesion.
O2 transport and proliferation are the Tier 1 parameters that determine whether
a tissue construct is viable. Scaffold materials support scaffold geometry
generation. Adhesion values are important but have wider variance between
sources and can initially be set qualitatively.

---

## Entry Schema (all tables)

Every entry in every table follows this base schema. Tables may add extra
fields as noted in each section.

```json
{
  "id": "unique_string_id",
  "parameter": "parameter_name",
  "value": 0.0,
  "unit": "SI or standard unit",
  "material": "scaffold material or null",
  "cell_type": "cell type or null",
  "conditions": "temperature, pH, media, etc.",
  "confidence": "high | medium | low",
  "doi": "10.xxxx/...",
  "pmid": "PubMed ID or null",
  "notes": "measurement method, caveats",
  "temporal_relevance": "all | regime_1 | regime_2 | regime_3 | regime_4"
}
```

---

## Table 1: O2 Transport (`data/parameters/o2_transport.json`)

### Target: ~40 entries (20 diffusion + 20 consumption)

### 1a. O2 Diffusion Coefficients in Hydrogels

| Field      | Description                                  |
|------------|----------------------------------------------|
| parameter  | `"D_o2"`                                     |
| value      | Diffusion coefficient in cm²/s               |
| unit       | `"cm2/s"`                                    |
| material   | Hydrogel name and concentration              |
| conditions | Temperature, buffer/media, crosslink density |

**Seed papers:**

- McMurtrey RJ (2016) "Analytic models of oxygen and nutrient diffusion,
  metabolism dynamics, and architecture optimization in three-dimensional
  tissue constructs with applications and insights in cerebral organoids."
  DOI: 10.1089/ten.tec.2015.0375
  — Comprehensive table of O2 diffusion in various matrices.

- Demol J et al. (2011) "Toward a 3D model of bone regeneration in a
  scaffold: oxygen diffusion and cell dynamics."
  — O2 diffusion in collagen and CaP scaffolds.

- Ehsan SM, George SC (2013) "Vessel network formation in response to
  intermittent hypoxia."
  — O2 in fibrin gels.

- Nichol JW et al. (2010) "Cell-laden microengineered gelatin methacrylate
  hydrogels."
  DOI: 10.1016/j.biomaterials.2010.01.018
  — GelMA mechanical and transport properties.

- Place TL et al. (2017) "Limitations of oxygen delivery to cells in
  culture."
  — O2 transport in standard culture geometries (useful for boundary
  condition validation).

**Typical value ranges:**

| Material          | D_O2 (cm²/s)        |
|-------------------|----------------------|
| Water (37°C)      | 2.8 × 10⁻⁵          |
| GelMA 5%          | 1.8–2.2 × 10⁻⁵      |
| Collagen 2 mg/mL  | 2.0–2.5 × 10⁻⁵      |
| Fibrin 10 mg/mL   | 1.5–2.0 × 10⁻⁵      |
| Alginate 2%       | 1.2–1.8 × 10⁻⁵      |
| Matrigel           | 1.5–2.0 × 10⁻⁵      |

### 1b. O2 Consumption Rates per Cell Type

| Field      | Description                              |
|------------|------------------------------------------|
| parameter  | `"Q_o2"`                                 |
| value      | Consumption rate                         |
| unit       | `"mol/cell/s"` or `"amol/cell/s"`        |
| cell_type  | Cell line or primary cell name           |
| conditions | Passage, media, O2 tension, confluence   |

**Seed papers:**

- Wagner BA et al. (2011) "The rate of oxygen utilization by cells."
  DOI: 10.1016/j.freeradbiomed.2011.05.024
  — Canonical reference. Table of O2 consumption rates for >20 cell types.

- Pattappa G et al. (2011) "The metabolism of human mesenchymal stem cells
  during proliferation and differentiation."
  DOI: 10.1002/jcp.22010
  — MSC O2 consumption under normoxia and hypoxia.

- Metzen E, Wolff M, Fandrey J, Jelkmann W (1995) "Pericellular PO2 and
  O2 consumption in monolayer cell cultures."
  — Classic dataset for common cell lines.

**Typical value ranges:**

| Cell type                | Q_O2 (amol/cell/s) |
|--------------------------|---------------------|
| HepG2                    | 30–80               |
| Primary hepatocytes      | 50–200              |
| MSCs                     | 5–20                |
| Fibroblasts (3T3)        | 10–30               |
| Cardiomyocytes (iPSC)    | 20–60               |
| HEK293                   | 10–25               |
| MCF-7                    | 15–40               |
| Caco-2                   | 20–50               |

---

## Table 2: Proliferation Kinetics (`data/parameters/proliferation.json`)

### Target: ~30 entries

### Extra fields

| Field                       | Description                                    |
|-----------------------------|------------------------------------------------|
| parameter                   | `"doubling_time"` or `"contact_inhibition"`    |
| value                       | Hours (doubling) or cells/cm² (CI threshold)   |
| unit                        | `"hours"` or `"cells/cm2"`                     |
| substrate_stiffness_kpa     | Substrate stiffness if relevant                |
| three_d_penalty_factor      | Ratio of 3D to 2D doubling time (if known)     |
| o2_dependence               | "normoxic" or O2 tension if measured at hypoxia |

**Seed papers:**

- ATCC cell line datasheets (atcc.org) — baseline doubling times for all
  common cell lines. Start here for the canonical 2D values.

- Freshney RI, "Culture of Animal Cells" (7th ed.) — comprehensive doubling
  time tables and contact inhibition discussion.

- Engler AJ et al. (2006) "Matrix elasticity directs stem cell lineage
  specification." DOI: 10.1016/j.cell.2006.06.044
  — Stiffness-dependent MSC proliferation and differentiation.

- Baker BM, Chen CS (2012) "Deconstructing the third dimension: how 3D
  culture microenvironments alter cellular cues."
  DOI: 10.1242/jcs.079509
  — 2D vs 3D proliferation rate comparisons.

- Tibbitt MW, Anseth KS (2009) "Hydrogels as extracellular matrix mimics
  for 3D cell culture."
  DOI: 10.1002/bit.22361
  — Proliferation in hydrogels, contact inhibition in 3D.

- Keith B, Simon MC (2007) "Hypoxia-inducible factors, stem cells, and
  cancer." DOI: 10.1016/j.cell.2007.01.003
  — O2 dependence of proliferation.

**Typical value ranges:**

| Cell type               | Doubling time (2D) | 3D penalty factor |
|-------------------------|--------------------|-------------------|
| HEK293                  | 20–24 h            | 1.5–2.0×          |
| HeLa                    | 20–24 h            | 1.5–2.5×          |
| MCF-7                   | 29–35 h            | 2.0–3.0×          |
| 3T3 fibroblasts         | 20–26 h            | 1.5–2.0×          |
| MSCs (bone marrow)      | 30–40 h            | 2.0–3.0×          |
| iPSC-cardiomyocytes     | Rarely divide      | N/A               |
| Primary hepatocytes     | Rarely divide      | N/A               |
| HepG2                   | 24–30 h            | 2.0–3.0×          |
| HUVEC                   | 18–24 h            | 2.0–3.0×          |
| Caco-2                  | 40–60 h            | 2.0–3.0×          |

**Contact inhibition saturation densities (2D):**

| Cell type       | Saturation (cells/cm²) |
|-----------------|------------------------|
| 3T3 fibroblasts | 3–5 × 10⁴             |
| HeLa            | 1–2 × 10⁵             |
| Caco-2          | 5–8 × 10⁵             |
| HUVEC           | 5–8 × 10⁴             |

---

## Table 3: Scaffold Material Properties (`data/parameters/scaffold_materials.json`)

### Target: ~25 entries

### Extra fields

| Field                  | Description                               |
|------------------------|-------------------------------------------|
| parameter              | `"stiffness"`, `"degradation_rate"`, `"swelling_ratio"`, `"pore_size"` |
| scaffold_type          | `"rigid"` or `"degradable"`               |
| concentration          | Material concentration (e.g., "5%", "2 mg/mL") |
| crosslink_density      | If known (qualitative: low/medium/high)   |
| fabrication_method     | "casting", "bioprinting", "electrospinning", etc. |

**Seed papers:**

- Yue K et al. (2015) "Synthesis, properties, and biomedical applications
  of gelatin methacryloyl (GelMA) hydrogels."
  DOI: 10.1016/j.biomaterials.2015.08.045
  — Comprehensive GelMA mechanical data across concentrations.

- Caliari SR, Burdick JA (2016) "A practical guide to hydrogels for cell
  culture." DOI: 10.1038/nmeth.3839
  — Comparative stiffness, degradation, and swelling for collagen, fibrin,
  GelMA, PEG, alginate, HA. Excellent summary tables.

- Nichol JW et al. (2010) — GelMA concentration-stiffness curves.
  DOI: 10.1016/j.biomaterials.2010.01.018

- Antoine EE et al. (2014) "Review of collagen I hydrogels for bioengineered
  tissue microenvironments." DOI: 10.1089/ten.teb.2013.0399
  — Collagen I systematic characterization.

- Drury JL, Mooney DJ (2003) "Hydrogels for tissue engineering: scaffold
  design variables and applications."
  DOI: 10.1016/S0142-9612(03)00340-5

**Typical value ranges:**

| Material           | Stiffness (kPa) | Degradation half-life | Swelling ratio |
|--------------------|-----------------|-----------------------|----------------|
| GelMA 3%           | 1–3             | 7–14 days (enzymatic) | 1.3–1.5        |
| GelMA 5%           | 3–8             | 14–28 days            | 1.2–1.4        |
| GelMA 10%          | 15–30           | 28–56 days            | 1.1–1.2        |
| Collagen I 2mg/mL  | 0.5–2           | 7–14 days (MMP)       | 1.0–1.1        |
| Collagen I 4mg/mL  | 2–5             | 14–21 days            | 1.0–1.1        |
| Fibrin 5mg/mL      | 0.5–2           | 3–7 days (plasmin)    | 1.0–1.1        |
| Fibrin 10mg/mL     | 1–3             | 7–14 days             | 1.0–1.1        |
| Alginate 2%        | 5–15            | Stable (no enzyme)    | 1.0–1.1        |
| Matrigel            | 0.1–0.5         | 3–7 days              | 1.0–1.2        |
| PCL (3D printed)   | 300,000–400,000 | Months–years          | N/A (rigid)    |
| PLGA 50:50         | 1,000–3,000     | 4–8 weeks             | 1.0            |
| PDMS (Sylgard 184) | 500–3,000       | Stable (non-degrad.)  | N/A (rigid)    |

---

## Table 4: Cell-Scaffold Adhesion (`data/parameters/adhesion.json`)

### Target: ~30 entries

### Extra fields

| Field             | Description                                       |
|-------------------|---------------------------------------------------|
| parameter         | `"J_cell_scaffold"` or `"J_cell_cell"` or `"J_cell_medium"` |
| value             | CC3D J value (arbitrary energy units) or qualitative strength |
| qualitative       | `"strong"`, `"moderate"`, `"weak"`, `"none"`      |
| measurement_method| `"AFM"`, `"micropipette"`, `"centrifugation"`, `"qualitative_assay"`, `"cc3d_calibrated"` |
| substrate         | Scaffold material name                            |

**Seed papers:**

- Foty RA, Steinberg MS (2005) "The differential adhesion hypothesis:
  a direct evaluation." DOI: 10.1016/j.ydbio.2004.11.012
  — Canonical adhesion energy measurements between cell types.

- Glazier JA, Graner F (1993) "Simulation of the differential adhesion
  driven rearrangement of biological cells."
  DOI: 10.1103/PhysRevE.47.2128
  — Original GGH model with J value framework.

- Swat MH et al. (2012) "Multi-scale modeling of tissues using
  CompuCell3D." DOI: 10.1007/978-1-61779-510-7_13
  PMID: 22482955
  — CC3D tutorial with standard J value tables for common configurations.

- Paluch EK et al. (2015) "Mechanotransduction: use the force(s)."
  DOI: 10.1186/s12915-015-0150-4
  — Cell-substrate adhesion forces across substrates.

- Murphy CM, O'Brien FJ (2010) "Understanding the effect of mean pore
  size on cell activity in collagen-glycosaminoglycan scaffolds."
  DOI: 10.1007/s10856-010-4199-8
  — Cell attachment and spreading on scaffolds of different architectures.

**Qualitative adhesion guide (for initial parameterisation):**

| Cell type / substrate    | Adhesion  | Suggested J (lower = stronger) |
|--------------------------|-----------|--------------------------------|
| Fibroblast / collagen    | Strong    | 2–5                            |
| Fibroblast / GelMA       | Strong    | 3–6                            |
| MSC / collagen           | Strong    | 2–5                            |
| MSC / GelMA              | Moderate  | 5–10                           |
| HUVEC / fibronectin      | Strong    | 2–4                            |
| HUVEC / plain GelMA      | Moderate  | 6–10                           |
| HepG2 / collagen         | Moderate  | 5–10                           |
| Epithelial / epithelial  | Strong    | 1–3                            |
| Mesenchymal / mesenchymal| Moderate  | 5–8                            |
| Any cell / medium (void) | Weak      | 12–20                          |
| Any cell / PCL           | Moderate  | 8–14                           |
| Any cell / untreated PDMS| Weak      | 14–20                          |

Note: J values in CC3D are relative. The *ratios* between J_cell_cell,
J_cell_scaffold, and J_cell_medium determine behavior. Absolute values
can be scaled. Standard convention: J_cell_medium > J_cell_scaffold >
J_cell_cell for adherent cells (cells prefer each other and scaffold
over floating in void).

---

## Table 5: Gel Penetration / Migration (optional, Tier 2)

### Target: ~15 entries (lower priority)

| Field      | Description                                    |
|------------|------------------------------------------------|
| parameter  | `"migration_speed"`, `"MMP_secretion_rate"`, `"optimal_ecm_density"` |
| value      | Speed in um/h, secretion in pg/cell/day, density in mg/mL |

**Seed papers:**

- Zaman MH et al. (2006) "Migration of tumor cells in 3D matrices is
  governed by matrix stiffness along with cell-matrix adhesion and
  proteolysis." DOI: 10.1073/pnas.0606087103

- Wolf K et al. (2013) "Physical limits of cell migration: control by
  ECM space and nuclear deformation and tuning by proteolysis and
  traction force." DOI: 10.1083/jcb.201210152

- Ehrbar M et al. (2011) "Elucidating the role of matrix stiffness in
  3D cell migration and remodeling."
  DOI: 10.1016/j.bpj.2010.11.082

---

## Research Workflow Tips

1. **Start with reviews, not primary papers.** Caliari & Burdick (2016),
   Yue et al. (2015), and Wagner et al. (2011) each contain tables with
   10+ data points that can be entered directly.

2. **Use supplementary materials.** Parameter values are almost always in
   supplementary tables, not the main text.

3. **Record measurement method.** "AFM" vs. "rheometry" vs. "tensile test"
   for stiffness matters — they don't always agree.

4. **Note the matrix concentration.** "GelMA" is not one material. 3% GelMA
   has different properties from 10% GelMA. Always record concentration.

5. **Cross-reference O2 data.** If a paper reports viability at different
   scaffold thicknesses, you can back-calculate whether their O2 parameters
   are consistent with the diffusion-consumption model.

6. **Use the temporal relevance field.** Parameters that only matter during
   seeding (regime_1) vs. proliferative expansion (regime_3) should be
   tagged accordingly so the simulation can prioritize computation.

---

## Estimated Effort

| Table                | Entries | Estimated hours |
|----------------------|---------|-----------------|
| O2 Transport         | ~40     | 8–12            |
| Proliferation        | ~30     | 6–8             |
| Scaffold Materials   | ~25     | 6–8             |
| Adhesion             | ~30     | 8–12            |
| Gel Penetration      | ~15     | 4–6             |
| **Total**            | **~140**| **32–46**       |
