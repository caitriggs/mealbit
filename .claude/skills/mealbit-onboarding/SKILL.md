---
name: mealbit-onboarding
description: Set up a freshly copied Mealbit for a new household by running the setup survey, writing config/household.yml and config/stores.yml from the answers, filling the library for their preferences, and ending with their first week on the screen. Use this the moment `python tools/setup_status.py` says NOT SET UP, before anything else — the survey is your first message, not something you wait to be asked for.
---

# Onboarding a new household

You are talking to someone who copied this repository and opened it in Claude Code. They
are not a programmer, they are on their phone, and they want the emails to start. **They
will not edit files.** You ask, they answer, you write everything, you show them their
first week. Every technical step is yours; every decision is theirs.

## How to talk (this is the part that went wrong the first time)

The first real onboarding produced messages with headers, a "readback" of what the code
does, file names with line numbers, and a paragraph weighing salmon recipes for a
household that had just said no salmon. Every one of those is a failure of this skill.

- **One round per message.** At most two short sentences before the questions, then the
  numbered questions, then stop. No header. No summary of what you learned.
- **Never mention a file, a folder, a path, a function, a line number, a slug, a test, a
  branch, a commit, or the word "code".** They cannot see any of it and do not want to.
  "I've written that down" is the whole story.
- **Decide; don't narrate.** Never explain what you checked, what the system does, or why
  a setting works the way it does, unless they ask. Not "the matcher is a substring match
  against the ingredient key." Just: done.
- **Never name an ingredient or dish they just excluded.** An exclusion is applied
  silently; the recipes that use it vanish and they never hear about them. Discussing
  salmon after "no salmon" is the exact thing this skill must not do.
- **Never read the answers back for confirmation.** Write them. The first week you show
  them is the confirmation, and a wrong answer is a one-line fix then.
- Plain sentences. No bold walls, no bullet essays. If a reply is longer than the
  questions it asks, cut it.
- When you *do* say something, say what it means to them ("Saturday at 5pm, your time"),
  not what you set.

## Before the survey

Run `python tools/setup_status.py`. If it says **NOT SET UP**, your very first reply is
Round 1 below. Not a description of the repository, not a menu, not "what would you like
to do." Open with one sentence — you'll get a weekly email with dinners, lunches, a
shopping list for your stores and printable cards, and I need about ten answers to start —
and ask.

## The survey

Three rounds. Accept casual answers. If an answer is missing, use the default and move on;
don't ask twice.

### Round 1 — who eats

1. First names of the two people eating. (Three or more: say, in one sentence, that it is
   built for two and offer to set it up for two of them now.)
2. Anything either of them won't eat at all — allergies and hard nos. →
   `exclude_ingredients`, and never mentioned again.
3. Anything one of them skips that the other likes (cilantro, raw tomato, blue cheese).
   → `per_plate`, keyed by who skips it. One line on what it means: the dish still gets
   made, that goes on the other plate.
4. Proteins they like most, in rough order, and how they feel about fish. →
   `protein_preference`; whitefish is capped at twice a month unless they say otherwise.

### Round 2 — the week

5. How many dinners a week, 2 to 5. Default 4, Monday to Thursday, weekend free.
6. Lunch: leftovers from dinner (the default, and the recommendation if they take lunch to
   work), fresh batches instead, or no lunch planning. → `lunch_mode`.
7. Which day and hour the email should arrive, and their timezone. Default Saturday 5pm;
   shopping is the day after. Any timezone works.
8. Coffee at home, and with what: espresso machine, Moka pot, AeroPress, French press, or
   none. Two drinks a week unless they want fewer.

### Round 3 — where they shop

9. Their shops in the order they visit them. The one that has everything goes last.
10. A farmers market? Name, day and hours, cross-street (never a home address). Around
    Puget Sound the shipped market model applies as-is. Elsewhere: one sentence offering
    to skip the market for now or write a model for theirs; don't reuse Washington for
    Vermont silently.

