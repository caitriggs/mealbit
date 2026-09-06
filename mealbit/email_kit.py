#!/usr/bin/env python3
"""
Email chrome, lifted from the production finance pulse (pulse/finance_pulse.py in
a sibling finance newsletter).

That file solves several email-client problems that took real iterations to get right,
and they are reproduced here deliberately rather than reinvented:

* LIGHT-FIRST THEME WITH A SELECTED DARK MODE. The light palette is inlined on every
  element; the dark palette is applied by class inside a prefers-color-scheme block with
  !important. Gmail ignores prefers-color-scheme and auto-adapts a light design, which is
  exactly why light has to be the base. Tokens are the pulse's WCAG-AA-verified set, so
  the two household emails read as one system.

* THE EMAIL-SAFE BAR (`hbar`). Gmail mis-sizes table-layout:fixed tables with %-only
  cells and collapses font-size:0 nested cells. Bars must be full-width with `bgcolor`
  AND `height` ATTRIBUTES, not just CSS. A px-width bar inside a %-width cell gets
  crushed on mobile — that was fixed twice upstream; don't reintroduce it.

* `send_email()`. Gmail SMTP over SSL with MIMEText(..., "utf-8"), which is what makes
  emoji and ✓ survive.

The palette is intentionally shared with the finance pulse. Two emails from the same
household should not look like two products.
"""
import os
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Addresses come from config/household.yml, never from here. A --test send goes to
# TEST_ONLY; the real send goes to RECIPIENT; config validation refuses a file where the
# two are the same, because a test that reaches the whole household is the one mistake
# this must never make. Always self-test before anything reaches RECIPIENT.
from . import config as _C
_send = _C.household()
SENDER = _send["send_from"]
RECIPIENT = _send["send_to"]
TEST_ONLY = _send["send_test_to"]
SUBJECT = _send.get("send_subject") or "Mealbit"

# ---- theme: light-first, with a selected dark mode --------------------------
PAGE = "#eef1e6"    # page plane (soft sage)
CARD = "#ffffff"    # card surface
PANEL = "#f2f5e8"   # raised panels (header, tiles, table headers)
LINE = "#d8dec9"    # borders / dividers
TRACK = "#e7ebda"   # unfilled bar track
INK = "#262b1d"     # primary text
MUTE = "#6c7458"    # muted text
BRAND = "#55760f"   # olive brand (headings)
RULE = "#8fb823"    # accent rule under the header
TEAL = "#0c7d70"    # secondary accent — used here for the Coffee Ritual
SOFT = "#b4c49a"    # light sage fill

GOOD = "#0ca30c"
WARN = "#fab219"
OVER = "#d03b3b"
GOOD_T = "#0a7d0a"
WARN_T = "#8a6300"
OVER_T = "#c0392b"

DARK_CSS = (
    ":root{color-scheme:light dark;}"
    "@media (prefers-color-scheme:dark){"
    "  body,.c-body{background-color:#11150d !important;}"
    "  .c-card{background-color:#1c2118 !important;}"
    "  .c-panel{background-color:#262f1d !important;}"
    "  .c-bd{border-color:#39432a !important;}"
    "  .c-trk{background-color:#3a4429 !important;}"
    "  .c-ink{color:#e7ecd6 !important;}"
    "  .c-mute{color:#9aa77d !important;}"
    "  .c-brand{color:#c6de5a !important;}"
    "  .c-rule{border-bottom-color:#c6de5a !important;}"
    "  .c-teal{color:#5cccb8 !important;}"
    "  .c-teal-bg{background-color:#5cccb8 !important;}"
    "  .c-soft-bg{background-color:#6f7d55 !important;}"
    "  .c-good{color:#5fc24f !important;}"
    "  .c-warn{color:#e8a838 !important;}"
    "  .c-over{color:#ef6a53 !important;}"
    "}"
)


def _head(bg):
    """Doctype + head (color-scheme meta + dark-mode CSS) + opening <body>."""
    return (
        '<!doctype html><html lang="en"><head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        '<meta name="supported-color-schemes" content="light dark">'
        f'<style>{DARK_CSS}</style></head>'
        f'<body class="c-body" style="margin:0;padding:0;background-color:{bg};">'
    )


def hbar(frac, color, h=12, fill_class=""):
    """
    Email-safe horizontal bar.

    Full-width table, percentage cells, bgcolor AND height as ATTRIBUTES (not only CSS).
    Do not convert the fill to a px width — it gets crushed inside a %-width cell on
    mobile Gmail.
    """
    pct = max(0, min(100, round(frac * 100)))
    rem = 100 - pct
    fc = f' class="{fill_class}"' if fill_class else ""
    fill = (f'<td{fc} width="{pct}%" height="{h}" bgcolor="{color}" '
            f'style="height:{h}px;line-height:{h}px;font-size:1px;'
            f'background-color:{color};">&nbsp;</td>') if pct > 0 else ""
    track = (f'<td class="c-trk" width="{rem}%" height="{h}" bgcolor="{TRACK}" '
             f'style="height:{h}px;line-height:{h}px;font-size:1px;'
             f'background-color:{TRACK};">&nbsp;</td>') if rem > 0 else ""
    return (f'<table role="presentation" class="c-trk" cellpadding="0" cellspacing="0" '
            f'width="100%" bgcolor="{TRACK}" style="width:100%;min-width:100%;'
            f'border-collapse:collapse;background-color:{TRACK};">'
            f'<tr>{fill}{track}</tr></table>')


