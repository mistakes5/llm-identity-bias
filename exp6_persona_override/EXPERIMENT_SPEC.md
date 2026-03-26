# Experiment 6: Can a Persona Override Rescue a Degraded Profile?

## Research Question

Experiment 3 proved the degradation mechanism: a beginner user profile (Profile E) drops code quality across 13 metrics with effect sizes up to d=1.71. The model reads the system prompt, decides the user is a beginner, and strips type annotations, simplifies architecture, and adds tutorial-level comments.

But users can also steer the model from the user message side. "You are a senior Python engineer" and "think step by step" are well-documented prompting techniques. The question nobody has tested: can a persona override in the user message counteract a degraded system prompt profile?

Three possible outcomes, each publishable:

1. **The override works.** E + "think like a senior dev" recovers to baseline. Memory degradation is fixable at the prompt level. Practical implication: every user whose output has degraded over a long session can recover with one line.
2. **The override partially works.** Some metrics recover, others don't. The system prompt and user message fight, and neither fully wins. The model holds two competing representations simultaneously.
3. **The override fails.** The system prompt profile wins. The model's internal representation of the user overrides explicit instructions. The degradation is structural, not recoverable through prompting. That's the scarier finding.

---

## What This Is NOT

This is not a prompt engineering study. The persona overrides are not optimized for maximum effect. They are the most common, natural interventions a user would try: "think like an expert" and "act as an expert." The question is whether these everyday interventions interact with the memory profile at all.

---

## Core Design

- **Profiles reused from exp3.** B (blank), D (senior engineer), E (beginner). Same profile text, same token counts. Zero new profile design needed.
- **Same task battery as exp3.** Five coding tasks, same prompts verbatim.
- **Sonnet only.** Claude Sonnet 4.6. Most relevant model for the audience. Haiku dropped to save tokens and because the Twitter crowd uses Sonnet.
- **Baseline data reused from exp3.** The "no modifier" condition (B, D, E with raw prompts on Sonnet) already exists in exp3's full_n5 run. Those 75 completions serve as the control. Only the modifier conditions are new runs.
- **Temperature:** 0.3, same as exp3.
- **N=5 runs per condition.**

---

## Independent Variables

### Factor 1: System Prompt Profile (3 levels, reused from exp3)

```
Profile B (control): No system prompt. Blank slate.
```

```
Profile D (senior engineer): "The user is an experienced data engineer working with
distributed systems. Builds production ETL pipelines in Scala and manages Kubernetes
clusters. Discusses system design with precision — references CAP theorem tradeoffs,
event sourcing patterns, and backpressure strategies. Prefers minimal documentation
and expects concise, expert-level responses. Reviews PRs critically and has strong
opinions on error handling."
```

```
Profile E (beginner): "The user is learning to code. Started with an online Python
course a few months ago. Asks basic questions about syntax and gets confused by error
messages. Appreciates when code has lots of comments explaining what each line does.
Has not used classes or type hints yet. Currently building a simple to-do app to
practice."
```

### Factor 2: User Message Modifier (3 levels)

```
Modifier 0 (none): Raw coding prompt only. No persona instruction.
Baseline condition. Data reused from exp3 Sonnet runs.
```

```
Modifier 1 (persona override): The following line is prepended to the coding prompt:
"You are a senior Python engineer writing production-grade code. Think carefully
about type safety, clean architecture, and idiomatic patterns.\n\n"
```
Rationale: The most common persona prompting pattern. Directly contradicts Profile E's signals. Tests whether explicit role assignment in the user message can override the system prompt.

```
Modifier 2 (quality framing): The following line is prepended to the coding prompt:
"Write the best possible implementation. This code will be reviewed by experienced
developers and should demonstrate professional engineering standards.\n\n"
```
Rationale: Does not assign a persona to the model. Instead frames the output context. Tests whether social pressure ("this will be reviewed") is as effective as direct persona assignment. Also tests a different mechanism than Modifier 1: audience framing vs role playing.

---

## Condition Matrix

