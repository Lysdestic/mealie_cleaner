"""
steps/audit.py  —  Step 1: Recipe Audit

Dumps every recipe with tags, categories, ingredients, and a snippet of
instructions. Pipe to a file and paste into an LLM for review.

Usage:
    python3 mealie_suite.py --step audit > audit.txt
"""
from __future__ import annotations

import re

from core import req, get_all, fail


def step_audit() -> None:
    print("\n▶ STEP 1: RECIPE AUDIT\n")
    print("Tip: pipe output to a file:  python3 mealie_suite.py --step audit > audit.txt")
    print("Then paste into Claude and ask it to review tags/categories.\n")

    recipes = get_all("/api/recipes")
    if not recipes:
        fail("No recipes returned.")

    recipes_sorted = sorted(recipes, key=lambda r: r["name"].lower())
    print(f"# MEALIE RECIPE AUDIT — {len(recipes_sorted)} recipes")
    print("# " + "=" * 70)
    print()

    for i, summary in enumerate(recipes_sorted, 1):
        title = summary["name"]
        slug  = summary["slug"]

        try:
            detail = req("GET", f"/api/recipes/{slug}")
        except Exception as e:
            print(f"[{i}] ERROR fetching {title}: {e}\n")
            continue

        categories  = [c["name"] for c in detail.get("recipeCategory", [])]
        tags        = [t["name"] for t in detail.get("tags", [])]
        description = (detail.get("description") or "").strip()[:150]
        total_time  = detail.get("totalTime", "") or ""
        servings    = detail.get("recipeServings") or detail.get("recipeYieldQuantity") or ""

        ingredients = []
        for ing in detail.get("recipeIngredient", []):
            d = ing.get("display", "").strip()
            if d:
                ingredients.append(d)
            elif ing.get("food"):
                ingredients.append(ing["food"].get("name", ""))

        inst_parts = []
        for step in detail.get("recipeInstructions", []):
            text = re.sub(r"<[^>]+>", " ", step.get("text", "")).strip()
            text = re.sub(r"\s+", " ", text)
            if text:
                inst_parts.append(text)
        full_inst = " | ".join(inst_parts)
        instructions = full_inst[:400] + ("..." if len(full_inst) > 400 else "")

        print(f"[{i}] {title}")
        print(f"     slug        : {slug}")
        print(f"     time        : {total_time}  |  servings: {servings}")
        print(f"     description : {description}")
        print(f"     categories  : {categories if categories else '(none)'}")
        print(f"     tags        : {tags if tags else '(none)'}")
        print(f"     ingredients : {', '.join(ingredients[:20])}")
        if instructions:
            print(f"     instructions: {instructions}")
        print()

    print("# END OF AUDIT")
    print(f"\n✓ {len(recipes_sorted)} recipes listed.")
    print("  Paste into Claude → ask it to review tags/categories → use output to update data/recipe_map.py")
