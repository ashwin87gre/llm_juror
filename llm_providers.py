"""Direct calls to foundation models (Claude, GPT, …), not via Jury Simulator.

Build :class:`option_counts.OptionCounts` with
:func:`option_counts.option_counts_from_replies` (``{\"reply\": \"1\"}`` style)
or :func:`option_counts.option_counts_from_mapping` (numeric option id → count).
"""
from __future__ import annotations

from option_counts import OptionCounts


def poll_models_option_counts(
    question_text: str,
    *,
    models: list[str],
    option_keys: list[str],
) -> OptionCounts:
    """Aggregate MC answers from direct model calls into standard counts."""
    raise NotImplementedError
