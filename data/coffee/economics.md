# Coffee Ritual — the money, and how it's calculated

> last_updated: 2026-08-29
> `meal_plan.py` reads the YAML block below. Change a number here and the newsletter
> changes. Every figure is sourced or flagged as an estimate — nothing is asserted
> without its arithmetic.

## Where the baseline comes from

The household's own numbers live in `config/household.yml` (`coffee.monthly_coffee_spend`,
`coffee.monthly_visits`); the email derives the average per visit from them and prints
nothing if they are not set. The worked example below uses one real household's figures —
**$545 a month across ~30 visits, $18.17 a visit** — because the arithmetic is the point.

**$18.17 a visit is not the price of a latte.** A 12 oz latte in Seattle is roughly
$5.75–6.50. So the average visit is carrying a pastry, a second drink, or two people.
That distinction matters, and the newsletter reports both numbers separately rather than
claiming credit for the pastry.

## The two savings figures

**1. Drink-for-drink (the conservative one, and the headline).**
What this specific drink costs to make, against what the same drink costs out.

    saved per drink = shop_equivalent − cost_per_serving

Averaged across the 12 drinks in the library: about **$6.72 out** vs **$1.48 at home** =
**$5.24 saved per drink.** Two drinks a day, five days a week ≈ **$52/week, ~$227/month**.

**2. Visit-for-visit (the upside, always labelled as such).**
A café trip that doesn't happen saves the whole visit, pastry included — $18.17 in the
example. Replacing
half of the 30 monthly visits ≈ **$272/month**. This is the bigger number and the softer
one — it assumes behavior change, not just substitution, so the newsletter never leads
with it.

## Ingredient cost assumptions

Per-drink costs in the drink files are built from these. They're estimates; correct them
here if the real receipts disagree.

| Item | Price | Per drink |
|---|---:|---:|
| Specialty beans, 12 oz bag | $18.00 | $0.95 (18 g double shot) |
| Trader Joe's beans, 12 oz | $8.50 | $0.45 |
| **Blended assumption** | | **$0.75** |
| Barista oat milk, 64 oz | $4.50 | $0.42 (6 oz) |
| Whole milk, gallon | $4.50 | $0.21 (6 oz) |
| Homemade syrup | ~$0.40/cup | $0.10–0.20 |

A home latte therefore lands at **$1.20–$1.80** depending on the drink. That's the range
in the `cost_per_serving` field of every drink file.

## Payback on gear

If they don't already own it: burr grinder + scale + frother + Moka pot ≈ **$150 all-in**
(see `fundamentals.md`). At the example's $545/month, that is **eight days** of the habit.

---

```yaml
# The household's own spend lives in config/household.yml (coffee.monthly_coffee_spend,
# coffee.monthly_visits) and overrides anything here. These are library-level costs.
typical_shop_latte: 6.25
drinks_per_week_assumed: 10     # 2 people x 5 weekdays — the conservative default
bean_cost_per_shot: 0.75
milk_cost_per_drink: 0.42
syrup_cost_per_drink: 0.15
gear_starter_cost: 150
```
