"""Visualization module for profile-bias experiment results.

Generates violin plots, grouped bar charts, heatmaps, interaction plots,
task breakdowns, radar charts, and auto-selected top-metric plots from the
collected metrics and analysis data.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

from .utils import load_json, setup_logging, ensure_dirs

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROFILE_COLORS: dict[str, str] = {
    "A": "#2196F3",   # blue — high sophistication non-technical
    "B": "#9E9E9E",   # gray — control
    "C": "#FF5722",   # orange — low sophistication non-technical
    "D": "#4CAF50",   # green — high sophistication technical
    "E": "#9C27B0",   # purple — low sophistication technical
}

PROFILE_LABELS: dict[str, str] = {
    "A": "High Soph (non-tech)",
    "B": "Control",
    "C": "Low Soph (non-tech)",
    "D": "High Soph (technical)",
    "E": "Low Soph (technical)",
}

_logger = logging.getLogger("experiment.visualize")

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _profile_palette() -> list[str]:
    """Return the color palette in profile order (A, B, C)."""
    return [PROFILE_COLORS["A"], PROFILE_COLORS["B"], PROFILE_COLORS["C"]]


def _save_and_close(fig: plt.Figure, path: str | Path) -> str:
    """Save *fig* to *path* at 150 dpi with tight layout, then close it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(path)


# ---------------------------------------------------------------------------
# 1. Violin plot
# ---------------------------------------------------------------------------


def plot_violin(df: pd.DataFrame, metric: str, output_dir: str | Path) -> str:
    """Violin plot of *metric* across the three profiles.

    Overlays individual data points as a strip plot.  Saves to
    ``<output_dir>/violin_<metric>.png`` and returns the path.
    """
    output_dir = Path(output_dir)
    ensure_dirs(output_dir)

    fig, ax = plt.subplots(figsize=(10, 6))
    order = ["A", "B", "C"]
    palette = _profile_palette()

    sns.violinplot(
        data=df,
        x="profile",
        y=metric,
        hue="profile",
        order=order,
        hue_order=order,
        palette=palette,
        inner=None,
        linewidth=1.2,
        legend=False,
        ax=ax,
    )
    sns.stripplot(
        data=df,
        x="profile",
        y=metric,
        order=order,
        color="black",
        alpha=0.4,
        size=4,
        jitter=True,
        ax=ax,
    )

    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([PROFILE_LABELS[p] for p in order])
    ax.set_title(metric, fontsize=14)
    ax.set_xlabel("")
    ax.set_ylabel(metric)
    ax.grid(axis="y", alpha=0.3)

    path = output_dir / f"violin_{metric}.png"
    return _save_and_close(fig, path)


# ---------------------------------------------------------------------------
# 2. Grouped bar chart (profile x model)
# ---------------------------------------------------------------------------


def plot_grouped_bars(df: pd.DataFrame, metric: str, output_dir: str | Path) -> str:
    """Grouped bar chart of *metric*: profile x model.

    Six bars total (3 profiles x 2 models) with standard-deviation error bars.
    Saves to ``<output_dir>/grouped_bars_<metric>.png``.
    """
    output_dir = Path(output_dir)
    ensure_dirs(output_dir)

    profiles = ["A", "B", "C"]
    models = sorted(df["model"].unique())

    grouped = df.groupby(["profile", "model"])[metric].agg(["mean", "std"]).reset_index()

    fig, ax = plt.subplots(figsize=(10, 6))
    n_models = len(models)
    bar_width = 0.35
    x = np.arange(len(profiles))

    for i, model in enumerate(models):
        subset = grouped[grouped["model"] == model].set_index("profile").reindex(profiles)
        offset = (i - (n_models - 1) / 2) * bar_width
        ax.bar(
            x + offset,
            subset["mean"],
            bar_width,
            yerr=subset["std"],
            label=model,
            capsize=4,
            color=[PROFILE_COLORS[p] for p in profiles],
            alpha=0.8 if i == 0 else 0.55,
            edgecolor="black",
            linewidth=0.5,
        )

    ax.set_xticks(x)
    ax.set_xticklabels([PROFILE_LABELS[p] for p in profiles])
    ax.set_ylabel(metric)
    ax.set_title(f"{metric} — Profile x Model", fontsize=14)
    ax.legend(title="Model")
    ax.grid(axis="y", alpha=0.3)

    path = output_dir / f"grouped_bars_{metric}.png"
    return _save_and_close(fig, path)


