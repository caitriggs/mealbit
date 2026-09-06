#!/usr/bin/env python3
"""
The household's next few weeks, and whether the library fits them.

    python tools/first_weeks.py             # next 4 weeks from today
    python tools/first_weeks.py --weeks 6 --today 2026-09-06

Written for the end of onboarding. The library was written for one household; a new one
has different exclusions and a different protein order, and the point of Mealbit is that
they never think about this. So this prints, in the words the agent can paste:

  * each week's dinners by day, the lunches, and any compromise the planner made
    (a dish back early, a repeated protein, a reach into another season)
  * a FIT line for the coming season: how many dinners are reachable after their
    exclusions and retirements, and how many use each protein they ranked

If the fit line says SHORT, or a week says THIN, the onboarding skill writes recipes
before the household sees anything. Nothing here is written to disk.
"""
import argparse
import os
import sys
from collections import Counter
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mealbit import library as L      # noqa: E402
from mealbit import planner as P      # noqa: E402

MIN_SEASON_DINNERS = 12     # below this the plan repeats before the season is out
MIN_TOP_PROTEIN = 2         # their first-choice protein wants at least this many dinners
THIN = ("thin", "share a protein", "came back after", "reached into")


def fit(cfg, month):
    season = L.load_seasonal()[month]["season"]
    pool = [r for r in L.load_dinners()
            if season in (r.get("seasons") or []) and not P._excluded(r, cfg)]
    by_protein = Counter(r.get("protein") for r in pool)
    prefs = list(cfg.get("protein_preference") or [])
    short = len(pool) < MIN_SEASON_DINNERS
    top_thin = bool(prefs) and by_protein.get(prefs[0], 0) < MIN_TOP_PROTEIN
    return season, len(pool), by_protein, prefs, short, top_thin


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weeks", type=int, default=4)
    ap.add_argument("--today", default=None)
    a = ap.parse_args(argv)
    today = date.fromisoformat(a.today) if a.today else date.today()
    cfg = L.load_household()

    thin_weeks = 0
    for i in range(a.weeks):
        plan = P.build_plan(today + timedelta(weeks=i))
        start = plan["week_start"]
        print(f"Week of {start.strftime('%A %-d %B')}:")
        for night, d in zip(plan["cook_nights"], plan["dinners"]):
            print(f"  {night[:3]} — {d['title']}")
        if plan["lunches"]:
            print("  Lunches: " + "; ".join(r["title"] for r in plan["lunches"]))
        flags = [n for n in plan["notes"] if any(t in n for t in THIN)]
        if flags:
            thin_weeks += 1
            for n in flags:
                print(f"  THIN — {n}")
        print()

    month = P.week_start(today).month
    season, n, by_protein, prefs, short, top_thin = fit(cfg, month)
    ranked = ", ".join(f"{p}: {by_protein.get(p, 0)}" for p in prefs) or "(no protein ranking)"
    print(f"FIT — {season}: {n} dinners reachable after their exclusions; "
          f"by their ranking — {ranked}")
    verdict = []
    if short:
        verdict.append(f"SHORT: fewer than {MIN_SEASON_DINNERS} dinners for the season")
    if top_thin:
        verdict.append(f"THIN: their first choice ({prefs[0]}) has fewer than {MIN_TOP_PROTEIN} dinners")
    if thin_weeks:
        verdict.append(f"THIN: {thin_weeks} of the next {a.weeks} weeks needed a compromise")
    if verdict:
        print("  -> write recipes before they see a week: " + "; ".join(verdict))
        return 1
    print("  -> fits. Show them the first week.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
