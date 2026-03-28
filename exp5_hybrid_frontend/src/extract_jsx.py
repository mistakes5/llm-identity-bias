"""Extract React/JSX code from markdown LLM responses.

Handles fenced code blocks with various language tags, multi-block
responses (common for React components with separate style/type files),
and validates that extracted content contains React indicators.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from .utils import save_json, load_json, ensure_dirs

# Language tags that indicate React/JS/TS code blocks.
_CODE_TAGS = r"(?:jsx|tsx|javascript|typescript|react|js|ts)"

# Patterns that indicate React content in an untagged block.
_REACT_INDICATORS = [
    r"\bimport\s+React\b",
    r"\bimport\s+\{.*\}\s+from\s+['\"]react['\"]",
    r"\bclassName\s*=",
    r"\buseState\b",
    r"\buseEffect\b",
    r"<\w+[\s/>]",  # JSX element
    r"\bexport\s+(?:default\s+)?function\b",
    r"\bconst\s+\w+\s*[:=]\s*(?:React\.FC|FC|\()",
]


def _extract_fenced_blocks(text: str) -> list[dict[str, Any]]:
    """Extract all fenced code blocks from markdown text.

    Returns a list of dicts with keys: code, tag, tagged (bool).
    """
    blocks: list[dict[str, Any]] = []

    # Match tagged code blocks.
    for m in re.finditer(
        r"```(" + _CODE_TAGS + r")\s*\n(.*?)```",
        text, re.DOTALL | re.IGNORECASE,
    ):
        blocks.append({"code": m.group(2).strip(), "tag": m.group(1).lower(), "tagged": True})

    # Match untagged code blocks that contain React indicators.
    for m in re.finditer(r"```\s*\n(.*?)```", text, re.DOTALL):
        code = m.group(1).strip()
        if any(re.search(p, code) for p in _REACT_INDICATORS):
            # Avoid duplicates if this block was already matched as tagged.
            if not any(b["code"] == code for b in blocks):
                blocks.append({"code": code, "tag": "untagged", "tagged": False})

    return blocks


def _has_react_content(code: str) -> bool:
    """Check if code contains at least one React indicator."""
    indicators_found = sum(1 for p in _REACT_INDICATORS if re.search(p, code))
    return indicators_found >= 2  # Require at least 2 indicators to reduce false positives.


def extract_from_response(response_text: str) -> dict[str, Any]:
    """Extract React code from a single LLM response.

    Returns a dict with:
        extracted_code: str (concatenated code blocks)
        blocks_found: int
        total_chars: int
        is_valid: bool (has React indicators)
        tags: list[str] (language tags found)
    """
    blocks = _extract_fenced_blocks(response_text)

    if not blocks:
        return {
            "extracted_code": "",
            "blocks_found": 0,
            "total_chars": 0,
            "is_valid": False,
            "tags": [],
        }

    combined = "\n\n".join(b["code"] for b in blocks)
    tags = [b["tag"] for b in blocks]
    is_valid = _has_react_content(combined)

    return {
        "extracted_code": combined,
        "blocks_found": len(blocks),
        "total_chars": len(combined),
        "is_valid": is_valid,
        "tags": tags,
    }


def extract_all(
    raw_dir: str | Path,
    extracted_dir: str | Path,
    log: logging.Logger | None = None,
) -> dict[str, Any]:
    """Extract React code from all raw response JSONs.

    Reads each JSON from raw_dir, extracts code, and writes results
    to extracted_dir. Tracks success/failure rates per profile.
    """
    raw_dir = Path(raw_dir)
    extracted_dir = Path(extracted_dir)
    log = log or logging.getLogger("extract")
    ensure_dirs(extracted_dir)

    response_files = sorted(raw_dir.glob("*.json"))
    if not response_files:
        log.warning("No JSON files found in %s", raw_dir)
        return {"extracted": 0, "failed": 0, "total": 0}

    extracted_count = 0
    failed_count = 0
    skipped_count = 0
    per_profile: dict[str, dict[str, int]] = {}

    for resp_path in response_files:
        stem = resp_path.stem
        out_path = extracted_dir / f"{stem}_extracted.json"

        # Resume support.
        if out_path.exists():
            skipped_count += 1
            continue

        raw_data = load_json(resp_path)
        response_text = raw_data.get("response_text", "")
        profile = raw_data.get("profile", "?")

        if profile not in per_profile:
            per_profile[profile] = {"extracted": 0, "failed": 0}

        if not response_text:
            log.warning("Empty response in %s -- skipping extraction.", stem)
            failed_count += 1
            per_profile[profile]["failed"] += 1
            continue

        result = extract_from_response(response_text)

        # Attach metadata.
        result["source_file"] = resp_path.name
        result["model"] = raw_data.get("model_short", "")
        result["profile"] = profile
        result["task_id"] = raw_data.get("task_id", "")
        result["run_id"] = raw_data.get("run_id", 0)

        save_json(result, out_path)

        if result["is_valid"]:
            extracted_count += 1
            per_profile[profile]["extracted"] += 1
            log.info(
                "Extracted %s: %d blocks, %d chars, tags=%s",
                stem, result["blocks_found"], result["total_chars"], result["tags"],
            )
        else:
            failed_count += 1
            per_profile[profile]["failed"] += 1
            log.warning(
                "Extraction invalid for %s: %d blocks found but no React content.",
                stem, result["blocks_found"],
            )

    summary = {
        "extracted": extracted_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "total": len(response_files),
        "per_profile": per_profile,
    }
    log.info("Extraction complete: %s", summary)
    return summary


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Extract React/JSX from experiment responses")
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--extracted-dir", required=True)
    args = parser.parse_args()

    from .utils import setup_logging
    log = setup_logging(args.extracted_dir, "extract")
    extract_all(args.raw_dir, args.extracted_dir, log=log)


if __name__ == "__main__":
    main()
