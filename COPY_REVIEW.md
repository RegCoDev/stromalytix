# Stromalytix Copy Review — "Simple, Fast, Fun" for Scientists

Target vibe: **Confident but not stiff. Direct. A tool that respects your time and your PhD.**

---

## LANDING / ASSESSMENT PHASE (app.py)

### Hits the vibe

| Location | Copy | Verdict |
|----------|------|---------|
| L529 | `"Stromalytix"` (title) | Clean, memorable. Works. |
| L530 | `"Compare your construct against ~8,100 published protocols"` | Great — specific number, clear value prop. |
| L707 | `"Describe your construct or answer the question..."` (chat placeholder) | Good. Natural. |
| L342 | `"3D cell culture analysis"` (sidebar subtitle) | Clear, short. |

### Needs work

| Location | Copy | Issue | Suggestion |
|----------|------|-------|------------|
| L531 | `"Describe your setup. Get parameter ranges from PubMed, risk flags, and optional 3D simulation."` | Too long for a subheader. Reads like a feature list, not a hook. | `"Describe your setup. See where you stand."` |
| L534-546 | "How Stromalytix works" expander — 3 paragraphs | Verbose. Nobody reads "How it works" blocks. The chat *is* the onboarding. | Cut to 2 bullets max or remove entirely. The chat greeting already explains the flow. |
| L536 | `"Map your bioink, scaffold, and culture conditions to published cell behavior data — adhesion, migration, proliferation."` | Sentence tries to do too much. Listing "adhesion, migration, proliferation" is jargon that doesn't help at this stage. | `"Match your protocol to what's been published."` |
| L597 | `"Optional: upload a protocol (PDF, DOCX, TXT)"` | `Optional:` prefix feels bureaucratic. | `"Upload a protocol"` — the expander itself makes it optional. |
| L644 | `"Optional: your role (for future tailoring)"` | Same problem + `"for future tailoring"` is meta/internal language. | `"Your role"` or just drop it — it says "Does not change the assistant today" which is basically telling the user it's useless. |
| L645 | `"Does not change the assistant today—optional context only."` | Actively discourages engagement. Why show it? | Either make it do something or hide it. |
| L683 | `"Initializing BioSim Copilot..."` (spinner) | "BioSim Copilot" name is used inconsistently (sidebar says "Stromalytix", here says "BioSim Copilot"). | `"Starting up..."` or use one brand name. |
| L789 | `"Querying PubMed knowledge base... Synthesizing variance report..."` | Too technical for a spinner. | `"Searching literature and building your report..."` |

---

## SIDEBAR (app.py)

### Hits the vibe

| Location | Copy | Verdict |
|----------|------|---------|
| L360 | `"Progress"` heading + checklist | Clean. Users like progress bars. |
| L382 | `"{completed_count}/{total_count} steps complete"` | Concise. |

### Needs work

| Location | Copy | Issue | Suggestion |
|----------|------|-------|------------|
| L232-236 | `"8/8 messages — usual minimum before automatic analysis..."` | Robotic. Exposes internal implementation (why 8?). | `"Almost there — keep going or hit Run analysis now."` |
| L245-248 | `"Enough messages, but the construct profile still looks incomplete."` | Passive, vague. | `"We need a few more details — keep chatting or use Run analysis now."` |
| L481 | `"Run analysis now"` button | Good label. But the help text `"Skip waiting for 8 messages / full profile"` exposes internals. | Help text: `"Jump straight to results with what you've told us so far."` |

---

## RESULTS HERO (app.py L198-224)

### Needs work

| Location | Copy | Issue | Suggestion |
|----------|------|-------|------------|
| L200 | `"At a glance"` | Generic. Every dashboard says this. | `"Your construct vs. the literature"` or just drop the heading — the metrics speak for themselves. |
| L207 | `"Library fit (feasibility)"` metric label | `"Library fit"` is unclear. Fit to what? | `"Literature match"` or `"Protocol fit"` |
| L218 | `"Red benchmark flags: none — still review Feasibility for marginal or aspirational axes."` | When there are no red flags, the message is weirdly cautious. Let the user celebrate. | `"No red flags. Check Feasibility for fine-tuning."` |
| L220-222 | `"Next step: open Methods & materials plan for prioritized measurements, gaps vs. literature ranges, and signup."` | Way too long. "Treat the profile as a working point in a larger experimental space" is philosophical fluff. | `"Next: check Methods & materials for what to measure and where you're outside published ranges."` |

---

## FEASIBILITY TAB (results_tab_renderers.py)

### Hits the vibe

| Location | Copy | Verdict |
|----------|------|---------|
| L31 | `"Feasibility Analysis"` | Clear. |
| L51-54 | `"Feasible — literature-backed"`, `"Marginal — partial data"`, `"Aspirational — limited / no data"` | Great tier names. Concise, informative, non-judgmental. |