# ---------------------------------------------------------------------------
# 3. Effect-size heatmap
# ---------------------------------------------------------------------------


def plot_effect_size_heatmap(effect_sizes_path: str | Path, output_dir: str | Path) -> str:
    """Heatmap of Cohen's-d effect sizes.

    Loads ``effect_sizes.json``, arranges metrics on the y-axis and comparison
    pairs (A_vs_B, A_vs_C, B_vs_C) on the x-axis.  Uses the RdBu_r colormap
    centred at 0 with annotated cell values.

    Saves to ``<output_dir>/effect_size_heatmap.png``.
    """
    output_dir = Path(output_dir)
    ensure_dirs(output_dir)

    raw = load_json(effect_sizes_path)

    pairs = ["A_vs_B", "A_vs_C", "B_vs_C"]

    # Support both list-of-dicts (from analyze_stats) and dict-of-dicts formats
    if isinstance(raw, list):
        # Convert list format [{metric, pairs: {A_vs_B: {cohens_d, ...}, ...}}, ...]
        metrics = sorted(entry["metric"] for entry in raw)
        lookup: dict[str, dict[str, float]] = {}
        for entry in raw:
            m = entry["metric"]
            lookup[m] = {}
            for pair, vals in entry.get("pairs", {}).items():
                lookup[m][pair] = vals.get("cohens_d", np.nan)
    else:
        # Legacy dict format {pair: {metric: value, ...}, ...}
        metrics = sorted({m for pair_data in raw.values() for m in pair_data})
        lookup = {}
        for m in metrics:
            lookup[m] = {}
            for pair in pairs:
                lookup[m][pair] = raw.get(pair, {}).get(m, np.nan)

    matrix = np.full((len(metrics), len(pairs)), np.nan)
    for i, m in enumerate(metrics):
        for j, pair in enumerate(pairs):
            matrix[i, j] = lookup.get(m, {}).get(pair, np.nan)

    df_heat = pd.DataFrame(matrix, index=metrics, columns=pairs)

    fig, ax = plt.subplots(figsize=(10, max(6, len(metrics) * 0.45)))
    sns.heatmap(
        df_heat,
        cmap="RdBu_r",
        center=0,
        annot=True,
        fmt=".2f",
        linewidths=0.5,
        ax=ax,
    )
    ax.set_title("Effect Sizes (Cohen's d)", fontsize=14)
    ax.set_ylabel("Metric")
    ax.set_xlabel("Comparison")

    path = output_dir / "effect_size_heatmap.png"
    return _save_and_close(fig, path)


# ---------------------------------------------------------------------------
# 4. Interaction plot (profile x model)
# ---------------------------------------------------------------------------


def plot_interaction(df: pd.DataFrame, metric: str, output_dir: str | Path) -> str:
    """Interaction (line) plot: profile sensitivity across models.

    X-axis = profile (A, B, C), separate lines for each model, error bars =
    SEM.  Saves to ``<output_dir>/interaction_<metric>.png``.
    """
    output_dir = Path(output_dir)
    ensure_dirs(output_dir)

    profiles = ["A", "B", "C"]
    models = sorted(df["model"].unique())

    fig, ax = plt.subplots(figsize=(10, 6))

    for model in models:
        sub = df[df["model"] == model]
        means = sub.groupby("profile")[metric].mean().reindex(profiles)
        sems = sub.groupby("profile")[metric].sem().reindex(profiles)
        ax.errorbar(
            profiles,
            means,
            yerr=sems,
            marker="o",
            capsize=5,
            linewidth=2,
            label=model,
        )

    ax.set_xticks(range(len(profiles)))
    ax.set_xticklabels([PROFILE_LABELS[p] for p in profiles])
    ax.set_xlabel("")
    ax.set_ylabel(metric)
    ax.set_title(f"{metric} — Interaction (Profile x Model)", fontsize=14)
    ax.legend(title="Model")
    ax.grid(alpha=0.3)

    path = output_dir / f"interaction_{metric}.png"
    return _save_and_close(fig, path)


