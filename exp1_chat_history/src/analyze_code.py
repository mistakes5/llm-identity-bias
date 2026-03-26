"""Compute AST metrics, behavioral metrics, and composite scores for extracted code.

This is the core analysis module of the profile-bias experiment.  It produces
per-file metric JSONs and an aggregate ``metrics_table.csv`` that downstream
statistical analysis consumes.

Metric groups
-------------
* **13 AST metrics** — static properties of the extracted Python code.
* **6 behavioral metrics** — properties of the full LLM response (explanation
  text, clarifying questions, patterns used, etc.).
* **4 composite scores** — derived indicators on a 0-10 scale (plus a
  verbosity ratio).
"""

from __future__ import annotations

import ast
import argparse
import csv
import logging
import re
from pathlib import Path
from typing import Any

from .utils import save_json, load_json, setup_logging, ensure_dirs

logger = logging.getLogger("experiment.analyze")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Regex that matches fenced code blocks (```...```)
_CODE_BLOCK_RE = re.compile(r"```(?:\w*\s*)?\n(.*?)```", re.DOTALL)


def _text_outside_code_blocks(text: str) -> str:
    """Return all text that is *not* inside fenced code blocks."""
    return _CODE_BLOCK_RE.sub("", text)


def _text_before_first_code_block(text: str) -> str:
    """Return text before the very first fenced code block."""
    match = _CODE_BLOCK_RE.search(text)
    if match is None:
        return text
    return text[: match.start()]


# ---------------------------------------------------------------------------
# AST Metrics
# ---------------------------------------------------------------------------

# Advanced-pattern keywords / tokens searched in raw code text.
_ADVANCED_PATTERNS: list[str] = [
    "@",            # decorators (broad — refined below)
    "with ",        # context managers
    "dataclass",    # dataclass import / decorator
    "ABC",          # abstract base class
    "yield",        # generators
    ":=",           # walrus operator
    "match ",       # structural pattern matching
    "case ",        # structural pattern matching
    "f\"", "f'",    # f-strings (both quote styles)
    "__slots__",
    "@property",
    "@staticmethod",
    "@classmethod",
    "async def",
    "await ",
]


