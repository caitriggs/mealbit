# The household model

What the two config files mean, and the assumptions the planner makes that they don't
expose.

## The week this system assumes

The week runs **Monday to Sunday**. The newsletter lands the evening before it, so there's
time to read it and swap a meal. Shopping and one block of batch prep happen the day
before the week opens. Then:

| | |
|---|---|
| Dinner | **Mon, Tue, Wed, Thu** — four nights, cooked from the library, up to 45 minutes hands-on |
| Fri, Sat, Sun dinners | deliberately unplanned |
| Lunch | every day, for each eater |

Four dinners, not seven. Seven is the classic meal-planner mistake: it ignores leftovers,
a night out, and the fact that plans slip.

## Two eaters, and why that isn't just a number

Every dinner is cooked to **serve 4**: two at the table and two as the next day's lunches.
That ratio is what makes the lunch column free — eight of the week's fourteen lunch slots
are paid for by dinner. The rest come from two batch lunches made on the shopping day
(served Mon–Fri only; by the weekend they're a week old) and a few five-minute builds.

`household.eaters` is therefore assumed to have **two** names. Supporting four would mean:

- dinners serving 6 or 8, which changes every portion ceiling in `data/portions.md`;
- a lunch ledger with 28 slots instead of 14, and a batch lunch that makes 10;
- leftover arithmetic (`serves >= leftovers + N`) everywhere it appears;
- re-thinking which dinners still work at that scale.

It's a real piece of work, not a config value, and it hasn't been done. If you need it,
that's the shape of it.

## Exclusions and per-plate items are different things

`diet.exclude_ingredients` removes every recipe that uses the thing. Use it for allergies
and hard nos.

`diet.per_plate` is for the case where one eater doesn't want something the other does —
cilantro, raw tomato, arugula. The recipe **stays**. The ingredient goes on the other
plate at the end, and every recipe in the library that buys a per-plate item declares
either:

- `per_plate: [x]` plus a `**Per plate:**` paragraph saying how the dish is complete
  without it, or
- `per_plate_exempt: [x]` with a reason it doesn't apply here (cooked down, roasted,
  sun-dried — not raw).

A test enforces this, because it was documented and unenforced once, and a salad shipped
with raw tomato juice *as the dressing*. The email and the card name the person:
"cilantro — not on Max's plate."

## Protein

`diet.protein_preference` ranks what the household likes. Separately, **three of the four
dinners must be built on a protein** — meat, fish, tofu or eggs. The fourth is free, and
that's where a dal or a bowl of beans goes. Which tags count is in `data/protein.md`, with
the reasoning; it was a judgement call that moved the outcome a long way.

## What's assumed to be in the house

Four things: salt, black pepper, olive oil, white vinegar. That's the whole of
`data/pantry.md`. Everything else a recipe leans on — soy sauce, garlic, a lemon — reaches
the shopping list in a **Check the cupboard** group that comes first, because it's the one
group you act on before leaving. You decide at shop time what you already own. The
system's job is never to decide that for you.

## Stores

`config/stores.yml` lists shops in visit order with what each `takes`. Recipes tag
ingredients by kind and never name a shop. See the comments in that file; the rule is one
line: **an ingredient goes to the first shop in visit order whose `takes` covers its kind.**

A `farmers_market` store is also checked against an **availability model** — what a
market in this region can credibly stock this month. The shipped one is for Washington
growers-only markets. Anything the market can't supply moves to the next shop and the
email says why, so the model can be corrected by whoever actually goes.

## Coffee

`coffee.gear` narrows the drink library to what your counter can make. `drinks_per_week`
is how many featured drinks the email carries. The syrup-and-crumble box is standing stock:
a syrup made once keeps about five weeks, so most weeks a new drink costs nothing extra,
and the email only asks you to make something when it's actually out.

## Leftovers are a judgement

Every dinner declares `leftover_quality: good | fair | none`. `none` means don't pack it —
it degrades, or reviving it means cooking — and forces `leftovers: 0`. At most one
non-packing dinner a week, because each one costs two lunch slots. The definitions, and
the reasoning about which error is worse, are in `CLAUDE.md`.
