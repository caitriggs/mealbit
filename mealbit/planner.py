#!/usr/bin/env python3
"""
Weekly plan assembly: pick the meals, work out who eats what for lunch, and route the
shopping list by store.

Three things here are load-bearing and worth reading before changing:

1. SELECTION IS SEASON-FIRST. We start from what a Western Washington market actually
   has this month and pick meals that use it — never the reverse. A generic planner picks
   recipes and then sends you hunting for February tomatoes.

2. THE LUNCH LEDGER IS REAL ARITHMETIC, NOT A SUGGESTION. Four dinners cooked to serve 4
   yield 2 leftover servings each. Ten weekday lunch slots (2 people x Mon-Fri) get filled
   from those leftovers first, then from Sunday-prepped batches, then from 5-minute
   assembly lunches. The newsletter prints the resulting grid so nobody does this at 7am.

3. THE SHOPPING LIST IS GROUPED BY STORE IN VISIT ORDER, NEVER BY RECIPE. People shop a
   store once, not a recipe once. This is the single most important UX decision in the
   system (build brief, section 2).
"""
import random
import re
from datetime import date, timedelta

from . import library as L
from . import config as C

# --- the week's shape -------------------------------------------------------
# The week runs MONDAY to SUNDAY. The newsletter lands Saturday evening, shopping and
# batch prep happen on the Sunday in between (market day, 10am-2pm), and the plan week
# opens on Monday with everything already in the house.
#
# Dinners are cooked Mon-Thu, four nights back to back. Fri/Sat/Sun are deliberately
# unplanned — a 7-dinner plan is the classic meal-planner mistake, because it ignores a
# night out and the fact that plans slip.
#
# Lunches are EVERY day, both people: 7 x 2 = 14 slots to fill.
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
COOK_NIGHTS = [0, 1, 2, 3]           # Mon, Tue, Wed, Thu — the default; see meal_settings()
FLEX_NIGHTS = [4, 5, 6]              # Fri, Sat, Sun — yours
LUNCH_DAYS = [0, 1, 2, 3, 4, 5, 6]   # every day
# Who eats, from config/household.yml. Two names: the whole lunch ledger — "two at the
# table, two for tomorrow" — is built on exactly two, and that is documented rather than
# hidden behind a number that looks adjustable.
EATERS = list(C.household()["eaters"])
LEFTOVER_WINDOW = 2                  # a dinner feeds lunch for this many following days

# Batch lunches are cooked on the Sunday BEFORE the week opens, so by Saturday a container
# is six days old and by Sunday it is seven. That is past the point anyone should be
# eating it, and well past the point it is nice. Batches therefore serve Mon-Fri only;
# weekend lunches fall to the 5-minute assembly recipes, which are made fresh anyway and
# which you have time for on a day you are home.
PREP_LASTS_DAYS = 5

N_DINNERS = 4
N_LUNCHES = 5


def meal_settings(cfg=None):
    """
    How many dinners this household cooks and what lunch means to it, from
    config/household.yml `meals:`. Read at call time, not import time, so a test can
    swap the household and see a different week.

      dinners_per_week  2..5, cooked Monday onward
      lunch_mode        leftovers | fresh | none  (see config.LUNCH_MODES)

    The module constants above are the defaults — the original household's week — and
    are what the rest of the library was sized for.
    """
    cfg = cfg or L.load_household()
    n = int(cfg.get("dinners_per_week") or N_DINNERS)
    mode = cfg.get("lunch_mode") or "leftovers"
    n_prep, n_asm = (0, 0) if mode == "none" else (N_PREP_LUNCHES, N_ASSEMBLY_LUNCHES)
    return {
        "n_dinners": n,
        "cook_nights": list(range(n)),
        "lunch_mode": mode,
        "n_prep": n_prep, "n_assembly": n_asm, "n_lunches": n_prep + n_asm,
        # "Three of four" generalises to "all but one": 2->1, 3->2, 4->3, 5->4.
        "min_protein": max(1, n - 1),
        # In leftovers mode a dinner is cooked to serve 4 and the list buys for 4. In the
        # other modes the recipe still SAYS 4 but the list buys for the people at the
        # table, and the card says to halve it.
        "table_only": mode != "leftovers",
    }

# --- how many dinners have to be built on a protein ---------------------------
# The brief: "we also want to ensure 3/4 meals have some kind of meat or high protein source
# in them." Three of the four; the fourth is free, and that is where a dal or a bowl of
# brothy beans goes. WHICH tags count is a judgement call that lives in data/protein.md
# rather than here, because the answer moved the outcome a long way: counting legumes as
# a protein made the rule true 52 weeks out of 52 and enforced nothing, counting only
# meat left 17 of 52 weeks short. The household chose the middle line.
MIN_PROTEIN_DINNERS = 3
N_PREP_LUNCHES = 2                   # batch-cooked Sunday
N_ASSEMBLY_LUNCHES = 3               # 5 minutes, day-of

# --- rotation cooldowns (in weeks) ------------------------------------------
# These are TARGETS, not guarantees, and the arithmetic is why. A seasonal dinner pool is
# ~10-14 recipes; at 4 a week, a 6-week cooldown would need 24 of them and could never be
# satisfied. So each cooldown is set to what the library can actually sustain, and the
# picker steps it down further (reporting that it did) rather than failing to produce a
# newsletter. A repeated meal is a mild annoyance; a Saturday with no plan is the thing
# that sends a household back to the meal-kit subscription.
#
# Sustainable ceiling = floor(smallest seasonal pool / picks per week):
#   dinners  ~12 in season / 4 per week -> 3
#   lunches    7 per style / 2-3 per week -> 2
#   coffee   ~6 in season  / 1 per week -> 5
COOLDOWN = {"dinners": 3, "lunches": 2, "coffee": 5, "syrups": 0, "crumbles": 0}


