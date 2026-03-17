"""
steps/enrich.py  —  Step 7: LLM Recipe Enrichment

Audits every recipe against a quality standard and interactively enriches
any that fall short. Rather than only filling in missing fields, this step
reviews ALL recipes and surfaces any that don't meet the full spec.

QUALITY STANDARD
────────────────
Every recipe should have:
  ✓ description     — substantive, ≥ 80 chars, specific to the dish
  ✓ notes           — ≥ 3 {title, text} items covering practical tips
  ✓ freezer note    — one note assessing freezability (only stored + tag
                       added if the dish actually freezes well)
  ✓ nutrition       — ≥ 4 of 7 fields filled (calories, fat, protein,
                       carbs, fiber, sodium, sugar)
  ✓ recipeServings  — non-zero, plausible given ingredient quantities
  ✓ totalTime       — present and non-empty
  ✓ prepTime        — present and non-empty
  ✓ performTime     — present and non-empty (cook time)

PROMPT APPROACH
───────────────
Rather than "fill in the blanks", the prompt passes the current values
and asks the LLM to review and improve them. This ensures consistency
across recipes that were partially enriched in earlier sessions.

FREEZER TAG LOGIC
─────────────────
  - Freezer tag ADDED only when a note positively confirms freezability
  - Freezer tag REMOVED if a negative freezer note exists and tag is present
  - No tag action if no freezer note exists at all (handled on next run)

NAVIGATION
──────────
  paste response + Enter twice  → review preview
  a                             → apply after preview
  r                             → redo / re-paste
  s                             → skip this recipe
  q                             → quit session
"""
from __future__ import annotations

import json
import re
import sys

from core import req, get_all, get_url, color, summary


# ══════════════════════════════════════════════════════════════════
# SKIP LIST — recipes permanently exempt from enrichment
# Add slugs here for joke/meta/placeholder recipes that will never
# have real nutrition data or meaningful enrichment.
# ══════════════════════════════════════════════════════════════════

ENRICH_SKIP_SLUGS: set[str] = {
    "cheap-steak",  # joke recipe — no real ingredients or nutrition
}

# ══════════════════════════════════════════════════════════════════
# QUALITY THRESHOLDS
# ══════════════════════════════════════════════════════════════════

DESCRIPTION_MIN_LEN  = 80
NOTES_MIN_COUNT      = 3
NUTRITION_FIELDS     = [
    "calories", "fatContent", "proteinContent", "carbohydrateContent",
    "fiberContent", "sodiumContent", "sugarContent",
]
NUTRITION_MIN_FIELDS = 4

NEGATIVE_FREEZE_PHRASES = [
    "does not freeze", "don't freeze", "do not freeze",
    "not freeze", "won't freeze", "cannot freeze",
    "doesn't freeze", "avoid freezing", "not suitable for freez",
    "not recommended for freez",
]


# ══════════════════════════════════════════════════════════════════
# AUDIT
# ══════════════════════════════════════════════════════════════════

class RecipeAudit:
    def __init__(self) -> None:
        self.needs_description  = False
        self.needs_notes        = False
        self.needs_more_notes   = False
        self.needs_freezer_note = False
        self.needs_nutrition    = False
        self.needs_servings     = False
        self.needs_total_time   = False
        self.needs_prep_time    = False
        self.needs_cook_time    = False

    @property
    def has_issues(self) -> bool:
        return any([
            self.needs_description, self.needs_notes, self.needs_more_notes,
            self.needs_freezer_note, self.needs_nutrition, self.needs_servings,
            self.needs_total_time, self.needs_prep_time, self.needs_cook_time,
        ])

    @property
    def issues(self) -> list[str]:
        out = []
        if self.needs_description:   out.append("description (missing or too short)")
        if self.needs_notes:         out.append("notes (none)")
        if self.needs_more_notes:    out.append(f"notes (fewer than {NOTES_MIN_COUNT} items)")
        if self.needs_freezer_note:  out.append("freezer note (not yet assessed)")
        if self.needs_nutrition:     out.append("nutrition (missing or sparse)")
        if self.needs_servings:      out.append("recipeServings (missing or zero)")
        if self.needs_total_time:    out.append("totalTime")
        if self.needs_prep_time:     out.append("prepTime")
        if self.needs_cook_time:     out.append("performTime (cook time)")
        return out


