#!/usr/bin/env python3
"""Bar charts for legal-scenario LLM responses.

Reads ``human_response_legal.csv`` (despite the name, values are **LLM** aggregates).
Expected columns: for each item in ``question_legal_list.json``, one column per answer
option, named ``{variable}_1``, ``{variable}_2``, … matching the JSON ``choices`` order
(same numbering as ``ask_question.py``). Values are numeric; multiple CSV rows are summed
per column (e.g. juror-level counts or indicator rows).

Does not modify ``ask_question.py``.
"""
from __future__ import annotations

import argparse
import csv
import json
import textwrap
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
DEFAULT_CSV = ROOT / "human_response_legal.csv"
DEFAULT_LEGAL_JSON = ROOT / "question_legal_list.json"
DEFAULT_OUT = ROOT / "legal_graphs.png"


def _load_legal_questions(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list) or not raw:
        raise ValueError("legal JSON must be a non-empty array")
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"legal item {i} is not an object")
        if "variable" not in item or "choices" not in item:
            raise ValueError(f"legal item {i} needs 'variable' and 'choices'")
        ch = item["choices"]
        if not isinstance(ch, list) or not ch:
            raise ValueError(f"legal item {i} needs non-empty 'choices'")
    return raw


def _column_names_for_question(q: dict[str, Any]) -> list[str]:
    var = str(q["variable"]).strip()
    k = len(q["choices"])
    return [f"{var}_{i}" for i in range(1, k + 1)]


def _aggregate_column(rows: list[dict[str, str]], col: str) -> float:
    total = 0.0
    for row in rows:
        raw = row.get(col, "")
        s = (raw or "").strip()
        if s == "":
            continue
        try:
            total += float(s)
        except ValueError:
            raise ValueError(f"non-numeric value in column {col!r}: {raw!r}") from None
    return total


def _wrap_lines(text: str, width: int = 42) -> str:
    return "\n".join(textwrap.wrap(text, width=width)) if text else ""


def main() -> int:
    p = argparse.ArgumentParser(description="Legal reasoning LLM response bar charts.")
    p.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="LLM response CSV")
    p.add_argument("--legal-json", type=Path, default=DEFAULT_LEGAL_JSON)
    p.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()

    questions = _load_legal_questions(args.legal_json)

    with args.csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit(f"no header row: {args.csv}")
        fieldnames = set(reader.fieldnames)
        rows = list(reader)

    if not rows:
        raise SystemExit(f"no data rows: {args.csv}")

    nq = len(questions)
    ncols = 2
    nrows = (nq + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(6.5 * ncols, 4.2 * nrows))
    axes_list = list(axes.flatten()) if hasattr(axes, "flatten") else [axes]

    for idx, q in enumerate(questions):
        ax = axes_list[idx]
        cols = _column_names_for_question(q)
        missing = [c for c in cols if c not in fieldnames]
        if missing:
            raise SystemExit(
                f"{args.csv}: missing column(s) for {q.get('variable')!r}: {missing}. "
                f"Expected names {{variable}}_1 … _K per question_legal_list.json."
            )

        heights = [_aggregate_column(rows, c) for c in cols]
        x_pos = range(len(cols))
        bars = ax.bar(x_pos, heights, color="#2c5282", edgecolor="white", linewidth=0.6)
        ax.bar_label(bars, fmt="%.0f", fontsize=9, padding=2)

        choice_labels = [_wrap_lines(str(ch).strip(), 32) for ch in q["choices"]]
        ax.set_xticks(list(x_pos))
        ax.set_xticklabels(
            [f"{i + 1}\n{lbl}" for i, lbl in enumerate(choice_labels)],
            fontsize=7,
            linespacing=1.15,
        )

        case_title = (q.get("case_title") or "").strip()
        var = (q.get("variable") or "").strip()
        ax.set_title(f"{var}\n{_wrap_lines(case_title, 50)}", fontsize=9, fontweight="bold")
        ax.set_xlabel("Answer option (same index as survey prompt)")
        ax.set_ylabel("Aggregated count / score (summed over CSV rows)")
        ax.grid(axis="y", linestyle=":", alpha=0.45)
        ax.set_ylim(bottom=0)

    for j in range(len(questions), len(axes_list)):
        axes_list[j].set_visible(False)

    fig.suptitle(
        "Legal reasoning — LLM response distribution\n"
        "(source: human_response_legal.csv — filename refers to human; data are LLM outputs)",
        fontsize=12,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
