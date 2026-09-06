#!/usr/bin/env python3
"""
Pin a photo that a person chose by looking at it.

    python tools/pin_photo.py <slug> <image-url> "<credit>" "<source-page>"

tools/find_photos.py picks from an image search on title text alone, and title text is a
weak signal for a photograph — it chose a bag of wild rice for a wild-rice bowl and a
packet of dry slaw for a slaw wrap, both with the right words in the title. Anything
pinned here was looked at, and `--recheck` will not overwrite it.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mealbit import library as L  # noqa: E402


def main():
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    slug, url, credit = sys.argv[1], sys.argv[2], sys.argv[3]
    source = sys.argv[4] if len(sys.argv) > 4 else ""
    hit = next((r for r in L.load_dinners() + L.load_lunches() if r["slug"] == slug), None)
    if not hit:
        raise SystemExit(f"no recipe with slug {slug!r}")
    txt = open(hit["path"], encoding="utf-8").read()
    for key in ("photo_url", "photo_credit", "photo_source", "photo_pinned"):
        txt = re.sub(rf"^{key}:.*\n", "", txt, flags=re.M)
    block = (f"photo_url: {url}\nphoto_credit: {credit}\n"
             f"photo_source: {source}\nphoto_pinned: true\n")
    txt = re.sub(r"^(rating:)", block + r"\1", txt, count=1, flags=re.M)
    open(hit["path"], "w", encoding="utf-8").write(txt)
    print(f"pinned {slug} -> {credit}")


if __name__ == "__main__":
    main()