class PlanError(Exception):
    pass


# ---------------------------------------------------------------- filtering

def _excluded(recipe, cfg):
    """Drop anything the household has said it won't eat (config/household.yml -> diet),
    and anything they have rated at or below L.RETIRE_AT_OR_BELOW — a verdict, not a diet
    rule, but the effect is the same: never planned again until someone re-rates it."""
    if L.is_retired(recipe):
        return True
    if set(recipe.get("tags") or []) & set(cfg.get("exclude_tags") or []):
        return True
    bad = set(cfg.get("exclude_ingredients") or [])
    if not bad:
        return False
    # Substring, not equality. An excluded "salmon" has to catch "salmon fillet",
    # "raw shrimp, peeled" and "cold-smoked salmon" — matching the whole normalized key
    # exactly meant the exclusion list silently excluded nothing, which is the worst
    # possible failure mode for a dietary constraint.
    for line in L.ingredients(recipe) + [str(x) for x in (recipe.get("pantry") or [])]:
        if True:
            key = L.parse_item(str(line))["key"]
            if any(b in key or b in recipe.get("title", "").lower() for b in bad):
                return True
    return False


def eligible(pool, season, hist, kind, cfg, widen=0, cooldown=None):
    """Season-matched, not-recently-served, not-excluded."""
    cooldown = COOLDOWN[kind] if cooldown is None else cooldown
    ok_seasons = set(L.adjacent_seasons(season, widen)) if widen else {season}
    out = []
    for r in pool:
        if _excluded(r, cfg):
            continue
        if not (set(r.get("seasons") or []) & ok_seasons):
            continue
        ago = L.weeks_since(hist, kind, r["slug"])
        if ago is not None and ago < cooldown:
            continue
        out.append(r)
    return out


# Reaching one season bucket outward costs about this much, expressed in weeks of lost
# rotation. PNW season buckets are two months wide and their edges blur — a summer recipe
# in the first week of September is fine. Serving the same dinner two weeks running is
# not: "chicken again" is precisely the failure that gets a meal plan abandoned. So one
# widen step is priced above one week of cooldown, and the ladder is walked cheapest-first.
WIDEN_COST = 1.5


def _attempts(kind):
    """Degradation ladder, cheapest compromise first."""
    full = COOLDOWN[kind]
    opts = [(widen, cd) for widen in (0, 1, 2) for cd in range(full, -1, -1)]
    return sorted(opts, key=lambda wc: (full - wc[1]) + WIDEN_COST * wc[0])


# ---------------------------------------------------------------- selection

def pick_dinners(pool, season, hist, cfg, rng, n=N_DINNERS, pinned=()):
    """
    Greedy pick under variety constraints, relaxing in a fixed, reported order.

    `pinned` dinners were asked for by name this week (data/this-week.yml). They take
    their slots first and the rules fill the rest around them.

    Hard-ish rules, strictest first:
      * no repeated protein in a week   <- the "chicken again" guard
      * no repeated cuisine in a week
      * at most one dinner that does not pack as a lunch (leftover_quality: none)
      * at least MIN_PROTEIN_DINNERS built on a protein (data/protein.md)
      * at most one `project` (multi-hour) dinner
      * at least two `comfort`-register dinners -- the household's demonstrated taste
        runs to craveable comfort food, not a tasting menu (see docs/household-model.md)
      * at least one `easy` dinner, for the night the day went badly

    Every relaxation applied is returned so the newsletter can be honest about it rather
    than silently serving chicken twice.
    """
    # Nesting matters. Within-week variety is protected HARDER than rotation: serving
    # chicken twice in one week is a worse dinner-table experience than bringing a meal
    # back a week early, and it is the specific complaint that kills meal plans. So we
    # walk the entire cooldown/season ladder at full strictness before conceding a single
    # variety rule, not the other way round.
    anchors, _light = L.load_protein()
    served = L.ever_served(hist, "dinners")
    pinned = list(pinned)
    if len(pinned) > n:
        raise PlanError(f"{len(pinned)} dinners are pinned this week but only {n} are "
                        f"cooked — drop one from data/this-week.yml")
    for relax in range(4):
        for widen, cd in _attempts("dinners"):
            cands = eligible(pool, season, hist, "dinners", cfg, widen, cd)
            picked = _greedy(cands, n, rng, relax, anchors, served, pinned)
            if len(picked) != n:
                continue
            notes = []
            if cd < COOLDOWN["dinners"]:
                notes.append(f"a dinner came back after {cd} week(s) rather than the usual "
                             f"{COOLDOWN['dinners']} — the {season} shelf is thin")
            if widen:
                notes.append(f"reached into neighbouring seasons (±{widen}) to fill the week")
            if relax >= 1:
                notes.append("two dinners share a cuisine this week")
            if relax >= 2:
                notes.append("could not hold the comfort/effort balance")
            if relax >= 3:
                notes.append("two dinners share a protein — the library is genuinely thin "
                             "for this season; worth adding a few recipes")
            got = sum(1 for p in picked if p.get("protein") in anchors)
            want = meal_settings(cfg)["min_protein"]
            if got < want:
                notes.append(f"only {got} of {n} dinners is built on a protein rather "
                             f"than {want} — the {season} shelf could use "
                             f"another meat or tofu dish")
            return picked, notes
    raise PlanError(
        f"No workable dinner set for {season}: need {n} recipes and the library cannot "
        f"supply them even with every rule relaxed. Add recipes to data/recipes/dinners/.")


