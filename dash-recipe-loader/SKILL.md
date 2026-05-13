---
name: dash-recipe-loader
description: Fetch recipe from any URL → parse ingredients via LLM subagent → validate algebraically → save as normalized Component to food-recipes repo.
tags: [dash-diet, recipe, meal-planning, llm, extraction]
category: dash-diet-recipes
---
# dash-recipe-loader

## Purpose
Fetch a recipe from any URL → parse HTML to extract raw ingredients → LLM subagent inference → algebraic validation → save as normalized Component to food-recipes repo.

## Architecture

```
Recipe URL
  └─ browser_navigate → HTML content
        └─ loader.py --html → raw_ingredients[]
              └─ SKILL.md: delegate_task → LLM parsed JSON
                    └─ loader.py --html --parsed-json → validated Component
                          └─ save to repo + git push
```

**Critical: LLM calls live in SKILL.md (via `delegate_task` tool), NOT in Python code.**
Python 3.9 in skill context cannot import hermes-agent (3.10+ syntax). Python modules = pure data ops.

## Key Rules

**LLM for ingredient parsing, NOT regex.** User explicitly rejected regex for ambiguous text parsing. Regex is acceptable only for deterministic HTML structure extraction (title, `<li>` items). All ingredient name/amount/unit inference → `delegate_task`.

**delegate_task lives in SKILL.md, not Python.** `delegate_task` is a Hermes tool callable only from the orchestration layer. Python loader files cannot import it (hermes-agent uses Python 3.10+ syntax incompatible with host Python 3.9). LLM inference always goes in SKILL.md; loader.py does pure data ops only.

**Field name mapping is required.** Subagent output may use `ingredient` (not `name_normalized`), `name` (not `name_normalized`), `amount_grams` as `[n]` list (not scalar). Always normalize — see field mapping table below.

**Check "Makes N" in page content.** Pass `--servings N` explicitly when the page states serving count. HTML parser won't find it automatically.

**Emphasize nutrients in LLM prompt.** If prompt doesn't explicitly ask for `{kcal,protein_g,carbs_g,fat_g,sodium_mg,fiber_g}`, model returns null. Not an error — but nutrients=null makes the component incomplete. Always include nutrient computation in the prompt.

## Field Mapping (subagent output → loader normalization)

| Subagent may return | → Normalized to |
|---------------------|----------------|
| `ingredient` / `name` / `name_normalized` / `food_name` | `name_normalized` |
| `amount_grams` as `40` or `[40]` | `amount_grams` as float |
| `nutrients` as object or `null` | passed through (null = incomplete, not error) |
| `original` (string) | `original_text` fallback |

## Pipeline

```
URL
  │
  ├─ Step 1: FETCH ──────────→ browser_navigate(url)
  │                              browser_console("document.querySelector('article').innerHTML")
  │
  ├─ Step 2: EXTRACT ─────────→ execute_code: loader.py --html "<html>" --url "<url>" --json
  │                              → { success, component: { raw_ingredients[], title } }
  │
  ├─ Step 3: PARSE ────────────→ delegate_task (leaf, terminal+file)
  │                              Goal: ingredient-parsing prompt (see below)
  │                              Context: raw_ingredients[]
  │                              → returns JSON array of parsed ingredients
  │
  ├─ Step 4: BUILD ─────────────→ execute_code: loader.py --html "<html>" --url "<url>" --parsed-json "<llm_json>" --servings N --json
  │                              → { success, component: Component, warnings[], saved_to }
  │
  └─ Step 5: PUSH ──────────────→ git commit + push happens inside loader.py save_component()
```

## Algebraic Component Schema

```json
{
  "name": "string",
  "category": "breakfast | lunch | dinner | snack | dessert | high-protein",
  "tags": ["string"],
  "servings": 2,
  "source_url": "https://...",
  "raw_ingredients": ["1/2 cup rolled oats", "..."],
  "ingredients": [{
    "original_text": "1/2 cup rolled oats",
    "parsed_amount": "0.5 cup",
    "amount_grams": 80.0,
    "name_normalized": "rolled oats",
    "fdc_id": null,
    "food_name": "rolled oats",
    "dash_group": "grains | meats | vegetables | fruits | dairy | nuts | sweets | fats | null",
    "match_confidence": 0.0,
    "nutrients": { "kcal": float, "protein_g": float, "carbs_g": float, "fat_g": float, "sodium_mg": float, "fiber_g": float } | null,
    "_status": "known | uncertain | unknown"
  }],
  "totals_per_serving": {
    "kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0,
    "fat_g": 0.0, "sodium_mg": 0.0, "fiber_g": 0.0, "gl": null
  },
  "dash_servings_per_serving": {
    "grains": 0.0, "meats": 0.0, "vegetables": 0.0, "fruits": 0.0,
    "dairy": 0.0, "nuts": 0.0, "sweets": 0.0, "fats": 0.0
  },
  "compliance": { "bp": bool, "diabetes": bool, "biliary": bool },
  "_meta": {
    "unknown_ingredients": ["string"],
    "unknown_nutrients": ["string"],
    "parsing_warnings": ["string"],
    "inference_notes": ["string"],
    "suspicious": true
  }
}
```

