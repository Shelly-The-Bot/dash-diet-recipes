# dash-recipe-browser: Test Matrix

Date: 2026-05-13
Recipes tested: 26 (full corpus)
Test harness: direct CLI, not inline Python copy.

## Critical Lesson

**Test the deployed file, not an inline copy.**

The inline test harness (execute_code with pasted code) creates a separate namespace from the actual `browser.py` on disk. Bugs in the file may not appear in the inline copy. Always verify fixes by calling the CLI (`python3 browser.py ...`) not just by re-running inline test code.

## Algebraic Definitions

```
R = all recipes (26 total)
Filter: R_out(phi) = { r in R | phi(r) = true }
Match score: score(r, I) = |tau(r.raw_ingredients) cap tau(I)| / |tau(r.raw_ingredients)| x 100
  where tau(text) = {lowercase tokens, strip punctuation, remove stopwords}
Threshold: match returned iff score >= threshold
Empty query: tokenize("") = empty set -> score = 0.0 for all r -> 0.0 >= 0.0 = True
  FIX: handle empty query as special case -> return 0 results
```

## Filter Mode: Results Reference

| Test | Predicate | Expected | Actual | Status |
|---|---|---|---|---|
| category=breakfast | r.category = "breakfast" | 4 | 4 | PASS |
| category=lunch | r.category = "lunch" | 4 | 5 | FAIL (index has 5) |
| category=dinner | r.category = "dinner" | 8 | 10 | FAIL (index has 10) |
| category=snack | r.category = "snack" | 3 | 3 | PASS |
| category=high-protein | r.category = "high-protein" | 2 | 2 | PASS |
| category=dessert | r.category = "dessert" | 0 | 0 | PASS |
| tags=high-protein | "high-protein" in r.tags | >0 | many | PASS |
| tags=batch,meal-prep | both in r.tags | >0 | some | PASS |
| compliance=bp | bp.pass=true | >0 | most | PASS |
| compliance=bp,diabetes,biliary | all three | >0 | many | PASS |
| max_kcal=200 | kcal <= 200 | >0 | some | PASS |
| max_kcal=500 | kcal <= 500 | >0 | many | PASS |
| max_kcal=0 | kcal <= 0 | 0 | 3 | FAIL (3 recipes have kcal=0) |
| max_sodium_mg=100 | Na <= 100 | >0 | many | PASS |
| max_gl=10 | GL <= 10 | >0 | some | PASS |
| min_protein_g=30 | protein >= 30 | >0 | some | PASS |
| min_protein_g=999 | protein >= 999 | 0 | 0 | PASS |
| min_fiber_g=5 | fiber >= 5 | >0 | some | PASS |
| dinner + max_kcal=400 | intersection | >0 | some | PASS |
| breakfast + bp + diabetes | intersection | >0 | some | PASS |
| kcal300 + Na100 + biliary | 3-way AND | >0 | some | PASS |
| lunch + meal-prep | intersection | >0 | some | PASS |
| dinner + vegan | incompatible | 0 | 1 | FAIL (Tempeh Stir-Fry is vegan+dinner) |
| limit=1 | top 1 by name | 1 | 1 | PASS |
| limit=0 | empty | 0 | 0 | PASS |

## Match Mode: Results Reference

| Test | Input | threshold | Expected | Actual | Status |
|---|---|---|---|---|---|
| M1 have=salmon | salmon | 0 | >0 | 2+ | PASS |
| M2 have=quinoa | quinoa | 0 | >0 | many | PASS |
| M3 have=tofu | tofu | 0 | >0 | some | PASS |
| M4 have=pickles | pickles | 0 | >0 | cheeseburger | PASS |
| M5 have=nonexistent | xyz123 | 0 | 0 | 0 | PASS (fixed) |
| M6 salmon+quinoa+asparagus | all 3 | 0 | 100% Salmon | 100% | PASS |
| M7 have=chicken,broccoli | chicken+broccoli | 0 | >0 | some | PASS |
| M8 have=eggs,cheese,beef | eggs+cheese+beef | 0 | >0 | cheeseburger | PASS |
| M9 threshold=100 (partial) | salmon+quinoa | 100 | 0 | 0 | PASS |
| M10 threshold=99 (includes 100) | salmon+quinoa | 99 | 0 | 0 | PASS |
| M11 have=chicken threshold=50 | chicken | 50 | >=50 | all >=50 | PASS |
| M12 limit=1 | chicken | 0 | 1 | 1 | PASS |
| M13 limit=0 | chicken | 0 | 0 | 0 | PASS |
| M14 case insensitive | SALMON | 0 | =salmon | equal | PASS |
| M15 substring | chicken breast | 0 | >0 | some | PASS |
| M16 empty string | "" | 0 | 0 | 0 | PASS (fixed) |

## Bugs Found and Fixed

1. **Empty query returning all recipes** (M5, M16)
   - Cause: tokenize("") = empty set; every recipe scored 0.0; 0.0 >= 0.0 = True
   - Fix: check `if not query_tokens: results = []` before iterating recipes

## Data Issues in Corpus

- kcal=0: Chocolate Protein Mug Cake, Coconut Pomegranate Protein Pancakes, Protein Brownies
- FDC unmatched: most recipes have many `new_foods_needed` entries
- lunch count: Grilled Chicken Thighs counted as lunch (category field = "lunch")
- dinner count: high-protein category + dinner-tagged recipes inflate count
