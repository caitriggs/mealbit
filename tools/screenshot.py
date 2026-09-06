#!/usr/bin/env python3
"""
Render the newsletter at phone width in both themes, so a design change can be looked at
before it reaches an inbox.

    python -m mealbit.meal_plan && python tools/screenshot.py

Writes out/mealbit-412-{light,dark}.png. 412px is the Pixel/Android viewport and the
narrowest thing worth designing for; if it survives 412 it survives everything.

Chromium is preinstalled in this environment — do NOT run `playwright install`.
"""
import os
import sys
import glob

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CHROME = "/opt/pw-browsers/chromium-*/chrome-linux/chrome"


def chrome_path():
    hit = sorted(glob.glob(os.environ.get("CHROME_PATH", DEFAULT_CHROME)))
    return hit[-1] if hit else None


def main():
    src = os.path.abspath(sys.argv[1] if len(sys.argv) > 1
                          else os.path.join(ROOT, "out", "meal_plan.html"))
    if not os.path.exists(src):
        raise SystemExit(f"{src} not found — run `python -m mealbit.meal_plan` first.")
    exe = chrome_path()
    with sync_playwright() as p:
        for scheme in ("light", "dark"):
            kw = {"args": ["--no-sandbox"]}
            if exe:
                kw["executable_path"] = exe
            browser = p.chromium.launch(**kw)
            page = browser.new_page(viewport={"width": 412, "height": 900},
                                    color_scheme=scheme, device_scale_factor=2)
            page.goto("file://" + src)
            page.wait_for_timeout(400)
            out = os.path.join(ROOT, "out", f"mealbit-412-{scheme}.png")
            page.screenshot(path=out, full_page=True)
            print(f"wrote {out}")
            browser.close()


if __name__ == "__main__":
    main()
