"""
steps/freetext.py  —  Step 6: Fix Free-Text Ingredients

Finds recipe ingredients that have no structured food object (free-text
only) and runs them through Mealie's built-in ingredient parser to
create proper food/unit/quantity links. This ensures they appear
correctly in shopping lists.

Recipes with incompatible ingredient formats (e.g. "Dough — X g flour")
are excluded via SKIP_SLUGS. Known bad parser outputs are corrected via
TEXT_REWRITES and FOOD_NAME_OVERRIDES.

To exclude a recipe:  add its slug to SKIP_SLUGS
To fix a bad parse:   add the display text to TEXT_REWRITES or FOOD_NAME_OVERRIDES
"""
from __future__ import annotations

import sys
import time

from core import req, get_all, dry_run_banner, is_dry_run, summary, color
from data import FREETEXT_SKIP_SLUGS

# SKIP_SLUGS is loaded from userdata/recipe_map.json ("freetext_skip_slugs" key)
# Add slugs there for any recipe whose ingredient format is parser-incompatible
# (e.g. "Dough — 180g flour" style prefixes that confuse the parser)
SKIP_SLUGS = FREETEXT_SKIP_SLUGS

# ── Pre-parse rewrites ────────────────────────────────────────────
# Applied to ingredient display text before sending to the parser.
# Use this to fix badly formatted strings that confuse the parser.
TEXT_REWRITES: dict[str, str] = {
    "additional vegetable oil for frying eggs": "1 teaspoon vegetable oil",
    "diced leftover chicken, pork, shrimp, or Spam": "leftover protein optional",
    "1 cup red bell pepper, diced":              "1 cup red bell pepper",
    "1 lb andouille sausage, sliced":            "1 lb andouille sausage",
    "1 tbsp dark sweet soy sauce (kecap manis)": "1 tbsp dark sweet soy sauce",
}

# ── Post-parse food name overrides ───────────────────────────────
# Applied after parsing when the parser returns the wrong food name.
# Key = rewritten text sent to parser. Value = correct food name.
FOOD_NAME_OVERRIDES: dict[str, str] = {
    "1 cup red bell pepper": "red bell pepper",
    "1 lb andouille sausage": "andouille sausage",
}

# ── Skip patterns for non-ingredient lines ───────────────────────
SKIP_PATTERNS: list[str] = [
    r"^---", r"---$", r"^\s*$",
    r"^for serving$", r"^optional$", r"^to taste$", r"^as needed$",
    r"^1 teaspoon$", r"^leftover protein optional$",
]

# ── In-memory food resolution cache ──────────────────────────────
_food_cache: dict[str, dict] = {}


def _should_skip(text: str) -> bool:
    import re
    return any(re.search(p, text.strip(), re.IGNORECASE) for p in SKIP_PATTERNS)


def _search_food(name: str) -> dict | None:
    """Search Mealie foods by name with exact-match check across pages."""
    name_lower = name.strip().lower()
    page = 1
    while True:
        try:
            results = req("GET", "/api/foods", params={"search": name, "perPage": 50, "page": page})
        except Exception:
            return None
        for food in results.get("items", []):
            if food.get("name", "").strip().lower() == name_lower:
                return food
        total = (results.get("total_pages") or results.get("pageCount")
                 or results.get("totalPages") or page)
        if not results.get("items") or page >= total:
            break
        page += 1
    return None


def _ensure_food(name: str) -> dict | None:
    """Return a Mealie food object by name, creating it if it doesn't exist."""
    name = name.strip()
    if not name:
        return None
    key = name.lower()
    if key in _food_cache:
        return _food_cache[key]

    found = _search_food(name)
    if found:
        _food_cache[key] = found
        return found

    try:
        created = req("POST", "/api/foods", {"name": name})
        if created and created.get("id"):
            print(f"    created food: {name!r}")
            _food_cache[key] = created
            return created
    except Exception as e:
        if "400" in str(e):
            # UNIQUE constraint — food exists but search missed it; scan broadly
            try:
                all_foods = req("GET", "/api/foods", params={"perPage": 500, "page": 1})
                for food in all_foods.get("items", []):
                    if food.get("name", "").strip().lower() == key:
                        _food_cache[key] = food
                        return food
            except Exception:
                pass
        print(f"    WARNING: could not resolve food {name!r}: {e}", file=sys.stderr)
    return None


def _parse_text(text: str) -> dict | None:
    try:
        return req("POST", "/api/parser/ingredient", {"ingredient": text})
    except Exception as e:
        print(f"    parser error for {text!r}: {e}", file=sys.stderr)
        return None


