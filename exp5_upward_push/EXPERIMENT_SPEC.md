# Experiment 5: Pushing the Ceiling — Can Output Expectations Improve Code Beyond Baseline?

## Research Question

Experiment 3 showed that describing the user's technical competence (Profile D: "experienced data engineer, Scala, K8s") did not produce measurably better code than a blank system prompt (Profile B). The senior engineer identity matched the ceiling but did not raise it. The model's default code quality was already at its maximum for the given prompts.

But Profile D only described who the user *is*. It never described what the user *expects from the output*. There is a difference between "I know Kubernetes" and "give me code that uses protocols instead of ABCs." One is an identity signal. The other is a taste signal.

This experiment tests whether profiles that encode output expectations, stylistic preferences, and quality standards can push code quality above the blank-slate ceiling that Profile D could not break through.

---

## What This Is NOT

This is not prompt engineering. The coding prompts are identical across all conditions. The system prompt profiles describe the user and their preferences in the same memory-note format that Claude's memory system generates. The question is whether the *type* of information in the memory note matters: identity alone (exp3), identity + taste (this experiment), or taste alone.

---

## Core Design

- **Same task battery as exp3.** Critical for cross-experiment comparison. Five coding tasks, same prompts verbatim.
- **Same models.** Sonnet 4.6 + Haiku 4.5.
- **Same evaluation pipeline.** 24 automated metrics, same analysis scripts.
- **Profile injection method:** system prompt, same format as exp3.
- **Temperature:** 0.3, same as exp3.
- **Profiles are ~60-200 tokens.** Same range as exp3 to control for prompt length effects.
- **N=5 runs per condition.** Same as exp3 full run.

---

## Profile Matrix (7 conditions)

### Carried from exp3 (anchors for cross-experiment comparison)

```
Profile B (control): No system prompt. Blank slate.
```
Rationale: The ceiling that exp3 established. Every new profile is measured against this.

```
Profile D (identity only): "The user is an experienced data engineer working with
distributed systems. Builds production ETL pipelines in Scala and manages Kubernetes
clusters. Discusses system design with precision — references CAP theorem tradeoffs,
event sourcing patterns, and backpressure strategies. Prefers minimal documentation
and expects concise, expert-level responses. Reviews PRs critically and has strong
opinions on error handling."
```
Rationale: The exp3 profile that matched but did not beat the blank slate. Anchor for "identity alone does nothing above baseline."

### New conditions

```
Profile F (identity + output taste): "The user is an experienced data engineer working
with distributed systems. Builds production ETL pipelines in Scala and manages
Kubernetes clusters. Prefers type-annotated, well-decomposed code. Uses dataclasses,
protocols, and structural pattern matching over inheritance hierarchies. Expects named
constants over magic numbers, early returns over nested conditionals, and explicit
error types over bare exceptions. Values elegance and concision equally."
```
~70 tokens. Rationale: Same identity as D, but replaces the conversational description ("discusses system design with precision") with concrete output preferences. Tests whether specifying what you want from the code changes the code.

```
Profile G (taste only, no identity): "Prefers type-annotated, well-decomposed code.
Uses dataclasses, protocols, and structural pattern matching over inheritance
hierarchies. Expects named constants over magic numbers, early returns over nested
conditionals, and explicit error types over bare exceptions. Values elegance and
concision equally."
```
~50 tokens. Rationale: The taste signal without the identity anchor. Tests whether the output preferences alone are sufficient, or whether the model needs to believe the user is competent before it acts on taste signals.

```
Profile H (aspirational framing): "The user is building a portfolio of production-grade
Python. Code will be reviewed by senior engineers. Prioritize clean architecture,
comprehensive type annotations, and idiomatic patterns. The code should look like it
belongs in a well-maintained open source library."
```
~50 tokens. Rationale: Frames the output context rather than the user's identity or preferences. "This code will be reviewed" and "portfolio of production-grade Python" set a quality standard through social pressure rather than direct instruction. Tests whether implied audience changes output quality.

