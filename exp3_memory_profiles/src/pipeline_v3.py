"""Experiment 3 pipeline: memory-level profile bias in code generation."""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

from .utils import setup_logging, ensure_dirs
from .run_experiment_v3 import run_experiment
from .extract_code import extract_all as extract_code
from .analyze_code import analyze_all as analyze_code
from .classify_strategy import classify_all as classify_strategy
from .analyze_stats import run_full_analysis as analyze_stats
from .visualize import generate_all_plots as visualize


def run_pipeline(
    base_dir: str = "experiment_3",
    run_name: str | None = None,
    models: list[str] | None = None,
    n_runs: int = 5,
    temperature: float = 0.3,
    seed: int = 42,
    skip_experiment: bool = False,
    skip_analysis: bool = False,
    skip_classification: bool = False,
    resume: bool = True,
) -> None:
    """
    Full Experiment 3 pipeline:
    1. run_experiment (250 API calls) — profiles as system prompts
    2. extract_code (local)
    3. analyze_code (local)
    4. classify_strategy (uses haiku for cheap LLM judging)
    5. analyze_stats (local)
    6. visualize (local)
    """
    base = Path(base_dir)

    if run_name is None:
        run_name = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base / "runs" / run_name

    logger = setup_logging(str(run_dir), "pipeline")
    logger.info(f"Experiment 3 — Memory-Level Profile Bias")
    logger.info(f"Run output directory: {run_dir}")

    dirs = {
        "profiles": base / "profiles",
        "prompts": base / "prompts",
        "results": run_dir / "results",
        "raw": run_dir / "results" / "raw",
        "extracted": run_dir / "results" / "extracted",
        "metrics": run_dir / "results" / "metrics",
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

        # Step 2: Extract code
        logger.info("-" * 40)
        logger.info("STEP 2/6: Extracting code")
        step_start = time.time()
        extract_code(
            raw_dir=str(dirs["raw"]),
            extracted_dir=str(dirs["extracted"]),
            logger=logger,
        )
        logger.info(f"Step 2 completed in {time.time() - step_start:.1f}s")

        # Step 3: Analyze code metrics
        logger.info("-" * 40)
        logger.info("STEP 3/6: Computing code metrics")
        step_start = time.time()
        analyze_code(
            extracted_dir=str(dirs["extracted"]),
            raw_dir=str(dirs["raw"]),
            metrics_dir=str(dirs["metrics"]),
            log=logger,
        )
        logger.info(f"Step 3 completed in {time.time() - step_start:.1f}s")

        # Step 4: Strategy classification (LLM judge)
        if not skip_classification:
            logger.info("-" * 40)
            logger.info("STEP 4/6: Classifying solution strategies (LLM judge)")
            step_start = time.time()
            classify_strategy(
                extracted_dir=str(dirs["extracted"]),
                analysis_dir=str(dirs["analysis"]),
                metrics_csv=str(dirs["metrics"] / "metrics_table.csv"),
                log=logger,
            )
            logger.info(f"Step 4 completed in {time.time() - step_start:.1f}s")
        else:
            logger.info("Skipping step 4 (strategy classification)")

        # Step 5: Statistical analysis
        logger.info("-" * 40)
        logger.info("STEP 5/6: Running statistical analysis")
        step_start = time.time()
        csv_path = str(dirs["metrics"] / "metrics_table.csv")
        analyze_stats(csv_path=csv_path, output_dir=str(dirs["analysis"]))
        logger.info(f"Step 5 completed in {time.time() - step_start:.1f}s")

        # Step 6: Visualization
        logger.info("-" * 40)
        logger.info("STEP 6/6: Generating plots")
        step_start = time.time()
        plots = visualize(
            metrics_csv=csv_path,
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
    parser = argparse.ArgumentParser(description="Experiment 3: memory-level profile bias")
    parser.add_argument("--base-dir", default="experiment_3")
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--n-runs", type=int, default=5)
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-experiment", action="store_true")
    parser.add_argument("--skip-analysis", action="store_true")
    parser.add_argument("--skip-classification", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="N=1 for testing")
    args = parser.parse_args()

    n_runs = 1 if args.dry_run else args.n_runs
    run_name = args.run_name
    if run_name is None and args.dry_run:
        run_name = f"dry_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    run_pipeline(
        base_dir=args.base_dir,
        run_name=run_name,
        n_runs=n_runs,
        temperature=args.temperature,
        seed=args.seed,
        skip_experiment=args.skip_experiment,
        skip_analysis=args.skip_analysis,
        skip_classification=args.skip_classification,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
