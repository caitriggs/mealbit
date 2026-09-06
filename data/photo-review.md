# Photo review — 2026-09-02

The household: *"the lunch photos need to be higher quality and actually the meal they represent
not bad quality photo photos taken by home chefs."*

All 33 dinners and 13 lunches looked at by eye, one contact sheet at a time. The result
splits cleanly by SOURCE, which is the finding:

| Tier | Reviewed | Bad |
|---|---|---|
| `image_url` — verified published recipe | 20 dinners, 6 lunches | 4 (all wrong *variant*, none badly shot) |
| `photo_url` — Openverse | 13 dinners, 5 lunches | **13** (poor, wrong, or both) |

Openverse indexes openly-licensed images of *anything* — a bag of wild rice, a leek on a
table, someone's dinner under a kitchen bulb. Nothing in its metadata separates those
from a composed food photograph, which is why the automated pass and then a human pass
both landed on bad pictures. The fix is a better-curated source, not a better filter:
`tools/stock_photos.py` adds Pexels as a third tier.

## Replace — wrong dish (the photo is not the meal)

| # | Recipe | What the photo shows |
|---|---|---|
| 2 | Seared beef and cabbage, chili oil noodles | plain noodles and sprouts. No beef, no cabbage |
| 9 | Chorizo and charred corn skillet | a breakfast hash with fried eggs and avocado |
| 18 | Oven-fried turkey taquitos | a dark burrito cut open, badly lit |
| 29 | Blistered shishitos and shrimp over coconut rice | a plate of shishito peppers. No shrimp, no rice |
| 32 | Turkey and white bean green chile chili | a murky pot of beans, and not green |
| 3 | Charred sweet potato and black bean tacos | meal-prep containers of rice and chickpeas — no tacos in frame |
| 14 | Green shakshuka with asparagus, peas and feta | a *red* shakshuka, with brussels sprouts |
| 26 | Salmon with rhubarb-ginger glaze | teriyaki salmon |
| 28 | Braised short rib ragù with pappardelle | the ragù on gnocchi |

## Replace — poor quality (right dish, bad photograph)

| # | Recipe | |
|---|---|---|
| 1 | BBQ pulled pork over cheesy grits | dim, murky plate |
| 10 | Cod in saffron-tomato broth | pale fish in pink liquid, unlit |
| 24 | Red lentil dal | flash-lit snapshot on a placemat |
| 33 | Zucchini and corn carbonara | plain spaghetti; neither zucchini nor corn visible |

## Keep

Everything else. Notably the whole verified-recipe tier apart from the four above — those
photos were shot by the recipes' own authors and they look it.

Borderline, left alone rather than churned: #5 chanterelle skillet (dark and moody, but
a real composed photograph), #16 miso squash (roasted squash only, no tofu in frame),
#21 grilled pork with peaches, #22 pork larb.


---

## Outcome, 2026-09-02 (after the Pexels key landed)

**21 photos replaced, every one looked at before it was pinned.** The Openverse tier is
now empty: all 46 cards carry either the recipe author's own photo or a Pexels one.

The top-ranked search result was wrong often enough to be worth recording — "loaded
fries" for the pulled pork grits, raw butternut squash for the miso squash, a full
English breakfast for the white bean toast, miso *soup* for the soba bowl. Pexels fixes
photo QUALITY, not accuracy; the reviewing step is still what makes the tier work.

Five recipes needed a hand-written query because the default (the title's leading words)
was too generic or too obscure. They are worth keeping if the queries are ever re-run:

| slug | query that worked |
|---|---|
| `bbq-pulled-pork-cheesy-grits` | pulled pork cheesy grits |
| `chanterelle-farro-skillet` | mushroom farro risotto bowl |
| `miso-tofu-soba-snap-peas` | soba noodles tofu bowl |
| `roasted-squash-wild-rice-kale` | roasted squash grain bowl kale |
| `pork-chops-peaches-basil` | pork chop plate grilled peach |

## Still open — 4 wrong variants in the verified-recipe tier

These are good photographs of *nearly* the right dish, and they are the recipe author's
own picture of the recipe the QR opens — so replacing the photo would mean either
dropping the QR link or letting a borrowed photo outrank the recipe's own, which the
two-tier rule currently forbids. Left as they are, deliberately, for the household to call:

| Recipe | The photo |
|---|---|
| Charred sweet potato and black bean tacos | a meal-prep container. No tacos in frame |
| Green shakshuka with asparagus and peas | a *red* shakshuka |
| Salmon with rhubarb-ginger glaze | teriyaki salmon |
| Braised short rib ragù with pappardelle | the ragù on gnocchi |
