---
name: mealbit-onboarding
description: Set up a freshly forked Mealbit for a new household by running the setup survey, writing config/household.yml and config/stores.yml from the answers, and walking a non-technical person through the secrets and the first test send. Use this the moment `python tools/setup_status.py` says NOT SET UP, before anything else — the survey is your first message, not something you wait to be asked for.
---

# Onboarding a new household

You are talking to someone who forked this repository and opened it in Claude Code. They
are probably not a programmer. **They will not edit files.** You ask, they answer, you
write the config, you run the checks, you tell them what you did in plain words. Every
technical step is yours; every decision is theirs.

## Before the survey

Run `python tools/setup_status.py`. If it says **NOT SET UP**, your very first reply is the
survey below — do not describe the repository, do not offer options, do not ask what they'd
like to do. They forked a meal-planning newsletter; the thing they want is for it to start.

Open with two sentences: what they'll get (a weekly email with dinners, a lunch plan, a
shopping list grouped by their stores, and printable recipe cards), and that you need
about ten answers to set it up. Then ask.

## The survey

Ask in **three short rounds**, not one wall. Accept casual answers and confirm what you
heard back to them before writing anything. Never ask for anything you won't use.

### Round 1 — who eats

1. **First names of the two people eating.** First names only — that is the one personal
   detail the repository is allowed to hold. If they name three or more people, explain
   plainly: dinners are cooked to serve four, two at the table and two as tomorrow's
   lunches, and the whole plan is built on two. Offer to set it up for two of them for
   now; a bigger household is real work that hasn't been done (docs/household-model.md).
2. **Anything either of them won't eat at all.** These become `exclude_ingredients` —
   the recipe disappears entirely. Allergies and hard nos.
3. **Anything one of them skips that the other likes.** Cilantro, raw tomato, arugula,
   blue cheese. These become `per_plate`, keyed by the person who skips it — the recipe
   stays, the ingredient goes on the other plate at the end. Explain the difference in one
   line; it matters. The library already handles cilantro, raw tomatoes and arugula this
   way. Anything else they name will work as an exclusion-style check but the recipes
   haven't been written around it — say so.
4. **Which proteins they like most, in rough order.** Chicken, beef, pork, turkey, fish,
   tofu. Becomes `protein_preference`. Also ask about fish — the library caps whitefish at
   twice a month by default.

### Round 2 — the week

5. **How many dinners a week to plan, 2 to 5.** Cooked Monday onward. Default is 4
   (Mon–Thu) and the weekend stays free; say that's the default and why.
6. **What lunch means to them.** Three choices, in plain words:
   - *Leftovers* — dinners are cooked to serve four and two portions become tomorrow's
     lunches; the other lunch slots come from two batches cooked on shopping day plus
     five-minute builds. The original design; recommend it if they take lunch to work.
   - *Fresh* — dinners are cooked just for the table; every lunch is a batch or a
     five-minute build.
   - *None* — dinners only, no lunch planning.
   Becomes `lunch_mode`.
7. **Which day and hour the email should arrive, and their timezone.** Default Saturday
   5pm. The shop day is the day before the week starts (Sunday) — say so. Any timezone
   works; you write the schedule from it (below).
8. **Coffee.** Do they make coffee at home, and with what — espresso machine, Moka pot,
   AeroPress, French press, none of these? Two featured drinks a week by default; ask if
   they want fewer or none. Skip the cost line unless they volunteer a monthly coffee-shop
   spend; never invent one.

### Round 3 — where they shop

9. **Their shops, in the order they visit them on a shopping trip.** Names only. One of
   them has to be the place that has everything — usually the big supermarket — and it
   goes last.
10. **Do they shop a farmers market?** If yes: its name, the day and hours, and where it
    is (a cross-street is plenty — never a home address). If they're anywhere around the
    Puget Sound, the shipped availability model (`data/markets/pnw-washington-growers.md`)
    applies as-is. If they're somewhere else, tell them the market model is written for
    Western Washington growers and offer two honest choices: skip the market for now, or
    spend ten minutes with you writing a new one (what never grows locally, what's there
    year-round). Don't silently reuse the Washington model for Vermont.

