#!/usr/bin/env python3
"""
The two printed sheets, and the phone shopping list.

Three different jobs, three different documents, and conflating them is why most meal
planners are annoying to actually use:

  cards.pdf   — TWO sheets of letter paper, landscape, printed Saturday night. Two
                dinners per sheet, cut down the middle: four half-letter cards, one per
                night. PDF because it is going to a printer, and a browser's HTML print
                path adds headers, footers and its own margins.

  list.html   — the phone list, ATTACHED TO THE EMAIL, and the only HTML of the three.
                It has to be HTML: the checkboxes are tapped in the aisle. Open it in
                Chrome, tap items off, close it. Used once, so it deliberately keeps no
                state and needs no hosting, no account and no app.

Google Keep has no API for personal accounts — it is Workspace-only, and has been since
the API shipped — so a Keep list cannot be created programmatically. An attached page is
the closest thing that still works the way Keep does in the aisle.
"""
import base64
import re
import html as _html
import os
from urllib.parse import quote_plus

from . import library as L
from .planner import EATERS

E = _html.escape

from . import config as C

# One colour per store, in visit order, from config/stores.yml. The palette cycles if a
# household shops more than four places; the short code is theirs.
_TAG_COLOURS = ("#55760f", "#0c7d70", "#8a6300", "#7a4a8a", "#2f5f8a", "#8a3a3a")
STORE_TAG = {st["id"]: (st["short"], _TAG_COLOURS[i % len(_TAG_COLOURS)])
             for i, st in enumerate(C.stores())}
STORE_FULL = {st["id"]: st["name"] for st in C.stores()}
STORE_KEY = " &middot; ".join(
    st["name"] if st["short"].lower() == st["name"].lower() else f'{st["short"]} {st["name"]}'
    for st in C.stores())


def _qr_svg(url, scale=3):
    """Inline SVG QR. Optional: without segno the card falls back to a printed URL."""
    try:
        import segno
    except ImportError:
        return None
    buf = segno.make(url, error="m").svg_inline(scale=scale, dark="#262b1d")
    return buf


def qr_target(recipe):
    """
    What the card's QR code points at.

    A curated `source_url` is best — a real published version of the dish, with a photo and
    a second opinion on technique. But a link has to be REAL and CHECKED: a dead or
    misattributed URL wastes a scan in the kitchen and poisons trust in every other code on
    the sheet. Search results alone are not verification (they surface mirrors and
    scraper sites), and this environment's egress proxy blocks most recipe domains, so
    they cannot be checked here.

    So until a recipe carries a verified link, the QR falls back to an IMAGE SEARCH for the
    dish. It always resolves, it can never be misattributed, it needs no maintenance, and
    it answers the actual question — "what is this supposed to look like?" — with fifty
    photos instead of one.

    Returns (url, caption, is_curated).
    """
    if recipe.get("source_url"):
        return (recipe["source_url"],
                recipe.get("source_name") or "recipe + photo", True)
    # Use the WHOLE title. Trimming at " with " turned "Skirt steak with chimichurri and
    # smashed new potatoes" into "Skirt steak", which is a search for a different dinner.
    q = quote_plus(recipe["title"] + " recipe")
    return (f"https://www.google.com/search?q={q}&udm=2", "see the dish", False)


def _by_store(recipe):
    """
    The recipe's ingredients grouped by the store the plan sends you to.

    A recipe that reached here through build_plan already carries `_by_store`. One that
    didn't — a test rendering a bare recipe — is routed now, for the current month.
    """
    if "_by_store" in recipe:
        return recipe["_by_store"]
    from .planner import route_to_stores
    from datetime import date
    return route_to_stores([recipe], date.today().month)[0][0]["_by_store"]


def _ingredients(recipe):
    """Every buyable ingredient for one recipe, tagged with the store it comes from."""
    out = []
    for store, lines in _by_store(recipe).items():
        for line in lines:
            it = L.parse_item(str(line))
            if not it["name"]:
                continue
            qty = L.fmt_qty(it["qty"])
            unit = L.fmt_unit(it["unit"], it["qty"]) if it["unit"] else ""
            name = L.fmt_name(it["name"], it["qty"], it["unit"])
            out.append({"store": store,
                        "text": " ".join(x for x in (qty, unit, name) if x)})
    return out