def _has_positive_freezer_note(notes: list[dict]) -> bool:
    """True if any note positively confirms the dish freezes well."""
    for note in notes:
        title = str(note.get("title", "")).lower()
        text  = str(note.get("text",  "")).lower()
        if "freez" in title or "freez" in text:
            if not any(p in text for p in NEGATIVE_FREEZE_PHRASES):
                return True
    return False


def _has_any_freezer_note(notes: list[dict]) -> bool:
    """True if any note (positive or negative) mentions freezing."""
    for note in notes:
        title = str(note.get("title", "")).lower()
        text  = str(note.get("text",  "")).lower()
        if "freez" in title or "freez" in text:
            return True
    return False


def _has_freezer_tag(detail: dict) -> bool:
    return any(
        t.get("name", "").lower() == "freezer"
        for t in (detail.get("tags") or [])
    )


def audit_recipe(detail: dict) -> RecipeAudit:
    a = RecipeAudit()

    desc = (detail.get("description") or "").strip()
    if len(desc) < DESCRIPTION_MIN_LEN:
        a.needs_description = True

    notes = detail.get("notes") or []
    if not notes:
        a.needs_notes = True
    elif len(notes) < NOTES_MIN_COUNT:
        a.needs_more_notes = True

    if not _has_any_freezer_note(notes):
        a.needs_freezer_note = True

    nutrition = detail.get("nutrition") or {}
    filled = sum(
        1 for f in NUTRITION_FIELDS
        if str(nutrition.get(f, "") or "").strip()
        and str(nutrition.get(f, "") or "").strip() not in ("0", "0.0")
    )
    if filled < NUTRITION_MIN_FIELDS:
        a.needs_nutrition = True

    servings = detail.get("recipeServings") or detail.get("recipeYieldQuantity") or 0
    try:
        if float(servings) <= 0:
            a.needs_servings = True
    except (ValueError, TypeError):
        a.needs_servings = True

    if not (detail.get("totalTime") or "").strip():
        a.needs_total_time = True
    if not (detail.get("prepTime") or "").strip():
        a.needs_prep_time = True
    if not (detail.get("performTime") or "").strip():
        a.needs_cook_time = True

    return a


# ══════════════════════════════════════════════════════════════════
# RECIPE TEXT EXTRACTION
# ══════════════════════════════════════════════════════════════════

def _extract_ingredients(detail: dict) -> list[str]:
    result = []
    for ing in detail.get("recipeIngredient", []):
        d = ing.get("display", "").strip()
        if d:
            mid = len(d) // 2
            if len(d) % 2 == 0 and d[:mid].strip() == d[mid:].strip():
                d = d[:mid].strip()
            result.append(d)
        elif ing.get("food"):
            qty       = ing.get("quantity") or ""
            unit      = ing.get("unit", {}) or {}
            food      = ing["food"].get("name", "")
            unit_name = unit.get("name", "") if unit else ""
            parts     = [str(qty) if qty else "", unit_name, food]
            result.append(" ".join(p for p in parts if p).strip())
    return [i for i in result if i]


def _extract_instructions(detail: dict) -> str:
    parts = []
    for step in detail.get("recipeInstructions", []):
        text = re.sub(r"<[^>]+>", " ", step.get("text", "")).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            parts.append(text)
    return "\n".join(f"{i+1}. {p}" for i, p in enumerate(parts))


def _format_existing_notes(notes: list[dict]) -> str:
    if not notes:
        return "    (none)"
    return "\n".join(
        f"    [{n.get('title', '')}] {str(n.get('text', ''))[:120]}"
        for n in notes
    )


# ══════════════════════════════════════════════════════════════════
# PROMPT BUILDER
# ══════════════════════════════════════════════════════════════════

