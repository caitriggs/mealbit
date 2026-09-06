"""
Measure every card in the library against its half-sheet.

    python tools/card_fit.py            # every dinner, lunch, drink, syrup, crumble
    python tools/card_fit.py slug ...   # just these

Prints one line per card: the slug and how many pixels it overflows (0 is fine, negative
is slack). Exits non-zero if anything overflows. This is the check to run after writing
or editing a recipe: a card is a fixed 8.5in with overflow:hidden, so anything that does
not fit vanishes silently — you would find out at the store.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mealbit import library as L          # noqa: E402
from mealbit import printable as PR       # noqa: E402
from mealbit import topdf                 # noqa: E402


def pool():
    return L.load_dinners() + L.load_lunches() + L.load_drinks() + L.load_syrups() + L.load_crumbles()


def main(argv):
    want = set(argv)
    recipes = [r for r in pool() if not want or r["slug"] in want]
    if want and len(recipes) != len(want):
        missing = want - {r["slug"] for r in recipes}
        print("no such recipe:", ", ".join(sorted(missing)))
        return 2
    bad = 0
    with topdf.page(viewport={"width": 1056, "height": 816}) as pg:
        if pg is None:
            print("no browser — cannot measure")
            return 2
        for i in range(0, len(recipes), 2):
            two = recipes[i:i + 2]
            cards = "".join(PR._card("Mon", r) for r in two)
            if len(two) == 1:
                cards += '<div class="card"></div>'
            html = (f'<!doctype html><html><head><meta charset="utf-8"><style>{PR.PRINT_CSS}</style>'
                    f'</head><body><div class="sheet">{cards}</div></body></html>')
            pg.set_content(html, wait_until="load")
            over = pg.evaluate("""() => [...document.querySelectorAll('.card')]
                .map(c => { const p = c.querySelector('.photo');
                            return [c.scrollHeight - c.clientHeight, p ? p.offsetHeight : -1]; })""")
            for r, (px, photo) in zip(two, over):
                flag = "  OVER" if px > 0 else ""
                # The photo absorbs slack; it bottoms out at 0.8in (77px). Near that,
                # the next added line is the one that clips.
                print(f"{px:+5d}px over  photo {photo:4d}px  {r['slug']}{flag}")
                bad += px > 0
    print(f"\n{bad} of {len(recipes)} cards overflow")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
