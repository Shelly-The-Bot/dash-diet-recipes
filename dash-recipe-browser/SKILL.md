---
name: dash-recipe-browser
description: Search and filter DASH diet recipes from Shelly-The-Bot/food-recipes. Supports filter mode (by category, macros, tags, compliance) and ingredient-match mode (given a list of available ingredients, rank recipes by how many ingredients match). Returns structured recipe list with match scores or nutrient summaries.
category: dash-diet-recipes
tags: [DASH, diet, recipes, meal-planning, food-database]
created: 2026-05-13
validated_recipes: 26
data_repo: Shelly-The-Bot/food-recipes
data_path: recipes/*.json
schema: recipes/schema.json
---

# `dash-recipe-browser`

Search DASH diet recipes from `Shelly-The-Bot/food-recipes` (26 recipes, all JSON).

## Two modes

### Mode 1 — Filter (structural constraints)

Exact-match or range filters on recipe attributes.

```
category:       breakfast | lunch | dinner | snack | dessert | high-protein
tags:           comma-separated tag list (any match)
max_kcal:       integer — per serving, inclusive
max_sodium_mg:  integer — per serving, inclusive
max_gl:         float   — glycemic load per serving, inclusive
min_protein_g:  float   — per serving, inclusive
max_protein_g:  float   — per serving, inclusive
min_fiber_g:    float   — per serving, inclusive
compliance:     bp | diabetes | biliary | unconditional  (must pass)
servings:       integer — exact match
```

### Mode 2 — Ingredient Match (inverse lookup)

Given a set of available ingredients, rank recipes by ingredient overlap.

CLI invocation:
```
browser.py match --have "ingredient1, ingredient2, ..." --threshold 0 --limit 10
```

Param `--have` (required): comma-separated available ingredients
Param `--threshold` (optional, default 0): minimum match score 0-100
Param `--limit` (optional, default 10): max results returned

**Score algebra:**
```
score(recipe R, ingredient set I) = | R.raw_ingredients ∩ I | / | R.raw_ingredients | × 100
```

- `∩` = token-level fuzzy match (lowercase, stemmed, stopwords removed)
- Score is a percentage: 100% = all ingredients matched
- Both matched and missing ingredients are reported per recipe

## Workflow

1. Load `index.json` from the repo to get the list of recipe files
2. Load each recipe JSON (lazy — only load fields needed for the query)
3. Apply filters in Mode 1; compute scores in Mode 2
4. Sort: Mode 1 by name, Mode 2 by score descending
5. Return structured results

## Output schema (per recipe)

**Filter mode:**
```json
{
  "name": "string",
  "category": "string",
  "tags": ["string"],
  "servings": "number",
  "source_url": "string | null",
  "per_serving": {
    "kcal": "number",
    "protein_g": "number",
    "carbs_g": "number",
    "fat_g": "number",
    "fiber_g": "number",
    "sodium_mg": "number",
    "gl": "number | null"
  },
  "compliance": {
    "bp": "boolean",
    "diabetes": "boolean",
    "biliary": "boolean"
  }
}
```

**Ingredient-match mode:**
```json
{
  "name": "string",
  "category": "string",
  "match_score": "number (0–100)",
  "matched_ingredients": ["string"],
  "missing_ingredients": ["string"],
  "per_serving": { ... }
}
```

## Data source

Repo: `https://github.com/Shelly-The-Bot/food-recipes`
Clone path: `~/.hermes/skills/dash-diet-recipes/dash-recipe-browser/repo/`
Schema: `recipes/schema.json`

Clone if not present. Update via `git -C repo pull origin main`.

## User-facing output format (IMPORTANT)

D expects human-friendly output. DASH is the GOAL — always calculated — but **never shown as tables or flags** to the user.

**Wrong (technical card format):**
```
## High-Protein Overnight Oats
category: breakfast
tags: high-protein, meal-prep, no-cook, vegetarian
per_serving: 864 kcal | 104g protein | 83g carbs | 14g fat | 607mg sodium
compliance: bp=true, diabetes=true, biliary=true
DASH servings: 2.4 grains, 3.33 sweets, 0.5 nuts, 0.83 fruits, 0.75 dairy
```

**Correct (human natural format):**
```
→ High-Protein Overnight Oats (breakfast)
  Oats, whey protein, chia seeds, banana, almond milk
  Mix in a jar, fridge overnight, eat in the morning
  104g protein, 864 kcal
```

Rules:
- Short natural description (what to make, not nutritional breakdown)
- No DASH tables, no compliance flags, no per-serving macros unless asked
- DASH is always calculated under the hood
- If multiple recipes: bullet list, one per line, max 3-4 lines each

## Pitfalls

- **Empty `have_ingredients` must return 0 results.** `tokenize("") = {}` so every recipe scores 0.0; `0.0 >= 0.0 = True`. Fix: check `if not query_tokens: results = []` before iterating recipes. Tested 2026-05-13.
- **No recipe in DB combines oatmeal + chicken for breakfast.** Tested 2026-05-13: 4 breakfast recipes exist — none have both oats and poultry. The gap is in the data, not the skill. Users should combine multiple recipe outputs or add whole ingredients.
- `raw_ingredients` are free-text strings — fuzzy matching is imperfect. Log match failures.
- `new_foods_needed` in recipes means FDC match failed — these ingredients may have unreliable nutrient data
- `compliance` flags are per-recipe; cumulative day-level sodium/protein must be tracked separately (planner skill)
- Some recipes have `prep_minutes: 0` or `cook_minutes: 0` — these are placeholders, not verified
- **3 recipes have `kcal=0`:** Chocolate Protein Mug Cake, Coconut Pomegranate Protein Pancakes, Protein Brownies. Do not rely on kcal for sorting/filtering without also checking protein_g or other macros.

## References

- `references/human-queries.md` — real human query transcripts and expected outputs (session 2026-05-13)
- **Empty `have_ingredients` must return 0 results.** `tokenize("") = {}` so every recipe scores 0.0; `0.0 >= 0.0 = True`. Fix: check `if not query_tokens: results = []` before iterating recipes. Tested 2026-05-13.
- **No recipe in DB combines oatmeal + chicken for breakfast.** Tested 2026-05-13: 4 breakfast recipes exist (High-Protein Overnight Oats, Coconut Pomegranate Protein Pancakes, Tofu Scramble, Turkey Egg Muffins) — none have both oats and poultry. Match query `oatmeal + chicken breast` at any threshold returns 0 results. The gap is in the data, not the skill.
