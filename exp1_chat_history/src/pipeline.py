"""End-to-end experiment pipeline with resume, timing, and cost estimation."""

import argparse
import time
import sys
import os
from datetime import datetime
from pathlib import Path

from .utils import AnthropicClient, setup_logging, ensure_dirs
from .generate_profiles import generate_all as generate_profiles
from .run_experiment import run_experiment
from .extract_code import extract_all as extract_code
from .analyze_code import analyze_all as analyze_code
from .analyze_stats import run_full_analysis as analyze_stats
from .visualize import generate_all_plots as visualize


def run_pipeline(
    base_dir: str = ".",
    run_name: str | None = None,
    models: list[str] | None = None,
    n_runs: int = 5,
    temperature: float = 0.3,
    skip_profile_gen: bool = False,
    skip_experiment: bool = False,
    skip_analysis: bool = False,
    resume: bool = True,
) -> None:
    """
    Full pipeline:
    1. generate_profiles (32 API calls, ~$0.50) — skip if transcripts exist or --skip-profile-gen
    2. run_experiment (150 API calls, ~$8) — resume from where it stopped
    3. extract_code (local, fast)
    4. analyze_code (local, fast)
    5. analyze_stats (local, fast)
    6. visualize (local, fast)
    """
    base = Path(base_dir)

    # Each run gets its own labeled folder inside runs/
    if run_name is None:
        run_name = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base / "runs" / run_name

    logger = setup_logging(str(run_dir), "pipeline")
    logger.info(f"Run output directory: {run_dir}")

    dirs = {
        "scripts": base / "scripts",
        "transcripts": base / "transcripts",
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

    # Step 1: Generate profile transcripts
    if not skip_profile_gen:
        logger.info("=" * 60)
        logger.info("STEP 1/6: Generating profile conversation transcripts")
        logger.info("  This step costs money (32 API calls, ~$0.50)")
        logger.info("=" * 60)
        step_start = time.time()
        generate_profiles(
            scripts_dir=str(dirs["scripts"]),
            output_dir=str(dirs["transcripts"]),
            models=models,
            logger=logger,
        )
        logger.info(f"Step 1 completed in {time.time() - step_start:.1f}s")
    else:
        logger.info("Skipping step 1 (profile generation)")

    # Step 2: Run experiment
    if not skip_experiment:
        logger.info("=" * 60)
        logger.info(f"STEP 2/6: Running coding experiment ({n_runs} runs per cell)")
        total_calls = 2 * 3 * 5 * n_runs  # models * profiles * tasks * runs
        logger.info(f"  This step costs money ({total_calls} API calls, ~${total_calls * 0.055:.2f})")
        logger.info("=" * 60)
        step_start = time.time()
        usage = run_experiment(
            transcripts_dir=str(dirs["transcripts"]),
            prompts_dir=str(dirs["prompts"]),
            output_dir=str(dirs["results"]),
            models=models,
            n_runs=n_runs,
            temperature=temperature,
            resume=resume,
            logger=logger,
        )
        logger.info(f"Step 2 completed in {time.time() - step_start:.1f}s")
        logger.info(f"  Usage: {usage}")
    else:
        logger.info("Skipping step 2 (experiment)")

    # Steps 3-6: Local analysis (no API calls, free)
    if not skip_analysis:
        logger.info("=" * 60)
        logger.info("STEPS 3-6: Local analysis (no API calls)")
        logger.info("=" * 60)

        # Step 3: Extract code
        logger.info("-" * 40)
        logger.info("STEP 3/6: Extracting code from responses")
        step_start = time.time()
        extract_code(
            raw_dir=str(dirs["raw"]),
            extracted_dir=str(dirs["extracted"]),
            logger=logger,
        )
        logger.info(f"Step 3 completed in {time.time() - step_start:.1f}s")

        # Step 4: Analyze code metrics
        logger.info("-" * 40)
        logger.info("STEP 4/6: Computing code metrics")
        step_start = time.time()
        analyze_code(
            extracted_dir=str(dirs["extracted"]),
            raw_dir=str(dirs["raw"]),
            metrics_dir=str(dirs["metrics"]),
            log=logger,
        )
        logger.info(f"Step 4 completed in {time.time() - step_start:.1f}s")

        # Step 5: Statistical analysis
        logger.info("-" * 40)
        logger.info("STEP 5/6: Running statistical analysis")
        step_start = time.time()
        csv_path = str(dirs["metrics"] / "metrics_table.csv")
        analyze_stats(
            csv_path=csv_path,
            output_dir=str(dirs["analysis"]),
        )
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
    logger.info(f"  Results: {dirs['raw']}")
    logger.info(f"  Metrics: {dirs['metrics']}")
    logger.info(f"  Analysis: {dirs['analysis']}")
    logger.info(f"  Plots: {dirs['plots']}")
    logger.info("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full profile bias experiment pipeline")
    parser.add_argument("--base-dir", default=".", help="Base experiment directory")
    parser.add_argument("--run-name", default=None, help="Label for this run (default: timestamp)")
    parser.add_argument("--n-runs", type=int, default=5, help="Runs per cell (default: 5)")
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--skip-profile-gen", action="store_true", help="Skip transcript generation")
    parser.add_argument("--skip-experiment", action="store_true", help="Skip API calls")
    parser.add_argument("--skip-analysis", action="store_true", help="Skip local analysis")
    parser.add_argument("--no-resume", action="store_true", help="Don't resume from existing results")
    parser.add_argument("--dry-run", action="store_true", help="Run with n_runs=1 for testing")
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
        skip_profile_gen=args.skip_profile_gen,
        skip_experiment=args.skip_experiment,
        skip_analysis=args.skip_analysis,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
