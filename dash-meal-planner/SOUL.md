# dash-meal-planner

## Concept
Compose meals from **components** — any discrete food item with DASH data, regardless of source.

**Every component has:**
- name + source (recipe / reference food / batch)
- servings available (from a recipe = N portions; from a batch = N portions; from reference food = any amount)
- per-serving DASH profile (kcal, protein_g, carbs_g, fat_g, sodium_mg, fiber_g, gl, DASH group servings)

**Meal = Σ components (each scaled to target)**
**Time window = any (1 meal → 7 days → week)**

## Component Model

```
Component = {
  name: str,              # "Grilled Chicken Breast", "Stir-Fry Base"
  source: str,            # "recipe" | "reference" | "batch"
  servings: int,         # how many portions this batch makes
  per_serving: {
    kcal, protein_g, carbs_g, fat_g, sodium_mg, fiber_g, gl,
    dash_servings: { grains, meats, vegetables, fruits, dairy, nuts, sweets, fats }
  }
}
```

**Three sources:**
1. **Recipe** — run recipe → N identical portions
2. **Reference food** — store-bought / raw ingredient (boiled egg, banana, slice of bread)
3. **Batch** — self-contained cooked base (chicken+leeks+pepper+garlic+cabbage = stir-fry base x 7 servings)

**Key insight:** At meal-planning level, all three are identical — a component with N servings and known DASH per serving. The source doesn't matter to the planner.

## Recipe = Component Factory

```
Input:  recipe URL or structured recipe JSON
Output: Component(s) with DASH data per serving

The recipe is a "component factory":
  run it once → N portions of the same component
  each portion = same DASH profile

Complex multi-ingredient recipes abstract to a single component
with a summed DASH profile per serving.
```

Example: "Chicken with leeks, bell pepper, garlic, cabbage"
```
Recipe → stir-fry base → 7 servings
Each serving: { kcal, protein, carbs, fat, sodium, DASH groups }
User portions 1 serving per day → DASH accounted for
```

## Two Inference Modes for Portion Sizes

### Mode 1: DASH-driven (nutrient targets)
- Breakfast/Lunch/Dinner = 1/3 of daily DASH per category
- Time-of-day constrains the slot
- Find optimal portions that fit within DASH nutrient windows

### Mode 2: Requirements-driven (personal constraints)
- Daily kcal, sodium, body weight → per-meal budget
- Stomach capacity: ~300-400g solid food per meal
- Satiety: protein fills faster than carbs, fat fills slowest
- Max feasible portion per component

### Combined Output = Intersection
```
DASH breakfast slot:  sodium ≤ 800mg, kcal 400-600, protein ≥ 25g
Personal limits:      sodium ≤ 500mg, kcal ≤ 550, max 400g food volume

→ Intersection: sodium ≤ 500mg, kcal 400-550, protein ≥ 25g, max 400g
→ Portion sizes computed to fit inside this intersection
```

If modes contradict → warning shown, stricter constraint wins.

## Portion Adjustment (Sliders)

Portions are not fixed — user adjusts with sliders:
```
User moves "chicken" slider from 120g → 150g
→ system recalculates: DASH totals update live
→ warns if the move exceeds DASH or personal limits
```

Starting point is computed from DASH intersection. User fine-tunes.

## Time Window Scope

```
- Single meal (one plate)
- One day (breakfast + lunch + dinner, each calculated)
- Multi-day (3 days, 7 days, week)

System calculates portions for the chosen scope,
respecting cumulative DASH limits across all meals.

Batch components: portion-per-day from the batch, day-by-day combinations
Fresh components: added per day, DASH sums per day
```

## Real Human Example

User: "oatmeal, banana, chicken breast for breakfast"

```
Step 1: Classify each as component
  - "oatmeal"    → Component from recipe (cooked oats)
  - "banana"     → Component from reference food (whole, no cooking)
  - "chicken"    → Component from recipe (cooked chicken)

Step 2: Compute portions from DASH intersection
  - DASH breakfast: 400-600kcal, ≤500mg sodium, ≥25g protein
  - Personal: 550kcal max, 500mg sodium max, 400g volume max
  - → Starting portions calculated from intersection

Step 3: Output
  - Oatmeal: 150g cooked (275kcal, 9.7g protein, 49.5g carbs)
  - Banana: 1 medium (105kcal, 1.3g protein, 27g carbs)
  - Chicken: 120g cooked (165kcal, 31g protein, 0g carbs)
  - Combined: 545kcal, 42g protein, 76.5g carbs, ~280mg sodium
  - Fits within both DASH and personal constraints ✓

User adjusts sliders → DASH totals update live
```

## Relationship to Other Skills

| Skill | Role |
|-------|------|
| `dash-recipe-loader` | Extract recipe from URL → Component(s) with DASH data |
| `dash-recipe-browser` | Find recipes in the food-recipes repo |
| `dash-meal-planner` | Compose components into meals, any time window |
| `dash-grocery-list` | TBD |
| `dash-batch-prep` | TBD |

## Status
Not yet built. Design documented here.