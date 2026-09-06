# Mealbit — guide for Claude

A weekly meal-plan + Coffee Ritual newsletter for one household, sent on the day and hour
in `config/household.yml`. Read `README.md` for what it does; this file is about how to
work on it safely.

## Start here — every session, before anything else

```bash
python tools/setup_status.py
```

- **"TEMPLATE"** — this is the upstream itself, where the product is developed. No
  household lives here and nothing is onboarded. Keep it in starter state (rule 17);
  never write a real name, a schedule, a verdict or a week of history into it.
- **"NOT SET UP"** — this is a fresh fork. Your **first reply** is the setup survey in
  `.claude/skills/mealbit-onboarding/SKILL.md`. Not a summary of the repository, not a
  menu of things you could do: the survey. The person forked a meal-planning newsletter
  and wants it to start.
- **"Set up"** — carry on with whatever they asked. Preference changes go through
  `.claude/skills/mealbit-preferences`, sends through `.claude/skills/mealbit-send`,
  anything about a specific dish — a swap, a verdict, a new recipe, the monthly refresh —
  through `.claude/skills/mealbit-recipes`. Also run `python -m mealbit.audit
  --fail-on-gaps`; if it exits non-zero, say in **one line** that the coming season is
  short of recipes and you can write them, then do what they asked.

**The person you're talking to will not edit files.** Assume they are not a programmer.
You ask, they answer, you write the config, you run the checks, you say what you did in
plain words. Every technical step is yours; every decision is theirs. When something has to
happen in *their* browser — a Gmail app password, a GitHub secret — walk them through it
one sentence at a time (`.claude/skills/mealbit-secrets`), and never ask them to paste a
secret into the chat.

**Never commit personal information.** First names are the one exception. No surnames,
email addresses, phone numbers, home or work addresses, employers. Addresses that the
send needs live in repository secrets, never in a file. A test scans every committed file
and fails the build; the upstream repository is public and a fork may be too.

## The skills

| Skill | Use it when |
|---|---|
| `mealbit-onboarding` | `setup_status.py` says NOT SET UP. The survey, writing the two config files, recording `config/onboarded.yml` |
| `mealbit-secrets` | Gmail app password and the four repository secrets, in their browser |
| `mealbit-send` | rendering, test sends to the person alone, the real send, reading a failed run |
| `mealbit-preferences` | changing anything about how the week is planned, after setup |
| `mealbit-recipes` | a specific dish: "not that one this week", "we loved / hated it", "add a katsu", the monthly seasonal-refresh issue |

Every rule below exists because a real printed card or a real email came back wrong. The
quotes are from the household this was built for, kept because the reasoning is the point.

## How to work here

- **Plain English. Define acronyms. No corporate jargon.**
- **Show the math and the source data.** Assertions without evidence get challenged,
  correctly. If a number can't be sourced, say so instead of estimating quietly — the
  shopping list is deliberately unpriced for exactly this reason.
- **Render before shipping.** Screenshot at 412px in light *and* dark
  (`python tools/screenshot.py`) and look at it before sending anything. Render the cards
  too: what doesn't fit an 8.5in card vanishes *silently*.
- **Never let an untested design reach a real inbox.** `--send --test` goes to
  `send.test_to` alone, and config validation refuses a file where that equals `send.to`.
- **Give a strong recommendation with the reasoning shown, not a menu of options.**
- **Nothing household-specific goes in code or prose.** Names, addresses, shops and
  equipment live in `config/`. If you find yourself typing a name into `mealbit/`, stop.

## Where the household lives

| File | Holds |
|---|---|
| `config/household.yml` | who eats (two names), what they won't eat, per-plate items, how many dinners and what lunch means (`meals:`), where it's sent and when, the coffee counter |
| repository secrets | `GMAIL_APP_PASSWORD` and the three real addresses `MEALBIT_SEND_FROM / _TO / _TEST_TO`; the file carries placeholders |
| `config/stores.yml` | shops in visit order, what each `takes:`, which one is the catch-all, which is a farmers market and what model it uses |
| `data/markets/` | the market availability model (shared across a region) and one file of stall tips per market |

`mealbit/config.py` reads both config files and fails loudly. `library.load_household()`
returns the flat dict the planner has always consumed. Never read `config/` from anywhere
else.

## The rules that are load-bearing

Break these and the newsletter stops doing its job, even if it still renders:

1. **The shopping list is grouped by store, in visit order — never by recipe.** It also
   has to be a *believable amount of food.* `data/portions.md` holds both halves of that:
   per-serving ceilings (boneless meat 1½ lb for four, not 2; ground meat 1 lb; beans 2
   cans; cherry tomatoes 1 pint) and a `one_is_enough` list of things where the
   consolidator takes the **largest single requirement instead of the sum** — herbs,
   lettuce heads, jars that keep. Three recipes each wanting "1 bunch cilantro" want one
   bunch. An ingredient appears at only one store. All enforced by tests.

