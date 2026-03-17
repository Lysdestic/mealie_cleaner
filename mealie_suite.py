#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║              MEALIE MAINTENANCE SUITE  —  lysdestic              ║
╚══════════════════════════════════════════════════════════════════╝

Unified interactive tool for keeping your Mealie instance clean and
well-organised. Run with no arguments for the interactive menu, or
pass --step to run a single step directly.

STEPS
─────
1  audit    — Dump all recipes for LLM review (pipe to a file)
2  cleanup  — Delete non-canonical tags and categories
3  apply    — Apply curated tags/categories from userdata/recipe_map.json
4  sync     — Sync tags → categories (keep filters in sync)
5  foods    — Label unlabeled foods, delete junk food entries
6  freetext — Fix free-text ingredients so they appear in shopping lists
7  enrich   — Interactive LLM enrichment: descriptions, notes, nutrition
   all      — Run steps 2-6 in sequence (audit and enrich are separate)

EDITING THE DATA
────────────────
  userdata/taxonomy.json    — add/remove canonical tags or categories
  userdata/recipe_map.json  — add/update per-recipe tag and category assignments
  data/food_labels.py — add food→label mappings, flag junk food IDs

LLM WORKFLOW
────────────
  python3 mealie_suite.py --step audit > userdata/audit.txt
  # paste audit.txt into Claude, ask for tag/category review
  # update userdata/recipe_map.json with the results
  python3 mealie_suite.py --step apply

  python3 mealie_suite.py --step enrich
  # interactive: paste recipe context into Claude, paste JSON back

USAGE
─────
  python3 mealie_suite.py                        interactive menu
  python3 mealie_suite.py --dry-run              preview mode (no changes)
  python3 mealie_suite.py --step audit           run one step directly
  python3 mealie_suite.py --step enrich          LLM enrichment session
  python3 mealie_suite.py --step all             run steps 2-6 in sequence
  python3 mealie_suite.py --step audit > out.txt pipe audit to a file

SETUP
─────
  cp .env.example .env
  # edit .env with your MEALIE_URL and MEALIE_TOKEN
  python3 mealie_suite.py
"""
from __future__ import annotations

import argparse
import sys

from core.config import load_env, check_env, set_dry_run, is_dry_run, set_group_slug
from core.utils  import confirm
from core        import color
from core.summary import summary
from steps       import (
    step_audit, step_cleanup, step_apply,
    step_sync, step_foods, step_freetext, step_enrich,
    step_nutrition_tags,
)
from core.config import get_url

# ── Step registry ─────────────────────────────────────────────────
STEPS: dict[str, tuple[str, callable]] = {
    "audit":    ("Recipe Audit  (dump all recipes for LLM review)",         step_audit),
    "cleanup":  ("Tag & Category Cleanup  (delete junk organizers)",         step_cleanup),
    "apply":    ("Apply Tag & Category Map  (set curated tags/categories)",  step_apply),
    "sync":     ("Sync Tags → Categories  (keep filters in sync)",           step_sync),
    "foods":    ("Food Label Cleanup  (delete junk, label unlabeled foods)", step_foods),
    "freetext": ("Fix Free-Text Ingredients  (repair shopping lists)",       step_freetext),
    "enrich":        ("LLM Recipe Enrichment  (descriptions, notes, nutrition)",  step_enrich),
    "nutritiontags": ("Nutrition Tag Rules  (auto-tag by protein, calories, etc.)", step_nutrition_tags),
}

ALL_STEPS_ORDER = ["cleanup", "apply", "sync", "foods", "freetext", "nutritiontags"]


# ── Run all ───────────────────────────────────────────────────────

def run_all() -> None:
    print(f"\n{color.header('▶ RUNNING ALL MAINTENANCE')}")
    print(f"  {color.muted('Order: ' + ' → '.join(ALL_STEPS_ORDER))}")
    print(f"  {color.muted('Audit and LLM enrichment are not included — they require you at the keyboard.')}\n")

    if not is_dry_run():
        if not confirm("This will modify your Mealie instance. Continue?"):
            print("Aborted.")
            return

    for key in ALL_STEPS_ORDER:
        print(f"\n{'═' * 60}")
        _, fn = STEPS[key]
        fn()

    print(f"\n{'═' * 60}")
    print("✓ All steps complete.")
    summary.print()


# ── Interactive menu ──────────────────────────────────────────────

def interactive_menu() -> None:
    print(color.header("""