def _clip_sentences(text, budget):
    """
    Whole sentences up to a character budget. Never clips mid-word.

    Recipe bodies are Markdown and the card is not: emphasis markers are stripped, both
    the ** of bold and the lone * of italics. A card that printed `the pan must be *warm,
    not hot*` is a card someone has to mentally edit while cooking.
    """
    text = text.replace("**", "").replace("*", "")
    out = []
    for sentence in text.replace("? ", "?|").replace("! ", "!|").replace(". ", ".|").split("|"):
        sentence = sentence.strip()
        if not sentence:
            continue
        if out and len(" ".join(out)) + len(sentence) > budget:
            break
        out.append(sentence)
    return " ".join(out)


def _tips(recipe, budget=430):
    """
    The technique notes, not the whole method.

    The brief asked for ingredients and a couple of technique tips, not granular steps, so this
    is still only the "The move" paragraph — never the numbered method. But the budget was
    230 characters when four recipes shared one portrait page, and it was cutting recipes
    off mid-thought: panzanella lost "the bread is torn, not cubed" entirely. A card is now
    a whole half-sheet, so the second move fits too.

    The budget is what keeps the card on one half-sheet. Raising it clips the bottom of
    the card silently — test_cards_fit_their_sheet measures the real rendered height and
    will catch it, but only if a browser is installed.

    Recipes bold the move that matters, and often bold a second one. Split on those so
    each gets its own line instead of running together in a wall of prose.
    """
    from .render import _para
    move = _para(recipe.get("body", ""), "**The move:**")
    if not move:
        return []
    move = _html.unescape(move)
    body = _clip_sentences(move, budget)
    # "Second move:" / "Then:" introduce a genuinely separate instruction — a line break
    # there is the difference between two tips and one paragraph nobody reads.
    for marker in ("Second move:", "Then, the second move:", "The second move:"):
        if marker in body:
            head, tail = body.split(marker, 1)
            return [head.strip(), tail.strip()]
    return [body]


def _leftover_plan(recipe):
    """
    How the food gets eaten later — the same job under two names.

    A dinner writes "**Leftover plan:**" (how tomorrow's lunch is packed); a Sunday batch
    lunch writes "**At the desk:**" (what goes on it when you open the container). Both
    are the instruction that makes the food work hours after it was made, and both were
    printed nowhere.

    Every dinner is cooked to serve 4 so that two portions become lunch — that ratio is
    the entire economics of the plan, and "don't add the mozzarella until you eat" is
    what keeps it true.
    """
    from .render import _para
    for prefix, heading in (("**Leftover plan:**", "Tomorrow&rsquo;s lunch"),
                            ("**At the desk:**", "At the desk")):
        para = _para(recipe.get("body", ""), prefix)
        if para:
            text = _clip_sentences(
                _html.unescape(para).replace(prefix.strip("*"), "").strip(), 185)
            return text, heading
    return "", ""


# A card is HALF a landscape letter sheet: 5.5in wide, 8.5in tall, two to a page with a
# cut line down the middle. Four dinners therefore print on exactly two sheets, and four
# scissor cuts give four kitchen cards. The old layout put all four on one portrait page
# as quarter-tiles, which printed but was not cuttable into anything.
CARD_W, CARD_H, PAD = "5.5in", "8.5in", "0.42in"