2. **Recipes say what an ingredient *is*; the household says who sells it.** Every
   ingredient line ends in a kind tag — `[produce]`, `[protein]`, `[dairy]`, `[bakery]`,
   `[pantry]`, `[specialty]`, `[wine]` — and never names a shop. `planner.route_to_stores`
   sends it to the first store in `stores.yml` whose `takes:` covers the kind. Exactly one
   store takes `everything`, validated, so nothing falls off the list. Before this, three
   fixed fields filed 358 lines under three named shops, and adding a fourth meant
   re-filing all of them. A test requires every line to carry a known kind.

3. **Seasonality selects the meals, not the reverse.** Start from
   `data/seasonal-pnw.md`, then pick recipes that fit.

4. **A farmers market is not a shop.** A `farmers_market` store is checked against its
   `availability:` model for the month — a lemon can't come from a Washington growers'
   market, a pepper can't in February — and the ingredient moves to the next store with
   the reason printed in the email, because the only way the model improves is a person
   correcting it after a market run. Every `[produce]` line also carries a `|| fallback`
   for the stall that's out. Exemptions live in the availability file. Enforced by tests.

5. **Dinners are cooked to serve 4** — 2 at the table, 2 as next-day lunches. That ratio
   is how the lunch column gets paid for. `serves >= leftovers + 2` is enforced.
   **But only if the dish is still good as a lunch.** Every dinner declares
   `leftover_quality: good | fair | none`:
   - `good` — the box is complete as packed. Eats cold, at room temperature, or after a
     plain microwave. A condiment jar or a splash of water does **not** demote it.
   - `fair` — genuinely worse without one specific intervention: a re-crisp, a component
     kept apart so it doesn't go soggy, an unpack-and-rebuild.
   - `none` — don't pack it. It degrades past being a lunch you're glad to open, or
     reviving it means *cooking*. Forces `leftovers: 0` and a plan that starts "don't pack
     this one".

   **The two errors are not symmetric.** A wrong `none` costs two lunch slots. A wrong
   `good`/`fair` prints a lunch in the ledger that does not exist — so lean toward `none`
   when it's genuinely close, but don't reach for it out of caution: carbonara and a farro
   skillet were both marked `none` on a straw man (frying a carbonara cake) when both pack
   fine cool with a spoon of oil. A `good`/`fair` plan may **not** send you to the stove
   for *new food* ("cook two extra portions", "fry a fresh egg") — that is `none` advice,
   and a test rejects it. At most **one** non-packing dinner a week.

6. **Three of the four dinners are built on a protein.** The fourth is free — that is
   where a dal or brothy beans goes. Where the line sits was the household's call and it
   moves the outcome a long way: over 52 simulated weeks, counting legumes made the rule
   true 52/52 and enforced nothing, counting only meat left 17/52 short. The middle line —
   **meat, fish, tofu and eggs count; legumes, mushroom and cheese do not** — lives in
   `data/protein.md`, and every dinner's `protein:` tag has to appear there. In practice
   it costs nothing: the same compromises over 52 weeks with the rule as without.

7. **Four dinners, not seven**, cooked **Mon–Thu** by default. `meals.dinners_per_week`
   (2–5, Monday onward) and `meals.lunch_mode` (`leftovers` / `fresh` / `none`) are the
   household's call, via `planner.meal_settings()`. In `fresh` and `none` the recipe still
   serves 4, the list buys for the table and the card says "halve it"; the "three of four
   built on a protein" rule generalises to "all but one". The week runs Mon–Sun; shopping
   and batch prep land on the Sunday before. Remaining dinners are deliberately unplanned.

8. **Assembly lunches are ≤5 minutes.** If it needs a pan and a timer it's `sunday-prep`.

9. **A Sunday batch is only served Mon–Fri** (`PREP_LASTS_DAYS`). By the weekend it is a
   week old. The weekend runs on assembly lunches. Enforced by a test.

10. **Only a real send writes `data/history.json`.** A `--test` that recorded history
    would burn the week's recipes and the household would get a different plan than the
    one reviewed.

11. **A per-plate ingredient may never be load-bearing.** `diet.per_plate` names the
    things one eater skips. Those are *per-plate*, not exclusions: the recipe stays, the
    ingredient goes on the other plate at the end, and **the dish has to be complete
    without it**. A recipe that buys one must declare `per_plate: [x]` plus a `**Per
    plate:**` paragraph, or `per_plate_exempt: [x]` with a reason (cooked down, roasted —
    not raw). Enforced by a test; nothing is inferred from prose. This was documented from
    day one and enforced nowhere, which is how a panzanella shipped with raw tomato juice
    *as the dressing*. The email and the card name the person: "not on Sam's plate".

