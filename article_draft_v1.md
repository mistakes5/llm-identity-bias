# Does Claude Write Better Code If It Thinks You're Smart?

250 API calls. Five fake identities. The answer was no.

---

I gave Claude five different user profiles and asked it the same coding questions across all of them. Same prompts. Same model. Same temperature. The only variable was a short description of the user, injected into the system prompt. The kind of thing Claude's memory system builds about you after a few conversations.

One profile described an experienced data engineer who builds ETL pipelines in Scala and manages Kubernetes clusters. Another described someone who started learning Python a few months ago and has never used a class. The other three sat between those two poles: a philosopher, a surface-level casual user, and a blank slate with no profile at all.

Five profiles. Five coding tasks. Two models (Sonnet 4.6, Haiku 4.5). Five runs each. 250 completions total, scored on 24 automated metrics.

I expected the senior engineer profile to win. Obvious hypothesis.

---

## The Obvious Result

Profile D versus Profile E was a massacre.

[VISUAL: Bar chart showing D vs E across key metrics, effect sizes labeled]

Type annotation count: d = 1.71. That is an enormous effect. Profile D averaged 18.9 type annotations per completion. Profile E averaged 2.1. The model looked at the beginner profile and stripped the types out entirely.

Architectural sophistication: d = 1.40. Class count: d = 1.19. Idiomatic density: d = 1.31. Thirteen metrics were statistically significant between D and E after Bonferroni correction. Thirteen.

The code was functionally identical. Both profiles produced a working LRU cache, a working rate limiter, a working event system. But the structure, the typing, the decomposition, the level of explanation changed completely based on who the model thought was asking.

[VISUAL: Side-by-side code comparison, Profile D vs Profile E, LRU Cache task. Haiku, same run. Annotate the differences: type hints present/absent, comment density, return types]

Profile D got `from typing import Optional, Any`, sentinel nodes, a `ValueError` guard on capacity, terse docstrings. Profile E got the same algorithm with twice the comments explaining what a pointer is, no type hints anywhere, `prev_node`/`next_node` spelled out for clarity, and `-1` returns instead of `None`. The Profile E version is 125 lines. Profile D is 90. The difference is almost entirely comments the model decided a beginner would need.

So far, nothing surprising. Tell the model you're experienced, get experienced code. Tell it you're learning, get training wheels.

---

## The Part I Did Not Expect

Profile B (no profile, no system prompt, blank context) matched Profile D on almost everything.

[VISUAL: Table or grouped bar chart showing B vs D across key metrics, showing they're nearly identical]

Architectural sophistication: D = 6.31, B = 6.03. Type annotations: D = 18.9, B = 16.8. Idiomatic density: D = 5.63, B = 5.61. Function count: D = 10.9, B = 11.7. Advanced pattern count: D = 10.4, B = 10.8.

B actually beat D on several raw metrics. More functions, more advanced patterns, more cyclomatic complexity. The planned contrasts between "has any profile at all" versus "no profile" found zero significant effects after correction.

I assumed giving the model a strong identity to work with would produce the best output. It did not. A blank context performed at the same level as a carefully crafted senior engineer profile. The senior engineer profile bought type annotations and class organization. It did not buy better code.

---

## The Other Surprise

Profile A (the philosopher, the person who reads academic papers and builds layered arguments) and Profile C (the surface-level, simple-answers person) produced functionally identical code.

[VISUAL: A vs C comparison, showing near-zero differences. One bar chart.]

One significant metric between A and C. One. Explanation length (d = 0.55). The model gave the philosopher longer explanations. That was the entire effect. Architectural sophistication, type annotations, class count, complexity: all statistically indistinguishable.

The model does not generalize from "sounds smart" to "write smart code." It reads technical competence signals. It reads coding-specific identity markers. General intelligence, cross-domain sophistication, academic vocabulary: the model ignores all of it when deciding how to structure your code.

---

## Why This Matters If You Use Claude Code

Every Claude Code user has a memory file. Every conversation builds context. And the conventional wisdom among power users is to refresh that context constantly, clear the memory, start new sessions. The data suggests they are right, but maybe for the wrong reason.

The model with zero context matched the model with a senior engineer context. So the value of clearing your context is not that you're removing noise. The value is that you're preventing the model from accumulating the wrong signal about you.

One offhand question about a basic concept. One moment where you paste an error message and say "I don't understand this." The model updates its internal representation of your competence. And if that representation drifts toward Profile E, even slightly, you start losing type annotations. You start getting longer comments explaining things you already know. The code gets simpler in ways you did not ask for.

[VISUAL: Conceptual diagram showing context accumulation over time, with competence signal degrading]

There is a running conversation on Twitter about Opus 4.6 degrading over extended sessions. Benchmarks exist, and models do degrade with long contexts. But how much of the perceived degradation is the model reading your accumulated context and deciding you need simpler output? The model treating your confusion from turn 40 as evidence about your competence on turn 200? I don't have the data to answer that definitively. But the mechanism is there. This experiment proves the mechanism works.

---

## The Uncomfortable Part

This is about coding. One subject. Constrained, measurable, automatable.

But the same memory systems, the same context accumulation, the same profile inference is happening in every conversation you have with these models. And most of those conversations are not about code.

If you talk to an LLM regularly (those of us deep enough in this to admit it), the model is building a profile of you whether you asked it to or not. That profile affects what it gives you. The Anthropic team published research on this in August 2025. They found what they called "persona vectors," actual directions in the model's activation space that control traits like sycophancy and hallucination. The model has an internal concept of who it is talking to, and that concept changes the output.

So the question is not whether this effect exists. The question is whether you have thought about what it means that every conversation you have with these models is training them to see you a certain way. And whether that representation is the one you want.

---

## Methodology

For anyone who wants the details or wants to reproduce this.

Models: Claude Sonnet 4.6, Claude Haiku 4.5. Direct API calls via the Anthropic SDK. Temperature fixed at 0.3. No system prompt contamination (Profile B had literally no system prompt, not an empty one).

Five coding tasks spanning different skill domains: token bucket rate limiter, LRU cache, CLI task manager, pub/sub event system, and a refactor task. Five runs per profile per task per model. 250 total completions.

24 automated metrics computed via AST parsing: cyclomatic complexity, nesting depth, function/class counts, type annotation counts, import diversity, docstring density, comment ratio, and composite scores for architectural sophistication, defensive coding, and idiomatic density.

Statistical analysis: one-way and two-way ANOVA, Mann-Whitney U with Bonferroni correction, Kruskal-Wallis H-test for robustness, Cohen's d effect sizes, PELT change-point detection.

The full dataset, code, and analysis pipeline are available [here].

[VISUAL: Summary statistics table, clean, showing all 5 profiles across 5-6 key metrics]

---

*I built this experiment with Claude Code. The irony is not lost on me.*