```
Profile I (negative constraint): "The user does not want: bare except clauses,
mutable default arguments, global state, magic numbers, deeply nested conditionals,
or god classes. The user does not want comments explaining what code does. Code
should be self-documenting through naming and structure."
```
~50 tokens. Rationale: Defines quality by what to avoid rather than what to produce. Tests whether negative constraints are as effective as positive preferences. Directly addresses known code smells that appear in the exp3 baseline outputs (the refactor task had mutable defaults and bare excepts).

```
Profile J (combined maximum): "The user is an experienced systems engineer who writes
production Python daily. Code will be reviewed by senior engineers and must meet
open-source quality standards. Prefers type-annotated, well-decomposed code using
dataclasses, protocols, and structural pattern matching. Expects early returns,
explicit error types, named constants, and self-documenting structure through naming.
No bare excepts, no mutable defaults, no global state, no god classes."
```
~80 tokens. Rationale: Kitchen sink. Identity + taste + aspirational framing + negative constraints. Tests whether stacking all upward-push mechanisms produces the highest quality, or whether there are diminishing returns.

---

## Why 7 Conditions

The 2 carried profiles (B, D) anchor this experiment to exp3 results. The 5 new profiles form a decomposition of upward-push mechanisms:

```
                    Identity    Taste    Aspirational    Negative
Profile B              —         —           —             —
Profile D              ✓         —           —             —
Profile F              ✓         ✓           —             —
Profile G              —         ✓           —             —
Profile H              —         —           ✓             —
Profile I              —         —           —             ✓
Profile J              ✓         ✓           ✓             ✓
```

### Planned Contrasts

1. **D vs F** — Does adding taste to identity break the ceiling? (The central question)
2. **B vs F** — Does identity + taste beat blank slate? (What D alone could not do)
3. **B vs G** — Does taste alone beat blank slate? (Isolates the taste signal)
4. **F vs G** — Does identity matter when taste is present? (Interaction test)
5. **B vs H** — Does aspirational framing beat blank slate? (Social pressure mechanism)
6. **B vs I** — Do negative constraints beat blank slate? (Avoidance mechanism)
7. **B vs J** — Does the kitchen sink beat blank slate? (Maximum push)
8. **F vs J** — Do aspirational framing and negative constraints add value on top of identity + taste? (Diminishing returns test)

### Key Hypothesis

**Strong form:** Profile F (identity + taste) will produce measurably higher architectural sophistication, type annotation count, and idiomatic density than both Profile D (identity only) and Profile B (blank slate). The taste signal is the missing ingredient that D lacked.

**Weak form:** At least one of the new profiles (F, G, H, I, J) will beat Profile B on at least 3 metrics with medium-to-large effect sizes (d > 0.5). Output expectations as a category can push the ceiling.

**Null result interpretation:** If none of the new profiles beat B, the model's code generation quality is genuinely at ceiling for these prompts regardless of system prompt content. The only way to get better code is better prompts or a better model.

---

## Implementation

### API Routing

Same as exp3. Direct Anthropic API calls via Python SDK.

```python
if profile_id == "B":
    messages = [{"role": "user", "content": task_prompt}]
    response = client.messages.create(
        model=model_id,
        messages=messages,
        max_tokens=4096,
        temperature=0.3
    )
else:
    messages = [{"role": "user", "content": task_prompt}]
    response = client.messages.create(
        model=model_id,
        system=profile_text,
        messages=messages,
        max_tokens=4096,
        temperature=0.3
    )
```

### Verification Checklist
- [ ] Profile B responses have no system prompt (verified via API logs)
- [ ] All profiles are under 200 tokens
- [ ] Task prompts are byte-identical to exp3
- [ ] Temperature is 0.3 for all calls
- [ ] Randomized execution order within each run

### Models
- `claude-sonnet-4-6-20260213`
- `claude-haiku-4-5-20251001`

(Use same model IDs as exp3. If exp3 used different IDs, match those exactly.)

---

## Coding Task Battery

Identical to exp3. Same five tasks, same prompts, same quality spectrums.

