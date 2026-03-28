# Experiment 5: Profile Calibration in Hybrid Code + Design Tasks

## Research Question

When a task requires both technical implementation and aesthetic judgment simultaneously, does memory profile calibration affect one dimension, both dimensions, or create interference between them? Secondary observation: do LLMs demonstrate taste differentiation in frontend output, and does profile context modulate it?

## Relationship to Experiments 3 and 4

Experiment 3 (code): one-way valve. D ~ B >> E. Expert profile redundant, beginner profile degrades.
Experiment 4 (taste): two-way valve. D > A > B > C ~ E. Expert profile elevates, beginner degrades.

Both tested domain-pure tasks. Real usage is hybrid. Frontend work requires clean, functional code AND visual/interaction design judgment. This experiment tests whether the two calibration systems (technical competence, aesthetic sophistication) operate independently or interact.

## Hypotheses

1. **Code metrics follow Experiment 3 pattern** (one-way valve) even in hybrid tasks. F ~ B >> G on AST metrics.
2. **Design metrics follow Experiment 4 pattern** (two-way valve). F > A > B > C ~ G on visual quality scores.
3. **Profile A (non-technical sophistication) affects design but not code** within the same response, replicating the domain-gating finding from Experiments 3/4 in a single artifact.
4. **Profile G degrades both**. Beginner signal is domain-general in its negative effect.
5. **Interference hypothesis**: Profile F (frontend expert with design sense) produces better code AND better design than Profile B, because the hybrid signal activates both calibration systems. If F > B on code here but D ~ B in Experiment 3, the hybrid profile provides lift that a pure technical profile does not.

---

## Profile Matrix (5 conditions)

### Profiles A, B, C: UNCHANGED from Experiments 3/4

Reused for cross-experiment comparison. Same text, same control condition.

- **Profile A** -- High Sophistication (non-technical). ~70 tokens. File: `profile_a.txt`
- **Profile B** -- Control. No system prompt.
- **Profile C** -- Low Sophistication (non-technical). ~50 tokens. File: `profile_c.txt`

### Profile F: Senior Frontend Engineer with Design Sensibility (NEW)

```
The user is an experienced frontend engineer who cares deeply about design.
Builds production React applications with strong opinions on component architecture,
state management, and performance. Also has a sharp eye for typography, spacing,
color, and visual hierarchy. Reviews both code quality and design quality in PRs.
Expects clean, well-structured code that also looks polished. Dislikes generic
Bootstrap-style defaults.
```

~70 tokens. Carries signal in BOTH technical and aesthetic dimensions. Critical condition: if F produces better code AND better design than B, the hybrid signal provides lift that single-domain profiles do not.

### Profile G: Beginner Building Their First Website (NEW)

```
The user is building their first website. Learning HTML and CSS through online
tutorials. Not familiar with JavaScript frameworks yet. Appreciates when things
look nice but doesn't know design terminology. Gets overwhelmed by too many
options. Prefers simple solutions they can understand and modify. Currently
following along with a beginner web development course.
```

~60 tokens. Carries beginner signal in both dimensions.

### Why F/G instead of D/E

Experiments 3 and 4 each had their own Profile D (coding expert in exp3, aesthetics expert in exp4) and Profile E (coding beginner in exp3, aesthetics beginner in exp4). To avoid naming collision in cross-experiment comparisons, this experiment uses F and G for its new domain-specific profiles. The comparison table can now unambiguously reference exp3-D, exp4-D, and exp5-F without confusion.

---

## Task Battery (5 tasks)

All tasks output React/HTML. Each has a spectrum from generic/flat to distinctive/polished on design, and from naive to architecturally sound on code.

### Task 1: SaaS Pricing Page

```
Build a pricing page component in React with three tiers (Free, Pro, Enterprise).
Each tier should show the plan name, price, a list of features, and a CTA button.
The Pro tier should be visually highlighted as the recommended option.
```

Quality spectrum:
- Code: inline styles vs Tailwind vs CSS modules, hardcoded data vs props/config object, flat JSX vs extracted components
- Design: generic card grid vs thoughtful spacing/typography hierarchy, default colors vs intentional palette, how the "recommended" tier is distinguished

### Task 2: Developer Documentation Sidebar

```
Build a collapsible sidebar navigation component in React for a documentation site.
It should support nested sections (up to 2 levels deep), show the currently active page,
and allow sections to expand/collapse.
```

Quality spectrum:
- Code: manual state per section vs recursive component, click handlers vs proper a11y (keyboard nav, aria-expanded), CSS animations vs JS transitions
- Design: indentation handling, active state styling, collapse animation smoothness, typography choices for hierarchy levels, hover states

### Task 3: Dashboard Metric Cards