class ASTMetrics:
    """Static analysis metrics derived from ``ast.parse``."""

    @staticmethod
    def analyze(code: str) -> dict[str, Any]:
        """Return a dict of all 13 AST metrics for *code*.

        If the code cannot be parsed, every metric value is ``None`` and an
        extra ``parse_error`` key is set to ``True``.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            keys = [
                "cyclomatic_complexity",
                "max_nesting_depth",
                "function_count",
                "class_count",
                "total_lines",
                "comment_lines",
                "comment_ratio",
                "docstring_count",
                "type_annotation_count",
                "comprehension_count",
                "try_except_count",
                "unique_imports",
                "avg_function_length",
            ]
            result: dict[str, Any] = {k: None for k in keys}
            result["parse_error"] = True
            return result

        # -- cyclomatic complexity -------------------------------------------
        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                                 ast.Assert, ast.With)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                # Each `and`/`or` adds (number of operands - 1) decision points
                complexity += len(node.values) - 1

        # -- max nesting depth -----------------------------------------------
        max_depth = ASTMetrics._max_nesting_depth(tree)

        # -- function / class counts -----------------------------------------
        function_count = sum(
            1 for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
        class_count = sum(
            1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        )

        # -- line counts -----------------------------------------------------
        total_lines = code.count("\n") + 1
        comment_lines = sum(
            1 for line in code.splitlines() if line.strip().startswith("#")
        )
        comment_ratio = comment_lines / max(1, total_lines)

        # -- docstring count -------------------------------------------------
        docstring_count = 0
        # Module-level docstring
        if ast.get_docstring(tree) is not None:
            docstring_count += 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if ast.get_docstring(node) is not None:
                    docstring_count += 1

        # -- type annotation count -------------------------------------------
        type_annotation_count = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Return annotation
                if node.returns is not None:
                    type_annotation_count += 1
                # Argument annotations
                for arg in node.args.args:
                    if arg.annotation is not None:
                        type_annotation_count += 1
                for arg in node.args.posonlyargs:
                    if arg.annotation is not None:
                        type_annotation_count += 1
                for arg in node.args.kwonlyargs:
                    if arg.annotation is not None:
                        type_annotation_count += 1
                if node.args.vararg and node.args.vararg.annotation is not None:
                    type_annotation_count += 1
                if node.args.kwarg and node.args.kwarg.annotation is not None:
                    type_annotation_count += 1

        # -- comprehension count ---------------------------------------------
        comprehension_count = sum(
            1 for node in ast.walk(tree)
            if isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp,
                                 ast.GeneratorExp))
        )

        # -- try/except count ------------------------------------------------
        try_except_count = sum(
            1 for node in ast.walk(tree) if isinstance(node, ast.Try)
        )

        # -- unique imports --------------------------------------------------
        import_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    import_names.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    import_names.add(node.module.split(".")[0])
        unique_imports = len(import_names)

        # -- average function length -----------------------------------------
        func_lengths: list[int] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if hasattr(node, "end_lineno") and node.end_lineno is not None:
                    func_lengths.append(node.end_lineno - node.lineno + 1)
        avg_function_length = (
            sum(func_lengths) / len(func_lengths) if func_lengths else 0.0
        )

        return {
            "cyclomatic_complexity": complexity,
            "max_nesting_depth": max_depth,
            "function_count": function_count,
            "class_count": class_count,
            "total_lines": total_lines,
            "comment_lines": comment_lines,
            "comment_ratio": round(comment_ratio, 4),
            "docstring_count": docstring_count,
            "type_annotation_count": type_annotation_count,
            "comprehension_count": comprehension_count,
            "try_except_count": try_except_count,
            "unique_imports": unique_imports,
            "avg_function_length": round(avg_function_length, 2),
            "parse_error": False,
        }

    # -- nesting depth helper ------------------------------------------------

    @staticmethod
    def _max_nesting_depth(tree: ast.Module) -> int:
        """Walk the AST and return the maximum nesting depth of control-flow
        / compound statements (If, For, While, With, Try)."""
        nesting_types = (ast.If, ast.For, ast.While, ast.With, ast.Try)

        def _walk(node: ast.AST, depth: int) -> int:
            best = depth
            for child in ast.iter_child_nodes(node):
                if isinstance(child, nesting_types):
                    best = max(best, _walk(child, depth + 1))
                else:
                    best = max(best, _walk(child, depth))
            return best

        return _walk(tree, 0)


# ---------------------------------------------------------------------------
# Behavioral Metrics
# ---------------------------------------------------------------------------


class BehavioralMetrics:
    """Metrics derived from the full LLM response text (not just the code)."""

    @staticmethod
    def analyze(response_text: str, code: str) -> dict[str, Any]:
        """Return a dict of all 6 behavioral metrics."""

        # -- clarifying questions --------------------------------------------
        preamble = _text_before_first_code_block(response_text)
        has_clarifying_questions = any(
            line.rstrip().endswith("?") for line in preamble.splitlines()
        )

        # -- explanation vs code lengths -------------------------------------
        explanation_text = _text_outside_code_blocks(response_text)
        explanation_length = len(explanation_text)
        code_length = len(code)
        code_to_explanation_ratio = round(
            code_length / max(1, explanation_length), 4
        )

        # -- advanced pattern count ------------------------------------------
        advanced_pattern_count = BehavioralMetrics._count_advanced_patterns(code)

        # -- assumption count (in non-code text, case-insensitive) -----------
        assumption_count = len(re.findall(r"assum", explanation_text, re.IGNORECASE))

        return {
            "has_clarifying_questions": has_clarifying_questions,
            "explanation_length": explanation_length,
            "code_length": code_length,
            "code_to_explanation_ratio": code_to_explanation_ratio,
            "advanced_pattern_count": advanced_pattern_count,
            "assumption_count": assumption_count,
        }

    @staticmethod
    def _count_advanced_patterns(code: str) -> int:
        """Count occurrences of advanced / idiomatic Python patterns in *code*.

        Each pattern is counted by the number of matching lines or occurrences
        so that heavier use of a pattern yields a higher score.
        """
        count = 0

        # Decorator usage (lines starting with @, but not @= or @@)
        count += len(re.findall(r"^\s*@\w", code, re.MULTILINE))

        # `with` statements
        count += len(re.findall(r"^\s*(?:async\s+)?with\s", code, re.MULTILINE))

        # dataclass
        count += len(re.findall(r"dataclass", code))

        # ABC
        count += len(re.findall(r"\bABC\b", code))

        # yield
        count += len(re.findall(r"\byield\b", code))

        # walrus operator
        count += code.count(":=")

        # match/case (structural pattern matching)
        count += len(re.findall(r"^\s*match\s", code, re.MULTILINE))
        count += len(re.findall(r"^\s*case\s", code, re.MULTILINE))

        # f-strings
        count += len(re.findall(r"""f["']""", code))

        # __slots__
        count += code.count("__slots__")

        # @property, @staticmethod, @classmethod (already caught by decorator
        # line above, but we give extra credit for these specific ones)
        count += len(re.findall(r"@property\b", code))
        count += len(re.findall(r"@staticmethod\b", code))
        count += len(re.findall(r"@classmethod\b", code))

        # async def / await
        count += len(re.findall(r"\basync\s+def\b", code))
        count += len(re.findall(r"\bawait\b", code))

        return count


