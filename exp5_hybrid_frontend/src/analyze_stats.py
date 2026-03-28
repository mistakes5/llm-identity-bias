"""Statistical analysis module for the profile-bias experiment.

Runs one-way ANOVA, two-way ANOVA, Mann-Whitney U, Kruskal-Wallis,
Cohen's d effect sizes, and PELT change-point detection on experiment
metrics. Produces JSON result files and a human-readable summary report.

Exp5 additions: axis correlation (code vs design composites) and
profile x axis interaction analysis.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import f_oneway, kruskal, mannwhitneyu, pearsonr, shapiro
import statsmodels.api as sm
from statsmodels.formula.api import ols
from statsmodels.stats.anova import anova_lm

from .utils import save_json, setup_logging, ensure_dirs

# Lazy import of PhaseTransitionDetector to avoid pulling in Flask
_PhaseTransitionDetector = None


def _build_fallback_regimes(values: np.ndarray, change_points: list[int]) -> list[dict[str, Any]]:
    regimes: list[dict[str, Any]] = []
    start = 0
    for end in [*change_points, len(values)]:
        segment = values[start:end]
        if len(segment) == 0:
            continue
        regimes.append(
            {
                "start": int(start),
                "end": int(end),
                "n": int(len(segment)),
                "mean": float(np.nanmean(segment)),
                "std": float(np.nanstd(segment)),
            }
        )
        start = end
    return regimes


class _FallbackPhaseTransitionDetector:
    """Small in-repo fallback when no external detector path is configured."""

    def __init__(self, min_segment_length: int = 3, penalty_multiplier: float = 1.0):
        self.min_segment_length = min_segment_length
        self.penalty_multiplier = penalty_multiplier

    def detect_transitions(self, values: list[float]) -> dict[str, Any]:
        arr = np.asarray(values, dtype=float)
        n_vals = len(arr)

        if n_vals == 0:
            return {"change_points": [], "n_regimes": 0, "regimes": [], "phase": "empty"}

        if n_vals < self.min_segment_length * 2:
            return {
                "change_points": [],
                "n_regimes": 1,
                "regimes": _build_fallback_regimes(arr, []),
                "phase": "insufficient_data",
            }

        spread = float(np.nanstd(arr))
        if spread == 0.0:
            return {
                "change_points": [],
                "n_regimes": 1,
                "regimes": _build_fallback_regimes(arr, []),
                "phase": "stable",
            }

        best_cp = None
        best_delta = 0.0
        for cp in range(self.min_segment_length, n_vals - self.min_segment_length + 1):
            left = arr[:cp]
            right = arr[cp:]
            delta = abs(float(np.nanmean(left)) - float(np.nanmean(right)))
            if delta > best_delta:
                best_delta = delta
                best_cp = cp

        threshold = spread * self.penalty_multiplier
        change_points = [best_cp] if best_cp is not None and best_delta >= threshold else []
        return {
            "change_points": change_points,
            "n_regimes": len(change_points) + 1,
            "regimes": _build_fallback_regimes(arr, change_points),
            "phase": "shift_detected" if change_points else "stable",
        }


def _load_external_pelt_detector():
    import importlib.util

    candidates: list[Path] = []
    env_path = os.environ.get("STATISTICAL_DETECTORS_PATH")
    if env_path:
        candidates.append(Path(env_path).expanduser())
    candidates.append(Path(__file__).with_name("statistical_detectors.py"))

    for candidate in candidates:
        if not candidate.exists():
            continue
        spec = importlib.util.spec_from_file_location("statistical_detectors", candidate)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.PhaseTransitionDetector

    return None


def _get_pelt_detector():
    global _PhaseTransitionDetector
    if _PhaseTransitionDetector is None:
        _PhaseTransitionDetector = _load_external_pelt_detector() or _FallbackPhaseTransitionDetector
    return _PhaseTransitionDetector
# ---------------------------------------------------------------------------
# Metadata columns excluded from metric analysis
# ---------------------------------------------------------------------------

_NON_METRIC_COLS = {"model", "model_short", "profile", "task_id", "run_id"}


# ---------------------------------------------------------------------------
# 1. Load metrics
# ---------------------------------------------------------------------------


def load_metrics(csv_path: str | Path) -> pd.DataFrame:
    """Load the experiment metrics CSV into a DataFrame.

    Handles None values stored as empty strings and converts all metric
    columns to numeric types.
    """
    df = pd.read_csv(csv_path, dtype=str)

    # Replace empty strings and literal "None" with actual NaN
    df.replace({"": np.nan, "None": np.nan, "none": np.nan}, inplace=True)

    # Convert metric columns to numeric
    for col in df.columns:
        if col not in _NON_METRIC_COLS:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# ---------------------------------------------------------------------------
# 2. Get metric columns
# ---------------------------------------------------------------------------


def get_metric_columns(df: pd.DataFrame) -> list[str]:
    """Return all column names that represent metrics (not metadata)."""
    return [c for c in df.columns if c not in _NON_METRIC_COLS]


# ---------------------------------------------------------------------------
# 3. One-way ANOVA
# ---------------------------------------------------------------------------


def run_one_way_anova(df: pd.DataFrame, metric: str) -> dict | None:
    """Run one-way ANOVA on *metric* grouped by profile (A, B, C).

    Returns a result dict or ``None`` if any group has fewer than 2
    non-null observations.
    """
    groups: dict[str, pd.Series] = {}
    for profile in ("A", "B", "C"):
        vals = df.loc[df["profile"] == profile, metric].dropna()
        if len(vals) < 2:
            return None
        groups[profile] = vals

    f_stat, p_val = f_oneway(*groups.values())

    group_means = {k: float(v.mean()) for k, v in groups.items()}
    group_stds = {k: float(v.std()) for k, v in groups.items()}

    return {
        "metric": metric,
        "F_statistic": float(f_stat),
        "p_value": float(p_val),
        "significant": p_val < 0.05,
        "group_means": group_means,
        "group_stds": group_stds,
    }


# ---------------------------------------------------------------------------
# 4. Two-way ANOVA
# ---------------------------------------------------------------------------


def run_two_way_anova(df: pd.DataFrame, metric: str) -> dict | None:
    """Run two-way ANOVA (profile x model_short) using statsmodels.

    Returns a result dict or ``None`` on failure.
    """
    try:
        subset = df[["profile", "model_short", metric]].dropna()
        if len(subset) < 6:
            return None

        # Ensure the metric column name is safe for the formula
        safe_metric = metric
        # If the column name has special chars, temporarily rename
        needs_rename = not metric.isidentifier()
        if needs_rename:
            safe_metric = "metric_val"
            subset = subset.rename(columns={metric: safe_metric})

        formula = f"{safe_metric} ~ C(profile) * C(model_short)"
        model = ols(formula, data=subset).fit()
        table = sm.stats.anova_lm(model, typ=2)

        # Extract rows — statsmodels uses these index names
        result: dict[str, Any] = {"metric": metric}

        for factor, prefix in [
            ("C(profile)", "profile"),
            ("C(model_short)", "model"),
            ("C(profile):C(model_short)", "interaction"),
        ]:
            if factor in table.index:
                result[f"{prefix}_F"] = float(table.loc[factor, "F"])
                result[f"{prefix}_p"] = float(table.loc[factor, "PR(>F)"])
            else:
                result[f"{prefix}_F"] = None
                result[f"{prefix}_p"] = None

        return result

    except Exception:
        return None


# ---------------------------------------------------------------------------
# 5. Cohen's d
# ---------------------------------------------------------------------------


def compute_cohens_d(group1: pd.Series | np.ndarray, group2: pd.Series | np.ndarray) -> float:
    """Compute Cohen's d (standardized mean difference) between two groups.

    Uses the pooled standard deviation. Returns 0.0 for degenerate cases
    (empty groups, zero variance).
    """
    g1 = np.asarray(group1, dtype=float)
    g2 = np.asarray(group2, dtype=float)

    g1 = g1[~np.isnan(g1)]
    g2 = g2[~np.isnan(g2)]

    if len(g1) < 1 or len(g2) < 1:
        return 0.0

    n1, n2 = len(g1), len(g2)
    mean1, mean2 = g1.mean(), g2.mean()
    var1, var2 = g1.var(ddof=1) if n1 > 1 else 0.0, g2.var(ddof=1) if n2 > 1 else 0.0

    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / max(n1 + n2 - 2, 1))

    if pooled_std == 0.0:
        return 0.0

    return float((mean1 - mean2) / pooled_std)


def _interpret_cohens_d(d: float) -> str:
    """Return a textual interpretation of an absolute Cohen's d value."""
    ad = abs(d)
    if ad < 0.2:
        return "negligible"
    elif ad < 0.5:
        return "small"
    elif ad < 0.8:
        return "medium"
    else:
        return "large"