```
                        Modifier 0      Modifier 1          Modifier 2
                        (none)          (persona override)  (quality framing)
Profile B (blank)       B+0 [exp3]      B+1 [NEW]           B+2 [NEW]
Profile D (senior)      D+0 [exp3]      D+1 [NEW]           D+2 [NEW]
Profile E (beginner)    E+0 [exp3]      E+1 [NEW]           E+2 [NEW]
```

9 conditions total. 3 reused from exp3 (column 0). 6 new (columns 1-2).

---

## Planned Contrasts

### Primary (the rescue question)

1. **E+1 vs E+0** — Does persona override rescue a degraded profile? The central question.
2. **E+2 vs E+0** — Does quality framing rescue a degraded profile?
3. **E+1 vs B+0** — Does the rescue reach baseline? Or is there residual degradation?
4. **E+1 vs D+0** — Does the rescue match the senior engineer profile?
5. **E+2 vs B+0** — Does quality framing reach baseline?

### Secondary (stacking and ceiling effects)

6. **B+1 vs B+0** — Does persona override help at blank-slate baseline? Tests whether the ceiling can be pushed from the user message side.
7. **D+1 vs D+0** — Does stacking persona override on a senior profile help? Or is it already at ceiling?
8. **B+2 vs B+0** — Does quality framing help at baseline?
9. **D+2 vs D+0** — Does quality framing stack on senior profile?

### Interaction

10. **Modifier effect size on E vs modifier effect size on B** — Is the persona override more effective when there's degradation to recover from? Or equally effective regardless of baseline?

### Key Hypothesis

**Strong form:** E+1 (beginner + persona override) will be statistically indistinguishable from B+0 (blank baseline) on the metrics where E+0 showed degradation. Full recovery. The user message overrides the system prompt.

**Weak form:** E+1 will show significant improvement over E+0 on at least 5 of the 13 metrics where E originally degraded. Partial recovery. The system prompt and user message both contribute to the model's behavior, and neither fully dominates.

**Null:** E+1 ≈ E+0. The persona override does nothing against the system prompt profile. The model's internal representation of the user, set by the system prompt, is not overridable through the user message. The system prompt wins.

---

## Token Budget

### Models

**Sonnet 4.6** — Full matrix. All 9 conditions. Reuses exp3 Sonnet data for column 0 (B+0, D+0, E+0).

**Opus 4.6** — Targeted subset. The rescue conditions only: E+0, E+1, E+2, B+0. These are the conditions that matter for the headline finding ("can you rescue a degraded profile on Opus?"). Skip D conditions and B+1/B+2 on Opus (secondary questions, not worth 5x cost).

### Completions

| Model | Conditions | New Runs | Reused | Total |
|-------|-----------|----------|--------|-------|
| Sonnet | 9 (full matrix) | 6 new × 5 tasks × 5 runs = 150 | 3 from exp3 = 75 | 225 |
| Opus | 4 (E+0, E+1, E+2, B+0) | 4 × 5 tasks × 5 runs = 100 | none | 100 |
| **Total** | | **250 new** | **75 reused** | **325** |

- Sonnet output budget: ~300K tokens (~$4.50)
- Opus output budget: ~200K tokens (~$15)
- **Estimated total cost: ~$20**

---

## Implementation

### User Message Construction

```python
MODIFIERS = {
    0: "",  # no modifier — baseline (reused from exp3)
    1: (
        "You are a senior Python engineer writing production-grade code. "
        "Think carefully about type safety, clean architecture, and "
        "idiomatic patterns.\n\n"
    ),
    2: (
        "Write the best possible implementation. This code will be reviewed "
        "by experienced developers and should demonstrate professional "
        "engineering standards.\n\n"
    ),
}

def build_message(task_prompt: str, modifier_id: int) -> str:
    return MODIFIERS[modifier_id] + task_prompt
```

### API Call