def _greedy(cands, n, rng, relax, anchors=None, served=None, pinned=()):
    anchors = L.load_protein()[0] if anchors is None else anchors
    served = set() if served is None else served
    order = [r for r in cands if r["slug"] not in {p["slug"] for p in pinned}]
    rng.shuffle(order)
    # Untried recipes surface first. "Untried" is read from history.json — the one record
    # of what was served — not from a field on the recipe, which nothing ever wrote.
    order.sort(key=lambda r: 0 if r["slug"] not in served else 1)
    # A pinned dish was asked for by name; it takes its slot before any rule is consulted.
    picked = list(pinned)
    proteins = {p.get("protein") for p in picked}
    cuisines = {p.get("cuisine") for p in picked}
    for r in order:
        if len(picked) == n:
            break
        if relax < 3 and r.get("protein") in proteins:
            continue
        # Three of the four dinners must be built on a protein. Checked as a look-ahead
        # rather than a count at the end: taking a `light` dinner is only wrong if it
        # puts the third anchor out of reach, so the test is whether the anchors already
        # picked plus every slot after this one can still get there. Protected at the
        # same level as the no-repeated-protein rule, so the picker will bring a meal
        # back off cooldown early and reach into a neighbouring season before it concedes.
        if relax < 3 and r.get("protein") not in anchors:
            got = sum(1 for p in picked if p.get("protein") in anchors)
            if got + (n - len(picked) - 1) < max(1, n - 1):
                continue
        if relax < 1 and r.get("cuisine") in cuisines:
            continue
        # At most one dinner a week that doesn't pack. Each one costs two lunch slots
        # (both eaters, the next day), and four dinners are what pay for ten weekday
        # lunches — two non-packing dinners in the same week starve the column and push
        # it onto assembly sandwiches. Relaxed second-to-last, ahead of only protein
        # repetition, because a soggy lunch box is still better than chicken twice.
        if relax < 3 and r.get("leftover_quality") == "none" and any(
                p.get("leftover_quality") == "none" for p in picked):
            continue
        if relax < 2:
            if r.get("effort") == "project" and any(p.get("effort") == "project" for p in picked):
                continue
            remaining = n - len(picked) - 1
            comfort = sum(1 for p in picked if p.get("register") == "comfort")
            if r.get("register") != "comfort" and comfort + remaining < 2:
                continue    # taking this would make 2 comfort dinners unreachable
            easy = any(p.get("effort") == "easy" for p in picked)
            if r.get("effort") != "easy" and not easy and remaining < 1:
                continue    # last slot must be the easy one
        picked.append(r)
        proteins.add(r.get("protein"))
        cuisines.add(r.get("cuisine"))
    return picked


def pick_lunches(pool, season, hist, cfg, rng):
    """Batch-cooked + five-minute lunches per meal_settings(), proteins spread."""
    ms = meal_settings(cfg)
    if ms["n_lunches"] == 0:
        return [], []
    for widen, cd in _attempts("lunches"):
        cands = eligible(pool, season, hist, "lunches", cfg, widen, cd)
        prep = [r for r in cands if r.get("lunch_style") == "sunday-prep"]
        asm = [r for r in cands if r.get("lunch_style") == "assembly"]
        out = _spread(prep, ms["n_prep"], rng) + _spread(asm, ms["n_assembly"], rng)
        if len(out) == ms["n_lunches"]:
            notes = []
            if widen:
                notes.append(f"lunches reached into neighbouring seasons (±{widen})")
            return out, notes
    raise PlanError(
        f"No workable lunch set: need {N_PREP_LUNCHES} sunday-prep and "
        f"{N_ASSEMBLY_LUNCHES} assembly recipes and the library cannot supply them. "
        f"Add files to data/recipes/lunches/.")


def _spread(cands, n, rng):
    """Pick n, preferring distinct proteins, then falling back to any."""
    order = list(cands)
    rng.shuffle(order)
    picked, seen = [], set()
    for r in order:
        if len(picked) == n:
            break
        if r.get("protein") in seen:
            continue
        picked.append(r)
        seen.add(r.get("protein"))
    for r in order:                      # top up if proteins were too concentrated
        if len(picked) == n:
            break
        if r not in picked:
            picked.append(r)
    return picked[:n]


def pick_drink(pool, season, hist, cfg, rng):
    """Season-appropriate, gear-appropriate, not served in COOLDOWN['coffee'] weeks."""
    gear = set(cfg.get("gear") or [])
    for widen, cd in _attempts("coffee"):
        cands = [d for d in eligible(pool, season, hist, "coffee", cfg, widen, cd)
                 if not gear or (set(d.get("gear") or []) & gear)]
        if cands:
            return rng.choice(sorted(cands, key=lambda d: d["slug"]))
    # Cooldown has eaten the whole pool: fall back to the least recently served.
    ranked = sorted(pool, key=lambda d: (L.weeks_since(hist, "coffee", d["slug"]) or 999),
                    reverse=True)
    return ranked[0]


