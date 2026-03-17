"""
core/config.py

Global configuration: .env loading, URL/token access, dry-run state.
All modules import from here rather than reading os.environ directly.
"""
from __future__ import annotations

import os
import sys

_MEALIE_URL: str = ""
_TOKEN: str = ""
_DRY_RUN: bool = False


def load_env() -> None:
    """
    Load .env from the project root (two levels up from this file).
    Supports KEY=value and KEY="value" formats.
    Shell environment variables take priority over .env values.
    """
    global _MEALIE_URL, _TOKEN

    # Walk up to project root (mealie_cleaner/)
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    env_path = os.path.join(root, ".env")

    if os.path.isfile(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip("\"'")
                if not os.environ.get(key):
                    os.environ[key] = val

    _MEALIE_URL = os.environ.get("MEALIE_URL", "").rstrip("/")
    _TOKEN = os.environ.get("MEALIE_TOKEN", "")


def check_env() -> None:
    if not _MEALIE_URL:
        print("\n✗ MEALIE_URL is not set. Add it to your .env file.", file=sys.stderr)
        sys.exit(1)
    if not _TOKEN:
        print("\n✗ MEALIE_TOKEN is not set. Add it to your .env file.", file=sys.stderr)
        sys.exit(1)


def get_url() -> str:
    return _MEALIE_URL


def get_token() -> str:
    return _TOKEN


def is_dry_run() -> bool:
    return _DRY_RUN


def set_dry_run(value: bool) -> None:
    global _DRY_RUN
    _DRY_RUN = value