def section(title, sub="", accent=None):
    """A section heading with an optional explanatory line under it."""
    accent = accent or BRAND
    cls = "c-teal" if accent == TEAL else "c-brand"
    sub_html = (f'<div class="c-mute" style="font:400 11px Arial;color:{MUTE};'
                f'padding-top:4px;line-height:1.55;">{sub}</div>') if sub else ""
    return (f'<tr><td style="padding:20px 20px 2px;">'
            f'<div class="{cls}" style="font:700 15px Arial;color:{accent};">{title}</div>'
            f'{sub_html}</td></tr>')


def card_open(title, subtitle):
    return (
        _head(PAGE) +
        f'<table role="presentation" class="c-body" width="100%" cellpadding="0" '
        f'cellspacing="0" bgcolor="{PAGE}" style="background-color:{PAGE};padding:18px 0;">'
        '<tr><td align="center">'
        f'<table role="presentation" class="c-card c-bd" width="640" cellpadding="0" '
        f'cellspacing="0" bgcolor="{CARD}" style="width:640px;max-width:640px;'
        f'background-color:{CARD};border-radius:10px;overflow:hidden;'
        f'font-family:Arial,sans-serif;border:1px solid {LINE};">'
        f'<tr><td class="c-panel c-rule" bgcolor="{PANEL}" style="background-color:{PANEL};'
        f'padding:16px 20px;border-bottom:2px solid {RULE};">'
        f'<div class="c-brand" style="font:700 19px Arial;color:{BRAND};">{title}</div>'
        f'<div class="c-mute" style="font:400 11px Arial;color:{MUTE};padding-top:3px;">'
        f'{subtitle}</div></td></tr>'
    )


def card_close(footer):
    return (
        f'<tr><td class="c-bd" style="padding:14px 20px 18px;border-top:1px solid {LINE};">'
        f'<div class="c-mute" style="font:italic 10px Arial;color:{MUTE};line-height:1.6;">'
        f'{footer}</div></td></tr>'
        '</table></td></tr></table></body></html>'
    )


def send_email(html, subject, to_addr=RECIPIENT, attachments=(), images=()):
    """
    Gmail SMTP. Refuses to send rather than failing quietly if the secret is missing.

    Structure is mixed( alternative(html), attachments ) — the alternative part has to
    wrap the body on its own or some clients show the attachments and hide the email.

    `attachments` is a list of (filename, payload) pairs. A bytes payload is attached as
    a PDF (the printable recipe cards); a str payload as HTML (the shopping list, which
    opens in Chrome on a phone and has real checkboxes).

    `images` is a list of (cid, path) pairs attached INLINE, so the meal photos travel
    with the message instead of being fetched from the publisher. Remote images did not
    render in Gmail even though they were reachable; carrying them removes the whole
    class of problem — no external fetch, no "display images below", nothing to block.
    Inline parts live in a related( alternative(html), images ) subtree, which is the
    structure clients expect for cid: references.
    """
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not pw:
        raise SystemExit("GMAIL_APP_PASSWORD not set — refusing to send.")
    if to_addr != RECIPIENT:
        subject = "[TEST] " + subject
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = SENDER
    msg["To"] = to_addr
    body = MIMEMultipart("alternative")
    body.attach(MIMEText(html, "html", "utf-8"))
    if images:
        related = MIMEMultipart("related")
        related.attach(body)
        for cid, path in images:
            with open(path, "rb") as fh:
                part = MIMEImage(fh.read(), _subtype="jpeg")
            part.add_header("Content-ID", f"<{cid}>")
            part.add_header("Content-Disposition", "inline",
                            filename=os.path.basename(path))
            related.attach(part)
        msg.attach(related)
    else:
        msg.attach(body)
    for filename, payload in attachments:
        # bytes = the printed recipe cards, which are a PDF because they go to a printer.
        # str = the shopping list, which stays HTML because its checkboxes get tapped in
        # the aisle. Sending the PDF as text/html would corrupt it silently.
        if isinstance(payload, bytes):
            part = MIMEApplication(payload, _subtype="pdf")
        else:
            part = MIMEText(payload, "html", "utf-8")
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)
    ctx = ssl.create_default_context()
    recipients = [a.strip() for a in to_addr.split(",") if a.strip()]
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
        s.login(SENDER, pw)
        s.sendmail(SENDER, recipients, msg.as_string())
    print(f"sent to {to_addr}")
