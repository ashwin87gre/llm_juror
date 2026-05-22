#!/usr/bin/env python3
"""
POST to Jury Simulator ask_question with configured case, thread, and question.

By default only **political** NPORS-style survey items run (``dataset`` required).
Legal scenarios are disabled in the default file list; pass ``question_legal_list.json``
explicitly to include them. Legal items (``case_title`` set) omit ``dataset``.

Options are numbered 1…n. For each question, parses juror replies into option numbers,
stores them under the JSON ``variable`` field, prints that list's size, and after all
questions writes a CSV (columns = variables, rows = aligned answer index).

Questions use the existing jurors on ``THREAD_ID`` (optional per-question
``generate_personas`` remains commented below).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd
import requests

import jury_simulator
from option_counts import individual_responses_from_replies, option_keys_for_count

ROOT = Path(__file__).resolve().parent
DEFAULT_QUESTION_FILES: tuple[Path, ...] = (
    ROOT / "question_political_list_full.json",
    # Political-only default; re-enable to run legal + political in one invocation:
    # ROOT / "question_legal_list.json",
)
DEFAULT_CSV_OUTPUT = ROOT / "question_political_list_full.csv"
PERSONA_BATCH_SIZE = 6


def _format_number_choice_list(nums: list[str]) -> str:
    if len(nums) == 1:
        return nums[0]
    if len(nums) == 2:
        return f"{nums[0]} or {nums[1]}"
    return f"{', '.join(nums[:-1])}, or {nums[-1]}"


def _is_legal_scenario_item(data: dict) -> bool:
    ct = data.get("case_title")
    return isinstance(ct, str) and bool(ct.strip())


def _validate_question_item(data: dict) -> None:
    """Shared: ``item_id``, ``variable``, ``dimension``. Survey items need ``dataset``; legal items use ``case_title`` instead."""
    item_id = data.get("item_id")
    if item_id is None:
        raise ValueError("JSON must include integer 'item_id'")
    if isinstance(item_id, bool) or not isinstance(item_id, int):
        raise ValueError("'item_id' must be an integer")
    for key in ("variable", "dimension"):
        v = data.get(key)
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"JSON must include non-empty string '{key}'")
    if _is_legal_scenario_item(data):
        return
    ds = data.get("dataset")
    if not isinstance(ds, str) or not ds.strip():
        raise ValueError(
            "JSON must include non-empty 'dataset' for survey items, "
            "or non-empty 'case_title' for legal scenario items."
        )


def build_question_text(data: dict) -> str:
    """Assemble the API question: MC instruction (numeric) + stem + numbered options."""
    _validate_question_item(data)
    q = (data.get("question") or "").strip()
    raw_choices = data.get("choices")
    if not isinstance(raw_choices, list) or not raw_choices:
        raise ValueError("JSON must include non-empty 'choices' array of option labels")
    if not q:
        raise ValueError("JSON must include a non-empty 'question' string")

    nums = option_keys_for_count(len(raw_choices))
    number_choices = _format_number_choice_list(nums)

    lines = [t.strip() for t in raw_choices]
    for line in lines:
        if not line:
            raise ValueError("each choice must be non-empty")

    values_framing = ""
    if _is_legal_scenario_item(data):
        values_framing = (
            "These are hypothetical legal scenarios. "
            "Do not think about any separate case or role you may have been assigned—"
            "answer each question based only on your personal values, intuitions, and sense of what is fair or right.\n\n"
        )

    instruction = (
        "This is a multiple choice question. "
        f"You must answer by outputting nothing except one option number: {number_choices}. "
        "Do not write sentences, explanations, reasoning, labels like 'Option 2', or the choice text. "
        "Do not add punctuation, words, or line breaks—only the digits of the number that matches your choice."
    )
    numbered_options = "\n".join(f"{nums[i]}. {lines[i]}" for i in range(len(lines)))
    reminder = (
        f"Reply with only the number {number_choices} and absolutely nothing else."
    )
    return f"{values_framing}{instruction}\n\n{q}\n\n{numbered_options}\n\n{reminder}"


def load_question_items(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        if not raw:
            raise ValueError("question list is empty")
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ValueError(f"question list entry {i} is not an object")
        return raw
    raise ValueError("JSON root must be an object or a non-empty array of objects")


def load_question_blocks(paths: list[Path]) -> list[tuple[Path, list[dict]]]:
    """Load each file into ``(path, items)`` for ordered processing."""
    blocks: list[tuple[Path, list[dict]]] = []
    for path in paths:
        try:
            items = load_question_items(path)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"{path}: {e}") from e
        blocks.append((path, items))
    return blocks


def column_key_for_question(qdata: dict, used_base: set[str]) -> str:
    """Stable CSV column name from ``variable``; suffix if duplicate variable strings."""
    base = str(qdata.get("variable") or "").strip()
    if base not in used_base:
        used_base.add(base)
        return base
    item_id = qdata.get("item_id")
    sid = item_id if isinstance(item_id, int) and not isinstance(item_id, bool) else "dup"
    key = f"{base}__item_{sid}"
    n = 2
    while key in used_base:
        key = f"{base}__item_{sid}_{n}"
        n += 1
    used_base.add(key)
    return key


def fetch_parsed_answers(
    question_text: str,
    headers: dict[str, str],
    *,
    thread_id: str,
    option_keys: list[str],
) -> list[str]:
    status, replies = jury_simulator.post_ask_question_replies(
        question_text, headers, thread_id=thread_id
    )
    print("Status:", status, file=sys.stderr)
    return individual_responses_from_replies(replies, option_keys, warn_dropped=True)


def generate_persona_batch_thread_id(
    headers: dict[str, str],
    *,
    persona_count: int = PERSONA_BATCH_SIZE,
) -> str:
    """Generate personas and return thread id used for subsequent question."""
    status, body = jury_simulator.post_generate_personas(
        headers, persona_count=persona_count
    )
    print(f"Generate Personas Status: {status}", file=sys.stderr)
    print("Generate Personas Output:", file=sys.stderr)
    print(json.dumps(body, indent=2), file=sys.stderr)
    return jury_simulator.thread_id_from_generate_personas_body(body)


def save_results_csv(results: dict[str, list[str]], path: Path) -> None:
    """Wide table: one row per response index; columns are variables; pad short columns."""
    if not results:
        return
    max_len = max(len(v) for v in results.values())
    padded = {col: lst + [""] * (max_len - len(lst)) for col, lst in results.items()}
    df = pd.DataFrame(padded)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def main() -> int:
    p = argparse.ArgumentParser(
        description="POST ask_question to Jury Simulator from one or more JSON files."
    )
    p.add_argument(
        "question_files",
        nargs="*",
        type=Path,
        default=None,
        help=f"question JSON files (default: {' then '.join(p.name for p in DEFAULT_QUESTION_FILES)})",
    )
    p.add_argument(
        "--csv-output",
        type=Path,
        default=DEFAULT_CSV_OUTPUT,
        help=f"path for combined responses CSV (default: {DEFAULT_CSV_OUTPUT.name})",
    )
    args = p.parse_args()
    paths: list[Path] = (
        list(args.question_files) if args.question_files else list(DEFAULT_QUESTION_FILES)
    )

    for path in paths:
        if not path.is_file():
            print(f"Error: question file not found: {path}", file=sys.stderr)
            return 2

    try:
        blocks = load_question_blocks(paths)
    except ValueError as e:
        print(f"Error loading or parsing question file: {e}", file=sys.stderr)
        return 2

    token = os.environ.get("JURYSIMULATOR_API_KEY", "nJ/Fb7ko7RNy8AURdhFlV1qnYcbQWnrL3PeIeRDNf/4=")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    total = sum(len(items) for _, items in blocks)
    global_idx = 0
    multi_file = len(blocks) > 1

    results: dict[str, list[str]] = {}
    used_column_bases: set[str] = set()

    for path, items in blocks:
        if multi_file:
            print(f"--- {path.name} ({len(items)} questions) ---", file=sys.stderr)
        for qdata in items:
            global_idx += 1
            _iid = qdata.get("item_id")
            item_id = _iid if isinstance(_iid, int) and not isinstance(_iid, bool) else None
            label = f"Question {global_idx}/{total}"
            if item_id is not None:
                label += f" (item_id={item_id})"
            if multi_file:
                label += f" [{path.name}]"
            print(label, file=sys.stderr)

            var_raw = str(qdata.get("variable") or "").strip()
            col_key = column_key_for_question(qdata, used_column_bases)
            print(f"variable={var_raw!r} (column={col_key!r})", file=sys.stderr)

            try:
                question = build_question_text(qdata)
                raw_choices = qdata.get("choices")
                n = len(raw_choices) if isinstance(raw_choices, list) else 0
                option_keys = option_keys_for_count(n) if n else []
            except ValueError as e:
                print(f"Error in {path.name} item: {e}", file=sys.stderr)
                return 2
            print(question, file=sys.stderr)
            print(file=sys.stderr)
            try:
                # batch_thread_id = generate_persona_batch_thread_id(
                #     headers, persona_count=PERSONA_BATCH_SIZE
                # )
                answers = fetch_parsed_answers(
                    question,
                    headers,
                    thread_id=jury_simulator.THREAD_ID,
                    option_keys=option_keys,
                )
            except requests.HTTPError as e:
                print(f"HTTP error: {e}", file=sys.stderr)
                if e.response is not None and e.response.text:
                    print(e.response.text, file=sys.stderr)
                return 1
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1

            results[col_key] = answers
            size = len(answers)
            print(f"{col_key}\t{size}")
            print(f"answers ({size}): {answers}", file=sys.stderr)

    save_results_csv(results, args.csv_output)
    print(f"Wrote CSV: {args.csv_output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