12. **Three attachments, three formats, and only one of them is HTML.** The shopping list
    is HTML because its checkboxes get tapped in the aisle. The recipe cards are a **PDF**
    — landscape letter, **two recipes per sheet**, cut down the middle. Every cooked dinner,
    **every lunch, both coffee drinks and anything the box needs made** gets one, so a
    normal week is 11–13 cards on 6–7 sheets. A card is a fixed 8.5in with
    `overflow:hidden`; `test_cards_fit_their_sheet` renders several draws and measures.
    The **photo** is the flexible element and absorbs the slack. Coffee files use the same
    `ingredients:` kind tags as recipes; they once carried fixed store fields instead, the
    router read nothing from them, and **no coffee line reached the list for weeks**.

13. **Four things are assumed to be in the house, and nothing else:** salt, black pepper,
    olive oil, white vinegar. That is the whole of `data/pantry.md`. Everything else a
    recipe leans on is printed on the card *and* reaches the shopping list in a **"Check
    the cupboard"** group that sits **first**, because it is the one group acted on at
    home. There used to be a second tier of "rotation aromatics" assumed present; the
    household killed it — a lemon silently missing from the list is a dish missing its
    acid at 6pm. The shopper decides at shop time; the system never decides for them.

14. **Cottage cheese goes sweet.** Berries and maple, or nut butter and preserve — never
    chili crisp, furikake or cucumber. The rejected recipe scored well on every number the
    library tracks (5 minutes, no cooking, 30g protein), which is exactly why it needed a
    test rather than a note: a refresh optimising for those would write it straight back.

15. **A request is a file, a verdict is a rating, and neither is a diet rule.** "Not the
    pulled pork this week" is `data/this-week.yml` — skips and pins for **one** named
    Monday, written by `tools/this_week.py`, read by the planner, **cleared by the real
    send** and committed by the workflow. "Never again" is `rating:` on the recipe, written
    by `tools/verdict.py`; **1–2 retires the dish** until re-rated, 3+ stays, `null` is no
    opinion, and `feedback:` keeps every verdict in their words. The scheduled send takes
    no arguments, so the file is the only way a Tuesday request reaches Saturday. A slug
    that matches nothing fails the run — silently planning the dish someone asked to skip
    is the one thing the file exists to prevent. **The upstream library ships with no
    verdicts**; a fork's ratings are its own (`verdict.py --reset-all` on a fresh fork).

16. **Untried before repeated.** The picker puts recipes never in `history.json` first.
    It used to key on a `last_served` field on the recipe that nothing wrote, so it did
    nothing; history is the one record of what was served and the only thing consulted.

17. **The template carries nothing that is anyone's.** The upstream ships with placeholder
    names, no `config/onboarded.yml`, an empty `history.json`, a clear `this-week.yml`, no
    verdicts, and **no cron in either workflow** — it must never send from itself, and a
    scheduled run on a public repository with placeholder config is a red run every
    Saturday. `python tools/schedule.py --write` adds the schedule for the household's own
    timezone during onboarding; `--remove` puts the template back. A test holds all of
    this on the upstream and is a no-op on a copy.

## The email HTML has hard constraints

`mealbit/email_kit.py` encodes fixes that took real iterations:

- **Light-first, with dark applied by class.** Gmail ignores `prefers-color-scheme` and
  auto-adapts a light design — that's why light is the base.
- **Bars need `bgcolor` and `height` as HTML *attributes*, and percentage widths.** A px
  width inside a %-width cell gets crushed on mobile Gmail. A test guards it.
- **`MIMEText(..., "utf-8")`** is what keeps emoji and ✓ alive.
- Tables only. No flexbox, no grid, no external CSS.
- **Keep it short.** It is a reference, not an essay: image, title, time, one sentence.
  The shopping list lives in the attachment and must not be duplicated in the body.

## Before you commit

```bash
python tests/test_mealbit.py     # 80 tests, including a 52-week rotation simulation
python -m mealbit.meal_plan      # renders out/meal_plan.html + out/cards.pdf
python tools/screenshot.py       # 412px light + dark
```

The test suite is the guard on hand-edited data. A malformed recipe file should fail
there, not in the inbox — which is why CI runs it before the send step.

## Planner behaviour worth knowing

Selection degrades rather than failing, and reports every compromise in the email's
"how this week was picked" footnote. The priority order is deliberate:

**Within-week variety > rotation > season fidelity.** Serving chicken twice in one week is
the specific complaint that kills meal plans, so the picker exhausts the whole
cooldown/season ladder at full strictness before it concedes a single variety rule.

