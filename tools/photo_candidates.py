#!/usr/bin/env python3
"""
Contact sheet of candidate photos, for choosing one by eye.

    python tools/photo_candidates.py slug-a slug-b ...   -> out/cand-<slug>.png

Openverse is searched by title text, and a title is a weak signal for a photograph: the
first pass picked a bag of wild rice for a wild-rice bowl, a packet of dry slaw for a slaw
wrap, and a bento box for a chicken salad. Every one of them had the right words in the
title. Nothing short of looking at the picture separates those from a photo of the dish.

So this renders the candidates as a numbered grid. The choice is made by a person (or by
Claude, which can see them) and pinned with tools/pin_photo.py, which is the only way a
photo gets onto a card that this file's search could not have justified on its own.
"""
import io
import os
import subprocess
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mealbit import library as L  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import importlib.util  # noqa: E402
_s = importlib.util.spec_from_file_location(
    "find_photos", os.path.join(os.path.dirname(os.path.abspath(__file__)), "find_photos.py"))
FP = importlib.util.module_from_spec(_s)
_s.loader.exec_module(FP)

COLS, W, H, LAB = 6, 260, 200, 26


def thumb(url):
    try:
        raw = subprocess.run(f'curl -sSL --max-time 20 -A "{FP.UA}" "{url}"',
                             shell=True, capture_output=True, timeout=25).stdout
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        im.thumbnail((W - 6, H - 6))
        return im
    except Exception:
        return None


def sheet_for(recipe, per=6, override=None):
    """
    `override` is a plain search phrase, for when the title's rarest words are the ones a
    photo library has never heard of. "fresnos" and "crunchy" lead two of these titles and
    return nothing edible; "pulled pork grits" returns the dish.
    """
    terms = FP.FS.keywords(recipe["title"])
    if override:
        seen, cands = set(), []
        for r in FP.rank(FP.query(override.split(), n=24), terms):
            u = r.get("url") or ""
            if u and u not in seen:
                seen.add(u)
                cands.append(r)
        return cands[:per]
    seen, cands = set(), []
    for q in ([terms[:3], terms[:2], terms[:1]]
              + [[terms[0], t] for t in terms[1:4]] + [[t] for t in terms[1:3]]):
        if len(cands) >= per or not q:
            continue
        for r in FP.rank(FP.query(q, n=20), terms):
            if len(cands) >= per:
                break
            u = r.get("url") or ""
            if u in seen or not FP.titled_right(r, terms):
                continue
            seen.add(u)
            cands.append(r)
    return cands


def main():
    # slug or slug=query phrase
    pairs = [a.split("=", 1) if "=" in a else [a, None] for a in sys.argv[1:]]
    by_slug = {r["slug"]: r for r in L.load_dinners() + L.load_lunches()}
    rows = [(s, sheet_for(by_slug[s], override=q)) for s, q in pairs if s in by_slug]
    sheet = Image.new("RGB", (COLS * W, len(rows) * (H + LAB)), "white")
    d = ImageDraw.Draw(sheet)
    for ri, (slug, cands) in enumerate(rows):
        y = ri * (H + LAB)
        d.rectangle([0, y, COLS * W, y + LAB], fill="#222")
        d.text((6, y + 3), f"{slug}   —   {by_slug[slug]['title'][:70]}", fill="white")
        for ci, c in enumerate(cands[:COLS]):
            x = ci * W
            im = thumb(c.get("url") or "")
            if im:
                sheet.paste(im, (x + 3, y + LAB + 3))
            d.text((x + 4, y + LAB + 4), f"{ci+1}", fill="yellow")
        print(f"{slug}")
        for ci, c in enumerate(cands[:COLS], 1):
            print(f"   {ci}. {(c.get('title') or '')[:46]:48} {FP.credit(c)}")
            print(f"      {c.get('url')}")
    out = f"out/cand-{rows[0][0][:18]}.png" if rows else "out/cand.png"
    sheet.save(out)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