# ---------------------------------------------------------------------------
# 6. Effect sizes for all pairs
# ---------------------------------------------------------------------------


def compute_effect_sizes(df: pd.DataFrame, metric: str) -> dict:
    """Compute Cohen's d for all three profile pairs (A vs B, A vs C, B vs C).

    Each pair includes the raw d value and a human-readable interpretation.
    """
    groups: dict[str, pd.Series] = {}
    for profile in ("A", "B", "C"):
        groups[profile] = df.loc[df["profile"] == profile, metric].dropna()

    pairs = [("A", "B"), ("A", "C"), ("B", "C")]
    result: dict[str, Any] = {"metric": metric, "pairs": {}}

    for p1, p2 in pairs:
        d = compute_cohens_d(groups[p1], groups[p2])
        pair_key = f"{p1}_vs_{p2}"
        result["pairs"][pair_key] = {
            "cohens_d": round(d, 4),
            "abs_d": round(abs(d), 4),
            "interpretation": _interpret_cohens_d(d),
        }

    return result


# ---------------------------------------------------------------------------
# 7. Mann-Whitney U
# ---------------------------------------------------------------------------


def run_mann_whitney(df: pd.DataFrame, metric: str) -> dict:
    """Run Mann-Whitney U tests for all three profile pairs with Bonferroni correction.

    The Bonferroni correction multiplies each p-value by 3 (number of
    comparisons) and caps at 1.0.
    """
    groups: dict[str, pd.Series] = {}
    for profile in ("A", "B", "C"):
        groups[profile] = df.loc[df["profile"] == profile, metric].dropna()

    pairs = [("A", "B"), ("A", "C"), ("B", "C")]
    result: dict[str, Any] = {"metric": metric, "pairs": {}}

    for p1, p2 in pairs:
        g1, g2 = groups[p1], groups[p2]
        pair_key = f"{p1}_vs_{p2}"

        if len(g1) < 2 or len(g2) < 2:
            result["pairs"][pair_key] = {
                "U_statistic": None,
                "p_value_raw": None,
                "p_value_corrected": None,
                "significant": False,
                "skipped": True,
            }
            continue

        u_stat, p_val = mannwhitneyu(g1, g2, alternative="two-sided")
        p_corrected = min(p_val * 3, 1.0)

        result["pairs"][pair_key] = {
            "U_statistic": float(u_stat),
            "p_value_raw": float(p_val),
            "p_value_corrected": float(p_corrected),
            "significant": p_corrected < 0.05,
        }

    return result


# ---------------------------------------------------------------------------
# 7b. Planned contrasts (Experiment 5)
# ---------------------------------------------------------------------------