PRINT_CSS = f"""
@page {{ size: 11in 8.5in; margin: 0; }}
* {{ box-sizing: border-box; }}
html, body {{ margin:0; padding:0; }}
body {{ font-family: Helvetica, Arial, sans-serif; color:#262b1d; background:#fff;
       -webkit-print-color-adjust:exact; print-color-adjust:exact; }}

/* One sheet = one landscape page = two cards. break-after on the last sheet would emit a
   trailing blank page, which is the classic way a "two sheet" document prints as three. */
.sheet {{ width:11in; height:8.5in; display:flex; page-break-after:always;
         break-after:page; overflow:hidden; }}
.sheet:last-child {{ page-break-after:auto; break-after:auto; }}

.card {{ width:{CARD_W}; height:{CARD_H}; padding:{PAD}; overflow:hidden;
        display:flex; flex-direction:column; }}
/* The cut guide. Dashed so it reads as "cut here" and not as a table border. */
.card:first-child {{ border-right:1pt dashed #93a077; }}
.cut {{ position:absolute; left:50%; transform:translateX(-50%); font-size:9pt;
       color:#93a077; background:#fff; padding:0 3pt; }}
.cut.top {{ top:0.10in; }}
.cut.bot {{ bottom:0.10in; }}
.sheet {{ position:relative; }}

.night {{ font-size:8.5pt; font-weight:bold; color:#55760f; letter-spacing:.6pt;
         text-transform:uppercase; }}
.title {{ font-size:17pt; font-weight:bold; line-height:1.15; margin:3pt 0 7pt;
         letter-spacing:-.3pt; }}
/* The photo is the flexible one, deliberately. A card carries between 5 and 11
   ingredients and one or two technique moves, and that swing is about four lines — more
   than the slack on the sheet. Shaving type until the WORST week fits leaves every other
   week cramped, so instead the photo shrinks (flex-shrink on a flex item wins over its
   height) and the list and technique are never touched. Floor at 0.95in so it stays a
   photograph rather than a stripe. */
.photo {{ width:100%; flex:0 1 auto; height:1.68in; min-height:0.95in; object-fit:cover;
         border-radius:5pt; display:block; margin-bottom:9pt; }}
/* No verified photo yet: a labelled rule beats an empty grey box, which reads as broken. */
.nophoto {{ border-top:1.5pt solid #e7ebda; margin-bottom:9pt; }}
.credit {{ font-size:5.5pt; color:#a3ab90; margin:-7pt 0 4pt; letter-spacing:.2pt; }}

.h2 {{ font-size:7.5pt; font-weight:bold; color:#8a9178; letter-spacing:1pt;
      text-transform:uppercase; margin:0 0 4pt; }}
ul {{ margin:0 0 7pt; padding:0; list-style:none; }}
/* A long shop list is the one thing that reliably will not fit, and it is also the one
   thing that must never be trimmed — a missing ingredient is discovered at the store.
   Past nine items it goes two-up, which buys back about five lines and lets the photo
   return to full height. Below nine, one column reads better. */
ul.two {{ column-count:2; column-gap:11pt; }}
ul.two li {{ break-inside:avoid; }}
li {{ font-size:9.5pt; line-height:1.42; }}
.tag {{ display:inline-block; width:24pt; font-size:6.5pt; font-weight:bold;
       vertical-align:1pt; letter-spacing:.3pt; }}
.have {{ font-size:8pt; line-height:1.45; color:#6c7458; margin-bottom:8pt; }}
.have b {{ color:#8a9178; letter-spacing:.6pt; text-transform:uppercase; font-size:7pt; }}

.tips {{ border-top:1px solid #e7ebda; padding-top:7pt; margin-bottom:7pt; }}
.tip {{ font-size:8.5pt; line-height:1.42; color:#3d4630; margin-bottom:4pt; }}
.tip b {{ color:#55760f; }}
.left {{ border-top:1px solid #e7ebda; padding-top:5pt; margin-bottom:5pt;
        font-size:8.5pt; line-height:1.42; color:#3d4630; }}
.pp-box .h2 {{ color:#8a6300; }}
.pp {{ font-size:6pt; font-weight:bold; letter-spacing:.4pt; text-transform:uppercase;
      color:#8a6300; border:0.6pt solid #d8c39a; border-radius:2pt; padding:0 2pt;
      vertical-align:1pt; }}

/* mt:auto pins the footer to the bottom of the card however tall the content above is,
   so all four cards line up when they are stacked on the counter. */
.foot {{ margin-top:auto; padding-top:8pt; border-top:1px solid #e7ebda;
        display:flex; align-items:flex-end; justify-content:space-between; gap:8pt; }}
.serves {{ font-size:8pt; color:#6c7458; line-height:1.4; }}
.serves b {{ color:#262b1d; }}
.qr {{ text-align:center; flex:0 0 auto; }}
.qr svg {{ width:54pt; height:54pt; display:block; }}
.qr .cap {{ font-size:5.8pt; color:#8a9178; margin-top:2pt; max-width:62pt; line-height:1.2; }}
"""


