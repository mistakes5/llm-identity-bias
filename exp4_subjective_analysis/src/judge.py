"""LLM-as-judge scoring for experiment responses.

Batches all 4 rubrics into a single prompt per evaluation to minimize API
usage.  Runs each response through the judge *n_runs* times and takes the
median score per metric for robustness.  Saves results incrementally so
interrupted runs can resume without re-scoring completed responses.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import statistics
from pathlib import Path

from .utils import AnthropicClient, save_json, load_json, setup_logging, ensure_dirs

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RUBRIC_KEYS: list[str] = [
    "analytical_depth",
    "specificity",
    "challenge_level",
    "register_level",
]

ZERO_SCORES: dict[str, int] = {k: 0 for k in RUBRIC_KEYS}


# ---------------------------------------------------------------------------
# Rubric loading
# ---------------------------------------------------------------------------


def load_rubrics(rubrics_dir: str | Path) -> dict[str, str]:
    """Load all 4 rubric ``.txt`` files from *rubrics_dir*.

    Expected filenames: ``analytical_depth.txt``, ``specificity.txt``,
    ``challenge_level.txt``, ``register_level.txt``.

    Returns
    -------
    dict[str, str]
        Mapping from rubric key to its full text content.
    """
    rubrics_dir = Path(rubrics_dir)
    rubrics: dict[str, str] = {}
    for key in RUBRIC_KEYS:
        path = rubrics_dir / f"{key}.txt"
        if not path.exists():
            raise FileNotFoundError(f"Missing rubric file: {path}")
        rubrics[key] = path.read_text(encoding="utf-8").strip()
    return rubrics


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def build_judge_prompt(rubrics: dict[str, str], response_text: str) -> str:
    """Build a single evaluation prompt containing all 4 rubrics.

    The prompt instructs the judge to return exactly 4 labelled scores so
    we can parse them deterministically.
    """
    return (
        "You are evaluating the quality of an analytical response. "
        "Score it on 4 dimensions.\n"
        "For each dimension, respond with ONLY a number 1-5.\n"
        "\n"
        "Format your response as exactly 4 lines, one number per line:\n"
        "analytical_depth: [1-5]\n"
        "specificity: [1-5]\n"
        "challenge_level: [1-5]\n"
        "register_level: [1-5]\n"
        "\n"
        "--- RUBRICS ---\n"
        "\n"
        "ANALYTICAL DEPTH:\n"
        f"{rubrics['analytical_depth']}\n"
        "\n"
        "SPECIFICITY:\n"
        f"{rubrics['specificity']}\n"
        "\n"
        "CHALLENGE LEVEL:\n"
        f"{rubrics['challenge_level']}\n"
        "\n"
        "REGISTER LEVEL:\n"
        f"{rubrics['register_level']}\n"
        "\n"
        "--- RESPONSE TO EVALUATE ---\n"
        "\n"
        f"{response_text}"
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def parse_judge_response(text: str) -> dict[str, int] | None:
    """Parse the 4 scores from a judge response.

    Tries two strategies:

    1. Look for labelled lines like ``analytical_depth: 4``.
    2. Fall back to extracting the first 4 standalone integers (1-5) from
       separate lines, mapping them to rubric keys in order.

    Returns
    -------
    dict[str, int] | None
        Mapping of rubric key to integer score, or ``None`` if the
        response cannot be parsed into exactly 4 valid scores.
    """
    scores: dict[str, int] = {}

    # Strategy 1: labelled lines.
    for key in RUBRIC_KEYS:
        pattern = rf"{key}\s*:\s*([1-5])"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            scores[key] = int(match.group(1))

    if len(scores) == len(RUBRIC_KEYS):
        return scores

    # Strategy 2: bare numbers on separate lines.
    numbers: list[int] = []
    for line in text.strip().splitlines():
        line = line.strip()
        # Accept a line that is just a digit 1-5, possibly with a label.
        m = re.search(r"\b([1-5])\b", line)
        if m:
            numbers.append(int(m.group(1)))

    if len(numbers) >= len(RUBRIC_KEYS):
        return dict(zip(RUBRIC_KEYS, numbers[: len(RUBRIC_KEYS)]))

    return None


# ---------------------------------------------------------------------------
# Single-response judging
# ---------------------------------------------------------------------------


def judge_single(
    client: AnthropicClient,
    response_text: str,
    rubrics: dict[str, str],
    model: str = "haiku",
    n_runs: int = 3,
    log: logging.Logger | None = None,
) -> dict:
    """Run the judge *n_runs* times and return median scores.

    Parameters
    ----------
    client:
        The API client wrapper.
    response_text:
        The experiment response to evaluate.
    rubrics:
        Loaded rubric texts keyed by metric name.
    model:
        Model to use for judging (``"haiku"`` for dry runs, ``"opus"`` for
        full runs).
    n_runs:
        Number of independent judge runs.  Median is taken per metric.
    log:
        Optional logger for audit trail.

    Returns
    -------
    dict
        ``{"analytical_depth": <median>, ..., "raw_scores": [[run1], ...]}``.
    """
    log = log or logging.getLogger("judge")
    prompt = build_judge_prompt(rubrics, response_text)

    raw_scores: list[dict[str, int]] = []

    for run_idx in range(n_runs):
        scores: dict[str, int] | None = None
        retries = 2  # 1 initial attempt + 1 retry on parse failure

        for attempt in range(retries):
            try:
                result = client.send(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    skip_validation=True,
                )
                scores = parse_judge_response(result["text"])

                if scores is not None:
                    log.debug(
                        "Judge run %d/%d — scores: %s",
                        run_idx + 1, n_runs, scores,
                    )
                    break

                log.warning(
                    "Judge run %d/%d parse failed (attempt %d/%d): %s",
                    run_idx + 1, n_runs, attempt + 1, retries,
                    result["text"][:200],
                )

            except Exception as exc:
                log.warning(
                    "Judge run %d/%d API error (attempt %d/%d): %s",
                    run_idx + 1, n_runs, attempt + 1, retries, exc,
                )

        if scores is None:
            log.warning(
                "Judge run %d/%d defaulting to zeros after exhausting retries.",
                run_idx + 1, n_runs,
            )
            scores = dict(ZERO_SCORES)

        raw_scores.append(scores)

    # Compute median per metric.
    medians: dict[str, float] = {}
    for key in RUBRIC_KEYS:
        values = [run[key] for run in raw_scores]
        medians[key] = statistics.median(values)

    # Convert raw scores to list-of-lists for compact storage.
    raw_as_lists = [[run[k] for k in RUBRIC_KEYS] for run in raw_scores]

    return {**medians, "raw_scores": raw_as_lists}


# ---------------------------------------------------------------------------
# Batch judging with resume support
# ---------------------------------------------------------------------------


def judge_all(
    raw_dir: str | Path,
    rubrics_dir: str | Path,
    judge_dir: str | Path,
    model: str = "haiku",
    n_runs: int = 3,
    log: logging.Logger | None = None,
    max_calls: int | None = None,
) -> dict:
    """Score every raw response JSON and save results incrementally.

    Parameters
    ----------
    raw_dir:
        Directory containing ``*_response.json`` files (each must have a
        ``"response"`` key with the text to evaluate).
    rubrics_dir:
        Directory containing the 4 rubric ``.txt`` files.
    judge_dir:
        Output directory for ``*_judge.json`` result files.
    model:
        Judge model name.
    n_runs:
        Number of judge runs per response.
    log:
        Optional logger.

    Returns
    -------
    dict
        Summary with counts of scored, skipped, and failed responses.
    """
    raw_dir = Path(raw_dir)
    judge_dir = Path(judge_dir)
    log = log or logging.getLogger("judge")

    ensure_dirs(judge_dir)
    rubrics = load_rubrics(rubrics_dir)
    client = AnthropicClient()

    response_files = sorted(raw_dir.glob("*.json"))
    if not response_files:
        log.warning("No JSON files found in %s", raw_dir)
        return {"scored": 0, "skipped": 0, "failed": 0, "total": 0}

    scored = 0
    skipped = 0
    failed = 0
    calls_made = 0
    budget_exhausted = False

    for resp_path in response_files:
        stem = resp_path.stem
        judge_path = judge_dir / f"{stem}_judge.json"

        # Resume support: skip already-scored responses.
        if judge_path.exists():
            log.info("Skipping already scored: %s", stem)
            skipped += 1
            continue

        # Budget check: scoring one response costs n_runs API calls.
        if max_calls is not None and calls_made + n_runs > max_calls:
            budget_exhausted = True
            log.info("Judge batch limit reached (%d/%s calls). Pausing.", calls_made, max_calls)
            break

        try:
            raw_data = load_json(resp_path)
            response_text = raw_data.get("response_text", "")

            if not response_text:
                log.warning("Empty response in %s — skipping.", stem)
                failed += 1
                continue

            log.info("Judging: %s (model=%s, n_runs=%d)", stem, model, n_runs)
            scores = judge_single(
                client, response_text, rubrics,
                model=model, n_runs=n_runs, log=log,
            )

            # Attach metadata for traceability.
            scores["source_file"] = str(resp_path.name)
            scores["judge_model"] = model
            scores["n_runs"] = n_runs

            save_json(scores, judge_path)
            log.info(
                "Saved judge scores for %s: %s",
                stem,
                {k: scores[k] for k in RUBRIC_KEYS},
            )
            scored += 1
            calls_made += n_runs

        except Exception as exc:
            log.error("Failed to judge %s: %s", stem, exc, exc_info=True)
            failed += 1

    summary = {
        "scored": scored,
        "skipped": skipped,
        "failed": failed,
        "total": len(response_files),
        "calls_made": calls_made,
        "budget_exhausted": budget_exhausted,
        "usage": client.get_usage_summary(),
    }
    log.info("Judge %s — %s", "paused" if budget_exhausted else "complete", summary)
    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Command-line interface for running LLM-as-judge scoring."""
    parser = argparse.ArgumentParser(
        description="Run LLM-as-judge scoring on experiment responses.",
    )
    parser.add_argument(
        "--raw-dir",
        type=str,
        required=True,
        help="Directory containing raw response JSON files.",
    )
    parser.add_argument(
        "--rubrics-dir",
        type=str,
        required=True,
        help="Directory containing the 4 rubric .txt files.",
    )
    parser.add_argument(
        "--judge-dir",
        type=str,
        required=True,
        help="Output directory for judge score JSON files.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="haiku",
        help="Judge model name (default: haiku).",
    )
    parser.add_argument(
        "--n-runs",
        type=int,
        default=3,
        help="Number of judge runs per response (default: 3).",
    )

    args = parser.parse_args()

    log = setup_logging(args.judge_dir, name="judge")
    summary = judge_all(
        raw_dir=args.raw_dir,
        rubrics_dir=args.rubrics_dir,
        judge_dir=args.judge_dir,
        model=args.model,
        n_runs=args.n_runs,
        log=log,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
