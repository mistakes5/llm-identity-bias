"""React-specific code metrics for Experiment 5.

Computes structural and stylistic metrics from extracted JSX/TSX code
using regex-based heuristics. These are approximate but consistent
across conditions, making comparative analysis valid.
"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from typing import Any

from .utils import load_json, save_json, ensure_dirs


# ---------------------------------------------------------------------------
# Metric extractors
# ---------------------------------------------------------------------------


def _count_components(code: str) -> int:
    """Count React component definitions (function and arrow styles)."""
    # function MyComponent(
    func_components = re.findall(
        r"(?:export\s+(?:default\s+)?)?function\s+[A-Z]\w*\s*\(", code
    )
    # const MyComponent = ( or const MyComponent: React.FC
    arrow_components = re.findall(
        r"const\s+[A-Z]\w*\s*(?::\s*\w+(?:\.\w+)*\s*)?=\s*(?:\([^)]*\)\s*=>|function)",
        code,
    )
    return len(func_components) + len(arrow_components)


def _count_hooks(code: str) -> int:
    """Count React hook calls (useState, useEffect, custom useX)."""
    return len(re.findall(r"\buse[A-Z]\w*\s*\(", code))


def _count_prop_interfaces(code: str) -> int:
    """Count TypeScript interface/type definitions for props."""
    interfaces = re.findall(r"\b(?:interface|type)\s+\w*(?:Props|Config|Options)\b", code)
    return len(interfaces)


def _count_event_handlers(code: str) -> int:
    """Count onX event handler attributes in JSX."""
    return len(re.findall(r"\bon[A-Z]\w+\s*=\s*\{", code))


def _count_imports(code: str) -> int:
    """Count import statements."""
    return len(re.findall(r"^import\s", code, re.MULTILINE))


def _count_tailwind_classes(code: str) -> int:
    """Count approximate number of Tailwind utility classes in className strings."""
    class_strings = re.findall(r'className\s*=\s*[{"\']([^"\'{}]+)["\'}]', code)
    # Also match template literals: className={`...`}
    class_strings += re.findall(r"className\s*=\s*\{`([^`]+)`\}", code)
    total = 0
    for s in class_strings:
        # Each space-separated token in a className is roughly one utility class.
        total += len(s.split())
    return total


def _count_inline_styles(code: str) -> int:
    """Count style={{}} JSX attributes."""
    return len(re.findall(r"style\s*=\s*\{\{", code))


def _has_typescript(code: str) -> bool:
    """Check for TypeScript annotations."""
    ts_patterns = [
        r":\s*(?:string|number|boolean|void|never|any|unknown)\b",
        r":\s*React\.\w+",
        r":\s*(?:JSX|FC|ReactNode|ReactElement)\b",
        r"<\w+(?:Props|Config)>",
        r"interface\s+\w+",
        r"type\s+\w+\s*=",
        r"as\s+\w+",
    ]
    return any(re.search(p, code) for p in ts_patterns)


def _count_lines(code: str) -> tuple[int, int]:
    """Return (non-empty non-comment lines, comment lines)."""
    loc = 0
    comments = 0
    for line in code.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            comments += 1
        else:
            loc += 1
    return loc, comments


def _has_exports(code: str) -> bool:
    """Check for export statements."""
    return bool(re.search(r"export\s+(?:default\s+)?(?:const|function|class)\b", code))


def _count_classnames(code: str) -> int:
    """Count className attributes."""
    return len(re.findall(r"className\s*=", code))


def _count_aria(code: str) -> int:
    """Count ARIA accessibility attributes."""
    return len(re.findall(r"aria-\w+\s*=", code))


def _count_jsx_elements(code: str) -> int:
    """Count JSX element openings (both HTML and custom components)."""
    # Match <Tag or <tag but not <= or << or closing tags
    return len(re.findall(r"<(?!/)[A-Za-z]\w*[\s/>]", code))


def _detect_style_approach(code: str) -> str:
    """Categorize the primary styling approach."""
    has_tailwind = bool(re.search(r'className\s*=\s*["{].*(?:flex|grid|p-|m-|text-|bg-|w-|h-)', code))
    has_css_modules = bool(re.search(r"styles\.\w+|\.module\.css", code))
    has_inline = bool(re.search(r"style\s*=\s*\{\{", code))

    approaches = []
    if has_tailwind:
        approaches.append("tailwind")
    if has_css_modules:
        approaches.append("css-modules")
    if has_inline:
        approaches.append("inline")

    if len(approaches) > 1:
        return "mixed"
    elif len(approaches) == 1:
        return approaches[0]
    else:
        return "none"


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------


def analyze_single(extracted_code: str) -> dict[str, Any]:
    """Compute all React metrics for a single extracted code sample."""
    loc, comments = _count_lines(extracted_code)

    return {
        "component_count": _count_components(extracted_code),
        "hook_count": _count_hooks(extracted_code),
        "prop_interface_count": _count_prop_interfaces(extracted_code),
        "event_handler_count": _count_event_handlers(extracted_code),
        "import_count": _count_imports(extracted_code),
        "tailwind_class_count": _count_tailwind_classes(extracted_code),
        "inline_style_count": _count_inline_styles(extracted_code),
        "typescript_usage": int(_has_typescript(extracted_code)),
        "lines_of_code": loc,
        "comment_lines": comments,
        "has_exports": int(_has_exports(extracted_code)),
        "className_count": _count_classnames(extracted_code),
        "aria_attribute_count": _count_aria(extracted_code),
        "jsx_element_count": _count_jsx_elements(extracted_code),
        "style_approach": _detect_style_approach(extracted_code),
    }


def analyze_all(
    raw_dir: str | Path,
    extracted_dir: str | Path,
    metrics_dir: str | Path,
    judge_dir: str | Path | None = None,
    log: logging.Logger | None = None,
) -> None:
    """Compute React metrics for all extracted responses and write CSV.

    Merges judge scores if judge_dir is provided.
    """
    raw_dir = Path(raw_dir)
    extracted_dir = Path(extracted_dir)
    metrics_dir = Path(metrics_dir)
    log = log or logging.getLogger("analyze_react")
    ensure_dirs(metrics_dir)

    extracted_files = sorted(extracted_dir.glob("*_extracted.json"))
    if not extracted_files:
        log.warning("No extracted files found in %s", extracted_dir)
        return

    rows: list[dict[str, Any]] = []
    judge_dir_path = Path(judge_dir) if judge_dir else None

    for ext_path in extracted_files:
        ext_data = load_json(ext_path)

        if not ext_data.get("is_valid", False):
            log.debug("Skipping invalid extraction: %s", ext_path.stem)
            continue

        code = ext_data.get("extracted_code", "")
        if not code:
            continue

        metrics = analyze_single(code)

        # Attach metadata from extraction result.
        metrics["model"] = ext_data.get("model", "")
        metrics["profile"] = ext_data.get("profile", "")
        metrics["task_id"] = ext_data.get("task_id", "")
        metrics["run_id"] = ext_data.get("run_id", 0)
        metrics["source_file"] = ext_data.get("source_file", "")
        metrics["blocks_found"] = ext_data.get("blocks_found", 0)
        metrics["total_chars"] = ext_data.get("total_chars", 0)

        # Merge judge scores if available.
        if judge_dir_path:
            # Judge file matches the original raw file stem.
            raw_stem = ext_data.get("source_file", "").replace(".json", "")
            judge_path = judge_dir_path / f"{raw_stem}_judge.json"
            if judge_path.exists():
                judge_data = load_json(judge_path)
                for key in ["visual_sophistication", "component_architecture",
                            "design_intentionality", "taste_signal"]:
                    metrics[key] = judge_data.get(key, None)

        rows.append(metrics)

        # Save per-file metrics.
        stem = ext_path.stem.replace("_extracted", "")
        save_json(metrics, metrics_dir / f"{stem}_metrics.json")

    # Write CSV.
    if rows:
        csv_path = metrics_dir / "metrics_table.csv"
        fieldnames = list(rows[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        log.info("Analysis complete -- %d files processed. CSV: %s", len(rows), csv_path)
    else:
        log.warning("No valid extracted code to analyze.")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Compute React metrics for extracted code")
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--extracted-dir", required=True)
    parser.add_argument("--metrics-dir", required=True)
    parser.add_argument("--judge-dir", default=None)
    args = parser.parse_args()

    from .utils import setup_logging
    log = setup_logging(args.metrics_dir, "analyze_react")
    analyze_all(args.raw_dir, args.extracted_dir, args.metrics_dir,
                judge_dir=args.judge_dir, log=log)


if __name__ == "__main__":
    main()
