# Stromalytix Parameter Library — Tables 2–5: JSON Entries + Gap Analysis

**Generated:** 2026-03-25  
**Scope:** Proliferation Kinetics, Scaffold Materials, Cell-Scaffold Adhesion, Gel Penetration/Migration  
**Total entries:** 86 (25 proliferation + 23 scaffold + 24 adhesion + 14 migration)  
**Combined with Table 1:** ~129 entries total across all five tables

---

## Table 2: Proliferation Kinetics — Summary

**File:** `data/parameters/proliferation.json`  
**Entries:** 25 (19 doubling times + 6 contact inhibition saturation densities)  
**Cell types covered:** HEK293, HEK293T, HeLa, MCF-7, NIH 3T3, hMSCs, iPSC-CMs, primary hepatocytes, HepG2, HUVEC, Caco-2, A549, CHO-K1, U87MG, MDCK, Vero, primary chondrocytes, 4T1

### Strong literature support

2D doubling times for immortalized cell lines are extremely well-characterized. ATCC product sheets, the Cytiva/HyClone comparative study, and Freshney's "Culture of Animal Cells" provide consistent, reproducible values across labs. HeLa (~24h), NIH 3T3 (~22h), A549 (~22h), and CHO-K1 (~17h) have the tightest consensus ranges.

Contact inhibition saturation densities for 3T3 (3–5 × 10⁴) and Caco-2 (5–8 × 10⁵) are well-established and functionally important — 3T3 is the canonical contact-inhibited line, while Caco-2 differentiation at confluence is a standard model for intestinal epithelium.

### Sparse or conflicting data

**HEK293 doubling time** shows the widest discrepancy of any common line: ATCC lists ~34h for the serum-free suspension variant, ResearchGate users report 18h for adherent HEK293T in 10% FBS, and Sen Lab reports 12h for optimized HEK293T cultures. The variant (parental vs. T antigen), medium (serum-free vs. 10% FBS), and growth mode (adherent vs. suspension) create a 3× range. For CC3D modeling, use 24h as a safe default for adherent HEK293 in serum-containing media.

**3D penalty factors** are the weakest parameter in this table. The checklist provides estimates of 1.5–3.0× based on Baker & Chen (2012) and general literature, but there are very few papers that directly measure the same cell line's doubling time in both 2D and 3D under otherwise identical conditions. Most 3D proliferation data comes from spheroid growth curves, which conflate proliferation with quiescence in the spheroid core due to O₂/nutrient gradients. The 2–3× penalty factors listed should be treated as order-of-magnitude estimates.

**Hypoxic proliferation dependence** is poorly characterized quantitatively. Keith & Simon (2007) describe the biology of HIF-mediated proliferation arrest, but few papers provide doubling time measurements at specific O₂ tensions (e.g., "doubling time at 2% O₂ vs. 20% O₂"). This is a critical gap for CC3D simulations of thick constructs where O₂ gradients create spatially varying proliferation rates.

### Recommendations

1. **Measure 3D penalty factors directly** for the 3–5 most important cell types (MSCs, HUVECs, HepG2, fibroblasts) in GelMA and collagen at defined concentrations, using EdU incorporation or Ki67 staining to count dividing cells.
2. **Hypoxic doubling time measurements** at 1%, 2%, 5% O₂ would enable CC3D to implement O₂-dependent proliferation rather than using a simple on/off threshold.
3. **Contact inhibition in 3D** is conceptually different from 2D — cells experience confinement and neighbor pressure differently. A density-dependent growth arrest parameter for 3D would improve simulation realism.

---

## Table 3: Scaffold Material Properties — Summary

**File:** `data/parameters/scaffold_materials.json`  
**Entries:** 23 (12 stiffness + 4 degradation + 2 swelling + 1 pore size + 4 additional)  
**Materials covered:** GelMA (3%, 5%, 10%), Collagen I (2–4 mg/mL), Fibrin (5–10 mg/mL), Alginate 2%, Matrigel, PCL, PLGA 50:50, PDMS, PEG-DA, MeHA, Collagen-GAG, Silk fibroin

### Strong literature support

**GelMA stiffness** is the strongest dataset thanks to Yue et al. (2015) and Nichol et al. (2010), who provide concentration-resolved compressive modulus data with well-defined crosslinking conditions. The relationship between GelMA concentration and stiffness is nearly linear from 3–10%, making interpolation straightforward.

**Collagen I stiffness** is well-characterized by Antoine et al. (2014) across concentrations, and Caliari & Burdick (2016) provide an excellent cross-material comparison table.

**PCL and PLGA bulk moduli** are well-established from polymer engineering literature.

### Sparse or conflicting data