def _photo(r):
    """
    The dish photo, embedded as a data: URI.

    The cards are rendered to PDF by a headless browser that has no access to this repo's
    filesystem in the same working directory, and the HTML fallback is opened as a
    standalone email attachment. A file path or a remote URL would fail in one of those
    two; embedding survives both.
    """
    path = L.image_path(r["slug"])
    if not path:
        return '<div class="nophoto"></div>'
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()
    img = f'<img src="data:image/jpeg;base64,{b64}" class="photo" alt="">'
    # A CC-licensed stand-in is someone else's photograph of the same dish, not a picture
    # of this recipe. The licence requires the credit; saying so also stops the photo
    # being read as "this is exactly what yours will look like".
    cred = L.photo_credit(r)
    return img + (f'<div class="credit">a photo of the dish &mdash; {E(cred)}</div>'
                  if cred else "")


def _not_on(recipe):
    """'not on <name>'s plate' for the card's per-plate heading."""
    who = []
    for it in (recipe.get("per_plate") or []):
        for w in L.per_plate_who(str(it)):
            if w not in who:
                who.append(w)
    if not who:
        return "&mdash; one plate only"
    return "&mdash; not on " + " or ".join(f"{E(w)}&rsquo;s" for w in who)


def _per_plate(recipe):
    """
    The "this goes on one plate only" instruction, and the note explaining why.

    Printed as its own block rather than a footnote: it is the difference between a dinner
    someone can eat and one they can't, and the card is what is on the counter while you
    plate.
    """
    items = [str(x) for x in (recipe.get("per_plate") or [])]
    if not items:
        return "", ""
    from .render import _para
    note = _para(recipe.get("body", ""), "**Per plate:**")
    note = _clip_sentences(_html.unescape(note)
                           .replace("Per plate:", "").strip(), 215)
    return ", ".join(items), note


def _coffee_method(recipe, budget=400):
    """
    The whole method for a drink, a syrup or a crumble — not just the technique note.

    A dinner card prints ingredients and "The move", because the household asked for
    tips, not steps. A coffee card is different: the email says "make miso caramel
    syrup" and until this card existed the method was printed nowhere. The bodies are
    short — an intro, one or two bold-led method paragraphs, "The move" — so every
    paragraph after the intro goes on the card, bold lead kept as the label.
    """
    paras = [p.strip() for p in re.split(r"\n\s*\n", recipe.get("body") or "") if p.strip()]
    out = []
    for para in paras[1:]:
        para = _html.unescape(" ".join(para.split()))
        m = re.match(r"\*\*(.+?):\*\*\s*(.*)", para, re.S)
        lead, text = (m.group(1), m.group(2)) if m else ("", para)
        text = _clip_sentences(text, budget)
        if text:
            out.append((lead, text))
    return out


