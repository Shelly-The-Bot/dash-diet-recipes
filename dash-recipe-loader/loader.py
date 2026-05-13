#!/usr/bin/env python3
"""
dash-recipe-loader — core logic

HTML parsing, algebraic validation, component building, save.
No LLM calls — those happen in SKILL.md via delegate_task.
"""

import sys
import json
import re
import subprocess
import yaml
import argparse
from pathlib import Path
from datetime import date
from typing import Optional, List, Dict, Any

# ── Paths ──────────────────────────────────────────────────────────────────

SKILL_DIR = Path(__file__).parent
REFERENCES_DIR = SKILL_DIR / "references"
DASH_FOODS_PATH = REFERENCES_DIR / "dash_foods.yaml"
CONVERSIONS_PATH = REFERENCES_DIR / "conversions.yaml"

# ── Load reference data ──────────────────────────────────────────────────────

with open(DASH_FOODS_PATH) as f:
    dash_foods_data = yaml.safe_load(f)
    DASH_MAP = dash_foods_data.get("mapping", {})

with open(CONVERSIONS_PATH) as f:
    conversions = yaml.safe_load(f)

VOL_PER_CUP = conversions.get("volume_per_cup_g", {})
STANDARD_AMOUNTS = conversions.get("standard_amounts", {})

# ── DASH constants ────────────────────────────────────────────────────────────

DASH_GROUPS = ["grains", "meats", "vegetables", "fruits", "dairy", "nuts", "sweets", "fats"]
VALID_DASH_GROUPS = set(DASH_GROUPS)

# ── Data structures ───────────────────────────────────────────────────────────

class Nutrition:
    __slots__ = ('kcal', 'protein_g', 'carbs_g', 'fat_g', 'sodium_mg', 'fiber_g', 'gl')
    def __init__(self, kcal=0.0, protein_g=0.0, carbs_g=0.0, fat_g=0.0,
                 sodium_mg=0.0, fiber_g=0.0, gl=None):
        self.kcal = kcal; self.protein_g = protein_g; self.carbs_g = carbs_g
        self.fat_g = fat_g; self.sodium_mg = sodium_mg; self.fiber_g = fiber_g
        self.gl = gl
    def to_dict(self):
        return {"kcal": round(self.kcal,1), "protein_g": round(self.protein_g,1),
                "carbs_g": round(self.carbs_g,1), "fat_g": round(self.fat_g,1),
                "sodium_mg": round(self.sodium_mg,1), "fiber_g": round(self.fiber_g,1),
                "gl": round(self.gl,1) if self.gl is not None else None}
    def __add__(self, other):
        if other is None: return self
        return Nutrition(self.kcal+other.kcal, self.protein_g+other.protein_g,
                         self.carbs_g+other.carbs_g, self.fat_g+other.fat_g,
                         self.sodium_mg+other.sodium_mg, self.fiber_g+other.fiber_g,
                         (self.gl or 0)+(other.gl or 0) if other.gl is not None else None)
    def scale(self, f):
        return Nutrition(self.kcal*f, self.protein_g*f, self.carbs_g*f, self.fat_g*f,
                         self.sodium_mg*f, self.fiber_g*f, self.gl*f if self.gl else None)

# ── HTML Parsing ──────────────────────────────────────────────────────────────

class RecipeHTMLParser:
    def __init__(self):
        self.title = ""; self.ingredients = []
        self._in_title = False; self._title_tag = None
        self._in_ingredient_list = False; self._list_depth = 0
        self._saw_ingredients_heading = False

    def parse(self, html: str) -> dict:
        """Parse HTML → {title, ingredients[], servings}."""
        # Extract title from h1
        title_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
        if title_m:
            self.title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()

        # Extract ingredients from <li> blocks
        ingredient_blocks = re.findall(
            r'<li[^>]*>(.*?)</li>', html, re.IGNORECASE | re.DOTALL)
        for block in ingredient_blocks:
            text = re.sub(r'<[^>]+>', '', block).strip()
            if len(text) > 3 and len(text) < 500 and not text.startswith('{'):
                self.ingredients.append(text)

        return {"title": self.title, "ingredients": self.ingredients, "servings": None}

def parse_html(html_content: str) -> dict:
    parser = RecipeHTMLParser()
    return parser.parse(html_content)

# ── Algebraic validation ─────────────────────────────────────────────────────

