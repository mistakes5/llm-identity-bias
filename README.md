# LLM Identity Bias Experiments

This repo collects prompt-profile calibration experiments across coding, subjective analysis, and hybrid frontend tasks. Each experiment folder is self-contained with its spec, prompts, profiles, code, and any published run artifacts.

## Layout

- `exp1_chat_history`: early coding-task baseline with a completed clean dry run.
- `exp3_memory_profiles`: coding-focused profile-bias experiment with published dry-run and `full_n5` outputs.
- `exp4_subjective_analysis`: aesthetics / subjective-analysis experiment. Includes an older published dry run, a newer completed dry run, and an incomplete scheduled full run.
- `exp5_hybrid_frontend`: hybrid React + design experiment. Code/specs are present; the newest dry run is documented as unfinished.
- `exp5_upward_push`: draft experiment scaffold only.
- `exp6_persona_override`: draft experiment scaffold only.

## Recent Status

- `exp4_subjective_analysis/runs/dry_run_20260327_153818` is a completed dry run with a run-level summary.
- `exp4_subjective_analysis/runs/full_n5` is unfinished. The first scheduled batch failed immediately because `claude` was not on `PATH` in the launchd environment.
- `exp5_hybrid_frontend/runs/dry_run_20260327_210258` is unfinished. Generation stopped at 49/50 raw outputs and never reached extraction, judge, or stats.

## Publish Hygiene

- Batch scripts now resolve their experiment directory relative to the script instead of hard-coding a home-directory path.
- Statistical analysis no longer depends on a private file path outside the repo. If no external detector is configured, it falls back to a small in-repo detector.
- New summaries were added for the recent runs so incomplete work is clearly labeled before publication.