def _coffee_meta_and_foot(label, r):
    """What kind of coffee card this is, top and bottom."""
    kind = r.get("kind")
    if kind == "drink":
        temp = {"either": "hot or iced"}.get(r.get("temp"), r.get("temp") or "")
        gear = ", ".join(str(g) for g in (r.get("gear") or [])[:2])
        head = f'{E(label)} &nbsp;&middot;&nbsp; {E(temp)}' + (f' &nbsp;&middot;&nbsp; {E(gear)}' if gear else "")
        bits = []
        for part, name in (("_syrup", "Syrup"), ("_crumble", "Crumble")):
            item, needed = (r.get(part) or (None, None))
            if item:
                bits.append(f'{name}: <b>{E(item["title"])}</b> &mdash; '
                            + ("<b>make it</b>, its card is attached" if needed else "in the box"))
        foot = " &nbsp;&middot;&nbsp; ".join(bits) or "Makes one. Nothing to make ahead."
        return head, foot
    makes = r.get("makes") or ""
    head = (f'{E(label)} &nbsp;&middot;&nbsp; {r.get("active_time") or "?"} min, once'
            + (f' &nbsp;&middot;&nbsp; makes {E(str(makes))}' if makes else ""))
    keeps = r.get("keeps_weeks")
    foot = (f'Keeps <b>{keeps} weeks</b>' if keeps else "Keeps") + \
           (f' &mdash; {E(str(r.get("storage")))}.' if r.get("storage") else ".") + \
           " Made once, used all season; the email says when it is due again."
    return head, foot


def _meta_and_foot(label, r):
    """
    The two lines that say what KIND of thing this card is, top and bottom.

    A dinner is a night and a hands-on time; a Sunday batch is a job you do once and eat
    five times; a five-minute build is a list you assemble the morning of. Printing
    "serves 4, two for tomorrow's lunch" over a sandwich would be nonsense.
    """
    if r.get("kind") in L.COFFEE_KINDS:
        return _coffee_meta_and_foot(label, r)
    style = r.get("lunch_style")
    if r.get("kind") == "lunch" and style == "sunday-prep":
        makes = r.get("makes") or r.get("serves")
        return (f'{E(label)} &nbsp;&middot;&nbsp; {r.get("active_time")} min, once '
                f'&nbsp;&middot;&nbsp; makes {makes}',
                f'Batched Sunday &mdash; <b>{makes}</b> lunches out of one job. '
                f'A Sunday batch is only served Mon&ndash;Fri; by the weekend it is a '
                f'week old.')
    if r.get("kind") == "lunch":
        # Don't claim more than the recipe does. An earlier version of this line said
        # "nothing here needs a pan or a timer" and printed it under a tuna melt whose
        # own technique note is "cook it like a grilled cheese in a pan".
        return (f'{E(label)} &nbsp;&middot;&nbsp; {r.get("active_time")} min, day-of',
                f'Built the day you eat it, in <b>{r.get("active_time")}</b> minutes. '
                f'Makes {r.get("makes") or r.get("serves")}.')
    left = int(r.get("leftovers") or 0)
    head = (f'{E(label)} &nbsp;&middot;&nbsp; {r.get("active_time")} min hands-on'
            f' &nbsp;&middot;&nbsp; {r.get("total_time")} min total')
    if r.get("_scale"):
        # This household cooks for the table only: the recipe still says 4, the list
        # bought for fewer, and the card has to say so or the cook doubles the shop.
        return (head, f'Recipe serves <b>{r.get("serves")}</b>; the list bought for '
                      f'<b>{len(EATERS)}</b> &mdash; <b>halve it.</b>')
    # Don't print a lunch box the dish cannot fill. This line used to read "2 for
    # tomorrow's lunch" under a panzanella that is soggy bread by morning.
    return (head,
            f'Serves <b>{r.get("serves")}</b> &mdash; two at the table, <b>{left}</b> for '
            f'tomorrow&rsquo;s lunch.' if left else
            f'Serves <b>{r.get("serves")}</b> &mdash; <b>eat it tonight.</b> This one does '
            f'not pack; the week&rsquo;s lunches are covered elsewhere.')