## DASH Food → Group Reference

| Group | Examples |
|-------|----------|
| grains | oats, rice, wheat, bread, pasta, quinoa, barley, couscous |
| meats | chicken, beef, pork, fish, turkey, lamb |
| vegetables | broccoli, spinach, carrots, peppers, tomatoes, turmeric, vegetable stock |
| fruits | banana, apple, berries, orange, mango |
| dairy | milk, yogurt, cheese |
| nuts | almonds, walnuts, peanuts |
| sweets | sugar, honey, maple syrup, mango chutney |
| fats | olive oil, butter, coconut oil, curry paste |

Full mapping: `dash-recipe-loader/references/dash_foods.yaml`

## Validation Rules (Algebraic)

For each parsed ingredient:
- `amount_grams > 0` if known
- `dash_group ∈ {grains,meats,vegetables,fruits,dairy,nuts,sweets,fats,null}`
- `nutrients.{kcal,protein_g,carbs_g,fat_g,sodium_mg,fiber_g} ≥ 0` if present

For component:
- `name` is non-empty
- `category ∈ {breakfast,lunch,dinner,snack,dessert,high-protein}`
- `servings ≥ 1`
- `ingredients` is a list

Any violation → mark `suspicious=true`, log to `parsing_warnings`.

## LLM Subagent Prompt (delegate_task goal)

```
You are a precise ingredient parser for DASH diet meal planning.

Given a list of raw ingredient texts from a recipe, output ONLY a valid JSON array — no markdown fences, no explanation, no preamble.

For each ingredient text return:
{
  "ingredient": "rolled oats",
  "amount_grams": 80.0,
  "dash_group": "grains",
  "match_confidence": 1.0,
  "nutrients": { "kcal": 389, "protein_g": 16.9, "carbs_g": 66, "fat_g": 6.9, "sodium_mg": 2, "fiber_g": 11 },
  "_status": "known",
  "original": "1/2 cup rolled oats"
}

Rules:
- amount_grams: metric. 1 cup rolled oats=80g, 1 cup water=240ml≈240g, 1 medium banana=118g, 1 tbsp=15ml→olive oil≈14g, 1 tsp=5ml, chicken breast 1 breast≈170g
- `"to taste"` / unquantified → `amount_grams: null, _status: "uncertain"` — INCLUDED in meal plan with warning
- salt and sugar are NEVER adjustable by D — they are fixed recipe ingredients
- If food not in DASH reference → dash_group=null, match_confidence=0.0, _status="unknown"
- If uncertain → _status="uncertain", still provide best guess
- nutrients: per 100g, scaled to amount_grams. Always compute: kcal, protein_g, carbs_g, fat_g, sodium_mg, fiber_g
- original: exact text from recipe
- Return JSON array only. Output nothing else.
```

## Usage

```
load: dash-recipe-loader

Single recipe from URL:
  loader.py --url "https://example.com/recipe" [--json]

Provide raw HTML (if fetching separately):
  loader.py --html "<html content>" --url "<source_url>" [--json]

Provide pre-parsed LLM JSON:
  loader.py --html "<html>" --url "<url>" --parsed-json '<llm_output>'

With servings override (when page says "Makes N"):
  loader.py --html "<html>" --url "<url>" --servings 4 --parsed-json '<llm_output>'
```

## Output

- Success: prints Component JSON, saves to `~/.hermes/skills/dash-diet-recipes/dash-recipe-loader/repo/recipes/<slug>-YYYY-MM-DD.json`
- Suspicious: `component._meta.suspicious=true`, unknown_ingredients listed
- Git: auto-commits and pushes to Shelly-The-Bot/food-recipes

## Limitations & Pitfalls

- **HTTP fetch blocked**: Most recipe sites (AllRecipes, BBC, FoodNetwork) return 402/404 to headless HTTP clients. Use `browser_navigate` + `browser_console("document.querySelector('article').innerHTML")` for fetch.
- **Ingredients matched by index**: `llm_parsed[i]` maps to `raw_ingredients[i]`. If counts differ, smaller count wins — no re-ordering.
- **Suspicious ≠ error**: `suspicious: true` means unknown ingredients or incomplete data. Save anyway; mark for human review.
- **`save_component` auto-pushes**: git commit + push happens inside `save_component()` — no separate push step needed.
- **LLM nutrients may be null**: If prompt doesn't emphasize nutrients, model returns null. Not an error — mark `nutrients: null`, `suspicious: true`.

## Files

- `loader.py` — HTML parsing, validation, component building, save. No LLM calls.
- `references/dash_foods.yaml` — food→DASH group mapping (extend as needed)
- `references/conversions.yaml` — volume/weight conversions for metric normalization
