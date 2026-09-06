# Portions and quantities

A reader, on a shopping list: *"calling for 2 pints of tomatoes, 3 bunches of cilantro
and 2 romaine lettuce heads is WAY too much for a single meal and a few lunches. Ensure
the portions are smaller than a typical American recipe calls for."*

Two separate faults produced that list, and they need different fixes.

## 1. One bunch is one bunch — `one_is_enough`

The consolidator sums every recipe's line. Three recipes each asking for "1 bunch
cilantro" became **3 bunches**, and cilantro is a garnish — one bunch covers a week and
the other two rot in the drawer. Same for a head of romaine, and worse for a jar of
pickled jalapeños, which keeps for months and was being bought three times.

For anything on this list the shopping list takes the **largest single requirement**, not
the sum. If one recipe genuinely needs 2 bunches it still says 2; three recipes each
needing one still says one.

The test of membership is: **does one purchase cover the whole week's uses?** A bunch of
herbs, yes. A pound of chicken thighs, obviously not — that scales with how much you cook.

```yaml
one_is_enough:
  # Fresh herbs. A supermarket bunch is far more than any single recipe uses.
  - cilantro
  - parsley
  - basil
  - mint
  - dill
  - tarragon
  - oregano
  - thyme
  - sage
  - chives
  # Salad and sandwich greens, bought by the head
  - romaine
  - lettuce
  - butter lettuce
  # Jars and cans that keep for months once opened
  - pickled jalapeno
  - hot giardiniera
  - salsa verde
  - chipotles in adobo
  - caper
  - olive
  - preserved lemon
  - fish sauce
  - gochujang
  - tahini
  - miso
  - harissa
  - chili onion crunch
  - chili crisp
  # Spice-rack quantities sold in one packet
  - culinary lavender
  - dried rose petal
  - saffron
  - black mustard seed
  # Aromatics sold in a bunch or a knob
  - ginger
  - scallion
  # Tubs of dairy used a spoonful at a time. Two recipes each wanting "1 container
  # Mexican crema" want the same container.
  - mexican crema
  - sour cream
  - greek yogurt
  - creme fraiche
  # The coffee counter. A drink uses a splash of milk and a spoon of honey; two drinks in
  # a week and a syrup to make still want one carton and one jar.
  - whole milk
  - heavy cream
  - barista oat milk
  - honey
  - maple syrup
  - condensed milk
  - cinnamon stick
  - cardamom pod
  - vanilla
  - tonic water
  - cocoa powder
  - dark brown sugar
  - black tea
```

## 2. Recipes were written at American restaurant scale

The second fault is in the recipes themselves. A US recipe "for four" routinely calls for
2 lb of meat, which is half a pound a head before any sides. This household cooks four
portions where two are eaten at the table and two are lunch — so a portion is a portion,
not a platter.

**House sizing, for a dinner cooked to serve 4:**

| | House | Typical US recipe |
|---|---|---|
| Boneless meat / fish | **1¼–1½ lb** | 2 lb |
| Bone-in meat | 2 lb | 3 lb |
| Ground meat | **1 lb** | 1½ lb |
| Dried pasta / grains | **12 oz** | 1 lb |
| Beans | **2 cans** | 3 cans |
| A vegetable that IS the dish | 1½–2 lb | 2–3 lb |
| A vegetable alongside | **1 lb** | 1½ lb |
| Cherry tomatoes | **1 pint** | 2 pints |
| Tinned fish | **2 jars** | 4 jars |

Assembly lunches make 2, so they scale to that — a sub is two rolls, not a bag of six.

`test_portions_are_household_sized` enforces the ceilings, because a hand-edited recipe
file is exactly where a 2 lb habit creeps back in.

## 3. The same thing may not appear in two stores

"Pickled jalapeños" was on the Trader Joe's list *and* the QFC list, because two recipes
filed it under different stores — three jars across two shops. An ingredient now appears
once, at the first store in visit order that any recipe assigns it to.