Nothing else. Not photos, not syrups, not ratings, not anything under `data/`.

## Writing it (nothing here is said aloud)

Write `config/household.yml` and `config/stores.yml` from the answers, keeping the
comments. The tests enforce these; get them right first time:

- `household.eaters` is exactly the two first names; `per_plate` keys are one of them.
- `send.from / to / test_to` stay as placeholders; real addresses are repository secrets.
- `meals.dinners_per_week` 2–5; `meals.lunch_mode` is `leftovers`, `fresh` or `none`.
- Every store has `id`, `short` (2–3 letters), `name`, `takes`; exactly one takes
  `everything`, last. A farmers market has `kind: farmers_market`, `when`, `where`,
  `availability`, `tips`, `takes: [produce]`. For a new market, copy
  `data/markets/west-seattle.md` to `data/markets/<their-market>.md` with the stall notes
  replaced by "nothing verified yet".
- Kinds: `produce protein dairy bakery pantry specialty wine`, plus `everything`.

Then:

```bash
python tools/verdict.py --reset-all    # another household's opinions are not theirs
python tools/schedule.py --write       # the cron lines for THEIR timezone; the template ships none
python tests/test_mealbit.py           # must pass
python tools/first_weeks.py            # their next four weeks, and whether the library fits them
```

## Round 4 — their first week (the part that captures their taste)

The library was written for one household. Theirs has different exclusions and a
different protein order, and **the point of Mealbit is that they never have to think
about this**. So before they see anything, make the library fit them:

`tools/first_weeks.py` prints the next four weeks with any compromise the planner had to
make, and a fit line for the coming season: how many dinners are reachable after their
exclusions, and how many use each protein they ranked. **If it says the season is short
(fewer than 12 reachable dinners), or their first-choice protein has fewer than 2 dinners,
or any of the four weeks carries a "thin" or "share a protein" note, write recipes now**
— `.claude/skills/mealbit-recipes`, the "Add a dish" contract, no shortlist, no
discussion — until it doesn't. Weight them to their top proteins and the coming season's
market. Up to six at setup; `photo_pending: true` is fine on a copy (the cap is 12 here,
4 on the upstream). Re-run the tests and `first_weeks.py` after.

Then render and look, once, yourself (`python -m mealbit.meal_plan`, `python
tools/screenshot.py`): the names on the per-plate lines, the store names, the number of
dinners. Fix anything wrong without mentioning it.

Write `config/onboarded.yml` — overwrite, never append:

```yaml
repo: their-github-name/their-repo   # exactly what `git remote get-url origin` names
onboarded: 2026-09-06                # today
for: [Ada, Sam]                      # first names only
by: Claude, from the setup survey
```

Commit everything together ("Set up Mealbit for Ada and Sam"). Then the **only** thing
you say is their first week, in this shape and nothing more:

> Here's your first week, starting Monday the 14th:
> Mon — Chicken katsu with cabbage slaw
> Tue — …
> Wed — …
> Thu — …
> Lunches are leftovers plus two Sunday batches: a white bean and tuna jar, a noodle salad.
> Want to swap any of these? If not, next is the two things only you can do — a Gmail app
> password and four secrets — and then I'll send you a test.

A swap is `.claude/skills/mealbit-recipes` (skip and re-render, library first). Then
`.claude/skills/mealbit-secrets`, then `.claude/skills/mealbit-send` for the first test —
to them alone, never the household, until they've seen one.

## What never goes in the repository

First names only. No surnames, email addresses, phone numbers, home or work addresses,
employer, or health detail beyond the food itself. A test scans every committed file and
fails the build; do not work around it. Anything personal that must exist goes in a
repository secret.

## If they came back later

`setup_status.py` says "Set up" and they want to change something: use
`.claude/skills/mealbit-preferences`. Don't re-run the survey. If they want the latest
fixes from the template: `.claude/skills/mealbit-preferences`, "Taking fixes from the
template".
