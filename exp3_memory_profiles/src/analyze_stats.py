"""Statistical analysis module for the profile-bias experiment.

Runs one-way ANOVA, two-way ANOVA, Mann-Whitney U, Kruskal-Wallis,
Cohen's d effect sizes, and PELT change-point detection on experiment
metrics. Produces JSON result files and a human-readable summary report.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import f_oneway, kruskal, mannwhitneyu, shapiro
import statsmodels.api as sm
from statsmodels.formula.api import ols
from statsmodels.stats.anova import anova_lm

from .utils import save_json, setup_logging, ensure_dirs

# Lazy import of PhaseTransitionDetector to avoid pulling in Flask
_PhaseTransitionDetector = None

def _get_pelt_detector():
    global _PhaseTransitionDetector
    if _PhaseTransitionDetector is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "statistical_detectors",
            "/Users/admin/miroshark/backend/app/services/statistical_detectors.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _PhaseTransitionDetector = mod.PhaseTransitionDetector
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
# 7b. Planned contrasts (Experiment 3)
# ---------------------------------------------------------------------------


def compute_planned_contrasts(df: pd.DataFrame, metric: str) -> dict:
    """Compute 4 planned contrasts for the 5-profile Experiment 3 design.

    Contrasts:
        1. A vs C  — non-technical sophistication effect
        2. D vs E  — technical sophistication effect
        3. B vs {A,C,D,E} mean — profile existence effect
        4. {A,D} vs {C,E} — high vs low collapsed across domain

    Each contrast uses Mann-Whitney U with rank-biserial r as effect size.
    """
    groups: dict[str, pd.Series] = {}
    for profile in ("A", "B", "C", "D", "E"):
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

    # Contrast 1: A vs C (non-technical sophistication)
    c1 = _contrast(groups["A"], groups["C"], "A_vs_C (non-tech sophistication)")

    # Contrast 2: D vs E (technical sophistication)
    c2 = _contrast(groups["D"], groups["E"], "D_vs_E (tech sophistication)")

    # Contrast 3: B vs {A,C,D,E} mean (profile existence effect)
    non_control = pd.concat([groups["A"], groups["C"], groups["D"], groups["E"]])
    c3 = _contrast(groups["B"], non_control, "B_vs_ACDE (profile existence)")

    # Contrast 4: {A,D} vs {C,E} (high vs low collapsed)
    high_soph = pd.concat([groups["A"], groups["D"]])
    low_soph = pd.concat([groups["C"], groups["E"]])
    c4 = _contrast(high_soph, low_soph, "AD_vs_CE (high vs low)")

    return {
        "metric": metric,
        "contrasts": [c1, c2, c3, c4],
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

    # --- Planned Contrasts (Experiment 3) ---
    if planned_contrasts:
        lines.append(sep)
        lines.append("PLANNED CONTRASTS (Experiment 3)")
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


def run_full_analysis(csv_path: str | Path, output_dir: str | Path) -> dict:
    """Run all statistical tests on all metrics and save results.

    Outputs:
        - anova_results.json
        - effect_sizes.json
        - interaction_effects.json
        - pelt_results.json
        - summary_report.txt

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

    # -- Planned contrasts (Experiment 3, 5 profiles) --
    profiles_present = set(df["profile"].unique())
    planned_contrast_results: list[dict] = []
    if {"A", "B", "C", "D", "E"}.issubset(profiles_present):
        logger.info("Running planned contrasts (5-profile design)...")
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
            str(output_dir / "summary_report.txt"),
        ] + ([str(output_dir / "planned_contrasts.json")] if planned_contrast_results else []),
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
    args = parser.parse_args()

    summary = run_full_analysis(args.metrics, args.output)

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
