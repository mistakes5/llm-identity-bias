"""Experiment 3 runner: memory-level profile bias in code generation.

Profiles are injected as system prompt content (memory position), not as
chat history turns. Execution order is randomized within each model.
"""

from __future__ import annotations

import argparse
import itertools
import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .utils import AnthropicClient, save_json, load_json, setup_logging, ensure_dirs

MODELS: list[str] = ["claude-sonnet-4", "claude-haiku-4"]
MODEL_SHORT: dict[str, str] = {"claude-sonnet-4": "sonnet", "claude-haiku-4": "haiku"}

PROFILES: list[str] = ["A", "B", "C", "D", "E"]
PROFILE_TYPES: dict[str, str] = {
    "A": "high_sophistication_nontechnical",
    "B": "control",
    "C": "low_sophistication_nontechnical",
    "D": "high_sophistication_technical",
    "E": "low_sophistication_technical",
}

TEMPERATURE: float = 0.3


def load_profile(profiles_dir: str | Path, profile: str) -> str:
    """Load profile text from file. Returns empty string for Profile B (control).

    Profile B gets an empty system prompt so the CLI still receives
    ``--system-prompt`` and replaces its default agent instructions.
    This ensures all conditions have the same CLI framing.
    """
    if profile == "B":
        return ""
    path = Path(profiles_dir) / f"profile_{profile.lower()}.txt"
    return path.read_text().strip()


def load_tasks(prompts_dir: str | Path) -> list[dict[str, Any]]:
    """Load all task JSON files, sorted by task_id."""
    tasks = []
    for f in sorted(Path(prompts_dir).glob("task*.json")):
        tasks.append(load_json(str(f)))
    return tasks


def run_single(
    client: AnthropicClient,
    model: str,
    profile: str,
    profile_text: str | None,
    task: dict[str, Any],
    run_id: int,
    temperature: float = TEMPERATURE,
) -> dict[str, Any]:
    """Run a single coding completion with profile as system prompt."""
    start = time.time()
    response = client.send_for_profile(
        model=model,
        profile_text=profile_text,
        coding_prompt=task["prompt"],
    )
    elapsed_ms = (time.time() - start) * 1000

    return {
        "model": model,
        "model_short": MODEL_SHORT[model],
        "profile": profile,
        "profile_type": PROFILE_TYPES[profile],
        "task_id": task["task_id"],
        "task_name": task["name"],
        "run_id": run_id,
        "temperature": temperature,
        "system_prompt": profile_text or "",
        "user_prompt": task["prompt"],
        "response_text": response["text"],
        "stop_reason": response["stop_reason"],
        "input_tokens": response["input_tokens"],
        "output_tokens": response["output_tokens"],
        "system_chars": response.get("system_chars", 0),
        "prompt_chars": response.get("prompt_chars", 0),
        "elapsed_ms": round(elapsed_ms, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def run_experiment(
    profiles_dir: str,
    prompts_dir: str,
    output_dir: str,
    models: list[str] | None = None,
    n_runs: int = 5,
    temperature: float = TEMPERATURE,
    resume: bool = True,
    seed: int = 42,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """Run the full experiment with randomized execution order."""
    if logger is None:
        logger = logging.getLogger("experiment")
    if models is None:
        models = MODELS

    client = AnthropicClient(default_temperature=temperature, default_max_tokens=4096)
    tasks = load_tasks(prompts_dir)
    raw_dir = Path(output_dir) / "raw"
    ensure_dirs(str(raw_dir))

    # Load all profile texts
    profile_texts: dict[str, str | None] = {}
    for p in PROFILES:
        profile_texts[p] = load_profile(profiles_dir, p)
        if profile_texts[p]:
            logger.info(f"Profile {p} ({PROFILE_TYPES[p]}): {len(profile_texts[p])} chars")
        else:
            logger.info(f"Profile {p} ({PROFILE_TYPES[p]}): no system prompt (control)")

    for model in models:
        short = MODEL_SHORT[model]

        # Build all cells and shuffle for this model
        cells = list(itertools.product(PROFILES, tasks, range(1, n_runs + 1)))
        rng = random.Random(seed)
        rng.shuffle(cells)

        total = len(cells)
        completed = 0
        skipped = 0

        logger.info(f"Model {short}: {total} calls (randomized, seed={seed})")

        for profile, task, run in cells:
            filename = f"{short}_{profile}_{task['task_id']}_run{run}.json"
            out_path = raw_dir / filename

            if resume and out_path.exists():
                skipped += 1
                continue

            completed += 1
            logger.info(
                f"[{completed + skipped}/{total}] {short} {profile}({PROFILE_TYPES[profile]}) "
                f"{task['task_id']} run{run}"
            )

            result = run_single(
                client, model, profile, profile_texts[profile],
                task, run, temperature,
            )
            save_json(result, str(out_path))

            logger.info(
                f"  -> sys={result['system_chars']} chars, prompt={result['prompt_chars']} chars, "
                f"out={result['output_tokens']} est tokens, {result['elapsed_ms']}ms"
            )

        logger.info(f"Model {short} done: {completed} calls, {skipped} skipped")

    usage = client.get_usage_summary()
    logger.info(f"Experiment complete. {usage}")
    return usage


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Experiment 3: memory-level profile bias")
    parser.add_argument("--profiles-dir", default="profiles")
    parser.add_argument("--prompts-dir", default="prompts")
    parser.add_argument("--output-dir", default="results")
    parser.add_argument("--n-runs", type=int, default=5)
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    logger = setup_logging(args.output_dir, "run_experiment")
    run_experiment(
        args.profiles_dir, args.prompts_dir, args.output_dir,
        n_runs=args.n_runs, temperature=args.temperature,
        seed=args.seed, resume=not args.no_resume, logger=logger,
    )


if __name__ == "__main__":
    main()
