"""Core experiment runner: send coding prompts with profile context to models.

Runs a full factorial design: 3 profiles x 5 tasks x 2 models x N runs.
Each result is saved individually so the experiment can be resumed after
interruption without repeating completed calls.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .utils import AnthropicClient, save_json, load_json, setup_logging, ensure_dirs

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODELS: list[str] = [
    "claude-sonnet-4",
    "claude-haiku-4",
]

MODEL_SHORT: dict[str, str] = {
    "claude-sonnet-4": "sonnet",
    "claude-haiku-4": "haiku",
}

PROFILES: list[str] = ["A", "B", "C"]

TEMPERATURE: float = 0.3


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_transcript(
    transcripts_dir: str | Path,
    model_short: str,
    profile: str,
) -> list[dict[str, str]]:
    """Load a frozen profile transcript.

    Returns an empty list for profile B (the no-context control condition).
    """
    if profile == "B":
        return []
    path = Path(transcripts_dir) / model_short / f"profile_{profile.lower()}.json"
    data: dict[str, Any] = load_json(str(path))
    return data["transcript"]


def load_tasks(prompts_dir: str | Path) -> list[dict[str, Any]]:
    """Load all ``task*.json`` files from *prompts_dir*.

    Returns a list of task dicts sorted by filename (and therefore task_id).
    """
    tasks: list[dict[str, Any]] = []
    for f in sorted(Path(prompts_dir).glob("task*.json")):
        tasks.append(load_json(str(f)))
    return tasks


# ---------------------------------------------------------------------------
# Single run
# ---------------------------------------------------------------------------


def run_single(
    client: AnthropicClient,
    model: str,
    profile: str,
    task: dict[str, Any],
    run_id: int,
    transcript: list[dict[str, str]],
    temperature: float = TEMPERATURE,
) -> dict[str, Any]:
    """Execute a single coding completion and return a result dict.

    Constructs the message array as ``transcript + [user coding prompt]``,
    sends it via *client*, and packages response metadata for storage.
    """
    messages: list[dict[str, str]] = transcript + [
        {"role": "user", "content": task["prompt"]},
    ]

    start: float = time.time()
    response: dict[str, Any] = client.send(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=4096,
    )
    elapsed_ms: float = (time.time() - start) * 1000

    return {
        "model": model,
        "model_short": MODEL_SHORT[model],
        "profile": profile,
        "task_id": task["task_id"],
        "task_name": task["name"],
        "run_id": run_id,
        "temperature": temperature,
        "response_text": response["text"],
        "stop_reason": response["stop_reason"],
        "input_tokens": response["input_tokens"],
        "output_tokens": response["output_tokens"],
        "elapsed_ms": round(elapsed_ms, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "transcript_turns": len(transcript),
    }


# ---------------------------------------------------------------------------
# Full experiment loop
# ---------------------------------------------------------------------------


def run_experiment(
    transcripts_dir: str | Path,
    prompts_dir: str | Path,
    output_dir: str | Path,
    models: list[str] | None = None,
    n_runs: int = 5,
    temperature: float = TEMPERATURE,
    resume: bool = True,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """Run the full factorial experiment, saving each result individually.

    Parameters
    ----------
    transcripts_dir:
        Directory containing frozen profile transcripts organized by model.
    prompts_dir:
        Directory containing ``task*.json`` prompt files.
    output_dir:
        Root output directory; raw results go into ``<output_dir>/raw/``.
    models:
        Model identifiers to test. Defaults to :data:`MODELS`.
    n_runs:
        Number of independent runs per (model, profile, task) cell.
    temperature:
        Sampling temperature for all calls.
    resume:
        When ``True``, skip cells whose output file already exists.
    logger:
        Logger instance. If ``None``, a basic fallback is created.

    Returns
    -------
    dict
        Cumulative usage summary from :meth:`AnthropicClient.get_usage_summary`.
    """
    if models is None:
        models = MODELS
    if logger is None:
        logger = logging.getLogger("run_experiment")

    client = AnthropicClient(
        default_temperature=temperature,
        default_max_tokens=4096,
    )
    tasks: list[dict[str, Any]] = load_tasks(prompts_dir)

    raw_dir: Path = Path(output_dir) / "raw"
    ensure_dirs(str(raw_dir))

    total: int = len(models) * len(PROFILES) * len(tasks) * n_runs
    completed: int = 0
    skipped: int = 0

    for model in models:
        short: str = MODEL_SHORT[model]
        for profile in PROFILES:
            transcript: list[dict[str, str]] = load_transcript(
                transcripts_dir, short, profile,
            )
            for task in tasks:
                for run in range(1, n_runs + 1):
                    filename: str = f"{short}_{profile}_{task['task_id']}_run{run}.json"
                    out_path: Path = raw_dir / filename

                    if resume and out_path.exists():
                        skipped += 1
                        continue

                    completed += 1
                    logger.info(
                        "[%d/%d] %s profile_%s %s run%d",
                        completed + skipped, total, short, profile,
                        task["task_id"], run,
                    )

                    result: dict[str, Any] = run_single(
                        client, model, profile, task, run, transcript, temperature,
                    )
                    save_json(result, str(out_path))

                    logger.info(
                        "  -> %d in, %d out, %.1fms",
                        result["input_tokens"],
                        result["output_tokens"],
                        result["elapsed_ms"],
                    )

    usage: dict[str, Any] = client.get_usage_summary()
    logger.info(
        "Experiment complete. %d calls made, %d skipped (resume). Usage: %s",
        completed, skipped, usage,
    )
    return usage


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse arguments and launch the experiment."""
    parser = argparse.ArgumentParser(
        description="Run the profile bias coding experiment",
    )
    parser.add_argument("--transcripts-dir", default="transcripts")
    parser.add_argument("--prompts-dir", default="prompts")
    parser.add_argument("--output-dir", default="results")
    parser.add_argument("--n-runs", type=int, default=5)
    parser.add_argument("--temperature", type=float, default=TEMPERATURE)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    logger: logging.Logger = setup_logging(args.output_dir, "run_experiment")

    run_experiment(
        transcripts_dir=args.transcripts_dir,
        prompts_dir=args.prompts_dir,
        output_dir=args.output_dir,
        n_runs=args.n_runs,
        temperature=args.temperature,
        resume=not args.no_resume,
        logger=logger,
    )


if __name__ == "__main__":
    main()
