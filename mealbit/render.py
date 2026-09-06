#!/usr/bin/env python3
"""
Newsletter HTML.

Section order is deliberate and follows the build brief: the thing you act on first comes
first. Meals, then the ledger that says who eats what, then the store-routed shopping
list, then what's actually at the market, then the one Sunday prep job — and the Coffee
Ritual last, because it's the part you read with a drink rather than a shopping bag.
"""
import base64
import html as _html

from .email_kit import (PAGE, CARD, PANEL, LINE, INK, MUTE, BRAND, TEAL, SOFT,
                        GOOD, GOOD_T, WARN_T, hbar, section, card_open, card_close)
from . import library as L
from .planner import EATERS

E = _html.escape

KIND_COLOR = {"leftovers": GOOD_T, "prep": TEAL, "assembly": WARN_T, "gap": MUTE}
KIND_LABEL = {"leftovers": "leftovers", "prep": "Sun batch",
              "assembly": "5-min", "gap": "unfilled"}


def _p(txt, size=12, color=None, cls="c-mute", pad="0", weight=400, lh=1.6):
    color = color or MUTE
    return (f'<div class="{cls}" style="font:{weight} {size}px Arial;color:{color};'
            f'padding:{pad};line-height:{lh};">{txt}</div>')


def _para(body, prefix):
    """
    Pull one whole Markdown paragraph starting with `prefix`.

    Recipe bodies are hard-wrapped at ~88 columns, so taking a single line truncates the
    sentence mid-clause. Join until the blank line that ends the paragraph.
    """
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            buf = [line]
            for nxt in lines[i + 1:]:
                if not nxt.strip():
                    break
                buf.append(nxt.strip())
            text = " ".join(buf)
            return text.split(":**", 1)[-1].strip() if ":**" in text else text.strip()
    return ""


def _why(recipe):
    return _para(recipe.get("body", ""), "**Why")


def _the_move(recipe):
    return _para(recipe.get("body", ""), "**The move:**")


def _lead(recipe):
    """The drink card's opening paragraph — the pitch, before any technique."""
    body = recipe.get("body", "")
    buf = []
    for line in body.splitlines():
        if line.startswith("**"):
            break
        if not line.strip():
            if buf:
                break
            continue
        buf.append(line.strip())
    return " ".join(buf)


def _clip(text, budget):
    """
    Whole sentences up to a budget, and never fewer than one useful one.

    Taking only the first sentence produced "The move — the timer.", which is true and
    says nothing. Keep adding sentences until there's something to act on.
    """
    out = []
    for part in text.replace("? ", "?|").replace("! ", "!|").replace(". ", ".|").split("|"):
        part = part.strip()
        if not part:
            continue
        if out and (len(" ".join(out)) > 55 or len(" ".join(out)) + len(part) > budget):
            break
        out.append(part)
    return " ".join(out)


def _md_bold(t):
    """
    Recipe bodies are Markdown. Bold and italic survive into the email; everything else
    is dropped. Bold is handled first so the ** of a bold run is never mistaken for two
    italic markers.
    """
    out, parts = "", t.split("**")
    for i, p in enumerate(parts):
        out += (f'<b class="c-ink" style="color:{INK};">{p}</b>' if i % 2 else p)
    chunks = out.split("*")
    if len(chunks) > 2:
        out = "".join(f"<i>{c}</i>" if i % 2 else c for i, c in enumerate(chunks))
    return out.replace("*", "")


# ---------------------------------------------------------------- sections