That's everything. Do not ask about photos, syrups, recipe ratings, or anything in
`data/`. Those work out of the box.

## Writing the config

Write **`config/household.yml`** and **`config/stores.yml`** yourself from the answers.
Both files are heavily commented; keep the comments. Rules that the tests will enforce
and you should not wait for the tests to tell you:

- `household.eaters` is exactly the two first names. `per_plate` keys must be one of them.
- `send.from / to / test_to` **stay as the placeholders** in the file. The real addresses
  go into repository secrets (next section). `to` and `test_to` must differ.
- `meals.dinners_per_week` is 2–5; `meals.lunch_mode` is `leftovers`, `fresh` or `none`.
- Every store has `id`, `short` (2–3 letters for the card), `name`, `takes`. Exactly one
  store takes `everything`, and it should be last. A farmers market has
  `kind: farmers_market`, `when`, `where`, `availability`, `tips`, and `takes: [produce]`.
  For a new market, copy `data/markets/west-seattle.md` to `data/markets/<their-market>.md`,
  replace its stall notes with "nothing verified yet", and point `tips:` at it.
- Kinds a store can take: `produce protein dairy bakery pantry specialty wine` and
  `everything`. A typical supermarket takes `everything`; Trader Joe's-style stores take
  `[protein, dairy, bakery, pantry, specialty, wine]`; a market takes `[produce]`.

Then, in this order:

```bash
python tools/schedule.py --write     # the weekly and monthly cron lines for THEIR timezone
python tests/test_mealbit.py         # must pass; the messages name what's wrong
python -m mealbit.meal_plan          # renders out/meal_plan.html — open it, look at it
python tools/screenshot.py           # 412px light and dark
```

The template ships with **no schedule** — the public copy must never send from itself —
so the first command is what makes Saturday happen. It writes into both workflow files
between two marker comments; commit them with the config. On a **fork**, GitHub also
switches scheduled workflows off until someone presses **Enable** on the Actions tab;
tell them, in one sentence, when you get to the secrets.

Look at the render before you say it's done. Check the names on the per-plate lines, the
store names on the list, the market day, the number of dinners.

Write **`config/onboarded.yml`** when the config is written and the tests pass:

```yaml
repo: their-github-name/mealbit   # exactly what `git remote get-url origin` names
onboarded: 2026-09-05             # today
for: [Ada, Sam]                   # first names only
by: Claude, from the setup survey
```

`repo:` is the line that matters. The template ships without this file; if one is
there, it came from another household's copy, and `setup_status.py` counts it only when
`repo:` names *this* repository.
Overwrite it, don't append. That is what tells the next session this fork is set up.
Commit both config files and `onboarded.yml` together, with a message like "Set up
Mealbit for Ada and Sam".

## A fresh palate

The library may carry another household's verdicts — `rating:` and `feedback:` on the
recipes — if the fork came from a live instance rather than the upstream. Those are not
this household's, and a low one would retire a dish they never tasted. Before the first
render:

```bash
python tools/verdict.py --reset-all       # prints how many it cleared; 0 is fine
```

## What never goes in the repository

**First names only.** No surnames, no email addresses, no phone numbers, no home or work
address, no employer, no health detail beyond the food itself. The test suite scans every
committed file for addresses and phone numbers and fails the build; do not work around it.
If something personal needs to exist, it goes in a repository secret. When in doubt, ask
yourself whether you'd be comfortable if the repository were public tomorrow — for the
upstream repository, it is.

## Then: secrets, then a test send

Hand off to **`.claude/skills/mealbit-secrets/SKILL.md`** for the Gmail app password and
the four repository secrets. Only after that: **`.claude/skills/mealbit-send/SKILL.md`**
for the first test send — to them alone, never the household, until they've seen one.

## If they came back later

`setup_status.py` says "Set up" and they want to change something: use
`.claude/skills/mealbit-preferences/SKILL.md`. Don't re-run the survey.
