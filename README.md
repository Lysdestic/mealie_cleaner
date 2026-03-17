# mealie_cleaner

A maintenance and enrichment suite for self-hosted [Mealie](https://mealie.io) recipe instances.

> **A note on how this was built:** This project was developed collaboratively with [Claude](https://claude.ai) (Anthropic) as a learning exercise in Python project structure, API integration, and CLI tooling. The code was written iteratively through conversation — not generated in one shot — with real debugging, refactoring, and design decisions made along the way.

---

## What is this?

If you self-host Mealie and have more than a handful of recipes, you've probably run into some of these problems:

- Tags and categories that got created by accident and now litter your filters
- Recipes imported from the web with no description, no nutrition info, and ingredients that don't link to your shopping list
- Foods that show up unlabeled in shopping lists, or junk entries that snuck in
- No consistent way to know which recipes are high protein, low calorie, or freeze well

**mealie_cleaner** is a CLI tool that fixes all of this. It talks to your Mealie instance via its API and gives you an interactive menu to clean, organise, and enrich your recipe library — with color-coded output, interactive prompts, and a session summary at the end of every run.

---

## Requirements

- Python 3.10+ (stdlib only — no pip install needed)
- A running Mealie instance with API access
- A Mealie API token (`Settings → API Tokens`)

---

## Setup

```bash
git clone https://github.com/Lysdestic/mealie_cleaner
cd mealie_cleaner

# 1. Configure your credentials
cp env.example .env
# Edit .env — set MEALIE_URL and MEALIE_TOKEN

# 2. Set up your instance data
cp -r userdata.example userdata
# Edit the files in userdata/ to match your Mealie setup
```

---

## The menu

```
── Setup & Organisation ─────────────────────────────────
  [1] Recipe Audit          (dump all recipes for LLM review)
  [2] Tag & Category Cleanup
  [3] Apply Tag & Category Map
  [4] Sync Tags → Categories

── Shopping & Ingredients ───────────────────────────────
  [5] Food Label Cleanup
  [6] Fix Free-Text Ingredients

── Enrichment ───────────────────────────────────────────
  [7] LLM Recipe Enrichment
  [8] Nutrition Tag Rules

── Run All ──────────────────────────────────────────────
  [9] Run all maintenance  (2→3→4→5→6→8 — no interactive steps)

  [0] Exit
```

---

## How you'll actually use this

### First-time setup

The typical first-time flow is:

1. **Audit** — `python3 mealie_suite.py --step audit > userdata/audit.txt`, paste into an LLM, ask it to suggest tags and categories for all your recipes
2. **Build your taxonomy** — add the suggested tags/categories to `userdata/taxonomy.json`
3. **Build your recipe map** — add the slug→tags/categories assignments to `userdata/recipe_map.json`
4. **Run step 3** (apply) — pushes the map to Mealie; missing tags/categories are created automatically
5. **Run step 5** (food labels) — assign labels to unlabeled foods via numbered menu
6. **Run step 6** (freetext) — fix any ingredients that don't link to your shopping list
7. **Run step 7** (enrich) — work through recipes that need descriptions, notes, and nutrition
8. **Define nutrition rules** — use step 8 to set up rules like "protein ≥ 20g → High Protein"

### Ongoing use

Once set up, ongoing maintenance is mostly:

```bash
# After adding new recipes — run everything non-interactive
python3 mealie_suite.py --step all

# Work through enrichment periodically
python3 mealie_suite.py --step enrich
```

Step 9 (run all) handles organisation, labels, ingredients, and nutrition tags automatically. It deliberately excludes audit and LLM enrichment since those require you at the keyboard.

> ⚠️ Step 2 (cleanup) will **delete** any tag or category in Mealie not listed in `userdata/taxonomy.json`. Always add new tags there before running cleanup.

---

## Running it

```bash
# Interactive menu
python3 mealie_suite.py

# Preview mode — no changes applied
python3 mealie_suite.py --dry-run

# Run a specific step directly
python3 mealie_suite.py --step apply
python3 mealie_suite.py --step enrich
python3 mealie_suite.py --step nutritiontags

# Run all maintenance (non-interactive steps only)
python3 mealie_suite.py --step all

# Dump all recipes for LLM review
python3 mealie_suite.py --step audit > userdata/audit.txt
```

---

## Your instance data

Everything specific to your Mealie instance lives in `userdata/` (gitignored — never committed).

### `userdata/taxonomy.json`

Which tags and categories are canonical for your instance. Step 2 deletes anything in Mealie not listed here. Step 3 creates anything listed here that's missing from Mealie.

```json
{
  "tags": ["Main Course", "Weeknight", "Chicken", "High Protein", "Freezer"],
  "categories": ["Dinner", "Lunch", "Breakfast", "Side Dish"]
}
```

When step 2 finds a non-canonical tag it asks you: `k` keep (adds to `taxonomy.json` automatically), `d` delete, `s` skip.

### `userdata/recipe_map.json`

Maps recipe slugs to their tags and categories. The slug is the last part of the recipe URL (`/g/home/r/my-recipe-slug`).

```json
{
  "freetext_skip_slugs": ["my-recipe-with-section-headers"],
  "butter-chicken": {
    "tags": ["Main Course", "Chicken", "Indian", "Comfort Food"],
    "categories": ["Dinner"]
  }
}
```

Step 3 **merges** tags — it preserves any canonical tags already on a recipe in Mealie and syncs this file to match. When it finds unmapped recipes it fetches their current Mealie tags and lets you confirm via numbered picker. `freetext_skip_slugs` lists recipes whose ingredient format breaks the parser (e.g. `"Dough — 180g flour"` style lines).

### `userdata/food_labels.json`

Maps food names to Mealie shopping list labels. Step 5 shows a numbered menu of your labels when assigning — no typing. You can create new labels on the spot.

```json
{
  "food_labels": {
    "chicken breast": "Poultry",
    "olive oil": "Oils & Fats"
  },
  "junk_food_ids": [],
  "junk_food_patterns": ["^---", "---$", "^\\s*$"]
}
```

### `userdata/nutrition_rules.json`

Threshold-based rules that auto-tag recipes. Managed entirely through step 8's interactive menu — you rarely need to edit this file directly.

```json
{
  "rules": [
    {"field": "proteinContent", "operator": ">=", "threshold": 20, "tag": "High Protein"},
    {"field": "proteinContent", "operator": ">=", "threshold": 35, "tag": "Very High Protein"}
  ]
}
```

Available fields: `calories`, `fatContent`, `proteinContent`, `carbohydrateContent`, `fiberContent`, `sodiumContent`, `sugarContent`. Operators: `>=` or `<=`.

---

## LLM enrichment (step 7)

Audits every recipe against a quality standard and surfaces any that fall short.

| Field | Requirement |
|---|---|
| Description | ≥ 80 characters, specific to the dish |
| Notes | ≥ 3 practical tip items |
| Freezer note | Always assessed — Freezer tag added only if dish genuinely freezes well |
| Nutrition | ≥ 4 of 7 fields filled |
| Servings | Non-zero and plausible |
| Times | Total, prep, and cook time all present |

For each failing recipe the tool generates a prompt you copy into any LLM. Paste the JSON response back, review the preview, confirm. Navigation: `a` apply, `r` redo, `s` skip, `q` quit.

After each recipe is enriched, nutrition tag rules are automatically re-evaluated — so if a recipe just got protein data and now qualifies for "High Protein", the tag is applied immediately without a separate step 8 run.

---

## Nutrition tags (step 8)

Define rules that auto-tag recipes based on their nutrition data. New tags are created in Mealie and added to `taxonomy.json` automatically when you save a rule.

Recipes that have a tag but no longer meet the threshold are **flagged in the session summary** for your review — never auto-removed.

Step 8 also runs automatically at the end of the run-all sequence (step 9).

---

## Project structure

```
mealie_cleaner/
├── mealie_suite.py          # entry point — menu and argparse
├── env.example              # template — copy to .env
├── .env                     # your credentials (gitignored)
├── userdata/                # your instance data (gitignored)
│   ├── taxonomy.json
│   ├── recipe_map.json
│   ├── food_labels.json
│   └── nutrition_rules.json
├── userdata.example/        # committed templates with inline instructions
├── core/
│   ├── api.py               # HTTP helpers
│   ├── config.py            # .env loading, URL/token/dry-run/group slug
│   ├── color.py             # ANSI color helpers (auto-disabled when piped)
│   ├── summary.py           # session summary collector
│   └── utils.py             # shared utilities
├── data/
│   ├── __init__.py          # exports CANONICAL_TAGS, RECIPE_MAP, NUTRITION_RULES, etc.
│   └── loader.py            # reads from userdata/*.json at runtime
└── steps/
    ├── audit.py             # [1] dump recipes for LLM review
    ├── cleanup.py           # [2] interactive cleanup → auto-saves to taxonomy.json
    ├── apply.py             # [3] apply recipe map, merge tags, auto-sync map file
    ├── sync.py              # [4] sync tags → categories
    ├── foods.py             # [5] numbered label picker, new label creation
    ├── freetext.py          # [6] fix free-text ingredients
    ├── enrich.py            # [7] LLM quality audit and enrichment
    └── nutrition_tags.py    # [8] threshold-based nutrition auto-tagging
```

---

## Design notes

**No external dependencies.** Everything uses Python's stdlib.

**Your data stays local.** `userdata/` is gitignored. Your recipe assignments, taxonomy, food labels, and nutrition rules never leave your machine.

**Self-maintaining data files.** `taxonomy.json` updates when you keep a tag in cleanup. `recipe_map.json` syncs when step 3 detects new tags. `food_labels.json` updates when you assign a label. `nutrition_rules.json` is managed through the step 8 menu. You should rarely need to edit these files manually.

**Merge, don't replace.** Step 3 preserves tags already on recipes in Mealie — it only adds what's in your map, never strips existing canonical tags.

**Graceful Ctrl+C.** Interrupting mid-run prints the session summary of completed actions and exits cleanly.

**PATCH not PUT.** All recipe updates use Mealie's PATCH endpoint. PUT triggers a slug uniqueness check that causes silent failures on some Mealie versions.

**Group slug is dynamic.** Recipe URLs in prompts use your actual Mealie group slug fetched from the API on startup — works correctly regardless of your instance's group name.