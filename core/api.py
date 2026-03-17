"""
core/api.py

Low-level Mealie API helpers: req() and get_all().
All HTTP calls go through here.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import get_url, get_token


def req(
    method: str,
    path: str,
    payload: dict | None = None,
    params: dict | None = None,
) -> Any:
    url = f"{get_url()}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    data = None
    headers = {
        "Authorization": f"Bearer {get_token()}",
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except KeyboardInterrupt:
        raise  # let it propagate cleanly to the top-level handler
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"  HTTP {e.code} on {method} {url}", file=sys.stderr)
        print(f"  {body[:400]}", file=sys.stderr)
        raise


def get_all(path: str) -> list[dict]:
    """Fetch all pages of a paginated Mealie endpoint."""
    items: list[dict] = []
    page = 1
    while True:
        data = req("GET", path, params={"page": page, "perPage": 200})
        batch = data.get("items", [])
        items.extend(batch)
        page_count = (
            data.get("total_pages")
            or data.get("pageCount")
            or data.get("totalPages")
            or page
        )
        if not batch or page >= page_count:
            break
        page += 1
    return items