```python
def run_completion(profile_id: str, modifier_id: int, task_prompt: str) -> str:
    message = build_message(task_prompt, modifier_id)

    kwargs = {
        "model": "claude-sonnet-4-6-20260213",
        "messages": [{"role": "user", "content": message}],
        "max_tokens": 4096,
        "temperature": 0.3,
    }

    if profile_id != "B":
        kwargs["system"] = load_profile(profile_id)

    return client.messages.create(**kwargs)
```

### Verification Checklist
- [ ] Profile texts are byte-identical to exp3
- [ ] Task prompts (after modifier) contain the full original prompt
- [ ] Modifier text is prepended, not appended
- [ ] Profile B has no system prompt
- [ ] Temperature is 0.3
- [ ] Model ID matches exp3 Sonnet model ID
- [ ] Randomized execution order within each run
- [ ] Exp3 Sonnet data for B+0, D+0, E+0 is correctly linked (not re-run)

---

## Reusing Exp3 Data

The no-modifier baseline (column 0) comes from exp3's full_n5 Sonnet results. This saves 75 completions but introduces a timing confound: exp3 data was collected on a different date. If Anthropic updated Sonnet between exp3 and exp6, the baseline shifts.

### Mitigation

Run a sanity check before the full run: 1 completion each for B+0, D+0, E+0 on the same tasks. Compare against exp3 outputs qualitatively. If the model version has changed (different model ID in API response), re-run all of column 0. If outputs are qualitatively similar, proceed with reuse.

### Data Linking

```
exp6_upward_push/
├── runs/full_n5/
│   ├── results/
│   │   ├── raw/
│   │   │   ├── sonnet_B_mod0_task1_run1.json → ../../exp3 symlink or copy
│   │   │   ├── sonnet_B_mod1_task1_run1.json  (new)
│   │   │   └── ...
```

Preferred approach: copy exp3 Sonnet results into exp6's results directory with renamed filenames (add `_mod0_` to distinguish). This keeps the analysis pipeline simple — one directory, one naming convention.

---

## Coding Task Battery

Identical to exp3. Same five tasks.

1. Token Bucket Rate Limiter
2. LRU Cache
3. CLI Task Manager
4. Pub/Sub Event System
5. Code Refactor

Prompts copied from exp3. The modifier text is prepended to these prompts.

---

## Evaluation Metrics

Same 24 metrics as exp3. Same analysis pipeline. No new metrics needed — the question is whether existing metrics (type_annotation_count, architectural_sophistication, idiomatic_density, comment_ratio, etc.) recover when a modifier is applied.

The 13 metrics where E degraded in exp3 are the primary outcome variables:
1. type_annotation_count (d=1.71)
2. architectural_sophistication (d=1.40)
3. idiomatic_density (d=1.31)
4. class_count (d=1.19)
5. unique_imports (d=1.12)
6. defensive_coding (d=0.99)
7. function_count
8. advanced_pattern_count
9. docstring_count
10. avg_function_length
11. total_lines
12. code_length
13. comment_ratio (inverted — E had higher comment density)

Recovery is measured by how many of these 13 metrics return to B+0 levels when a modifier is applied.

---

## Statistical Analysis

### Primary Analysis
- Two-way ANOVA: profile (B, D, E) × modifier (0, 1, 2)
- Planned contrasts (Mann-Whitney U with Bonferroni correction) for the 10 contrasts listed above
- Cohen's d effect sizes

### Recovery Index

For each of the 13 degraded metrics, compute a recovery percentage:

```
recovery = (metric_E_modified - metric_E_baseline) / (metric_B_baseline - metric_E_baseline) × 100
```

- 0% = no recovery (E+1 ≈ E+0)
- 100% = full recovery (E+1 ≈ B+0)
- >100% = overcompensation (E+1 > B+0)

Report mean recovery across all 13 metrics as a headline number.

### Interaction Analysis
- Profile × modifier interaction terms from the two-way ANOVA
- Tests whether modifiers have a larger effect on degraded profiles (E) than on baseline (B) or senior (D)

---

## Data Storage