def step_freetext() -> None:
    print(f"\n{color.header('▶ STEP 6: FIX FREE-TEXT INGREDIENTS')}\n")
    if is_dry_run():
        dry_run_banner()

    recipes = get_all("/api/recipes")
    total_fixed = total_skipped = total_errors = total_ok = 0

    for recipe in sorted(recipes, key=lambda r: r["name"].lower()):
        title = recipe["name"]
        slug  = recipe["slug"]

        if slug in SKIP_SLUGS:
            print(f"  {color.muted('SKIPPED:')} {color.muted(title)}  {color.muted('(ingredient format not parser-compatible)')}")
            continue

        try:
            detail = req("GET", f"/api/recipes/{slug}")
        except Exception as e:
            print(f"  ERROR fetching {title}: {e}", file=sys.stderr)
            total_errors += 1
            continue

        # Find ingredients with no food object
        problem_ings: list[tuple[dict, str]] = []
        for ing in detail.get("recipeIngredient", []):
            if ing.get("food"):
                total_ok += 1
                continue
            display = (ing.get("display") or "").strip()
            note    = (ing.get("note") or "").strip()
            raw     = display or note
            text    = TEXT_REWRITES.get(raw, raw)
            if not text or _should_skip(text):
                total_skipped += 1
                continue
            problem_ings.append((ing, text))

        if not problem_ings:
            continue

        print(f"\n  {title}  ({len(problem_ings)} to fix)")
        updated_ings = list(detail.get("recipeIngredient", []))
        changed = False

        for ing, text in problem_ings:
            parsed = _parse_text(text)
            if not parsed:
                total_errors += 1
                continue

            parsed_ing  = parsed.get("ingredient", parsed)
            food        = parsed_ing.get("food")
            unit        = parsed_ing.get("unit")
            qty         = parsed_ing.get("quantity")
            note_parsed = parsed_ing.get("note", "")

            if not food:
                print(f"    {color.warn('NO FOOD PARSED:')} {repr(text)}")
                total_skipped += 1
                continue

            # Post-process: strip whitespace and apply name overrides
            if food.get("name"):
                food["name"] = food["name"].strip()
            if text in FOOD_NAME_OVERRIDES:
                food["name"] = FOOD_NAME_OVERRIDES[text]

            if is_dry_run():
                print(f"    {text!r}")
                print(f"      -> food={food.get('name')!r}  unit={unit.get('name') if unit else None}  qty={qty}")
                changed = True
                total_fixed += 1
                continue

            # Resolve food to a valid Mealie food object with a real ID
            food = _ensure_food(food.get("name", ""))
            if not food:
                print(f"    SKIP (could not resolve food for {text!r})")
                total_skipped += 1
                continue

            ref_id = ing.get("referenceId")
            for i, full_ing in enumerate(updated_ings):
                if full_ing.get("referenceId") == ref_id:
                    updated_ings[i] = {
                        **full_ing,
                        "food":     food,
                        "unit":     unit,
                        "quantity": qty if qty is not None else full_ing.get("quantity"),
                        "note":     note_parsed or full_ing.get("note", ""),
                    }
                    changed = True
                    total_fixed += 1
                    break

            time.sleep(0.1)

        if changed and not is_dry_run():
            try:
                req("PATCH", f"/api/recipes/{slug}", {"recipeIngredient": updated_ings})
                print(f"    {color.ok('✓ patched')}")
            except Exception as e:
                print(f"    ✗ ERROR patching {title}: {e}", file=sys.stderr)
                total_errors += 1

        time.sleep(0.1)

    print(f"\n{color.ok('✓')} {color.bold('Free-text fix complete.')}")
    print(f"  Fixed            : {color.ok(str(total_fixed))}")
    print(f"  Skipped          : {color.muted(str(total_skipped))}  (headers, garnishes, optionals)")
    print(f"  Already had food : {color.muted(str(total_ok))}")
    print(f"  Errors           : {color.error(str(total_errors)) if total_errors else color.muted('0')}")
    summary.add("freetext", f"Total: {total_fixed} fixed, {total_skipped} skipped, {total_errors} errors")
    if SKIP_SLUGS:
        print()
        print(f"  NOTE: {len(SKIP_SLUGS)} recipe(s) were skipped (parser-incompatible format).")
        print(f"  To remove from skip list, edit 'freetext_skip_slugs' in userdata/recipe_map.json")