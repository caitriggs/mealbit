#!/usr/bin/env python3
"""
Every card in the library, numbered, for a person to QA.

    python tools/library_review.py            # out/library-review.pdf (+ .html)

The tests hold a recipe's SHAPE — tags, leftover quality, per-plate, a photo someone
looked at. They cannot say whether the dish is any good. That is a person reading every
card and replying with numbers: "1, 4, 7 pass; 12 needs less sugar; cut 20." So each card
carries a running number in its header, and the first sheet is an index of numbers and
titles, so the reply can be a list.

Order: dinners, lunches, coffee drinks, syrups, crumbles — each alphabetical by file
name, so the numbering is stable between reviews as long as nothing is added in between.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mealbit import library as L          # noqa: E402
from mealbit import printable as PR       # noqa: E402
from mealbit import topdf                 # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")


def numbered():
    """[(number, label, recipe)] in review order."""
    groups = [("Dinner", L.load_dinners()), ("Lunch", L.load_lunches()),
              ("Coffee", L.load_drinks()), ("Syrup", L.load_syrups()), ("Crumble", L.load_crumbles())]
    out, n = [], 0
    for kind, recipes in groups:
        for r in sorted(recipes, key=lambda x: x["slug"]):
            n += 1
            label = kind
            if kind == "Lunch":
                label = "Sunday batch" if r.get("lunch_style") == "sunday-prep" else "5-minute build"
            out.append((n, label, r))
    return out


def index_sheet(items):
    cols = 3
    per = -(-len(items) // cols)
    columns = ""
    for c in range(cols):
        rows = "".join(f'<div style="font:9pt Arial;line-height:1.5;">'
                       f'<b style="color:#55760f;">#{n}</b>&nbsp; {PR.E(r["title"])}'
                       f'<span style="color:#8a9178;"> &middot; {PR.E(kind)}</span></div>'
                       for n, kind, r in items[c * per:(c + 1) * per])
        columns += f'<div style="flex:1;padding:0 0.15in;">{rows}</div>'
    kinds = {}
    for _n, kind, _r in items:
        kinds[kind] = kinds.get(kind, 0) + 1
    summary = ", ".join(f"{v} {k.lower()}{'s' if v != 1 else ''}" for k, v in kinds.items())
    return (f'<div class="sheet" style="display:block;padding:0.4in 0.5in;">'
            f'<div style="font:700 16pt Arial;color:#2f3a1f;margin-bottom:4pt;">Library review</div>'
            f'<div style="font:9.5pt Arial;color:#6c7458;margin-bottom:10pt;">{len(items)} cards: {summary}. '
            f'Reply with the numbers that pass, and a note on any that don\'t.</div>'
            f'<div style="display:flex;">{columns}</div></div>')


def render():
    items = numbered()
    sheets = index_sheet(items)
    for i in range(0, len(items), 2):
        two = items[i:i + 2]
        cards = "".join(PR._card(f"#{n} \u00b7 {label}", r) for n, label, r in two)
        if len(two) == 1:
            cards += '<div class="card"></div>'
        sheets += (f'<div class="sheet">{cards}'
                   f'<div class="cut top">&#9986;</div><div class="cut bot">&#9986;</div></div>')
    html = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<title>Mealbit library review</title><style>{PR.PRINT_CSS}</style></head>'
            f'<body>{sheets}</body></html>')
    return items, html


def main():
    items, html = render()
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "library-review.html"), "w", encoding="utf-8") as f:
        f.write(html)
    pdf = topdf.to_pdf(html)
    if pdf:
        with open(os.path.join(OUT, "library-review.pdf"), "wb") as f:
            f.write(pdf)
        print(f"wrote out/library-review.pdf — {len(items)} cards, {topdf.page_count(pdf)} pages")
    else:
        print(f"wrote out/library-review.html — {len(items)} cards (no browser for a PDF)")
    for n, _label, r in items:
        print(f"  #{n:<3} {r['title']}")


if __name__ == "__main__":
    main()
