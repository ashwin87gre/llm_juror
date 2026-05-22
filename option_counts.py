"""Multiple-choice results keyed by 1-based option numbers (``\"1\"``, ``\"2\"``, …).

Parse raw jury or LLM ``replies`` here; downstream code can use counts or ordered
individual response lists.
"""
from __future__ import annotations

import sys
from collections import Counter
from collections.abc import Mapping
from typing import Any, TypeAlias

OptionCounts: TypeAlias = dict[str, int]
"""Each allowed option id (``\"1\"``, ``\"2\"``, …) maps to a count; all options appear."""


def option_keys_for_count(n: int) -> list[str]:
    if n < 1 or n > 99:
        raise ValueError("there must be between 1 and 99 choices.")
    return [str(i) for i in range(1, n + 1)]


def _reply_as_option_string(raw: Any) -> str | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return str(raw)
    if isinstance(raw, str):
        return raw.strip()
    return None


def normalize_reply_to_option_key(raw: Any, valid: set[str]) -> str | None:
    """If ``raw`` denotes one of ``valid`` option ids (strings ``\"1\"``…), return that key."""
    s = _reply_as_option_string(raw)
    if s is None or s == "":
        return None
    if s in valid:
        return s
    return None


def _reply_row_label(item: Any, index: int) -> str:
    if isinstance(item, dict):
        parts = [f"index={index}"]
        if "persona_id" in item:
            parts.append(f"persona_id={item.get('persona_id')}")
        if "reply_id" in item:
            parts.append(f"reply_id={item.get('reply_id')}")
        return ", ".join(parts)
    return f"index={index}"


def _parse_reply_item(
    item: Any,
    valid: set[str],
    index: int,
    *,
    warn_dropped: bool,
) -> str | None:
    """Return option key or None; optionally print drop reason to stderr."""
    label = _reply_row_label(item, index)
    if not isinstance(item, dict):
        if warn_dropped:
            print(
                f"dropped reply ({label}): not an object, got {type(item).__name__}",
                file=sys.stderr,
            )
        return None
    if "reply" not in item:
        if warn_dropped:
            print(
                f"dropped reply ({label}): missing 'reply' key; keys={list(item.keys())}",
                file=sys.stderr,
            )
        return None
    raw = item["reply"]
    if isinstance(raw, bool):
        if warn_dropped:
            print(f"dropped reply ({label}): 'reply' is boolean {raw!r}", file=sys.stderr)
        return None
    s = _reply_as_option_string(raw)
    if s is None:
        if warn_dropped:
            print(
                f"dropped reply ({label}): unsupported 'reply' type {type(raw).__name__}, value={raw!r}",
                file=sys.stderr,
            )
        return None
    if s == "":
        if warn_dropped:
            print(f"dropped reply ({label}): empty or whitespace-only reply", file=sys.stderr)
        return None
    if s not in valid:
        if warn_dropped:
            valid_preview = ", ".join(sorted(valid, key=lambda x: int(x) if x.isdigit() else x))
            print(
                f"dropped reply ({label}): reply {s!r} is not a valid option (expected one of: {valid_preview})",
                file=sys.stderr,
            )
        return None
    return s


def individual_responses_from_replies(
    replies: object,
    option_keys: list[str],
    *,
    warn_dropped: bool = True,
) -> list[str]:
    """Ordered list of option ids for each valid reply; invalid dropped."""
    valid = set(option_keys)
    if not isinstance(replies, list):
        if warn_dropped:
            print(
                f"dropped: 'replies' is not a list (got {type(replies).__name__}); no responses extracted",
                file=sys.stderr,
            )
        return []
    out: list[str] = []
    for i, item in enumerate(replies):
        key = _parse_reply_item(item, valid, i, warn_dropped=warn_dropped)
        if key is not None:
            out.append(key)
    return out


def format_individual_responses_line(response_keys: list[str]) -> str:
    """``1, 2, 1, 2`` style (comma + space)."""
    return ", ".join(response_keys)


def option_counts_from_replies(
    replies: object,
    option_keys: list[str],
    *,
    warn_dropped: bool = True,
) -> OptionCounts:
    """Count replies per option; invalid replies skipped. Every option key present, including zeros."""
    valid = set(option_keys)
    if not isinstance(replies, list):
        if warn_dropped:
            print(
                f"dropped: 'replies' is not a list (got {type(replies).__name__}); counts are all zero",
                file=sys.stderr,
            )
        return {k: 0 for k in option_keys}
    counts: Counter[str] = Counter()
    for i, item in enumerate(replies):
        key = _parse_reply_item(item, valid, i, warn_dropped=warn_dropped)
        if key is not None:
            counts[key] += 1
    return {k: counts[k] for k in option_keys}


def option_counts_from_mapping(
    mapping: Mapping[str, Any],
    option_keys: list[str],
) -> OptionCounts:
    """Normalize a mapping keyed by option id strings (``\"1\"``, ``\"2\"``, …)."""
    out: dict[str, int] = {}
    for k in option_keys:
        raw = mapping.get(k)
        if raw is None:
            try:
                ik = int(k)
                raw = mapping.get(ik)
            except ValueError:
                pass
        if raw is None:
            out[k] = 0
            continue
        try:
            out[k] = max(0, int(raw))
        except (TypeError, ValueError):
            out[k] = 0
    return out


def format_option_counts(counts: OptionCounts) -> str:
    """Single-line ``1-4, 2-3, 3-0`` summary."""
    if not counts:
        return ""
    return ", ".join(f"{key}-{n}" for key, n in counts.items())
