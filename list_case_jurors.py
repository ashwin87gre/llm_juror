#!/usr/bin/env python3
"""Print juror count for a case via get_personas."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import requests

import jury_simulator

GET_PERSONAS_URL = "https://my.jurysimulator.com/api/external/get_personas"


def _extract_juror_ids(items: list[Any]) -> list[int]:
    """Accept either ``id`` or ``persona_id`` fields from juror objects."""
    ids: set[int] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        pid = item.get("id")
        if not isinstance(pid, int) or isinstance(pid, bool):
            pid = item.get("persona_id")
        if isinstance(pid, int) and not isinstance(pid, bool):
            ids.add(pid)
    return sorted(ids)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Print juror count using get_personas."
    )
    p.add_argument(
        "--case-id",
        default=jury_simulator.CASE_ID,
        help=f"case id to query (default: {jury_simulator.CASE_ID})",
    )
    args = p.parse_args()

    token = os.environ.get(
        "JURYSIMULATOR_API_KEY",
        "nJ/Fb7ko7RNy8AURdhFlV1qnYcbQWnrL3PeIeRDNf/4=",
    )
    headers = {
        "Authorization": f"Bearer {token}",
    }

    try:
        resp = requests.get(
            GET_PERSONAS_URL,
            headers=headers,
            params={"case_id": args.case_id},
            timeout=120,
        )
        status = resp.status_code
        resp.raise_for_status()
        body = resp.json()
    except requests.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        if e.response is not None and e.response.text:
            print(e.response.text, file=sys.stderr)
        return 1
    except ValueError:
        print("Error: get_personas response is not JSON", file=sys.stderr)
        return 1
    except requests.RequestException as e:
        print(f"Request error: {e}", file=sys.stderr)
        return 1

    if not isinstance(body, dict):
        print("Error: get_personas response JSON is not an object", file=sys.stderr)
        return 1

    personas = body.get("personas")
    if not isinstance(personas, list):
        # Try nested fallback structures.
        nested = body.get("data")
        if isinstance(nested, dict) and isinstance(nested.get("personas"), list):
            personas = nested["personas"]
        else:
            print(
                "Error: could not find 'personas' list in response body:",
                file=sys.stderr,
            )
            print(json.dumps(body, indent=2), file=sys.stderr)
            return 1

    print(f"Status: {status}", file=sys.stderr)
    ids = _extract_juror_ids(personas)
    if ids:
        print(f"Total jurors: {len(ids)}")
        return 0

    # Fallback: even if ids are missing, we can still report list size.
    print("Warning: juror IDs missing; using personas list length.", file=sys.stderr)
    print(f"Total jurors: {len(personas)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