def pick_coffee_week(drinks, syrups, crumbles, season, hist, cfg, rng):
    """
    Two featured drinks a week, each with ITS OWN syrup and a crumble that suits it.

    A reader, on a card: "why does the recipe card title one flavor syrup but then list
    an unrelated one? eg Miso Caramel Latte says to use syrup: Rosemary honey syrup.
    makes no sense."

    It made no sense because the syrup was matched on TEMPERATURE, not flavour. A syrup's
    `pairs_with` mixes temperatures with drink and crumble slugs, so the test was whether
    the drink's `temp` string appeared in that list — and "either" appears in none of
    them, so every `temp: either` drink fell through to the catch-all and took whichever
    stocked syrup sorted first alphabetically. Miso caramel latte got rosemary honey.

    The deeper error was the model. Every drink in this library already makes its own
    flavouring inline — a brown butter syrup, a chai concentrate, a ganache, the miso
    caramel itself — so there was never a free slot to fill. Bolting a second, unrelated
    syrup on printed two chores for a drink that needed one, and named the wrong one.

    So the syrup is now the drink's, declared in its frontmatter and not chosen at all.
    Where the box holds that exact syrup, the drink points at it, and the "already in the
    box, keeps 5 weeks" economics still work. Where the drink makes something the box has
    no equivalent for (horchata is a milk, a mocha wants melted chocolate rather than
    syrup), `syrup: null` and the card just carries the drink's own method.

    The CRUMBLE stays a free variable, because that is genuinely what a crumble is —
    sugar and nuts scattered on top. It is picked from the drink's own shortlist, so
    pistachio rose never lands on a Vietnamese iced coffee. Two drinks list none at all:
    a crumble sinks in an iced tonic and in a glass of condensed milk, and saying so is
    better than finding a plausible-looking wrong answer.
    """
    n = int(cfg.get("drinks_per_week") or 2)
    by_slug = {x["slug"]: x for x in syrups}
    have = {x["slug"]: x for x in crumbles}
    picked, used = [], set()
    for i in range(n):
        drink = pick_drink([d for d in drinks if d["slug"] not in {p["drink"]["slug"] for p in picked}]
                           or drinks, season, hist, cfg, rng)
        syrup = by_slug.get(drink.get("syrup")) if drink.get("syrup") else None
        # The drink's shortlist is written best-first, so it is walked in order rather
        # than shuffled: a crumble already stocked wins, then the drink's own first
        # choice. Skip one the other drink took, unless that leaves nothing.
        want = [have[c] for c in (drink.get("crumbles") or []) if c in have]
        fresh = [c for c in want if c["slug"] not in used] or want
        stocked = [c for c in fresh if not L.needs_making(c, hist, "crumbles")[0]]
        crumble = (stocked or fresh or [None])[0]
        if crumble:
            used.add(crumble["slug"])
        picked.append({
            "drink": drink, "syrup": syrup, "crumble": crumble,
            "syrup_needed": L.needs_making(syrup, hist, "syrups") if syrup else (False, None),
            "crumble_needed": L.needs_making(crumble, hist, "crumbles") if crumble else (False, None),
        })
    return picked


def _unique_moves(moves):
    seen, uniq = set(), []
    for m in moves:
        k = L.normalize(m["item"])
        if k not in seen:
            seen.add(k)
            uniq.append(m)
    return uniq


def _unique(items):
    """Preserve order, drop repeats and Nones, keyed on slug."""
    out, seen = [], set()
    for x in items:
        if x and x["slug"] not in seen:
            seen.add(x["slug"])
            out.append(x)
    return out


def pick_quote(quotes, hist, rng):
    """Never repeat until the pool is exhausted, then start the cycle again."""
    used = {q for wk in hist.get("weeks", []) for q in [wk.get("quote")] if q}
    fresh = [q for q in quotes if q["id"] not in used]
    return rng.choice(sorted(fresh or quotes, key=lambda q: q["id"]))


# ---------------------------------------------------------------- lunch ledger

