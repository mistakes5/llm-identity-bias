"""Experiment 5 pipeline: hybrid code + design profile bias.

Steps:
    1. run_experiment   (API calls)  -- generation
    2. extract_jsx      (local)      -- extract React code from responses
    3. analyze_react    (local)      -- compute code metrics
    4. judge            (API calls)  -- LLM-as-judge design scoring (gated)
    5. analyze_react    (local)      -- re-run to merge judge scores
    6. analyze_stats    (local)      -- statistical analysis
    7. visualize        (local)      -- plots
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from .utils import setup_logging, ensure_dirs
from .run_experiment_v5 import run_experiment
from .extract_jsx import extract_all as extract_jsx
from .analyze_react import analyze_all as analyze_react
from .judge import judge_all
from .analyze_stats import run_full_analysis as analyze_stats
from .visualize import generate_all_plots as visualize

# Gate: minimum extraction success rate before running judge.
_EXTRACTION_GATE_THRESHOLD: float = 0.50


def _check_extraction_gate(extraction_summary: dict, logger) -> bool:
    """Return True if enough responses were successfully extracted."""
    total = extraction_summary.get("total", 0) - extraction_summary.get("skipped", 0)
    extracted = extraction_summary.get("extracted", 0)

    if total == 0:
        logger.warning("No responses to extract -- skipping judge.")
        return False

    rate = extracted / total
    logger.info(f"Extraction gate: {extracted}/{total} = {rate:.1%} (threshold = {_EXTRACTION_GATE_THRESHOLD:.0%})")

    if rate < _EXTRACTION_GATE_THRESHOLD:
        logger.warning(
            f"Extraction success rate {rate:.1%} below threshold {_EXTRACTION_GATE_THRESHOLD:.0%}. "
            "Skipping judge to investigate extraction failures."
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
    max_calls: int | None = None,
) -> None:
    """Full Experiment 5 pipeline."""
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
    logger.info("Experiment 5 -- Hybrid Frontend: Code + Design Profile Bias")
    logger.info(f"Run output directory: {run_dir}")
    if dry_run:
        logger.info("DRY RUN mode: n_runs=1")

    dirs = {
        "profiles": base / "profiles",
        "prompts": base / "prompts",
        "rubrics": base / "rubrics",
        "results": run_dir / "results",
        "raw": run_dir / "results" / "raw",
        "extracted": run_dir / "results" / "extracted",
        "metrics": run_dir / "results" / "metrics",
        "judge": run_dir / "results" / "judge",
        "analysis": run_dir / "analysis",
        "plots": run_dir / "plots",
    }
    for d in dirs.values():
        ensure_dirs(str(d))

    total_start = time.time()
    remaining_budget = max_calls

    # Step 1: Run experiment (generation)
    if not skip_experiment:
        logger.info("=" * 60)
        total_calls = (len(models) if models else 2) * 5 * 5 * n_runs
        logger.info(f"STEP 1/7: Running experiment ({total_calls} API calls)")
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
            max_calls=remaining_budget,
        )
        logger.info(f"Step 1 completed in {time.time() - step_start:.1f}s")
        logger.info(f"  Usage: {usage}")
        if remaining_budget is not None:
            remaining_budget = max(0, remaining_budget - usage.get("calls_made", 0))
            logger.info(f"  Remaining budget: {remaining_budget} calls")
    else:
        logger.info("Skipping step 1 (experiment)")

    # Step 2: Extract JSX from responses
    logger.info("=" * 60)
    logger.info("STEP 2/7: Extracting React code from responses")
    logger.info("=" * 60)
    step_start = time.time()
    extraction_summary = extract_jsx(
        raw_dir=str(dirs["raw"]),
        extracted_dir=str(dirs["extracted"]),
        log=logger,
    )
    logger.info(f"Step 2 completed in {time.time() - step_start:.1f}s")

    # Step 3: Compute code metrics
    logger.info("-" * 40)
    logger.info("STEP 3/7: Computing React code metrics")
    step_start = time.time()
    analyze_react(
        raw_dir=str(dirs["raw"]),
        extracted_dir=str(dirs["extracted"]),
        metrics_dir=str(dirs["metrics"]),
        log=logger,
    )
    logger.info(f"Step 3 completed in {time.time() - step_start:.1f}s")

    # Step 4: Judge (gated on extraction success)
    run_judge = not skip_judge
    if run_judge:
        run_judge = _check_extraction_gate(extraction_summary, logger)

    if run_judge:
        logger.info("-" * 40)
        logger.info(f"STEP 4/7: LLM-as-judge design scoring (model={judge_model}, runs={judge_runs})")
        step_start = time.time()
        judge_summary = judge_all(
            raw_dir=str(dirs["raw"]),
            extracted_dir=str(dirs["extracted"]),
            rubrics_dir=str(dirs["rubrics"]),
            judge_dir=str(dirs["judge"]),
            model=judge_model,
            n_runs=judge_runs,
            log=logger,
            max_calls=remaining_budget,
        )
        logger.info(f"Step 4 completed in {time.time() - step_start:.1f}s")
        if remaining_budget is not None:
            remaining_budget = max(0, remaining_budget - judge_summary.get("calls_made", 0))
            logger.info(f"  Remaining budget: {remaining_budget} calls")
    else:
        logger.info("Skipping step 4 (judge)")

    if not skip_analysis:
        # Step 5: Re-compute metrics with judge scores merged
        logger.info("-" * 40)
        logger.info("STEP 5/7: Re-computing metrics (merging judge scores)")
        step_start = time.time()
        analyze_react(
            raw_dir=str(dirs["raw"]),
            extracted_dir=str(dirs["extracted"]),
            metrics_dir=str(dirs["metrics"]),
            judge_dir=str(dirs["judge"]),
            log=logger,
        )
        logger.info(f"Step 5 completed in {time.time() - step_start:.1f}s")

        metrics_csv = str(dirs["metrics"] / "metrics_table.csv")

        # Step 6: Statistical analysis
        logger.info("-" * 40)
        logger.info("STEP 6/7: Running statistical analysis")
        step_start = time.time()
        analyze_stats(csv_path=metrics_csv, output_dir=str(dirs["analysis"]))
        logger.info(f"Step 6 completed in {time.time() - step_start:.1f}s")

        # Step 7: Visualization
        logger.info("-" * 40)
        logger.info("STEP 7/7: Generating plots")
        step_start = time.time()
        plots = visualize(
            metrics_csv=metrics_csv,
            analysis_dir=str(dirs["analysis"]),
            output_dir=str(dirs["plots"]),
        )
        logger.info(f"Step 7 completed in {time.time() - step_start:.1f}s")
        logger.info(f"  Generated {len(plots)} plots")

    total_elapsed = time.time() - total_start
    logger.info("=" * 60)
    logger.info(f"PIPELINE COMPLETE in {total_elapsed:.1f}s ({total_elapsed / 60:.1f} minutes)")
    logger.info(f"  Run: {run_dir}")
    logger.info("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Experiment 5: hybrid frontend profile bias")
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
    parser.add_argument("--max-calls", type=int, default=None,
                        help="Max API calls per batch (for scheduled runs)")
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
        max_calls=args.max_calls,
    )


if __name__ == "__main__":
    main()