def _build_prompt(detail: dict, audit: RecipeAudit) -> str:
    title        = detail.get("name", "Unknown")
    servings     = detail.get("recipeServings") or detail.get("recipeYieldQuantity") or "unknown"
    total_time   = detail.get("totalTime") or "unknown"
    prep_time    = detail.get("prepTime") or "unknown"
    cook_time    = detail.get("performTime") or "unknown"
    description  = (detail.get("description") or "").strip()
    notes        = detail.get("notes") or []
    nutrition    = detail.get("nutrition") or {}
    ingredients  = _extract_ingredients(detail)
    instructions = _extract_instructions(detail)

    issues_str       = "\n".join(f"  - {i}" for i in audit.issues)
    current_desc     = description or "(none)"
    current_notes    = _format_existing_notes(notes)
    current_nutrition_str = ", ".join(
        f"{k}: {v}" for k, v in nutrition.items()
        if str(v or "").strip() and str(v or "").strip() not in ("0", "0.0")
    ) or "(none)"

    return f"""You are a culinary assistant reviewing a recipe for quality and completeness.

RECIPE: {title}
Servings: {servings}
Total time: {total_time} | Prep: {prep_time} | Cook: {cook_time}

INGREDIENTS:
{chr(10).join(f"  - {i}" for i in ingredients)}

INSTRUCTIONS:
{instructions}

CURRENT VALUES (review and improve where needed):
  description :
    {current_desc}
  notes :
{current_notes}
  nutrition   : {current_nutrition_str}

QUALITY ISSUES DETECTED:
{issues_str}

TASK:
Fix ONLY the detected issues listed above. Return null for any field that already
meets the standard and is NOT listed as an issue.

Exceptions:
- nutrition: always return all 7 fields (we merge with existing, not replace)
- notes: always return the complete array so existing notes are preserved

Return ONLY this JSON object:

{{
  "description": "1-2 sentences describing the dish — or null if description is not listed as an issue.",
  "notes": [
    {{"title": "Tip title", "text": "Tip detail (1-2 sentences)."}},
    {{"title": "Storage", "text": "How to store and for how long."}},
    {{"title": "Freezer", "text": "How to freeze and reheat — OR a brief note explaining why it does not freeze well."}}
  ],
  "nutrition": {{
    "calories": "kcal per serving",
    "fatContent": "grams",
    "proteinContent": "grams",
    "carbohydrateContent": "grams",
    "fiberContent": "grams",
    "sodiumContent": "milligrams",
    "sugarContent": "grams"
  }},
  "recipeServings": "corrected float or null if correct",
  "totalTime": "e.g. 45 minutes — or null if already correct",
  "prepTime": "e.g. 15 minutes — or null if already correct",
  "performTime": "cook time e.g. 30 minutes — or null if already correct"
}}

RULES:
- description: return null if NOT listed as an issue. If it IS an issue, write 1-2
  sentences specific to this dish, its flavor, and appeal.
- notes: return the COMPLETE updated array. Preserve any existing good notes and add
  missing ones. Aim for 3-5 items: storage, substitutions, make-ahead, serving tips,
  heat/seasoning.
  FREEZER RULE: ALWAYS include a "Freezer" note. If the dish freezes well, explain
  how to freeze and reheat. If it does NOT freeze well (crispy elements, fresh greens,
  fried components, delicate emulsions), write a brief note explaining why not.
  The Freezer tag will only be added for dishes that freeze well.
- nutrition: estimate all 7 fields. Return all fields even if some were already present.
- recipeServings: return corrected float only if wrong, null if correct.
- times: return value only if missing (e.g. "45 minutes"), null if already present.
- Return raw JSON only. No markdown fences, no preamble, no explanation."""


# ══════════════════════════════════════════════════════════════════
# FREEZER TAG MANAGEMENT
# ══════════════════════════════════════════════════════════════════

def _add_freezer_tag(slug: str, detail: dict) -> None:
    try:
        tags_resp = req("GET", "/api/organizers/tags",
                        params={"search": "Freezer", "perPage": 20})
        freezer_tag = next(
            (t for t in tags_resp.get("items", [])
             if t.get("name", "").lower() == "freezer"),
            None
        )
        if not freezer_tag:
            print(f"  {color.warn("WARNING")}: Freezer tag not found in Mealie", file=sys.stderr)
            return
        current_tags = detail.get("tags") or []
        if any(t.get("name", "").lower() == "freezer" for t in current_tags):
            return
        tag_payload = [
            {"id": t["id"], "name": t["name"], "slug": t["slug"]}
            for t in current_tags if t.get("id")
        ]
        tag_payload.append({
            "id":   freezer_tag["id"],
            "name": freezer_tag["name"],
            "slug": freezer_tag["slug"],
        })
        req("PATCH", f"/api/recipes/{slug}", {"tags": tag_payload})
        print(f"    {color.ok("✓ Freezer tag added")}")
    except Exception as e:
        print(f"  WARNING: could not add Freezer tag: {e}", file=sys.stderr)


