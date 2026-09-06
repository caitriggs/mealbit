#!/usr/bin/env python3
"""
Mealbit — weekly meal plan + Coffee Ritual newsletter.

    python -m mealbit.meal_plan                       # render to out/meal_plan.html
    python -m mealbit.meal_plan --send --test         # smoke test to send.test_to only
    python -m mealbit.meal_plan --send                # the real send
    python -m mealbit.meal_plan --today 2026-01-10    # render any week (no history write)
    python -m mealbit.meal_plan --box 3               # 3 dinners already in the house

History is only recorded on a real send, so rendering previews and running tests can
never poison the rotation.
"""
import argparse
import os
import sys
from datetime import date

if __package__ in (None, ""):                       # allow `python mealbit/meal_plan.py`
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "mealbit"

from . import planner as P                          # noqa: E402
from . import render as R                           # noqa: E402
from . import printable as PR                      # noqa: E402
from . import topdf                                # noqa: E402
from .email_kit import send_email, RECIPIENT, TEST_ONLY  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--send", action="store_true", help="email it")
    ap.add_argument("--test", action="store_true",
                    help="with --send, deliver a [TEST] copy to send.test_to only")
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "meal_plan.html"))
    ap.add_argument("--cards", default=os.path.join(ROOT, "out", "cards.pdf"),
                    help="two-sheet printable recipe cards, two per sheet, cut in half")
    ap.add_argument("--list", dest="listfile",
                    default=os.path.join(ROOT, "out", "shopping-list.html"),
                    help="phone shopping list — attached to the email")
    ap.add_argument("--today", default=None, help="override today's date, YYYY-MM-DD")
    ap.add_argument("--seed", type=int, default=None,
                    help="override the rotation seed (testing / forcing a reshuffle)")
    ap.add_argument("--no-record", action="store_true",
                    help="send without writing to history.json")
    ap.add_argument("--box", type=int, default=0, metavar="N",
                    help="N dinners already shopped for (a meal kit, a freezer stash). "
                         "They take the first cooking nights, contribute nothing to the "
                         "shopping list, and get no printed card.")
    ap.add_argument("--box-label", default="meal-kit box",
                    help="what to call those dinners in the email and the ledger")
    ap.add_argument("--box-leftovers", type=int, default=1, metavar="N",
                    help="lunch servings each boxed dinner actually yields (default 1 — "
                         "a two-person meal kit leaves about one)")
    a = ap.parse_args(argv)

    today = date.fromisoformat(a.today) if a.today else date.today()
    box = ({"count": a.box, "label": a.box_label, "leftovers": a.box_leftovers}
           if a.box else None)
    plan = P.build_plan(today, seed=a.seed, box=box)
    # Two renders of the same plan: the file is opened in a browser, so its photos are
    # inlined as data: URIs; the email carries them as attachments and points at cid:.
    html = R.render(plan, embed="data")

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {a.out}")
    cards_html = PR.render_cards(plan)
    # The cards go to a printer, so they ship as a PDF; the browser's own HTML print path
    # would add its headers, footers and margins on top of a layout measured to the inch.
    # If no browser is installed the HTML is attached instead — a worse attachment, but
    # the Saturday send must not depend on Chromium being present.
    cards_pdf = topdf.to_pdf(cards_html)
    cards_path = a.cards if cards_pdf else os.path.splitext(a.cards)[0] + ".html"
    cards_body = cards_pdf if cards_pdf else cards_html

    os.makedirs(os.path.dirname(cards_path), exist_ok=True)
    with open(cards_path, "wb" if cards_pdf else "w",
              **({} if cards_pdf else {"encoding": "utf-8"})) as f:
        f.write(cards_body)
    print(f"wrote {cards_path}" + (f" ({topdf.page_count(cards_pdf)} pages)" if cards_pdf else ""))

    os.makedirs(os.path.dirname(a.listfile), exist_ok=True)
    with open(a.listfile, "w", encoding="utf-8") as f:
        f.write(PR.render_list(plan))
    print(f"wrote {a.listfile}")
    print(f"week of {plan['week_start']} · {plan['season']}")
    for night, d in zip(plan["cook_nights"], plan["dinners"]):
        print(f"  {night}: {d['title']}")
    print(f"  lunches: {', '.join(r['title'] for r in plan['lunches'])}")
    for c in plan["coffee"]:
        bits = []
        if c["syrup"]:
            bits.append(c["syrup"]["title"] + (" (make it)" if c["syrup_needed"][0] else ""))
        else:
            bits.append("makes its own")
        if c["crumble"]:
            bits.append(c["crumble"]["title"])
        print(f"  coffee:  {c['drink']['title']} — {' + '.join(bits)}")
    print(f"  quote:   {plan['quote']['who']}")
    for n in plan["notes"]:
        print(f"  note: {n}")

    if a.send:
        subject = (f"Mealbit — week of {plan['week_start'].strftime('%b %-d')}: "
                   f"{plan['dinners'][0]['title']}, and {len(plan['dinners']) - 1} more")
        week = plan["week_start"].isoformat()
        send_email(R.render(plan, embed="cid"), subject,
                   to_addr=(TEST_ONLY if a.test else RECIPIENT),
                   attachments=[
                       (f"mealbit-shopping-{week}.html", PR.render_list(plan)),
                       (f"mealbit-cards-{week}"
                        f"{'.pdf' if cards_pdf else '.html'}", cards_body),
                   ],
                   images=plan["images"])
        # Only a real send advances the rotation. A [TEST] would otherwise burn the
        # week's recipes and the family would get a different plan than the one reviewed.
        if not a.test and not a.no_record:
            P.record(plan)
            print("recorded to data/history.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
