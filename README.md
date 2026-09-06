# Mealbit

A weekly meal-plan and Coffee Ritual newsletter for one household, planned from a
recipe library you can read and edit, shopped from the stores *you* visit, and sent on
the day and hour you choose.

## Want one for your household?

**Press "Use this template" above, make the new repository private, open it in
[Claude Code](https://claude.ai/code), and say hello.** Claude notices it's a fresh copy
and opens with a short survey — who eats, what they won't eat, where you shop, how many
dinners, what lunch means to you — then writes the configuration, schedules the weekly
send for your timezone, walks you through the two things only you can do in your browser
(a Gmail app password and four repository secrets), and sends you a test. You never edit
a file. About twenty minutes, most of it Google.

A fork works too, but GitHub won't let a fork of a public repository be made private, and
your household's diet is yours.

Prefer to do it by hand? [SETUP.md](SETUP.md).

---

## The job this does

Meal-kit subscriptions sell a service, and the service was never really the food. It was
*not having to decide what to cook, and not having to figure out what to buy*. Cancel one
and that cognitive load comes straight back, and quietly pushes a household toward
restaurants if nothing replaces it.

So the success test is not "was the email nice." It is:

> **On shopping day, can two people walk out the door and shop without thinking, and
> cook that week without deciding anything?**

If the newsletter needs a planning session to act on, it has failed.

The second job is the **Coffee Ritual**: for a lot of households the coffee-shop line is
the largest food-and-drink expense after restaurants. One properly-made drink a week,
taught properly, is a bigger lever than anything on the grocery list.

---

## What lands in the inbox each week

| Section | What it does |
|---|---|
| **Dinners** | Four by default (**Mon–Thu**), two to five if you like; the rest of the week is yours. Up to 45 min hands-on. Each cooked to serve 4 — two at the table, two for tomorrow's lunches — or for the table only, if that's how you eat. |
| **The lunch ledger** | **Every day** × 2 people = 14 lunch slots, every one filled and named, plus a 5-minute swap per day. Leftovers, batch lunches, or none at all — your choice. Nobody does arithmetic at 7am. |
| **The shopping list** | Grouped **by store, in visit order** — your stores, from `config/stores.yml`. Quantities summed across every meal. A **Check the cupboard** group leads, holding everything a recipe leans on beyond the four staples (salt, pepper, olive oil, white vinegar). Market lines carry fallbacks. |
| **At the market** | What's actually in season this month, if you shop a farmers market. |
| **Worth doing Sunday** | The one block of prep that makes Wednesday easy. |
| **The Coffee Ritual** | One coffee-shop-grade drink with real technique, the cost math against buying it, and a quote — interesting, fun or weird — about making rather than buying. |

Three attachments: the shopping list as HTML (its checkboxes get tapped in the aisle), the
recipe cards as a PDF (landscape letter, two per sheet, cut down the middle — every
dinner, every lunch, both coffee drinks and whatever the syrup box needs made), and every
dish photo carried inline so nothing depends on a remote fetch.

---

## The design decisions that matter

**The shopping list is grouped by store, never by recipe.** People shop a store once, not
a recipe once. A recipe-grouped list forces the shopper to re-sort in the aisle.

**Recipes don't know your stores.** Every ingredient is tagged with what it *is* —
`[produce]`, `[protein]`, `[dairy]`, `[pantry]`… — and `config/stores.yml` says who sells
it. Adding a shop, dropping one, or moving to a different farmers market is a config
change, not a recipe change.

**Seasonality picks the meals, not the reverse.** A generic planner picks recipes and then
sends you hunting for February tomatoes. This starts from what a Western Washington market
actually has this month (`data/seasonal-pnw.md`) and picks meals that use it.

**A farmers market is not a shop.** Market lines are cross-referenced against what a
growers-only market can credibly supply this month; anything it can't is moved to the next
store and the newsletter prints why — because the only way that model improves is a person
correcting it after a market run. Every market line also carries a `|| fallback` for the
stall that's out.

**Four dinners, not seven.** Seven is the classic meal-planner mistake: it ignores
leftovers, one night out, and the fact that plans slip. Dinners are cooked Mon–Thu so the
weekend is genuinely free.

**Leftovers are a judgement, not a default.** Every dinner declares whether it's still
good as a lunch. Soggy bread salad isn't. At most one non-packing dinner a week, because
each one costs two lunch slots.

**Three of four dinners are built on a protein.** Meat, fish, tofu or eggs; the fourth
night is free for a dal or brothy beans.

**A curated library, not an LLM improvising weekly.** Recipes are files. They compound —
meals people liked stay and come back. They're reviewable — you can read and edit a recipe
file; you cannot audit a prompt. Rotation is tractable. And if anything upstream breaks,
last week's plan still works.

**The list is not priced.** There is no price feed behind it. Inventing grocery prices
would be worse than omitting them.

---

## Running it

```bash
pip install -r requirements.txt

python -m mealbit.meal_plan                      # render to out/meal_plan.html
python -m mealbit.meal_plan --today 2026-01-10   # preview any week (no history written)
python -m mealbit.meal_plan --send --test        # [TEST] copy to send.test_to only
python -m mealbit.meal_plan --send               # the real send; records to history.json

python -m mealbit.audit                          # is the library deep enough for the season?
python -m mealbit.audit --issue                  # the same, as a GitHub issue body

python tests/test_mealbit.py                     # 80 tests, incl. a 52-week simulation
python tools/screenshot.py                       # 412px light + dark PNGs into out/
```

## How it stays seasonal

Two separate things, and only one of them is automatic.

**Selection is seasonal on its own.** `data/seasonal-pnw.md` maps each month to one of six
season buckets, and the planner only offers recipes tagged for the current bucket. That
part needs no maintenance.

**Depth is the part that decays.** A season bucket lasts about nine weeks. At four dinners
a week that is ~36 dinner slots, and each bucket holds 10–14 recipes — so from about week
four of every season the plan starts repeating.

So `.github/workflows/seasonal-refresh.yml` runs on the **25th of each month** and opens a
GitHub issue saying exactly what the *coming* month's pool is short of. It deliberately
does **not** write recipes — a recipe file is readable, editable and auditable, and
auto-committing generated recipes nobody reviewed would give that up to save the smallest
part of the work.

Scheduled sends run from `.github/workflows/meal-plan.yml` and need the
`GMAIL_APP_PASSWORD` repo secret. **This template carries no schedule** — it must never
send from itself — and `python tools/schedule.py --write` adds one for your timezone
during onboarding. **Schedules only fire from the repository's default branch.** Always
self-test before a send that reaches anyone else.

---

## Layout

```
config/
  household.yml     who eats, what they won't eat, where it's sent, the coffee counter
  stores.yml        where they shop, in visit order, and what each shop takes
mealbit/
  config.py         reads and validates the two files above
  library.py        frontmatter/ingredient parsing, seasons, pantry, history
  planner.py        selection, variety rules, store routing, the lunch ledger
  render.py         the email (tables only; light-first, dark by class)
  printable.py      the PDF recipe cards and the HTML shopping list
  email_kit.py      Gmail SMTP + the shared palette
  audit.py          seasonal depth report
data/
  recipes/          dinners/ and lunches/, one Markdown file each
  coffee/           drinks/, syrups/, crumbles/, quotes, fundamentals, economics
  markets/          availability model (shared) and per-market stall tips
  seasonal-pnw.md   month -> season bucket -> what's at peak
  pantry.md         the four staples assumed on hand — nothing else
  portions.md       per-serving ceilings and the one-purchase-covers-the-week list
  protein.md        which protein tags count toward "three of four"
  images/           cached 320px thumbnails, carried inline in the email
  history.json      what was served, so rotation works
tools/              photo and source finders; all show candidates and make you pick
tests/              one file, 80 tests
docs/               the household model, explained
```

## Changing the menu

All of this is a sentence to Claude; none of it is a file you edit.

- **"Not the pulled pork this week"** — a one-week request. It goes in `data/this-week.yml`
  (`tools/this_week.py`), the planner fills the slot from the library, the real send
  clears it. Name a dish and it is pinned instead.
- **"We loved it" / "never again"** — a verdict, `rating:` 1–5 on the recipe itself
  (`tools/verdict.py`), with the words you used kept under `feedback:`. A 1 or 2 retires
  the dish until you re-rate it.
- **"Add a chicken adobo"** — a new recipe file, written to the contract the tests
  enforce, with a photo someone looked at and a link someone opened.
- **The monthly refresh** — an issue says what next month is short of; a session writes
  those recipes and shows you the result.

## Editing it

- **Add a dinner** — a Markdown file in `data/recipes/dinners/`. Frontmatter is validated
  by the tests; the messages name the rule you broke. `.claude/skills/mealbit-recipes`
  carries the whole contract.
- **Change who eats what** — `config/household.yml`.
- **Change where you shop** — `config/stores.yml`. Recipes never need touching.
- **Stop re-buying something** — add it to `data/pantry.md`. Be sparing: anything in there
  is a line the shopper never sees, so it had better always be in the house.
- **The market never has X** — correct `data/markets/pnw-washington-growers.md`.

## Still open

- **Household size.** Two eaters is built in, not configured. See
  `docs/household-model.md` for what four would take.
- **Farmers markets outside Western Washington** need their own availability model; the
  onboarding skill offers to write one with you.
