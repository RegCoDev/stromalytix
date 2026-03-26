# Cellular Agriculture — Research Checklist

What needs to be sourced from the literature to make Stromalytix useful for
cultivated meat / structured protein applications. Organised by parameter
table, priority tier, and estimated difficulty.

---

## 1. `o2_transport.json` — O₂ Diffusion & Consumption

### What we have
- D_o2 in collagen, alginate, fibrin, agarose, GelMA (estimated), water
- Q_o2 for HepG2, HUVEC, chondrocytes, generic fibroblast
- Km_o2 (generic mammalian, hepatocyte, chondrocyte)

### What we need for cell ag

| Parameter | Cell/Material | Priority | Notes |
|-----------|--------------|----------|-------|
| Q_o2 | Bovine satellite cells (BSC) | **Tier 1** | Primary cell type for cultivated beef. Likely ~2–5 × 10⁻¹⁷ mol/cell/s based on myoblast metabolism. Check: Post et al. 2013, Stout et al. 2023 |
| Q_o2 | C2C12 mouse myoblasts | **Tier 1** | Most-used model line. Extensive data in exercise physiology literature |
| Q_o2 | Chicken satellite cells | **Tier 1** | Poultry is the largest cell-ag segment. Check: Zhu et al. 2022 (Good Food Institute reports) |
| Q_o2 | Porcine satellite cells | Tier 2 | Less common but commercially relevant |
| Q_o2 | Preadipocytes / adipocytes | Tier 2 | Fat tissue constructs; lipid-loaded cells may have different O₂ demand |
| Q_o2 change during differentiation | BSC (proliferating vs. fused myotube) | **Tier 1** | Metabolic switch at fusion: myotubes are more oxidative. Critical for long cultures |
| D_o2 | Textured soy protein scaffold | Tier 2 | No published data. Need to estimate from porosity/tortuosity or measure |
| D_o2 | Chitosan scaffold | Tier 2 | Some data in wound-healing literature |
| D_o2 | Cellulose / decellularized plant tissue | **Tier 1** | Apple, spinach leaf scaffolds — structurally interesting for cell ag. Check: Modulevsky et al. 2014, Gershlak et al. 2017 |
| D_o2 | Konjac glucomannan | Tier 3 | Niche but used in some structured products |

### Key insight
Myoblasts undergo a metabolic shift during differentiation — proliferating cells are glycolytic; fused myotubes switch to oxidative phosphorylation. This means Q_o2 can **increase 2–5×** during the differentiation phase, dramatically changing O₂ penetration depth mid-culture.

---

## 2. `proliferation.json` — Doubling Times & Contact Inhibition

### What we have
- Doubling times for HepG2, A549, MCF-7, HUVEC, MSC, primary hepatocytes, Caco-2, Vero, CHO
- 3D penalty factors (generic 1.2–1.5×)
- Contact inhibition thresholds (generic)

### What we need for cell ag

| Parameter | Cell Type | Priority | Notes |
|-----------|----------|----------|-------|
| Doubling time (2D) | Bovine satellite cells (primary) | **Tier 1** | ~24–36 h in growth medium (10% FBS + FGF-2). Highly passage-dependent. Check: Ding et al. 2018, Stout et al. 2023 |
| Doubling time (2D) | Bovine satellite cells (serum-free) | **Tier 1** | Critical for cost modeling. Typically 1.5–2× slower without FBS. Check: Kolkmann et al. 2020 |
| Doubling time (2D) | C2C12 | **Tier 1** | ~14–18 h in 10% FBS. Well-characterised. ATCC datasheet + many papers |
| Doubling time (2D) | Chicken satellite cells | **Tier 1** | ~20–30 h. Check: Zhu et al. 2022 |
| Doubling time (2D) | Porcine satellite cells | Tier 2 | ~24–40 h depending on isolation protocol |
| Doubling time (2D) | Preadipocytes (3T3-L1 model) | Tier 2 | ~20 h in growth phase. Stops at confluence → differentiation trigger |
| Doubling time (2D) | Bovine preadipocytes (primary) | Tier 2 | Less data than 3T3-L1 |
| 3D penalty factor | Satellite cells in hydrogels | **Tier 1** | Likely 1.5–3× slower than 2D. Encapsulated cells may not proliferate well; surface-seeded do better |
| Contact inhibition density | Myoblasts | **Tier 1** | Myoblasts fuse at confluence rather than arresting — this is differentiation, not inhibition. The model needs to trigger a differentiation switch, not a growth stop |
| Max passage before senescence | BSC, chicken SC | Tier 2 | Satellite cells have limited expansion capacity (~15–25 doublings for primary). Critical for scale-up feasibility |

