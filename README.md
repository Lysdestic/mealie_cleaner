# mealie_cleaner

A maintenance and enrichment suite for self-hosted [Mealie](https://mealie.io) recipe instances.

> **A note on how this was built:** This project was developed collaboratively with [Claude](https://claude.ai) (Anthropic) as a learning exercise in Python project structure, API integration, and CLI tooling. The code was written iteratively through conversation — not generated in one shot — with real debugging, refactoring, and design decisions made along the way. If you're learning Python or exploring what's possible with LLM-assisted development, the commit history reflects how a project like this grows organically.

---

## What is this?

If you self-host Mealie and have more than a handful of recipes, you've probably run into some of these problems:

- Tags and categories that got created by accident and now litter your filters
- Recipes imported from the web with no description, no nutrition info, and ingredients that don't link to your shopping list
- Foods that show up unlabeled in shopping lists, or junk entries that snuck in
- No consistent way to know which recipes are high protein, low calorie, or freeze well

**mealie_cleaner** is a CLI tool that fixes all of this. It talks to your Mealie instance via its API and gives you an interactive menu to clean, organise, and enrich your recipe library — with color-coded output, interactive prompts, and a session summary at the end of every run.

---

## Features

### Maintenance
- **Tag & category cleanup** — finds anything in Mealie not in your canonical list and asks per-item: keep it (written to `taxonomy.json` automatically), delete it, or skip
- **Tag & category apply** — pushes a curated tag/category map to all recipes; missing organizers are auto-created; tags already on recipes in Mealie are preserved (merge, not replace); `recipe_map.json` is auto-synced to reflect reality
- **Tag → category sync** — Mealie has two separate filter systems; this keeps them in sync so both work correctly
- **Food label cleanup** — labels unlabeled foods via a numbered menu (no typing), creates new labels on the spot if needed, deletes junk entries, saves everything back to `food_labels.json` automatically
- **Free-text ingredient repair** — recipes imported from the web often have plain-text ingredients with no structured food link; this runs them through Mealie's parser to fix them

### Enrichment
- **LLM recipe enrichment** — audits every recipe against a quality standard and walks you through improving any that fall short, one at a time, using any LLM (Claude, GPT, etc.); automatically re-evaluates nutrition tag rules after each recipe is enriched
- **Nutrition tag rules** — define threshold-based rules (e.g. protein ≥ 20g → "High Protein") that auto-tag recipes; rules persist in `userdata/nutrition_rules.json`; recipes that lose qualification are flagged for review rather than silently un-tagged

### Utilities
- **Recipe audit** — dumps all recipes with tags, categories, ingredients, and instructions to stdout; pipe to a file and paste into an LLM to review your tagging scheme in bulk

### General
- **Session summary** — printed at the end of every run showing every action taken
- **Graceful Ctrl+C** — prints the summary of completed actions and exits cleanly
- **Dry run mode** — any step can be previewed with `--dry-run` before touching anything
- **Dynamic recipe URLs** — group slug fetched automatically from your Mealie API so recipe links always point to the right place
- **No external dependencies** — stdlib only; no pip install needed

---

## Requirements

- Python 3.10+
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

## Running it

```bash
# Interactive menu (recommended)
python3 mealie_suite.py

# Preview mode — shows what would happen without making any changes
python3 mealie_suite.py --dry-run

# Run a specific step directly
python3 mealie_suite.py --step cleanup
python3 mealie_suite.py --step enrich
python3 mealie_suite.py --step nutritiontags

# Run all maintenance steps in sequence (2 → 3 → 4 → 5 → 6 → 8)
python3 mealie_suite.py --step all

# Dump all recipes for LLM review
python3 mealie_suite.py --step audit > userdata/audit.txt
```

The menu:

```
── Maintenance ──────────────────────────────────────────
  [2] Tag & Category Cleanup
  [3] Apply Tag & Category Map
  [4] Sync Tags → Categories
  [5] Food Label Cleanup
  [6] Fix Free-Text Ingredients
  [9] Run all maintenance steps  (2 → 3 → 4 → 5 → 6 → 8)

── Enrichment ───────────────────────────────────────────
  [7] LLM Recipe Enrichment
  [8] Nutrition Tag Rules

── Utilities ────────────────────────────────────────────
  [1] Recipe Audit  (dump all recipes for LLM review)
```

---

## Instance data

Your personal data lives in `userdata/` (gitignored — never committed). Four JSON files:

### `userdata/taxonomy.json`

Defines which tags and categories are canonical for your Mealie instance.

```json
{
  "tags": ["Main Course", "Weeknight", "Chicken", "High Protein", "Freezer"],
  "categories": ["Dinner", "Lunch", "Breakfast", "Side Dish"]
}
```

> ⚠️ **Step 2 (cleanup) will DELETE** any tag or category in Mealie not listed here.  
> **Step 3 (apply) will AUTO-CREATE** anything listed here that's missing from Mealie.

When cleanup finds a non-canonical tag or category it asks interactively:
- `k` — keep it and add it to `taxonomy.json` **automatically**
- `d` — delete it from Mealie
- `s` — skip for now

### `userdata/recipe_map.json`

Maps each recipe slug to its canonical tags and categories.

```json
{
  "freetext_skip_slugs": ["my-recipe-with-weird-ingredients"],
  "my-pasta-recipe": {
    "tags": ["Main Course", "Pasta", "Italian", "Weeknight"],
    "categories": ["Dinner"]
  }
}
```

- Step 3 merges tags (preserves canonical tags already on recipes in Mealie) and auto-syncs this file to reflect reality
- When step 3 finds unmapped recipes it shows their current Mealie tags and prompts you to confirm via numbered picker — no typing
- `freetext_skip_slugs` lists recipes whose ingredient format is incompatible with the parser

### `userdata/food_labels.json`

Maps food names to Mealie shopping list label categories, and flags junk entries for deletion.

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

Step 5 shows a numbered menu of your Mealie labels when assigning — no typing required. You can create a new label on the spot with `N`. Everything saves automatically.

### `userdata/nutrition_rules.json`

Defines rules that automatically tag recipes based on nutrition thresholds.

```json
{
  "rules": [
    {
      "field": "proteinContent",
      "operator": ">=",
      "threshold": 20,
      "tag": "High Protein"
    },
    {
      "field": "proteinContent",
      "operator": ">=",
      "threshold": 35,
      "tag": "Very High Protein"
    }
  ]
}
```

Rules are managed interactively via step 8 — you rarely need to edit this file directly. Available fields: `calories`, `fatContent`, `proteinContent`, `carbohydrateContent`, `fiberContent`, `sodiumContent`, `sugarContent`. Operators: `>=` or `<=`.

---

## LLM enrichment (step 7)

Audits every recipe against a quality standard and walks you through improving any that fall short.

**Quality standard:**

| Field | Requirement |
|---|---|
| Description | ≥ 80 characters, specific to the dish |
| Notes | ≥ 3 practical tip items |
| Freezer note | Always assessed — Freezer tag added only if dish genuinely freezes well |
| Nutrition | ≥ 4 of 7 fields filled |
| Servings | Non-zero and plausible |
| Times | Total time, prep time, and cook time all present |

For each recipe that fails, the tool generates a prompt you copy into any LLM. Paste the JSON response back, review the preview, confirm before anything is applied. Navigation: `a` to apply, `r` to redo, `s` to skip, `q` to quit.

After each recipe is enriched, nutrition tag rules are automatically re-evaluated for that recipe — so if a recipe just got protein data added and now qualifies for "High Protein", the tag is applied immediately without needing a separate run of step 8.

---

## Nutrition tag rules (step 8)

Define threshold-based rules that auto-tag recipes based on their nutrition data.

```
▶ STEP 8: NUTRITION TAG RULES

  Current rules:
   1. Protein (g) ≥ 20  →  tag 'High Protein'
   2. Protein (g) ≥ 35  →  tag 'Very High Protein'

  [a] Run all rules now
  [r] Add a new rule
  [d] Delete a rule
  [0] Back to menu
```

- New tags are added to `taxonomy.json` and created in Mealie automatically when a rule is created
- Recipes with no nutrition data are skipped silently
- Recipes that have a tag but no longer meet the threshold are **flagged in the session summary** for your review — never auto-removed
- Step 8 runs automatically at the end of the run-all sequence (step 9)

---

## Bulk tag review workflow

When adding recipes in bulk or revisiting your tagging scheme:

1. `python3 mealie_suite.py --step audit > userdata/audit.txt`
2. Paste `audit.txt` into an LLM — ask it to review tags and categories
3. If new tags or categories are suggested, add them to `userdata/taxonomy.json`
4. Add the new slug entries the LLM suggests to `userdata/recipe_map.json`
5. Run step 3 — missing tags and categories are created in Mealie automatically

> ⚠️ Step 2 (cleanup) will delete any tag or category in Mealie not listed in `taxonomy.json`. Always update `taxonomy.json` before running cleanup if you've added new organizers.

---

## Project structure

```
mealie_cleaner/
├── mealie_suite.py          # entry point — menu and argparse
├── env.example              # template — copy to .env
├── .env                     # your credentials (gitignored)
├── userdata/                # your instance data (gitignored)
│   ├── taxonomy.json        # canonical tags and categories
│   ├── recipe_map.json      # per-recipe assignments + freetext skip list
│   ├── food_labels.json     # food → shopping label map and junk IDs
│   └── nutrition_rules.json # threshold-based auto-tagging rules
├── userdata.example/        # committed templates with inline instructions
│   ├── taxonomy.json
│   ├── recipe_map.json
│   ├── food_labels.json
│   └── nutrition_rules.json
├── core/
│   ├── api.py               # HTTP helpers (req, get_all)
│   ├── config.py            # .env loading, URL/token/dry-run/group slug
│   ├── color.py             # ANSI color helpers (auto-disabled when piped)
│   ├── summary.py           # session summary collector
│   └── utils.py             # normalize, confirm, dry_run_banner
├── data/
│   ├── __init__.py          # exports CANONICAL_TAGS, RECIPE_MAP, NUTRITION_RULES, etc.
│   └── loader.py            # reads from userdata/*.json at runtime
└── steps/
    ├── audit.py             # step 1: dump recipes for LLM review
    ├── cleanup.py           # step 2: interactive cleanup → auto-saves to taxonomy.json
    ├── apply.py             # step 3: apply recipe map, merge tags, auto-sync map file
    ├── sync.py              # step 4: sync tags → categories
    ├── foods.py             # step 5: numbered label picker, new label creation
    ├── freetext.py          # step 6: fix free-text ingredients
    ├── enrich.py            # step 7: LLM quality audit and enrichment
    └── nutrition_tags.py    # step 8: threshold-based nutrition auto-tagging
```

---

## Design notes

**No external dependencies.** Everything uses Python's stdlib. No `pip install`, no virtual environment, no version conflicts.

**Your data stays local.** `userdata/` is gitignored. Your recipe assignments, taxonomy, food labels, and nutrition rules never leave your machine.

**Interactive by default.** Nothing destructive happens silently. Cleanup asks about each non-canonical item individually. Food labels use a numbered menu. Enrichment previews every change before applying. New recipes prompt you to confirm their tags.

**Self-maintaining data files.** `taxonomy.json` is updated automatically when you keep a tag in cleanup. `recipe_map.json` is synced when step 3 detects tags not in the map. `food_labels.json` is updated when you assign a label to an unmapped food. `nutrition_rules.json` is managed entirely through the step 8 interactive menu. You should rarely need to edit these files manually.

**Nutrition tags stay in sync.** Rules run automatically after each enrichment session, after the run-all sequence, and on demand via step 8. Recipes that lose qualification for a tag are flagged for review rather than silently modified.

**PATCH not PUT.** All recipe updates use Mealie's PATCH endpoint. PUT triggers a slug uniqueness check that causes silent failures on some Mealie versions.

**Group slug is dynamic.** Recipe URLs in prompts use your actual Mealie group slug (fetched from `/api/users/self` on startup) so they work correctly regardless of your instance's group name.