### Needs work

| Location | Copy | Issue | Suggestion |
|----------|------|-------|------------|
| L32 | `"Checking your parameters against published ranges."` | Fine but could be punchier. | `"How your parameters stack up against the literature."` |
| L80 | `"Migration & Gradient Hypotheses"` | `"Hypotheses"` is tentative. | `"Migration & Gradient Predictions"` — be confident. |
| L82-83 | `"Predicted gradient effects on cell migration based on your scaffold geometry and culture conditions."` | Reads like an abstract sentence. | `"What gradients form in your construct and how cells might respond."` |

---

## SIMULATION TAB (results_tab_renderers.py)

### The FEA Section (L351-404) — BIGGEST PROBLEM

This section is **defensive to the point of being unusable**. The copy reads like a legal disclaimer, not a tool.

| Location | Copy | Issue |
|----------|------|-------|
| L358 | `"Scaffold mechanics (linear elastic sketch)"` | `"sketch"` undermines the feature. Just call it what it is. |
| L359-362 | `"Not viscoelastic: no creep, relaxation, or poroelastic flow. Readouts are coarse order-of-magnitude sketches..."` | **Two disclaimers** stacked before any data. User hasn't even seen a number yet. |
| L364 | `FEM_EXCLUDED_PHYSICS_SUMMARY` — another wall of bold disclaimers | Three layers of caveats in a row. This is the equivalent of showing someone a map and saying "this doesn't show traffic, weather, road conditions, construction, or elevation" before they can see the route. |
| L379-381 | `"Construct integrity band"` label | Unclear. Is this good or bad? |
| L384 | `failure_risk_explainer` — yet another disclaimer paragraph | **Four** disclaimer blocks before the user gets to the recommendation. |
| L397 | `"Porous solid: elastic load-path hotspot index"` | Reads like a paper section heading, not a UI label. |

**The FEA section needs: one short disclaimer, then data, then interpretation. Not four disclaimers wrapped around data.**

Suggested restructure:
1. Expander title: `"Scaffold mechanics"` (no qualifier)
2. One line: `"Linear elastic estimate — real matrices are viscoelastic. Treat as order-of-magnitude."`
3. Metrics row (deformation, strain, risk)
4. Recommendation box
5. Stress hotspot section (if porosity available)
6. **NEW: FEA 3D visualization** (currently missing from this section — `render_fea_results` exists but is never called!)

### Other simulation tab issues

| Location | Copy | Issue | Suggestion |
|----------|------|-------|------------|
| L142 | `"Benchmarks & narrative"` expander | `"narrative"` is meta. | `"Results & benchmarks"` |
| L150 | `"Analysis summary"` | Fine. |
| L178 | `"Scaffold geometry"` expander | Good. |
| L406 | `"CompuCell3D Simulation Brief"` | CC3D-specific jargon as a section title. | `"3D Simulation"` |
| L568 | `"Exports (PDF & PNG)"` | Functional but dull. | `"Download"` — everyone knows what export means. |

---

## METHODS & MATERIALS TAB (results_tab_renderers.py)

### Hits the vibe

| Location | Copy | Verdict |
|----------|------|---------|
| L633 | `"Methods & materials plan"` | Clear. |
| L643 | `"Top priorities (first five)"` | Direct. |

### Needs work

| Location | Copy | Issue | Suggestion |
|----------|------|-------|------------|
| L634-636 | `"Action items based on parameter gaps. Use Expand with AI for a detailed write-up."` | `"parameter gaps"` is jargon. `"Expand with AI"` is generic. | `"What to do next. Hit Expand for a full lab-ready plan."` |
| L689 | `"Save your report and join the beta"` | The save + signup CTA feels tacked on. | `"Get updates"` — keep it low-pressure. |
| L707 | `"Tip: download the PDF report from the Simulation tab."` | Cross-tab tips are confusing. | Move the download button here too, or drop the tip. |

---

## BRAND CONSISTENCY

- **"BioSim Copilot"** (chat init) vs **"Stromalytix"** (everywhere else) — pick one.
- **"Variance report"** appears in spinners and debug but is internal jargon. Users see "results" or "analysis."
- The word **"sketch"** appears 4 times in FEA copy. Once is cautious, four is apologetic.

---

## SUMMARY: Top 5 Changes for Vibe

1. **FEA section: collapse 4 disclaimers into 1 line, add the 3D viz**
2. **Kill "BioSim Copilot" name — it's Stromalytix everywhere**
3. **Shorten the landing page subheader and "How it works" block**
4. **Drop "Optional:" prefixes and the "does nothing today" persona copy**
5. **Replace internal jargon in user-facing spinners** ("variance report", "knowledge base", "8 messages minimum")