def build_ledger(dinners, lunches, cfg=None):
    """
    Work out, concretely, what each person eats for lunch Monday to Friday.

    Supply, in priority order:
      1. leftovers from a dinner cooked in the previous LEFTOVER_WINDOW days (freshest
         first) — this is what the 4 dinners exist to produce
      2. servings from the Sunday-prepped batch lunches
      3. a 5-minute assembly lunch, made that morning

    Returns (grid, stats) where grid is a list of one row per weekday.
    """
    ms = meal_settings(cfg)
    if ms["lunch_mode"] == "none":
        return [], {"leftovers": 0, "prep": 0, "assembly": 0, "total": 0, "filled": 0}
    # leftover servings, tagged with the night they were cooked. In `fresh` mode dinners
    # are cooked for the table only, so there are none to pool.
    pool = []
    if ms["lunch_mode"] == "leftovers":
        for night, d in zip(ms["cook_nights"], dinners):
            for _ in range(int(d.get("leftovers") or 0)):
                pool.append({"night": night, "recipe": d})

    prep = [r for r in lunches if r.get("lunch_style") == "sunday-prep"]
    asm = [r for r in lunches if r.get("lunch_style") == "assembly"]
    prep_left = [[r, int(r.get("makes") or 0)] for r in prep]

    grid, counts = [], {"leftovers": 0, "prep": 0, "assembly": 0}
    asm_i = 0
    for di, day in enumerate(LUNCH_DAYS):
        # Every day also names a 5-minute swap. Leftovers cover most slots, but "I don't
        # want that again" is a real thing and it is exactly how a plan gets abandoned —
        # so the escape hatch is scheduled, not improvised.
        swap = asm[di % len(asm)] if asm else None
        row = {"day": DAYS[day], "slots": [],
               "swap": swap["title"] if swap else None,
               "swap_time": (swap.get("active_time") if swap else None)}
        # Who gets FIRST pick rotates by day. With the usual 2 leftover servings a night
        # both eaters get one and the order is invisible — but a meal-kit box leaves only
        # one, and then a fixed order hands the first eater every single leftover of the
        # week and the second the batch container seven days running. Same parity trap as the batch
        # rotation below, one level up.
        pick_order = [(i, EATERS[i]) for i in range(len(EATERS))]
        pick_order = pick_order[di % len(EATERS):] + pick_order[:di % len(EATERS)]
        for ei, eater in pick_order:
            fresh = sorted(
                [p for p in pool if 0 < day - p["night"] <= LEFTOVER_WINDOW],
                key=lambda p: -p["night"])          # freshest first
            if fresh:
                take = fresh[0]
                pool.remove(take)
                counts["leftovers"] += 1
                row["slots"].append({
                    "eater": eater, "kind": "leftovers",
                    "what": take["recipe"]["title"],
                    "note": f"from {DAYS[take['night']]} night"})
                continue
            # Rotate the batches by (day + eater) rather than draining one dry. A plain
            # counter aligns with the two-eater parity and hands the same person the same
            # container every time.
            avail = None
            if prep_left and di < PREP_LASTS_DAYS:
                order = len(prep_left)
                for k in range(order):
                    cand = prep_left[(di + ei + k) % order]
                    if cand[1] > 0:
                        avail = cand
                        break
            if avail:
                avail[1] -= 1
                counts["prep"] += 1
                row["slots"].append({"eater": eater, "kind": "prep",
                                     "what": avail[0]["title"],
                                     "note": f"batch-prepped Sunday, day {di + 1}"})
                continue
            if asm:
                r = asm[asm_i % len(asm)]
                asm_i += 1
                counts["assembly"] += 1
                row["slots"].append({"eater": eater, "kind": "assembly",
                                     "what": r["title"],
                                     "note": f"{r.get('active_time', 5)} min, day-of"})
                continue
            row["slots"].append({"eater": eater, "kind": "gap", "what": "—",
                                 "note": "nothing scheduled"})
        row["slots"].sort(key=lambda sl: EATERS.index(sl["eater"]))
        grid.append(row)

    used_swaps = {r["day"]: r["swap"] for r in grid if r["swap"]}
    total = len(LUNCH_DAYS) * len(EATERS)
    stats = {
        "total_slots": total,
        "leftover_servings": sum(int(d.get("leftovers") or 0) for d in dinners),
        "unused_leftovers": len(pool),
        **counts,
        "leftover_share": counts["leftovers"] / total if total else 0,
        "swaps_offered": len(set(used_swaps.values())),
    }
    return grid, stats


# ---------------------------------------------------------------- shopping list

def _strip_fallback(line):
    """Drop `|| fallback` from a line but keep its [kind] tag."""
    m = re.search(r"\s*\[([a-z]+)\]\s*$", line)
    tag = f" [{m.group(1)}]" if m else ""
    head = (line[:m.start()] if m else line).split("||")[0].strip()
    return head + tag


def route_to_stores(recipes, month):
    """
    Decide which shop each ingredient comes from, per the household's config/stores.yml.

    An ingredient goes to the FIRST store in visit order whose `takes:` covers its kind.
    A farmers market is additionally checked against its availability model for this
    month — a lemon in Washington, a pepper in February — and when it can't credibly stock
    the thing the ingredient moves on to the next store, with the reason kept so the
    newsletter can print it and the model can be corrected by the person who actually
    goes. The `|| fallback` is dropped when that happens: a fallback exists because a
    stall might be out, and a supermarket will not be.

    Exactly one store takes `everything`, which config validation enforces, so every
    ingredient lands somewhere. Nothing silently vanishes.

    Returns (routed_recipes, moves). Each routed recipe is a shallow copy carrying
    `_by_store: {store_id: [line, ...]}`; the originals are not mutated.
    """
    stores = C.stores()
    avail = L.load_market_availability()
    seasonal = L.load_seasonal()
    out, moves = [], []
    for r in recipes:
        by = {st["id"]: [] for st in stores}
        for line in L.ingredients(r):
            item = L.parse_item(line)
            if not item["name"]:
                continue
            kind = item["kind"] or "pantry"     # untagged -> the safe default; a test forbids it
            bounced = False
            for st in stores:
                if not C.takes(st, kind):
                    continue
                # The shop takes this kind of thing but has said it never carries this
                # particular thing: move on, line intact. The catch-all takes everything
                # and validation makes sure there is one.
                if C.never_stocks(st, item["key"]) and C.EVERYTHING not in st["takes"]:
                    continue
                if st.get("kind") == "farmers_market":
                    ok, why = L.market_has(item["key"], month, avail, seasonal)
                    if not ok:
                        moves.append({"item": item["name"], "why": why,
                                      "recipe": r["title"], "store": st["name"]})
                        bounced = True
                        continue
                by[st["id"]].append(_strip_fallback(line) if bounced else line)
                break
        clone = dict(r)
        clone["_by_store"] = by
        out.append(clone)
    # De-duplicate: the same lemon moved by three recipes is one line of explanation.
    seen, uniq = set(), []
    for m in moves:
        k = L.normalize(m["item"])
        if k not in seen:
            seen.add(k)
            uniq.append(m)
    return out, uniq


def _store_sub(st):
    """The grey line under a store's name on the list."""
    if st.get("kind") == "farmers_market":
        return " \u00b7 ".join(x for x in (st.get("when"), st.get("where")) if x)
    return st.get("sub") or ""


