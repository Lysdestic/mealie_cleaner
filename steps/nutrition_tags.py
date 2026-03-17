"""
steps/nutrition_tags.py  —  Step 8: Nutrition Tag Rules

Applies tags to recipes automatically based on nutrition thresholds.
Rules are stored in userdata/nutrition_rules.json and persist between runs.

EXAMPLES
────────
  protein ≥ 20g  →  tag "High Protein"
  calories ≤ 400  →  tag "Light Meal"
  fiberContent ≥ 8  →  tag "High Fiber"
  sodiumContent ≤ 500  →  tag "Low Sodium"

FLOW
────
  [a] Run all rules  — scans every recipe with nutrition data, applies/flags tags
  [r] Add a rule     — interactive prompt to define a new rule
  [d] Delete a rule  — remove a rule by number
  [0] Back to menu

FLAGGING
────────
  If a recipe already has a tag from a rule but no longer meets the threshold,
  it's flagged in the session summary for your review — never auto-removed.

TAXONOMY
────────
  New tags are added to userdata/taxonomy.json automatically when a rule is created.
"""
from __future__ import annotations

import json
import os
import sys

from core import req, get_all, get_recipe_url, color, summary, is_dry_run
from data import NUTRITION_RULES

_ROOT            = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RULES_FILE      = os.path.join(_ROOT, "userdata", "nutrition_rules.json")
_TAXONOMY_FILE   = os.path.join(_ROOT, "userdata", "taxonomy.json")

NUTRITION_FIELDS = {
    "calories":              "Calories (kcal)",
    "fatContent":            "Fat (g)",
    "proteinContent":        "Protein (g)",
    "carbohydrateContent":   "Carbohydrates (g)",
    "fiberContent":          "Fiber (g)",
    "sodiumContent":         "Sodium (mg)",
    "sugarContent":          "Sugar (g)",
}

OPERATORS = {">=": "≥", "<=": "≤"}


# ── File helpers ──────────────────────────────────────────────────