def _remove_freezer_tag(slug: str, detail: dict) -> None:
    try:
        current_tags = detail.get("tags") or []
        if not any(t.get("name", "").lower() == "freezer" for t in current_tags):
            return
        tag_payload = [
            {"id": t["id"], "name": t["name"], "slug": t["slug"]}
            for t in current_tags
            if t.get("id") and t.get("name", "").lower() != "freezer"
        ]
        req("PATCH", f"/api/recipes/{slug}", {"tags": tag_payload})
        print(f"    {color.warn("✓ Freezer tag removed")} (dish does not freeze well)")
    except Exception as e:
        print(f"  WARNING: could not remove Freezer tag: {e}", file=sys.stderr)


def _sync_freezer_tag(slug: str, detail: dict, applied_notes: list[dict]) -> None:
    """Add or remove the Freezer tag based on the applied notes."""
    has_positive = _has_positive_freezer_note(applied_notes)
    has_any      = _has_any_freezer_note(applied_notes)
    has_tag      = _has_freezer_tag(detail)

    if has_positive and not has_tag:
        _add_freezer_tag(slug, detail)
    elif has_any and not has_positive and has_tag:
        _remove_freezer_tag(slug, detail)
    elif has_positive and has_tag:
        pass  # already correct, no action needed


# ══════════════════════════════════════════════════════════════════
# APPLY ENRICHMENT
# ══════════════════════════════════════════════════════════════════

def _apply_enrichment(slug: str, detail: dict, data: dict) -> bool:
    patch: dict = {}

    if data.get("description") and data["description"] is not None:
        new_desc = str(data["description"]).strip()
        existing_desc = (detail.get("description") or "").strip()
        if new_desc and new_desc != existing_desc:
            patch["description"] = new_desc

    applied_notes: list[dict] = []
    if data.get("notes") and isinstance(data["notes"], list):
        note_items = []
        for item in data["notes"]:
            if isinstance(item, dict):
                note_items.append({
                    "title": str(item.get("title", "")).strip(),
                    "text":  str(item.get("text",  "")).strip(),
                })
            elif isinstance(item, str) and item.strip():
                parts = item.strip().split(":", 1)
                if len(parts) == 2:
                    note_items.append({"title": parts[0].strip(), "text": parts[1].strip()})
                else:
                    note_items.append({"title": "", "text": item.strip()})
        if note_items:
            patch["notes"] = note_items
            applied_notes = note_items

    if not applied_notes:
        applied_notes = detail.get("notes") or []

    if data.get("nutrition") and isinstance(data["nutrition"], dict):
        existing = detail.get("nutrition") or {}
        merged = {}
        for f in NUTRITION_FIELDS:
            llm_val = data["nutrition"].get(f)
            existing_val = str(existing.get(f, "") or "").strip()
            # Reject zero values from LLM — they mean "I don't know", not actual zeros
            llm_str = str(llm_val).strip() if llm_val is not None else ""
            if llm_str and llm_str not in ("0", "0.0", "null", "None"):
                merged[f] = llm_str
            elif existing_val and existing_val not in ("0", "0.0"):
                merged[f] = existing_val
        if merged:
            patch["nutrition"] = merged

    if data.get("recipeServings") is not None:
        try:
            corrected = float(data["recipeServings"])
            current   = float(detail.get("recipeServings") or 0)
            if corrected != current and corrected > 0:
                patch["recipeServings"] = corrected
        except (ValueError, TypeError):
            pass

    for tf in ("totalTime", "prepTime", "performTime"):
        if data.get(tf) is not None:
            patch[tf] = str(data[tf]).strip()

    if not patch:
        print("  Nothing to apply.")
        return False

    try:
        req("PATCH", f"/api/recipes/{slug}", patch)
    except Exception as e:
        print(f"  ✗ PATCH failed: {e}", file=sys.stderr)
        return False

    _sync_freezer_tag(slug, detail, applied_notes)
    return True


# ══════════════════════════════════════════════════════════════════
# PREVIEW
# ══════════════════════════════════════════════════════════════════

