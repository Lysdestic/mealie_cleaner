# mealie_cleaner

A maintenance and enrichment suite for self-hosted [Mealie](https://mealie.io) recipe instances.

> **A note on how this was built:** This project was developed collaboratively with [Claude](https://claude.ai) (Anthropic) as a learning exercise in Python project structure, API integration, and CLI tooling. The code was written iteratively through conversation — not generated in one shot — with real debugging, refactoring, and design decisions made along the way. If you're learning Python or exploring what's possible with LLM-assisted development, the commit history is a reasonable reflection of how a project like this grows organically.

---

## What is this?

If you self-host Mealie and have more than a handful of recipes, you've probably run into some of these problems:

- Tags and categories that got created by accident and now litter your filters
- Recipes imported from the web with no description, no nutrition info, and ingredients that don't link to your shopping list
- Foods that show up unlabeled in shopping lists, or duplicate junk entries that snuck in
- No consistent way to know which recipes freeze well

**mealie_cleaner** is a CLI tool that fixes all of this. It talks to your Mealie instance via its API and gives you an interactive menu to clean, organise, and enrich your recipe library — one step at a time or all at once.

---

## Features

### Maintenance
- **Tag & category cleanup** — finds anything in Mealie that isn't in your canonical list and asks you what to do with each one: keep it (and add it to your taxonomy automatically), delete it, or skip for now
- **Tag & category apply** — pushes a curated tag/category map to all your recipes; missing tags and categories are created in Mealie automatically
- **Tag → category sync** — Mealie has two separate filter systems (Tags and Categories); this keeps them in sync so both work correctly
- **Food label cleanup** — labels unlabeled foods in your shopping list, deletes junk entries (blank rows, `--- section headers ---`), and prompts you to assign labels to anything new
- **Free-text ingredient repair** — recipes imported from the web often have ingredients stored as plain text with no structured food link, which means they don't appear in shopping lists correctly; this runs them through Mealie's own parser to fix them

### Enrichment
- **LLM recipe enrichment** — audits every recipe against a quality standard and walks you through improving any that fall short, one at a time, using any LLM of your choice (Claude, GPT, etc.)

### Utilities
- **Recipe audit** — dumps all your recipes with tags, categories, ingredients, and instructions to stdout; pipe it to a file and paste it into an LLM to review your tagging scheme in bulk

---

## Requirements

- Python 3.10+ (stdlib only — no pip installs needed)
- A running Mealie instance with API access
- A Mealie API token (`Settings → API Tokens`)

---

## Setup

```bash
git clone https://github.com/lysdestic/mealie_cleaner
cd mealie_cleaner

# 1. Configure your credentials
cp .env.example .env
# Edit .env and set your MEALIE_URL and MEALIE_TOKEN

# 2. Set up your instance data
cp -r userdata.example userdata
# Edit the three files in userdata/ to match your Mealie setup
# (see "Instance data" below)
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
python3 mealie_suite.py --step apply
python3 mealie_suite.py --step enrich

# Run all maintenance steps in sequence (2 → 3 → 4 → 5 → 6)
python3 mealie_suite.py --step all

# Dump all recipes for LLM review
python3 mealie_suite.py --step audit > audit.txt
```

The menu looks like this:

```
── Maintenance ──────────────────────────────────────────
  [2] Tag & Category Cleanup  (delete junk organizers)
  [3] Apply Tag & Category Map  (set curated tags/categories)
  [4] Sync Tags → Categories  (keep filters in sync)
  [5] Food Label Cleanup  (delete junk, label unlabeled foods)
  [6] Fix Free-Text Ingredients  (repair shopping lists)
  [8] Run all maintenance steps  (2 → 3 → 4 → 5 → 6)

── Enrichment ───────────────────────────────────────────
  [7] LLM Recipe Enrichment  (descriptions, notes, nutrition)

── Utilities ────────────────────────────────────────────
  [1] Recipe Audit  (dump all recipes for LLM review)
```

At the end of every run, a **session summary** is printed showing every action taken — no scrolling back through output to figure out what changed.

---

## Instance data

Your personal data lives in `userdata/` which is gitignored — it never gets committed. Three JSON files:

### `userdata/taxonomy.json`

Defines which tags and categories are canonical for your Mealie instance.

```json
{
  "tags": ["Main Course", "Weeknight", "Italian", "Chicken", "Oven", "Freezer"],
  "categories": ["Dinner", "Lunch", "Breakfast", "Side Dish", "Dessert"]
}
```

> ⚠️ **Step 2 (cleanup) will DELETE** any tag or category in Mealie that isn't listed here.  
> **Step 3 (apply) will AUTO-CREATE** anything listed here that doesn't exist in Mealie yet.  
> Always add new tags/categories to this file before running cleanup.

When cleanup finds something non-canonical, it asks you what to do:
- `k` — keep it and add it to `taxonomy.json` automatically
- `d` — delete it from Mealie
- `s` — skip for now and decide later

### `userdata/recipe_map.json`

Maps each recipe slug to its canonical tags and categories. The slug is the last part of the recipe URL in Mealie (`/g/home/r/my-recipe-slug`).

```json
{
  "my-pasta-recipe": {
    "tags": ["Main Course", "Pasta", "Italian", "Weeknight"],
    "categories": ["Dinner"]
  },
  "my-hummus": {
    "tags": ["Appetizer", "Vegan", "No-Cook"],
    "categories": ["Appetizer"]
  }
}
```

When step 3 finds recipes not in the map, it fetches their current tags from Mealie and prompts you to confirm or change them — you don't have to re-enter everything from scratch.

### `userdata/food_labels.json`

Maps food names to Mealie shopping list label categories, and flags junk entries for deletion.

```json
{
  "food_labels": {
    "chicken breast": "Poultry",
    "olive oil": "Oils & Fats",
    "baby spinach": "Vegetables & Greens"
  },
  "junk_food_ids": [],
  "junk_food_patterns": ["^---", "---$", "^\\s*$"]
}
```

Label names must already exist in Mealie (`Shopping → Labels`). When step 5 finds unlabeled foods, it shows you the available labels and prompts you to assign them interactively — they get saved to this file automatically.

---

## LLM enrichment (step 7)

This is the most interactive feature. It audits every recipe against a quality standard and walks you through improving any that fall short.

**What it checks:**
| Field | Standard |
|---|---|
| Description | ≥ 80 characters, specific to the dish |
| Notes | ≥ 3 practical tip entries |
| Freezer note | Explicitly assessed — Freezer tag added only if dish genuinely freezes well |
| Nutrition | ≥ 4 of 7 fields filled (calories, fat, protein, carbs, fiber, sodium, sugar) |
| Servings | Non-zero and plausible given the ingredients |
| Times | Total time, prep time, and cook time all present |

**How it works:**

For each recipe that fails the audit, the tool generates a prompt block you copy and paste into any LLM. You paste the JSON response back, get a preview of what will change, and confirm before anything is applied.

```
  [12/34] Butter Chicken
  http://192.168.0.66:9925/g/home/r/butter-chicken
  Issues:
    ✗ notes (none)
    ✗ freezer note (not yet assessed)
    ✗ nutrition (missing or sparse)

  ┌─ COPY THIS PROMPT TO YOUR LLM ────────────────────────
  │ You are a culinary assistant reviewing a recipe...
  └────────────────────────────────────────────────────────

  Butter Chicken  http://192.168.0.66:9925/g/home/r/butter-chicken
  Paste LLM response below. Press Enter twice when done.
  (s = skip,  q = quit,  r = redo)
```

The Freezer tag in Mealie is managed automatically — added when the LLM confirms a dish freezes well, removed if a negative assessment is found and the tag was previously applied incorrectly.

---

## Bulk tag review workflow

When you add a batch of new recipes and want to review their tagging scheme:

1. `python3 mealie_suite.py --step audit > audit.txt`
2. Paste `audit.txt` into an LLM and ask it to review tags and categories
3. If new tags or categories are suggested, add them to `userdata/taxonomy.json`
4. Paste the resulting recipe map into `userdata/recipe_map.json`
5. Run step 3 — missing tags and categories are created in Mealie automatically

---

## Project structure

```
mealie_cleaner/
├── mealie_suite.py          # entry point — menu and argparse
├── .env                     # your credentials (gitignored)
├── .env.example             # template — copy to .env
├── userdata/                # your instance data (gitignored)
│   ├── taxonomy.json        # canonical tags and categories
│   ├── recipe_map.json      # per-recipe tag/category assignments
│   └── food_labels.json     # food → shopping label map
├── userdata.example/        # committed templates with instructions
│   ├── taxonomy.json
│   ├── recipe_map.json
│   └── food_labels.json
├── core/
│   ├── api.py               # HTTP helpers (req, get_all)
│   ├── config.py            # .env loading, URL/token/dry-run state
│   ├── color.py             # ANSI color helpers (auto-disabled when piped)
│   ├── summary.py           # session summary collector
│   └── utils.py             # normalize, confirm, dry_run_banner
├── data/
│   ├── __init__.py          # exports CANONICAL_TAGS, RECIPE_MAP, etc.
│   └── loader.py            # reads from userdata/*.json at runtime
└── steps/
    ├── audit.py             # step 1: dump recipes for LLM review
    ├── cleanup.py           # step 2: interactive tag/category cleanup
    ├── apply.py             # step 3: apply recipe map, auto-create organizers
    ├── sync.py              # step 4: sync tags → categories
    ├── foods.py             # step 5: food label cleanup
    ├── freetext.py          # step 6: fix free-text ingredients
    └── enrich.py            # step 7: LLM quality audit and enrichment
```

---

## A few design decisions worth knowing

**No external dependencies.** Everything uses Python's stdlib. No `pip install` needed, no virtual environment required, no version conflicts.

**Dry run mode.** Any step can be run with `--dry-run` to preview exactly what would change without touching anything. Good habit before running cleanup for the first time.

**Your data stays local.** `userdata/` is gitignored. Your recipe assignments, taxonomy, and food labels never leave your machine unless you explicitly choose to commit them.

**Interactive by default.** Nothing destructive happens silently. Cleanup asks about each non-canonical item individually. Enrichment shows a preview before every apply. Unmapped recipes and unlabeled foods prompt you inline rather than failing quietly.

**PATCH not PUT.** All recipe updates use Mealie's PATCH endpoint. PUT triggers a slug uniqueness check that causes silent failures on some Mealie versions.