### Key insight
Satellite cells don't undergo classic contact inhibition — they **fuse into multinucleated myotubes** at high density. The CC3D model needs a "differentiation trigger" that replaces the contact-inhibition growth arrest with a fusion event. This is qualitatively different from most tissue engineering cell types.

---

## 3. `scaffold_materials.json` — Material Properties

### What we have
- GelMA, collagen, fibrin, alginate, Matrigel, PCL, PLGA, PDMS, PEG, HA, silk fibroin
- Properties: stiffness, degradation_rate, swelling_ratio, pore_size

### What we need for cell ag

| Parameter | Material | Priority | Notes |
|-----------|----------|----------|-------|
| Stiffness (kPa) | Textured soy protein (TSP) | **Tier 1** | Primary edible scaffold candidate. ~10–100 kPa depending on hydration. Check: Kyriakopoulou et al. 2021 |
| Stiffness (kPa) | Chitosan | Tier 2 | ~1–50 kPa depending on crosslinking/deacetylation. Biomedical literature is extensive |
| Stiffness (kPa) | Cellulose (plant-derived) | **Tier 1** | Decellularised apple: ~1–5 kPa. Spinach leaf: ~10–30 kPa. Check: Modulevsky et al. 2014 |
| Stiffness (kPa) | Starch gel | Tier 2 | ~5–50 kPa. Food science literature, not biomedical |
| Stiffness (kPa) | Konjac glucomannan | Tier 3 | ~0.5–10 kPa. Used in food products (shirataki noodles) |
| Stiffness (kPa) | Zein (corn protein) | Tier 3 | Electrospun or cast films. ~50–500 kPa |
| Pore size (µm) | TSP | **Tier 1** | Naturally porous: ~50–500 µm depending on processing |
| Pore size (µm) | Decellularised plant tissue | **Tier 1** | Retains natural vascular channels (~20–200 µm) |
| Degradation rate | TSP, chitosan, starch, zein | Tier 2 | Enzymatic degradation by cell-secreted proteases; varies widely |
| Swelling ratio | TSP, chitosan, starch, konjac | Tier 2 | Important for dimensional stability during culture |
| Food-grade status | All edible scaffolds | **Tier 1** | Flag: is this material food-safe / GRAS? Binary yes/no per material |

### Key insight
The "food-grade" constraint eliminates many well-characterised biomedical materials (Matrigel, PEG, PDMS) from cell-ag applications. The edible scaffold literature is 5–10 years behind biomedical scaffolds in terms of quantitative characterisation — most cell-ag papers report qualitative "cells adhered and proliferated" without rigorous mechanical testing.

---

## 4. `adhesion.json` — CC3D J-Values & Surface Tension

### What we have
- J_cell_cell, J_cell_scaffold, J_cell_medium for generic epithelial, mesenchymal, neural, endothelial
- Tissue surface tension (Foty & Steinberg 2005)

### What we need for cell ag

| Parameter | Cell Type | Priority | Notes |
|-----------|----------|----------|-------|
| J_cell_cell | Myoblasts (pre-fusion) | **Tier 1** | Need to distinguish pre-fusion (moderate adhesion) vs. fusing (very high adhesion). Myoblast fusion is a specific adhesion event mediated by myomaker/myomerger |
| J_cell_cell | Myotubes (post-fusion) | **Tier 1** | Fused myotubes are tightly bonded. Very low J (= strong adhesion in CC3D convention) |
| J_cell_scaffold | Satellite cells on RGD-modified hydrogels | **Tier 1** | Most cell-ag scaffolds need RGD functionalisation. Adhesion depends on RGD density |
| J_cell_scaffold | Myoblasts on collagen/gelatin-coated TSP | **Tier 1** | Gelatin coating is common for edible scaffolds. Gelatin = denatured collagen |
| J_cell_cell | Adipocytes | Tier 2 | Adipocytes are loosely adherent. Higher J than myoblasts |
| J_cell_medium | Satellite cells | **Tier 1** | Determines whether cells spread on scaffold or remain rounded. Critical for alignment |
| Surface tension | Skeletal muscle tissue (native) | Tier 2 | Benchmark for how tightly the cultivated tissue should cohere |