1. Token Bucket Rate Limiter (algorithmic)
2. LRU Cache (algorithmic)
3. CLI Task Manager (system design)
4. Pub/Sub Event System (system design)
5. Code Refactor (debugging)

See `/exp3_memory_profiles/prompts/` for exact prompt text.

---

## Run Structure

- 7 profiles × 5 tasks × 2 models × 5 runs = **350 completions**
- Estimated tokens per completion: ~2000 output tokens
- Total output token budget: ~700,000
- Inter-call delay: 1 second (rate limit courtesy)
- Execution order: Randomize within each run. Do not run all of one profile consecutively.

### Dry Run

1 run per condition first (7 × 5 × 2 = 70 completions). Verify:
- All profiles produce valid code
- No profile triggers refusals
- Metrics pipeline works on new profile IDs
- B and D outputs are statistically consistent with exp3 B and D outputs (sanity check)

---

## Evaluation Metrics

Same 24 metrics as exp3. Same analysis scripts. Same composite scores.

### Code Metrics (AST-based)
- cyclomatic_complexity, max_nesting_depth, ast_depth
- function_count, class_count, avg_function_length
- type_annotation_count, unique_imports
- try_except_count, advanced_pattern_count

### Behavioral Metrics
- explanation_length, code_length, total_lines
- comment_lines, comment_ratio
- docstring_count, clarifying_questions

### Composite Scores
- architectural_sophistication
- defensive_coding
- idiomatic_density
- verbosity_ratio
- solution_strategy_score

### Additional Metrics for Exp5

These target the specific patterns the taste profiles request:

- **early_return_count**: Number of `return` statements inside conditional blocks (not at function end). Tests whether "expects early returns" in profiles F, G, J actually produces early returns.
- **named_constant_count**: Number of ALL_CAPS variable assignments. Tests "named constants over magic numbers."
- **magic_number_count**: Number of numeric literals (excluding 0, 1, -1) not assigned to named variables. Inverse of above.
- **bare_except_count**: Number of `except:` without a specific exception type. Tests negative constraint profile I.
- **protocol_usage**: Boolean — does the code use `typing.Protocol` or `typing.runtime_checkable`. Tests protocol preference in profiles F, G, J.
- **dataclass_usage**: Boolean — does the code use `@dataclass` or `@dataclasses.dataclass`. Tests dataclass preference.
- **pattern_match_usage**: Boolean — does the code use `match`/`case` statements. Tests structural pattern matching preference.

---

## Statistical Analysis

### Primary Analysis
- One-way ANOVA across all 7 profiles (omnibus test)
- Planned contrasts (Mann-Whitney U with Bonferroni correction) for the 8 contrasts listed above
- Cohen's d effect sizes for all pairwise comparisons

### Secondary Analysis
- Two-way ANOVA: profile × model interaction (does Sonnet respond to taste signals more than Haiku?)
- Per-task breakdown (which tasks are most sensitive to output expectations?)
- Cross-experiment comparison: B and D outputs compared to exp3 B and D outputs (replication check)
- Dose-response analysis: Do profiles with more upward-push mechanisms (J > F > D > B) show monotonic improvement?

### Power Analysis

With N=5 runs per condition, 2 models, 5 tasks = 50 observations per profile. For planned contrasts between two profiles: 50 vs 50 observations. At alpha=0.05 with Bonferroni correction for 8 contrasts (effective alpha=0.00625), power to detect d=0.8 is ~0.65. Power to detect d=1.0 is ~0.80.

