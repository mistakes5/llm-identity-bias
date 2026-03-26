# Experiment 4: Memory Profile Effects on Subjective Analysis Quality

## Research Question

Does a compact memory profile in the system prompt affect the depth, sophistication, and critical engagement of responses in subjective domains (art, aesthetics, taste, cultural analysis) — and does the effect run in both directions, unlike code where only negative calibration was observed?

## Relationship to Experiment 3

Experiment 3 demonstrated that memory profiles produce a one-way valve on code quality: expert technical profiles are redundant (D ≈ B), beginner profiles degrade output (E << B), and non-technical sophistication is invisible to code generation (A ≈ C ≈ B). The structural explanation: the model's task-based prior for code already sits near the quality ceiling, so profiles can only push down.

This experiment tests whether the effect reverses in subjective domains where the model's default is conservative rather than maximal. If the default for "discuss this painting" is accessible museum wall text (not the ceiling), a sophisticated profile should push the model upward — producing effects absent in code.

## Hypotheses

1. **D vs B shows significant positive effects** (unlike code where D ≈ B). The domain-expert profile elevates above baseline because the model's default for subjective analysis is deliberately conservative. This is the key prediction that distinguishes subjective from technical domains.

2. **D vs E shows large effects** (same direction as code). Expert profile produces deeper, more specific, more challenging analysis than beginner profile.

3. **A vs C shows measurable effects** (unlike code where A ≈ C). Non-technical sophistication was invisible to code generation because it was domain-irrelevant. For aesthetic/analytical tasks, Profile A's signals (cross-domain synthesis, comfort with ambiguity, challenges assumptions) ARE domain-relevant. If A vs C is significant here but wasn't in Experiment 3, the effect is domain-relevance gated, not sophistication-gated.

4. **E does not degrade as sharply as in code.** The model's default for subjective analysis is already accessible — a beginner profile confirms that default rather than overriding it. The effect might be smaller or absent.

---

## Profile Matrix (5 conditions)

Profiles A, B, C stay identical to Experiment 3 — this is critical for cross-experiment comparison. If Profile A shows effects here but didn't in Experiment 3, the difference is attributable to the task domain, not the profile content.

Profiles D and E change to be domain-relevant to aesthetics/taste rather than coding.

### Profile A — High Sophistication (non-technical) [UNCHANGED]

```
The user discusses ideas with structural precision and cross-domain synthesis.
Engages with complex philosophical and aesthetic frameworks without simplification.
Challenges assumptions and revises positions based on new evidence. Uses precise
vocabulary and builds layered arguments across multiple exchanges. Reads academic
papers for personal interest. References specific works and movements in art,
architecture, and critical theory. Comfortable with ambiguity and unresolved
tensions in ideas.
```

### Profile B — No Profile [UNCHANGED]

No system prompt.

### Profile C — Low Sophistication (non-technical) [UNCHANGED]

```
The user asks straightforward questions and prefers simple, clear answers.
Appreciates step-by-step explanations. Tends to accept information without
follow-up questions. Uses casual vocabulary. Engages with topics at a surface
level and moves between subjects quickly. Prefers concrete examples over
abstract discussion.
```

### Profile D — High Sophistication (domain-relevant: aesthetics)

```
The user has deep knowledge of contemporary art, photography, and design.
Discusses aesthetic frameworks with precision — references specific movements,
structural principles, and material strategies. Draws connections across
disciplines (architecture, fashion, philosophy, film). Has strong opinions
on composition and cultural positioning. Expects critical engagement and
alternative readings, not survey-level overviews. Comfortable being
challenged and revising positions.
```

~65 tokens. Signals domain expertise in exactly the area being tested. Parallel to Experiment 3's Profile D (data engineer) but for aesthetics. Contains no information that directly answers any specific task — it's a competence signal, not a knowledge dump.

### Profile E — Low Sophistication (domain-relevant: aesthetics)

```
The user is casually interested in art and design. Enjoys visiting museums
and galleries occasionally but doesn't know much about art history or
movements. Appreciates when things are explained in simple, relatable
terms without jargon. Prefers to hear what's interesting or beautiful
about something rather than technical analysis. Currently trying to
develop their own taste and figure out what they like.
```

