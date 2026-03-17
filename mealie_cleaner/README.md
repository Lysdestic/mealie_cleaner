# mealie_cleaner

A modular maintenance and enrichment suite for self-hosted [Mealie](https://mealie.io) instances.
Keeps your recipes, tags, categories, foods, and ingredients clean and consistent via an
interactive CLI — no external dependencies, stdlib only.

## Features

- **Tag & category cleanup** — interactively review non-canonical organizers, keep or delete
- **Tag & category apply** — push a curated tag/category map to all recipes; missing organizers are auto-created
- **Tag → category sync** — keep Mealie's two filter systems in sync automatically
- **Food label cleanup** — label unlabeled foods, delete junk entries
- **Free-text ingredient repair** — run unlinked ingredients through Mealie's parser so they appear in shopping lists
- **LLM recipe enrichment** — interactive per-recipe quality audit; generate descriptions, notes, nutrition, times, and freezer assessments using any LLM

## Requirements

- Python 3.10+
- A running Mealie instance with API access
- A Mealie API token (Settings → API Tokens)

## Setup

```bash
git clone https://github.com/yourname/mealie_cleaner
cd mealie_cleaner

# 1. Configure credentials
cp .env.example .env
# edit .env — set MEALIE_URL and MEALIE_TOKEN

# 2. Configure your instance data
cp -r userdata.example userdata
# edit each file in userdata/ — see below
```

## Instance data

Your instance-specific data lives in `userdata/` (gitignored). Three files:

### `userdata/taxonomy.json`
Defines which tags and categories are canonical for your instance.

- **Step 2 (cleanup) will DELETE** any tag or category in Mealie not listed here
- **Step 3 (apply) will AUTO-CREATE** anything listed here that's missing from Mealie
- Add new tags/categories here first, then to `recipe_map.json`

```json
{
  "tags": ["Main Course", "Weeknight", "Italian", "Chicken", "Oven"],
  "categories": ["Dinner", "Lunch", "Breakfast"]
}
```

### `userdata/recipe_map.json`
Maps recipe slugs to their canonical tags and categories.

- Slugs come from your Mealie URLs: `/g/home/r/my-recipe-slug`
- Run step 1 (audit) to dump all slugs for easy reference
- All tags and categories must exist in `taxonomy.json`

```json
{
  "my-pasta-recipe": {
    "tags": ["Main Course", "Pasta", "Italian", "Weeknight"],
    "categories": ["Dinner"]
  }
}
```

### `userdata/food_labels.json`
Maps food names to Mealie shopping list labels, and flags junk entries for deletion.

- Label names must already exist in Mealie (Shopping → Labels)
- `junk_food_ids`: Mealie UUIDs of blank/header food entries to delete
- `junk_food_patterns`: regex patterns — matching food names are deleted

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

## Usage

```bash
# Interactive menu
python3 mealie_suite.py

# Preview mode — no changes applied
python3 mealie_suite.py --dry-run

# Run a specific step directly
python3 mealie_suite.py --step cleanup
python3 mealie_suite.py --step apply
python3 mealie_suite.py --step enrich

# Dump all recipes for LLM review
python3 mealie_suite.py --step audit > audit.txt

# Run all maintenance steps (2 → 3 → 4 → 5 → 6)
python3 mealie_suite.py --step all
```

## Menu overview

```
── Maintenance ──────────────────────────────────────────
  [2] Tag & Category Cleanup
  [3] Apply Tag & Category Map
  [4] Sync Tags → Categories
  [5] Food Label Cleanup
  [6] Fix Free-Text Ingredients
  [8] Run all maintenance steps (2 → 3 → 4 → 5 → 6)

── Enrichment ───────────────────────────────────────────
  [7] LLM Recipe Enrichment

── Utilities ────────────────────────────────────────────
  [1] Recipe Audit  (dump all recipes for LLM review)
```

## LLM enrichment workflow

Step 7 audits every recipe against a quality standard and surfaces any that need work:

- Description ≥ 80 chars
- ≥ 3 notes with practical tips
- Freezer note assessed (Freezer tag added only if dish freezes well)
- ≥ 4/7 nutrition fields filled
- Servings non-zero
- Total time, prep time, cook time all present

For each recipe that fails, it generates a prompt you paste into any LLM (Claude, GPT, etc).
You paste the JSON response back and confirm before anything is applied.

## Bulk tag review workflow

When adding recipes in bulk or revisiting your tagging scheme:

1. `python3 mealie_suite.py --step audit > audit.txt`
2. Paste `audit.txt` into Claude — ask it to review tags and categories
3. If new tags/categories are suggested, add them to `userdata/taxonomy.json`
4. Paste the resulting recipe map into `userdata/recipe_map.json`
5. Run step 3 — missing tags/categories are created in Mealie automatically

> ⚠️ Step 2 (cleanup) will delete any tag or category in Mealie not listed in `taxonomy.json`.
> Always update `taxonomy.json` before running cleanup if you've added new organizers.

## Project structure

```
mealie_cleaner/
├── mealie_suite.py          # entry point — menu and argparse
├── .env                     # your credentials (gitignored)
├── .env.example             # template
├── userdata/                # your instance data (gitignored)
│   ├── taxonomy.json        # canonical tags and categories
│   ├── recipe_map.json      # per-recipe tag/category assignments
│   └── food_labels.json     # food → label map and junk IDs
├── userdata.example/        # committed templates
│   ├── taxonomy.json
│   ├── recipe_map.json
│   └── food_labels.json
├── core/                    # shared utilities
│   ├── api.py               # HTTP helpers
│   ├── config.py            # .env loading, dry-run state
│   ├── color.py             # ANSI color helpers
│   └── utils.py             # normalize, confirm, etc.
├── data/                    # data loader (reads from userdata/)
│   └── loader.py
└── steps/                   # one file per menu step
    ├── audit.py
    ├── cleanup.py
    ├── apply.py
    ├── sync.py
    ├── foods.py
    ├── freetext.py
    └── enrich.py
```