def build_shopping_list(recipes):
    """
    Consolidate every ingredient across the week's recipes, grouped by store in visit
    order, with the four true pantry staples suppressed and everything else it leans on
    gathered into a "Check the cupboard" group.

    Quantities sum when the unit matches; mismatched units for the same ingredient are
    kept as separate lines rather than silently guessing a conversion (2 lb + 3 cups of
    the same thing is not a number anyone should invent).
    """
    staples, rotation = L.load_pantry()
    shared = L.load_shared_items()
    out = []
    for st in C.stores():
        store, label, sub = st["id"], st["name"], _store_sub(st)
        # Keyed by INGREDIENT NAME, with units tracked inside it. Keying on (name, unit)
        # split "1 packet culinary lavender" from a bare "culinary lavender" into two
        # lines for the same jar. A bare mention — no quantity, no unit — is absorbed into
        # whatever quantified entry exists; two genuinely different units with real
        # quantities still get separate lines, because 2 lb + 3 cups of the same thing is
        # not a number anyone should invent.
        bucket = {}
        for r in recipes:
            if "_by_store" not in r:
                raise ValueError(f"{r.get('slug')}: build_shopping_list needs routed "
                                 f"recipes — call route_to_stores first")
            for line in r["_by_store"].get(store) or []:
                item = L.parse_item(str(line))
                if not item["name"] or L.is_pantry(item, staples, rotation):
                    continue
                b = bucket.setdefault(item["key"], {
                    "name": item["name"], "units": {}, "bare": False,
                    "fallbacks": [], "used_in": []})
                if item["qty"] is None and item["unit"] is None:
                    b["bare"] = True
                else:
                    u = item["unit"]
                    q = (item["qty"] or 0) * float(r.get("_scale") or 1)
                    # Sum what gets consumed in proportion to how much you cook; take the
                    # LARGEST single requirement for anything one purchase covers. Three
                    # recipes each wanting "1 bunch cilantro" need one bunch, not three,
                    # and a jar of pickled jalapenos that keeps for months was being
                    # bought once per recipe that mentioned it.
                    if any(k in item["key"] or item["key"] in k for k in shared):
                        b["units"][u] = max(b["units"].get(u) or 0, q)
                    else:
                        b["units"][u] = (b["units"].get(u) or 0) + q
                if len(item["name"]) < len(b["name"]):
                    b["name"] = item["name"]        # prefer the plainest wording
                if item["fallback"] and item["fallback"] not in b["fallbacks"]:
                    b["fallbacks"].append(item["fallback"])
                if r["title"] not in b["used_in"]:
                    b["used_in"].append(r["title"])

        lines = []
        for b in bucket.values():
            if not b["units"]:                       # only ever mentioned bare
                lines.append({"name": b["name"], "unit": None, "qty": None,
                              "fallbacks": b["fallbacks"], "used_in": b["used_in"]})
                continue
            for unit, qty in sorted(b["units"].items(), key=lambda kv: (kv[0] or "")):
                lines.append({"name": b["name"], "unit": unit, "qty": qty or None,
                              "fallbacks": b["fallbacks"], "used_in": b["used_in"]})
        out.append({"store": store, "label": label, "sub": sub,
                    "lines": sorted(lines, key=lambda x: x["name"].lower())})

    # Everything a recipe leans on that is not one of the four true staples. It is not
    # routed to a store, because nobody is walking to the spice aisle for cumin they
    # already own — the point is that it is VISIBLE, in one place, before leaving, so
    # the shopper can decide. Previously this was silently assumed and a recipe could call for
    # hoisin, toasted sesame oil and rice vinegar without any of the three appearing
    # anywhere at all.
    on_a_list = {L.normalize(x["name"]) for g in out for x in g["lines"]}
    cupboard, seen_c = [], set()
    for r in recipes:
        for raw in r.get("pantry") or []:
            it = L.parse_item(str(raw))
            key = it["key"]
            if not key or key in seen_c or L.is_pantry(it, staples, rotation):
                continue
            if key in on_a_list:
                continue          # already being bought outright this week
            seen_c.add(key)
            cupboard.append({"name": it["name"], "unit": None, "qty": None,
                             "fallbacks": [], "used_in": [r["title"]]})
    for line in cupboard:
        for r in recipes:
            for raw in r.get("pantry") or []:
                if L.parse_item(str(raw))["key"] == L.normalize(line["name"]):
                    if r["title"] not in line["used_in"]:
                        line["used_in"].append(r["title"])
    # First, not last: this is the one group you act on at home, before leaving.
    out.insert(0, {"store": "cupboard", "label": "Check the cupboard",
                   "sub": "Not assumed \u2014 tick what you actually need before you go",
                   "lines": sorted(cupboard, key=lambda x: x["name"].lower())})

    # One ingredient, one store. Two recipes filing "pickled jalapenos" under different
    # stores put it on the Trader Joe's list AND the QFC list — three jars across two
    # shops, and the second one gets bought because the list said to. Whichever store
    # comes first in visit order keeps it.
    seen = {}
    for grp in out:
        keep = []
        for line in grp["lines"]:
            key = L.normalize(line["name"])
            if key in seen:
                first = seen[key]
                for u in line["used_in"]:
                    if u not in first["used_in"]:
                        first["used_in"].append(u)
                for f in line["fallbacks"]:
                    if f not in first["fallbacks"]:
                        first["fallbacks"].append(f)
                # Keep the larger requirement, in the units already on the earlier line.
                if line["unit"] == first["unit"] and line["qty"] and first["qty"]:
                    first["qty"] = max(first["qty"], line["qty"])
                continue
            seen[key] = line
            keep.append(line)
        grp["lines"] = keep
    return out


# ---------------------------------------------------------------- prep-ahead