**Degradation rates** are the weakest category. Published values vary enormously because degradation depends on cell density (enzyme source), enzyme concentration, scaffold geometry, and culture medium composition. The half-life values listed are rough central estimates — actual degradation in a cell-laden construct can be 2–5× faster due to local MMP secretion. For CC3D, degradation should ideally be modeled as a cell-density-dependent process rather than a fixed rate constant.

**Stiffness measurement method** introduces systematic bias: compressive modulus (unconfined compression) gives different values than storage modulus (rheometry) for the same material. Yue et al. (2015) report compressive modulus, while many fibrin and Matrigel papers report rheometric G'. As a rough conversion, E ≈ 3G' for incompressible hydrogels (Poisson ratio ≈ 0.5), but this is approximate.

**Pore size** data is sparse because it depends heavily on fabrication method. Lyophilized GelMA has very different porosity than directly photocrosslinked GelMA hydrogel (which has mesh-scale porosity, not µm-scale pores). For CC3D, the relevant parameter is the effective mesh size that determines cell migration, not the macroscopic pore structure.

**Silk fibroin and PEG hydrogels** have tunable properties spanning 3+ orders of magnitude in stiffness, making single-value entries misleading. The entries provided are for common low-concentration formulations.

### Recommendations

1. **Standardize measurement method reporting.** Always record whether stiffness was measured by compression, rheometry, AFM, or tensile testing, and at what strain rate and temperature.
2. **Cell-dependent degradation rates** should be modeled as a function of cell density and MMP secretion rate (Table 5) rather than using fixed half-lives.
3. **Composite bioink properties** (GelMA-alginate blends, GelMA-HAMA, etc.) are almost entirely uncharacterized and should be measured for any blend used in bioprinting.

---

## Table 4: Cell-Scaffold Adhesion — Summary

**File:** `data/parameters/adhesion.json`  
**Entries:** 24 (10 J_cell_scaffold + 6 J_cell_cell + 2 J_cell_medium + 3 adhesion_energy + 3 additional)  
**Interactions covered:** Fibroblast, MSC, HUVEC, HepG2, epithelial, mesenchymal, chondrocyte on collagen, GelMA, fibrin, fibronectin, PCL, PDMS, alginate, Matrigel, HA

### Strong literature support

**Foty & Steinberg (2005)** remains the gold standard for quantitative tissue surface tension measurements. Their direct adhesion energy data (L929 = 22.8 mJ/m², CHO = 14.0 mJ/m²) are the most rigorous measurements available and validate the differential adhesion hypothesis that underlies CC3D's GGH model.

**Glazier & Graner (1993)** established the J-value framework, and **Swat et al. (2012)** provide practical CC3D J-value tables that have been widely used in the modeling community.

### Sparse or conflicting data

**Nearly all J_cell_scaffold values are qualitative estimates**, not direct measurements. The fundamental problem is that CC3D J-values are model parameters, not physical quantities — they cannot be directly measured by AFM or micropipette aspiration. Instead, they must be calibrated by running simulations and comparing cell sorting, spreading, and morphology outcomes to experimental observations. The values provided follow the community convention (lower J = stronger adhesion) but should be treated as starting points for calibration, not ground truth.

**Heterotypic adhesion** (epithelial/mesenchymal, different cell types in co-culture) is poorly characterized. This matters for bioprinting constructs with multiple cell types — cell sorting behavior depends on J_cell_cell ratios between different cell types.

**Substrate modification effects** (plasma treatment of PCL, RGD-functionalization of alginate, fibronectin coating of GelMA) can shift J values by 5–10 units but are rarely quantified.

### Recommendations

1. **Calibration simulations** are essential. Run CC3D cell sorting experiments with different J-value sets and compare against experimental cell sorting assays (hanging drop aggregation, tissue surface tensiometry) for each specific cell type / material combination.
2. **The ratio J_cell_medium : J_cell_scaffold : J_cell_cell matters more than absolute values.** For adherent cells, maintain J_cell_medium > J_cell_scaffold > J_cell_cell.
3. **Surface treatment effects** should be parameterized as J_value modifiers rather than absolute values.

---

## Table 5: Gel Penetration / Migration — Summary

**File:** `data/parameters/gel_penetration.json`  
**Entries:** 14 (8 migration speeds + 3 MMP secretion rates + 1 optimal ECM density + 1 nuclear diameter + 1 critical pore size)  
**Cell types covered:** MDA-MB-231, HT-1080, dermal fibroblast, HUVEC, MSC  
**Materials covered:** Collagen I (various densities), Matrigel, Fibrin, GelMA, Alginate

### Strong literature support

**Zaman et al. (2006)** and **Wolf et al. (2013)** provide the foundational quantitative framework for 3D migration: the biphasic speed-vs-density relationship, the critical pore size threshold (~7 µm), and the nuclear deformation limit. These two papers alone account for most of the quantitative migration data available.

