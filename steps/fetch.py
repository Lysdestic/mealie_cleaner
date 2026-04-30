"""
steps/fetch.py  —  Read-only recipe fetch helpers

Implements native equivalents of the old mealie-fetch.sh script:
- list recipe names + slugs
- fetch full recipe JSON by slug
"""
from __future__ import annotations

import json

from core import get_all, req, fail


def step_recipe_list() -> None:
    """Print all recipes as: name<TAB>slug (sorted by name)."""
    print("\n▶ STEP: RECIPE LIST\n")
    recipes = get_all("/api/recipes")
    if not recipes:
        fail("No recipes returned.")

    rows = []
    for recipe in recipes:
        name = (recipe.get("name") or "").replace("\t", " ").strip()
        slug = (recipe.get("slug") or "").strip()
        if slug:
            rows.append((name, slug))

    for name, slug in sorted(rows, key=lambda r: r[0].lower()):
        print(f"{name}\t{slug}")

    print(f"\n✓ {len(rows)} recipes listed.")


def step_recipe_fetch(slugs: list[str] | None = None) -> None:
    """Fetch and print full recipe JSON for one or more slugs."""
    if slugs is None:
        raw = input("Enter one or more recipe slugs (space-separated): ").strip()
        slugs = [s for s in raw.split() if s]

    if not slugs:
        fail("No slugs provided. Use --slugs slug1 slug2 ... with --step recipefetch.")

    payload = [req("GET", f"/api/recipes/{slug}") for slug in slugs]
    print(json.dumps(payload, indent=2, ensure_ascii=True))