def _show_preview(detail: dict, data: dict) -> None:
    print(f"\n  {color.bold('Preview of changes:')}") 

    if data.get("description"):
        print(f"    {color.label('description')} : {str(data['description'])[:120]}")

    if data.get("notes") and isinstance(data["notes"], list):
        notes = data["notes"]
        print(f"    {color.label('notes')}       : {color.info(str(len(notes)) + ' items:')}")
        for n in notes[:4]:
            t  = n.get("title", "") if isinstance(n, dict) else ""
            tx = n.get("text",  "") if isinstance(n, dict) else str(n)
            print(f"      {color.cyan('[' + t + ']')} {color.muted(str(tx)[:90])}")
        if len(notes) > 4:
            print(f"      {color.muted(f'... ({len(notes) - 4} more)')}")

        has_positive = _has_positive_freezer_note(notes)
        has_any      = _has_any_freezer_note(notes)
        has_tag      = _has_freezer_tag(detail)
        if has_positive and not has_tag:
            print(f"    {color.label('freezer tag')} : {color.ok('✓ will be ADDED')}")
        elif has_any and not has_positive and has_tag:
            print(f"    {color.label('freezer tag')} : {color.error('✗ will be REMOVED')} (dish does not freeze well)")
        elif has_positive and has_tag:
            print(f"    {color.label('freezer tag')} : {color.ok('already present ✓')}")
        elif not has_any:
            print(f"    {color.label('freezer tag')} : {color.muted('no freezer note — tag unchanged')}")

    if data.get("nutrition") and isinstance(data["nutrition"], dict):
        n = data["nutrition"]
        print(f"    {color.label('nutrition')}   : "
              f"{color.bright_yellow(str(n.get('calories','?')) + ' kcal')} | "
              f"protein {n.get('proteinContent','?')}g | "
              f"carbs {n.get('carbohydrateContent','?')}g | "
              f"fat {n.get('fatContent','?')}g")

    if data.get("recipeServings") is not None:
        print(f"    {color.label('servings')}    : "
              f"{color.muted(str(detail.get('recipeServings','?')))} → "
              f"{color.ok(str(data['recipeServings']))}")

    for tf, lbl in [("totalTime","total time"), ("prepTime","prep time "), ("performTime","cook time ")]:
        if data.get(tf):
            print(f"    {color.label(lbl)}  : {data[tf]}")

    print()


# ══════════════════════════════════════════════════════════════════
# INPUT / PARSE
# ══════════════════════════════════════════════════════════════════

def _collect_input(title: str = "", url: str = "") -> str:
    if title:
        print(f"  {color.bold(color.bright_cyan(title))}  {color.link(url)}")
    print(f"  {color.bold('Paste LLM response below.')} Press Enter twice when done.")
    print(f"  {color.muted('(s = skip,  q = quit,  r = redo)')}\n")
    lines = []
    try:
        while True:
            line = input()
            if not lines and line.strip().lower() in ("s", "q", "r"):
                return line.strip().lower()
            if line == "" and lines:
                break
            lines.append(line)
    except (KeyboardInterrupt, EOFError):
        print()
        return "q"
    return "\n".join(lines)


def _parse_response(raw: str) -> dict | None:
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ✗ Could not parse JSON: {e}", file=sys.stderr)
        return None


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

def _recipe_url(slug: str) -> str:
    return f"{get_url()}/g/home/r/{slug}"


