# What counts as a protein dinner

The brief: *"we also want to ensure 3/4 meals have some kind of meat or high protein source
in them."*

Four dinners a week, and **at least three of them have to be built around a protein.**
The fourth is free — that is where a dal or a bowl of brothy beans goes.

## Where the line is, and why it is here

Asked which reading was meant, the household picked the middle one: **meat, fish, tofu and eggs
count; beans, lentils and chickpeas do not.**

That choice matters, because the other two readings are useless in opposite directions.
Simulated over 52 weeks of real plans:

| Counts as protein | Weeks that fell short of 3 |
|---|---|
| meat and fish only | 17 / 52 |
| **+ tofu and eggs** | **7 / 52** |
| + tofu, eggs *and* legumes | 0 / 52 |

Counting legumes makes the rule true every week by construction — it would enforce
nothing and quietly ratify whatever the picker already did. Counting only meat squeezes
the vegetarian dinners down to roughly one a week and makes the picker reach past season
fidelity a third of the time. The middle line is the one that does work.

It is not a claim that lentils are not food. A cup of cooked lentils is around 18g of
protein, which is real; a chicken thigh is around 35g and a block of tofu around 20g. The
rule is about what the plate is *built* around, and a legume dinner can still take the
fourth slot every single week.

## The tiers

`anchor` dinners satisfy the rule. `light` ones do not — the recipe's `protein:` tag
names something that is flavouring the plate rather than carrying it.

```yaml
anchor:
  - beef
  - pork
  - chicken
  - turkey
  - fish
  - shellfish
  - tofu
  - egg

light:
  - legume        # beans, lentils, chickpeas — real protein, but not the anchor here
  - mushroom      # the chanterelle skillet is a grain dish with mushrooms in it
  - cheese        # the green risotto's protein tag is Parmigiano, which is a seasoning

min_anchor_dinners: 3
```

## If you add a recipe

Every dinner's `protein:` value must appear in one of the two lists above — a tag that is
in neither fails `test_every_protein_is_classified`, because an unclassified tag would
silently count as `light` and quietly tighten the rule on a dish that should have passed.

If you add a genuinely protein-forward vegetarian dinner — a paneer curry, a tempeh
traybake, a seitan stir-fry — give it its own tag and put it under `anchor`. Do not file
it as `legume` to sneak it past the rule; the tag is what the audit reads.

## What the picker does with it

`planner.pick_dinners` will not take a `light` dinner if doing so would put three anchors
out of reach for the rest of the week. It is protected at the same level as the
no-repeated-protein rule — the last things given up — so the picker will bring a meal
back off cooldown early, and reach into a neighbouring season, before it serves a week
with only two protein dinners. If it does have to concede, the email's "how this week was
picked" footnote says so out loud.