def _src(slug, path, embed):
    """
    Where the thumbnail comes from, which is not the same answer in both places.

    In the email it is `cid:` — the photo rides along as an inline attachment, because a
    remote URL did not survive delivery. But `cid:` resolves only inside a mail client, so
    a file written to out/ and opened in a browser would show four broken boxes, and
    `tools/screenshot.py` would quietly stop being a check on anything. The preview
    therefore inlines the same bytes as a data: URI.
    """
    if embed == "cid":
        return f"cid:{E(slug)}"
    with open(path, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("ascii")


def _n_cooked(plan):
    """Dinners actually cooked from this library this week."""
    return sum(1 for d in plan["dinners"] if not d.get("external"))


def _sheets(plan):
    """
    How many sheets the cards come to, in words.

    Hard-coded "two sheets" was a lie the week a meal kit covered three nights and there
    was one card to print — and then a lie again once every lunch got a card too, because
    this counted dinners only. Every cooked dinner, every lunch, each coffee drink and
    each syrup or crumble to make is a card; two cards to a sheet, rounded up.
    """
    n = -(-(_n_cooked(plan) + len(plan.get("lunches") or [])
            + len(plan.get("coffee") or []) + len(plan.get("to_make") or [])) // 2)
    return {0: "nothing to print this week", 1: "one sheet",
            2: "two sheets"}.get(n, f"{n} sheets")


def _gear_line():
    """What the drink is made on, from config — the machine and grinder if named, else gear."""
    cfg = L.load_household()
    named = [cfg.get("espresso_machine"), cfg.get("grinder")]
    named = [str(x) for x in named if x]
    if named:
        return " + ".join(named)
    return ", ".join(str(g) for g in (cfg.get("gear") or [])) or "the counter"


def _not_for(items):
    """'not on <name>'s plate' — whoever per_plate says skips any of these items."""
    who = []
    for it in items:
        for w in L.per_plate_who(it):
            if w not in who:
                who.append(w)
    if not who:
        return "one plate only"
    return "not on " + " or ".join(f"{E(w)}&rsquo;s" for w in who) + " plate"


def _dinners(plan, embed):
    """
    Image, title, time, one line. Nothing else.

    The household's note on the first send: "way too verbose — just a clear cut reference for meals
    with some light contextual notes." So the why-line is clipped to a single sentence and
    the picture does the rest of the talking.
    """
    rows = ""
    for night, d in zip(plan["cook_nights"], plan["dinners"]):
        if d.get("external"):
            # Already in the house, nothing to shop for and no card to print. It still
            # gets a row, because the week has to read as a week.
            rows += (
                f'<tr><td class="c-bd" style="padding:10px 4px 11px;'
                f'border-bottom:1px solid {LINE};">'
                f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
                f'<td width="104" valign="top">'
                f'<div class="c-panel c-bd" bgcolor="{PANEL}" style="width:104px;height:78px;'
                f'background-color:{PANEL};border:1px dashed {LINE};border-radius:6px;">'
                f'</div></td>'
                f'<td valign="top" style="padding-left:12px;">'
                f'<div class="c-brand" style="font:700 10px Arial;color:{BRAND};'
                f'letter-spacing:.5px;text-transform:uppercase;">{E(night)}</div>'
                f'<div style="font:700 14px Arial;line-height:1.3;padding-top:2px;">'
                f'{E(d["title"])}</div>'
                f'<div class="c-mute" style="font:400 11.5px Arial;color:{MUTE};'
                f'padding-top:4px;line-height:1.45;">Already in the house &mdash; nothing '
                f'for it on the shopping list, and it brings its own card.</div>'
                f'</td></tr></table></td></tr>')
            continue
        # Whole first sentence or nothing. Clipping mid-word ("...which is exactly what
        # you want when you're…") reads as broken, not brief.
        why = _why(d).split(". ")[0].rstrip(".") + "."
        if len(why) > 155:
            why = ""
        url = d.get("source_url")
        # The photo is carried, not fetched: a remote <img src="https://..."> did not
        # survive into the inbox even though the images themselves were reachable.
        img = L.image_path(d["slug"])
        # Only link the photo when there is a recipe to link TO. A representative photo
        # has no source_url, and wrapping it in <a href="None"> is how this first broke.
        pic = (f'<img src="{_src(d["slug"], img, embed)}" width="104" height="78" alt="" '
               f'style="width:104px;height:78px;border-radius:6px;'
               f'display:block;border:0;">') if img else ""
        thumb = ((f'<a href="{E(url)}" style="text-decoration:none;">{pic}</a>'
                  if url else pic)) if img else (
                 f'<div class="c-panel c-bd" bgcolor="{PANEL}" style="width:104px;height:78px;'
                 f'background-color:{PANEL};border:1px solid {LINE};border-radius:6px;"></div>')
        title = (f'<a href="{E(url)}" class="c-ink" style="color:{INK};text-decoration:none;">'
                 f'{E(d["title"])}</a>') if url else E(d["title"])
        rows += (
            f'<tr><td class="c-bd" style="padding:10px 4px 11px;border-bottom:1px solid {LINE};">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
            f'<td width="104" valign="top">{thumb}</td>'
            f'<td valign="top" style="padding-left:12px;">'
            f'<div class="c-brand" style="font:700 10px Arial;color:{BRAND};'
            f'letter-spacing:.5px;text-transform:uppercase;">{E(night)} '
            f'&middot; {d.get("active_time")} min</div>'
            f'<div style="font:700 14px Arial;line-height:1.3;padding-top:2px;">{title}</div>'
            f'<div class="c-mute" style="font:400 11.5px Arial;color:{MUTE};padding-top:4px;'
            f'line-height:1.45;">{E(why)}</div>'
            # A few words, because getting this wrong puts a plate in front of someone
            # that they cannot eat. The card carries the full instruction; this is the flag,
            # and it names the person rather than saying "one plate only".
            + (f'<div style="font:700 10px Arial;color:{WARN_T};padding-top:4px;'
               f'letter-spacing:.3px;">'
               f'{E(", ".join(str(x) for x in d["per_plate"]))} '
               f'&mdash; {_not_for(d["per_plate"])}</div>' if d.get("per_plate") else "")
            # The ledger below already says what lunch is; this line only has to explain
            # why THIS night isn't feeding it.
            + (f'<div style="font:400 10px Arial;color:{MUTE};padding-top:3px;">'
               f'Eat it tonight &mdash; doesn&rsquo;t pack as a lunch.</div>'
               if not int(d.get("leftovers") or 0) else "")
            + (f'<div class="c-mute" style="font:400 9px Arial;color:{MUTE};'
               f'padding-top:4px;">photo: {E(L.photo_credit(d))}</div>'
               if L.photo_credit(d) else "")
            + '</td></tr></table></td></tr>')
    n_box = sum(1 for d in plan["dinners"] if d.get("external"))
    ms = plan.get("meals") or {}
    if n_box:
        sub = (f'{n_box} came in the box and {_n_cooked(plan)} '
               f'{"is" if _n_cooked(plan) == 1 else "are"} cooked from scratch. '
               f'Tap a photo for the full recipe.')
    elif ms.get("table_only"):
        sub = (f'Each recipe serves 4; the list buys for {len(EATERS)}, so halve it. '
               f'Tap a photo for the full recipe.')
    else:
        sub = ('Each serves 4: two at the table, two for tomorrow&rsquo;s lunch. '
               'Tap a photo for the full recipe.')
    nights = plan.get("cook_nights") or ["Mon", "Thu"]
    return (
        section(f"🥘 Dinners &mdash; {nights[0]} to {nights[-1]}", sub)
        + f'<tr><td style="padding:6px 18px 0;"><table role="presentation" width="100%" '
          f'cellpadding="0" cellspacing="0">{rows}</table></td></tr>')


def _ledger(plan):
    if not plan.get("ledger"):
        return ""           # lunch_mode: none — this household plans dinners only
    st = plan["ledger_stats"]
    rows = ""
    for row in plan["ledger"]:
        cells = ""
        for slot in row["slots"]:
            c = KIND_COLOR[slot["kind"]]
            cells += (
                f'<td width="43%" valign="top" style="padding:0 6px;">'
                f'<div class="c-mute" style="font:700 9px Arial;color:{c};'
                f'letter-spacing:.4px;text-transform:uppercase;">{E(slot["eater"])} '
                f'&middot; {KIND_LABEL[slot["kind"]]}</div>'
                f'<div class="c-ink" style="font:400 12px Arial;color:{INK};padding-top:2px;'
                f'line-height:1.4;">{E(slot["what"])}</div></td>')
        swap = (f'<tr><td colspan="3" class="c-mute" style="font:400 10px Arial;color:{MUTE};'
                f'padding:5px 6px 0;line-height:1.5;">Not feeling it? '
                f'<b class="c-ink" style="color:{INK};">{E(row["swap"])}</b> '
                f'&mdash; {row["swap_time"]} minutes, no cooking.</td></tr>'
                ) if row.get("swap") else ""
        rows += (
            f'<tr><td class="c-bd" style="padding:10px 6px 11px;border-bottom:1px solid {LINE};">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            f'<tr><td width="34" valign="top" class="c-brand" '
            f'style="font:700 12px Arial;color:{BRAND};padding-top:1px;">{row["day"]}</td>'
            f'{cells}</tr>{swap}</table></td></tr>')

    return (
        section("🥡 Lunches",
                f'<b class="c-good" style="color:{GOOD_T};">{st["leftovers"]}</b> from '
                f'dinner leftovers &nbsp;·&nbsp; <b class="c-teal" style="color:{TEAL};">'
                f'{st["prep"]}</b> from Sunday&rsquo;s batch &nbsp;·&nbsp; '
                f'<b class="c-warn" style="color:{WARN_T};">{st["assembly"]}</b> five-minute '
                f'builds at the weekend.')
        + f'<tr><td style="padding:6px 16px 0;"><table role="presentation" width="100%" '
          f'cellpadding="0" cellspacing="0">{rows}</table></td></tr>')


def _market(plan):
    """
    One market block: what's good, what the market won't have, and how to shop it.

    Previously three separate sections plus a paragraph of preamble. The household asked for the
    sourcing notes to stay but for the prose to go, so this is the merge.
    """
    chips = "".join(
        f'<span style="display:inline-block;background-color:{PANEL};border:1px solid {LINE};'
        f'border-radius:11px;padding:3px 9px;margin:0 4px 5px 0;font:400 11px Arial;'
        f'color:{INK};" class="c-panel c-bd c-ink">{E(i)}</span>'
        for i in plan["in_season"])

    moves = plan.get("market_moves") or []
    moved = ""
    if moves:
        moved = (f'<tr><td style="padding:10px 20px 0;">'
                 + _p('<b class="c-ink" style="color:' + INK + ';">Buy at QFC instead:</b> '
                      + ", ".join(f'{E(m["item"])} <span style="color:' + MUTE + ';">('
                                  + E(m["why"].split("—")[0].strip()) + ')</span>'
                                  for m in moves), size=11)
                 + '</td></tr>')

    tips = "".join(
        f'<tr><td class="c-mute" style="font:400 11px Arial;color:{MUTE};padding:3px 0;'
        f'line-height:1.5;">&bull;&nbsp; {E(t)}</td></tr>' for t in plan.get("market_tips") or [])
    news = plan.get("market", {}).get("market", {}).get("whats_in_season")
    tip_block = (f'<tr><td style="padding:10px 20px 0;">'
                 f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                 f'class="c-panel c-bd" bgcolor="{PANEL}" style="background-color:{PANEL};'
                 f'border:1px solid {LINE};border-radius:7px;">'
                 f'<tr><td style="padding:10px 14px;">'
                 f'<div class="c-ink" style="font:700 11px Arial;color:{INK};">'
                 f'Shopping the stalls</div>'
                 f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                 f'style="padding-top:3px;">{tips}</table>'
                 + (f'<div class="c-mute" style="font:400 10.5px Arial;color:{MUTE};'
                    f'padding-top:6px;line-height:1.5;">They publish the week&rsquo;s harvest: '
                    f'<b class="c-ink" style="color:{INK};">{E(news)}</b></div>' if news else "")
                 + '</td></tr></table></td></tr>') if tips else ""

    ms = plan.get("market_store")
    if not ms:
        return ""           # this household shops no farmers market; nothing to say
    where = " &middot; ".join(E(x) for x in (ms.get("when"), ms.get("where")) if x)
    return (
        section(f"🌿 At the market {plan['shop_day'].strftime('%A')}",
                f'{plan["shop_day"].strftime("%-d %B")}, {where}. Full list attached.')
        + f'<tr><td style="padding:8px 20px 0;">{chips}</td></tr>'
        + moved + tip_block)


def _prep(plan):
    items = "".join(
        f'<tr><td class="c-ink" style="font:400 12px Arial;color:{INK};padding:5px 0;'
        f'line-height:1.6;">&bull;&nbsp; {_md_bold(b)}</td></tr>' for b in plan["prep"])
    return (
        section("⏱️ Sunday prep", 'One block, after the market.')
        + f'<tr><td style="padding:6px 20px 0;"><table role="presentation" width="100%" '
          f'cellpadding="0" cellspacing="0">{items}</table></td></tr>')


def _coffee(plan):
    econ, q = plan["econ"], plan["quote"]
    n = int(econ["drinks_per_week_assumed"])

    cards, week_home, week_shop = "", 0.0, 0.0
    for c in plan["coffee"]:
        d, syrup, crumble = c["drink"], c["syrup"], c["crumble"]
        cost = float(d.get("cost_per_serving") or 0)
        shop = float(d.get("shop_equivalent") or econ["typical_shop_latte"])
        week_home += cost * n / len(plan["coffee"])
        week_shop += shop * n / len(plan["coffee"])
        move = _the_move(d)

        # Two bars on one scale — the gap is the message.
        bars = (
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            f'<tr><td class="c-ink" style="font:400 11px Arial;color:{INK};padding-bottom:4px;">'
            f'At home <b class="c-good" style="color:{GOOD_T};">${cost:.2f}</b></td></tr>'
            f'<tr><td style="padding-bottom:8px;">{hbar(cost / shop, GOOD, h=12)}</td></tr>'
            f'<tr><td class="c-ink" style="font:400 11px Arial;color:{INK};padding-bottom:4px;">'
            f'The same drink out <b class="c-ink" style="color:{INK};">${shop:.2f}</b></td></tr>'
            f'<tr><td>{hbar(1.0, SOFT, h=12, fill_class="c-soft-bg")}</td></tr></table>')

        def _kit(item, needed, label):
            # A drink whose flavouring the box has no equivalent for — a horchata milk,
            # a ganache, a chai concentrate — carries the method on its own card and
            # prints no syrup line at all. Better a missing line than a wrong one.
            if not item:
                return ""
            need, why = needed
            tag = (f'<span class="c-warn" style="color:{WARN_T};font-weight:700;">make it</span>'
                   if need else
                   f'<span class="c-good" style="color:{GOOD_T};">in the box</span>')
            return (f'<div class="c-mute" style="font:400 11px Arial;color:{MUTE};'
                    f'padding-top:5px;line-height:1.5;">{label} '
                    f'<b class="c-ink" style="color:{INK};">{E(item["title"])}</b> '
                    f'&mdash; {tag} <span class="c-mute" style="color:{MUTE};">'
                    f'({E(why)})</span></div>')

        cards += (
            f'<tr><td style="padding:12px 20px 0;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'class="c-panel c-bd" bgcolor="{PANEL}" style="background-color:{PANEL};'
            f'border:1px solid {LINE};border-radius:8px;">'
            f'<tr><td style="padding:13px 16px 4px;">'
            f'<div class="c-teal" style="font:700 15px Arial;color:{TEAL};">{E(d["title"])}</div>'
            f'<div class="c-mute" style="font:400 10px Arial;color:{MUTE};padding-top:3px;">'
            f'{E(d.get("temp", ""))} &nbsp;·&nbsp; {E(_gear_line())}</div>'
            + (_p(f'<b class="c-ink" style="color:{INK};">The move &mdash;</b> '
                  f'{_md_bold(E(_clip(move, 190)))}', size=11.5, pad="7px 0 0")
               if move else "")
            + _kit(syrup, c["syrup_needed"], "Syrup:")
            + _kit(crumble, c["crumble_needed"], "Crumble:")
            + f'</td></tr>'
              f'<tr><td style="padding:10px 16px 14px;">{bars}</td></tr>'
              f'</table></td></tr>')

    make = plan["to_make"]
    make_line = (
        f'<b class="c-ink" style="color:{INK};">Make this week:</b> '
        f'{E(", ".join(m["title"] for m in make))} &mdash; the method is on its card. '
        f'Everything else in the box is still good.'
        if make else
        f'<b class="c-ink" style="color:{INK};">Nothing to make</b> &mdash; the syrup and '
        f'crumble box is stocked, so both drinks cost you only beans and milk.')

    flag = {"verified": "", "attributed": " · widely attributed, primary source not pinned down",
            "disputed": " · almost certainly never said it",
            "legend": " · a legend, told as one",
            "fiction": " · fictional, and included on purpose",
            "history": " · a true and strange thing that happened"}.get(q["attribution"], "")
    src = E(q.get("source", "")) + flag
    q_note = (f'<div class="c-mute" style="font:400 10px Arial;color:{MUTE};padding-top:7px;'
              f'line-height:1.55;">{_md_bold(E(q.get("note", "")))}</div>'
              ) if q.get("note") else ""

    return (
        section("☕ Coffee &mdash; two this week", accent=TEAL,
                sub='The syrup and crumble box is standing stock; most weeks a new drink '
                    'costs nothing extra.')
        + cards
        + f'<tr><td style="padding:10px 20px 0;">'
        + _p(make_line, size=11) + '</td></tr>'
        + f'<tr><td style="padding:8px 20px 0;">'
        + _p(f'<b class="c-good" style="color:{GOOD_T};">'
             f'${week_shop - week_home:.0f} saved this week</b> &mdash; about '
             f'${week_home:.0f} of ingredients against ${week_shop:.0f} at a counter, across '
             f'{n} drinks.'
             # The "visit you skip" figure is the household's own spend, from config. No
             # spend on file, no sentence — a made-up average would be worse than none.
             + (f' The bigger number is the visit you skip entirely: those average '
                f'<b class="c-ink" style="color:{INK};">${econ["avg_per_visit"]:.2f}</b> '
                f'(${econ["monthly_coffee_spend"]:.0f} &divide; {econ["monthly_visits"]} '
                f'visits), because a visit is rarely just a drink.'
                if econ.get("avg_per_visit") else ""), size=11)
        + '</td></tr>'
        + f'<tr><td style="padding:14px 20px 0;">'
          f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
          f'<tr><td style="border-left:3px solid {TEAL};padding:2px 0 2px 13px;" class="c-bd">'
          f'<div class="c-ink" style="font:italic 400 13px Arial;color:{INK};'
          f'line-height:1.65;">&ldquo;{E(q["text"])}&rdquo;</div>'
          f'<div class="c-mute" style="font:700 11px Arial;color:{MUTE};padding-top:7px;">'
          f'&mdash; {E(q["who"])}</div>'
          + (f'<div class="c-mute" style="font:400 10px Arial;color:{MUTE};padding-top:2px;">'
             f'{src}</div>' if src.strip() else "")
          + q_note
          + '</td></tr></table></td></tr>')


def _notes(plan):
    if not plan["notes"]:
        return ""
    items = "".join(f'<li style="padding-bottom:3px;">{E(n)}</li>' for n in plan["notes"])
    return (f'<tr><td style="padding:16px 20px 0;">'
            f'<div class="c-mute" style="font:400 10px Arial;color:{MUTE};line-height:1.6;">'
            f'<b class="c-ink" style="color:{INK};">How this week was picked, where it '
            f'bent the rules:</b><ul style="margin:5px 0 0;padding-left:16px;">{items}</ul>'
            f'</div></td></tr>')


# ---------------------------------------------------------------- top level

def render(plan, embed="data"):
    """
    embed="cid" for the outgoing email, "data" for anything opened in a browser.

    The default is the safe one: a preview that renders standalone. Only the send path
    asks for cid:, and it is the only path that also attaches the images.
    """
    ws, we = plan["week_start"], plan["week_end"]
    span = f'{ws.strftime("%b %-d")} &ndash; {we.strftime("%b %-d")}'
    sub = (f'{span} &nbsp;·&nbsp; shop {plan["shop_day"].strftime("%a %-d %b")} '
           f'&nbsp;·&nbsp; {plan["season"].replace("-", " ")}')
    return (
        card_open("Mealbit", sub)
        + f'<tr><td style="padding:13px 20px 0;">'
        + _p('<b class="c-ink" style="color:' + INK + ';">Attached:</b> the shopping list '
             f'(open in Chrome, tap items off) and the recipe cards '
             f'({_sheets(plan)}, print them).',
             size=11.5)
        + '</td></tr>'
        + _dinners(plan, embed)
        + _ledger(plan)
        + _market(plan)
        + _prep(plan)
        + _coffee(plan)
        + _notes(plan)
        + card_close(
            'Every meal is a file in the repo you can edit or rate. Nothing is generated '
            'at send time. Market day confirmed 2026-08-30; stock varies week to week.')
    )
