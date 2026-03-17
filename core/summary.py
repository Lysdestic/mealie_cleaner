"""
core/summary.py

A simple session-level summary log. Steps append lines to it during
their run, and mealie_suite.py prints the full summary at the end.

Usage in a step:
    from core.summary import summary
    summary.add("cleanup", "Deleted 3 non-canonical tags")
    summary.add("cleanup", "Kept 2 tags → added to taxonomy.json")
"""
from __future__ import annotations


class SummaryLog:
    def __init__(self) -> None:
        self._entries: list[tuple[str, str]] = []

    def add(self, step: str, message: str) -> None:
        self._entries.append((step, message))

    def clear(self) -> None:
        self._entries.clear()

    @property
    def has_entries(self) -> bool:
        return bool(self._entries)

    def print(self) -> None:
        if not self._entries:
            return

        from core import color

        print(f"\n{color.bold('─' * 60)}")
        print(f"{color.bold('SESSION SUMMARY')}")
        print(f"{color.bold('─' * 60)}")

        current_step = None
        for step, message in self._entries:
            if step != current_step:
                print(f"\n  {color.bold(color.bright_cyan(f'[{step}]'))}")
                current_step = step
            print(f"    {message}")

        print(f"\n{color.bold('─' * 60)}\n")


# Module-level singleton — import this everywhere
summary = SummaryLog()