def compute_planned_contrasts(df: pd.DataFrame, metric: str) -> dict:
    """Compute 5 planned contrasts for the 7-profile Experiment 5 design.

    Contrasts (exp5 profile letters):
        1. F vs B  -- high-design persona vs control
        2. G vs B  -- high-code persona vs control
        3. A vs C  -- non-technical sophistication effect
        4. F vs G  -- design-focused vs code-focused
        5. A vs F  -- general high-soph vs design specialist

    Each contrast uses Mann-Whitney U with rank-biserial r as effect size.
    """
    all_profiles = sorted(df["profile"].dropna().unique())
    groups: dict[str, pd.Series] = {}
    for profile in all_profiles:
        groups[profile] = df.loc[df["profile"] == profile, metric].dropna()

    def _contrast(g1: pd.Series, g2: pd.Series, label: str) -> dict:
        if len(g1) < 2 or len(g2) < 2:
            return {"label": label, "skipped": True}
        u_stat, p_val = mannwhitneyu(g1, g2, alternative="two-sided")
        n1, n2 = len(g1), len(g2)
        # rank-biserial r = 1 - 2U/(n1*n2)
        r_effect = 1.0 - (2.0 * u_stat) / (n1 * n2) if n1 * n2 > 0 else 0.0
        d = compute_cohens_d(g1, g2)
        return {
            "label": label,
            "U_statistic": float(u_stat),
            "p_value": float(p_val),
            "rank_biserial_r": round(float(r_effect), 4),
            "cohens_d": round(d, 4),
            "n1": n1,
            "n2": n2,
            "significant": p_val < 0.05,
        }

    contrasts: list[dict] = []

    # Contrast 1: F vs B (high-design persona vs control)
    if "F" in groups and "B" in groups:
        contrasts.append(_contrast(groups["F"], groups["B"], "F_vs_B (high-design vs control)"))

    # Contrast 2: G vs B (high-code persona vs control)
    if "G" in groups and "B" in groups:
        contrasts.append(_contrast(groups["G"], groups["B"], "G_vs_B (high-code vs control)"))

    # Contrast 3: A vs C (non-technical sophistication effect)
    if "A" in groups and "C" in groups:
        contrasts.append(_contrast(groups["A"], groups["C"], "A_vs_C (non-tech sophistication)"))

    # Contrast 4: F vs G (design-focused vs code-focused)
    if "F" in groups and "G" in groups:
        contrasts.append(_contrast(groups["F"], groups["G"], "F_vs_G (design vs code focus)"))

    # Contrast 5: A vs F (general high-soph vs design specialist)
    if "A" in groups and "F" in groups:
        contrasts.append(_contrast(groups["A"], groups["F"], "A_vs_F (general vs design specialist)"))

    return {
        "metric": metric,
        "contrasts": contrasts,
    }


# ---------------------------------------------------------------------------
# 8. Kruskal-Wallis
# ---------------------------------------------------------------------------


def run_kruskal_wallis(df: pd.DataFrame, metric: str) -> dict | None:
    """Run the Kruskal-Wallis H-test as a non-parametric ANOVA alternative.

    Returns ``None`` if any group has fewer than 2 observations.
    """
    groups: list[pd.Series] = []
    for profile in ("A", "B", "C"):
        vals = df.loc[df["profile"] == profile, metric].dropna()
        if len(vals) < 2:
            return None
        groups.append(vals)

    h_stat, p_val = kruskal(*groups)

    return {
        "metric": metric,
        "H_statistic": float(h_stat),
        "p_value": float(p_val),
        "significant": p_val < 0.05,
    }


# ---------------------------------------------------------------------------
# 8b. Krippendorff's alpha (ordinal)
# ---------------------------------------------------------------------------


def compute_krippendorffs_alpha(ratings: list[list[int]]) -> float:
    """Compute ordinal Krippendorff's alpha for inter-rater reliability.

    Args:
        ratings: List of lists where each inner list contains the scores
            from one judge run across all items.  E.g.
            ``[[4,3,4,3,...], [4,4,3,3,...], [3,3,4,3,...]]`` for 3 runs.
            All inner lists must have the same length (number of items).

    Returns:
        Krippendorff's alpha (float).  1.0 = perfect agreement,
        0.0 = agreement equivalent to chance, negative = worse than chance.
    """
    if not ratings or len(ratings) < 2:
        return float("nan")

    n_raters = len(ratings)
    n_items = len(ratings[0])

    if n_items == 0:
        return float("nan")

    # Build reliability data matrix: shape (n_items, n_raters)
    # Each cell is the rating rater k gave to item i.
    data = np.array(ratings, dtype=float).T  # (n_items, n_raters)

    # Collect all unique values (levels) for ordinal distance
    all_values = sorted(set(int(v) for v in data[~np.isnan(data)]))
    if len(all_values) < 2:
        # All ratings identical → perfect agreement
        return 1.0

    # Ordinal distance function: |i - j|
    def _ordinal_dist(a: float, b: float) -> float:
        return abs(a - b)

    # Build coincidence matrix from the reliability data
    # For each item with m_u pairable raters, add 1/(m_u - 1) to cell (c,k)
    # for every pair of values (c, k) assigned to that item.
    val_to_idx = {v: i for i, v in enumerate(all_values)}
    n_vals = len(all_values)
    coincidence = np.zeros((n_vals, n_vals), dtype=float)

    for i in range(n_items):
        item_ratings = data[i, :]
        valid = item_ratings[~np.isnan(item_ratings)]
        m_u = len(valid)
        if m_u < 2:
            continue
        weight = 1.0 / (m_u - 1)
        for r1 in valid:
            for r2 in valid:
                if r1 != r2 or True:  # include self-pairs for coincidence
                    coincidence[val_to_idx[int(r1)], val_to_idx[int(r2)]] += weight

    # Marginals: n_c = sum of column c in coincidence matrix
    n_c = coincidence.sum(axis=0)
    n_total = n_c.sum()

    if n_total == 0:
        return float("nan")

    # Observed disagreement D_o
    d_o = 0.0
    for c in range(n_vals):
        for k in range(n_vals):
            if c != k:
                d_o += coincidence[c, k] * _ordinal_dist(all_values[c], all_values[k])
    d_o /= n_total

    # Expected disagreement D_e
    d_e = 0.0
    for c in range(n_vals):
        for k in range(n_vals):
            if c != k:
                d_e += n_c[c] * n_c[k] * _ordinal_dist(all_values[c], all_values[k])
    d_e /= (n_total * (n_total - 1))

    if d_e == 0.0:
        return 1.0  # no expected disagreement → perfect agreement

    alpha = 1.0 - d_o / d_e
    return float(alpha)


# ---------------------------------------------------------------------------
# 9. PELT change-point analysis
# ---------------------------------------------------------------------------