# ---------------------------------------------------------------------------
# 5. Task breakdown
# ---------------------------------------------------------------------------


def plot_task_breakdown(df: pd.DataFrame, metric: str, output_dir: str | Path) -> str:
    """Grouped bar chart: x = task_id, grouped by profile.

    Highlights which individual tasks exhibit the largest profile effects.
    Saves to ``<output_dir>/task_breakdown_<metric>.png``.
    """
    output_dir = Path(output_dir)
    ensure_dirs(output_dir)

    profiles = ["A", "B", "C"]
    tasks = sorted(df["task_id"].unique())

    grouped = df.groupby(["task_id", "profile"])[metric].mean().reset_index()

    fig, ax = plt.subplots(figsize=(max(10, len(tasks) * 1.2), 6))
    bar_width = 0.25
    x = np.arange(len(tasks))

    for i, profile in enumerate(profiles):
        subset = grouped[grouped["profile"] == profile].set_index("task_id").reindex(tasks)
        offset = (i - 1) * bar_width
        ax.bar(
            x + offset,
            subset[metric],
            bar_width,
            label=PROFILE_LABELS[profile],
            color=PROFILE_COLORS[profile],
            edgecolor="black",
            linewidth=0.5,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(tasks, rotation=45, ha="right")
    ax.set_xlabel("Task")
    ax.set_ylabel(metric)
    ax.set_title(f"{metric} — Breakdown by Task", fontsize=14)
    ax.legend(title="Profile")
    ax.grid(axis="y", alpha=0.3)

    path = output_dir / f"task_breakdown_{metric}.png"
    return _save_and_close(fig, path)


# ---------------------------------------------------------------------------
# 6. Composite radar / spider chart
# ---------------------------------------------------------------------------

_COMPOSITE_SCORES = [
    "architectural_sophistication",
    "defensive_coding",
    "idiomatic_density",
    "verbosity_ratio",
]


def plot_composite_radar(df: pd.DataFrame, output_dir: str | Path) -> str:
    """Radar (spider) chart of the four composite scores per profile.

    Saves to ``<output_dir>/composite_radar.png``.
    """
    output_dir = Path(output_dir)
    ensure_dirs(output_dir)

    profiles = ["A", "B", "C"]
    categories = _COMPOSITE_SCORES
    n_cats = len(categories)

    # Compute angles for the radar chart.
    angles = np.linspace(0, 2 * np.pi, n_cats, endpoint=False).tolist()
    angles += angles[:1]  # close the polygon

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw={"projection": "polar"})

    for profile in profiles:
        sub = df[df["profile"] == profile]
        values = [sub[cat].mean() for cat in categories]
        values += values[:1]  # close the polygon
        ax.plot(
            angles,
            values,
            linewidth=2,
            label=PROFILE_LABELS[profile],
            color=PROFILE_COLORS[profile],
        )
        ax.fill(angles, values, alpha=0.15, color=PROFILE_COLORS[profile])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=10)
    ax.set_title("Composite Scores by Profile", fontsize=14, y=1.08)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1))
    ax.grid(alpha=0.3)

    path = output_dir / "composite_radar.png"
    return _save_and_close(fig, path)


# ---------------------------------------------------------------------------
# 7. Top metrics (auto-selected by effect size)
# ---------------------------------------------------------------------------


