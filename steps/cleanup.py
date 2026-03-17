"""
steps/cleanup.py  —  Step 2: Tag & Category Cleanup

Finds tags and categories in Mealie that aren't in the canonical sets
defined in userdata/taxonomy.json and walks you through each one:

  k = keep  — adds it to userdata/taxonomy.json automatically
  d = delete — removes it from Mealie
  s = skip   — leaves it in Mealie without adding to taxonomy
"""
from __future__ import annotations

import json
import os
import sys

from core import req, get_all, normalize, dry_run_banner, is_dry_run

# Path to taxonomy.json
_ROOT         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TAXONOMY     = os.path.join(_ROOT, "userdata", "taxonomy.json")


def _load_taxonomy_json() -> dict:
    with open(_TAXONOMY, encoding="utf-8") as f:
        return json.load(f)


def _save_taxonomy_json(data: dict) -> None:
    with open(_TAXONOMY, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _prompt_decision(name: str, kind: str) -> str:
    """Ask the user what to do. Returns 'keep', 'delete', or 'skip'."""
    print(f"\n  Non-canonical {kind}: {name!r}")
    print(f"    k = keep   (add to userdata/taxonomy.json automatically)")
    print(f"    d = delete (remove from Mealie)")
    print(f"    s = skip   (leave in Mealie, decide later)")
    while True:
        try:
            choice = input("    Choice [k/d/s]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return "skip"
        if choice in ("k", "d", "s"):
            return {"k": "keep", "d": "delete", "s": "skip"}[choice]
        print("    Please enter k, d, or s.")


def step_cleanup() -> None:
    print("\n▶ STEP 2: TAG & CATEGORY CLEANUP\n")
    if is_dry_run():
        dry_run_banner()

    kept_cats, kept_tags = _cleanup_categories(), _cleanup_tags()

    # Write all kept items to taxonomy.json in one shot at the end
    if (kept_cats or kept_tags) and not is_dry_run():
        try:
            tax = _load_taxonomy_json()
            existing_tags = set(tax.get("tags", []))
            existing_cats = set(tax.get("categories", []))

            new_tags = sorted(existing_tags | set(kept_tags))
            new_cats = sorted(existing_cats | set(kept_cats))

            tax["tags"]       = new_tags
            tax["categories"] = new_cats
            _save_taxonomy_json(tax)

            print("\n" + "─" * 60)
            print("  ✓ userdata/taxonomy.json updated automatically.")
            if kept_tags:
                print(f"    Tags added      : {sorted(kept_tags)}")
            if kept_cats:
                print(f"    Categories added: {sorted(kept_cats)}")
            print()
        except Exception as e:
            print(f"\n  ERROR writing taxonomy.json: {e}", file=sys.stderr)
            print("  Add these manually:")
            if kept_tags:
                print(f"    Tags      : {sorted(kept_tags)}")
            if kept_cats:
                print(f"    Categories: {sorted(kept_cats)}")

    print("\n✓ Cleanup complete.")


def _cleanup_categories() -> list[str]:
    """Returns list of category names the user chose to keep."""
    from data import KEEP_CATEGORIES

    print("\n── Categories ──")
    all_cats  = get_all("/api/organizers/categories")
    keep_norm = {normalize(c) for c in KEEP_CATEGORIES}
    to_delete = [c for c in all_cats if normalize(c["name"]) not in keep_norm]
    to_keep   = [c for c in all_cats if normalize(c["name"]) in keep_norm]

    print(f"Found {len(all_cats)} categories.")
    print(f"Canonical ({len(to_keep)}): {sorted(c['name'] for c in to_keep)}")

    if not to_delete:
        print("No non-canonical categories found.")
        return []

    print(f"\n{len(to_delete)} non-canonical category/categories found.")

    kept = []
    deleted = errors = skipped = 0

    for cat in sorted(to_delete, key=lambda x: x["name"]):
        if is_dry_run():
            print(f"  [DRY RUN] would prompt about category: {cat['name']!r}")
            continue

        decision = _prompt_decision(cat["name"], "category")

        if decision == "keep":
            print(f"    → Will add {cat['name']!r} to taxonomy.json")
            kept.append(cat["name"])
        elif decision == "delete":
            try:
                req("DELETE", f"/api/organizers/categories/{cat['id']}")
                print(f"    → Deleted {cat['name']!r}")
                deleted += 1
            except Exception as e:
                print(f"    → ERROR deleting {cat['name']!r}: {e}", file=sys.stderr)
                errors += 1
        else:
            print(f"    → Skipped {cat['name']!r}")
            skipped += 1

    print(f"\n  Categories — kept: {len(kept)}  deleted: {deleted}  "
          f"skipped: {skipped}  errors: {errors}")
    return kept


def _cleanup_tags() -> list[str]:
    """Returns list of tag names the user chose to keep."""
    from data import CANONICAL_TAGS

    print("\n── Tags ──")
    all_tags       = get_all("/api/organizers/tags")
    keep_norm_tags = {normalize(t) for t in CANONICAL_TAGS}
    to_delete      = [t for t in all_tags if normalize(t["name"]) not in keep_norm_tags]
    to_keep        = [t for t in all_tags if normalize(t["name"]) in keep_norm_tags]

    print(f"Found {len(all_tags)} tags.")
    print(f"Keeping {len(to_keep)} canonical tags.")

    if not to_delete:
        print("No non-canonical tags found.")
        return []

    print(f"\n{len(to_delete)} non-canonical tag(s) found.")

    kept = []
    deleted = errors = skipped = 0

    for tag in sorted(to_delete, key=lambda x: x["name"]):
        if is_dry_run():
            print(f"  [DRY RUN] would prompt about tag: {tag['name']!r}")
            continue

        decision = _prompt_decision(tag["name"], "tag")

        if decision == "keep":
            print(f"    → Will add {tag['name']!r} to taxonomy.json")
            kept.append(tag["name"])
        elif decision == "delete":
            try:
                req("DELETE", f"/api/organizers/tags/{tag['id']}")
                print(f"    → Deleted {tag['name']!r}")
                deleted += 1
            except Exception as e:
                print(f"    → ERROR deleting {tag['name']!r}: {e}", file=sys.stderr)
                errors += 1
        else:
            print(f"    → Skipped {tag['name']!r}")
            skipped += 1

    print(f"\n  Tags — kept: {len(kept)}  deleted: {deleted}  "
          f"skipped: {skipped}  errors: {errors}")
    return kept