def _card(label, r):
    """One recipe, one half-sheet. Dinners and lunches print the same shape."""
    url, caption, _curated = qr_target(r)
    qr = _qr_svg(url)
    qr_html = (f'<div class="qr">{qr}<div class="cap">{E(caption)}</div></div>'
               if qr else "")

    pp_items, pp_note = _per_plate(r)
    pp_keys = [L.normalize(x) for x in (r.get("per_plate") or [])]

    def _mark(text):
        """Flag the bought line itself, so it is obvious while you are plating."""
        name = L.normalize(text)
        if any(k in name or name in k for k in pp_keys):
            who = L.per_plate_who(name)
            label = ("not for " + " or ".join(who)) if who else "one plate only"
            return f'{E(text)} <span class="pp">{E(label)}</span>'
        return E(text)

    items = _ingredients(r)
    ings = "".join(
        f'<li><span class="tag" style="color:{STORE_TAG[i["store"]][1]}">'
        f'{STORE_TAG[i["store"]][0]}</span>{_mark(i["text"])}</li>' for i in items)
    ul_class = ' class="two"' if len(items) >= 9 else ""
    pantry = ", ".join(str(x) for x in (r.get("pantry") or [])[:10])
    # NOT "already have". Only salt, pepper, olive oil and white vinegar are assumed;
    # everything else here is a thing to look for on a shelf before you start.
    have = f'<div class="have"><b>Check you have</b> &nbsp;{E(pantry)}</div>' if pantry else ""
    coffee = r.get("kind") in L.COFFEE_KINDS
    if coffee:
        tips = "".join(f'<div class="tip"><b>{E(lead) + " &mdash; " if lead else "&rsaquo; "}</b>'
                       f'{E(text)}</div>' for lead, text in _coffee_method(r))
    else:
        tips = "".join(f'<div class="tip"><b>&rsaquo;</b> {E(t)}</div>' for t in _tips(r))
    packing, packing_head = _leftover_plan(r)
    left = int(r.get("leftovers") or 0)
    meta, serves_line = _meta_and_foot(label, r)

    return (
        f'<div class="card">'
        f'<div class="night">{meta}</div>'
        f'<div class="title">{E(r["title"])}</div>'
        f'{_photo(r)}'
        f'<div class="h2">Shop for this</div><ul{ul_class}>{ings}</ul>{have}'
        + (f'<div class="tips"><div class="h2">{"Method" if coffee else "Technique"}</div>{tips}</div>' if tips else "")
        + (f'<div class="left pp-box"><div class="h2">Per plate &mdash; {E(pp_items)} '
           f'{_not_on(r)}</div>{E(pp_note)}</div>' if pp_items else "")
        + (f'<div class="left"><div class="h2">'
           f'{packing_head if (left or r.get("kind") == "lunch") else "Why it doesn&rsquo;t pack"}'
           f'</div>{E(packing)}</div>' if packing else "")
        + f'<div class="foot">'
        f'<div class="serves">{serves_line}<br>'
        f'<span style="color:#8a9178;">{STORE_KEY}</span></div>{qr_html}</div>'
        f'</div>')


def render_cards(plan):
    """
    Every card of the week on landscape sheets, two per sheet, cut down the middle.

    Dinners first, in cooking order, then the lunches — Sunday batches before the
    five-minute builds, which is the order you actually do the work in — then the two
    coffee drinks and anything the box needs made. Lunches had no
    card at all until the household asked for them, which meant the two dishes you cook on Sunday
    and eat all week existed only in the email.

    Fewer cards when some dinners came from a meal kit: those bring their own, and there
    is nothing of ours to print.

    That ask changed the shape of the document: the previous version was two
    PORTRAIT sheets — four quarter-tiles on one, the shopping list on the other — which
    printed fine but could not be cut into anything you would put on a counter. Shopping
    left the print entirely; it is the HTML attachment with the checkboxes, which is the
    one file that has to stay HTML because it is tapped in the aisle.
    """
    sheets = ""
    for group in card_groups(plan):
        for i in range(0, len(group), 2):
            two = group[i:i + 2]
            cards = "".join(_card(n, r) for n, r in two)
            # An odd group would otherwise leave a half-width sheet; pad so the cut line
            # still lands on the centre of the page.
            if len(two) == 1:
                cards += '<div class="card"></div>'
            # The cut markers come AFTER the cards: they are absolutely positioned so the
            # order is invisible, but it keeps the first .card an actual :first-child,
            # which is what draws the cut line.
            sheets += (f'<div class="sheet">{cards}'
                       f'<div class="cut top">&#9986;</div>'
                       f'<div class="cut bot">&#9986;</div></div>')

    ws, we = plan["week_start"], plan["week_end"]
    span = f'{ws.strftime("%b %-d")} – {we.strftime("%b %-d, %Y")}'
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<title>Mealbit cards — {E(span)}</title>'
            f'<style>{PRINT_CSS}</style></head><body>{sheets}</body></html>')


