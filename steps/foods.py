"""
steps/foods.py  —  Step 5: Food Label Cleanup

1. Deletes junk food entries (blank rows, --- section headers ---)
2. Assigns labels to all unlabeled foods based on FOOD_LABELS

To label a new food: add it to data/food_labels.py.
To flag a junk entry: add its UUID to JUNK_FOOD_IDS in data/food_labels.py.
"""
from __future__ import annotations

import json
import os
import re
import sys

from core import req, get_all, dry_run_banner, is_dry_run, summary
from data import FOOD_LABELS, JUNK_FOOD_IDS, JUNK_FOOD_PATTERNS

_ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FOOD_LABELS = os.path.join(_ROOT, "userdata", "food_labels.json")


def _prompt_food_labels(unmapped: list[str]) -> None:
    """Interactively assign labels to unmapped foods and save to food_labels.json."""
    try:
        with open(_FOOD_LABELS, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  WARNING: could not read food_labels.json: {e}", file=sys.stderr)
        return

    labels = data.get("food_labels", {})

    # Show available labels for reference
    from core import req, get_all
    try:
        all_labels = get_all("/api/groups/labels")
        label_names = sorted(l["name"] for l in all_labels)
        print(f"\n  Available labels: {label_names}")
    except Exception:
        pass

    print(f"\n  {len(unmapped)} food(s) with no label — assign now.")
    print(f"  (Press Enter to skip a food and leave it unlabeled)\n")

    updated = []
    for name in unmapped:
        if name in labels and labels[name]:
            continue
        try:
            label = input(f"    Label for {name!r}: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if label:
            labels[name] = label
            updated.append(name)
            print(f"    ✓ Saved")
        else:
            print(f"    Skipped")

    if updated:
        data["food_labels"] = labels
        try:
            with open(_FOOD_LABELS, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"\n  userdata/food_labels.json updated ({len(updated)} food(s) labeled).")
            print(f"  Run step 5 again to apply the new labels.")
        except Exception as e:
            print(f"  WARNING: could not write food_labels.json: {e}", file=sys.stderr)


def _is_junk(name: str) -> bool:
    return any(re.search(p, name.strip()) for p in JUNK_FOOD_PATTERNS)


def step_foods() -> None:
    print("\n▶ STEP 5: FOOD LABEL CLEANUP\n")
    if is_dry_run():
        dry_run_banner()

    all_labels   = get_all("/api/groups/labels")
    label_lookup = {l["name"]: l for l in all_labels}

    bad = {v for v in FOOD_LABELS.values() if v not in label_lookup}
    if bad:
        print(f"WARNING: label names not found in Mealie: {bad}", file=sys.stderr)

    all_foods = get_all("/api/foods")
    print(f"Found {len(all_foods)} foods.")

    # ── Delete junk ──────────────────────────────────────────────
    print("\n── Deleting junk entries ──")
    junk_ids = set(JUNK_FOOD_IDS)
    deleted = del_errors = 0

    for food in all_foods:
        name = (food.get("name") or "").strip()
        if food["id"] not in junk_ids and not _is_junk(name):
            continue
        display = repr(name) if not name else name
        if is_dry_run():
            print(f"  [DRY RUN] would delete: {display}")
            deleted += 1
        else:
            try:
                req("DELETE", f"/api/foods/{food['id']}")
                print(f"  deleted: {display}")
                deleted += 1
                summary.add("foods", f"Junk food deleted: {display}")
            except Exception as e:
                print(f"  ERROR: {display}: {e}", file=sys.stderr)
                del_errors += 1

    print(f"  => {deleted} deleted, {del_errors} errors")

    # ── Label unlabeled ──────────────────────────────────────────
    print("\n── Labeling unlabeled foods ──")
    food_labels_lower = {k.lower(): v for k, v in FOOD_LABELS.items()}
    labeled = already_labeled = no_mapping = label_errors = 0
    unmapped_names: list[str] = []

    for food in sorted(all_foods, key=lambda f: (f.get("name") or "").lower()):
        name = (food.get("name") or "").strip()
        if not name or _is_junk(name):
            continue
        if food.get("label"):
            already_labeled += 1
            continue

        label_name = FOOD_LABELS.get(name) or food_labels_lower.get(name.lower())
        if not label_name:
            no_mapping += 1
            unmapped_names.append(name)
            print(f"  NO MAPPING: {name!r}")
            continue

        label_obj = label_lookup.get(label_name)
        if not label_obj:
            no_mapping += 1
            continue

        if is_dry_run():
            print(f"  [DRY RUN] {name!r}  ->  {label_name}")
            labeled += 1
            continue

        try:
            req("PUT", f"/api/foods/{food['id']}", {
                "id":          food["id"],
                "name":        food["name"],
                "pluralName":  food.get("pluralName"),
                "description": food.get("description", ""),
                "extras":      food.get("extras", {}),
                "labelId":     label_obj["id"],
                "aliases":     food.get("aliases", []),
            })
            print(f"  ✓ {name!r}  ->  {label_name}")
            labeled += 1
            summary.add("foods", f"Food labeled: {name!r} → {label_name}")
        except Exception as e:
            print(f"  ✗ {name!r}: {e}", file=sys.stderr)
            label_errors += 1

    if unmapped_names and not is_dry_run():
        _prompt_food_labels(unmapped_names)

    print(f"\n✓ Foods complete.")
    print(f"  Deleted          : {deleted}")
    print(f"  Labeled          : {labeled}")
    print(f"  Already labeled  : {already_labeled}")
    print(f"  No mapping found : {no_mapping}")
    print(f"  Errors           : {del_errors + label_errors}")
    summary.add("foods", f"Total: {deleted} deleted, {labeled} labeled, {no_mapping} unmapped, {del_errors + label_errors} errors")