def plot_top_metrics(
    df: pd.DataFrame,
    effect_sizes_path: str | Path,
    output_dir: str | Path,
) -> list[str]:
    """Auto-select the top 6 metrics by largest |A_vs_C| effect size.

    Generates a violin plot for each.  Returns the list of saved file paths.
    """
    raw = load_json(effect_sizes_path)

    # Support both list-of-dicts and dict-of-dicts formats
    if isinstance(raw, list):
        a_vs_c: dict[str, float] = {}
        for entry in raw:
            pair_data = entry.get("pairs", {}).get("A_vs_C", {})
            a_vs_c[entry["metric"]] = pair_data.get("cohens_d", 0.0)
    else:
        a_vs_c = raw.get("A_vs_C", {})

    ranked = sorted(a_vs_c.items(), key=lambda kv: abs(kv[1]), reverse=True)
    top_metrics = [m for m, _ in ranked[:6]]

    paths: list[str] = []
    for metric in top_metrics:
        if metric in df.columns:
            paths.append(plot_violin(df, metric, output_dir))
    return paths


# ---------------------------------------------------------------------------
# 8. Generate all plots
# ---------------------------------------------------------------------------


def generate_all_plots(
    metrics_csv: str | Path,
    analysis_dir: str | Path,
    output_dir: str | Path,
) -> list[str]:
    """Generate every available plot from the experiment results.

    Parameters
    ----------
    metrics_csv:
        Path to the CSV table produced by the metrics module.
    analysis_dir:
        Directory containing ``effect_sizes.json`` (from the analysis module).
    output_dir:
        Directory where plot images are written.

    Returns
    -------
    list[str]
        List of saved file paths.
    """
    metrics_csv = Path(metrics_csv)
    analysis_dir = Path(analysis_dir)
    output_dir = Path(output_dir)
    ensure_dirs(output_dir)

    df = pd.read_csv(metrics_csv)
    effect_sizes_path = analysis_dir / "effect_sizes.json"

    saved: list[str] = []

    # Determine numeric metric columns (exclude metadata columns).
    meta_cols = {"profile", "model", "task_id", "trial", "run_id", "timestamp"}
    metric_cols = [c for c in df.columns if c not in meta_cols and df[c].dtype in ("float64", "int64", "float32", "int32")]

    # Violin + grouped bars + interaction + task breakdown for each metric.
    for metric in metric_cols:
        _logger.info("Generating plots for metric: %s", metric)
        saved.append(plot_violin(df, metric, output_dir))
        saved.append(plot_grouped_bars(df, metric, output_dir))
        saved.append(plot_interaction(df, metric, output_dir))
        if "task_id" in df.columns:
            saved.append(plot_task_breakdown(df, metric, output_dir))

    # Effect-size heatmap.
    if effect_sizes_path.exists():
        _logger.info("Generating effect-size heatmap")
        saved.append(plot_effect_size_heatmap(effect_sizes_path, output_dir))

        _logger.info("Generating top-metric violin plots")
        saved.extend(plot_top_metrics(df, effect_sizes_path, output_dir))

    # Composite radar chart (only if the composite columns exist).
    if all(c in df.columns for c in _COMPOSITE_SCORES):
        _logger.info("Generating composite radar chart")
        saved.append(plot_composite_radar(df, output_dir))

    _logger.info("All plots generated — %d files saved to %s", len(saved), output_dir)
    return saved


# ---------------------------------------------------------------------------
# 9. CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Command-line interface for plot generation.

    Usage::

        python -m src.visualize \
            --metrics results/metrics/metrics_table.csv \
            --analysis analysis/ \
            --output plots/
    """
    parser = argparse.ArgumentParser(
        description="Generate all visualizations for the profile-bias experiment.",
    )
    parser.add_argument(
        "--metrics",
        type=str,
        default="results/metrics/metrics_table.csv",
        help="Path to the metrics CSV table.",
    )
    parser.add_argument(
        "--analysis",
        type=str,
        default="analysis/",
        help="Directory containing analysis artifacts (e.g. effect_sizes.json).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="plots/",
        help="Directory to save plot images.",
    )

    args = parser.parse_args()

    setup_logging(args.output, name="experiment.visualize")
    _logger.info("Starting plot generation")

    saved = generate_all_plots(args.metrics, args.analysis, args.output)
    _logger.info("Done — %d plots saved", len(saved))


if __name__ == "__main__":
    main()
