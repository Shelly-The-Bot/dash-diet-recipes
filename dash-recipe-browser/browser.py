#!/usr/bin/env python3
"""
dash-recipe-browser
Search and filter DASH diet recipes from Shelly-The-Bot/food-recipes.

Two modes:
  --filter    Apply structural filters (category, macros, tags, compliance)
  --match     Rank recipes by ingredient overlap score

Algebraic:
  Filter mode:   R_out = { r ∈ R | pred(r) = true }
  Match mode:    score(r, I) = |tokens(r.raw_ingredients) ∩ tokens(I)| / |tokens(r.raw_ingredients)| × 100
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# ── Paths ──────────────────────────────────────────────────────────────────────

SKILL_DIR = Path(__file__).parent
REPO_DIR  = SKILL_DIR / "repo"

# ── Helpers ────────────────────────────────────────────────────────────────────

STOPWORDS = {"and", "or", "the", "a", "an", "of", "in", "on", "with", "for", "to", "from", "any", "desired"}


def tokenize(text: str) -> set[str]:
    """Lowercase, strip punctuation, split on whitespace, remove stopwords."""
    words = re.sub(r"[^\w\s]", " ", text.lower()).split()
    return {w for w in words if w and w not in STOPWORDS}


def fuzzy_match(query_tokens: set[str], ingredient_tokens: set[str]) -> bool:
    """
    Returns True if any query token appears in any ingredient token.
    Allows partial substring match (e.g. "chicken" matches "chicken breast").
    """
    for qt in query_tokens:
        for it in ingredient_tokens:
            if qt in it or it in qt:
                return True
    return False


def load_index() -> list[dict[str, Any]]:
    """Load recipe index."""
    idx = REPO_DIR / "recipes" / "index.json"
    with open(idx) as f:
        return json.load(f)["recipes"]


def load_recipe(file_path: Path) -> dict[str, Any]:
    """Load a single recipe JSON."""
    with open(file_path) as f:
        return json.load(f)


def ensure_repo() -> None:
    """Clone or pull the food-recipes repo silently."""
    if REPO_DIR.exists():
        os.system(f"git -C {REPO_DIR} pull origin main >/dev/null 2>&1")
    else:
        os.system(f"git clone --quiet https://github.com/Shelly-The-Bot/food-recipes {REPO_DIR}")


# ── Filter mode ────────────────────────────────────────────────────────────────

def apply_filter(recipe: dict[str, Any], args: argparse.Namespace) -> bool:
    """Return True if recipe passes all filter predicates."""

    # Category
    if args.category:
        if recipe.get("category") != args.category:
            return False

    # Tags (any tag in args.tags must be present in recipe)
    if args.tags:
        recipe_tags = set(recipe.get("tags", []))
        for tag in args.tags:
            if tag not in recipe_tags:
                return False

    # Servings
    if args.servings is not None:
        if recipe.get("servings") != args.servings:
            return False

    # Compliance
    if args.compliance:
        comp = recipe.get("compliance", {})
        for flag in args.compliance:
            if not comp.get(flag, {}).get("pass", False):
                return False

    totals = recipe.get("totals_per_serving", {})

    def check(field: str, op: str, threshold: float) -> bool:
        val = totals.get(field, 0)
        if op == "<=":
            return val <= threshold
        if op == ">=":
            return val >= threshold
        return False

    if args.max_kcal is not None and not check("energy_kcal", "<=", args.max_kcal):
        return False
    if args.max_sodium_mg is not None and not check("sodium_mg", "<=", args.max_sodium_mg):
        return False
    if args.max_gl is not None:
        gl = totals.get("gl_fdc")
        if gl is not None and gl > args.max_gl:
            return False
    if args.min_protein_g is not None and not check("protein_g", ">=", args.min_protein_g):
        return False
    if args.max_protein_g is not None and not check("protein_g", "<=", args.max_protein_g):
        return False
    if args.min_fiber_g is not None and not check("fiber_g", ">=", args.min_fiber_g):
        return False

    return True


def recipe_to_filter_output(recipe: dict[str, Any]) -> dict[str, Any]:
    totals = recipe.get("totals_per_serving", {})
    comp   = recipe.get("compliance", {})
    src    = recipe.get("source", {})

    return {
        "name":       recipe.get("name", ""),
        "category":   recipe.get("category", "unknown"),
        "tags":       recipe.get("tags", []),
        "servings":   recipe.get("servings"),
        "source_url": src.get("url") if src.get("type") == "url" else None,
        "per_serving": {
            "kcal":      round(totals.get("energy_kcal", 0), 1),
            "protein_g": round(totals.get("protein_g", 0), 1),
            "carbs_g":   round(totals.get("carbohydrate_g", 0), 1),
            "fat_g":     round(totals.get("total_fat_g", 0), 1),
            "fiber_g":   round(totals.get("fiber_g", 0), 1),
            "sodium_mg": round(totals.get("sodium_mg", 0), 1),
            "gl":        totals.get("gl_fdc"),
        },
        "compliance": {
            "bp":       comp.get("bp", {}).get("pass", False),
            "diabetes": comp.get("diabetes", {}).get("pass", False),
            "biliary":  comp.get("biliary", {}).get("pass", False),
        },
    }


# ── Match mode ────────────────────────────────────────────────────────────────

def compute_match(
    recipe: dict[str, Any],
    query_tokens: set[str],
) -> tuple[float, list[str], list[str]]:
    """
    Algebraic match score.

    score  = |matched_ingredients| / |all_ingredients| × 100
    matched   = raw_ingredients where token intersection is non-empty
    missing   = raw_ingredients where token intersection is empty
    """
    raw = recipe.get("raw_ingredients", [])
    if not raw:
        return 0.0, [], []

    matched: list[str] = []
    missing: list[str] = []

    for ingredient in raw:
        ing_tokens = tokenize(ingredient)
        if fuzzy_match(query_tokens, ing_tokens):
            matched.append(ingredient)
        else:
            missing.append(ingredient)

    score = round(len(matched) / len(raw) * 100, 1)
    return score, matched, missing


def recipe_to_match_output(recipe: dict[str, Any]) -> dict[str, Any]:
    totals = recipe.get("totals_per_serving", {})
    return {
        "name":       recipe.get("name", ""),
        "category":   recipe.get("category", "unknown"),
        "per_serving": {
            "kcal":      round(totals.get("energy_kcal", 0), 1),
            "protein_g": round(totals.get("protein_g", 0), 1),
            "carbs_g":   round(totals.get("carbohydrate_g", 0), 1),
            "fat_g":     round(totals.get("total_fat_g", 0), 1),
            "sodium_mg": round(totals.get("sodium_mg", 0), 1),
        },
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="dash-recipe-browser")
    sub = parser.add_subparsers(dest="mode", required=True)

    # ── Filter subcommand ──
    f = sub.add_parser("filter", help="Filter recipes by structural constraints")
    f.add_argument("--category", choices=["breakfast","lunch","dinner","snack","dessert","high-protein"])
    f.add_argument("--tags", type=lambda s: s.split(","))
    f.add_argument("--servings", type=int)
    f.add_argument("--compliance", type=lambda s: s.split(","))
    f.add_argument("--max-kcal", type=float)
    f.add_argument("--max-sodium-mg", type=float)
    f.add_argument("--max-gl", type=float)
    f.add_argument("--min-protein-g", type=float)
    f.add_argument("--max-protein-g", type=float)
    f.add_argument("--min-fiber-g", type=float)
    f.add_argument("--limit", type=int, default=50)
    f.add_argument("--json", action="store_true", help="Output raw JSON")

    # ── Match subcommand ──
    m = sub.add_parser("match", help="Rank recipes by ingredient overlap")
    m.add_argument("--have", required=True, help="Comma-separated available ingredients")
    m.add_argument("--threshold", type=float, default=0.0, help="Minimum match score %% (0–100)")
    m.add_argument("--limit", type=int, default=10)
    m.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    ensure_repo()

    index = load_index()
    results: list[dict[str, Any]] = []

    for entry in index:
        file_name = entry.get("file", "")
        if not file_name or file_name.endswith("/index.json") or file_name.endswith("/schema.json"):
            continue

        recipe_path = REPO_DIR / "recipes" / file_name
        if not recipe_path.exists():
            continue

        recipe = load_recipe(recipe_path)

        if args.mode == "filter":
            if apply_filter(recipe, args):
                results.append(recipe_to_filter_output(recipe))

        elif args.mode == "match":
            query_tokens = tokenize(args.have)
            score, matched, missing = compute_match(recipe, query_tokens)
            if score >= args.threshold:
                out = recipe_to_match_output(recipe)
                out["match_score"]           = score
                out["matched_ingredients"]  = matched
                out["missing_ingredients"]  = missing
                results.append(out)

    # Sort
    if args.mode == "filter":
        results.sort(key=lambda r: r["name"])
    elif args.mode == "match":
        results.sort(key=lambda r: r["match_score"], reverse=True)

    # Limit
    limit = args.limit
    results = results[:limit]

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"  dash-recipe-browser  |  {len(results)} result(s)  |  mode={args.mode}")
        print(f"{'='*60}")

        for r in results:
            if args.mode == "filter":
                print(f"\n  [{r['category']}] {r['name']}")
                print(f"  kcal {r['per_serving']['kcal']}  "
                      f"P {r['per_serving']['protein_g']}g  "
                      f"C {r['per_serving']['carbs_g']}g  "
                      f"F {r['per_serving']['fat_g']}g  "
                      f"Na {r['per_serving']['sodium_mg']}mg  "
                      f"GL {r['per_serving']['gl']}")
                print(f"  compliance  BP {r['compliance']['bp']}  "
                      f"DM {r['compliance']['diabetes']}  "
                      f"BILIARY {r['compliance']['biliary']}")
                if r["source_url"]:
                    print(f"  source: {r['source_url']}")
                if r["tags"]:
                    print(f"  tags: {', '.join(r['tags'])}")

            elif args.mode == "match":
                print(f"\n  [{r['category']}] {r['name']}  "
                      f"★ {r['match_score']}%")
                print(f"  kcal {r['per_serving']['kcal']}  "
                      f"P {r['per_serving']['protein_g']}g  "
                      f"Na {r['per_serving']['sodium_mg']}mg")
                print(f"  ✓ have: {', '.join(r['matched_ingredients']) or '—'}")
                print(f"  ✗ need: {', '.join(r['missing_ingredients']) or '—'}")

        print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
