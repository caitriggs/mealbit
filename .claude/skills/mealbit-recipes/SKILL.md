---
name: mealbit-recipes
description: Change what is on the menu for a Mealbit household — swap a dish out of this week ("not the pulled pork"), add a dish they name, record what they thought of one ("we loved it", "never again"), and work the monthly seasonal-refresh issue by writing new recipes. Covers the whole recipe contract (frontmatter, ingredient kinds, leftover quality, per-plate, protein tag, photo and source), so a new file passes the tests first time. Use for any request about a specific dish, a dislike, a craving, a rating, or "the plan keeps repeating".
---

# Changing the menu

They will not edit a file. They say what they want in plain words; you find the dish, write
or change the file, run the tests, render, show them, commit. Every path below ends the
same way: **tests, render, look, commit, offer a test send.**

Four requests come here. Work out which one it is first.

| They say | It is | Go to |
|---|---|---|
| "not the pulled pork this week", "can we skip Thursday's" | a one-week request | **Swap** |
| "I want the katsu this week", "put the dal back on" | a one-week request | **Swap** (pin) |
| "we never want X again", "X was great", "the grits were gluey" | a verdict | **Verdicts** |
| "add a chicken adobo", "I had a great thing at a restaurant", "more fish" | a new recipe | **Add a dish** |
| "the plan keeps repeating", an open "Seasonal refresh" issue | depth | **Seasonal refresh** |

## Swap: "not that one this week"

The scheduled send runs on GitHub with no arguments, so a request made on Tuesday reaches
Saturday through a **committed file**: `data/this-week.yml`. The planner reads it for the
one week it names and the real send clears it.

1. Find the slug. `python tools/this_week.py` with no arguments lists every dinner and
   lunch with its slug and title. Match what they said to a title; if two could match, ask.
2. **Library first.** Write the skip and re-render:
   ```bash
   python tools/this_week.py --skip <slug>          # the week is the Monday after today
   python -m mealbit.meal_plan                      # the plan re-picks around the gap
   ```
   The planner fills the slot from the library under every rule (season, cooldown, no
   repeated protein). Tell them, in one line, what replaced it: *"Instead of the pulled
   pork, Thursday is now the chicken katsu."* The email's footnote also says the dish was
   left out at their request, so nobody wonders.
3. **If they want something specific** ("something with fish", "the katsu"): a dish
   already in the library gets `--pin <slug>` alongside the skip. One they name that the
   library doesn't have → **Add a dish**, then pin the new slug. A pinned dinner takes its
   slot before any rule; the rest of the week is planned around it.
4. Ask once, plainly: *"Just this week, or off the menu for good?"* "For good" is a
   verdict — see below — and you do both.
