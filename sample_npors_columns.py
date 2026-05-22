#!/usr/bin/env python3
"""Build a random 200-row CSV from NPORS with selected columns (exclude any row with 99 in those columns)."""
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

COLUMNS = [
    "GOVPROTCT",
    "UNITY",
    "MOREGUNIMPACT",
    "VET1",
    "VOL12_CPS",
    "INTFREQ",
    "SMUSE_TS",
    "AGECAT",
    "GENDER",
    "RACETHN",
    "INC_SDT1",
    "METRO",
]

DEFAULT_INPUT = Path(__file__).resolve().parent / "NPORS_2025_for_public_release_FINAL.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "NPORS_2025_sample_200.csv"


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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    with args.input.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames or not set(COLUMNS).issubset(fieldnames):
            missing = set(COLUMNS) - set(fieldnames or [])
            raise SystemExit(f"missing columns in CSV: {sorted(missing)}")

        eligible: list[dict[str, str]] = []
        for row in reader:
            if any(_is_99(row.get(c)) for c in COLUMNS):
                continue
            eligible.append({c: row.get(c, "") for c in COLUMNS})

    if len(eligible) < args.n:
        raise SystemExit(f"only {len(eligible)} rows after dropping 99; need {args.n}")

    rng = random.Random(args.seed)
    sample = rng.sample(eligible, args.n)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(sample)

    print(f"wrote {args.n} rows to {args.output} (from {len(eligible)} eligible)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