### Key insight
Myoblast fusion is NOT captured by standard CC3D adhesion dynamics. It requires a custom steppable that merges adjacent myoblast cells into a single elongated multinucleated cell (myotube). This is a **new CC3D model component** — not just a parameter lookup. The J-values still matter for positioning cells before fusion, but the fusion event itself needs explicit modeling.

---

## 5. `gel_penetration.json` — Migration & Infiltration

### What we have
- Migration speeds for MDA-MB-231, HT-1080, fibroblasts, HUVECs, MSCs in collagen/fibrin/Matrigel/GelMA/alginate
- MMP secretion rates for fibroblasts, MSCs, cancer cells
- Critical pore size (7 µm generic)
- Nuclear diameter (12 µm generic)

### What we need for cell ag

| Parameter | Cell Type | Priority | Notes |
|-----------|----------|----------|-------|
| Migration speed | Bovine satellite cells in collagen | **Tier 1** | Satellite cells are moderately migratory. ~5–15 µm/h in loose gels. Check wound healing / regeneration literature (in vivo) |
| Migration speed | C2C12 in GelMA | Tier 2 | C2C12 migration is well-studied in 2D but 3D data in hydrogels is sparse |
| Migration speed | Satellite cells in TSP scaffold | **Tier 1** | No published data. This is a key unknownfor cell ag |
| Migration speed | Satellite cells on decellularised plant | **Tier 1** | Cells migrate along preserved vascular channels. Check: Allan et al. 2021 |
| MMP secretion | Satellite cells (MMP-2, MMP-9) | Tier 2 | Satellite cells secrete MMPs during muscle regeneration. In vitro data is limited |
| Nuclear diameter | Bovine satellite cells | Tier 2 | Likely ~10–14 µm, similar to other mesenchymal cells |
| Fusion distance | Myoblasts | **Tier 1** | Max distance between myoblasts that allows fusion. Not a migration parameter per se, but critical for CC3D: cells within ~1 cell diameter of each other will fuse if in differentiation medium |

### Key insight
In cell ag, "migration" often means something different than in tissue engineering. Satellite cells in porous scaffolds migrate to coat surfaces; in gels they remodel and penetrate. But the unique cell-ag event is **alignment and fusion** — myoblasts line up along fibers or surface topography and then fuse. The migration model needs to capture this directional bias, not just speed.

---

## 6. New Table Needed: `differentiation.json`

This doesn't exist yet and is **essential for cell ag**. Cell ag constructs go through distinct phases:

| Parameter | Cell Type | Priority | Notes |
|-----------|----------|----------|-------|
| Differentiation trigger | C2C12 | **Tier 1** | Switch to 2% horse serum at confluence. Fusion begins ~24–48 h later |
| Differentiation trigger | BSC (primary) | **Tier 1** | Low serum + IGF-1. Fusion takes 3–5 days |
| Fusion efficiency (%) | C2C12 | **Tier 1** | ~60–80% in 2D. Lower in 3D (~30–50%). Check: Liao et al. 2008 |
| Fusion efficiency (%) | BSC in 3D scaffold | **Tier 1** | Very limited data. Key gap |
| Myotube diameter (µm) | C2C12 | Tier 2 | ~10–20 µm in 2D; affects CC3D target volume |
| Myotube length (µm) | C2C12 | Tier 2 | ~200–500 µm. Determines multinucleation |
| Lipid accumulation rate | 3T3-L1 / primary preadipocytes | Tier 2 | µg lipid/cell/day post-differentiation induction |
| Lipid accumulation trigger | 3T3-L1 | Tier 2 | Insulin + dexamethasone + IBMX cocktail, 48–72 h induction |
| Maturation marker expression | Myosin heavy chain (MHC) | **Tier 1** | % MHC+ cells at day 7, 14, 21 in 3D. This is the primary quality readout |
| Creatine kinase activity | C2C12 / BSC | Tier 2 | Functional maturation marker |

### Key insight
The **proliferation-to-differentiation switch** is the defining event in cell-ag culture. It's triggered by serum withdrawal and growth factor changes, and it fundamentally alters cell behavior: cells stop dividing, start fusing, elongate, and begin expressing muscle proteins. The CC3D steppable needs to model this as a discrete phase transition, not a continuous process.

