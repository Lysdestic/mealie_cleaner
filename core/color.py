"""
core/color.py

Lightweight ANSI color helpers. No dependencies.
Automatically disabled when output is not a TTY (e.g. piped to a file).
"""
from __future__ import annotations

import sys
import os

# Disable colors if not a TTY or if NO_COLOR env var is set
_ENABLED = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _c(code: str, text: str) -> str:
    if not _ENABLED:
        return text
    return f"\033[{code}m{text}\033[0m"


# ── Text styles ───────────────────────────────────────────────────
def bold(text: str)    -> str: return _c("1",  text)
def dim(text: str)     -> str: return _c("2",  text)
def italic(text: str)  -> str: return _c("3",  text)

# ── Foreground colors ─────────────────────────────────────────────
def red(text: str)     -> str: return _c("31", text)
def green(text: str)   -> str: return _c("32", text)
def yellow(text: str)  -> str: return _c("33", text)
def blue(text: str)    -> str: return _c("34", text)
def magenta(text: str) -> str: return _c("35", text)
def cyan(text: str)    -> str: return _c("36", text)
def white(text: str)   -> str: return _c("37", text)

# ── Bright variants ───────────────────────────────────────────────
def bright_red(text: str)     -> str: return _c("91", text)
def bright_green(text: str)   -> str: return _c("92", text)
def bright_yellow(text: str)  -> str: return _c("93", text)
def bright_blue(text: str)    -> str: return _c("94", text)
def bright_magenta(text: str) -> str: return _c("95", text)
def bright_cyan(text: str)    -> str: return _c("96", text)

# ── Semantic aliases ──────────────────────────────────────────────
def ok(text: str)      -> str: return bright_green(text)
def warn(text: str)    -> str: return bright_yellow(text)
def error(text: str)   -> str: return bright_red(text)
def info(text: str)    -> str: return cyan(text)
def header(text: str)  -> str: return bold(bright_cyan(text))
def label(text: str)   -> str: return bold(white(text))
def muted(text: str)   -> str: return dim(text)
def link(text: str)    -> str: return _c("4;34", text)   # underlined blue