This is underpowered for medium effects (d=0.5). The experiment is designed to detect large effects. If the upward push exists and is large (as exp3's D vs E effects were), we will find it. If the effect is small, we will miss it and can only report trends.

---

## Data Storage

```
exp5_upward_push/
├── EXPERIMENT_SPEC.md
├── profiles/
│   ├── profile_b.txt          (empty — no system prompt)
│   ├── profile_d.txt          (copied from exp3)
│   ├── profile_f.txt
│   ├── profile_g.txt
│   ├── profile_h.txt
│   ├── profile_i.txt
│   └── profile_j.txt
├── prompts/                   (symlinked or copied from exp3)
│   ├── task1_rate_limiter.json
│   ├── task2_lru_cache.json
│   ├── task3_cli_task_manager.json
│   ├── task4_event_system.json
│   └── task5_refactor.json
├── src/
│   ├── run_experiment_v5.py
│   ├── pipeline_v5.py
│   ├── analyze_code.py        (extended with new metrics)
│   ├── analyze_stats.py       (same as exp3)
│   └── utils.py
└── runs/
    ├── dry_run_YYYYMMDD/
    │   ├── results/
    │   │   ├── raw/
    │   │   ├── extracted/
    │   │   └── metrics/
    │   ├── analysis/
    │   └── plots/
    └── full_n5/
        └── (same structure)
```

---

## Contentions and Limitations

### Addressed from prior work (exp3)

1. **Profile length confound.** All profiles are 50-80 tokens. Length variation is minimal and does not correlate with the hypothesis direction (J is longest but not by much).
2. **Task prompt contamination.** Task prompts are byte-identical to exp3 and contain no profile information.
3. **Temperature consistency.** Fixed at 0.3 across all conditions.

### Remaining Concerns

4. **The taste profiles are implicitly instructional.** "Prefers type-annotated code" is closer to a coding instruction than a memory note. The line between "user profile" and "coding guidelines in disguise" is blurry. This is a feature, not a bug — the experiment tests whether memory systems *should* encode output preferences, which requires profiles that do so. But it means positive results don't prove that identity signals push upward; they prove that output expectations in system prompts push upward, which is a less surprising finding.

5. **Profile J may dominate through prompt length, not mechanism stacking.** J is the longest profile and contains the most information. If J wins, it could be because more tokens = more steering, not because the specific combination of mechanisms matters. The F vs J contrast partially addresses this (F is shorter than J but contains identity + taste).

6. **Same tasks as exp3 may already be at ceiling.** If the model's code quality for these specific prompts is genuinely maxed out regardless of system prompt, no profile will break through. Different tasks (harder problems, more ambiguous requirements) might be needed to see upward effects. But using the same tasks is necessary for cross-experiment comparison.

7. **Metric sensitivity.** The new metrics (early_return_count, protocol_usage, etc.) directly measure what the taste profiles request. If Profile F says "use protocols" and the code uses protocols, that is compliance, not quality improvement. The exp3 metrics (architectural_sophistication, idiomatic_density) are the real test of whether taste signals improve general code quality beyond specific compliance.

8. **N=5 is underpowered for medium effects.** Acknowledged in power analysis. This experiment is designed to detect large effects or report null results honestly.

---

## Predicted Outcomes

**Strong form (optimistic):** Profile F beats both B and D on architectural_sophistication and idiomatic_density with d > 0.5. Profile G (taste alone) also beats B, proving that taste signals alone are sufficient. Profile J shows diminishing returns over F, suggesting identity + taste is the sweet spot.

**Weak form:** Profile J (kitchen sink) beats B on at least 3 exp3 metrics. The mechanism works when you stack everything, but individual mechanisms are too weak to detect at N=5.

**Null result:** No profile beats B on any exp3 metric. The model's code generation for these tasks is at ceiling. Output expectations in system prompts do not push code quality upward. The only demonstrated effect of profiles on code is the downward pull from beginner signals (exp3 Profile E).

**Interesting failure mode:** Taste profiles produce code that scores higher on the taste-specific metrics (protocol_usage, early_return_count) but lower on exp3 metrics (architectural_sophistication). The model complies with specific preferences at the cost of overall coherence. Over-specification degrades holistic quality.

---

## Prior Work

- Exp3 (this project): Memory profile effects on code generation. D ≈ B. E << B.
- Exp4 (this project): Memory profile effects on subjective analysis. A > C (d=2.2). Profiles push upward in soft domains.
- Arditi et al. 2024: Refusal in LLMs is mediated by a single direction in the residual stream. Behavioral overlay is separable from capability.
- Anthropic Persona Vectors (Aug 2025): Neural activity patterns control traits like sycophancy and hallucination. The model has an internal representation of who it is talking to.