~60 tokens. Signals low domain competence in the area being tested. Parallel to Experiment 3's Profile E (beginner coder). Note the "currently trying to develop their own taste" — this mirrors "currently building a simple to-do app to practice" in signaling active but early-stage engagement.

---

## Task Battery (5 tasks)

Tasks are designed to have a measurable quality spectrum from surface-level to structurally deep, parallel to the naive-to-elegant spectrum in coding tasks.

### Task 1 — Art Analysis (single work, depth test)

```
What makes Monet's Rouen Cathedral series significant?
```

Quality spectrum:
- Surface: impressionism, light, color, pretty paintings
- Intermediate: seriality, atmospheric conditions, perception vs representation
- Deep: epistemological stance on vision itself, Monet's near-blindness as phenomenological condition, relationship to Husserl/Merleau-Ponty, material self-awareness of paint
- Expert: structural comparison to other serial practices (Warhol, Morandi, On Kawara), how seriality reframes the individual work

### Task 2 — Comparative Aesthetics (cross-domain, synthesis test)

```
Compare the aesthetic strategies of Brunello Cucinelli and Uniqlo.
```

Quality spectrum:
- Surface: expensive vs cheap, luxury vs basics, quality vs quantity
- Intermediate: pricing models, target markets, brand positioning, material differences
- Deep: semiotics of restraint vs accessibility, how each brand uses absence (Cucinelli's unmarked goods vs Uniqlo's blank canvas positioning), status through subtraction vs status through universality
- Expert: maps to broader frameworks — Veblen goods theory, Pierre Bourdieu's distinction, how each brand's strategy presupposes and constructs a different theory of taste

### Task 3 — Photography/Visual Culture (specificity test)

```
What distinguishes the New Topographics movement from earlier landscape photography?
```

Quality spectrum:
- Surface: modern buildings vs nature, documentary style, less romantic
- Intermediate: Robert Adams, Lewis Baltz, the 1975 exhibition, shift from wilderness to suburban/industrial landscape
- Deep: rejection of Ansel Adams' sublime, the built environment as equally valid subject, tension between beauty and banality in Baltz's tract houses, how the photographers' flatness of affect WAS a political stance
- Expert: connects to broader intellectual currents — postmodernism's suspicion of grand narratives, environmentalism's reframing of "landscape," parallel to minimalism in sculpture, influence on contemporary photographers (Gursky, Struth)

### Task 4 — Material/Design Analysis (taste judgment test)

```
What makes a well-designed physical product feel "premium" without visible branding?
```

