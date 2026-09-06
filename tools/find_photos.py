#!/usr/bin/env python3
"""
A photo for every card, for the dishes no published recipe matched.

    python tools/find_photos.py           # fill in anything without a picture
    python tools/find_photos.py --recheck # re-verify the ones already on file

`tools/find_sources.py` looks for a REAL PUBLISHED VERSION of each dish — the recipe
behind the card's QR code — and it is deliberately strict, because a QR that opens the
wrong dinner wastes a scan mid-cook and discredits every other code on the sheet. It
tops out around half the library: a chanterelle-and-farro skillet or a chili-crisp
cottage cheese bowl simply has no close published equivalent.

The brief: "every meal card should have a photo of what the dish should look like." So this
is a SECOND, separate tier, and the separation is the point:

    source_url / image_url    a verified published recipe. QR points at it.
    photo_url                 a representative photo of the dish. NOT a recipe, never
                              behind the QR, and credited on the card as someone else's
                              picture of the same food.

Openverse indexes openly-licensed images. Two disciplines carry over from find_sources:
the result's own TITLE must carry the dish's identity — two of the recipe's identifying
words, the same rule — so "IMG_1513" can never stand in for a chanterelle skillet; and
the image is fetched and checked before anything is written.

Licences are filtered to those that permit adaptation, because the photo gets resized and
cropped into a 220px thumbnail. Anything -nd is skipped on those grounds alone.
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

API = "https://api.openverse.org/v1/images/"
# upload.wikimedia.org rate-limits this environment's shared egress IP with a 429, whatever
# the user agent, so a Commons result can pass every check here and then fail to cache.
# Openverse indexes plenty of Flickr, which does not.
AVOID_HOSTS = ("upload.wikimedia.org",)
# Licences that allow the crop and resize into a thumbnail. Everything -nd is excluded:
# a derivative is exactly what a 220px centre-cropped copy is.
LICENSES = "cc0,pdm,by,by-sa,by-nc,by-nc-sa"
UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/124 Safari/537.36')


def sh(cmd, timeout=30):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=timeout).stdout
    except Exception:
        return ""


def status(url):
    return sh(f'curl -sSL -o /dev/null -w "%{{http_code}}" --max-time 20 '
              f'-A "{UA}" "{url}"').strip()[-3:]


def query(terms, n=8):
    # Openverse caps page_size at 20 for anonymous requests and returns an ERROR BODY
    # rather than a truncated page when you ask for more — which parses as zero results
    # and looks exactly like "this dish has no photos".
    n = min(n, 20)
    q = urllib.parse.quote(" ".join(terms))
    raw = sh(f'curl -sS --max-time 25 -A "{UA}" '
             f'"{API}?q={q}&page_size={n}&license={LICENSES}"', timeout=30)
    try:
        return json.loads(raw).get("results", [])
    except Exception:
        return []


def title_hits(result, terms):
    """How many of the recipe's identifying words the photo's own title carries."""
    words = [w for w in re.split(r"[^a-z]+", L.normalize(result.get("title") or "")) if w]
    n = 0
    for t in terms:
        t = t.rstrip("s")
        if any(w.rstrip("s") == t for w in words):
            n += 1
    return n


def rank(results, terms):
    """
    Best candidate first: most of the dish's words in the title, then the largest image.

    Taking the first hit that cleared the bar gave a chorizo-and-corn skillet a tight
    close-up of a sausage. More title words is more likely to be the actual dish, and a
    bigger original is more likely to be a composed food photograph than a snapshot.
    """
    return sorted(results,
                  key=lambda r: (-title_hits(r, terms), -(r.get("width") or 0)))


def titled_right(result, terms):
    """
    The photo's own title has to name the dish.

    Same two-word bar find_sources uses on a URL slug, for the same reason: one word is
    not identity. Openverse is full of pictures called "IMG_1513" and "DSC00042", and a
    photo with no title says nothing about what is in it.
    """
    return title_hits(result, terms) >= 2


def credit(r):
    """Attribution string for the card. CC requires it and it is also just correct."""
    who = (r.get("creator") or "").strip() or "unknown"
    lic = (r.get("license") or "").upper()
    ver = r.get("license_version") or ""
    return f"{who} / CC {lic} {ver}".strip()


def write_back(path, found):
    txt = open(path, encoding="utf-8").read()
    for key in ("photo_url", "photo_credit", "photo_source"):
        txt = re.sub(rf"^{key}:.*\n", "", txt, flags=re.M)
    block = "".join(f"{k}: {v}\n" for k, v in found.items())
    txt = re.sub(r"^(rating:)", block + r"\1", txt, count=1, flags=re.M)
    open(path, "w", encoding="utf-8").write(txt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recheck", action="store_true")
    ap.add_argument("--only", help="substring match on slug")
    a = ap.parse_args()

    ok = miss = skip = 0
    for r in L.load_dinners() + L.load_lunches():
        if a.only and a.only not in r["slug"]:
            continue
        # A verified recipe photo always wins; this tier only fills the gaps.
        # A pinned photo was chosen by someone looking at it; a search must never
        # silently replace it with something that merely scores well on title text.
        if (r.get("image_url") or r.get("photo_pinned")
                or (r.get("photo_url") and not a.recheck)):
            skip += 1
            continue
        terms = FS.keywords(r["title"])
        found = None
        # Progressively shorter queries, ending at the single most-identifying word.
        #
        # A photo library is not a recipe index: "larb charred beans pork" matches
        # nothing, while plain "larb" returns seventy pictures of larb. Precision does not
        # come from the query here — it comes from `titled_right`, which still demands two
        # of the recipe's words in the photo's own title. So the query can be as broad as
        # it needs to be to return anything at all.
        # Prefixes, then each leading word alone, then that word paired with each of the
        # others. The rarity ordering that makes find_sources work against URL slugs is
        # actively unhelpful here: "tadka" and "giardiniera" are the most identifying
        # words in their titles and almost nothing in a photo library is tagged with
        # them, while "dal" and "sub" return hundreds. Trying every combination costs a
        # few seconds and only runs for recipes that have no picture at all.
        attempts, seen_q = [], set()
        for cand in ([terms[:4], terms[:3], terms[:2]]
                     + [[t] for t in terms[:4]]
                     + [[terms[0], t] for t in terms[1:4]]
                     + [[a, b] for a in terms[1:3] for b in terms[2:5] if a != b]):
            key = " ".join(cand)
            if cand and key not in seen_q:
                seen_q.add(key)
                attempts.append(cand)
        for q_terms in attempts:
            if found or len(terms) < 2 or not q_terms:
                break
            for res in rank(query(q_terms, n=20), terms):
                if not titled_right(res, terms):
                    continue
                url = res.get("url") or ""
                if (not url.startswith("https://")
                        or any(h in url for h in AVOID_HOSTS)
                        or status(url) != "200"):
                    continue
                found = {"photo_url": url,
                         "photo_credit": credit(res),
                         "photo_source": res.get("foreign_landing_url") or res.get("source")}
                break
        if found:
            write_back(r["path"], found)
            print(f"OK    {r['slug']:44} {found['photo_credit']}")
            ok += 1
        else:
            print(f"MISS  {r['slug']:44} (no titled, licensed photo)")
            miss += 1
    print(f"\nphotos found {ok}, still none {miss}, already had one {skip}")


if __name__ == "__main__":
    main()
