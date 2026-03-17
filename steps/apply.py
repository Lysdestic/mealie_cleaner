"""
steps/apply.py  —  Step 3: Apply Tag & Category Map

Reads RECIPE_MAP from data/recipe_map.py and applies the defined tags
and categories to every recipe in the map via PATCH /api/recipes/{slug}.

Any tags or categories in the map that don't yet exist in Mealie are
created automatically before the apply run begins.

To add or update a recipe's tags: edit data/recipe_map.py.
To add new tags or categories:    edit data/taxonomy.py first, then here.
"""
from __future__ import annotations

import sys

import json
import os

from core import req, get_all, normalize_slug, dry_run_banner, is_dry_run, summary
from data import RECIPE_MAP, CANONICAL_TAGS, KEEP_CATEGORIES

_ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RECIPE_MAP  = os.path.join(_ROOT, "userdata", "recipe_map.json")


def _prompt_recipe_map(stubs: list[tuple[str, str]]) -> None:
    """Interactively assign tags and categories for unmapped recipes."""
    try:
        with open(_RECIPE_MAP, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  WARNING: could not read recipe_map.json: {e}", file=sys.stderr)
        return

    # Load canonical sets for validation
    from data import CANONICAL_TAGS, KEEP_CATEGORIES

    from core import color

    tag_list  = sorted(CANONICAL_TAGS)
    cat_list  = sorted(KEEP_CATEGORIES)

    def _print_numbered(label: str, items: list[str], cols: int = 4) -> None:
        print(f"\n  {color.bold(label)}")
        for i, item in enumerate(items, 1):
            entry = f"  {color.cyan(str(i).rjust(2))}. {item}"
            print(entry)
        print()

    def _pick_from_list(prompt: str, items: list[str], current: list[str]) -> list[str]:
        """Let user pick by number, comma-separated. Enter = keep current."""
        current_nums = []
        for c in current:
            if c in items:
                current_nums.append(str(items.index(c) + 1))
        default_str = ", ".join(current_nums) if current_nums else ""
        hint = f" [{color.muted(default_str)}]" if default_str else ""
        try:
            raw = input(f"    {prompt}{hint}: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return current
        if not raw:
            return current
        chosen = []
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(items):
                    chosen.append(items[idx])
                else:
                    print(f"    {color.warn(f'Ignoring out-of-range number: {part}')}")
            else:
                # Allow typing a name directly too
                if part:
                    chosen.append(part)
        return chosen

    print(f"\n  {color.bold(color.bright_cyan(f'{len(stubs)} recipe(s) not in map'))} — review and confirm tags/categories.")
    print(f"  {color.muted('Enter numbers (comma-separated) to select. Press Enter to accept current values.')}")

    _print_numbered("Available tags:", tag_list)
    _print_numbered("Available categories:", cat_list)

    updated = []
    for title, slug in stubs:
        if slug in data:
            continue

        current_tags: list[str] = []
        current_cats: list[str] = []
        try:
            detail = req("GET", f"/api/recipes/{slug}")
            current_tags = [t["name"] for t in detail.get("tags", [])]
            current_cats = [c["name"] for c in detail.get("recipeCategory", [])]
        except Exception:
            pass

        print(f"  {color.bold(color.bright_cyan('──'))} {color.bold(title)}  {color.muted(f'({slug})')}")
        if current_tags:
            print(f"     {color.label('Current tags')}      : {color.muted(str(current_tags))}")
        if current_cats:
            print(f"     {color.label('Current categories')}: {color.muted(str(current_cats))}")

        tags = _pick_from_list("Tags (numbers or names)", tag_list, current_tags)
        cats = _pick_from_list("Categories (numbers or names)", cat_list, current_cats)

        for t in tags:
            if t not in CANONICAL_TAGS:
                print(f"    {color.warn(f'WARNING: {t!r} not in taxonomy — add to userdata/taxonomy.json')}")
        for c in cats:
            if c not in KEEP_CATEGORIES:
                print(f"    {color.warn(f'WARNING: {c!r} not in taxonomy — add to userdata/taxonomy.json')}")

        data[slug] = {"tags": tags, "categories": cats}
        updated.append(title)
        print(f"    {color.ok('✓ Saved')}\n")

    if updated:
        try:
            with open(_RECIPE_MAP, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"\n  userdata/recipe_map.json updated ({len(updated)} recipe(s) added).")
            print(f"  Run step 3 again to apply the new assignments.")
        except Exception as e:
            print(f"  WARNING: could not write recipe_map.json: {e}", file=sys.stderr)


def _ensure_tags(needed: set[str], tag_lookup: dict, tag_by_slug: dict) -> None:
    """Create any tags that are in the map but missing from Mealie."""
    created = 0
    for name in sorted(needed):
        if tag_lookup.get(name) or tag_by_slug.get(normalize_slug(name)):
            continue
        if is_dry_run():
            print(f"  [DRY RUN] would create tag: {name!r}")
            continue
        try:
            new_tag = req("POST", "/api/organizers/tags", {"name": name})
            if new_tag and new_tag.get("id"):
                tag_lookup[new_tag["name"]] = new_tag
                tag_by_slug[normalize_slug(new_tag["name"])] = new_tag
                print(f"  created tag: {name!r}")
                created += 1
                summary.add("apply", f"Tag created in Mealie: {name!r}")
        except Exception as e:
            print(f"  ERROR creating tag {name!r}: {e}", file=sys.stderr)
    if created:
        print(f"  {created} tag(s) created.\n")


def _ensure_categories(needed: set[str], cat_lookup: dict, cat_by_slug: dict) -> None:
    """Create any categories that are in the map but missing from Mealie."""
    created = 0
    for name in sorted(needed):
        if cat_lookup.get(name) or cat_by_slug.get(normalize_slug(name)):
            continue
        if is_dry_run():
            print(f"  [DRY RUN] would create category: {name!r}")
            continue
        try:
            new_cat = req("POST", "/api/organizers/categories", {"name": name})
            if new_cat and new_cat.get("id"):
                cat_lookup[new_cat["name"]] = new_cat
                cat_by_slug[normalize_slug(new_cat["name"])] = new_cat
                print(f"  created category: {name!r}")
                created += 1
                summary.add("apply", f"Category created in Mealie: {name!r}")
        except Exception as e:
            print(f"  ERROR creating category {name!r}: {e}", file=sys.stderr)
    if created:
        print(f"  {created} category/categories created.\n")


def step_apply() -> None:
    print("\n▶ STEP 3: APPLY TAG & CATEGORY MAP\n")
    if is_dry_run():
        dry_run_banner()

    # Validate all map entries against taxonomy before touching anything
    errors_found = []
    for slug, entry in RECIPE_MAP.items():
        for tag in entry["tags"]:
            if tag not in CANONICAL_TAGS:
                errors_found.append(f"  {slug}: unknown tag {tag!r}")
        for cat in entry["categories"]:
            if cat and cat not in KEEP_CATEGORIES:
                errors_found.append(f"  {slug}: unknown category {cat!r}")
    if errors_found:
        print("VALIDATION ERRORS — fix data/recipe_map.py before running:")
        print("(All tags must be in CANONICAL_TAGS and categories in KEEP_CATEGORIES")
        print(" in data/taxonomy.py)\n")
        for e in errors_found:
            print(e)
        return

    # Collect all tags and categories actually used in the map
    all_tags_needed  = {tag for e in RECIPE_MAP.values() for tag in e["tags"]}
    all_cats_needed  = {cat for e in RECIPE_MAP.values() for cat in e["categories"] if cat}

    # Fetch current organizers from Mealie
    all_tags = get_all("/api/organizers/tags")
    tag_lookup   = {t["name"]: t for t in all_tags}
    tag_by_slug  = {normalize_slug(t["name"]): t for t in all_tags}

    all_cats = get_all("/api/organizers/categories")
    cat_lookup   = {c["name"]: c for c in all_cats}
    cat_by_slug  = {normalize_slug(c["name"]): c for c in all_cats}

    # Auto-create anything missing
    missing_tags = {n for n in all_tags_needed
                    if not tag_lookup.get(n) and not tag_by_slug.get(normalize_slug(n))}
    missing_cats = {n for n in all_cats_needed
                    if not cat_lookup.get(n) and not cat_by_slug.get(normalize_slug(n))}

    if missing_tags:
        print(f"  Creating {len(missing_tags)} missing tag(s):")
        _ensure_tags(missing_tags, tag_lookup, tag_by_slug)
    if missing_cats:
        print(f"  Creating {len(missing_cats)} missing category/categories:")
        _ensure_categories(missing_cats, cat_lookup, cat_by_slug)

    def resolve_tag(name: str) -> dict | None:
        obj = tag_lookup.get(name) or tag_by_slug.get(normalize_slug(name))
        if not obj:
            print(f"  WARNING: tag not found after creation attempt: {name!r}", file=sys.stderr)
        return obj

    def resolve_cat(name: str) -> dict | None:
        obj = cat_lookup.get(name) or cat_by_slug.get(normalize_slug(name))
        if not obj:
            print(f"  WARNING: category not found after creation attempt: {name!r}", file=sys.stderr)
        return obj

    # Apply
    all_recipes = get_all("/api/recipes")
    updated = errors = 0
    not_in_map = []

    for recipe in sorted(all_recipes, key=lambda r: r["name"].lower()):
        title = recipe["name"]
        slug  = recipe["slug"]

        if slug not in RECIPE_MAP:
            not_in_map.append((title, slug))
            continue

        entry = RECIPE_MAP[slug]
        tag_payload = [
            {"id": o["id"], "name": o["name"], "slug": o["slug"]}
            for name in entry["tags"]
            if (o := resolve_tag(name))
        ]
        cat_payload = [
            {"id": o["id"], "name": o["name"], "slug": o["slug"]}
            for name in entry["categories"]
            if (o := resolve_cat(name))
        ]

        if is_dry_run():
            print(f"  {title}")
            print(f"    tags       : {entry['tags']}")
            print(f"    categories : {entry['categories']}")
            updated += 1
            continue

        try:
            req("PATCH", f"/api/recipes/{slug}", {
                "tags": tag_payload,
                "recipeCategory": cat_payload,
            })
            print(f"  ✓ {title}")
            updated += 1
            summary.add("apply", f"Recipe updated: {title}")
        except Exception as e:
            print(f"  ✗ {title}: {e}", file=sys.stderr)
            errors += 1

    print(f"\n✓ Apply complete.")
    print(f"  Updated : {updated}")
    print(f"  Errors  : {errors}")
    summary.add("apply", f"Total: {updated} updated, {errors} errors")
    if not_in_map and not is_dry_run():
        _prompt_recipe_map(not_in_map)
    elif not_in_map and is_dry_run():
        print(f"\n  Not in map ({len(not_in_map)}) — would prompt for tags/categories:")
        for title, slug in not_in_map:
            print(f"    ? {title}  ({slug})")