def card_groups(plan):
    """
    The week's cards in print order, grouped so that a sheet never mixes kinds.

    Three groups, each padded to a whole sheet: the meals (dinners in cooking order,
    then Sunday batches, then the five-minute builds), the coffee drinks on a sheet of
    their own, and whatever the syrup box needs made — so the two things you make once a
    season come off one sheet and go in a drawer, and the drinks sheet lives by the
    machine. The household asked for exactly that split.
    """
    # A boxed dinner has no recipe of ours to print — the kit brings its own card. Cards
    # are only for the nights actually being cooked from this library.
    meals = [(n, r) for n, r in zip(plan["cook_nights"], plan["dinners"])
             if not r.get("external")]
    # Then the lunches, which are cooked and built in this kitchen too and had no card at
    # all. Sunday batches first, because that is the order you do the work in: everything
    # batched on Sunday, then the five-minute builds through the week.
    order = {"sunday-prep": 0, "assembly": 1}
    for r in sorted(plan["lunches"], key=lambda x: order.get(x.get("lunch_style"), 9)):
        meals.append(("Sunday batch" if r.get("lunch_style") == "sunday-prep"
                      else "5-minute build", r))
    # The coffee: each featured drink, with its photo in the header like a dinner's, and
    # whatever the box needs made this week. "Make miso caramel syrup" was in the email
    # for months with the method printed nowhere; the drink's card says what goes in
    # the cup and the syrup's says how the jar gets filled.
    drinks = []
    for c in plan.get("coffee") or []:
        d = dict(c["drink"], _syrup=(c["syrup"], c["syrup_needed"][0]),
                 _crumble=(c["crumble"], c["crumble_needed"][0]))
        drinks.append(("Coffee", d))
    box = [(str(t.get("kind", "syrup")).capitalize(), t) for t in (plan.get("to_make") or [])]
    return [g for g in (meals, drinks, box) if g]


