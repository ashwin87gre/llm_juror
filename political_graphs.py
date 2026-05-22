#!/usr/bin/env python3
"""Grouped bar charts: NPORS sample vs perturbed (“LLM agent”) value counts per column."""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sample_npors_columns import COLUMNS

ROOT = Path(__file__).resolve().parent
DEFAULT_NPORS = ROOT / "NPORS_2025_sample_200.csv"
DEFAULT_PERT = ROOT / "NPORS_2025_sample_200_perturbed.csv"
DEFAULT_OUT = ROOT / "political_graphs.png"


def _sort_value_keys(keys: set[str]) -> list[str]:
    def sort_key(v: str) -> tuple:
        if v == "":
            return (-1, "")
        try:
            return (0, int(v))
        except ValueError:
            try:
                return (0, float(v))
            except ValueError:
                return (1, v)

    return sorted(keys, key=sort_key)


def _load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if not r.fieldnames:
            raise ValueError(f"no header: {path}")
        cols = list(r.fieldnames)
        rows = list(r)
    return cols, rows


def _counts(rows: list[dict[str, str]], col: str) -> Counter[str]:
    return Counter((row.get(col) or "").strip() for row in rows)


def plot_distribution_panel(
    ax: plt.Axes,
    col: str,
    rows_npors: list[dict[str, str]],
    rows_llm: list[dict[str, str]],
) -> None:
    c_npors = _counts(rows_npors, col)
    c_llm = _counts(rows_llm, col)
    keys = _sort_value_keys(set(c_npors) | set(c_llm))
    if not keys:
        ax.set_visible(False)
        return

    y_npors = [c_npors[k] for k in keys]
    y_llm = [c_llm[k] for k in keys]
    x = range(len(keys))
    width = 0.38

    ax.bar([i - width / 2 for i in x], y_npors, width, label="NPORS", color="#2c5282", edgecolor="white", linewidth=0.5)
    ax.bar([i + width / 2 for i in x], y_llm, width, label="LLM agent", color="#c05621", edgecolor="white", linewidth=0.5)

    ax.set_title(col, fontsize=10, fontweight="bold")
    ax.set_xlabel("Value")
    ax.set_ylabel("Count")
    ax.set_xticks(list(x))
    ax.set_xticklabels(keys, rotation=45, ha="right", fontsize=8)
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", linestyle=":", alpha=0.5)


def main() -> int:
    p = argparse.ArgumentParser(description="Bar graphs: NPORS vs LLM agent column distributions.")
    p.add_argument("--npors", type=Path, default=DEFAULT_NPORS)
    p.add_argument("--perturbed", type=Path, default=DEFAULT_PERT)
    p.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()

    cols_npors, rows_npors = _load_rows(args.npors)
    cols_llm, rows_llm = _load_rows(args.perturbed)

    if cols_npors != COLUMNS or cols_llm != COLUMNS:
        raise SystemExit(
            f"expected columns {COLUMNS!r}; got npors={cols_npors!r} perturbed={cols_llm!r}"
        )
    n_a, n_b = len(rows_npors), len(rows_llm)
    if n_a != n_b:
        print(f"warning: row counts differ (NPORS={n_a}, LLM={n_b})", flush=True)

    ncols = 4
    nrows = (len(COLUMNS) + ncols - 1) // ncols
    fig_w = 4.2 * ncols
    fig_h = 3.4 * nrows
    fig, axes = plt.subplots(nrows, ncols, figsize=(fig_w, fig_h), constrained_layout=False)
    axes_list = axes.flatten() if len(COLUMNS) > 1 else [axes]

    for idx, col in enumerate(COLUMNS):
        plot_distribution_panel(axes_list[idx], col, rows_npors, rows_llm)

    for j in range(len(COLUMNS), len(axes_list)):
        axes_list[j].set_visible(False)

    fig.suptitle(
        "Response distribution by column\nNPORS  vs LLM agent",
        fontsize=14,
        fontweight="bold",
        y=1.01,
    )
    handles, labels = axes_list[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", bbox_to_anchor=(0.98, 0.98), fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.97])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
