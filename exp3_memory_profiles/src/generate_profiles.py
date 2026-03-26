"""Generate and freeze profile conversation transcripts for each model.

Sends pre-written user turns through each target model to produce frozen
transcripts that serve as the profile context in later coding-prompt trials.
Profiles A and C have scripted user turns; Profile B (control) has no
transcript and is omitted here.
"""

from __future__ import annotations

import argparse
import logging
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

PROFILES: list[str] = ["A", "C"]  # B has no transcript


# ---------------------------------------------------------------------------
# Transcript generation
# ---------------------------------------------------------------------------


def generate_transcript(
    client: AnthropicClient,
    model: str,
    user_turns: list[dict[str, str]],
    logger: logging.Logger,
) -> list[dict[str, str]]:
    """Send *user_turns* sequentially through the model, building conversation context.

    Each turn receives the full history accumulated so far so the model can
    condition on prior exchanges.  Temperature is fixed at 0.5 for natural
    variation.  No system prompt is provided.

    Parameters
    ----------
    client:
        Configured :class:`AnthropicClient` instance.
    model:
        Anthropic model identifier (e.g. ``"claude-sonnet-4-5-20250514"``).
    user_turns:
        List of dicts, each with a ``"content"`` key containing the user
        message text for that turn.
    logger:
        Logger for progress updates.

    Returns
    -------
    list[dict[str, str]]
        Alternating ``{"role": "user", "content": ...}`` and
        ``{"role": "assistant", "content": ...}`` messages.
    """
    transcript: list[dict[str, str]] = []

    for i, turn in enumerate(user_turns):
        logger.info(f"  Turn {i + 1}/{len(user_turns)}")
        transcript.append({"role": "user", "content": turn["content"]})

        response: dict[str, Any] = client.send(
            model=model,
            messages=transcript,
            temperature=0.5,
            max_tokens=1024,
        )

        transcript.append({"role": "assistant", "content": response["text"]})
        logger.info(
            f"    tokens: {response['input_tokens']} in, "
            f"{response['output_tokens']} out"
        )

    return transcript


# ---------------------------------------------------------------------------
# Batch generation
# ---------------------------------------------------------------------------


def generate_all(
    scripts_dir: str | Path,
    output_dir: str | Path,
    models: list[str] | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, dict[str, str]]:
    """Generate transcripts for profiles A and C across all target models.

    For each ``(model, profile)`` pair the function:

    1. Checks whether the output file already exists and skips if so.
    2. Loads the scripted user turns from *scripts_dir*.
    3. Sends them through the model via :func:`generate_transcript`.
    4. Saves the full transcript as JSON in *output_dir*.

    Parameters
    ----------
    scripts_dir:
        Directory containing ``profile_a_turns.json`` and
        ``profile_c_turns.json``.
    output_dir:
        Root output directory.  Transcripts are saved under
        ``<output_dir>/<model_short>/profile_<x>.json``.
    models:
        Model identifiers to use.  Defaults to :data:`MODELS`.
    logger:
        Logger instance.  A no-op fallback is used if ``None``.

    Returns
    -------
    dict[str, dict[str, str]]
        Nested mapping ``{model_short: {profile: filepath}}`` of all
        generated (or already-existing) transcript paths.
    """
    if models is None:
        models = MODELS

    if logger is None:
        logger = logging.getLogger(__name__)

    client = AnthropicClient(default_temperature=0.5, default_max_tokens=1024)
    results: dict[str, dict[str, str]] = {}

    for model in models:
        short: str = MODEL_SHORT[model]
        model_dir = Path(output_dir) / short
        ensure_dirs(str(model_dir))
        results[short] = {}

        for profile in PROFILES:
            out_path = model_dir / f"profile_{profile.lower()}.json"

            if out_path.exists():
                logger.info(f"Skipping existing transcript: {out_path}")
                results[short][profile] = str(out_path)
                continue

            script_path = Path(scripts_dir) / f"profile_{profile.lower()}_turns.json"
            script: dict[str, Any] = load_json(str(script_path))
            user_turns: list[dict[str, str]] = script["turns"]

            logger.info(
                f"Generating {short}/profile_{profile.lower()} "
                f"({len(user_turns)} turns)"
            )
            transcript = generate_transcript(client, model, user_turns, logger)

            save_json(
                {
                    "model": model,
                    "model_short": short,
                    "profile": profile,
                    "turn_count": len(user_turns),
                    "transcript": transcript,
                },
                str(out_path),
            )

            results[short][profile] = str(out_path)
            logger.info(f"  Saved: {out_path}")

    usage: dict[str, Any] = client.get_usage_summary()
    logger.info(f"Profile generation complete. {usage}")
    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse arguments and run transcript generation."""
    parser = argparse.ArgumentParser(
        description="Generate profile conversation transcripts"
    )
    parser.add_argument(
        "--scripts-dir",
        default="scripts",
        help="Directory with profile turn scripts (default: scripts)",
    )
    parser.add_argument(
        "--output-dir",
        default="transcripts",
        help="Output directory for transcripts (default: transcripts)",
    )
    args = parser.parse_args()

    logger = setup_logging(args.output_dir, "generate_profiles")
    generate_all(args.scripts_dir, args.output_dir, logger=logger)


if __name__ == "__main__":
    main()
