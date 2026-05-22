#!/usr/bin/env python3
"""Copy NPORS_2025_sample_200.csv with a random swap probability per column.

Each column gets its own threshold drawn uniformly from [--p-min, --p-max] (default
5%%–20%%); each cell is perturbed independently with that column's probability.

Primary swap: pick uniformly from full-data uniques for that column that never appear
in that column of the sample file (full NPORS rows with no 99 in the selected columns).

If that pool is empty (the sample already exhibits every distinct code seen in the
full file for that column), fall back to another value from the full-data universe
still different from the current cell.

Same columns and row count as the input sample; does not modify ask_question.py.
"""
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

from sample_npors_columns import COLUMNS

ROOT = Path(__file__).resolve().parent
DEFAULT_SAMPLE = ROOT / "NPORS_2025_sample_200.csv"
DEFAULT_FULL = ROOT / "NPORS_2025_for_public_release_FINAL.csv"
DEFAULT_OUTPUT = ROOT / "NPORS_2025_sample_200_perturbed.csv"


def _is_99(val: object) -> bool:
    if val is None:
        return False
    s = str(val).strip()
    if s == "" or s.lower() in ("nan", "none"):
        return False
    if s == "99":
        return True
    try:
        return float(s) == 99.0
    except ValueError:
        return False


def _row_ok(row: dict[str, str], cols: list[str]) -> bool:
    return not any(_is_99(row.get(c)) for c in cols)


def full_column_universes(full_path: Path, cols: list[str]) -> dict[str, set[str]]:
    """Distinct cell values per column from full CSV (only rows with no 99 in ``cols``)."""
    uniques: dict[str, set[str]] = {c: set() for c in cols}
    with full_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not set(cols).issubset(reader.fieldnames):
            raise SystemExit(f"full CSV missing columns: {sorted(set(cols) - set(reader.fieldnames or []))}")
        for row in reader:
            if not _row_ok(row, cols):
                continue
            for c in cols:
                v = row.get(c, "")
                uniques[c].add(v.strip() if v is not None else "")
    return uniques


def sample_column_uniques(rows: list[dict[str, str]], cols: list[str]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {c: set() for c in cols}
    for row in rows:
        for c in cols:
            out[c].add((row.get(c) or "").strip())
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE)
    p.add_argument("--full", type=Path, default=DEFAULT_FULL)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument(
        "--p-min",
        type=float,
        default=0.05,
        help="lower bound for each column's perturb probability (default: 0.05)",
    )
    p.add_argument(
        "--p-max",
        type=float,
        default=0.20,
        help="upper bound for each column's perturb probability (default: 0.20)",
    )
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    if not (0.0 <= args.p_min <= 1.0 and 0.0 <= args.p_max <= 1.0):
        raise SystemExit("--p-min and --p-max must be between 0 and 1")
    if args.p_min > args.p_max:
        raise SystemExit("--p-min must not exceed --p-max")

    full_uni = full_column_universes(args.full, COLUMNS)

    with args.sample.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            raise SystemExit(
                f"sample header must match COLUMNS exactly; got {reader.fieldnames}"
            )
        rows = [dict(row) for row in reader]

    if len(rows) != 200:
        print(f"warning: expected 200 rows, got {len(rows)}", flush=True)

    sample_uni = sample_column_uniques(rows, COLUMNS)

    # Values that appear in full (filtered) data but never in this sample column.
    outside_sample: dict[str, list[str]] = {}
    for c in COLUMNS:
        pool = sorted(full_uni[c] - sample_uni[c])
        outside_sample[c] = pool

    rng = random.Random(args.seed)
    column_p: dict[str, float] = {
        c: rng.uniform(args.p_min, args.p_max) for c in COLUMNS
    }
    print("Per-column perturb probability:", flush=True)
    for c in COLUMNS:
        print(f"  {c}: {column_p[c] * 100:.2f}%", flush=True)

    perturbed_cells = 0
    skipped_no_alternative = 0
    strict_swaps = 0
    fallback_swaps = 0

    out_rows: list[dict[str, str]] = []
    for row in rows:
        new_row = dict(row)
        for c in COLUMNS:
            if rng.random() >= column_p[c]:
                continue
            cur = (new_row.get(c) or "").strip()
            # Prefer a value that never appears in this column of the sample file.
            strict = [x for x in outside_sample[c] if x != cur]
            if strict:
                new_row[c] = rng.choice(strict)
                perturbed_cells += 1
                strict_swaps += 1
                continue
            # Sample already exhausted full-data uniques for this column; any other full value.
            loose = [x for x in sorted(full_uni[c]) if x != cur]
            if not loose:
                skipped_no_alternative += 1
                continue
            new_row[c] = rng.choice(loose)
            perturbed_cells += 1
            fallback_swaps += 1
        out_rows.append(new_row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(out_rows)

    print(
        f"wrote {args.output} ({len(out_rows)} rows); "
        f"perturbed {perturbed_cells} cells "
        f"(per-column p ~ Uniform({args.p_min:.0%}, {args.p_max:.0%}), seed={args.seed}); "
        f"strict outside-sample: {strict_swaps}, fallback other full value: {fallback_swaps}; "
        f"skipped {skipped_no_alternative} (column has only one value in full data)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