def step_enrich() -> None:
    print(f"\n{color.header('▶ STEP 7: RECIPE QUALITY AUDIT & ENRICHMENT')}\n")
    print(f"  {color.muted('Audits every recipe against the quality standard.')}")
    print(f"  {color.muted('Surfaces any that don\'t meet spec — not just ones with missing fields.')}\n")
    print(f"  {color.bold('Quality standard:')}")
    print(f"    {color.ok('•')} description    ≥ {DESCRIPTION_MIN_LEN} chars, specific to the dish")
    print(f"    {color.ok('•')} notes          ≥ {NOTES_MIN_COUNT} items with practical tips")
    print(f"    {color.ok('•')} freezer note   assessed (Freezer tag added ONLY if dish freezes well)")
    print(f"    {color.ok('•')} nutrition      ≥ {NUTRITION_MIN_FIELDS}/7 fields filled")
    print(f"    {color.ok('•')} servings       non-zero and plausible")
    print(f"    {color.ok('•')} times          totalTime, prepTime, performTime all present\n")

    recipes = get_all("/api/recipes")
    recipes_sorted = sorted(recipes, key=lambda r: r["name"].lower())

    print(f"  {color.muted(f'Auditing {len(recipes_sorted)} recipes...')}")
    candidates: list[tuple[dict, dict, RecipeAudit]] = []
    for summary in recipes_sorted:
        slug = summary["slug"]
        try:
            detail = req("GET", f"/api/recipes/{slug}")
        except Exception as e:
            print(f"  {color.error('ERROR')} fetching {summary['name']}: {e}", file=sys.stderr)
            continue
        if slug in ENRICH_SKIP_SLUGS:
            continue
        a = audit_recipe(detail)
        if a.has_issues:
            candidates.append((summary, detail, a))

    passing = len(recipes_sorted) - len(candidates)
    print(f"  {color.ok(str(passing))}/{len(recipes_sorted)} pass  —  {color.warn(str(len(candidates)))} need attention.\n")

    if not candidates:
        print(f"  {color.ok('✓ All recipes meet the quality standard.')}")
        return

    enriched = skipped = 0

    for idx, (summary, detail, audit) in enumerate(candidates, 1):
        title = summary["name"]
        slug  = summary["slug"]

        url = _recipe_url(slug)
        print(f"\n{color.muted('─' * 60)}")
        print(f"  {color.bold(color.bright_cyan(f'[{idx}/{len(candidates)}]'))} {color.bold(title)}")
        print(f"  {color.link(url)}")
        print(f"  {color.yellow('Issues:')}")
        for issue in audit.issues:
            print(f"    {color.error('✗')} {issue}")
        desc = (detail.get("description") or "").strip()
        if desc:
            print(f"  {color.muted('Current description:')} {desc[:100]!r}")
        print()

        prompt = _build_prompt(detail, audit)
        box_top    = color.cyan("  ┌─ COPY THIS PROMPT TO YOUR LLM ─────────────────────────")
        box_side   = color.cyan("  │ ")
        box_bottom = color.cyan("  └────────────────────────────────────────────────────────")
        print(box_top)
        for line in prompt.splitlines():
            print(f"{box_side}{line}")
        print(box_bottom)
        print()

        while True:
            raw = _collect_input(title=title, url=url)

            if raw == "q":
                print(f"\n  {color.warn('Quitting.')}")
                print(f"\n{color.ok('✓')} Session complete.  "
                      f"Enriched: {color.ok(str(enriched))}  "
                      f"Skipped: {color.muted(str(skipped))}")
                remaining = len(candidates) - enriched - skipped
                if remaining:
                    print(f"  {color.yellow(str(remaining))} remaining — run again to continue.")
                return

            if raw == "s":
                print(f"  {color.muted('Skipped.')}\n")
                skipped += 1
                break

            if raw == "r":
                print(f"  {color.yellow('Re-paste')} — go back to your LLM.\n")
                continue

            data = _parse_response(raw)
            if not data:
                print("  Could not parse JSON. Type r to re-paste, s to skip.\n")
                continue

            _show_preview(detail, data)

            action = input(f"  {color.bold('Apply (a), redo (r), or skip (s)?')} ").strip().lower()
            if action == "r":
                print(f"  {color.yellow('Re-paste')} — go back to your LLM.\n")
                continue
            elif action == "s":
                print(f"  {color.muted('Skipped.')}\n")
                skipped += 1
                break
            else:
                if _apply_enrichment(slug, detail, data):
                    print(f"  {color.ok('✓')} {color.bold(title)} updated.\n")
                    enriched += 1
                    summary.add("enrich", f"Recipe enriched: {title}")
                else:
                    skipped += 1
                break

    print(f"{color.muted('─' * 60)}")
    summary.add("enrich", f"Total: {enriched} enriched, {skipped} skipped")
    print(f"\n{color.ok('✓')} {color.bold('Enrichment session complete.')}")
    print(f"  Enriched : {color.ok(str(enriched))}")
    print(f"  Skipped  : {color.muted(str(skipped))}")
    remaining = len(candidates) - enriched - skipped
    if remaining:
        print(f"  {color.yellow(str(remaining))} remaining — run again to continue.")