---
name: dash-diet-recipes
description: "DASH Diet ecosystem: assess foods, browse/search recipes, create meal plans, batch-cook, generate grocery lists. Built on Shelly-The-Bot/food-recipes (26+ recipes). Core model: every food item = Component with servings, DASH profile, and nutritional data. Stack: dash-recipe-browser (search), dash-recipe-loader (URL→component), dash-meal-planner (compose meals), dash-grocery-list, dash-batch-prep, dash-diet-agent (orchestrator)."
category: dash-diet-recipes
tags: [DASH, diet, meal-planning, nutrition, food-database, health]
created: 2026-05-13
state: skeleton -- browser complete, others planned
children: [dash-recipe-browser]
---

# dash-diet-recipes

Class-level umbrella for the DASH Diet Agent ecosystem.

## Vision

Full stack for DASH-based nutrition management:

| Skill | Status | Responsibility |
|---|---|---|
| dash-recipe-browser | done | Filter + ingredient-match search |
| dash-meal-planner | planned | Profile + recipes to day/week plan |
| dash-grocery-list | planned | Plan to grouped shopping list |
| dash-batch-prep | planned | Batch sessions, timing, grouping |
| dash-diet-agent | planned | Orchestrator -- coordinates all sub-skills |

## Profile Model

Each skill accepts a profile for constraint propagation:

- gender: male | female
- age_range: 19-30 | 31-50 | 51+
- activity_level: sedentary | moderately_active | active
- weight_kg: float
- height_cm: float
- goals: bp | diabetes | weight-loss | athletic (list)
- max_sodium_mg: override DASH default (2300)
- max_calories: daily target

## DASH Compliance Flags

Each recipe has compliance object: bp (low sodium), diabetes (low GI/GL), biliary (low fat).
Sodium limit: 2,300 mg/day.

## Algebraic Definitions

```
R = set of all recipes (|R| = 26)
Filter: R_out(phi) = { r in R | phi(r) = true }
Match: score(r, I) = |tau(r.raw_ingredients) cap tau(I)| / |tau(r.raw_ingredients)| x 100
tau(text) = tokenize(lowercase, strip-punct, remove-stopwords)
```

## Known Data Issues

- 3 recipes have kcal=0 (import parsing incomplete)
- new_foods_needed non-empty means FDC matching failed
- Some prep_minutes/cook_minutes are 0 placeholders

## References

- references/test-matrix.md -- algebraic test matrix and results for dash-recipe-browser
- references/dash-reference.md -- DASH food groups, serving sizes, calorie tables
