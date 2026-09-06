#!/usr/bin/env python3
"""
HTML -> PDF for the printable recipe cards.

The cards go to a printer, so they ship as a PDF rather than as HTML. Printing HTML from
a browser adds the browser's own page headers, footers and margins on top of the layout —
which is exactly what makes a "two sheet" document come out as three, with a URL across
the bottom of each one. A PDF prints what it says.

Chromium is the renderer because the layout is CSS and rewriting it against a drawing API
would mean maintaining the design twice. But the Saturday send must not depend on a
browser being installed: if Chromium is missing or fails, `to_pdf` returns None and the
caller attaches the print-ready HTML instead. A slightly worse attachment beats no dinner
plan.
"""
import contextlib
import glob
import os

# Where Playwright's browsers live in this environment and on the GitHub runner. Set
# CHROME_PATH to override.
BROWSER_GLOB = "/opt/pw-browsers/chromium*/chrome-linux/chrome"


def _executable():
    hit = sorted(glob.glob(os.environ.get("CHROME_PATH", BROWSER_GLOB)))
    return hit[-1] if hit else None


@contextlib.contextmanager
def page(viewport=None):
    """
    A Chromium page, or None if there isn't one to be had.

    The single place that knows how to get a browser. Everything that needs one goes
    through here — rendering the PDF, and the test that measures whether the cards
    actually fit their sheet — so that "no browser installed" degrades identically in
    both. A test that raised where the send path shrugs would fail CI over an optional
    tool and block the newsletter, which is exactly backwards; that happened once.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        yield None
        return

    try:
        with sync_playwright() as p:
            kw = {"args": ["--no-sandbox"]}
            exe = _executable()
            if exe:
                kw["executable_path"] = exe
            browser = p.chromium.launch(**kw)
            try:
                yield browser.new_page(**({"viewport": viewport} if viewport else {}))
            finally:
                browser.close()
    except Exception as exc:                    # a missing browser, a crashed renderer
        print(f"No browser available ({exc.__class__.__name__}: "
              f"{str(exc).splitlines()[0]})")
        yield None


def to_pdf(html):
    """
    Render `html` to PDF bytes, or None if no browser is available.

    The page size comes from the document's own `@page` rule (prefer_css_page_size), so
    the sheet geometry lives in one place — the stylesheet — and this function does not
    need to know that the cards happen to be landscape.
    """
    with page() as pg:
        if pg is None:
            print("falling back to the HTML cards.")
            return None
        pg.set_content(html, wait_until="load")
        return pg.pdf(prefer_css_page_size=True, print_background=True,
                      margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})


def page_count(pdf_bytes):
    """
    How many pages a PDF has, without a parser dependency.

    Counts `/Type /Page` objects, excluding `/Pages` (the tree node). Enough to assert
    "this is two sheets", which is the only thing the tests need to know.
    """
    import re
    return len(re.findall(rb"/Type\s*/Page(?![s/\w])", pdf_bytes))
