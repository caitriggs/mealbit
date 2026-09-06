#!/usr/bin/env python3
"""
Professional stock photography for the cards Openverse cannot serve.

    export PEXELS_API_KEY=...   # or PEXEL_API_KEY; free at pexels.com/api
    python tools/stock_photos.py                    # fill anything without a good photo
    python tools/stock_photos.py --only tuna        # one recipe
    python tools/stock_photos.py --sheet turkey-provolone-giardiniera-sub
                                                    # contact sheet, then pin_photo.py

WHY A THIRD TIER. The household, on the printed lunch cards: "the lunch photos need to be higher
quality and actually the meal they represent not bad quality photo photos taken by home
chefs." She is describing the Openverse tier exactly. Reviewed by eye, 13 of the library's
Openverse photos were poor, wrong, or both, against 4 of 20 in the verified-recipe tier —
and the four bad ones there were wrong VARIANTS of the right dish, not bad photographs.

The cause is what each source is FOR. Openverse indexes openly-licensed images of
anything: a bag of wild rice, a leek on a table, someone's dinner under a kitchen bulb.
Pexels is a stock library curated for commercial use, so its food photography is lit,
styled and shot on purpose. That does not make it accurate — a search for "turkey sub"
returns beautiful photographs of sandwiches that are not our sandwich — so the tier's
rules are unchanged and non-negotiable:

    * the photo is NEVER the recipe behind the QR. That stays `image_url`, from
      find_sources.py, or the QR falls back to an image search.
    * a person looks at it. `photo_pinned` is required by test_every_recipe_has_a_photo,
      and --sheet exists so looking is one command.

The one thing that gets simpler: Pexels is licensed for use and modification without
attribution, so the credit line is a courtesy rather than a licence term, and there is no
-nd trap to filter for.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mealbit import library as L  # noqa: E402

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "find_sources", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "find_sources.py"))
FS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FS)

API = "https://api.pexels.com/v1/search"
UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/124 Safari/537.36')
# Pexels serves several renditions; "large" is ~1880px on the long edge, which is far
# more than the 320px thumbnail needs and leaves room for the card's centre crop.
RENDITION = "large"


# Both spellings, because the environment this runs in has it as PEXEL_API_KEY and
# Pexels' own docs say PEXELS_API_KEY. Failing on the singular would be a rename chore
# for whoever set it, over a letter.
KEY_VARS = ("PEXELS_API_KEY", "PEXEL_API_KEY")


def key():
    for var in KEY_VARS:
        k = os.environ.get(var, "").strip()
        if k:
            return k
    sys.exit(f"No Pexels key. Set one of {' or '.join(KEY_VARS)} — free at pexels.com/api.")


def sh(cmd, timeout=30):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=timeout).stdout
    except Exception:
        return ""


def search(query, n=15):
    """Pexels photo search. Returns [] on any failure rather than raising."""
    url = (f"{API}?query={urllib.parse.quote(query)}&per_page={n}"
           f"&orientation=landscape")
    raw = sh(f'curl -sS --max-time 25 -H "Authorization: {key()}" '
             f'-H "User-Agent: {UA}" "{url}"')
    try:
        return json.loads(raw).get("photos") or []
    except Exception:
        return []


def query_for(recipe):
    """
    What to actually search for.

    NOT the rarity ordering `keywords()` produces, which is right for matching a recipe
    URL and exactly wrong here. Rarity picks the word that most identifies the dish
    within OUR library — "pulled cheesy" for the BBQ pork grits, "wild mustard" for the
    squash bowl, "bean oil melt" for the white bean toast. A stock library is indexed on
    the common words, and those queries return nothing usable.

    So: the title's own leading words, in the order written, stopping at "with" — English
    food titles lead with the dish's identity and trail off into garnish. "BBQ pulled
    pork over cheesy grits" searches as "bbq pulled pork", "Turkey, provolone and
    giardiniera sub" as "turkey provolone sub". The trailing "food" keeps a bare dish
    name like "larb" inside the food category.
    """
    words = FS.title_words(recipe["title"])
    head, form = [], None
    for w in words:
        if w in ("with", "over", "topped", "served"):
            break
        if w in FS.FORMS:
            form = w          # the literal word, not its synonym class
        elif w not in FS.STOP and len(w) > 2:
            head.append(w)
    return " ".join(head[:3] + ([form] if form else [])) + " food"


def title_hits(photo, terms):
    """How many of the dish's words appear in the photographer's own description."""
    blob = f"{photo.get('alt') or ''} {photo.get('url') or ''}".lower()
    return sum(1 for t in terms if t.rstrip("s") in blob)


def rank(photos, terms):
    """Most of the dish's words in the description first, then the largest original."""
    return sorted(photos, key=lambda p: (-title_hits(p, terms), -(p.get("width") or 0)))


def found_for(photo):
    return {
        "photo_url": photo["src"][RENDITION],
        "photo_credit": f'{photo.get("photographer") or "Pexels"} / Pexels',
        "photo_source": photo.get("url") or "https://www.pexels.com/",
    }


def write_back(path, found):
    txt = open(path, encoding="utf-8").read()
    for k in ("photo_url", "photo_credit", "photo_source"):
        txt = re.sub(rf"^{k}:.*\n", "", txt, flags=re.M)
    block = "".join(f"{k}: {v}\n" for k, v in found.items())
    txt = re.sub(r"^(rating:)", block + r"\1", txt, count=1, flags=re.M)
    open(path, "w", encoding="utf-8").write(txt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="substring match on slug")
    ap.add_argument("--sheet", help="render a numbered contact sheet for one slug")
    ap.add_argument("--query", help="override the search text (use with --sheet/--only)")
    ap.add_argument("--replace-openverse", action="store_true",
                    help="also re-do photos currently borrowed from Openverse")
    a = ap.parse_args()

    pool = L.load_dinners() + L.load_lunches()
    if a.sheet:
        r = next((x for x in pool if x["slug"] == a.sheet), None)
        if not r:
            sys.exit(f"no recipe with slug {a.sheet!r}")
        q = a.query or query_for(r)
        photos = rank(search(q, 12), FS.keywords(r["title"]))
        print(f"{r['title']}\n  query: {q}\n  {len(photos)} candidates")
        for i, p in enumerate(photos, 1):
            print(f"  {i:2}. {p.get('alt') or '(no description)'}\n"
                  f"      {p['src'][RENDITION]}")
        return 0

    ok = miss = skip = 0
    for r in pool:
        if a.only and a.only not in r["slug"]:
            continue
        # A verified recipe photo always wins — it is the dish as its own author shot it.
        if r.get("image_url"):
            skip += 1
            continue
        # A pinned photo was chosen by a person. Only --replace-openverse overrides that,
        # and only for the tier being replaced.
        if r.get("photo_url") and not a.replace_openverse:
            skip += 1
            continue
        q = a.query or query_for(r)
        photos = rank(search(q), FS.keywords(r["title"]))
        if not photos:
            print(f"MISS  {r['slug']:44} (nothing for {q!r})")
            miss += 1
            continue
        write_back(r["path"], found_for(photos[0]))
        print(f"OK    {r['slug']:44} {photos[0].get('alt') or ''}"[:110])
        ok += 1
    print(f"\n{ok} written, {miss} missed, {skip} left alone.")
    print("NOTHING IS PINNED YET. Every one of these is an unreviewed search result, "
          "and test_every_recipe_has_a_photo will fail until a person has looked:\n"
          "  python tools/stock_photos.py --sheet <slug>\n"
          "  python tools/pin_photo.py <slug>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
