"""
steps/sync.py  —  Step 4: Sync Tags → Categories

For every recipe, if a tag name matches a category name, ensure that
category is also assigned to the recipe. Keeps the Tags filter and
the Categories filter in sync so both work correctly in Mealie.
"""
from __future__ import annotations

import sys

from core import req, get_all, normalize, dry_run_banner, is_dry_run, summary


def step_sync() -> None:
    print("\n▶ STEP 4: SYNC TAGS → CATEGORIES\n")
    if is_dry_run():
        dry_run_banner()

    all_categories = get_all("/api/organizers/categories")
    cat_by_norm    = {normalize(c["name"]): c for c in all_categories}
    print(f"Categories: {sorted(c['name'] for c in all_categories)}\n")

    recipes = get_all("/api/recipes")
    updated = skipped = errors = 0

    for recipe in sorted(recipes, key=lambda r: r["name"].lower()):
        title = recipe["name"]
        slug  = recipe["slug"]

        try:
            detail = req("GET", f"/api/recipes/{slug}")
        except Exception as e:
            print(f"  ERROR fetching {title}: {e}", file=sys.stderr)
            errors += 1
            continue

        current_tags     = detail.get("tags", [])
        current_cats     = detail.get("recipeCategory", [])
        current_cat_norm = {normalize(c["name"]) for c in current_cats}

        cats_to_add = [
            cat_by_norm[normalize(tag["name"])]
            for tag in current_tags
            if normalize(tag["name"]) in cat_by_norm
            and normalize(tag["name"]) not in current_cat_norm
        ]

        if not cats_to_add:
            skipped += 1
            continue

        adding = [c["name"] for c in cats_to_add]
        new_payload = current_cats + [
            {"id": c["id"], "name": c["name"], "slug": c["slug"]}
            for c in cats_to_add
        ]

        if is_dry_run():
            print(f"  {title} → would add: {adding}")
            updated += 1
            continue

        try:
            req("PATCH", f"/api/recipes/{slug}", {"recipeCategory": new_payload})
            print(f"  ✓ {title} — added: {adding}")
            updated += 1
            summary.add("sync", f"{title} → categories added: {adding}")
        except Exception as e:
            print(f"  ✗ {title}: {e}", file=sys.stderr)
            errors += 1

    print(f"\n✓ Sync complete.")
    print(f"  Updated : {updated}")
    print(f"  Skipped : {skipped}  (already in sync)")
    print(f"  Errors  : {errors}")
    summary.add("sync", f"Total: {updated} updated, {skipped} already in sync, {errors} errors")