#!/usr/bin/env python3
"""
"Not the pulled pork this week." Record a per-week request the planner will honour.

    python tools/this_week.py                          # show what is set, and the slugs
    python tools/this_week.py --skip bbq-pulled-pork-cheesy-grits
    python tools/this_week.py --pin chicken-katsu-curry --skip some-lunch
    python tools/this_week.py --clear
    python tools/this_week.py --skip x --today 2026-09-08   # for a week other than the next

Writes data/this-week.yml for the week the planner will build next (the Monday after
`today`). Skips apply to dinners and lunches; pins are dinners only. The scheduled send
reads the committed file, so COMMIT IT — and the real send clears it once the week is out.

This is a one-week request. A dish the household never wants again is a verdict:
tools/verdict.py <slug> --rating 1.
"""
import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mealbit import library as L      # noqa: E402
from mealbit import planner as P      # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip", action="append", default=[], metavar="SLUG",
                    help="leave this dinner or lunch out this week")
    ap.add_argument("--pin", action="append", default=[], metavar="SLUG",
                    help="put this dinner on the menu this week")
    ap.add_argument("--clear", action="store_true", help="forget every request")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD; the week is the Monday after")
    a = ap.parse_args(argv)

    today = date.fromisoformat(a.today) if a.today else date.today()
    start = P.week_start(today)
    recipes = {r["slug"]: r for r in L.load_dinners() + L.load_lunches()}

    if a.clear:
        L.clear_overrides()
        print("cleared data/this-week.yml")
        return 0

    if not a.skip and not a.pin:
        ov = L.load_overrides()
        if ov["week_of"]:
            print(f"week of {ov['week_of']}:  skip {ov['skip'] or '-'}   pin {ov['pin'] or '-'}")
        else:
            print("nothing set for this week")
        print("\ndinners:")
        for s, r in recipes.items():
            if r.get("kind") == "dinner":
                flag = "  (retired)" if L.is_retired(r) else ""
                print(f"  {s:45s} {r['title']}{flag}")
        print("lunches:")
        for s, r in recipes.items():
            if r.get("kind") == "lunch":
                print(f"  {s:45s} {r['title']}")
        return 0

    for slug in a.skip + a.pin:
        if slug not in recipes:
            near = [s for s in recipes if any(w in s for w in slug.split("-") if len(w) > 3)]
            hint = f" Did you mean: {', '.join(near[:4])}?" if near else ""
            raise SystemExit(f"no recipe with slug {slug!r}.{hint}")
    for slug in a.pin:
        if recipes[slug].get("kind") != "dinner":
            raise SystemExit(f"{slug} is a lunch; only dinners can be pinned")
        if L.is_retired(recipes[slug]):
            raise SystemExit(f"{slug} is rated {recipes[slug]['rating']} and retired; "
                             f"re-rate it with tools/verdict.py first")

    # Same week: merge with what is already there. A different week: start over — the
    # old request was for a week that has passed or was never sent.
    ov = L.load_overrides()
    skip, pin = ([], []) if ov["week_of"] != start else (ov["skip"], ov["pin"])
    skip = [s for s in skip + a.skip if s not in a.pin]
    pin = [s for s in pin + a.pin if s not in a.skip]
    L.save_overrides(start, skip, pin)
    print(f"week of {start}:  skip {skip or '-'}   pin {pin or '-'}")
    print("written to data/this-week.yml — render to see the week, then commit it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