def run_pelt_analysis(df: pd.DataFrame, metrics: list[str]) -> dict:
    """Apply PhaseTransitionDetector to each metric to find distributional shifts.

    Values are sorted by profile (A, B, C) so that a change point near the
    profile boundary suggests the profile has a distributional effect.
    """
    PTDetector = _get_pelt_detector()
    detector = PTDetector(min_segment_length=3, penalty_multiplier=1.0)
    results: dict[str, Any] = {}

    for metric in metrics:
        try:
            # Sort by profile so A values come first, then B, then C
            sorted_df = df[["profile", metric]].dropna().sort_values("profile")
            values = sorted_df[metric].tolist()

            if len(values) < 6:
                results[metric] = {"skipped": True, "reason": "insufficient data"}
                continue

            # Track where profile boundaries fall in the sorted array
            profile_counts = sorted_df["profile"].value_counts().sort_index()
            boundaries: dict[str, int] = {}
            running = 0
            for prof in ("A", "B", "C"):
                if prof in profile_counts.index:
                    running += int(profile_counts[prof])
                    boundaries[prof] = running

            detection = detector.detect_transitions(values)

            results[metric] = {
                "change_points": detection.get("change_points", []),
                "n_regimes": detection.get("n_regimes", 0),
                "regimes": detection.get("regimes", []),
                "phase": detection.get("phase", "unknown"),
                "profile_boundaries": boundaries,
                "total_values": len(values),
            }

        except Exception as exc:
            results[metric] = {"skipped": True, "reason": str(exc)}

    return results


# ---------------------------------------------------------------------------
# 9b. Cross-experiment comparison (exp3 vs exp4)
# ---------------------------------------------------------------------------


def cross_experiment_comparison(
    exp3_csv: str, exp4_csv: str, output_dir: str
) -> dict:
    """Compare A-vs-C effect sizes across experiment 3 and experiment 4.

    Loads both CSVs, filters to shared profiles (A, B, C), computes Cohen's d
    for A-vs-C on every metric present in both datasets, and writes a
    comparison JSON plus a text summary.

    Returns a dict with the comparison table.  If *exp3_csv* does not exist
    the function logs a warning and returns an empty dict.
    """
    logger = logging.getLogger("analyze_stats.cross_experiment")

    exp3_path = Path(exp3_csv)
    exp4_path = Path(exp4_csv)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    if not exp3_path.exists():
        logger.warning(
            "Exp3 CSV not found at %s — skipping cross-experiment comparison.",
            exp3_path,
        )
        return {}

    df3 = load_metrics(exp3_path)
    df4 = load_metrics(exp4_path)

    # Filter to shared profiles A, B, C
    shared_profiles = {"A", "B", "C"}
    df3 = df3[df3["profile"].isin(shared_profiles)]
    df4 = df4[df4["profile"].isin(shared_profiles)]

    metrics3 = set(get_metric_columns(df3))
    metrics4 = set(get_metric_columns(df4))
    shared_metrics = sorted(metrics3 & metrics4)

    if not shared_metrics:
        logger.warning("No shared metrics between exp3 and exp4.")
        return {}

    comparison_rows: list[dict] = []
    summary_lines: list[str] = [
        "CROSS-EXPERIMENT COMPARISON: Exp3 vs Exp4",
        "=" * 60,
        "",
        f"Shared metrics analyzed: {len(shared_metrics)}",
        "",
        f"{'Metric':<30} {'d_exp3':>10} {'d_exp4':>10} {'Delta':>10}  Note",
        "-" * 80,
    ]

    for metric in shared_metrics:
        a3 = df3.loc[df3["profile"] == "A", metric].dropna()
        c3 = df3.loc[df3["profile"] == "C", metric].dropna()
        a4 = df4.loc[df4["profile"] == "A", metric].dropna()
        c4 = df4.loc[df4["profile"] == "C", metric].dropna()

        d3 = compute_cohens_d(a3, c3)
        d4 = compute_cohens_d(a4, c4)
        delta = d4 - d3

        # Flag direction changes or large magnitude shifts
        note = ""
        if d3 != 0.0 and d4 != 0.0 and (d3 > 0) != (d4 > 0):
            note = "DIRECTION REVERSED"
        elif abs(delta) > 0.5:
            note = "large magnitude shift"
        elif abs(delta) > 0.2:
            note = "moderate magnitude shift"

        row = {
            "metric": metric,
            "cohens_d_exp3": round(d3, 4),
            "cohens_d_exp4": round(d4, 4),
            "delta": round(delta, 4),
            "interp_exp3": _interpret_cohens_d(d3),
            "interp_exp4": _interpret_cohens_d(d4),
            "note": note,
        }
        comparison_rows.append(row)

        summary_lines.append(
            f"{metric:<30} {d3:>10.4f} {d4:>10.4f} {delta:>10.4f}  {note}"
        )

    # Direction-reversed metrics
    reversed_metrics = [r for r in comparison_rows if r["note"] == "DIRECTION REVERSED"]
    summary_lines.append("")
    if reversed_metrics:
        summary_lines.append(
            f"WARNING: {len(reversed_metrics)} metric(s) changed effect direction:"
        )
        for r in reversed_metrics:
            summary_lines.append(f"  - {r['metric']}: d={r['cohens_d_exp3']:.3f} -> {r['cohens_d_exp4']:.3f}")
    else:
        summary_lines.append("No metrics changed A-vs-C effect direction between experiments.")

    result = {
        "comparison": comparison_rows,
        "n_shared_metrics": len(shared_metrics),
        "n_direction_changes": len(reversed_metrics),
    }

    save_json(result, out_path / "cross_experiment_comparison.json")
    logger.info("Saved cross_experiment_comparison.json")

    summary_text = "\n".join(summary_lines)
    (out_path / "cross_experiment_summary.txt").write_text(summary_text, encoding="utf-8")
    logger.info("Saved cross_experiment_summary.txt")

    return result


# ---------------------------------------------------------------------------
# 9c. Axis correlation: code composite vs design composite per profile
# ---------------------------------------------------------------------------


CODE_METRICS = [
    "component_count",
    "hook_count",
    "lines_of_code",
    "import_count",
    "prop_interface_count",
]

DESIGN_METRICS = [
    "visual_sophistication",
    "component_architecture",
    "design_intentionality",
    "taste_signal",
]


