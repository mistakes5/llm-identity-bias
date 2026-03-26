"""Experiment 4 pipeline: profile bias in subjective / aesthetics responses.

Steps:
    1. run_experiment   (50-250 API calls) — generation
    2. analyze_text      (local)           — automated text metrics
    3. judge             (haiku/opus)      — LLM-as-judge scoring (gated)
    4. analyze_text      (local)           — re-run to merge judge scores
    5. analyze_stats     (local)           — statistical analysis
    6. visualize         (local)           — plots
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from .utils import setup_logging, ensure_dirs
from .run_experiment_v4 import run_experiment
from .analyze_text import analyze_all as analyze_text
from .judge import judge_all
from .analyze_stats import run_full_analysis as analyze_stats
from .visualize import generate_all_plots as visualize

# Metrics checked for profile-level variance before running the judge step.
_GATE_METRICS: list[str] = [
    "response_length",
    "unique_entity_count",
    "cross_domain_count",
]

# If the maximum std across gate metrics is below this threshold, the judge
# step is skipped to save API spend.
_GATE_STD_THRESHOLD: float = 0.5


def _check_variance_gate(metrics_csv: str, logger) -> bool:
    """Return True if automated metrics show enough profile-level variance.

    Loads the metrics CSV, groups by profile, and computes the standard
    deviation for each gate metric.  If the maximum std across all gate
    metrics is below ``_GATE_STD_THRESHOLD``, returns ``False`` and logs
    a warning.
    """
    csv_path = Path(metrics_csv)
    if not csv_path.exists():
        logger.warning(f"Metrics CSV not found at {csv_path} — skipping gate check")
        return True  # Proceed if we can't check.

    df = pd.read_csv(csv_path)

    available = [m for m in _GATE_METRICS if m in df.columns]
    if not available:
        logger.warning("No gate metrics found in CSV columns — skipping gate check")
        return True

    profile_means = df.groupby("profile")[available].mean()
    stds = profile_means.std()
    max_std = stds.max()

    logger.info(f"Variance gate — per-metric std across profiles: {stds.to_dict()}")
    logger.info(f"  max std = {max_std:.4f}  (threshold = {_GATE_STD_THRESHOLD})")

    if max_std < _GATE_STD_THRESHOLD:
        logger.warning(
            "Automated metrics show minimal profile-level variance "
            f"(max std {max_std:.4f} < {_GATE_STD_THRESHOLD}). "
            "Skipping LLM judge step to save API spend."
        )
        return False

    return True


def run_pipeline(
    base_dir: str = ".",
    run_name: str | None = None,
    models: list[str] | None = None,
    n_runs: int = 5,
    judge_model: str = "haiku",
    judge_runs: int = 3,
    temperature: float = 0.3,
    seed: int = 42,
    skip_experiment: bool = False,
    skip_judge: bool = False,
    skip_analysis: bool = False,
    resume: bool = True,
    dry_run: bool = False,
) -> None:
    """
    Full Experiment 4 pipeline:
    1. run_experiment (50-250 API calls) — generation
    2. analyze_text (local) — automated text metrics
    3. judge (haiku/opus) — LLM-as-judge, GATED on variance
    4. analyze_text (local) — re-run to merge judge scores
    5. analyze_stats (local) — statistical analysis
    6. visualize (local) — plots
    """
    base = Path(base_dir)

    if dry_run:
        n_runs = 1

    if run_name is None:
        if dry_run:
            run_name = f"dry_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        else:
            run_name = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base / "runs" / run_name

    logger = setup_logging(str(run_dir), "pipeline")
    logger.info("Experiment 4 — Subjective / Aesthetics Profile Bias")
    logger.info(f"Run output directory: {run_dir}")
    if dry_run:
        logger.info("DRY RUN mode: n_runs=1")

    dirs = {
        "profiles": base / "profiles",
        "prompts": base / "prompts",
        "rubrics": base / "rubrics",
        "results": run_dir / "results",
        "raw": run_dir / "results" / "raw",
        "metrics": run_dir / "results" / "metrics",
        "judge": run_dir / "results" / "judge",
        "analysis": run_dir / "analysis",
        "plots": run_dir / "plots",
    }
    for d in dirs.values():
        ensure_dirs(str(d))

    total_start = time.time()

    # Step 1: Run experiment
    if not skip_experiment:
        logger.info("=" * 60)
        total_calls = (len(models) if models else 2) * 5 * 5 * n_runs
        logger.info(f"STEP 1/6: Running experiment ({total_calls} API calls)")
        logger.info("=" * 60)
        step_start = time.time()
        usage = run_experiment(
            profiles_dir=str(dirs["profiles"]),
            prompts_dir=str(dirs["prompts"]),
            output_dir=str(dirs["results"]),
            models=models,
            n_runs=n_runs,
            temperature=temperature,
            seed=seed,
            resume=resume,
            logger=logger,
        )
        logger.info(f"Step 1 completed in {time.time() - step_start:.1f}s")
        logger.info(f"  Usage: {usage}")
    else:
        logger.info("Skipping step 1 (experiment)")

    if not skip_analysis:
        logger.info("=" * 60)
        logger.info("STEPS 2-6: Analysis pipeline")
        logger.info("=" * 60)

        metrics_csv = str(dirs["metrics"] / "metrics_table.csv")

        # Step 2: Analyze text metrics
        logger.info("-" * 40)
        logger.info("STEP 2/6: Computing text metrics")
        step_start = time.time()
        analyze_text(
            raw_dir=str(dirs["raw"]),
            metrics_dir=str(dirs["metrics"]),
            log=logger,
        )
        logger.info(f"Step 2 completed in {time.time() - step_start:.1f}s")

        # Step 3: Judge (gated on variance)
        run_judge = not skip_judge
        if run_judge:
            run_judge = _check_variance_gate(metrics_csv, logger)

        if run_judge:
            logger.info("-" * 40)
            logger.info(f"STEP 3/6: LLM-as-judge scoring (model={judge_model}, runs={judge_runs})")
            step_start = time.time()
            judge_all(
                raw_dir=str(dirs["raw"]),
                rubrics_dir=str(dirs["rubrics"]),
                judge_dir=str(dirs["judge"]),
                model=judge_model,
                n_runs=judge_runs,
                log=logger,
            )
            logger.info(f"Step 3 completed in {time.time() - step_start:.1f}s")
        else:
            logger.info("Skipping step 3 (judge)")

        # Step 4: Re-run text metrics to merge judge scores
        logger.info("-" * 40)
        logger.info("STEP 4/6: Re-computing text metrics (merging judge scores)")
        step_start = time.time()
        analyze_text(
            raw_dir=str(dirs["raw"]),
            metrics_dir=str(dirs["metrics"]),
            judge_dir=str(dirs["judge"]),
            log=logger,
        )
        logger.info(f"Step 4 completed in {time.time() - step_start:.1f}s")

        # Step 5: Statistical analysis
        logger.info("-" * 40)
        logger.info("STEP 5/6: Running statistical analysis")
        step_start = time.time()
        analyze_stats(csv_path=metrics_csv, output_dir=str(dirs["analysis"]))
        logger.info(f"Step 5 completed in {time.time() - step_start:.1f}s")

        # Step 6: Visualization
        logger.info("-" * 40)
        logger.info("STEP 6/6: Generating plots")
        step_start = time.time()
        plots = visualize(
            metrics_csv=metrics_csv,
            analysis_dir=str(dirs["analysis"]),
            output_dir=str(dirs["plots"]),
        )
        logger.info(f"Step 6 completed in {time.time() - step_start:.1f}s")
        logger.info(f"  Generated {len(plots)} plots")

    total_elapsed = time.time() - total_start
    logger.info("=" * 60)
    logger.info(f"PIPELINE COMPLETE in {total_elapsed:.1f}s ({total_elapsed/60:.1f} minutes)")
    logger.info(f"  Run: {run_dir}")
    logger.info("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Experiment 4: subjective analysis profile bias")
    parser.add_argument("--base-dir", default=".")
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--n-runs", type=int, default=5)
    parser.add_argument("--judge-model", default="haiku")
    parser.add_argument("--judge-runs", type=int, default=3)
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-experiment", action="store_true")
    parser.add_argument("--skip-judge", action="store_true")
    parser.add_argument("--skip-analysis", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="N=1 for testing")
    args = parser.parse_args()

    run_pipeline(
        base_dir=args.base_dir,
        run_name=args.run_name,
        n_runs=args.n_runs,
        judge_model=args.judge_model,
        judge_runs=args.judge_runs,
        temperature=args.temperature,
        seed=args.seed,
        skip_experiment=args.skip_experiment,
        skip_judge=args.skip_judge,
        skip_analysis=args.skip_analysis,
        resume=not args.no_resume,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
