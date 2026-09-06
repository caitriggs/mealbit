# What the West Seattle Farmers Market actually has

> last_updated: 2026-08-30
> Confirmed 2026-08-30: WSFM is a **Washington State producers-only market** — 35+ farms
> and food vendors, Sundays 10am–2pm year-round. Vendors and stock vary week to week and
> the market's own guidance says last-minute changes happen.
> Sources: seattlefarmersmarkets.org/wsfm, LocalHarvest.

The planner cross-references every `market_items:` line against this file. **Anything the
market cannot credibly supply is rerouted to QFC**, with the reason printed in the
newsletter so it can be corrected here.

Three lists and one rule:

1. **`never`** — it does not grow in Washington, or a farmers market simply doesn't carry
   it. Always QFC, in every month.
2. **`year_round`** — reliably there any week the market is open.
3. **Everything else** is checked against the current month's `peak:` list in
   `seasonal-pnw.md`. In season → market. Out of season → QFC.

Unknown items default to **QFC**, deliberately. Sending someone to a stall that doesn't
have the thing is a worse failure than buying it at the store you were driving past anyway.

```yaml
never:
  # Doesn't grow in Washington — no amount of season will put it on a WSFM table.
  - lemon
  - lime
  - orange
  - grapefruit
  - banana
  - avocado
  - mango
  - pineapple
  - coconut
  - ginger
  - turmeric root
  - olive
  - sweet potato        # needs a long hot season; WA growers don't do it commercially
  - shishito pepper     # a few growers try it; too rare to plan a dinner around
  - napa cabbage        # sometimes at Asian-grower stalls, but not dependable
  - bok choy            # same

year_round:
  # Storage crops, perennials and the things every farm brings every week.
  - onion
  - yellow onion
  - red onion
  - white onion
  - spring onion
  - scallion
  - green onion
  - celery
  - shallot
  - garlic
  - leek
  - potato
  - waxy potato
  - carrot
  - beet
  - cabbage
  - green cabbage
  - red cabbage
  - kale
  - lacinato kale
  - chard
  - swiss chard
  - collard
  - spinach
  - lettuce
  - romaine
  - salad green
  - mushroom
  - egg
  - honey
  # Hardy herbs — perennial, cut all year
  - parsley
  - flat-leaf parsley
  - cilantro
  - thyme
  - rosemary
  - sage
  - oregano

# Produce that never needs a `|| fallback` on its recipe line. Two reasons an item lands
# here: it is at the market every week (so there is nothing to fall back FROM), or it is
# always routed to QFC (so there is nothing to fall back TO). Demanding "or any onion"
# after *onion* is noise, and noise is what makes a checklist stop being read.
fallback_exempt:
  - basil
  - bok choy
  - cabbage
  - carrot
  - celery
  - chive
  - cilantro
  - dill
  - flat-leaf parsley
  - fresno chile
  - garlic
  - ginger
  - green cabbage
  - green garlic
  - jalapeño
  - leek
  - lemon
  - lettuce
  - lime
  - mint
  - mushroom
  - napa cabbage
  - new potato
  - orange
  - oregano
  - parsley
  - poblano
  - potato
  - radish
  - red onion
  - romaine
  - rosemary
  - sage
  - scallion
  - serrano
  - shallot
  - shishito pepper
  - spring onion
  - sweet potato
  - tarragon
  - thyme
  - waxy potato
  - white onion
  - yellow onion

# Item head-noun -> words that mean the same thing on a market table, so "hot green chile"
# matches a month that lists "peppers".
synonyms:
  chile: [pepper, chili, chile]
  jalapeno: [pepper, chile, jalapeno]
  serrano: [pepper, chile, serrano]
  fresno: [pepper, chile, fresno]
  poblano: [pepper, chile, poblano]
  pepper: [pepper, chile, chili]
  squash: [squash, zucchini]
  zucchini: [zucchini, squash]
  bean: [bean]
  pea: [pea]
  tomato: [tomato]
  berry: [berry, strawberry, raspberry, blueberry, blackberry, marionberry]
  apple: [apple]
  pear: [pear]
  green: [green, kale, chard, collard, spinach]
  radish: [radish, turnip]
  broccoli: [broccoli, broccolini, rapini]
  mushroom: [mushroom, chanterelle, morel]
  chanterelle: [chanterelle, mushroom]
  corn: [corn]
  cucumber: [cucumber]
  eggplant: [eggplant]
  rhubarb: [rhubarb]
  asparagus: [asparagus]
  basil: [basil]
  mint: [mint]
  dill: [dill]
  tarragon: [tarragon]
  fennel: [fennel]
  cauliflower: [cauliflower]
  garlic: [garlic]
  sprout: [sprout, brussels]
```

## Correcting this

If you get to the market and something on the QFC list was sitting right there, move it
into `year_round` or add it to that month's `peak:` line in `seasonal-pnw.md`. If you
went looking for something and it wasn't there, add it to `never`. The file is the
system's model of the market, and you are the one who actually goes.
