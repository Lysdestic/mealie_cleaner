"""
data/loader.py

Loads userdata JSON files at runtime and exposes them as the same
Python objects the rest of the codebase expects.

userdata/ is gitignored — it contains your instance-specific data.
userdata.example/ is committed — it shows the expected structure.

Setup:
    cp -r userdata.example userdata
    # edit each file in userdata/ to match your Mealie instance
"""
from __future__ import annotations

import json
import os
import sys

# Path to the userdata directory (sibling of this file's parent)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_USERDATA = os.path.join(_ROOT, "userdata")
_EXAMPLE  = os.path.join(_ROOT, "userdata.example")


def _load(filename: str) -> dict:
    path = os.path.join(_USERDATA, filename)
    if not os.path.isfile(path):
        example = os.path.join(_EXAMPLE, filename)
        print(
            f"\n✗ Missing userdata file: {path}\n"
            f"  Copy the example to get started:\n"
            f"    cp -r userdata.example userdata\n"
            f"  Then edit userdata/{filename} with your own data.",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # Strip _comment and _instructions keys — they're docs, not data
    return {k: v for k, v in data.items() if not k.startswith("_")}


def load_taxonomy() -> tuple[set[str], set[str]]:
    """Returns (CANONICAL_TAGS, KEEP_CATEGORIES)."""
    data = _load("taxonomy.json")
    tags       = set(data.get("tags", []))
    categories = set(data.get("categories", []))
    if not tags:
        print("WARNING: taxonomy.json has no tags defined.", file=sys.stderr)
    if not categories:
        print("WARNING: taxonomy.json has no categories defined.", file=sys.stderr)
    return tags, categories


def load_recipe_map() -> dict[str, dict[str, list[str]]]:
    """Returns RECIPE_MAP: {slug: {tags: [...], categories: [...]}}."""
    data = _load("recipe_map.json")
    return data


def load_food_labels() -> tuple[dict[str, str], list[str], list[str]]:
    """Returns (FOOD_LABELS, JUNK_FOOD_IDS, JUNK_FOOD_PATTERNS)."""
    data = _load("food_labels.json")
    labels   = data.get("food_labels", {})
    junk_ids = data.get("junk_food_ids", [])
    patterns = data.get("junk_food_patterns", [r"^---", r"---$", r"^\s*$", r"^-+\s*$"])
    return labels, junk_ids, patterns
