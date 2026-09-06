---
name: mealbit-preferences
description: Change an already-set-up Mealbit household's preferences on their behalf — who skips what, exclusions, protein ranking, how many dinners, what lunch means, stores and their order, the farmers market, send day and hour, coffee gear — by editing config/household.yml and config/stores.yml, validating, rendering, and committing. Use whenever someone asks to change how their week is planned; never make them edit a file.
---

# Changing preferences for a household that's already set up

`python tools/setup_status.py` says **Set up**, and they want something different. You
edit; they never do. Every change ends with the tests, a render, a look, and a commit.

## Where each thing lives

| They say | You change | Notes |
|---|---|---|
| "we don't eat X" | `diet.exclude_ingredients` in `household.yml` | removes every recipe that uses it; matched inside names ("salmon" catches "salmon fillet") |
| "Max doesn't like X but I do" | `diet.per_plate` → `Max: [x]` | the recipe stays; X goes on the other plate. The library is written around cilantro, raw tomatoes, arugula. Anything else works as a check but the recipe prose won't mention it — say so |
| "more chicken, less pork" | `diet.protein_preference` | a ranking, not a rule |
| "3 dinners, not 4" | `meals.dinners_per_week` | 2–5, Monday onward |
| "we don't want leftover lunches" | `meals.lunch_mode: fresh` | dinners cooked for the table, list buys for two, cards say to halve |
| "no lunches at all" | `meals.lunch_mode: none` | dinners only; the lunch section disappears |
| "send it Friday evening" | `send.day`, `send.hour`, `household.timezone` | outside US Pacific: also the two `cron:` lines in the workflow, in UTC, for both halves of the year |
| "we got an espresso machine" | `coffee.gear` | `espresso`, `moka`, `aeropress`, `french-press`; drinks are filtered to what the counter can make |
| "add Costco / drop Trader Joe's / we go to Safeway first now" | `config/stores.yml` | order = visit order; exactly one store takes `everything`, last |
| "we switched farmers markets" | the `kind: farmers_market` entry | name, `when`, `where` (cross-street, never a home address), `tips:` → a new `data/markets/<name>.md` |
| "the market never has X" | `data/markets/pnw-washington-growers.md` | add to `never` (doesn't grow here) or check `seasonal-pnw.md` |
| "Trader Joe's doesn't carry X" | that store's `never:` list in `config/stores.yml` | the line moves to the next store; matched by name |
| "we always have soy sauce" | `data/pantry.md` | be sparing — anything in there is a line the shopper never sees |
| "not the pulled pork this week" / "we loved it" / "add a katsu" | not a preference — a dish | `.claude/skills/mealbit-recipes`: one-week skips and pins, verdicts, new recipes, the seasonal refresh |

**Two eaters is not a preference.** If they ask for a third person, explain that dinners
serve four as two-plus-two-lunches and the whole plan is built on two; point at
`docs/household-model.md` for what four would take. Don't add a third name — the config
refuses it and the arithmetic breaks behind the config.

## The stores model, so you can reason about edge cases

An ingredient goes to the **first store in visit order whose `takes:` covers its kind**.
Kinds: `produce protein dairy bakery pantry specialty wine`; `everything` is the catch-all.
A `farmers_market` store is also checked against its availability model for the month, and
what it can't stock moves to the next store with a printed reason. So:

- Removing a store: delete its entry. If it was the catch-all, make another store the
  catch-all or the config refuses to load — a list that can drop an ingredient is not
  allowed.
- A store that only sells one thing (a butcher, a bakery): `takes: [protein]` or
  `[bakery]`, placed where they visit it.
- Two supermarkets: the first takes what they prefer to buy there, the second takes
  `everything`.

## Taking fixes from the template

"Is there anything new?" or "update from the template": `CLAUDE.md`, "Taking fixes from
the template". Keep ours for the household's files, theirs for the rest, run the tests,
render, commit. Say what changed for them in one or two sentences — a bug fixed, a new
feature — never the file list.

## After every change

```bash
python tests/test_mealbit.py      # must pass; the message names the rule
python -m mealbit.meal_plan       # render
python tools/screenshot.py        # look at it — light and dark
```

Then commit with a message that says what changed in their words ("Max skips blue cheese
now"). Never commit an email address, phone number, or street address; the tests refuse
them, and the reason is that this repository's upstream is public.

If the change affects the email itself and they haven't seen the new version, offer a
test send (`.claude/skills/mealbit-send`) before Saturday.