# ---------------------------------------------------------------------------
# Composite Scores
# ---------------------------------------------------------------------------


class CompositeScores:
    """Derived composite indicators combining AST and behavioral metrics."""

    @staticmethod
    def compute(
        ast_metrics: dict[str, Any],
        behavioral: dict[str, Any],
    ) -> dict[str, Any]:
        """Return 4 composite scores.

        All 0-10 scores are rounded to 2 decimal places.  If any underlying
        AST metric is ``None`` (parse error), composites that depend on it
        are also ``None``.
        """
        has_parse_error = ast_metrics.get("parse_error", False)

        # -- architectural_sophistication ------------------------------------
        if has_parse_error:
            architectural_sophistication = None
        else:
            classes = min(ast_metrics["class_count"], 5)
            funcs = min(ast_metrics["function_count"], 10)
            imports = min(ast_metrics["unique_imports"], 8)
            nesting_penalty = 1.0 - min(ast_metrics["max_nesting_depth"] / 10.0, 1.0)
            # Each sub-score is normalised to [0, 1] then weighted.
            arch_raw = (
                0.3 * (classes / 5.0)
                + 0.3 * (funcs / 10.0)
                + 0.2 * (imports / 8.0)
                + 0.2 * nesting_penalty
            )
            architectural_sophistication = round(arch_raw * 10.0, 2)

        # -- defensive_coding ------------------------------------------------
        if has_parse_error:
            defensive_coding = None
        else:
            try_exc = min(ast_metrics["try_except_count"], 5)
            annotations = min(ast_metrics["type_annotation_count"], 20)
            docstrings = min(ast_metrics["docstring_count"], 5)
            def_raw = (
                0.4 * (try_exc / 5.0)
                + 0.3 * (annotations / 20.0)
                + 0.3 * (docstrings / 5.0)
            )
            defensive_coding = round(def_raw * 10.0, 2)

        # -- idiomatic_density -----------------------------------------------
        if has_parse_error:
            idiomatic_density = None
        else:
            comprehensions = min(ast_metrics["comprehension_count"], 5)
            adv_patterns = min(behavioral["advanced_pattern_count"], 10)
            annotations_id = min(ast_metrics["type_annotation_count"], 20)
            idiom_raw = (
                0.3 * (comprehensions / 5.0)
                + 0.3 * (adv_patterns / 10.0)
                + 0.4 * (annotations_id / 20.0)
            )
            idiomatic_density = round(idiom_raw * 10.0, 2)

        # -- verbosity_ratio -------------------------------------------------
        explanation_length = behavioral.get("explanation_length", 0)
        code_length = behavioral.get("code_length", 1)
        verbosity_ratio = round(explanation_length / max(1, code_length), 4)

        return {
            "architectural_sophistication": architectural_sophistication,
            "defensive_coding": defensive_coding,
            "idiomatic_density": idiomatic_density,
            "verbosity_ratio": verbosity_ratio,
        }


# ---------------------------------------------------------------------------
# Filename parsing
# ---------------------------------------------------------------------------

_FILENAME_RE = re.compile(
    r"^(?P<model_short>.+?)_(?P<profile>[A-Z])_(?P<task_id>task\d+)_run(?P<run_id>\d+)$"
)


def parse_filename(stem: str) -> dict[str, str]:
    """Parse ``{model_short}_{profile}_{task_id}_run{n}`` into components.

    Returns a dict with ``model_short``, ``profile``, ``task_id``, and
    ``run_id`` keys.  Values default to ``"unknown"`` on parse failure.
    """
    m = _FILENAME_RE.match(stem)
    if m:
        return m.groupdict()
    # Graceful fallback — don't crash the pipeline.
    logger.warning("Could not parse filename stem: %s", stem)
    return {
        "model_short": "unknown",
        "profile": "unknown",
        "task_id": "unknown",
        "run_id": "unknown",
    }


# ---------------------------------------------------------------------------
# Aggregate pipeline
# ---------------------------------------------------------------------------