def compute_axis_correlation(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Compute Pearson r between z-scored code and design composites per profile.

    For each profile present in the data, z-scores each code metric and each
    design metric across the full dataset, computes per-row composites (mean
    of z-scored code metrics, mean of z-scored design metrics), then computes
    Pearson r between the two composites within that profile.

    Returns:
        ``{profile: {"r": float, "p": float, "n": int}}``
        Empty dict if design metrics are not present in the data.
    """
    # Check that at least one design metric is present
    available_design = [m for m in DESIGN_METRICS if m in df.columns]
    available_code = [m for m in CODE_METRICS if m in df.columns]

    if not available_design or not available_code:
        return {}

    work = df.copy()

    # Z-score each metric across the full dataset
    for col in available_code + available_design:
        col_vals = work[col].astype(float)
        mu = col_vals.mean()
        sigma = col_vals.std()
        if sigma == 0 or np.isnan(sigma):
            work[f"z_{col}"] = 0.0
        else:
            work[f"z_{col}"] = (col_vals - mu) / sigma

    # Composite scores per row
    z_code_cols = [f"z_{c}" for c in available_code]
    z_design_cols = [f"z_{c}" for c in available_design]

    work["code_composite"] = work[z_code_cols].mean(axis=1)
    work["design_composite"] = work[z_design_cols].mean(axis=1)

    results: dict[str, dict[str, float]] = {}

    for profile in sorted(work["profile"].dropna().unique()):
        subset = work.loc[work["profile"] == profile, ["code_composite", "design_composite"]].dropna()
        n = len(subset)
        if n < 3:
            continue
        r_val, p_val = pearsonr(subset["code_composite"], subset["design_composite"])
        results[profile] = {
            "r": round(float(r_val), 4),
            "p": round(float(p_val), 6),
            "n": n,
        }

    return results


# ---------------------------------------------------------------------------
# 9d. Profile x Axis interaction (two-way ANOVA on z-scored composites)
# ---------------------------------------------------------------------------


def profile_axis_interaction(df: pd.DataFrame) -> dict[str, float]:
    """Test whether profiles differ in their code-vs-design emphasis.

    For each response, computes z-scored code composite and z-scored design
    composite, reshapes into long format (profile, axis, z_score), and runs
    two-way ANOVA with profile and axis as factors, testing the interaction
    term.

    Returns:
        ``{"interaction_F": float, "interaction_p": float, "partial_eta_sq": float}``
        Empty dict if design metrics are not present or the model fails.
    """
    available_design = [m for m in DESIGN_METRICS if m in df.columns]
    available_code = [m for m in CODE_METRICS if m in df.columns]

    if not available_design or not available_code:
        return {}

    work = df.copy()

    # Z-score each metric across the full dataset
    for col in available_code + available_design:
        col_vals = work[col].astype(float)
        mu = col_vals.mean()
        sigma = col_vals.std()
        if sigma == 0 or np.isnan(sigma):
            work[f"z_{col}"] = 0.0
        else:
            work[f"z_{col}"] = (col_vals - mu) / sigma

    # Composite scores per row
    z_code_cols = [f"z_{c}" for c in available_code]
    z_design_cols = [f"z_{c}" for c in available_design]

    work["code_composite"] = work[z_code_cols].mean(axis=1)
    work["design_composite"] = work[z_design_cols].mean(axis=1)

    # Build long-format dataframe: profile, axis, z_score
    rows: list[dict[str, Any]] = []
    for idx, row in work.iterrows():
        prof = row.get("profile")
        if pd.isna(prof):
            continue
        code_val = row["code_composite"]
        design_val = row["design_composite"]
        if not np.isnan(code_val):
            rows.append({"profile": prof, "axis": "code", "z_score": code_val})
        if not np.isnan(design_val):
            rows.append({"profile": prof, "axis": "design", "z_score": design_val})

    if len(rows) < 6:
        return {}

    long_df = pd.DataFrame(rows)

    try:
        model = ols("z_score ~ C(profile) * C(axis)", data=long_df).fit()
        table = anova_lm(model, typ=2)

        interaction_key = "C(profile):C(axis)"
        if interaction_key not in table.index:
            return {}

        inter_F = float(table.loc[interaction_key, "F"])
        inter_p = float(table.loc[interaction_key, "PR(>F)"])

        # Partial eta squared = SS_interaction / (SS_interaction + SS_residual)
        ss_inter = float(table.loc[interaction_key, "sum_sq"])
        ss_resid = float(table.loc["Residual", "sum_sq"])
        partial_eta_sq = ss_inter / (ss_inter + ss_resid) if (ss_inter + ss_resid) > 0 else 0.0

        return {
            "interaction_F": round(inter_F, 4),
            "interaction_p": round(inter_p, 6),
            "partial_eta_sq": round(partial_eta_sq, 4),
        }

    except Exception:
        return {}


# ---------------------------------------------------------------------------
# 10. Full analysis pipeline
# ---------------------------------------------------------------------------


def _build_summary_report(
    anova_results: list[dict],
    two_way_results: list[dict],
    effect_sizes: list[dict],
    mann_whitney_results: list[dict],
    kruskal_results: list[dict],
    pelt_results: dict,
    df: pd.DataFrame,
    planned_contrasts: list[dict] | None = None,
) -> str:
    """Build a thorough, human-readable summary report."""
    lines: list[str] = []
    sep = "=" * 72

    lines.append(sep)
    lines.append("PROFILE BIAS EXPERIMENT — STATISTICAL ANALYSIS REPORT")
    lines.append(sep)
    lines.append("")

    # --- Data overview ---
    n_total = len(df)
    profile_counts = df["profile"].value_counts().sort_index()
    model_counts = df["model_short"].value_counts().sort_index() if "model_short" in df.columns else pd.Series()

    lines.append("DATA OVERVIEW")
    lines.append("-" * 40)
    lines.append(f"  Total observations: {n_total}")
    for prof, cnt in profile_counts.items():
        lines.append(f"  Profile {prof}: {cnt}")
    for model, cnt in model_counts.items():
        lines.append(f"  Model {model}: {cnt}")
    lines.append("")

    # --- Key Findings ---
    lines.append(sep)
    lines.append("KEY FINDINGS")
    lines.append(sep)
    lines.append("")

    # Significant ANOVA results
    sig_anova = [r for r in anova_results if r and r.get("significant")]
    if sig_anova:
        lines.append(f"  * {len(sig_anova)} metric(s) show SIGNIFICANT profile effects (one-way ANOVA, p < 0.05):")
        for r in sorted(sig_anova, key=lambda x: x["p_value"]):
            lines.append(f"    - {r['metric']}: F={r['F_statistic']:.3f}, p={r['p_value']:.4f}")
    else:
        lines.append("  * No metrics show significant profile effects at p < 0.05 (one-way ANOVA).")
    lines.append("")

    # Largest effect sizes
    all_effects: list[tuple[str, str, float, str]] = []
    for es in effect_sizes:
        if not es:
            continue
        for pair_key, pair_data in es.get("pairs", {}).items():
            all_effects.append((
                es["metric"],
                pair_key,
                pair_data["abs_d"],
                pair_data["interpretation"],
            ))
    all_effects.sort(key=lambda x: x[2], reverse=True)

    if all_effects:
        lines.append("  * Largest effect sizes (Cohen's d):")
        for metric, pair, d, interp in all_effects[:10]:
            lines.append(f"    - {metric} ({pair}): |d|={d:.3f} ({interp})")
    lines.append("")

    # Model sensitivity comparison (Haiku vs Sonnet)
    lines.append("  * Model sensitivity to profile priming:")
    if "model_short" in df.columns:
        models = df["model_short"].unique()
        for model in sorted(models):
            model_df = df[df["model_short"] == model]
            sig_count = 0
            metric_cols = get_metric_columns(df)
            for metric in metric_cols:
                result = run_one_way_anova(model_df, metric)
                if result and result.get("significant"):
                    sig_count += 1
            lines.append(f"    - {model}: {sig_count}/{len(metric_cols)} metrics show significant profile effect")
    lines.append("")

    # Interaction effects
    sig_interactions = [
        r for r in two_way_results
        if r and r.get("interaction_p") is not None and r["interaction_p"] < 0.05
    ]
    if sig_interactions:
        lines.append(f"  * {len(sig_interactions)} metric(s) show significant profile x model INTERACTION:")
        for r in sorted(sig_interactions, key=lambda x: x["interaction_p"]):
            lines.append(f"    - {r['metric']}: F={r['interaction_F']:.3f}, p={r['interaction_p']:.4f}")
    else:
        lines.append("  * No significant profile x model interaction effects detected.")
    lines.append("")

    # PELT change-point alignment
    pelt_aligned = []
    for metric, data in pelt_results.items():
        if isinstance(data, dict) and not data.get("skipped"):
            cps = data.get("change_points", [])
            boundaries = data.get("profile_boundaries", {})
            total = data.get("total_values", 0)
            for cp in cps:
                for prof, boundary in boundaries.items():
                    if total > 0 and abs(cp - boundary) <= max(2, total * 0.1):
                        pelt_aligned.append((metric, cp, prof, boundary))

    if pelt_aligned:
        lines.append(f"  * PELT change-point detection found {len(pelt_aligned)} shift(s) near profile boundaries:")
        for metric, cp, prof, boundary in pelt_aligned:
            lines.append(f"    - {metric}: change at index {cp} (near profile {prof} boundary at {boundary})")
    else:
        lines.append("  * No PELT change points aligned with profile boundaries.")
    lines.append("")

    # --- Planned Contrasts (Experiment 5) ---
    if planned_contrasts:
        lines.append(sep)
        lines.append("PLANNED CONTRASTS (Experiment 5)")
        lines.append(sep)
        lines.append("")
        header_pc = (
            f"{'Metric':<25} {'Contrast':<30} {'U':>8} {'p':>10} {'r_rb':>8} {'d':>8} {'Sig?':>6}"
        )
        lines.append(header_pc)
        lines.append("-" * 100)
        for pc in planned_contrasts:
            metric_name = pc.get("metric", "?")
            for c in pc.get("contrasts", []):
                if c.get("skipped"):
                    lines.append(f"{metric_name:<25} {c['label']:<30} {'skipped':>8}")
                    continue
                sig_marker = "*" if c.get("significant") else ""
                lines.append(
                    f"{metric_name:<25} {c['label']:<30} "
                    f"{c['U_statistic']:>8.1f} {c['p_value']:>10.4f} "
                    f"{c['rank_biserial_r']:>8.3f} {c['cohens_d']:>8.3f} {sig_marker:>6}"
                )
            # Only print metric name on first row for readability
            metric_name = ""
        lines.append("")

    # =====================================================================
    # DETAILED TABLES
    # =====================================================================
    lines.append(sep)
    lines.append("DETAILED RESULTS")
    lines.append(sep)
    lines.append("")

    # --- One-Way ANOVA Table ---
    lines.append("ONE-WAY ANOVA (by Profile)")
    lines.append("-" * 72)
    header = f"{'Metric':<30} {'F':>8} {'p':>10} {'Sig?':>6}  {'Mean_A':>8} {'Mean_B':>8} {'Mean_C':>8}"
    lines.append(header)
    lines.append("-" * 72)
    for r in anova_results:
        if r is None:
            continue
        sig_marker = "***" if r["p_value"] < 0.001 else ("**" if r["p_value"] < 0.01 else ("*" if r["p_value"] < 0.05 else ""))
        means = r["group_means"]
        lines.append(
            f"{r['metric']:<30} {r['F_statistic']:>8.3f} {r['p_value']:>10.4f} {sig_marker:>6}"
            f"  {means.get('A', float('nan')):>8.3f} {means.get('B', float('nan')):>8.3f} {means.get('C', float('nan')):>8.3f}"
        )
    lines.append("")

    # --- Two-Way ANOVA Table ---
    lines.append("TWO-WAY ANOVA (Profile x Model)")
    lines.append("-" * 90)
    header2 = (
        f"{'Metric':<25} {'Prof_F':>8} {'Prof_p':>9} {'Model_F':>8} {'Model_p':>9}"
        f" {'Inter_F':>8} {'Inter_p':>9}"
    )
    lines.append(header2)
    lines.append("-" * 90)
    for r in two_way_results:
        if r is None:
            continue
        pf = r.get("profile_F")
        pp = r.get("profile_p")
        mf = r.get("model_F")
        mp = r.get("model_p")
        inf = r.get("interaction_F")
        inp = r.get("interaction_p")

        col_pf = f"{pf:>8.3f}" if pf is not None else f"{'N/A':>8}"
        col_pp = f"{pp:>9.4f}" if pp is not None else f"{'N/A':>9}"
        col_mf = f"{mf:>8.3f}" if mf is not None else f"{'N/A':>8}"
        col_mp = f"{mp:>9.4f}" if mp is not None else f"{'N/A':>9}"
        col_inf = f"{inf:>8.3f}" if inf is not None else f"{'N/A':>8}"
        col_inp = f"{inp:>9.4f}" if inp is not None else f"{'N/A':>9}"

        lines.append(
            f"{r['metric']:<25} {col_pf} {col_pp} {col_mf} {col_mp} {col_inf} {col_inp}"
        )
    lines.append("")

    # --- Effect Sizes Table ---
    lines.append("EFFECT SIZES (Cohen's d)")
    lines.append("-" * 80)
    header3 = f"{'Metric':<25} {'A_vs_B':>10} {'A_vs_C':>10} {'B_vs_C':>10}  {'Largest Pair':<15} {'Interp':<12}"
    lines.append(header3)
    lines.append("-" * 80)
    for es in effect_sizes:
        if not es:
            continue
        pairs = es.get("pairs", {})
        ab = pairs.get("A_vs_B", {}).get("cohens_d", 0)
        ac = pairs.get("A_vs_C", {}).get("cohens_d", 0)
        bc = pairs.get("B_vs_C", {}).get("cohens_d", 0)
        # Find largest
        largest_pair = max(pairs.items(), key=lambda x: x[1].get("abs_d", 0))
        lines.append(
            f"{es['metric']:<25} {ab:>10.3f} {ac:>10.3f} {bc:>10.3f}"
            f"  {largest_pair[0]:<15} {largest_pair[1].get('interpretation', 'N/A'):<12}"
        )
    lines.append("")

    # --- Mann-Whitney U Table ---
    lines.append("MANN-WHITNEY U (Bonferroni-corrected)")
    lines.append("-" * 80)
    header4 = f"{'Metric':<25} {'A_vs_B p':>10} {'A_vs_C p':>10} {'B_vs_C p':>10}  {'Any Sig?':>8}"
    lines.append(header4)
    lines.append("-" * 80)
    for mw in mann_whitney_results:
        if not mw:
            continue
        pairs = mw.get("pairs", {})
        p_ab = pairs.get("A_vs_B", {}).get("p_value_corrected")
        p_ac = pairs.get("A_vs_C", {}).get("p_value_corrected")
        p_bc = pairs.get("B_vs_C", {}).get("p_value_corrected")
        any_sig = any(
            pairs.get(k, {}).get("significant", False)
            for k in ("A_vs_B", "A_vs_C", "B_vs_C")
        )

        col_ab = f"{p_ab:>10.4f}" if p_ab is not None else f"{'N/A':>10}"
        col_ac = f"{p_ac:>10.4f}" if p_ac is not None else f"{'N/A':>10}"
        col_bc = f"{p_bc:>10.4f}" if p_bc is not None else f"{'N/A':>10}"
        col_sig = f"{'YES' if any_sig else 'no':>8}"

        lines.append(
            f"{mw['metric']:<25} {col_ab} {col_ac} {col_bc}  {col_sig}"
        )
    lines.append("")

    # --- Kruskal-Wallis Table ---
    lines.append("KRUSKAL-WALLIS H-TEST")
    lines.append("-" * 50)
    header5 = f"{'Metric':<30} {'H':>8} {'p':>10}"
    lines.append(header5)
    lines.append("-" * 50)
    for kr in kruskal_results:
        if kr is None:
            continue
        lines.append(f"{kr['metric']:<30} {kr['H_statistic']:>8.3f} {kr['p_value']:>10.4f}")
    lines.append("")

    # --- Per-Task Breakdown ---
    lines.append(sep)
    lines.append("PER-TASK BREAKDOWN OF SIGNIFICANT EFFECTS")
    lines.append(sep)
    lines.append("")

    if "task_id" in df.columns:
        tasks = sorted(df["task_id"].unique())
        metric_cols = get_metric_columns(df)
        for task in tasks:
            task_df = df[df["task_id"] == task]
            sig_metrics: list[str] = []
            for metric in metric_cols:
                result = run_one_way_anova(task_df, metric)
                if result and result.get("significant"):
                    sig_metrics.append(f"{metric} (p={result['p_value']:.4f})")
            lines.append(f"  Task: {task}")
            if sig_metrics:
                for sm_entry in sig_metrics:
                    lines.append(f"    - {sm_entry}")
            else:
                lines.append("    (no significant profile effects)")
            lines.append("")

    lines.append(sep)
    lines.append("END OF REPORT")
    lines.append(sep)

    return "\n".join(lines)


def run_full_analysis(
    csv_path: str | Path,
    output_dir: str | Path,
    exp3_csv_path: str | Path | None = None,
) -> dict:
    """Run all statistical tests on all metrics and save results.

    Outputs:
        - anova_results.json
        - effect_sizes.json
        - interaction_effects.json
        - pelt_results.json
        - planned_contrasts.json (if enough profiles present)
        - axis_correlation.json (exp5: code vs design composite per profile)
        - axis_interaction.json (exp5: profile x axis two-way ANOVA)
        - summary_report.txt
        - cross_experiment_comparison.json (if *exp3_csv_path* is provided)

    Args:
        csv_path: Path to this experiment's metrics CSV.
        output_dir: Directory to write result files.
        exp3_csv_path: Optional path to Experiment 3 metrics CSV for
            cross-experiment effect-size comparison.

    Returns a summary dict of what was produced.
    """
    csv_path = Path(csv_path)
    output_dir = Path(output_dir)
    ensure_dirs(output_dir)

    logger = setup_logging(output_dir, name="analyze_stats")
    logger.info("Loading metrics from %s", csv_path)

    df = load_metrics(csv_path)
    metrics = get_metric_columns(df)
    logger.info("Found %d metrics: %s", len(metrics), metrics)

    # -- One-way ANOVA --
    logger.info("Running one-way ANOVA...")
    anova_one_way: list[dict | None] = []
    for metric in metrics:
        anova_one_way.append(run_one_way_anova(df, metric))

    # -- Two-way ANOVA --
    logger.info("Running two-way ANOVA (profile x model)...")
    anova_two_way: list[dict | None] = []
    for metric in metrics:
        anova_two_way.append(run_two_way_anova(df, metric))

    # Combine into single ANOVA output
    anova_combined = {
        "one_way": [r for r in anova_one_way if r is not None],
        "two_way": [r for r in anova_two_way if r is not None],
    }
    save_json(anova_combined, output_dir / "anova_results.json")
    logger.info("Saved anova_results.json")

    # -- Effect sizes --
    logger.info("Computing effect sizes (Cohen's d)...")
    effect_size_results: list[dict] = []
    for metric in metrics:
        effect_size_results.append(compute_effect_sizes(df, metric))
    save_json(effect_size_results, output_dir / "effect_sizes.json")
    logger.info("Saved effect_sizes.json")

    # -- Mann-Whitney U --
    logger.info("Running Mann-Whitney U tests...")
    mann_whitney_results: list[dict] = []
    for metric in metrics:
        mann_whitney_results.append(run_mann_whitney(df, metric))

    # -- Kruskal-Wallis --
    logger.info("Running Kruskal-Wallis H-tests...")
    kruskal_results: list[dict | None] = []
    for metric in metrics:
        kruskal_results.append(run_kruskal_wallis(df, metric))

    # -- Planned contrasts (Experiment 5 design) --
    profiles_present = set(df["profile"].unique())
    planned_contrast_results: list[dict] = []
    # Run planned contrasts if we have at least F, G, B (the key exp5 profiles)
    if {"F", "G", "B"}.issubset(profiles_present):
        logger.info("Running planned contrasts (exp5 design)...")
        for metric in metrics:
            planned_contrast_results.append(compute_planned_contrasts(df, metric))
        save_json(planned_contrast_results, output_dir / "planned_contrasts.json")
        logger.info("Saved planned_contrasts.json")

    # -- Interaction effects (extracted from two-way ANOVA) --
    interaction_results = [
        r for r in anova_two_way
        if r is not None and r.get("interaction_p") is not None
    ]
    save_json(interaction_results, output_dir / "interaction_effects.json")
    logger.info("Saved interaction_effects.json")

    # -- PELT change-point detection --
    logger.info("Running PELT change-point analysis...")
    pelt_results = run_pelt_analysis(df, metrics)
    save_json(pelt_results, output_dir / "pelt_results.json")
    logger.info("Saved pelt_results.json")

    # -- Axis correlation (exp5: code vs design composite per profile) --
    logger.info("Computing axis correlation (code vs design composites)...")
    axis_corr_results = compute_axis_correlation(df)
    save_json(axis_corr_results, output_dir / "axis_correlation.json")
    logger.info("Saved axis_correlation.json")

    # -- Profile x Axis interaction (exp5) --
    logger.info("Computing profile x axis interaction...")
    axis_inter_results = profile_axis_interaction(df)
    save_json(axis_inter_results, output_dir / "axis_interaction.json")
    logger.info("Saved axis_interaction.json")

    # -- Cross-experiment comparison --
    cross_exp_result: dict = {}
    if exp3_csv_path is not None:
        logger.info("Running cross-experiment comparison (exp3 vs exp4)...")
        cross_exp_result = cross_experiment_comparison(
            exp3_csv=str(exp3_csv_path),
            exp4_csv=str(csv_path),
            output_dir=str(output_dir),
        )

    # -- Summary report --
    logger.info("Building summary report...")
    report = _build_summary_report(
        anova_results=[r for r in anova_one_way if r is not None],
        two_way_results=[r for r in anova_two_way if r is not None],
        effect_sizes=effect_size_results,
        mann_whitney_results=mann_whitney_results,
        kruskal_results=[r for r in kruskal_results if r is not None],
        pelt_results=pelt_results,
        df=df,
        planned_contrasts=planned_contrast_results if planned_contrast_results else None,
    )

    report_path = output_dir / "summary_report.txt"
    report_path.write_text(report, encoding="utf-8")
    logger.info("Saved summary_report.txt (%d lines)", report.count("\n") + 1)

    summary = {
        "csv_path": str(csv_path),
        "output_dir": str(output_dir),
        "n_observations": len(df),
        "n_metrics": len(metrics),
        "metrics": metrics,
        "significant_anova_count": sum(1 for r in anova_one_way if r and r.get("significant")),
        "significant_interaction_count": len([
            r for r in anova_two_way
            if r and r.get("interaction_p") is not None and r["interaction_p"] < 0.05
        ]),
        "files_written": [
            str(output_dir / "anova_results.json"),
            str(output_dir / "effect_sizes.json"),
            str(output_dir / "interaction_effects.json"),
            str(output_dir / "pelt_results.json"),
            str(output_dir / "axis_correlation.json"),
            str(output_dir / "axis_interaction.json"),
            str(output_dir / "summary_report.txt"),
        ]
        + ([str(output_dir / "planned_contrasts.json")] if planned_contrast_results else [])
        + ([str(output_dir / "cross_experiment_comparison.json")] if cross_exp_result else []),
    }

    logger.info(
        "Analysis complete: %d/%d metrics significant (one-way ANOVA)",
        summary["significant_anova_count"],
        len(metrics),
    )

    return summary


# ---------------------------------------------------------------------------
# 11. CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI: python -m src.analyze_stats --metrics <csv> --output <dir>"""
    parser = argparse.ArgumentParser(
        description="Run statistical analysis on profile-bias experiment metrics.",
    )
    parser.add_argument(
        "--metrics",
        type=str,
        default="results/metrics/metrics_table.csv",
        help="Path to the experiment metrics CSV file.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="analysis/",
        help="Output directory for analysis results.",
    )
    parser.add_argument(
        "--exp3-csv",
        type=str,
        default=None,
        help="Optional path to Experiment 3 metrics CSV for cross-experiment comparison.",
    )
    args = parser.parse_args()

    summary = run_full_analysis(args.metrics, args.output, exp3_csv_path=args.exp3_csv)

    print(f"\nAnalysis complete.")
    print(f"  Observations: {summary['n_observations']}")
    print(f"  Metrics analyzed: {summary['n_metrics']}")
    print(f"  Significant (ANOVA): {summary['significant_anova_count']}/{summary['n_metrics']}")
    print(f"  Significant interactions: {summary['significant_interaction_count']}")
    print(f"\nResults written to: {summary['output_dir']}")
    for f in summary["files_written"]:
        print(f"    {f}")


if __name__ == "__main__":
    main()