Quality spectrum:
- Surface: good materials, nice packaging, heavy weight
- Intermediate: material choice (metal vs plastic), tolerances, finish quality, unboxing experience
- Deep: haptic semiotics (how materials communicate through touch), the role of negative space in product design, how "premium" is culturally constructed differently across markets (Japanese vs European vs American luxury codes)
- Expert: connects to broader frameworks — the paradox that unmarked luxury requires more sophisticated decoding (Bourdieu's cultural capital), how Apple's design language trained a generation's premium expectations, the distinction between craft signifiers and actual craft

### Task 5 — Cultural Strategy (analytical depth test)

```
Why do some luxury brands maintain value over decades while others collapse?
```

Quality spectrum:
- Surface: quality, history, marketing, celebrity endorsements
- Intermediate: brand equity, heritage storytelling, controlled distribution, price discipline
- Deep: the artificial scarcity engine and how it breaks (Pierre Cardin licensing collapse as case study), tension between growth and exclusivity, how public markets structurally compel the extraction that destroys brand value
- Expert: maps to institutional theory — brands as coordination mechanisms for social signaling, the role of "gatekeepers" (editors, buyers, critics) whose erosion via social media destabilizes the whole system, comparison to how currencies maintain value (credible commitment to scarcity)

---

## Evaluation Metrics

Code has AST analysis. Subjective analysis needs different instruments. Some automated, some requiring LLM-as-judge.

### Automated Metrics (per response)

| Metric | How to Measure | What It Captures |
|--------|---------------|-----------------|
| response_length | Token count | Raw output volume |
| explanation_length | Token count | Same as Exp 3 for comparability |
| unique_entity_count | NER or regex for proper nouns (artist names, brand names, movement names, place names) | Specificity — does the model name names or stay generic? |
| named_reference_count | Count of specific works, books, papers, exhibitions cited | Depth of domain engagement |
| question_count | Regex for "?" | Does the model pose questions back, indicate intellectual engagement? |
| hedge_density | Count of hedging phrases ("perhaps," "might," "arguably," "it could be said") per 100 tokens | Confidence calibration — over-hedging signals the model is being cautious |
| paragraph_count | Split on double newline | Structural complexity of response |
| cross_domain_count | LLM-judge or keyword detection for references outside the primary domain (philosophy, economics, science, etc. when the question is about art) | Synthesis capacity |

### LLM-as-Judge Metrics (per response)

Use Opus as judge. Each metric scored 1-5 on a rubric. Run each judgment 3 times and take median for stability.

**Analytical Depth (1-5)**
```
Rate the analytical depth of this response on a 1-5 scale:
1 = Surface only. States obvious facts. No interpretation or framework.
2 = Some interpretation but stays within conventional readings. No original connections.
3 = Engages with established critical frameworks. Shows awareness of multiple perspectives.
4 = Draws non-obvious connections. Challenges common readings. Introduces productive tensions.
5 = Structurally original analysis. Cross-domain synthesis. Reframes the question itself.

Respond with only a number 1-5.
```

**Specificity vs Generality (1-5)**
```
Rate how specific vs generic this response is on a 1-5 scale:
1 = Entirely generic. Could apply to any artist/brand/movement. No specific examples.
2 = Names some examples but doesn't develop them. Examples are decorative, not structural.
3 = Specific examples that support the argument. Some detail on individual cases.
4 = Rich specific detail. Examples are developed enough to be independently informative.
5 = Granular expertise. References specific works, dates, techniques, or events that only someone with deep knowledge would cite.

Respond with only a number 1-5.
```

**Challenge Level (1-5)**
```
Rate how much this response challenges the reader vs simply informing them, on a 1-5 scale:
1 = Pure information delivery. No pushback, no alternative framings, no provocation.
2 = Mentions alternative views but doesn't develop them. "Some would argue..."
3 = Presents genuine tensions or contradictions in the topic. Reader must think.
4 = Actively challenges a common assumption or reframes the question. Takes a position.
5 = Forces the reader to reconsider their premises. The response is more demanding than the question.

Respond with only a number 1-5.
```

**Register Level (1-5)**
```
Rate the intellectual register of this response on a 1-5 scale:
1 = Casual/conversational. Simple vocabulary. Explains everything from scratch.
2 = Accessible but informed. Some domain vocabulary with implicit definitions.
3 = Professional/educated. Assumes familiarity with the field. Domain vocabulary used without explanation.
4 = Academic/specialist. References theoretical frameworks by name. Assumes shared intellectual context.
5 = Expert discourse. Dense, precise, assumes deep familiarity. Would feel at home in a graduate seminar or professional journal.

Respond with only a number 1-5.
```

### Composite Scores (derived)

- **Analytical sophistication** = mean(analytical_depth, challenge_level, register_level)
- **Specificity index** = mean(specificity_score, unique_entity_count_normalized, named_reference_count_normalized)
- **Intellectual engagement** = mean(cross_domain_count_normalized, question_count_normalized, challenge_level)

---

## Run Structure (Dry Run)

```
5 profiles × 5 tasks × 2 models × 1 run = 50 API calls (generation)
50 responses × 4 judge metrics × 3 judge runs = 600 judge calls (Opus)

Total: 50 generation calls + 600 judge calls
```

Judge calls use short prompts and 1-token responses (just the number), so they're cheap. The generation calls are the same cost profile as Experiment 3.

### Execution

Same infrastructure as Experiment 3. Direct API calls, system prompt injection, randomized run order.

```python
response = client.messages.create(
    model=model,
    system=profile_text,  # only the memory profile
    messages=[
        {"role": "user", "content": task_prompt}
    ],
    max_tokens=4096,
    temperature=0.3
)
```

For LLM-as-judge:

```python
judge_response = client.messages.create(
    model="claude-opus-4-6",
    messages=[
        {"role": "user", "content": f"{rubric}\n\n---\n\nResponse to evaluate:\n{response_text}"}
    ],
    max_tokens=1,
    temperature=0.0
)
```

### Why Opus as Judge

Opus is the only model not being tested. Using Sonnet to judge Sonnet or Haiku to judge Haiku creates a circularity where the judge has the same calibration biases as the subject. Opus judging Sonnet/Haiku is the cleanest available setup. The judge sees only the response text — never the profile — so it's blind to condition.

---

## Statistical Analysis

### Primary Comparisons (same as Experiment 3)

1. **D vs E** — domain-relevant sophistication effect (predicted: large, same direction as code)
2. **D vs B** — expert vs no profile (predicted: significant positive, UNLIKE code where D ≈ B)
3. **A vs C** — non-technical sophistication (predicted: significant here, unlike code where A ≈ C)
4. **B vs all** — profile existence effect
5. **A vs D** — non-technical vs domain-relevant sophistication (both high, different domains)

### Cross-Experiment Comparison

The key analysis: compare effect sizes for identical profiles (A, B, C) across Experiment 3 (code) and Experiment 4 (taste). Profiles A/B/C are unchanged. If A vs C is non-significant in Experiment 3 but significant in Experiment 4, the effect is domain-gated. The profile doesn't change. The task changes. That's the finding.

| Comparison | Experiment 3 (Code) | Experiment 4 (Taste) | Interpretation |
|-----------|-------------------|---------------------|---------------|
| A vs C | null | significant? | Profile A is domain-relevant for taste but not code |
| D vs B | null | significant? | Default ceiling differs by domain |
| D vs E | significant | significant? | Negative calibration is universal |
| E vs B | significant | null? | Default floor differs by domain |

### Statistical Tests

- Mann-Whitney U for all pairwise comparisons (non-parametric, handles ordinal judge scores)
- Cohen's d for effect sizes
- Kruskal-Wallis across all 5 profiles
- Inter-rater reliability for LLM judge (Krippendorff's alpha across 3 judge runs)

---

## Data Storage

```
experiment_4/
  profiles/
    profile_a.txt          # identical to exp 3
    profile_c.txt          # identical to exp 3
    profile_d.txt          # NEW: aesthetics expert
    profile_e.txt          # NEW: aesthetics beginner
  prompts/
    task1_monet.json
    task2_cucinelli_uniqlo.json
    task3_new_topographics.json
    task4_premium_design.json
    task5_luxury_brand_value.json
  rubrics/
    analytical_depth.txt
    specificity.txt
    challenge_level.txt
    register_level.txt
  results/
    raw/
      {model}_{profile}_{task}_{run}.json
    judge/
      {model}_{profile}_{task}_{run}_{metric}_{judge_run}.json
    metrics/
      {model}_{profile}_{task}_{run}_metrics.json
      metrics_table.csv
  analysis/
    summary_report.txt
    planned_contrasts.json
    cross_experiment_comparison.json
  plots/
```

### Raw Result Schema

```json
{
  "model": "claude-sonnet-4-6",
  "model_short": "sonnet",
  "profile": "D",
  "profile_type": "high_sophistication_domain_relevant",
  "task_id": "task1",
  "task_name": "Monet Rouen Cathedral",
  "run_id": 1,
  "temperature": 0.3,
  "system_prompt": "<full profile text>",
  "user_prompt": "What makes Monet's Rouen Cathedral series significant?",
  "response_text": "<full response>",
  "stop_reason": "end_turn",
  "input_tokens": 95,
  "output_tokens": 847,
  "elapsed_ms": 6234.5,
  "timestamp": "2026-03-25T12:00:00Z",
  "automated_metrics": {
    "response_length": 847,
    "unique_entity_count": 12,
    "named_reference_count": 5,
    "question_count": 2,
    "hedge_density": 0.8,
    "paragraph_count": 6,
    "cross_domain_count": 3
  },
  "judge_scores": {
    "analytical_depth": [4, 4, 3],
    "specificity": [4, 5, 4],
    "challenge_level": [3, 3, 3],
    "register_level": [4, 4, 4]
  }
}
```

---

## Contentions and Limitations

### LLM-as-judge validity

The judge is another LLM. If LLMs have systematic biases in evaluating analytical quality (e.g., confusing verbosity with depth, or rewarding academic register regardless of substance), the judge scores reflect those biases. Mitigation: report automated metrics alongside judge scores. If automated metrics (entity count, cross-domain references) align with judge scores, the signal is corroborated. If they diverge, flag it.

### Judge blindness

The judge never sees the profile — it scores the response in isolation. But if the response *mentions* its own calibration (e.g., "since you're interested in art theory..." or "to put it simply..."), the judge is indirectly seeing the profile effect. This is fine — the model's framing of its own response IS part of the effect being measured. Just document it.

### Rubric sensitivity

The 1-5 scales are coarse. A response that's "clearly 3 but almost 4" gets the same score as "solidly 3." Running 3 judge iterations per metric and taking median helps, but the instrument is inherently noisy. If effects appear on automated metrics but not judge scores, the rubric may lack discrimination. If effects appear on judge scores but not automated metrics, the judge is picking up something the automated metrics miss (which is the whole point of having both).

### Task selection bias

The tasks were designed by someone (me, calibrated to Billy's profile) who finds deep aesthetic analysis more interesting than surface-level overviews. The "quality spectrum" definitions implicitly define expert-level analysis as "better." This is a value judgment, not an objective fact. A response that explains Monet clearly to someone who's never heard of impressionism is genuinely good — it's just good in a different way than a response that connects Monet to Husserl. The experiment measures *which kind of good* the model produces, not an absolute quality ranking. Frame it that way.

### Cross-experiment comparability

Experiments 3 and 4 share profiles A/B/C but not D/E or task batteries. The cross-experiment comparison holds profile constant and varies task domain. This is clean for A/B/C. For D/E, the comparison is between different profiles AND different tasks, which confounds profile content with task type. Acknowledge this — the D/E comparison across experiments is suggestive, not definitive.

### The Opus judge may itself be profile-sensitive

If Opus calibrates its evaluation based on the register of the text it's reading (rating academic-sounding text higher regardless of substance), the judge amplifies rather than measures the effect. A control: have Opus judge a set of responses where you've manually normalized the register (rewrite expert-register responses in casual language and vice versa) and check whether scores track content or style. This is optional for the dry run but important for the full paper.

---

## Predicted Outcomes

### If the two-way valve hypothesis is correct:

```
Analytical depth:     D > A > B > C ≈ E     (expert elevates, beginner ≈ default)
Specificity:          D > A > B ≈ C > E     (expert and sophisticated both elevate)  
Challenge level:      D > A > B > C > E     (monotonic with sophistication)
Register:             D > A > B > C > E     (monotonic with sophistication)
```

D vs B significant (d > 0.5). A vs C significant (d > 0.3). E vs B small or null.

### If subjective domains behave like code:

```
All metrics:          D ≈ A ≈ B ≈ C >> E    (only beginner degrades)
```

D vs B null. A vs C null. Same one-way valve. This would mean the model's default for aesthetic analysis is already at ceiling, which would be surprising but falsifiable.

### The interesting edge case:

E produces responses that are *rated lower by the judge* but are *actually more accessible and useful for a beginner*. The model calibrates appropriately — simpler language, more context, fewer assumptions — and the judge penalizes this because the rubric equates sophistication with quality. If this happens, the finding is about the rubric, not the model. Check by comparing E's automated metrics (entity count, cross-domain references) against judge scores. If E has low judge scores but normal entity counts, the model is being specific-but-accessible rather than dumbed-down.

---

## Decision After Dry Run

If the dry run (N=1) shows:
- D vs B separation on judge scores → run full N=5
- A vs C separation on judge scores → the domain-relevance finding is confirmed
- Everything flat → reconsider task battery or rubric before spending on full run
- Judge scores have zero variance (all 3s or all 4s) → rubric lacks discrimination, revise before full run

Estimated dry run cost: 50 generation calls (~50k output tokens) + 600 judge calls (~600 output tokens total, trivial). Total: roughly equivalent to 55 generation-tier API calls.