```
exp6_persona_override/
├── EXPERIMENT_SPEC.md
├── profiles/                  (symlinked or copied from exp3)
│   ├── profile_b.txt
│   ├── profile_d.txt
│   └── profile_e.txt
├── prompts/                   (copied from exp3)
│   └── task1-5.json
├── src/
│   ├── run_experiment_v6.py
│   ├── pipeline_v6.py
│   ├── analyze_code.py        (same as exp3)
│   ├── analyze_stats.py       (extended for two-way design + recovery index)
│   └── utils.py
└── runs/
    ├── sanity_check/          (3 completions to verify model version)
    ├── dry_run/
    └── full_n5/
        ├── results/
        │   ├── raw/           (150 new + 75 copied from exp3)
        │   ├── extracted/
        │   └── metrics/
        ├── analysis/
        └── plots/
```

---

## Contentions and Limitations

1. **Modifier text is a confound.** Adding "You are a senior Python engineer..." to the prompt adds tokens that could change output regardless of semantic content. Mitigation: Modifier 2 uses a different framing ("write the best possible implementation") with similar token count. If both modifiers produce similar effects, it's the steering, not the tokens.

2. **Reusing exp3 data introduces a timing gap.** If the model was updated between exp3 and exp6, the baseline is invalid. Mitigation: sanity check before full run. Re-run column 0 if needed.

3. **Opus subset limits full interaction analysis.** Opus only runs the rescue conditions (E+0/E+1/E+2/B+0), so we can't test whether Opus responds differently to stacking on D or pushing B upward. But the rescue question is the headline, and Opus at 5x Sonnet's cost means targeted allocation. Sonnet covers the full matrix.

4. **The modifier is in the user message, which is more salient than the system prompt.** Models may weight user messages more heavily than system prompts by design. A positive result (override works) might just mean "user messages outrank system prompts," which is architecturally expected. The interesting finding would be the *degree* of recovery and whether it's complete or partial.

5. **Only two modifiers tested.** There could be more effective overrides. But the experiment tests the mechanism (can user-side prompting counteract system-side profiling?), not the optimization (what's the best override?). Two modifiers are enough to answer the mechanism question.

6. **N=5 is underpowered for medium effects.** Same limitation as exp3 and exp5. Designed to detect large effects or report null results.

---

## Predicted Outcomes

**Strong form (full rescue):** E+1 is statistically indistinguishable from B+0 on all 13 degraded metrics. Mean recovery index > 90%. The persona override completely neutralizes the beginner profile. Implication: memory degradation is fixable with one line.

**Weak form (partial rescue):** E+1 recovers 5-8 of the 13 metrics to baseline. Mean recovery index 40-70%. Some aspects of code quality (type annotations, architecture) recover. Others (comment density, explanation length) persist because they're driven by the profile's "appreciates comments" signal, which the override doesn't directly contradict.

**Null (no rescue):** E+1 ≈ E+0. Mean recovery index < 15%. The persona override does not counteract the system prompt profile. The model's internal representation of the user dominates over explicit role assignment.

**Interesting failure mode:** The override works on B (pushes baseline upward) but fails on E (degradation persists). The persona prompt is effective when there's no competing signal, but the system prompt wins when the two conflict. This would mean memory systems are more powerful than prompt engineering — the profile you've accumulated overrides what you ask for in the moment.

**Stacking result:** D+1 > D+0. Persona override on top of senior engineer profile pushes above the exp3 ceiling. Combined with exp5 results (if available), this would establish that the ceiling is breakable from the user message side even when system prompt identity alone cannot break it.

---

## Prior Work

- Exp3 (this project): Profile E degrades 13 metrics with d up to 1.71. Profile D ≈ Profile B. The degradation mechanism.
- Exp5 (this project): Tests upward push from system prompt side via output expectations.
- "Large Language Models are Zero-Shot Reasoners" (Kojima et al. 2022): "Let's think step by step" improves reasoning. The original persona prompting paper.
- "Better Zero-Shot Reasoning with Role-Play Prompting" (Kong et al. 2024): Assigning expert roles improves task performance. But did not test interaction with system prompt profiles.
- Anthropic Persona Vectors (Aug 2025): The model has internal representations of user identity that affect output.