**Wolf et al. (2013)** nuclear size limitation is particularly important for CC3D: below ~7 µm pore size, cells physically cannot squeeze through without MMP-mediated pore enlargement. This sets a hard constraint on migration in dense scaffolds.

### Sparse or conflicting data

**Migration speed in bioprinting-relevant hydrogels** (GelMA, alginate, PEG) is almost completely uncharacterized. Nearly all quantitative 3D migration data uses collagen I or Matrigel. The GelMA and alginate estimates in the table are extrapolations.

**MMP secretion rates** are difficult to measure per-cell in 3D because ELISA measures bulk secretion and cannot distinguish between active and latent MMP, or between cell-surface-bound and secreted enzyme. The values provided are order-of-magnitude estimates.

**Migration in co-culture systems** (e.g., HUVEC sprouting in MSC-laden GelMA) is functionally important for vascularized bioprinted constructs but has no standardized quantitative parameterization.

### Recommendations

1. **3D migration speed measurements in GelMA** at 3%, 5%, 10% for fibroblasts and MSCs using particle tracking or cell tracking in confocal time-lapse.
2. **Couple migration to scaffold degradation** in CC3D: cells should only migrate through degradable matrices at rates determined by MMP secretion × scaffold susceptibility, not at free-space migration speeds.
3. **Nuclear deformation sub-model** based on Wolf et al. (2013): implement a pore-size-dependent migration probability that drops sharply below the critical pore size.

---

## Cross-Table Integration Notes for CC3D

### Parameter coupling hierarchy

The five parameter tables are not independent — they form a coupled system:

1. **O₂ diffusion (Table 1a)** through the scaffold determines the **O₂ concentration profile**, which determines...
2. **O₂ consumption (Table 1b)** creates **local hypoxia** in thick constructs, which modulates...
3. **Proliferation rate (Table 2)** — cells divide slower or stop dividing in hypoxic cores, and...
4. **Migration speed (Table 5)** — hypoxia can either stimulate (chemotaxis toward O₂) or inhibit migration, while...
5. **Scaffold degradation (Table 3)** proceeds faster where cell density is high (more MMP secretion), which changes local...
6. **Adhesion (Table 4)** — as scaffold degrades, effective J_cell_scaffold changes, potentially triggering cell detachment or rearrangement.

### Recommended CC3D implementation order

1. Start with O₂ diffusion-consumption (Table 1) as a PDE field — this is the primary viability constraint.
2. Add proliferation (Table 2) with an O₂ threshold: cells divide above 1% O₂, arrest below.
3. Add adhesion (Table 4) as static J values — this determines tissue morphology.
4. Add scaffold degradation (Table 3) as a slow background process.
5. Add migration (Table 5) last — it requires the most calibration and has the most uncertainty.

### Default quick-start parameter set (all tables)

| Parameter | Symbol | Default | Unit |
|-----------|--------|---------|------|
| Generic cell doubling time (2D) | T_d | 24 | hours |
| 3D penalty factor | α_3D | 2.0 | × |
| Contact inhibition density (2D) | ρ_max | 1 × 10⁵ | cells/cm² |
| Generic hydrogel stiffness | E | 5 | kPa |
| Degradation half-life (enzymatic) | t_½ | 14 | days |
| J_cell_cell (homotypic) | J_cc | 5 | CC3D units |
| J_cell_scaffold | J_cs | 7 | CC3D units |
| J_cell_medium | J_cm | 16 | CC3D units |
| Migration speed (permissive matrix) | v_migr | 10 | µm/h |
| MMP secretion rate | R_MMP | 5 | pg/cell/day |
| Critical pore size | d_crit | 7 | µm |

---

## Entry Counts vs. Targets

| Table | Target | Delivered | Gap | Notes |
|-------|--------|-----------|-----|-------|
| O₂ Transport (Table 1) | ~40 | 43 | ✅ Met | 19 diffusion + 24 consumption |
| Proliferation (Table 2) | ~30 | 25 | 5 short | Missing: primary neurons, pancreatic β-cells, adipocytes |
| Scaffold Materials (Table 3) | ~25 | 23 | 2 short | Missing: agarose, dECM, Pluronic |
| Adhesion (Table 4) | ~30 | 24 | 6 short | Most gaps are specific cell/substrate combos |
| Gel Penetration (Table 5) | ~15 | 14 | 1 short | Missing: amoeboid migration data |
| **TOTAL** | **~140** | **129** | **11 short** | **92% of target** |

The 11-entry gap is concentrated in lower-priority parameters (specific cell/substrate adhesion pairs and niche cell types) that can be filled through targeted calibration experiments rather than literature mining.