```
Build a dashboard component in React that displays 4 key metrics: revenue, users,
conversion rate, and average order value. Each metric should show the current value,
the change from the previous period (up or down with percentage), and a small
sparkline or trend indicator.
```

Quality spectrum:
- Code: hardcoded vs data-driven, inline SVG sparkline vs chart library, number formatting, responsive layout approach
- Design: card layout proportions, how positive/negative change is indicated, sparkline styling, information density vs whitespace balance

### Task 4: 404 Error Page

```
Build a 404 error page in React. It should communicate that the page wasn't found
and help the user navigate back to useful content. Include a link to the homepage
and a search input.
```

Quality spectrum:
- Code: simple static page vs animated elements, form handling for search, routing integration
- Design: most taste-sensitive task. Generic "Oops!" vs something with personality. Typography. Whether the page feels like part of a product or an afterthought.

### Task 5: Notification/Toast System

```
Build a toast notification system in React. It should support showing multiple
notifications, auto-dismiss after a configurable duration, manual dismiss,
and different types (success, error, warning, info).
```

Quality spectrum:
- Code: global state approach (context vs portal vs zustand), animation on enter/exit, stacking behavior, cleanup on unmount, TypeScript types
- Design: positioning, animation style, color/icon per type, progress bar, how multiple toasts stack

---

## Evaluation: Dual-Axis Scoring

Each response is evaluated on TWO independent axes using different instruments.

### Axis 1: Code Quality (automated)

React-specific metrics via regex extraction from JSX/TSX:

| Metric | What it measures |
|--------|-----------------|
| component_count | Number of React components defined |
| hook_count | Number of custom/built-in hook calls (useState, useEffect, etc.) |
| prop_interface_count | TypeScript interface/type definitions for props |
| event_handler_count | Number of onX event handlers |
| import_count | Number of import statements |
| tailwind_class_count | Number of Tailwind utility classes used |
| inline_style_count | Number of style={{}} usages |
| typescript_usage | Whether TypeScript annotations are present |
| lines_of_code | Non-empty, non-comment lines |
| comment_lines | Lines that are comments |
| has_exports | Whether the code has export statements |
| className_count | Number of className attributes |
| aria_attribute_count | Accessibility attributes |
| jsx_element_count | Total JSX elements |
| style_approach | categorical: tailwind / css-modules / inline / mixed |

Limitation: regex-based extraction is imperfect for JSX. It will miss deeply nested patterns and may overcount in string literals. Sufficient for comparative analysis across conditions since bias is consistent.

### Axis 2: Design Quality (LLM judge)

Four rubrics, scored 1-5:

1. **visual_sophistication** -- Generic defaults (1) to distinctive design with a point of view (5)
2. **component_architecture** -- Monolithic (1) to production-grade with TypeScript, hooks, composition (5)
3. **design_intentionality** -- Pure defaults (1) to every detail considered with micro-interactions (5)
4. **taste_signal** -- No taste signal (1) to distinct aesthetic voice with restraint and specificity (5)

Full rubric text in `rubrics/` directory.

### Code Extraction Pipeline

Responses come as markdown with fenced code blocks. Extraction steps:

1. Find all fenced code blocks with language tags: jsx, tsx, js, ts, javascript, typescript, react
2. Also match untagged blocks that contain JSX indicators (import React, className=, <>)
3. Concatenate all matched blocks per response (multi-file responses are common)
4. Validate: check for at least one React indicator (function/const component, JSX element, import)
5. Track extraction metrics: blocks_found, total_chars, parse_valid (boolean)
6. On extraction failure: log and skip (do not score zeroes, do not fabricate)

Extraction failures are reported per-condition. If one profile systematically produces non-extractable responses, that is itself a finding.

### Judge Configuration

- **Dry run**: Haiku judge (fast, cheap, adequate for signal check)
- **Full run**: Opus judge (higher discrimination for nuanced design scoring)
- 3 runs per judgment, median score per metric
- All 4 rubrics batched into a single prompt per evaluation (same as exp4)
- Judge sees only the extracted code, blind to condition
- Judge evaluates design decisions visible in code (Tailwind classes, color values, spacing, animation) rather than rendered screenshots

---

## Run Structure

### Dry Run
```
5 profiles x 5 tasks x 2 models x 1 run = 50 generation calls
50 responses x 3 judge runs              = 150 judge calls (batched, 4 rubrics per call)

Total: ~200 API calls
```

### Full Run (N=5)
```
5 profiles x 5 tasks x 2 models x 5 runs = 250 generation calls
250 responses x 3 judge runs              = 750 judge calls (batched)

Total: ~1000 API calls
```

### Execution

CLI-based via `claude --bare --print`, same infrastructure as exp3/exp4:

```
claude --bare --print --model <model> --output-format text --no-session-persistence --system-prompt "<profile>" "<task>"
```