def _load_rules() -> list[dict]:
    if not os.path.isfile(_RULES_FILE):
        _save_rules([])
        return []
    with open(_RULES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("rules", [])


def _save_rules(rules: list[dict]) -> None:
    try:
        if os.path.isfile(_RULES_FILE):
            with open(_RULES_FILE, encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
        data["rules"] = rules
        with open(_RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"  {color.error('ERROR')} saving rules: {e}", file=sys.stderr)


def _add_tag_to_taxonomy(tag: str) -> None:
    """Add a tag to userdata/taxonomy.json if not already present."""
    try:
        with open(_TAXONOMY_FILE, encoding="utf-8") as f:
            data = json.load(f)
        tags = data.get("tags", [])
        if tag not in tags:
            tags.append(tag)
            data["tags"] = sorted(tags)
            with open(_TAXONOMY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"  {color.ok('✓')} Added {color.bright_cyan(repr(tag))} to taxonomy.json")
    except Exception as e:
        print(f"  {color.warn('WARNING')} could not update taxonomy.json: {e}", file=sys.stderr)


def _ensure_tag_in_mealie(tag: str) -> dict | None:
    """Look up tag in Mealie, create if missing. Returns tag object or None."""
    try:
        resp = req("GET", "/api/organizers/tags", params={"search": tag, "perPage": 20})
        found = next((t for t in resp.get("items", [])
                      if t["name"].lower() == tag.lower()), None)
        if found:
            return found
        new_tag = req("POST", "/api/organizers/tags", {"name": tag})
        if new_tag and new_tag.get("id"):
            print(f"  {color.ok('✓')} Created tag {color.bright_cyan(repr(tag))} in Mealie")
            return new_tag
    except Exception as e:
        print(f"  {color.error('ERROR')} ensuring tag {tag!r}: {e}", file=sys.stderr)
    return None


# ── Rule display ──────────────────────────────────────────────────

def _rule_str(rule: dict) -> str:
    field    = NUTRITION_FIELDS.get(rule["field"], rule["field"])
    operator = OPERATORS.get(rule["operator"], rule["operator"])
    return (f"{color.bright_yellow(field)} "
            f"{color.cyan(operator)} "
            f"{color.bold(str(rule['threshold']))}  "
            f"{color.muted('→')}  tag "
            f"{color.bright_cyan(repr(rule['tag']))}")


def _print_rules(rules: list[dict]) -> None:
    if not rules:
        print(f"  {color.muted('No rules defined yet.')}")
        return
    for i, rule in enumerate(rules, 1):
        print(f"  {color.cyan(str(i).rjust(2))}. {_rule_str(rule)}")


# ── Add / delete rules ────────────────────────────────────────────

def _add_rule(rules: list[dict]) -> list[dict]:
    print(f"\n  {color.bold('Available nutrition fields:')}")
    field_list = list(NUTRITION_FIELDS.items())
    for i, (key, label) in enumerate(field_list, 1):
        print(f"  {color.cyan(str(i).rjust(2))}. {label}")

    try:
        raw = input("\n    Pick field number: ").strip()
        if not raw.isdigit() or not (1 <= int(raw) <= len(field_list)):
            print(f"  {color.warn('Invalid selection.')}")
            return rules
        field_key, field_label = field_list[int(raw) - 1]

        print(f"\n  Operator:")
        print(f"  {color.cyan(' 1')}. ≥  (greater than or equal)")
        print(f"  {color.cyan(' 2')}. ≤  (less than or equal)")
        op_raw = input("    Pick operator: ").strip()
        operator = ">=" if op_raw == "1" else "<=" if op_raw == "2" else None
        if not operator:
            print(f"  {color.warn('Invalid operator.')}")
            return rules

        threshold_raw = input(f"    Threshold value for {field_label}: ").strip()
        threshold = float(threshold_raw)

        tag = input("    Tag to apply (e.g. 'High Protein'): ").strip()
        if not tag:
            print(f"  {color.warn('Tag cannot be empty.')}")
            return rules

    except (KeyboardInterrupt, EOFError, ValueError):
        print(f"\n  {color.muted('Cancelled.')}")
        return rules

    rule = {"field": field_key, "operator": operator,
            "threshold": threshold, "tag": tag}
    rules.append(rule)
    _save_rules(rules)
    _add_tag_to_taxonomy(tag)
    _ensure_tag_in_mealie(tag)
    print(f"\n  {color.ok('✓')} Rule added: {_rule_str(rule)}")
    return rules


def _delete_rule(rules: list[dict]) -> list[dict]:
    if not rules:
        print(f"  {color.muted('No rules to delete.')}")
        return rules
    _print_rules(rules)
    try:
        raw = input("\n    Delete rule number (or 0 to cancel): ").strip()
        idx = int(raw) - 1
        if raw == "0":
            return rules
        if not (0 <= idx < len(rules)):
            print(f"  {color.warn('Invalid number.')}")
            return rules
    except (ValueError, KeyboardInterrupt, EOFError):
        return rules

    removed = rules.pop(idx)
    _save_rules(rules)
    print(f"  {color.ok('✓')} Deleted: {_rule_str(removed)}")
    return rules


# ── Run rules ─────────────────────────────────────────────────────

def _meets(value_str: str, operator: str, threshold: float) -> bool:
    try:
        val = float(str(value_str).strip())
        return val >= threshold if operator == ">=" else val <= threshold
    except (ValueError, TypeError):
        return False


def _run_rules(rules: list[dict]) -> None:
    if not rules:
        print(f"  {color.warn('No rules defined. Add one with [r].')}")
        return

    print(f"\n  {color.bold('Running')} {len(rules)} rule(s) against all recipes...\n")

    # Pre-fetch tag objects for all rule tags
    tag_objects: dict[str, dict] = {}
    for rule in rules:
        tag = rule["tag"]
        if tag not in tag_objects:
            obj = _ensure_tag_in_mealie(tag)
            if obj:
                tag_objects[tag] = obj
            else:
                print(f"  {color.error('✗')} Could not resolve tag {tag!r} — skipping rule")

    recipes = get_all("/api/recipes")
    recipes_sorted = sorted(recipes, key=lambda r: r["name"].lower())

    total_tagged = total_flagged = total_skipped = 0

    for recipe in recipes_sorted:
        title = recipe["name"]
        slug  = recipe["slug"]

        try:
            detail = req("GET", f"/api/recipes/{slug}")
        except Exception as e:
            print(f"  {color.error('ERROR')} fetching {title}: {e}", file=sys.stderr)
            continue

        nutrition = detail.get("nutrition") or {}
        current_tags = detail.get("tags") or []
        current_tag_names = {t["name"] for t in current_tags}

        # Skip recipes with no nutrition data at all
        has_any_nutrition = any(
            str(nutrition.get(f, "") or "").strip()
            for f in NUTRITION_FIELDS
        )
        if not has_any_nutrition:
            total_skipped += 1
            continue

        tags_to_add   = []
        tags_to_flag  = []

        for rule in rules:
            tag      = rule["tag"]
            field    = rule["field"]
            operator = rule["operator"]
            threshold = rule["threshold"]
            tag_obj  = tag_objects.get(tag)

            if not tag_obj:
                continue

            value_str = str(nutrition.get(field, "") or "").strip()
            already_tagged = tag in current_tag_names

            # No nutrition value for this field — skip this rule for this recipe
            if not value_str or value_str in ("0", "0.0"):
                if already_tagged:
                    tags_to_flag.append((tag, field, operator, threshold))
                continue

            meets = _meets(value_str, operator, threshold)

            if meets and not already_tagged:
                tags_to_add.append(tag_obj)
            elif not meets and already_tagged:
                tags_to_flag.append((tag, field, operator, threshold))

        if tags_to_flag:
            for tag, field, operator, threshold in tags_to_flag:
                field_label = NUTRITION_FIELDS.get(field, field)
                op_sym = OPERATORS.get(operator, operator)
                msg = (f"{title} has tag {tag!r} but {field_label} "
                       f"no longer meets {op_sym} {threshold}")
                summary.add("nutrition_tags", f"⚠ REVIEW: {msg}")
                print(f"  {color.warn('⚠')} {color.bold(title)}")
                print(f"    {color.muted(f'Has tag {tag!r} but no longer meets threshold — review manually')}")
                print(f"    {color.link(get_recipe_url(slug))}")
                total_flagged += 1

        if not tags_to_add:
            continue

        tag_names = [t["name"] for t in tags_to_add]

        if is_dry_run():
            print(f"  {color.ok('[DRY RUN]')} {color.bold(title)}")
            print(f"    Would add: {color.bright_cyan(str(tag_names))}")
            total_tagged += 1
            continue

        new_tag_payload = [
            {"id": t["id"], "name": t["name"], "slug": t["slug"]}
            for t in current_tags if t.get("id")
        ] + [
            {"id": t["id"], "name": t["name"], "slug": t["slug"]}
            for t in tags_to_add
        ]

        try:
            req("PATCH", f"/api/recipes/{slug}", {"tags": new_tag_payload})
            print(f"  {color.ok('✓')} {color.bold(title)}")
            print(f"    {color.muted('Tagged:')} {color.bright_cyan(str(tag_names))}")
            summary.add("nutrition_tags", f"Tagged: {title} → {tag_names}")
            total_tagged += 1
        except Exception as e:
            print(f"  {color.error('✗')} {title}: {e}", file=sys.stderr)

    print(f"\n{color.ok('✓')} {color.bold('Nutrition tag run complete.')}")
    print(f"  Tagged   : {color.ok(str(total_tagged))}")
    print(f"  Flagged  : {color.warn(str(total_flagged))}  (review manually — tag no longer meets threshold)")
    print(f"  Skipped  : {color.muted(str(total_skipped))}  (no nutrition data)")
    summary.add("nutrition_tags",
                f"Total: {total_tagged} tagged, {total_flagged} flagged, {total_skipped} skipped")


# ── Main ──────────────────────────────────────────────────────────

def step_nutrition_tags() -> None:
    print(f"\n{color.header('▶ STEP 8: NUTRITION TAG RULES')}\n")
    print(f"  Automatically tag recipes based on nutrition thresholds.")
    print(f"  Rules are saved to userdata/nutrition_rules.json.\n")

    # Use the module-level loaded rules as starting point,
    # then re-read from file after any saves so changes are reflected immediately
    rules = list(NUTRITION_RULES)

    while True:
        print(f"\n  {color.bold('Current rules:')}")
        _print_rules(rules)
        print()
        print(f"  {color.cyan('[a]')} Run all rules now")
        print(f"  {color.cyan('[r]')} Add a new rule")
        print(f"  {color.cyan('[d]')} Delete a rule")
        print(f"  {color.muted('[0]')} Back to menu")

        try:
            choice = input("\n  Choice: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if choice == "0":
            break
        elif choice == "a":
            _run_rules(rules)
            break
        elif choice == "r":
            rules = _add_rule(rules)
            rules = _load_rules()  # re-read after save
        elif choice == "d":
            rules = _delete_rule(rules)
            rules = _load_rules()  # re-read after save
        else:
            print(f"  {color.warn('Invalid choice.')}")