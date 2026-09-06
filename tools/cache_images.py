#!/usr/bin/env python3
"""
Cache each recipe's photo into the repo as a small thumbnail.

    python tools/cache_images.py            # fetch anything missing
    python tools/cache_images.py --force    # re-fetch everything

WHY CACHE INSTEAD OF HOTLINKING

The first attempt put the publisher's image URL straight into the email. It did not
render: the images were reachable (Gmail's own proxy fetches them fine — that was
checked), but the <img> tags did not survive into the inbox. Rather than keep guessing at
which sanitizer or image-blocking setting ate them, the photo now travels WITH the email
as an inline CID attachment. Nothing to fetch, nothing to allow, nothing to block.

Caching also removes a network call from the send path, which keeps the promise that
nothing is generated or fetched at send time.

Thumbnails are 220px wide and re-encoded as JPEG, so four of them add ~40KB to an email
and the repo stays small.
"""
import argparse
import os
import subprocess
import sys
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mealbit import library as L  # noqa: E402

from PIL import Image  # noqa: E402

# The email displays these at 104px wide; 220 covers a 2x display and nothing more.
# Oversizing them just makes every message heavier for no visible gain.
WIDTH = 220
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'


def fetch(url):
    out = subprocess.run(
        ["curl", "-sSL", "--max-time", "30", "-A", UA, url],
        capture_output=True, timeout=40)
    return out.stdout or None


def thumbnail(raw, path):
    im = Image.open(BytesIO(raw))
    im = im.convert("RGB")
    w, h = im.size
    # Crop to 4:3 around the centre before scaling — recipe photos are usually square or
    # portrait, and a letterboxed thumbnail next to a title looks like a mistake.
    target = 4 / 3
    if w / h > target:
        new_w = int(h * target)
        im = im.crop(((w - new_w) // 2, 0, (w + new_w) // 2, h))
    else:
        new_h = int(w / target)
        im = im.crop((0, max(0, (h - new_h) // 2), w, max(0, (h - new_h) // 2) + new_h))
    im = im.resize((WIDTH, int(WIDTH / target)), Image.LANCZOS)
    im.save(path, "JPEG", quality=78, optimize=True)
    return os.path.getsize(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    got = skipped = failed = 0
    for r in L.load_dinners() + L.load_lunches():
        # A verified recipe's own photo first; otherwise the representative one that
        # tools/find_photos.py found, so every card gets a picture.
        url = r.get("image_url") or r.get("photo_url")
        if not url:
            continue
        path = os.path.join(L.DATA, "images", r["slug"] + ".jpg")
        if os.path.exists(path) and not a.force:
            skipped += 1
            continue
        raw = fetch(url)
        if not raw or len(raw) < 2000:
            print(f"FAIL  {r['slug']}")
            failed += 1
            continue
        try:
            size = thumbnail(raw, path)
        except Exception as e:                                   # noqa: BLE001
            print(f"FAIL  {r['slug']}: {e}")
            failed += 1
            continue
        print(f"OK    {r['slug']:44} {size // 1024} KB")
        got += 1
    print(f"\ncached {got}, already had {skipped}, failed {failed}")


if __name__ == "__main__":
    main()
