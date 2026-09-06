#!/usr/bin/env python3
"""
Record what the household thought of a dish, on the recipe itself.

    python tools/verdict.py chicken-katsu-curry --rating 5 --note "Max wants this monthly"
    python tools/verdict.py bbq-pulled-pork-cheesy-grits --rating 2 --note "grits were gluey"
    python tools/verdict.py some-lunch --note "needs more lemon"          # note only
    python tools/verdict.py --reset-all       # a fresh fork: the last household's opinions are not yours

`rating:` is 1-5 and is what the planner reads: a dish at or below 2 is RETIRED — never
planned again until someone re-rates it 3 or higher. `feedback:` keeps every verdict with
its date and the words that were used, for whatever gets built on it later. First names
are fine in a note; nothing else personal is.
"""
import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mealbit import library as L      # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--rating", type=int, help="1-5; 1-2 retires the dish")
    ap.add_argument("--note", help="what they said, in their words")
    ap.add_argument("--who", help="first name of who said it (optional)")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD, default today")
    ap.add_argument("--reset-all", action="store_true",
                    help="clear rating and feedback on every recipe (a new household)")
    a = ap.parse_args(argv)

    recipes = {r["slug"]: r for r in L.load_dinners() + L.load_lunches()}
    if a.reset_all:
        n = 0
        for r in recipes.values():
            if r.get("rating") is not None or r.get("feedback"):
                L.set_frontmatter_key(r["path"], "rating", ["rating: null"])
                L.set_frontmatter_key(r["path"], "feedback", [])
                n += 1
        print(f"reset {n} recipe(s) to no verdict")
        return 0
    if not a.slug:
        ap.error("which recipe? give a slug (tools/this_week.py lists them)")
    if a.slug not in recipes:
        raise SystemExit(f"no recipe with slug {a.slug!r} (tools/this_week.py lists them)")
    on = date.fromisoformat(a.date) if a.date else None
    r = L.record_verdict(recipes[a.slug]["path"], a.rating, a.note, a.who, on)
    state = f"rating {r.get('rating')}" if r.get("rating") is not None else "no rating"
    print(f"{a.slug}: {state}, {len(r.get('feedback') or [])} note(s) on file")
    if L.is_retired(r):
        print(f"  retired — it will not be planned again until it is re-rated "
              f"{L.RETIRE_AT_OR_BELOW + 1} or higher")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