def _market_tips(season):
    """One seasonal sourcing line, one evergreen one. Never more — nobody reads a wall."""
    data = L.load_market_vendors()
    tips = data.get("tips") or []
    seasonal = [t["text"] for t in tips if t.get("when") == season]
    evergreen = [t["text"] for t in tips if t.get("when") == "any"]
    return (seasonal[:1] + evergreen[:1])[:2]


def prep_note(dinners, lunches):
    """
    The one thing worth doing Sunday to make Wednesday easy.

    Preference order: a multi-hour project (it has to be a weekend anyway), then the
    batch lunches, then a make-ahead component from a dinner.
    """
    project = next((d for d in dinners if d.get("effort") == "project"), None)
    prep = [r for r in lunches if r.get("lunch_style") == "sunday-prep"]
    bits = []
    if project:
        bits.append(f"<b>{project['title']}</b> is the long one "
                    f"({project.get('total_time')} min, mostly unattended) — cook it Sunday "
                    f"while you're already in the kitchen, and it feeds you twice more.")
    if prep:
        names = " and ".join(f"<b>{r['title']}</b>" for r in prep)
        mins = sum(int(r.get("active_time") or 0) for r in prep)
        bits.append(f"Batch {names} — about {mins} minutes of work, and it covers every "
                    f"lunch the leftovers don't.")
    bits.append("Make a jar of quick-pickled red onions while you're at it. Half this "
                "library asks for them and they keep three weeks.")
    return bits


# ---------------------------------------------------------------- top level

def week_start(today):
    """
    The Monday after the Saturday send.

    Shopping and batch prep land on the Sunday in between, so Monday opens with the
    fridge already stocked and nothing to decide.
    """
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


def shop_day(start):
    """Market day — the Sunday before the week opens."""
    return start - timedelta(days=1)


def external_dinner(night_index, label, leftovers=1):
    """
    A dinner that arrives already shopped for — a meal-kit box, a gift, a freezer stash.

    It occupies a cooking night and it feeds the lunch ledger, but it contributes NOTHING
    to the shopping list, because its ingredients are already in the house. That is the
    whole point: `build_shopping_list` reads its ingredients, and an external dinner has none.

    `leftovers` is what it actually yields, which is not the library's default of 2. A
    meal-kit box for two leaves about one portion per meal — the household's number, not
    an estimate — so assuming 2 would silently promise three lunches that don't exist.
    """
    return {
        "slug": f"external-{night_index}",
        "title": label,
        "external": True,
        "serves": 2 + leftovers,
        "leftovers": leftovers,
        "leftover_quality": "fair",
        "active_time": None, "total_time": None,
        "protein": None, "cuisine": None, "effort": "easy", "register": "comfort",
        "seasons": [], "ingredients": [],
        "pantry": [], "per_plate": [], "body": "",
    }


def this_week_overrides(start, dinners, lunches, cfg):
    """
    Read data/this-week.yml for the week starting `start`. Anything for another week is
    ignored, so a preview of next month is not bent by this week's request. A slug that
    matches no recipe is an error, not a warning: silently planning the dish someone asked
    not to have is the exact failure this file exists to prevent.
    """
    ov = L.load_overrides()
    empty = {"skip": set(), "pin": []}
    if ov["week_of"] != start or not (ov["skip"] or ov["pin"]):
        return empty, []
    known = {r["slug"]: r for r in dinners + lunches}
    for slug in ov["skip"] + ov["pin"]:
        if slug not in known:
            raise PlanError(f"data/this-week.yml names {slug!r}, which is not a recipe in "
                            f"data/recipes/. Check the spelling (tools/this_week.py lists them).")
    both = set(ov["skip"]) & set(ov["pin"])
    if both:
        raise PlanError(f"data/this-week.yml both skips and pins {sorted(both)} — pick one")
    notes = []
    for slug in ov["pin"]:
        r = known[slug]
        if r.get("kind") == "lunch":
            raise PlanError(f"{slug} is a lunch; only dinners can be pinned this week")
        if _excluded(r, cfg):
            why = "rated too low to plan" if L.is_retired(r) else "excluded by the household diet"
            raise PlanError(f"{slug} is pinned this week but is {why}")
        notes.append(f"{r['title']} is on the menu because you asked for it this week")
    for slug in ov["skip"]:
        notes.append(f"{known[slug]['title']} was left out this week at your request")
    return {"skip": set(ov["skip"]), "pin": list(ov["pin"])}, notes


