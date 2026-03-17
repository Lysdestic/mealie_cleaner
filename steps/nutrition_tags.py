"""
data/__init__.py

Exports the canonical data objects used throughout the suite.
All data is loaded from userdata/*.json at runtime — nothing is
hardcoded here. See data/loader.py for details.
"""
from .loader import load_taxonomy, load_recipe_map, load_food_labels, load_nutrition_rules

CANONICAL_TAGS, KEEP_CATEGORIES = load_taxonomy()
RECIPE_MAP, FREETEXT_SKIP_SLUGS = load_recipe_map()
FOOD_LABELS, JUNK_FOOD_IDS, JUNK_FOOD_PATTERNS = load_food_labels()
NUTRITION_RULES                  = load_nutrition_rules()

__all__ = [
    "CANONICAL_TAGS", "KEEP_CATEGORIES",
    "RECIPE_MAP", "FREETEXT_SKIP_SLUGS",
    "FOOD_LABELS", "JUNK_FOOD_IDS", "JUNK_FOOD_PATTERNS",
    "NUTRITION_RULES",
]