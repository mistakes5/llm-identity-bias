"""LLM-as-judge scoring for experiment 5: design quality of React components.

Batches all 4 rubrics into a single prompt per evaluation. Runs each response
through the judge n_runs times and takes the median score per metric. Saves
results incrementally for resume support.

Judge evaluates EXTRACTED CODE, not the full response. This ensures the judge
sees only the artifact, blind to any conversational framing.
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
    "visual_sophistication",
    "component_architecture",
    "design_intentionality",
    "taste_signal",
]

ZERO_SCORES: dict[str, int] = {k: 0 for k in RUBRIC_KEYS}


# ---------------------------------------------------------------------------
# Rubric loading
# ---------------------------------------------------------------------------


def load_rubrics(rubrics_dir: str | Path) -> dict[str, str]:
    """Load all 4 rubric .txt files from rubrics_dir."""
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


def build_judge_prompt(rubrics: dict[str, str], code: str) -> str:
    """Build a single evaluation prompt containing all 4 rubrics.

    The judge scores the extracted React component code on design quality.
    """
    return (
        "You are evaluating the design and architecture quality of a React component. "
        "Score it on 4 dimensions.\n"
        "For each dimension, respond with ONLY a number 1-5.\n"
        "\n"
        "Format your response as exactly 4 lines, one number per line:\n"
        "visual_sophistication: [1-5]\n"
        "component_architecture: [1-5]\n"
        "design_intentionality: [1-5]\n"
        "taste_signal: [1-5]\n"
        "\n"
        "--- RUBRICS ---\n"
        "\n"
        "VISUAL SOPHISTICATION:\n"
        f"{rubrics['visual_sophistication']}\n"
        "\n"
        "COMPONENT ARCHITECTURE:\n"
        f"{rubrics['component_architecture']}\n"
        "\n"
        "DESIGN INTENTIONALITY:\n"
        f"{rubrics['design_intentionality']}\n"
        "\n"
        "TASTE SIGNAL:\n"
        f"{rubrics['taste_signal']}\n"
        "\n"
        "--- REACT COMPONENT CODE TO EVALUATE ---\n"
        "\n"
        f"{code}"
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def parse_judge_response(text: str) -> dict[str, int] | None:
    """Parse the 4 scores from a judge response.

    Tries labelled lines first, falls back to bare numbers.
    """
    scores: dict[str, int] = {}

    for key in RUBRIC_KEYS:
        pattern = rf"{key}\s*:\s*([1-5])"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            scores[key] = int(match.group(1))

    if len(scores) == len(RUBRIC_KEYS):
        return scores

    # Fallback: bare numbers on separate lines.
    numbers: list[int] = []
    for line in text.strip().splitlines():
        line = line.strip()
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
    code: str,
    rubrics: dict[str, str],
    model: str = "haiku",
    n_runs: int = 3,
    log: logging.Logger | None = None,
) -> dict:
    """Run the judge n_runs times and return median scores."""
    log = log or logging.getLogger("judge")
    prompt = build_judge_prompt(rubrics, code)

    raw_scores: list[dict[str, int]] = []

    for run_idx in range(n_runs):
        scores: dict[str, int] | None = None
        retries = 2

        for attempt in range(retries):
            try:
                result = client.send(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    skip_validation=True,
                )
                scores = parse_judge_response(result["text"])

                if scores is not None:
                    log.debug("Judge run %d/%d -- scores: %s", run_idx + 1, n_runs, scores)
                    break

                log.warning(
                    "Judge run %d/%d parse failed (attempt %d/%d): %s",
                    run_idx + 1, n_runs, attempt + 1, retries, result["text"][:200],
                )

            except Exception as exc:
                log.warning(
                    "Judge run %d/%d API error (attempt %d/%d): %s",
                    run_idx + 1, n_runs, attempt + 1, retries, exc,
                )

        if scores is None:
            log.warning("Judge run %d/%d defaulting to zeros.", run_idx + 1, n_runs)
            scores = dict(ZERO_SCORES)

        raw_scores.append(scores)

    medians: dict[str, float] = {}
    for key in RUBRIC_KEYS:
        values = [run[key] for run in raw_scores]
        medians[key] = statistics.median(values)

    raw_as_lists = [[run[k] for k in RUBRIC_KEYS] for run in raw_scores]

    return {**medians, "raw_scores": raw_as_lists}


# ---------------------------------------------------------------------------
# Batch judging with resume support
# ---------------------------------------------------------------------------


def judge_all(
    raw_dir: str | Path,
    extracted_dir: str | Path,
    rubrics_dir: str | Path,
    judge_dir: str | Path,
    model: str = "haiku",
    n_runs: int = 3,
    log: logging.Logger | None = None,
    max_calls: int | None = None,
) -> dict:
    """Score every extracted response and save results incrementally.

    Reads extracted code (not raw responses) to keep the judge blind
    to conversational framing.
    """
    extracted_dir = Path(extracted_dir)
    judge_dir = Path(judge_dir)
    log = log or logging.getLogger("judge")

    ensure_dirs(judge_dir)
    rubrics = load_rubrics(rubrics_dir)
    client = AnthropicClient()

    extracted_files = sorted(extracted_dir.glob("*_extracted.json"))
    if not extracted_files:
        log.warning("No extracted files found in %s", extracted_dir)
        return {"scored": 0, "skipped": 0, "failed": 0, "total": 0,
                "calls_made": 0, "budget_exhausted": False}

    scored = 0
    skipped = 0
    failed = 0
    calls_made = 0
    budget_exhausted = False

    for ext_path in extracted_files:
        # Judge file uses the original raw file stem.
        ext_data = load_json(ext_path)
        raw_stem = ext_data.get("source_file", "").replace(".json", "")
        if not raw_stem:
            raw_stem = ext_path.stem.replace("_extracted", "")
        judge_path = judge_dir / f"{raw_stem}_judge.json"

        # Resume support.
        if judge_path.exists():
            log.info("Skipping already scored: %s", raw_stem)
            skipped += 1
            continue

        # Skip invalid extractions.
        if not ext_data.get("is_valid", False):
            log.info("Skipping invalid extraction: %s", raw_stem)
            failed += 1
            continue

        code = ext_data.get("extracted_code", "")
        if not code:
            log.warning("Empty extracted code in %s -- skipping.", raw_stem)
            failed += 1
            continue

        # Budget check.
        if max_calls is not None and calls_made + n_runs > max_calls:
            budget_exhausted = True
            log.info("Judge batch limit reached (%d/%s calls). Pausing.", calls_made, max_calls)
            break

        log.info("Judging: %s (model=%s, n_runs=%d)", raw_stem, model, n_runs)
        scores = judge_single(client, code, rubrics, model=model, n_runs=n_runs, log=log)

        scores["source_file"] = ext_data.get("source_file", "")
        scores["judge_model"] = model
        scores["n_runs"] = n_runs

        save_json(scores, judge_path)
        log.info(
            "Saved judge scores for %s: %s",
            raw_stem, {k: scores[k] for k in RUBRIC_KEYS},
        )
        scored += 1
        calls_made += n_runs

    summary = {
        "scored": scored,
        "skipped": skipped,
        "failed": failed,
        "total": len(extracted_files),
        "calls_made": calls_made,
        "budget_exhausted": budget_exhausted,
        "usage": client.get_usage_summary(),
    }
    log.info("Judge %s -- %s", "paused" if budget_exhausted else "complete", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM-as-judge design scoring for exp5")
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--extracted-dir", required=True)
    parser.add_argument("--rubrics-dir", required=True)
    parser.add_argument("--judge-dir", required=True)
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--n-runs", type=int, default=3)
    args = parser.parse_args()

    log = setup_logging(args.judge_dir, name="judge")
    judge_all(
        raw_dir=args.raw_dir,
        extracted_dir=args.extracted_dir,
        rubrics_dir=args.rubrics_dir,
        judge_dir=args.judge_dir,
        model=args.model,
        n_runs=args.n_runs,
        log=log,
    )


if __name__ == "__main__":
    main()