def validate_parsed_ingredient(ing: dict) -> tuple[bool, List[str]]:
    """
    Validate a parsed ingredient against the schema.
    Returns (is_valid, list_of_errors).
    """
    errors = []
    if not ing.get("name") and not ing.get("name_normalized"):
        errors.append("missing: name or name_normalized")
    if ing.get("amount_grams") is not None and ing["amount_grams"] <= 0:
        errors.append(f"amount_grams must be > 0, got {ing['amount_grams']}")
    if ing.get("dash_group") is not None and ing["dash_group"] not in VALID_DASH_GROUPS:
        errors.append(f"invalid dash_group: {ing['dash_group']}")
    nutrients = ing.get("nutrients") or {}
    for field in ("kcal", "protein_g", "carbs_g", "fat_g", "sodium_mg", "fiber_g"):
        val = nutrients.get(field)
        if val is not None and val < 0:
            errors.append(f"negative nutrient {field}: {val}")
    return (len(errors) == 0, errors)

def validate_component(component: dict) -> tuple[bool, List[str]]:
    """Validate full component."""
    errors = []
    if not component.get("name"):
        errors.append("missing: name")
    if not component.get("category"):
        errors.append("missing: category")
    servings = component.get("servings")
    if not servings or servings < 1:
        errors.append(f"servings must be >= 1, got {servings}")
    if not isinstance(component.get("ingredients", []), list):
        errors.append("ingredients must be a list")
    return (len(errors) == 0, errors)

# ── Build Component ───────────────────────────────────────────────────────────

def infer_category(title: str, ingredient_names: List[str]) -> str:
    title_l = title.lower()
    names = " ".join(n.lower() for n in ingredient_names)
    cats = {
        "breakfast": ["oat", "porridge", "pancake", "muffin", "omelette", "scramble", "cereal", "overnight"],
        "lunch": ["sandwich", "wrap", "salad", "soup", "bowl"],
        "dinner": ["stir-fry", "roast", "bake", "grilled", "steamed", "braised"],
        "snack": ["ball", "bar", "bite", "crunch", "chip"],
        "dessert": ["cake", "cookie", "brownie", "pie", "ice cream", "sorbet"]
    }
    for cat, keywords in cats.items():
        if any(k in title_l or k in names for k in keywords):
            return cat
    return "high-protein"

def build_component(source_url: str, parsed_html: dict, llm_parsed: List[dict], servings: int = 2) -> dict:
    """
    Build Component from parsed HTML + LLM-parsed ingredients.

    Args:
        source_url: URL of the recipe
        parsed_html: {title, ingredients[], servings} from HTML parsing
        llm_parsed: list of {name, amount_grams, dash_group, nutrients, _status} from LLM
        servings: number of servings (default 2)
    """
    meta_warnings = []; unknown_ingredients = []; suspicious = False

    title = parsed_html.get("title") or "Unknown Recipe"
    raw_ingredients = parsed_html.get("ingredients") or []

    # Build ingredients list
    ingredients = []
    for i, raw_text in enumerate(raw_ingredients):
        if i < len(llm_parsed) and isinstance(llm_parsed[i], dict):
            p = llm_parsed[i]
        else:
            p = {}

        is_valid, ing_errors = validate_parsed_ingredient(p)
        if not is_valid:
            meta_warnings.append(f"ingredient[{i}]: {'; '.join(ing_errors)}")
            suspicious = True

        name_norm = (
            p.get("name_normalized") or p.get("name") or p.get("ingredient") or
            p.get("food_name") or ""
        )
        amount_grams = p.get("amount_grams")
        if isinstance(amount_grams, list):
            amount_grams = amount_grams[0] if amount_grams else None
        dash_group = p.get("dash_group")
        ing_status = p.get("_status", "unknown")

        ing = {
            "original_text": raw_text,
            "parsed_amount": p.get("amount_parsed", ""),
            "amount_grams": amount_grams,
            "name_normalized": name_norm,
            "fdc_id": p.get("fdc_id"),
            "food_name": name_norm,
            "dash_group": dash_group,
            "match_confidence": p.get("match_confidence", 0.0),
            "nutrients": p.get("nutrients"),
            "_status": ing_status
        }

        if dash_group is None:
            unknown_ingredients.append(raw_text)
            suspicious = True

        ingredients.append(ing)

    # DASH servings per group
    dash_per_serving = {g: 0.0 for g in DASH_GROUPS}
    group_counts = {}
    for ing in ingredients:
        if ing["dash_group"] and ing["amount_grams"]:
            group_counts[ing["dash_group"]] = group_counts.get(ing["dash_group"], 0) + 1
    if servings > 0:
        dash_per_serving.update({g: round(v/servings, 2) for g, v in group_counts.items()})

    # Compliance (placeholder — needs nutrients from LLM)
    bp_compliant = True; diabetes_compliant = True; biliary_compliant = True

    component = {
        "name": title,
        "category": infer_category(title, [i.get("name_normalized","") for i in ingredients]),
        "tags": [],
        "servings": servings,
        "source_url": source_url,
        "raw_ingredients": raw_ingredients,
        "ingredients": ingredients,
        "totals_per_serving": {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0,
                                "fat_g": 0.0, "sodium_mg": 0.0, "fiber_g": 0.0, "gl": None},
        "dash_servings_per_serving": dash_per_serving,
        "compliance": {"bp": bp_compliant, "diabetes": diabetes_compliant, "biliary": biliary_compliant},
        "_meta": {
            "unknown_ingredients": unknown_ingredients,
            "unknown_nutrients": [],
            "parsing_warnings": meta_warnings,
            "inference_notes": [f"servings: {servings}"],
            "suspicious": suspicious
        }
    }

    is_valid, comp_errors = validate_component(component)
    if not is_valid:
        component["_meta"]["parsing_warnings"].extend(comp_errors)
        component["_meta"]["suspicious"] = True

    return component

