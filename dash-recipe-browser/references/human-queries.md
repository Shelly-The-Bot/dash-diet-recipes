# Real Human Query Examples

## Session 2026-05-13

### Query: "oatmeal and chicken breast for breakfast"
**Command used:**
```bash
python browser.py match --have "oatmeal, chicken breast" --threshold 30 --json
python browser.py filter --category breakfast --json
```

**Result:** 0 match results (no recipe has both). Breakfast filter found 4 recipes, none combine oats + poultry.

**Outcome:** User asked for two separate recipes — one oatmeal, one chicken breast, both breakfast-appropriate.

**Lesson:** `match` mode ignores category entirely. User expected combined filtering. Always document this gap.

---

### Breakfast oatmeal → High-Protein Overnight Oats
- category: breakfast, tags: [high-protein, meal-prep, no-cook, vegetarian]
- 864 kcal | 104g protein | 83g carbs | 14g fat | 607mg sodium | GL 22.9
- ½ cup rolled oats + 1 scoop whey protein + chia seeds + banana + almond milk

### Breakfast chicken → Turkey & Veggie Egg Muffins  
- category: breakfast, tags: [high-protein, meal-prep, batch-cook, low-carb]
- 249 kcal | 27g protein | 4.8g carbs | 12.7g fat | 201mg sodium | GL 1.3
- ground turkey + eggs + spinach + bell peppers

---

### Filter example: dinner + low sodium
```bash
python browser.py filter --category dinner --max-sodium-mg 500 --json
```
→ 5 results (Beef Stir-Fry 56.6mg, Chocolate Protein Mug Cake 0mg, Protein Brownies 0mg, Salmon 27.6mg, Tempeh Stir-Fry 10.9mg)

---

### Match example: salmon + quinoa + asparagus @ 80%
```bash
python browser.py match --have "salmon, quinoa, asparagus" --threshold 80 --json
```
→ 1 result: Salmon with Quinoa and Asparagus (score=100.0)