---

## 7. New Table Needed: `serum_free_media.json`

Cost of medium is >50% of cultivated meat production cost. Serum-free formulations are essential for commercial viability.

| Parameter | Component | Priority | Notes |
|-----------|----------|----------|-------|
| FGF-2 concentration (ng/mL) | Growth phase | **Tier 1** | Typically 5–100 ng/mL. Single most expensive component. Check: Stout et al. 2023 |
| IGF-1 concentration (ng/mL) | Differentiation phase | **Tier 1** | ~10–100 ng/mL. Required for fusion |
| TGF-β concentration (ng/mL) | Differentiation phase | Tier 2 | ~1–10 ng/mL. Pro-fibrotic in some contexts |
| Transferrin concentration (µg/mL) | Both phases | Tier 2 | Iron carrier, replaces serum function |
| Insulin concentration (µg/mL) | Both phases | Tier 2 | ~5–10 µg/mL. Metabolic support |
| Basal medium | Growth & differentiation | **Tier 1** | DMEM/F12 is standard. Essential 8 formulation for iPSCs sometimes adapted |
| Cost per liter ($) | Complete serum-free medium | Tier 2 | Currently $10–50/L at lab scale; target $1/L for commercial |
| Proliferation rate impact | Serum-free vs. 10% FBS | **Tier 1** | How much slower is growth without serum? Typically 1.5–3× penalty |

### Key insight
Medium formulation directly affects every simulation parameter — proliferation rate, differentiation efficiency, and cell metabolism all change with growth factor cocktail. The simulation should eventually be able to model the effect of medium composition changes (e.g., switching from growth medium to differentiation medium at day X).

---

## 8. CC3D Model Changes Required (Code, Not Research)

Beyond parameter data, the CC3D steppable generator needs new capabilities:

1. **Myoblast fusion steppable** — When two adjacent myoblast cells are both in "differentiation mode" and touching, merge them into a single elongated cell (myotube type). Track nuclei count.

2. **Differentiation phase transition** — At a specified MCS step (corresponding to the medium switch day), change cell behavior: stop mitosis, enable fusion, switch Q_o2 profile.

3. **Adipocyte lipid accumulation** — For fat constructs: after differentiation trigger, cells swell (increase target volume) to model lipid loading.

4. **Alignment field** — Optional: bias cell elongation and migration along scaffold fiber direction (for structured whole-cut products).

5. **Co-culture logic** — Support seeding both myoblasts and preadipocytes with different adhesion energies and differentiation timelines (for marbled meat).

---

## Priority Summary

### Must-have for a credible cell-ag demo (Tier 1)
- Q_o2 for satellite cells / C2C12 (proliferating AND differentiated)
- Doubling time for BSC and C2C12 (with serum and serum-free)
- TSP and decellularised plant scaffold properties (stiffness, pore size)
- Myoblast J-values (pre-fusion, post-fusion)
- Differentiation parameters (trigger, fusion efficiency, timeline)
- Food-grade material flags

### Important but can use estimates initially (Tier 2)
- Chicken and porcine satellite cell kinetics
- Adipocyte-specific parameters
- Edible scaffold degradation rates
- MMP secretion for satellite cells
- Serum-free medium cost and performance data
- Max passage / senescence limits

### Nice-to-have refinements (Tier 3)
- Konjac, zein, starch scaffold characterisation
- Creatine kinase / functional maturation kinetics
- Alignment / anisotropy modeling parameters

---

## Recommended Search Strategy

1. **Start with review papers**: Post et al. 2020 "Scientific, sustainability and regulatory challenges of cultured meat" (Nature Food); Stout et al. 2023 (cultivated meat methods); GFI technical reports.

2. **C2C12 as proxy**: C2C12 is the most data-rich myoblast line. Use it as the default for demo, with BSC as the "upgrade path."

3. **Food science journals**: Unlike tissue engineering (Biomaterials, Acta Biomat), cell-ag data lives in Journal of Food Science, Food Hydrocolloids, Trends in Food Science & Technology, npj Science of Food.

4. **Preprint servers**: Cell ag moves fast. Check bioRxiv and the GFI publication database.

5. **Key labs to track**: Mark Post (Maastricht), David Kaplan (Tufts), Shulamit Levenberg (Technion), Amy Rowat (UCLA), Reza Ovissipour (Virginia Tech).