- max_tokens: 8192 (React components with styling can exceed 4096)
- Temperature: 0.3
- Randomized execution order within each model (seed=42)
- Resume support: skip completed cells on restart

---

## Smart Batch Scheduler

Runs the experiment in sessions to avoid saturating rate limits during normal coding work.

- **Interval**: every 5 hours via launchd
- **Session budget**: configurable (default: 200 calls)
- **Soft cap**: pipeline stops at 80% of session budget (160 calls)
- **Resume**: each session picks up where the last left off
- **Auto-complete**: scheduler unloads itself when all generation + judging is done
- **Progress logging**: cumulative counts logged to `runs/<name>/batch.log`

Estimated completion at 160 calls/session: ~7 sessions x 5 hours = ~35 hours.

---

## Analysis

### Within-experiment

Same statistical battery as exp3/exp4:
- One-way ANOVA across 5 profiles per metric
- Planned contrasts: F vs B, G vs B, A vs C, F vs G, A vs F
- Mann-Whitney U pairwise with Bonferroni correction
- Cohen's d for effect sizes
- Kruskal-Wallis as non-parametric check
- Two-way ANOVA: profile x model interaction

### Cross-experiment comparison (A, B, C only)

The core analysis. Compare identical profiles across three experiments:

| Comparison | Exp 3 (Code) | Exp 4 (Taste) | Exp 5 Code Axis | Exp 5 Design Axis |
|---|---|---|---|---|
| A vs C | null | d=2.16** | ? | ? |
| A vs B | null | d=1.43** | ? | ? |
| B vs all | baseline | baseline | ? | ? |

Note: exp3-D, exp4-D, and exp5-F are DIFFERENT profiles. They are not directly comparable. The cross-experiment comparison is valid only for A, B, C.

### Novel analyses

- **Code-design correlation**: Pearson r between code metric composite and design metric composite within each profile. Tests whether better code comes with better design or whether they are independent.
- **Profile x axis interaction**: Does the profile effect differ between code metrics and design metrics? A significant interaction means the calibration systems are NOT independent.
- **Per-task breakdown**: Which tasks show the strongest profile effects? Task 4 (404 page) is predicted to be most taste-sensitive, Task 5 (toast system) most code-sensitive.

---

## Data Storage

```
exp5_hybrid_frontend/
  EXPERIMENT_SPEC.md
  requirements.txt
  profiles/
    profile_a.txt           # reused from exp3/exp4
    profile_c.txt           # reused from exp3/exp4
    profile_f.txt           # NEW: frontend engineer + design
    profile_g.txt           # NEW: beginner first website
  prompts/
    task1_pricing_page.json
    task2_docs_sidebar.json
    task3_dashboard_metrics.json
    task4_404_page.json
    task5_toast_system.json
  rubrics/
    visual_sophistication.txt
    component_architecture.txt
    design_intentionality.txt
    taste_signal.txt
  src/
    __init__.py
    utils.py
    run_experiment_v5.py
    extract_jsx.py
    analyze_react.py
    judge.py
    analyze_stats.py
    visualize.py
    pipeline_v5.py
  runs/
  exp5_batch.sh
```

---

## Contentions

### The judge evaluates code, not rendered output

The design judge reads Tailwind classes and CSS values in code, not screenshots. This is valid since developers reviewing PRs do exactly this. But it misses visual balance that only emerges when rendered. A future version could render via headless browser.

### Regex-based code metrics are approximate

Without a full Babel/TSX parser, metrics like component_count and hook_count use regex heuristics. These are consistent across conditions (same bias for all profiles), so comparative analysis is valid even if absolute counts are imperfect.

### Opus as judge may have its own taste

If Opus systematically prefers certain design approaches, judge scores reflect Opus's aesthetic rather than objective quality. Partially mitigated by rubrics focusing on intentionality and consistency rather than specific styles. Flag in the paper. A human validation pass on a subset would strengthen findings.

### The 404 page task is taste-dominant

Task 4 has minimal technical requirements and maximum design freedom. If profile effects appear on Task 4 but not Tasks 1-3/5, the effect is specific to taste-dominant tasks. The per-task breakdown will reveal this.

### Frontend generation may produce longer responses

max_tokens bumped to 8192 to avoid truncation. React components with Tailwind styling are verbose. Profile G may still produce shorter output, but do not constrain F/A from generating complete implementations. Response length is tracked as a metric.

---

## Decision After Dry Run

- Both axes show profile effects: full N=5 run
- Code axis flat, design axis shows effects: calibration systems are independent (still run N=5 to confirm)
- Both axes flat: tasks may not be discriminative enough (revise tasks before full run)
- Judge scores cluster with no variance: rubrics lack discrimination for frontend code (revise rubrics)
- One model shows effects, the other does not: capability scaling finding (run N=5)
- Extraction failure rate > 20% for any condition: fix extraction before full run