Cooldowns in `planner.py` are **targets sized to what the library can sustain**, not
guarantees — a seasonal pool is ~12 recipes and 4 are used per week. If you add a lot of
recipes, raise them.

## Keeping the library from going stale

`python -m mealbit.audit` measures **seasonal depth** — the thing that actually decays. A
season bucket lasts ~9 weeks and holds 10–14 dinners, so the plan starts repeating around
week four. `.github/workflows/seasonal-refresh.yml` runs it monthly and opens an issue
naming the gaps. **It does not write recipes, and it shouldn't** — see "Don't". Writing
them is a session's job, with the person, through `.claude/skills/mealbit-recipes`: write
the recipes the issue asks for, render the coming month, show them, commit, close the
issue. Recipes written on request in a session are the library growing; recipes generated
at send time are the thing this project exists to replace.

## Photos come from two places, in a strict order

| | What it is | On the card |
|---|---|---|
| `image_url` | the photo from a **verified published recipe** | photo + the QR opens that recipe |
| `photo_url` | Pexels stock photography of the same dish | photo + a credit line; the QR falls back to an image search |

The household, on the printed lunch cards: *"the lunch photos need to be higher quality
and actually the meal they represent, not bad-quality photos taken by home chefs."*

A third tier, Openverse, was retired: reviewed by eye, 13 of 18 were poor, wrong, or
both, because it indexes openly-licensed images of *anything* and nothing in the metadata
separates a bag of wild rice from a composed food photograph. Pexels
(`tools/stock_photos.py`, `PEXELS_API_KEY`) fixes quality, not accuracy — its top result
was "loaded fries" for pulled pork grits and miso *soup* for a soba bowl. So **a person
must have looked**: `test_every_recipe_has_a_photo` requires `photo_pinned` on every
borrowed photo. `--sheet <slug>` renders candidates; `tools/pin_photo.py` records the
choice. A recipe may declare `photo_pending: true` — no photo on purpose — capped at 4 so
it stays a queue.

**A representative photo must never become the recipe behind the QR.**

**The recipe matcher has been wrong five times** (`tools/find_sources.py`). Site search is
loose, so the URL slug must carry the dish's identity: **FORMS** (wrap, bowl, soup) must
agree, taken as the *last* form noun because English puts the filling before the
container; **NAMES** (katsu, hummus) must be present; index pages are rejected. What no
URL rule can see — the right dish with the wrong main ingredient — goes in
`data/rejected-sources.md`, per recipe. No two recipes may share a source. Every link is
verified live before it is written.

**Photos are carried inline as `cid:` parts, never hotlinked.** Remote images did not
render in Gmail even when reachable. `cid:` only resolves inside `multipart/related`, so
`send_email` builds `mixed(related(alternative(html), images), attachments)`.

## Coffee: a drink's syrup is the drink's own

A reader: *"why does the recipe card title one flavor syrup but then list an unrelated
one? Miso Caramel Latte says to use Rosemary honey syrup. makes no sense."*

The syrup had been matched on **temperature**. And every drink already makes its own
flavouring inline, so there was never a slot to fill. Now **`syrup:` is declared in the
drink's frontmatter, never chosen** — a box syrup where the box holds that exact thing,
or `syrup: null`. The **crumble stays a free variable**, from the drink's own `crumbles:`
shortlist, skipping one the other drink took. `audit.py` reports orphan syrups.

Each drink gets a card (the cup, plus the syrup method most drinks make inline), and so
does every syrup or crumble the box needs made this week, with `makes`, `keeps_weeks` and
`storage` on it. The email's "Make this week" line points at those cards.

## Dinners that arrive already shopped for

`--box N` marks the first N cooking nights as meals already in the house — a meal kit, a
freezer stash. They hold their night and feed the lunch ledger but contribute **nothing**
to the shopping list and get **no card**. `--box-leftovers` is what they actually yield: a
two-person kit leaves about **one** serving, not two. Placeholder slugs never reach
`history.json`.

## Don't

- Don't generate recipes at send time. The library is the product; it compounds and it's
  auditable. If the model is unavailable, last week's plan still works.
- Don't add per-item grocery prices without a real source. Invented precision is worse
  than an honest blank.
- Don't send to `send.to` without being asked. `--test` goes to `send.test_to`; a test
  asserts the two differ.
- **Don't put an unverified URL behind a printed QR code.** Search results are not
  verification. Until a recipe carries a checked `source_url`, the QR falls back to an
  image search, which cannot 404 and cannot be misattributed.
- Don't put a name, an address or a shop into `mealbit/`, `tests/` or `data/recipes/`.
  That's what `config/` is for, and a fork that has to edit code can't take upstream fixes.
- Don't reintroduce hosting for the shopping list. It is an email attachment, opened once
  and thrown away.