# ── Save to repo ─────────────────────────────────────────────────────────────

def ensure_repo() -> str:
    repo_dir = SKILL_DIR / "repo"
    if repo_dir.exists():
        return str(repo_dir)
    subprocess.run(
        ["gh", "repo", "clone", "Shelly-The-Bot/food-recipes", str(repo_dir)],
        check=True, capture_output=True, stderr=subprocess.DEVNULL)
    return str(repo_dir)

def save_component(component: dict) -> Optional[str]:
    try:
        repo_dir = ensure_repo()
    except Exception:
        return None

    slug = re.sub(r'[^a-z0-9]+', '-', component["name"].lower())
    slug = re.sub(r'^-|-$', '', slug)
    today = date.today().isoformat()
    filename = f"{slug}-{today}.json"
    recipes_dir = Path(repo_dir) / "recipes"
    recipes_dir.mkdir(parents=True, exist_ok=True)
    filepath = recipes_dir / filename

    with open(filepath, "w") as f:
        json.dump(component, f, indent=2, ensure_ascii=False)

    try:
        subprocess.run(["git", "-C", repo_dir, "add", f"recipes/{filename}"],
                       check=True, capture_output=True)
        msg = f"Add recipe: {component['name']}"
        if component["_meta"]["suspicious"]:
            msg += " [suspicious]"
        subprocess.run(["git", "-C", repo_dir, "commit", "-m", msg],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", repo_dir, "push"],
                       check=True, capture_output=True)
    except Exception:
        pass  # file written, git may fail if nothing to commit

    return str(filepath)

# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--html", default=None)
    ap.add_argument("--url", default=None)
    ap.add_argument("--parsed-json", default=None)  # LLM output as JSON string
    ap.add_argument("--servings", type=int, default=None)  # override servings
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--help", action="store_true")
    args, _ = ap.parse_known_args()

    if args.help or not args.html:
        print("Usage: loader.py --html '<html>' --url '<url>' [--parsed-json '<llm_json>'] [--json]")
        sys.exit(0)

    html_content = args.html
    source_url = args.url or ""

    # Step 1: Parse HTML
    parsed = parse_html(html_content)
    if not parsed.get("title"):
        parsed["title"] = "Parsed Recipe"

    # Step 2: Get LLM-parsed ingredients (from --parsed-json argument)
    if args.parsed_json:
        try:
            llm_parsed = json.loads(args.parsed_json)
            if not isinstance(llm_parsed, list):
                llm_parsed = [llm_parsed]
        except json.JSONDecodeError:
            llm_parsed = []
    else:
        # No LLM data — all ingredients will be marked unknown
        llm_parsed = []

    # Step 3: Build Component
    servings = args.servings if args.servings else parsed.get("servings") or 2
    component = build_component(source_url, parsed, llm_parsed, servings=servings)

    # Step 4: Save
    saved = save_component(component)

    result = {
        "success": bool(saved),
        "component": component,
        "warnings": component["_meta"]["parsing_warnings"],
        "saved_to": saved
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        c = component; meta = c["_meta"]
        print(f"Name: {c['name']}")
        print(f"Category: {c['category']}")
        print(f"Servings: {c['servings']}")
        print(f"Ingredients: {len(c['ingredients'])} total, {len(meta['unknown_ingredients'])} unknown")
        print(f"DASH: {c['dash_servings_per_serving']}")
        if meta["suspicious"]:
            print(f"suspicious: {len(meta['unknown_ingredients'])} unmapped ingredients")
        for w in meta["parsing_warnings"]:
            print(f"  -> {w}")
        if saved:
            print(f"Saved to: {saved}")

if __name__ == "__main__":
    main()