# Column order for the CSV.
_CSV_COLUMNS: list[str] = [
    # identifiers
    "model",
    "model_short",
    "profile",
    "task_id",
    "run_id",
    # AST metrics
    "cyclomatic_complexity",
    "max_nesting_depth",
    "function_count",
    "class_count",
    "total_lines",
    "comment_lines",
    "comment_ratio",
    "docstring_count",
    "type_annotation_count",
    "comprehension_count",
    "try_except_count",
    "unique_imports",
    "avg_function_length",
    "parse_error",
    # behavioral
    "has_clarifying_questions",
    "explanation_length",
    "code_length",
    "code_to_explanation_ratio",
    "advanced_pattern_count",
    "assumption_count",
    # composites
    "architectural_sophistication",
    "defensive_coding",
    "idiomatic_density",
    "verbosity_ratio",
]


def analyze_all(
    extracted_dir: str | Path,
    raw_dir: str | Path,
    metrics_dir: str | Path,
    model_name: str = "",
    log: logging.Logger | None = None,
) -> list[dict[str, Any]]:
    """Analyse every extracted code file and its corresponding raw response.

    Parameters
    ----------
    extracted_dir:
        Directory containing ``{stem}.py`` files produced by ``extract_code``.
    raw_dir:
        Directory containing the original ``{stem}.json`` response files
        (used for behavioral metrics).
    metrics_dir:
        Output directory for per-file metric JSONs **and** the aggregate
        ``metrics_table.csv``.
    model_name:
        Full model identifier string to include in the CSV (e.g.
        ``"claude-sonnet-4-20250514"``).  Falls back to ``model_short`` if empty.
    log:
        Optional logger.

    Returns
    -------
    list[dict]
        The rows that were written to the CSV.
    """
    if log is None:
        log = logger

    extracted_path = Path(extracted_dir)
    raw_path = Path(raw_dir)
    metrics_path = Path(metrics_dir)
    ensure_dirs(metrics_path)

    rows: list[dict[str, Any]] = []

    py_files = sorted(extracted_path.glob("*.py"))
    if not py_files:
        log.warning("No .py files found in %s", extracted_path)
        return rows

    log.info("Analysing %d extracted files...", len(py_files))

    for py_file in py_files:
        stem = py_file.stem
        log.debug("Processing %s", stem)

        # --- load code ------------------------------------------------------
        code = py_file.read_text(encoding="utf-8")

        # --- load raw response (for behavioral metrics) ---------------------
        raw_json_path = raw_path / f"{stem}.json"
        if raw_json_path.exists():
            raw_data = load_json(raw_json_path)
            response_text: str = raw_data.get("response_text", "")
        else:
            log.warning(
                "Raw response not found for %s — behavioral metrics will use "
                "code-only fallback.",
                stem,
            )
            response_text = code

        # --- compute metrics ------------------------------------------------
        ast_m = ASTMetrics.analyze(code)
        beh_m = BehavioralMetrics.analyze(response_text, code)
        comp_m = CompositeScores.compute(ast_m, beh_m)

        # --- per-file JSON --------------------------------------------------
        per_file: dict[str, Any] = {
            "file": stem,
            **ast_m,
            **beh_m,
            **comp_m,
        }
        save_json(per_file, metrics_path / f"{stem}_metrics.json")

        # --- CSV row --------------------------------------------------------
        ident = parse_filename(stem)
        row: dict[str, Any] = {
            "model": model_name or ident["model_short"],
            "model_short": ident["model_short"],
            "profile": ident["profile"],
            "task_id": ident["task_id"],
            "run_id": ident["run_id"],
            **ast_m,
            **beh_m,
            **comp_m,
        }
        rows.append(row)

    # --- write aggregate CSV ------------------------------------------------
    csv_path = metrics_path / "metrics_table.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    log.info(
        "Wrote %d rows to %s (parse errors: %d)",
        len(rows),
        csv_path,
        sum(1 for r in rows if r.get("parse_error")),
    )

    return rows


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Command-line interface for the analysis module."""
    parser = argparse.ArgumentParser(
        description="Compute AST, behavioral, and composite metrics for extracted code.",
    )
    parser.add_argument(
        "--extracted-dir",
        default="results/extracted",
        help="Directory with extracted .py files (default: results/extracted)",
    )
    parser.add_argument(
        "--raw-dir",
        default="results/raw",
        help="Directory with raw response .json files (default: results/raw)",
    )
    parser.add_argument(
        "--metrics-dir",
        default="results/metrics",
        help="Output directory for metric JSONs and CSV (default: results/metrics)",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Full model name to record in the CSV (optional)",
    )
    args = parser.parse_args()

    log = setup_logging("results", "analyze_code")
    analyze_all(
        extracted_dir=args.extracted_dir,
        raw_dir=args.raw_dir,
        metrics_dir=args.metrics_dir,
        model_name=args.model,
        log=log,
    )


if __name__ == "__main__":
    main()
