"""Subjective text analysis — automated metrics and composite scoring.

Computes structural, rhetorical, and cross-domain metrics on aesthetic /
analytical model responses (not code).  Optionally merges LLM-judge scores
to produce composite indices.

Replaces ``analyze_code.py`` for the subjective-evaluation experiment track.
"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from typing import Any

from .utils import save_json, load_json, setup_logging, ensure_dirs

# ---------------------------------------------------------------------------
# Hedging phrases (case-insensitive matching)
# ---------------------------------------------------------------------------

_HEDGE_PHRASES: list[str] = [
    "perhaps",
    "might",
    "arguably",
    "it could be said",
    "one might argue",
    "potentially",
    "possibly",
    "in some ways",
    "to some extent",
    "it's worth noting",
    "it seems",
    "may be",
    "could be",
    "tends to",
]

# ---------------------------------------------------------------------------
# Cross-domain keyword buckets
# ---------------------------------------------------------------------------

_DOMAIN_BUCKETS: dict[str, list[str]] = {
    "philosophy": [
        "phenomenology", "epistemolog", "ontolog",
        "Heidegger", "Merleau-Ponty", "Husserl", "Derrida",
        "Foucault", "Deleuze", "Kant", "Hegel", "Nietzsche",
        "existential", "dialectic", "hermeneutic",
    ],
    "economics": [
        "Veblen", "Bourdieu", "capital", "market", "scarcity",
        "commodity", "pricing", "supply", "demand", "economic",
    ],
    "science": [
        "perception", "cognitive", "neural", "wavelength",
        "optic", "retina", "psychology",
    ],
    "architecture": [
        "Corbusier", "Gehry", "Hadid", "Bauhaus", "brutalis",
        "modernist architecture", "structural",
    ],
    "film": [
        "cinema", "cinematograph", "Kubrick", "Tarkovsky",
        "mise-en-scène", "montage",
    ],
    "fashion": [
        "couture", "silhouette", "drape", "textile",
        "Balenciaga", "Miyake", "Kawakubo",
    ],
    "politics": [
        "ideology", "hegemony", "colonial", "postcolonial",
        "imperialis", "neoliberal", "political",
    ],
    "music": [
        "harmonic", "polyphon", "Cage", "Stockhausen",
        "atonal", "contrapuntal",
    ],
}

# Pre-compiled patterns for named-reference detection.
_RE_QUOTED = re.compile(r'"[^"]{2,}"')
_RE_YEAR = re.compile(r"\((?:18|19|20)\d{2}\)")
_RE_REFERENCE_WORDS = re.compile(
    r"\b(?:series|exhibition|collection|movement)\b", re.IGNORECASE,
)

# Mid-sentence capitalized word (not sentence-initial, not all-caps).
_RE_MID_CAP = re.compile(r"(?<=[a-z] )[A-Z][a-z]+")

# Multi-word proper nouns: two or more capitalized words in sequence.
_RE_MULTI_CAP = re.compile(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")


# ---------------------------------------------------------------------------
# TextMetrics
# ---------------------------------------------------------------------------


class TextMetrics:
    """Static-only class that extracts automated metrics from response text."""

    @staticmethod
    def analyze(response_text: str) -> dict[str, Any]:
        """Return a dict of automated text metrics for *response_text*."""
        text = response_text
        length = len(text)
        est_tokens = length // 4

        # --- paragraph_count ---
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        paragraph_count = len(paragraphs)

        # --- question_count ---
        lines = text.splitlines()
        question_count = sum(1 for line in lines if line.rstrip().endswith("?"))

        # --- hedge_density (per 100 tokens) ---
        text_lower = text.lower()
        hedge_hits = sum(text_lower.count(phrase) for phrase in _HEDGE_PHRASES)
        token_denominator = max(est_tokens / 100, 1)
        hedge_density = round(hedge_hits / token_denominator, 3)

        # --- unique_entity_count ---
        entities: set[str] = set()
        for match in _RE_MULTI_CAP.finditer(text):
            entities.add(match.group())
        for match in _RE_MID_CAP.finditer(text):
            entities.add(match.group())
        unique_entity_count = len(entities)

        # --- named_reference_count ---
        ref_count = 0
        ref_count += len(_RE_QUOTED.findall(text))
        ref_count += len(_RE_YEAR.findall(text))
        ref_count += len(_RE_REFERENCE_WORDS.findall(text))
        named_reference_count = ref_count

        # --- cross_domain_count ---
        domains_hit: set[str] = set()
        for domain, keywords in _DOMAIN_BUCKETS.items():
            for kw in keywords:
                # Use case-insensitive search for partial matches (e.g. "brutalis" in "brutalism").
                if kw.lower() in text_lower:
                    domains_hit.add(domain)
                    break
        cross_domain_count = len(domains_hit)

        return {
            "response_length": length,
            "estimated_tokens": est_tokens,
            "paragraph_count": paragraph_count,
            "question_count": question_count,
            "hedge_density": hedge_density,
            "unique_entity_count": unique_entity_count,
            "named_reference_count": named_reference_count,
            "cross_domain_count": cross_domain_count,
        }


# ---------------------------------------------------------------------------
# CompositeScores
# ---------------------------------------------------------------------------


def _cap_scale(value: float, cap: float, scale_to: float = 5.0) -> float:
    """Clamp *value* to [0, cap] and rescale linearly to [0, scale_to]."""
    return round(min(value, cap) / cap * scale_to, 3)


class CompositeScores:
    """Compute composite indices from automated metrics + optional judge scores."""

    @staticmethod
    def compute(
        text_metrics: dict[str, Any],
        judge_scores: dict[str, Any] | None = None,
    ) -> dict[str, Any | None]:
        """Return composite score dict.

        When *judge_scores* is provided, composites blend automated metrics
        with judge ratings.  When ``None``, only normalised automated metrics
        are returned and judge-dependent composites are ``None``.
        """
        norm_entities = _cap_scale(text_metrics.get("unique_entity_count", 0), cap=20)
        norm_refs = _cap_scale(text_metrics.get("named_reference_count", 0), cap=10)
        norm_domains = _cap_scale(text_metrics.get("cross_domain_count", 0), cap=5)
        norm_questions = _cap_scale(text_metrics.get("question_count", 0), cap=5)

        if judge_scores is not None:
            analytical_depth = judge_scores.get("analytical_depth", 0)
            challenge_level = judge_scores.get("challenge_level", 0)
            register_level = judge_scores.get("register_level", 0)
            specificity_score = judge_scores.get("specificity_score", 0)

            analytical_sophistication = round(
                (analytical_depth + challenge_level + register_level) / 3, 3,
            )
            specificity_index = round(
                (specificity_score + norm_entities + norm_refs) / 3, 3,
            )
            intellectual_engagement = round(
                (norm_domains + norm_questions + challenge_level) / 3, 3,
            )
        else:
            analytical_sophistication = None
            specificity_index = None
            intellectual_engagement = None

        return {
            "analytical_sophistication": analytical_sophistication,
            "specificity_index": specificity_index,
            "intellectual_engagement": intellectual_engagement,
            "norm_unique_entity_count": norm_entities,
            "norm_named_reference_count": norm_refs,
            "norm_cross_domain_count": norm_domains,
            "norm_question_count": norm_questions,
        }


# ---------------------------------------------------------------------------
# Filename parsing
# ---------------------------------------------------------------------------

_RE_FILENAME = re.compile(
    r"^(?P<model_short>.+?)_(?P<profile>[^_]+)_(?P<task_id>[^_]+)_run(?P<run>\d+)\.json$"
)


def _parse_filename(name: str) -> dict[str, str] | None:
    """Extract metadata from the standard filename pattern.

    Expected format: ``{model_short}_{profile}_{task_id}_run{n}.json``
    """
    m = _RE_FILENAME.match(name)
    if not m:
        return None
    return {
        "model_short": m.group("model_short"),
        "profile": m.group("profile"),
        "task_id": m.group("task_id"),
        "run_id": f"run{m.group('run')}",
    }


# ---------------------------------------------------------------------------
# Main analysis pipeline
# ---------------------------------------------------------------------------

# Column ordering for the output CSV.
_META_COLS: list[str] = ["model", "model_short", "profile", "task_id", "run_id"]
_TEXT_METRIC_COLS: list[str] = [
    "response_length", "estimated_tokens", "paragraph_count",
    "question_count", "hedge_density", "unique_entity_count",
    "named_reference_count", "cross_domain_count",
]
_JUDGE_COLS: list[str] = [
    "analytical_depth", "challenge_level", "register_level",
    "specificity_score",
]
_COMPOSITE_COLS: list[str] = [
    "analytical_sophistication", "specificity_index", "intellectual_engagement",
    "norm_unique_entity_count", "norm_named_reference_count",
    "norm_cross_domain_count", "norm_question_count",
]


def analyze_all(
    raw_dir: str | Path,
    metrics_dir: str | Path,
    judge_dir: str | Path | None = None,
    log: logging.Logger | None = None,
) -> str:
    """Analyse every raw response JSON and write per-file metrics + summary CSV.

    Parameters
    ----------
    raw_dir:
        Directory containing raw response JSON files.
    metrics_dir:
        Output directory for per-file metric JSONs and the summary CSV.
    judge_dir:
        Optional directory containing LLM-judge score JSONs (filenames must
        match the raw files).
    log:
        Logger instance.  A no-op logger is used if ``None``.

    Returns
    -------
    str
        Absolute path to the generated ``metrics_table.csv``.
    """
    raw_dir = Path(raw_dir)
    metrics_dir = Path(metrics_dir)
    ensure_dirs(metrics_dir)

    if log is None:
        log = logging.getLogger("analyze_text")
        if not log.handlers:
            log.addHandler(logging.NullHandler())

    judge_path = Path(judge_dir) if judge_dir else None
    rows: list[dict[str, Any]] = []
    processed = 0
    skipped = 0

    for json_file in sorted(raw_dir.glob("*.json")):
        parsed = _parse_filename(json_file.name)
        if parsed is None:
            log.warning("Skipping file with unrecognised name pattern: %s", json_file.name)
            skipped += 1
            continue

        raw_data = load_json(json_file)
        response_text: str = raw_data.get("response_text", raw_data.get("text", ""))
        if not response_text:
            log.warning("No response text in %s — skipping.", json_file.name)
            skipped += 1
            continue

        # Automated metrics.
        text_metrics = TextMetrics.analyze(response_text)

        # Optional judge scores.
        judge_scores: dict[str, Any] | None = None
        if judge_path is not None:
            judge_file = judge_path / json_file.name
            if judge_file.exists():
                try:
                    judge_scores = load_json(judge_file)
                    log.debug("Loaded judge scores for %s", json_file.name)
                except Exception as exc:
                    log.warning("Failed to load judge scores for %s: %s", json_file.name, exc)

        # Composite scores.
        composites = CompositeScores.compute(text_metrics, judge_scores)

        # Assemble per-file output.
        per_file: dict[str, Any] = {
            **parsed,
            "model": raw_data.get("model", parsed["model_short"]),
            **text_metrics,
        }
        if judge_scores is not None:
            per_file["judge_scores"] = judge_scores
        per_file["composites"] = composites

        save_json(per_file, metrics_dir / json_file.name)

        # Flat row for CSV.
        row: dict[str, Any] = {
            "model": per_file["model"],
            "model_short": parsed["model_short"],
            "profile": parsed["profile"],
            "task_id": parsed["task_id"],
            "run_id": parsed["run_id"],
        }
        row.update(text_metrics)
        if judge_scores is not None:
            for col in _JUDGE_COLS:
                row[col] = judge_scores.get(col, "")
        else:
            for col in _JUDGE_COLS:
                row[col] = ""
        row.update(composites)

        rows.append(row)
        processed += 1

    # Write summary CSV.
    csv_path = metrics_dir / "metrics_table.csv"
    fieldnames = _META_COLS + _TEXT_METRIC_COLS + _JUDGE_COLS + _COMPOSITE_COLS
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    log.info(
        "Analysis complete — %d files processed, %d skipped. CSV → %s",
        processed, skipped, csv_path,
    )
    return str(csv_path.resolve())


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for standalone text analysis."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Compute automated text metrics on subjective model responses.",
    )
    parser.add_argument(
        "--raw-dir", type=str, required=True,
        help="Directory containing raw response JSON files.",
    )
    parser.add_argument(
        "--metrics-dir", type=str, required=True,
        help="Output directory for per-file metrics and summary CSV.",
    )
    parser.add_argument(
        "--judge-dir", type=str, default=None,
        help="Optional directory with LLM-judge score JSONs.",
    )
    parser.add_argument(
        "--log-dir", type=str, default=None,
        help="Directory for log files (defaults to metrics-dir).",
    )

    args = parser.parse_args()
    log_dir = args.log_dir or args.metrics_dir
    log = setup_logging(log_dir, name="analyze_text")

    csv_path = analyze_all(
        raw_dir=args.raw_dir,
        metrics_dir=args.metrics_dir,
        judge_dir=args.judge_dir,
        log=log,
    )
    print(f"Metrics CSV written to: {csv_path}")


if __name__ == "__main__":
    main()
