"""
core/utils.py

Shared string utilities and console helpers.
"""
from __future__ import annotations

import re
import sys


def normalize(s: str) -> str:
    """Lowercase, strip, collapse non-alphanumeric to spaces."""
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_slug(s: str) -> str:
    """Convert a string to a URL-safe slug."""
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


def fail(msg: str) -> None:
    print(f"\n✗ {msg}", file=sys.stderr)
    sys.exit(1)


def confirm(prompt: str) -> bool:
    """Prompt for y/N confirmation. Returns False on Ctrl-C."""
    try:
        return input(f"\n{prompt} [y/N] ").strip().lower() == "y"
    except (KeyboardInterrupt, EOFError):
        print()
        return False


def dry_run_banner() -> None:
    print("─" * 60)
    print("  DRY RUN — no changes will be made")
    print("  Omit --dry-run to apply changes.")
    print("─" * 60)