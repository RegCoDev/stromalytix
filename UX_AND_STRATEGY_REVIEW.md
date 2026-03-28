# Stromalytix: UX, Positioning & Process Intelligence Review

---

## 1. THE "VIBE CODE" PROBLEM

The current app looks like a dark-mode hackathon project. That's fine for prototyping, but it signals "weekend project" to anyone who has used professional software. Here's what gives it away and how to fix each:

### What screams "vibe code"

| Signal | Where | What pros do instead |
|--------|-------|---------------------|
| **All-dark-everything** (`#0a0a0a`, `#111111`) | Every component | Professional dark modes use dark *gray* not black. Figma: `#2c2c2c` bg, `#383838` cards. Linear: `#1b1b1f` bg. Pure black feels like a terminal. |
| **Neon green accent** (`#00ff88`) | Titles, highlights, progress | One accent color is fine but `#00ff88` at full saturation is eye-searing. Monday.com uses muted but recognizable brand colors. Dial it to `#34d399` (Tailwind emerald-400) or similar. |
| **JetBrains Mono everywhere** | Chart titles, all text | Mono font = code. Use it for data labels and values. Use Inter, DM Sans, or Source Sans for UI text. This alone changes perception more than anything. |
| **No whitespace/padding** | Metrics jammed together | Salesforce Lightning has generous spacing. Notion has breathing room. Add `margin-top: 1rem` between sections. |
| **Raw HTML injection** | `st.markdown(unsafe_allow_html=True)` | Dozens of inline CSS strings. Streamlit's theming + `st.container`/`st.columns` can handle 80% of this. The inline HTML makes it fragile and hard to theme. |
| **No visual hierarchy** | Every section looks the same | Good SaaS has: hero metric (big number), supporting details (smaller), then deep-dive. The current layout is flat. |
| **Emojis as icons** | Sidebar, progress, section headers | Emojis look casual. If you keep them, fine for a beta — but the "serious" competitors use SVG icons or nothing. |

### What professional SaaS dark modes look like

**Linear (project management for eng teams)**
- Background: `#1b1b1f`, cards: `#26262a`, borders: `#38383c`
- Text: `#e8e8e8` primary, `#8e8e93` secondary
- Accent: blue `#5e6ad2`, used sparingly (selected states, CTAs)
- Font: Inter. Small, dense. Lots of whitespace.
- Feel: "We built this for ourselves and we're a bit obsessive"

**Monday.com**
- Bright but structured. Not dark mode by default.
- Bold headers, clean table layouts, lots of color-coded status pills
- Generous padding, rounded corners
- Feel: "Accessible to non-technical people, still powerful"

**Salesforce Lightning**
- Card-based layouts with clear sections
- Heavy use of white/light gray, blue accent
- Every number has a label, unit, and context
- Feel: "Enterprise. Reliable. Probably too many features."

**Benchling (actual biotech competitor)**
- Clean white UI, blue accent
- Structured data tables with expandable rows
- Lab notebook metaphor — familiar to the audience
- Feel: "We know your workflow"

### What Stromalytix should feel like

Not Monday (too general), not Salesforce (too enterprise), not Linear (too dev). Closer to **Benchling meets Notion** — structured, calm, domain-aware. The dark theme can stay (it differentiates from Benchling's clinical white), but it needs to be *refined* dark, not *hacker* dark.

### Concrete Streamlit changes (no framework rewrite needed)

1. **Theme config** (`.streamlit/config.toml`):
   ```toml
   [theme]
   base = "dark"
   primaryColor = "#34d399"
   backgroundColor = "#1a1a1f"
   secondaryBackgroundColor = "#252529"
   textColor = "#e0e0e5"
   font = "sans serif"
   ```

2. **Replace inline HTML** with Streamlit components where possible. For the things you can't do natively, use a single CSS block injected once, not per-element.

3. **Metrics layout**: Use `st.columns` with proper ratios. Put the most important number first and biggest.

4. **Chart styling**: Switch chart font family from `JetBrains Mono` to `Inter, system-ui, sans-serif`. Keep mono only for axis tick values.

---

## 2. PROCESS INTELLIGENCE ANGLE

This is the sleeper feature. Here's why it matters and how it maps.

### What process intelligence means for tissue engineering

The user's workflow today (whether they know it or not) is:

```
Design construct → Fabricate → Culture → Assay → Analyze → Iterate
     ↑___________________________|_____________________________|
```

This loop runs **weeks to months per iteration**. The bottleneck isn't any single step — it's:

1. **Design decisions made on gut feel** — "I'll use GelMA because my PI used it." No systematic comparison.
2. **No traceability between design → outcome** — when an assay fails at week 3, there's no structured way to trace back to which parameter was the root cause.
3. **Invisible process waste** — running the same characterization experiments that 50 other labs already published, because nobody aggregated the results.
4. **Batch effects and protocol drift** — small changes in media change timing, cell passage, crosslinking UV dose that never get recorded but dominate outcomes.

### How Stromalytix already does process intelligence (even if you don't call it that)

| Process intelligence concept | Stromalytix feature | Gap |
|-------|---------|-----|
| **Process discovery** — map the actual workflow | Chat assessment extracts the user's real protocol (not what's in their grant, what they *actually do*) | Currently one-shot. No tracking over time. |
| **Conformance checking** — compare actual vs. ideal | Variance report: your protocol vs. 8,100 published protocols | This IS conformance checking. Just rebrand it. |
| **Root cause analysis** — why did my construct fail? | Risk flags, deviation scores, stress hotspot analysis | Missing: the temporal dimension. Need to track iteration history. |
| **Process optimization** — which parameters matter most? | Action plan priorities, sensitivity via FEA | Missing: actual experiment tracking and outcome correlation. |
| **Benchmarking** — how do I compare to peers? | Radar chart, parameter scatter vs. literature | This IS benchmarking. Already built. |