╔══════════════════════════════════════════════════════════════════╗
║              MEALIE MAINTENANCE SUITE  —  lysdestic              ║
╚══════════════════════════════════════════════════════════════════╝"""))

    print(f"\n  {color.label('Connected to')} : {color.link(get_url())}")
    mode_str = color.warn('⚠ DRY RUN — no changes will be applied') if is_dry_run() else color.ok('✓ LIVE — changes will be applied')
    print(f"  {color.label('Mode')}         : {mode_str}\n")

    # ── Setup & Organisation ──────────────────────────────────────
    print(f"  {color.bold('── Setup & Organisation ─────────────────────────────────')}")
    print(f"  {color.cyan('[1]')} {STEPS['audit'][0]}")
    print(f"  {color.muted('       Dump all recipes to a file and paste into an LLM to review tags in bulk.')}")
    print(f"  {color.muted('       python3 mealie_suite.py --step audit > userdata/audit.txt')}")
    print(f"  {color.muted('       NOTE: step 2 deletes any tag/category not in userdata/taxonomy.json')}")
    print(f"  {color.cyan('[2]')} {STEPS['cleanup'][0]}")
    print(f"  {color.cyan('[3]')} {STEPS['apply'][0]}")
    print(f"  {color.cyan('[4]')} {STEPS['sync'][0]}")

    # ── Shopping & Ingredients ────────────────────────────────────
    print(f"\n  {color.bold('── Shopping & Ingredients ───────────────────────────────')}")
    print(f"  {color.cyan('[5]')} {STEPS['foods'][0]}")
    print(f"  {color.cyan('[6]')} {STEPS['freetext'][0]}")

    # ── Enrichment ────────────────────────────────────────────────
    print(f"\n  {color.bold('── Enrichment ───────────────────────────────────────────')}")
    print(f"  {color.cyan('[7]')} {STEPS['enrich'][0]}")
    print(f"  {color.cyan('[8]')} {STEPS['nutritiontags'][0]}")

    # ── Run All ───────────────────────────────────────────────────
    print(f"\n  {color.bold('── Run All ──────────────────────────────────────────────')}")
    print(f"  {color.cyan('[9]')} {color.bold('Run all maintenance')}  {color.muted('(2→3→4→5→6→8  —  no interactive steps)')}")

    print(f"\n  {color.muted('[0]')} Exit\n")

    try:
        choice = input("Select an option: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
        return

    if choice == "0":
        print("Exiting.")
        return

    if choice == "9":
        run_all()
        return

    # Map number to step key — audit is [1], maintenance is [2-6], enrich is [7]
    choice_map = {
        "1": "audit",
        "2": "cleanup",
        "3": "apply",
        "4": "sync",
        "5": "foods",
        "6": "freetext",
        "7": "enrich",
        "8": "nutritiontags",
    }

    key = choice_map.get(choice)
    if not key:
        print("Invalid option.")
        return

    _, (desc, fn) = key, STEPS[key]
    desc = STEPS[key][0]
    fn   = STEPS[key][1]
    print(f"\nRunning: {desc}")

    if not is_dry_run() and key != "audit":
        if not confirm(f"Apply changes for '{desc}'?"):
            print("Aborted.")
            return

    fn()


# ── Entry point ───────────────────────────────────────────────────

def main() -> None:
    load_env()

    parser = argparse.ArgumentParser(
        description="Mealie Maintenance Suite — cleanup, tagging, and LLM enrichment.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 mealie_suite.py                          interactive menu
  python3 mealie_suite.py --dry-run                preview mode
  python3 mealie_suite.py --step audit > userdata/audit.txt dump recipes for LLM
  python3 mealie_suite.py --step cleanup --dry-run preview cleanup
  python3 mealie_suite.py --step apply             apply tag map
  python3 mealie_suite.py --step enrich            LLM enrichment session
  python3 mealie_suite.py --step all               run steps 2-6

Step names: audit, cleanup, apply, sync, foods, freetext, enrich, all
        """
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview changes without applying them.",
    )
    parser.add_argument(
        "--step",
        choices=list(STEPS.keys()) + ["all", "nutritiontags"],
        help="Run a specific step directly instead of the interactive menu.",
    )
    args = parser.parse_args()

    set_dry_run(args.dry_run)
    check_env()

    # Fetch group slug so recipe URLs are correct for this instance
    try:
        from core.api import req as _req
        user = _req("GET", "/api/users/self")
        slug = user.get("groupSlug") or "home"
        set_group_slug(slug)
    except Exception:
        pass  # falls back to "home"

    try:
        if args.step:
            if args.step == "all":
                run_all()
            else:
                _, fn = STEPS[args.step]
                fn()
                summary.print()
        else:
            interactive_menu()
    except KeyboardInterrupt:
        print(f"\n\n  {color.warn('Interrupted.')}  Printing summary of completed actions...")
        summary.print()
        print(f"  {color.muted('Exiting.')}")


if __name__ == "__main__":
    main()