def build_plan(today, seed=None, box=None):
    """
    Assemble the whole week. Deterministic for a given (week, library, history).

    `box` describes dinners that arrive already shopped for, as
    {"count": 3, "label": "meal-kit box", "leftovers": 1}. They take the first
    cooking nights, the library fills what's left, and only the library dinners reach the
    shopping list. Used for the changeover week: the last meal-kit box covers Mon-Wed and
    the list only has to buy Thursday's dinner, the lunches and the coffee.
    """
    start = week_start(today)
    seasonal = L.load_seasonal()
    season = seasonal[start.month]["season"]
    cfg = L.load_household()
    hist = L.load_history()
    rng = random.Random(seed if seed is not None else start.toordinal())

    ms = meal_settings(cfg)
    n_box = int((box or {}).get("count") or 0)
    all_dinners, all_lunches = L.load_dinners(), L.load_lunches()
    ov, ov_notes = this_week_overrides(start, all_dinners, all_lunches, cfg)
    dinner_pool = [d for d in all_dinners if d["slug"] not in ov["skip"]]
    lunch_pool = [l for l in all_lunches if l["slug"] not in ov["skip"]]
    pinned = [d for d in all_dinners if d["slug"] in ov["pin"]]
    dinners, notes = pick_dinners(dinner_pool, season, hist, cfg, rng,
                                  n=max(ms["n_dinners"] - n_box, 0), pinned=pinned)
    notes = ov_notes + notes
    if n_box:
        label = (box or {}).get("label") or "Already in the house"
        left = int((box or {}).get("leftovers", 1))
        boxed = [external_dinner(i, f"{label} \u2014 meal {i + 1}", left)
                 for i in range(n_box)]
        # The box goes first: those meals are perishable and dated, and the one dinner
        # being shopped for on Sunday is the one that can wait until Thursday.
        dinners = boxed + dinners
        notes.append(
            f"{n_box} dinner{'s' if n_box > 1 else ''} came from the {label} — already "
            f"shopped for, so nothing for them is on the list. At {left} leftover serving"
            f"{'s' if left != 1 else ''} each they cover "
            f"{n_box * left} lunch slot{'s' if n_box * left != 1 else ''} instead of the "
            f"usual {n_box * 2}, so the rest of the week leans on the Sunday batch.")
    lunches, lnotes = pick_lunches(lunch_pool, season, hist, cfg, rng)
    coffee = pick_coffee_week(L.load_drinks(), L.load_syrups(), L.load_crumbles(),
                              season, hist, cfg, rng)
    quote = pick_quote(L.load_quotes(), hist, rng)

    if ms["table_only"]:
        # The recipe serves 4; the household eats for the table only. The list buys for
        # the eaters, the ledger gets no leftovers, and the card says to halve it.
        dinners = [dict(d, leftovers=0, _scale=len(EATERS) / max(int(d.get("serves") or 4), 1))
                   if not d.get("external") else d for d in dinners]
    grid, stats = build_ledger(dinners, lunches, cfg)
    # Only the syrups and crumbles that actually need making contribute to the list.
    # Everything else is already in the box.
    # Deduped: two drinks can want the same crumble, and one jar of espresso sugar makes
    # thirty drinks. "Make this week: Espresso sugar, Espresso sugar" was on a real send.
    to_make = _unique([c["syrup"] for c in coffee if c["syrup_needed"][0]]
                      + [c["crumble"] for c in coffee if c["crumble_needed"][0]])
    # Decide the shop for every ingredient BEFORE consolidating, so the store lists and
    # their quantities are right — and route the dinners and lunches themselves, so the
    # printed cards tag each line with the same shop the list sends you to.
    dinners, m1 = route_to_stores(dinners, start.month)
    lunches, m2 = route_to_stores(lunches, start.month)
    drinks, m3 = route_to_stores([c["drink"] for c in coffee], start.month)
    to_make, m4 = route_to_stores(to_make, start.month)
    for c, d in zip(coffee, drinks):
        c["drink"] = d
    moves = _unique_moves(m1 + m2 + m3 + m4)
    shoppable = [d for d in dinners if not d.get("external")]
    sources = shoppable + lunches + drinks + to_make
    shopping = build_shopping_list(sources)
    econ = L.load_coffee_economics()

    return {
        "week_start": start,
        "week_end": start + timedelta(days=6),
        "shop_day": shop_day(start),
        "season": season,
        "in_season": seasonal[start.month]["peak"],
        "dinners": dinners,
        "cook_nights": [DAYS[i] for i in ms["cook_nights"]],
        "meals": ms,
        "lunches": lunches,
        "ledger": grid,
        "ledger_stats": stats,
        "shopping": shopping,
        "market_moves": moves,
        "images": [(d["slug"], L.image_path(d["slug"]))
                   for d in dinners if L.image_path(d["slug"])],
        "boxed": [d for d in dinners if d.get("external")],
        "market": L.load_market_vendors(),
        "market_store": C.market_store(),
        "stores": C.stores(),
        "market_tips": _market_tips(season),
        "coffee": coffee,
        "drink": coffee[0]["drink"],          # kept for callers that want just the headline
        "to_make": to_make,
        "quote": quote,
        "econ": econ,
        "prep": prep_note(shoppable, lunches),
        "notes": notes + lnotes,
        "generated": today,
    }


def record(plan):
    """Append this week to history.json so rotation works next week."""
    hist = L.load_history()
    hist.setdefault("weeks", []).append({
        "week_of": plan["week_start"].isoformat(),
        "season": plan["season"],
        # Externals are placeholders for meals that came from somewhere else. Writing
        # "external-0" into history would put a slug in the rotation that matches no
        # recipe and can never come off cooldown.
        "dinners": [d["slug"] for d in plan["dinners"] if not d.get("external")],
        "lunches": [r["slug"] for r in plan["lunches"]],
        "coffee": [c["drink"]["slug"] for c in plan["coffee"]],
        # Recording these is what makes the box a library: next week knows the syrup is
        # already in the fridge and leaves its ingredients off the list.
        "syrups": [c["syrup"]["slug"] for c in plan["coffee"] if c["syrup_needed"][0]],
        "crumbles": [c["crumble"]["slug"] for c in plan["coffee"] if c["crumble_needed"][0]],
        "quote": plan["quote"]["id"],
    })
    L.save_history(hist)
    # The request was for this week and this week has now been sent. A stale file left
    # behind would silently bend a later week, so it is cleared here and nowhere else —
    # a --test send leaves it in place, exactly like history.
    ov = L.load_overrides()
    if ov["week_of"] and ov["week_of"] <= plan["week_start"]:
        L.clear_overrides()