### The latent pain you're revealing

Most tissue engineers don't think they have a "process problem." They think they have a "biology problem" — "my cells aren't behaving." But the real issue is:

> **They're running uncontrolled process experiments and calling them biology experiments.**

When someone changes their media change interval from 48h to 72h because they were at a conference, and then their viability drops — that's a process change. But they'll blame the cells, the lot of Matrigel, or Mercury in retrograde.

Stromalytix makes this visible for the first time: "Your protocol says 48h media changes but the literature range for this tissue type is 24-72h. At 72h with your construct height, our O2 model shows hypoxic core at day 3."

**That's process intelligence. You just don't call it that yet.**

### What to build (later, not now)

- **Experiment journal**: track iterations. "Run 1: GelMA 6%, 5e6 cells/mL, viability 78%. Run 2: GelMA 4%, same density, viability 89%." Then correlate.
- **Process map export**: let the user see their actual workflow as a BPMN-style diagram. "Where in your process are you losing the most time?"
- **Drift detection**: "Your last 3 runs used different crosslinking times. This correlates with your viability variance."

But don't build these now. The current feature set is the wedge. The experiment journal is the expansion.

---

## 3. LINKEDIN DEMO FRAMES — WHAT MAKES THEM CLICK

### The audience

Tissue engineers, biotech R&D managers, bioprinting companies, cell ag startups. They're on LinkedIn between experiments or during a boring seminar. They scroll fast.

### Frame sequence for maximum conversion

**Frame 1 (0-3 sec) — THE HOOK**
> Screen recording: user types "GelMA 6%, hMSCs, bone tissue" into the chat.
> Text overlay: **"Stop guessing your construct parameters."**

Why it works: They *are* guessing. They know it. This is the latent pain.

**Frame 2 (3-8 sec) — THE AHA**
> Chat fills in. Profile extraction. Phase transition to results.
> The radar chart appears. Red flags light up on porosity.
> Text overlay: **"8,100 published protocols. Yours compared in seconds."**

Why it works: The number is concrete. "Seconds" contrasts with their experience of literature review taking days.

**Frame 3 (8-13 sec) — THE DEPTH**
> Scaffold geometry preview spinning in 3D. Switch to gyroid → cylinder → core-shell.
> FEA compression visualization with stress heatmap.
> Text overlay: **"Geometry. Mechanics. Simulation. One tool."**

Why it works: 3D visuals stop the scroll. Scientists love interactive 3D. The FEA heatmap looks serious — this isn't a toy.

**Frame 4 (13-18 sec) — THE SIMULATION**
> CC3D running. VTK frames appearing with cell positions + O2 field.
> Hypoxic zone in red.
> Text overlay: **"See where your cells will struggle before you plate them."**

Why it works: This is the promise. Predictive, not retrospective.

**Frame 5 (18-22 sec) — THE CTA**
> Methods & materials plan. Action items. PDF download.
> Text overlay: **"Free during beta. Link in comments."**
> End card: Stromalytix logo + URL.

### What makes them give email

Not the demo. The demo gets them to the site. What converts:

1. **Specificity to their problem**: "Enter your exact protocol — materials, cells, culture conditions — and see how it compares to what's published." Not "AI for biotech" — that's meaningless now.

2. **Instant value before signup**: Let them run the chat + see the radar chart without an account. Gate the PDF export, the CC3D simulation, and the action plan behind email.

3. **Social proof from their world**: "Used by researchers at [universities]." Even 3-5 logos. Or: "Covers 8,100 PubMed abstracts across scaffolds, bioinks, and culture conditions."

### What makes them pay

Different from what makes them sign up. They pay when:

1. **They've used it 3+ times** and it saved them from a bad experiment. The first value moment is "I was about to use 80% porosity and Stromalytix flagged it as way above the published range for my tissue type."

2. **They need it for a grant or paper**: "Protocol optimization was performed using Stromalytix (v2.x), comparing construct parameters against 8,100 published tissue engineering protocols." That sentence in a methods section is worth $30/month.

3. **Team features**: shared profiles, protocol versioning, experiment history. This is the "process intelligence" expansion. A PI would pay for visibility into what their students are actually doing.

4. **Simulation access**: CC3D runs are compute. Charge for it. "5 free simulations/month, $X for unlimited."

---

## 4. SUMMARY: PRIORITY ORDER

| Priority | What | Effort | Impact |
|----------|------|--------|--------|
| 1 | Fix theme (config.toml, muted accent, sans-serif font) | 30 min | Transforms first impression |
| 2 | Collapse FEA disclaimers, add 3D viz | Done (this session) | The FEA section is now usable |
| 3 | Shape primitives (line, disc, tube) | Done (this session) | Complete the geometry toolbox |
| 4 | VTK parser + O2 field fix | Done (this session) | CC3D viz actually works now |
| 5 | Record the LinkedIn demo video | 1-2 hrs (human task) | Top of funnel |
| 6 | Gate PDF/sim behind email, free chat+radar | 1-2 hrs code | Conversion |
| 7 | Process intelligence framing on landing page | Copy changes | Positioning for PIs and R&D managers |
| 8 | Experiment journal (future) | Weeks | Retention + expansion revenue |
