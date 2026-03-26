"""Classify each code response on a 1-5 ordinal strategy scale using an LLM judge.

This module is a **post-processing step** that runs after the main experiment.
It sends each extracted ``.py`` file to Haiku with a task-specific rubric and
parses the returned integer score.  Results are saved to
``analysis/strategy_classifications.json`` and, if ``metrics_table.csv``
exists, a ``strategy_score`` column is appended.

Usage
-----
Standalone::

    python -m src.classify_strategy --extracted-dir runs/<run>/results/extracted \\
                                     --analysis-dir runs/<run>/analysis \\
                                     --metrics-csv  runs/<run>/results/metrics/metrics_table.csv

From the pipeline::

    from src.classify_strategy import classify_all
    classify_all(extracted_dir, analysis_dir, metrics_csv)
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
from pathlib import Path
from typing import Any

from .utils import AnthropicClient, save_json, setup_logging, ensure_dirs

logger = logging.getLogger("experiment.classify_strategy")

# ---------------------------------------------------------------------------
# Task rubrics
# ---------------------------------------------------------------------------

RUBRICS: dict[str, dict[str, Any]] = {
    "task1": {
        "max_score": 5,
        "rubric": (
            "Task: Rate Limiter\n"
            "1 = simple counter/sleep\n"
            "2 = fixed window\n"
            "3 = sliding window log\n"
            "4 = token bucket or sliding window counter\n"
            "5 = multiple strategies offered with tradeoff discussion"
        ),
    },
    "task2": {
        "max_score": 4,
        "rubric": (
            "Task: LRU Cache\n"
            "1 = list-based O(n)\n"
            "2 = OrderedDict wrapper\n"
            "3 = dict + doubly-linked list\n"
            "4 = above + thread safety + generics"
        ),
    },
    "task3": {
        "max_score": 4,
        "rubric": (
            "Task: CLI Task Manager\n"
            "1 = flat script with if/elif\n"
            "2 = functions + JSON persistence\n"
            "3 = class-based with argparse\n"
            "4 = dataclass model + repository pattern + subcommand architecture"
        ),
    },
    "task4": {
        "max_score": 4,
        "rubric": (
            "Task: Event System\n"
            "1 = dict of lists, string matching\n"
            "2 = proper unsubscribe handles\n"
            "3 = type-safe, wildcard support\n"
            "4 = thread-safe, weak references, middleware"
        ),
    },
    "task5": {
        "max_score": 4,
        "rubric": (
            "Task: Refactor\n"
            "1 = cosmetic fixes (variable names, comments)\n"
            "2 = function extraction\n"
            "3 = class-based separation of concerns\n"
            "4 = dependency injection, error hierarchy, tests suggested"
        ),
    },
}

# ---------------------------------------------------------------------------
# Filename parsing (mirrors analyze_code._FILENAME_RE)
# ---------------------------------------------------------------------------

_FILENAME_RE = re.compile(
    r"^(?P<model_short>.+?)_(?P<profile>[A-Z])_(?P<task_id>task\d+)_run(?P<run_id>\d+)$"
)


def _parse_task_from_stem(stem: str) -> str | None:
    """Return the task_id (e.g. ``'task1'``) from a filename stem, or ``None``."""
    m = _FILENAME_RE.match(stem)
    if m:
        return m.group("task_id")
    return None


# ---------------------------------------------------------------------------
# Classification prompt
# ---------------------------------------------------------------------------


def _build_classification_prompt(code: str, rubric: str, max_score: int) -> str:
    """Build the prompt sent to the LLM judge."""
    return (
        f"You are a code quality classifier. Given the following Python code, "
        f"classify the solution strategy on a scale of 1 to {max_score}.\n\n"
        f"{rubric}\n\n"
        f"Respond with ONLY a single integer (1-{max_score}). No explanation.\n\n"
        f"Code:\n```python\n{code}\n```"
    )


# ---------------------------------------------------------------------------
# Single-file classification
# ---------------------------------------------------------------------------


def _classify_one(
    client: AnthropicClient,
    code: str,
    task_id: str,
    *,
    model: str = "haiku",
) -> int:
    """Classify a single code file.  Returns 0 on unrecoverable failure."""
    rubric_info = RUBRICS.get(task_id)
    if rubric_info is None:
        logger.warning("No rubric defined for %s — returning 0", task_id)
        return 0

    # Edge case: empty / placeholder code
    stripped = code.strip()
    if not stripped or stripped == "# NO CODE BLOCKS EXTRACTED":
        return 0

    prompt = _build_classification_prompt(
        code, rubric_info["rubric"], rubric_info["max_score"]
    )
    messages = [{"role": "user", "content": prompt}]
    max_score = rubric_info["max_score"]

    # Attempt up to 2 times (initial + 1 retry) to get a valid integer.
    for attempt in range(2):
        try:
            result = client.send(
                model=model,
                messages=messages,
                skip_validation=True,  # classifier expects single-digit responses
            )
            text = result["text"].strip()
            # Extract the first integer found in the response.
            match = re.search(r"\b(\d+)\b", text)
            if match:
                score = int(match.group(1))
                if 1 <= score <= max_score:
                    return score
                logger.warning(
                    "Score %d out of range [1, %d] — %s",
                    score, max_score, "retrying" if attempt == 0 else "defaulting to 0",
                )
            else:
                logger.warning(
                    "No integer found in response %r — %s",
                    text[:80], "retrying" if attempt == 0 else "defaulting to 0",
                )
        except Exception as exc:
            logger.warning(
                "Classification call failed (attempt %d): %s — %s",
                attempt + 1, exc, "retrying" if attempt == 0 else "defaulting to 0",
            )

    return 0


# ---------------------------------------------------------------------------
# Batch classification
# ---------------------------------------------------------------------------


def classify_all(
    extracted_dir: str | Path,
    analysis_dir: str | Path,
    metrics_csv: str | Path | None = None,
    *,
    model: str = "haiku",
    log: logging.Logger | None = None,
) -> dict[str, Any]:
    """Classify every extracted ``.py`` file and persist results.

    Parameters
    ----------
    extracted_dir:
        Directory containing ``{model}_{profile}_task{N}_run{M}.py`` files.
    analysis_dir:
        Output directory for ``strategy_classifications.json``.
    metrics_csv:
        Path to ``metrics_table.csv``.  If provided **and** the file exists,
        a ``strategy_score`` column is appended (or overwritten).
    model:
        Model name to use for the judge calls (default ``"haiku"``).
    log:
        Optional logger instance.

    Returns
    -------
    dict
        The full classification mapping ``{stem: {"task_id": ..., "score": ...}}``.
    """
    if log is None:
        log = logger

    extracted_path = Path(extracted_dir)
    analysis_path = Path(analysis_dir)
    ensure_dirs(analysis_path)

    py_files = sorted(extracted_path.glob("*.py"))
    if not py_files:
        log.warning("No .py files found in %s", extracted_path)
        return {}

    client = AnthropicClient(inter_call_delay=0.3)

    # Load existing classifications for resume support
    out_path = analysis_path / "strategy_classifications.json"
    if out_path.exists():
        classifications = load_json(str(out_path))
        log.info("Loaded %d existing classifications (resume)", len(classifications))
    else:
        classifications = {}

    log.info("Classifying %d files with %s judge...", len(py_files), model)

    for i, py_file in enumerate(py_files, 1):
        stem = py_file.stem

        # Skip already-classified files
        if stem in classifications and classifications[stem].get("score", 0) > 0:
            log.info("  [%d/%d] %s → cached score %d", i, len(py_files), stem, classifications[stem]["score"])
            continue

        task_id = _parse_task_from_stem(stem)

        if task_id is None:
            log.warning("Skipping %s — does not match expected filename pattern", stem)
            continue

        code = py_file.read_text(encoding="utf-8")
        score = _classify_one(client, code, task_id, model=model)

        classifications[stem] = {
            "task_id": task_id,
            "score": score,
        }
        log.info(
            "  [%d/%d] %s → score %d",
            i, len(py_files), stem, score,
        )

        # Save incrementally so progress survives usage exhaustion
        out_path = analysis_path / "strategy_classifications.json"
        save_json(classifications, out_path)

    log.info("Saved %d classifications to %s", len(classifications), out_path)

    # --- append to metrics CSV if requested ---------------------------------
    if metrics_csv is not None:
        _append_to_csv(Path(metrics_csv), classifications, log)

    # --- usage summary ------------------------------------------------------
    usage = client.get_usage_summary()
    log.info(
        "Judge calls: %d  |  est. cost: $%.4f",
        usage["call_count"], usage["estimated_cost_usd"],
    )

    return classifications


# ---------------------------------------------------------------------------
# CSV augmentation
# ---------------------------------------------------------------------------


def _append_to_csv(
    csv_path: Path,
    classifications: dict[str, dict[str, Any]],
    log: logging.Logger,
) -> None:
    """Add or overwrite a ``strategy_score`` column in *csv_path*."""
    if not csv_path.exists():
        log.warning("metrics CSV not found at %s — skipping column append", csv_path)
        return

    # Read existing rows.
    with open(csv_path, "r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if not rows:
        log.warning("metrics CSV is empty — skipping column append")
        return

    # Ensure the column exists.
    if "strategy_score" not in fieldnames:
        fieldnames.append("strategy_score")

    # Build a lookup key from each row.  The CSV uses
    # model_short / profile / task_id / run_id which maps back to the stem.
    for row in rows:
        stem = (
            f"{row.get('model_short', '')}_{row.get('profile', '')}_"
            f"{row.get('task_id', '')}_run{row.get('run_id', '')}"
        )
        entry = classifications.get(stem)
        row["strategy_score"] = entry["score"] if entry else ""

    # Re-write the CSV.
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    log.info("Appended strategy_score column to %s", csv_path)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Command-line interface for strategy classification."""
    parser = argparse.ArgumentParser(
        description="Classify extracted code on a strategy-complexity scale using an LLM judge.",
    )
    parser.add_argument(
        "--extracted-dir",
        default="results/extracted",
        help="Directory with extracted .py files (default: results/extracted)",
    )
    parser.add_argument(
        "--analysis-dir",
        default="analysis",
        help="Output directory for classification JSON (default: analysis)",
    )
    parser.add_argument(
        "--metrics-csv",
        default=None,
        help="Path to metrics_table.csv to append strategy_score column (optional)",
    )
    parser.add_argument(
        "--model",
        default="haiku",
        help="Model to use as judge (default: haiku)",
    )
    args = parser.parse_args()

    log = setup_logging(args.analysis_dir, "classify_strategy")

    classify_all(
        extracted_dir=args.extracted_dir,
        analysis_dir=args.analysis_dir,
        metrics_csv=args.metrics_csv,
        model=args.model,
        log=log,
    )


if __name__ == "__main__":
    main()