5. **Commit `data/this-week.yml`** (message in their words: "skip the pulled pork this
   week"). An uncommitted file never reaches Saturday's run. Then offer a test send via
   `.claude/skills/mealbit-send` so they see the new week before it goes to the household.

Things the file refuses, on purpose: a slug that matches no recipe (a typo must fail the
run, not silently plan the dish they asked to skip), a lunch as a pin, a dish both skipped
and pinned, a retired dish as a pin, more pins than there are dinners. The tool checks the
same things before writing.

A request is for **one Monday**. Previewing another week is unaffected. After the real
send the file is cleared and committed by the workflow. A `--test` send leaves it alone.

## Verdicts: what they thought

Ratings live on the recipe itself so the library stays the product, and they are the
only signal the library has about taste. Record them whenever they volunteer one — after a
send, in passing, mid-conversation.

```bash
python tools/verdict.py <slug> --rating 5 --note "Sam wants this monthly" --who Ada
python tools/verdict.py <slug> --rating 2 --note "grits were gluey"
python tools/verdict.py <slug> --note "needs more lemon"           # a note, no rating
```

- **1–5.** Map words to numbers and say the number back: "loved it" → 5, "good" → 4,
  "fine" → 3, "meh / wouldn't again" → 2, "hated it" → 1.
- **1 or 2 retires the dish.** It is never planned again until someone re-rates it 3 or
  higher. Say so: *"That's a 2, so it's off the menu until you tell me otherwise."*
- **The note is their words**, not yours. First names are fine; nothing else personal is.
  The note is what gets built on later, so keep the specific complaint ("gluey grits") over
  a summary ("didn't like it").
- A verdict is a commit of its own: "rate the pulled pork 2 — gluey grits".

**A fresh fork starts with no verdicts.** The upstream library ships every recipe at
`rating: null`, and a test on the upstream holds that. If you are onboarding a fork and
find ratings from another household, `python tools/verdict.py --reset-all` — their
opinions are not this household's.

## Add a dish

**At setup** (from the onboarding skill's Round 4): write without a shortlist and without
discussion — they haven't seen a week yet and the point is that they never have to think
about this. Weight to their top proteins and the coming season. `photo_pending: true` is
allowed up to 12 on a copy; the Pexels key is part of the secrets step that follows, so pin the photos right after it.

You write the file; they never do. The recipe is a Markdown file with YAML frontmatter in
`data/recipes/dinners/` or `data/recipes/lunches/`, and **the tests are the contract** —
run them and the message names the rule you broke. Copy the frontmatter of the nearest
neighbour and change every field; don't start from blank.

**Before writing, check three things with them if the request left room:**
which season it belongs to (start from `data/seasonal-pnw.md` and use what is at the
market that month, never the reverse), what protein carries it, and whether it packs as a
lunch. Then write.

### The dinner contract

```yaml
---
title: Chicken katsu with cabbage slaw and tonkatsu sauce   # what it IS; forms and names matter for the photo search
kind: dinner
serves: 4                    # >= leftovers + 2, always; the household eats 2, the rest is lunch
leftovers: 2                 # 0 if leftover_quality is none
leftover_quality: good       # good = packs as-is | fair = one small step | none = don't pack it
active_time: 35              # hands-on minutes, <= 45
total_time: 45
seasons: [late-fall, deep-winter]     # buckets from data/seasonal-pnw.md; usually two
protein: chicken             # MUST appear in data/protein.md (anchor or light)
cuisine: japanese            # the week never repeats a cuisine
effort: easy                 # easy | medium | project (multi-hour; at most one a week)
register: comfort            # comfort | elegant; a week needs two comfort
tags: [crispy, weeknight]
ingredients:
  - 1 head green cabbage || napa cabbage [produce]         # EVERY produce line has a || fallback
  - 1½ lb boneless chicken thighs [protein]                # ceilings in data/portions.md
  - 1 bag panko [pantry]
  - 1 bottle tonkatsu sauce || Worcestershire + ketchup [specialty]
pantry: [flour, eggs, neutral oil, rice vinegar, sugar, soy sauce, kosher salt]   # everything beyond salt, pepper, olive oil, white vinegar
per_plate: []                # cilantro / raw tomatoes / arugula if bought; then a **Per plate:** paragraph
photo_pending: true          # until a photo is pinned — see Photos
rating: null
---
```

Every ingredient line ends in one kind tag — `[produce] [protein] [dairy] [bakery]
[pantry] [specialty] [wine]` — and **never names a shop**; `config/stores.yml` decides
that. Quantities are for four and believable: `data/portions.md` caps them (boneless meat
1½ lb, ground 1 lb, beans 2 cans, cherry tomatoes 1 pint) and lists what is bought once
for the week (herbs, a head of lettuce, jars). A per-plate ingredient (`diet.per_plate` in
`household.yml`) is never load-bearing: declare `per_plate: [x]` and say in a `**Per
plate:**` paragraph how the dish is complete without it, or `per_plate_exempt: [x]` with a
reason (cooked down, roasted — not raw). Nothing is inferred from prose.

### The body

Four bold-led paragraphs, then numbered steps, in this order. The email prints the first
sentence of *Why this week*; the card prints all of it.

```markdown
**Why this week:** one sentence on why this dish, this month.

**The move:** the one or two techniques that make it work, in a paragraph.

1. Numbered steps, each a real instruction with quantities, heat and time.
2. ...

**Leftover plan:** how to pack it and what it is like on day two. For `fair`, the one
step. For `none`, the paragraph STARTS with "don't pack this one" and says why. A good/fair
plan may not send anyone to the stove for new food — "fry a fresh egg" is `none` advice.

**Per plate:** (only if per_plate is set) how the dish is complete without it and where it
goes on the other plate.
```

`leftover_quality` is a judgement and the two errors are not symmetric: a wrong `none`
costs two lunch slots; a wrong `good` prints a lunch that doesn't exist. Lean `none` only
when it is genuinely close. Carbonara and a farro skillet pack fine cool with a spoon of
oil; a panzanella does not.

### The lunch contract

Same shape with `kind: lunch`, `lunch_style: sunday-prep | assembly`, `makes:` and
`serves:` (portions the batch yields), no `leftovers`. An **assembly** lunch is five minutes
and no pan; if it needs a timer it is `sunday-prep`. A Sunday batch is served Mon–Fri only.
Cottage cheese goes sweet — berries and maple, nut butter and preserve — never savoury; a
test holds that because the savoury version scored well on every number and was awful.

### Coffee: drinks, syrups, crumbles

`data/coffee/drinks|syrups|crumbles/` use the same `ingredients:` lines with `[kind]`
tags, and the same `pantry:` for what the cupboard should hold. A drink names the box
syrup it *is* (`syrup: <slug>` or `null`) and a `crumbles:` shortlist, best first. Syrups
and crumbles carry `makes`, `keeps_weeks`, `storage`, `active_time`. Each drink and each
thing the box needs made gets a printed card, so the body has to be a method: an intro
paragraph, then bold-led paragraphs (`**Build:**`, `**The move:**`) that go on the card
in order.

### Photos and the source link

Every card carries a photo **a person has looked at**, and a QR code — dinners, lunches
and coffee drinks alike (syrups and crumbles print without one). Two tiers, in order:

1. **A verified published recipe** — the real dish, its photo, and the QR opens it.
   ```bash
   python tools/find_sources.py --only <slug>
   ```
   It searches, checks the URL slug carries the dish's identity (form and name), verifies
   the page live, and writes `source_url` and `image_url`. It has been wrong before — the
   right dish with the wrong main ingredient. **Open the link and look.** If it is wrong,
   add the URL under the recipe's heading in `data/rejected-sources.md` and run it again.
   No two recipes may share a source.
2. **Stock photography of the same dish**, when no trustworthy recipe turns up. Needs
   `PEXELS_API_KEY` in the environment (a free key; `.claude/skills/mealbit-secrets`).
   ```bash
   python tools/stock_photos.py --sheet <slug>          # renders a numbered contact sheet into out/
   python tools/pin_photo.py <slug> "<image-url>" "<Photographer / Pexels>" "<pexels page>"
   ```
   Look at the sheet. Pick the one that is **this dish**, composed and lit — the top result
   was "loaded fries" for pulled pork grits once. Pinning records that a person chose it.
3. **No key, or nothing right:** leave `photo_pending: true`. The card prints without a
   photo and the QR falls back to an image search. At most four recipes may be pending; if
   that is full, get a key or find a source before adding a fifth.

Then `python tools/cache_images.py` so the photo travels inside the email. Never hotlink;
never put an unverified URL behind a QR; a stock photo never becomes the recipe link.

### Finish

```bash
python tests/test_mealbit.py            # the contract; fix what it names
python -m mealbit.meal_plan --today <a date in that season>
python tools/screenshot.py              # look at the email, light and dark
```

Open `out/cards.pdf` too — a card is a fixed sheet with `overflow:hidden`, and text that
doesn't fit vanishes silently. Commit as "add chicken katsu (late fall, chicken)". If they
want it *this* week, pin it (**Swap**, step 3).

## Seasonal refresh

Selection is seasonal on its own. **Depth** is what decays: a season bucket runs about nine
weeks and holds 10–14 dinners, so the plan repeats from week four. On the 25th of each
month `.github/workflows/seasonal-refresh.yml` opens an issue titled *Seasonal refresh —
<Month>* saying exactly what the coming month is short of. It writes nothing; that is your
job, in a session, with the person.

**Mention it once.** If `python -m mealbit.audit --fail-on-gaps` exits non-zero at the
start of a session, say in one line that the coming season is short and you can write the
recipes, then carry on with whatever they asked. Don't lead with it and don't repeat it.

**When they say go**, write first, show after — that is how this household wanted it:

1. `python -m mealbit.audit --issue` is the brief (or read the open issue with the GitHub
   tools if you have them). It names the count, the proteins that are thin, the register
   to lean, and what is at the market that month.
2. Write that many recipes under **Add a dish**, each a different protein and cuisine
   from each other and from what the season already holds. Sources and photos for each.
   Prefer dishes that pack well: the lunch column is half leftovers.
3. Render the coming month and look: `python -m mealbit.meal_plan --today <the 1st of
   that month>`, then `python tools/screenshot.py`, then `python -m mealbit.audit`
   again — the gap should be gone.
4. Show them the titles with one line each and the rendered email. Anything they don't
   want, delete the file; the library only holds dishes someone wanted.
5. Commit ("seasonal refresh: four late-fall dinners"), and close the issue with a
   comment listing what was added (if you have the GitHub tools; otherwise tell them it can
   be closed).

## What never goes in a recipe

A shop name, a person's surname, an address, a price. A URL nobody opened. A photo nobody
looked at. Generated prose that reads like a recipe but was never checked against the
rules above — the tests catch the shape, not the sense, so read what you wrote.
