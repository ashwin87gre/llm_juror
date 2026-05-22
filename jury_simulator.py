"""HTTP client for the Jury Simulator external API.

Keep jury-specific URLs, payloads, and response parsing here. Other backends
(e.g. direct LLM calls) live in separate modules.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

import requests

from option_counts import OptionCounts, option_counts_from_replies

ASK_QUESTION_URL = "https://my.jurysimulator.com/api/external/ask_question"
GENERATE_PERSONAS_URL = "https://my.jurysimulator.com/api/external/generate_personas"
CASE_ID = "c74cd1f5-1fe1-4e77-b045-5fcfdb92e8e6"
THREAD_ID = "2b98e5e2-da26-4e62-80ae-a5f71f993626"


def post_ask_question(
    question_text: str,
    headers: Mapping[str, str],
    *,
    thread_id: str = THREAD_ID,
    timeout: float = 120,
) -> tuple[int, dict[str, Any]]:
    """POST ``/api/external/ask_question``.

    Returns ``(http_status, parsed_json_object)``. Raises
    :class:`requests.HTTPError` on non-success HTTP status.
    Raises :class:`ValueError` if the body is not a JSON object.
    """
    payload = {
        "case_id": CASE_ID,
        "thread_id": thread_id,
        "question": question_text,
    }
    r = requests.post(
        ASK_QUESTION_URL,
        headers=dict(headers),
        json=payload,
        timeout=timeout,
    )
    status = r.status_code
    r.raise_for_status()
    try:
        body = r.json()
    except ValueError as e:
        raise ValueError(
            f"response body is not JSON (HTTP {status}): {r.text!r}"
        ) from e
    if not isinstance(body, dict):
        raise ValueError("response JSON is not an object")
    return status, body


def replies_from_ask_question_body(body: dict[str, Any]) -> list[Any]:
    """Validate a successful ask_question response and return the ``replies`` list."""
    if body.get("success") is not True:
        raise ValueError(f"API reported failure: {json.dumps(body)}")
    replies = body.get("replies")
    if replies is None:
        return []
    if not isinstance(replies, list):
        raise ValueError("'replies' is not an array")
    return replies


def post_ask_question_replies(
    question_text: str,
    headers: Mapping[str, str],
    *,
    thread_id: str = THREAD_ID,
    timeout: float = 120,
) -> tuple[int, list[Any]]:
    """POST ask_question and return ``(http_status, replies list)``."""
    status, body = post_ask_question(
        question_text, headers, thread_id=thread_id, timeout=timeout
    )
    return status, replies_from_ask_question_body(body)


def post_ask_question_option_counts(
    question_text: str,
    option_keys: list[str],
    headers: Mapping[str, str],
    *,
    thread_id: str = THREAD_ID,
    timeout: float = 120,
) -> tuple[int, OptionCounts]:
    """POST ask_question and return ``(http_status, option_counts)``."""
    status, replies = post_ask_question_replies(
        question_text, headers, thread_id=thread_id, timeout=timeout
    )
    return status, option_counts_from_replies(replies, option_keys)


def post_generate_personas(
    headers: Mapping[str, str],
    *,
    persona_count: int = 6,
    timeout: float = 120,
) -> tuple[int, dict[str, Any]]:
    """POST generate_personas and return ``(http_status, parsed_json_object)``."""
    payload = {
        "case_id": CASE_ID,
        "persona_count": persona_count,
    }
    r = requests.post(
        GENERATE_PERSONAS_URL,
        headers=dict(headers),
        json=payload,
        timeout=timeout,
    )
    status = r.status_code
    r.raise_for_status()
    try:
        body = r.json()
    except ValueError as e:
        raise ValueError(
            f"response body is not JSON (HTTP {status}): {r.text!r}"
        ) from e
    if not isinstance(body, dict):
        raise ValueError("response JSON is not an object")
    return status, body


def thread_id_from_generate_personas_body(body: dict[str, Any]) -> str:
    """Extract thread id when present; otherwise keep configured default."""
    if "thread_id" in body and isinstance(body["thread_id"], str) and body["thread_id"].strip():
        return body["thread_id"].strip()
    thread_obj = body.get("thread")
    if isinstance(thread_obj, dict):
        candidate = thread_obj.get("thread_id")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return THREAD_ID


def persona_ids_from_generate_personas_body(body: dict[str, Any]) -> set[int]:
    """Best-effort extraction of generated persona ids from response JSON."""
    out: set[int] = set()

    def collect_from_seq(seq: Any) -> None:
        if not isinstance(seq, list):
            return
        for item in seq:
            if not isinstance(item, dict):
                continue
            pid = item.get("persona_id")
            if isinstance(pid, int) and not isinstance(pid, bool):
                out.add(pid)

    collect_from_seq(body.get("personas"))
    collect_from_seq(body.get("generated_personas"))
    data = body.get("data")
    if isinstance(data, dict):
        collect_from_seq(data.get("personas"))
        collect_from_seq(data.get("generated_personas"))

    return out