def sheet_count(plan):
    """Sheets the cards come to: each group padded to whole sheets, two cards a sheet."""
    return sum(-(-len(g) // 2) for g in card_groups(plan))



# ---------------------------------------------------------------- the phone list

LIST_CSS = """
:root { color-scheme: light dark;
  --page:#eef1e6; --card:#fff; --line:#d8dec9; --ink:#262b1d; --mute:#6c7458;
  --brand:#55760f; --done:#8a9178; }
@media (prefers-color-scheme: dark) { :root {
  --page:#11150d; --card:#1c2118; --line:#39432a; --ink:#e7ecd6; --mute:#9aa77d;
  --brand:#c6de5a; --done:#6b7758; } }
* { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
body { margin:0; background:var(--page); color:var(--ink); font:16px/1.4 -apple-system,
       BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; padding-bottom:80px; }
header { position:sticky; top:0; z-index:5; background:var(--card);
         border-bottom:2px solid var(--brand); padding:12px 16px; }
h1 { margin:0; font-size:17px; color:var(--brand); }
.sub { font-size:12px; color:var(--mute); margin-top:2px; }
.bar { height:6px; background:var(--line); border-radius:3px; margin-top:9px; overflow:hidden; }
.fill { height:100%; background:var(--brand); width:0%; transition:width .2s; }
section { margin:14px 10px; background:var(--card); border:1px solid var(--line);
          border-radius:12px; overflow:hidden; }
h2 { margin:0; padding:12px 15px 3px; font-size:15px; color:var(--brand); }
.when { padding:0 15px 9px; font-size:11.5px; color:var(--mute); }
/* 48px minimum touch target - this gets used one-handed, in an aisle, holding a bag. */
label { display:flex; align-items:flex-start; gap:12px; padding:13px 15px; min-height:48px;
        border-top:1px solid var(--line); cursor:pointer; user-select:none; }
input { appearance:none; -webkit-appearance:none; flex:0 0 22px; width:22px; height:22px;
        margin-top:1px; border:2px solid var(--done); border-radius:6px; background:transparent;
        position:relative; }
input:checked { background:var(--brand); border-color:var(--brand); }
input:checked::after { content:""; position:absolute; left:6px; top:2px; width:5px; height:10px;
        border:solid var(--card); border-width:0 2.5px 2.5px 0; transform:rotate(45deg); }
.t { flex:1; font-size:15.5px; }
.t b { font-weight:700; }
.fb { display:block; font-size:12px; color:var(--mute); margin-top:2px; }
label.done .t { text-decoration:line-through; color:var(--done); }
footer { position:fixed; bottom:0; left:0; right:0; background:var(--card);
         border-top:1px solid var(--line); padding:10px 16px calc(10px + env(safe-area-inset-bottom));
         display:flex; justify-content:space-between; align-items:center; }
button { font:600 14px inherit; color:var(--brand); background:transparent;
         border:1.5px solid var(--line); border-radius:9px; padding:9px 14px; }
.count { font-size:13px; color:var(--mute); }
.note { margin:14px 12px; font-size:12px; color:var(--mute); line-height:1.55; }
"""


def render_list(plan):
    """
    The phone shopping list, attached to the email.

    Opened once, in a store, then thrown away — so there is no saved state, no hosting and
    nothing to sign into. Just big checkboxes, a live counter so you can see how much is
    left, and store sections in visit order.
    """
    ws = plan["week_start"]
    span = f'{ws.strftime("%b %-d")} – {plan["week_end"].strftime("%b %-d")}'

    total, sections = 0, ""
    for grp in plan["shopping"]:
        if not grp["lines"]:
            continue
        rows = ""
        for line in grp["lines"]:
            total += 1
            qty = L.fmt_qty(line["qty"])
            unit = L.fmt_unit(line["unit"], line["qty"]) if line["unit"] else ""
            amount = " ".join(x for x in (qty, unit) if x)
            name = L.fmt_name(line["name"], line["qty"], line["unit"])
            fb = (f'<span class="fb">or {E(line["fallbacks"][0])}</span>'
                  if line["fallbacks"] else "")
            rows += (f'<label><input type="checkbox">'
                     f'<span class="t"><b>{E(amount)}</b> {E(name)}{fb}</span></label>')
        sections += (f'<section><h2>{E(grp["label"])}</h2>'
                     f'<div class="when">{E(grp["sub"])}</div>{rows}</section>')

    make = plan["to_make"]
    make_note = (f'Worth making this week: {E(", ".join(m["title"] for m in make))}. '
                 f'Everything else in the syrup and crumble box is still good.'
                 if make else 'The syrup and crumble box is stocked — nothing to make.')

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#eef1e6">
<title>Mealbit list — {E(span)}</title><style>{LIST_CSS}</style></head><body>
<header>
  <h1>Shopping — {E(span)}</h1>
  <div class="sub">Market first (closes 2pm), then Trader Joe&rsquo;s, then QFC</div>
  <div class="bar"><div class="fill" id="fill"></div></div>
</header>
{sections}
<p class="note">{make_note}</p>
<footer><span class="count" id="count">0 of {total}</span>
<span class="count">tap to check off</span></footer>
<script>
(function () {{
  var boxes = Array.prototype.slice.call(document.querySelectorAll("input[type=checkbox]"));
  function paint() {{
    var n = 0;
    boxes.forEach(function (b) {{
      b.parentNode.classList.toggle("done", b.checked);
      if (b.checked) n++;
    }});
    document.getElementById("count").textContent = n + " of " + boxes.length;
    document.getElementById("fill").style.width =
      (boxes.length ? (n / boxes.length * 100) : 0) + "%";
  }}
  boxes.forEach(function (b) {{ b.addEventListener("change", paint); }});
  paint();
}})();
</script></body></html>"""
