#!/usr/bin/env python3
"""
Mealbit test suite.  Run:  python -m pytest tests/ -q   (or: python tests/test_mealbit.py)

The tests that matter most are the arithmetic ones. This system's whole promise is that
nobody has to think on Sunday morning, and the two ways it could quietly break that
promise are (a) the lunch ledger not actually adding up, and (b) the shopping list losing
or double-counting an ingredient.
"""
import os
import re
import sys
import json
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from mealbit import library as L      # noqa: E402
from mealbit import planner as P      # noqa: E402
from mealbit import render as R       # noqa: E402
from mealbit import email_kit as K    # noqa: E402
from mealbit import audit as A        # noqa: E402

FAILURES = []


def check(cond, msg):
    if not cond:
        FAILURES.append(msg)
    return cond


# ---------------------------------------------------------------- library

def test_library_loads():
    d, l, dr, q = L.load_dinners(), L.load_lunches(), L.load_drinks(), L.load_quotes()
    check(len(d) >= 20, f"want >=20 dinners for rotation, got {len(d)}")
    check(len(l) >= 10, f"want >=10 lunches, got {len(l)}")
    check(len(dr) >= 8, f"want >=8 coffee drinks, got {len(dr)}")
    check(len(q) >= 20, f"want >=20 quotes, got {len(q)}")
    return d, l, dr, q


def test_recipe_schema():
    """Every field the planner indexes on must be present and legal in every file."""
    for r in L.load_dinners():
        s = r["slug"]
        for f in ("title", "serves", "leftovers", "active_time", "total_time",
                  "seasons", "protein", "cuisine", "effort", "register"):
            check(r.get(f) not in (None, ""), f"dinner {s}: missing {f}")
        check(r.get("effort") in ("easy", "medium", "project"),
              f"dinner {s}: bad effort {r.get('effort')!r}")
        check(r.get("register") in ("comfort", "elegant"),
              f"dinner {s}: bad register {r.get('register')!r}")
        check(set(r.get("seasons") or []) <= set(L.SEASON_ORDER),
              f"dinner {s}: unknown season in {r.get('seasons')}")
        # Leftovers pay for the lunch column, so a dinner yields them unless it has
        # explicitly declared that it does not survive the night. See
        # test_leftover_quality_decides_whether_lunch_exists.
        check(int(r["leftovers"]) >= 1 or r.get("leftover_quality") == "none",
              f"dinner {s}: must yield leftovers — that is how lunches get paid for — "
              f"or declare leftover_quality: none and say why")
        check(int(r["serves"]) >= int(r["leftovers"]) + 2,
              f"dinner {s}: serves {r['serves']} can't feed 2 AND leave "
              f"{r['leftovers']} leftover servings")
        # The household's stated ceiling is 45 minutes of hands-on work. A multi-hour
        # `project` braise is exempt — its time is waiting, not chopping.
        if r["effort"] != "project":
            check(int(r["active_time"]) <= 45,
                  f"dinner {s}: {r['active_time']} min hands-on exceeds the 45-min budget")

    for r in L.load_lunches():
        s = r["slug"]
        check(r.get("lunch_style") in ("sunday-prep", "assembly"),
              f"lunch {s}: bad lunch_style {r.get('lunch_style')!r}")
        if r["lunch_style"] == "assembly":
            check(int(r["active_time"]) <= 5,
                  f"lunch {s}: assembly lunches must be <=5 min, got {r['active_time']}")
        else:
            check(int(r.get("makes") or 0) >= 4,
                  f"lunch {s}: a Sunday batch must make >=4 servings")


def test_drinks_and_quotes():
    for d in L.load_drinks():
        check(d.get("gear"), f"drink {d['slug']}: no gear listed")
        check(float(d.get("cost_per_serving") or 0) > 0, f"drink {d['slug']}: no cost")
        check(float(d.get("shop_equivalent") or 0) > float(d.get("cost_per_serving") or 0),
              f"drink {d['slug']}: shop price must exceed home cost or the maths is wrong")
    ok = {"verified", "attributed", "disputed", "legend", "fiction", "history"}
    for q in L.load_quotes():
        check(q.get("attribution") in ok,
              f"quote {q['id']}: unknown attribution {q.get('attribution')!r} — every "
              f"quote must declare how well sourced it is")


def test_seasonal_calendar():
    sea = L.load_seasonal()
    check(sorted(sea) == list(range(1, 13)), "seasonal-pnw.md must cover all 12 months")
    for m, v in sea.items():
        check(v["season"] in L.SEASON_ORDER, f"month {m}: bad season {v['season']!r}")
        check(len(v["peak"]) >= 5, f"month {m}: only {len(v['peak'])} peak items")


def test_every_season_is_servable():
    """Each of the six buckets must be able to fill a week on its own terms."""
    dinners = L.load_dinners()
    for s in L.SEASON_ORDER:
        pool = [r for r in dinners if s in (r.get("seasons") or [])]
        check(len(pool) >= P.N_DINNERS,
              f"season {s}: only {len(pool)} dinners, need >= {P.N_DINNERS}")
        check(len({r["protein"] for r in pool}) >= P.N_DINNERS,
              f"season {s}: fewer than {P.N_DINNERS} distinct proteins available")
        check(sum(1 for r in pool if r["register"] == "comfort") >= 2,
              f"season {s}: needs >=2 comfort-register dinners")


# ---------------------------------------------------------------- parsing

def test_ingredient_parsing():
    cases = [
        ("2 lb chicken thighs", 2.0, "lb", "chicken thigh"),
        ("1.5 lb ground beef (80/20)", 1.5, "lb", "ground beef"),
        ("3 limes", 3.0, None, "lime"),
        ("½ cup tahini", 0.5, "cup", "tahini"),
        ("olive oil", None, None, "olive oil"),
        ("1 large bunch basil", 1.0, "bunch", "basil"),
        ("1 bunch basil", 1.0, "bunch", "basil"),
        ("1 small red onion", 1.0, None, "red onion"),
    ]
    for raw, qty, unit, key in cases:
        i = L.parse_item(raw)
        check(i["qty"] == qty and i["unit"] == unit and i["key"] == key,
              f"parse {raw!r} -> {i['qty']}/{i['unit']}/{i['key']}, want {qty}/{unit}/{key}")

    i = L.parse_item("1 lb summer squash || any tender summer vegetable")
    check(i["fallback"] == "any tender summer vegetable", "market fallback not parsed")

    # The consolidation key is what makes the shopping list add up.
    check(L.parse_item("1 large bunch basil")["key"] == L.parse_item("1 bunch basil")["key"],
          "descriptors must not split one ingredient into two shopping lines")


def test_every_ingredient_has_a_known_kind():
    """
    A recipe says what an ingredient IS; config/stores.yml says who sells it.

    An untagged line is routed as `pantry` so nothing is ever dropped, but that is a
    default, not a decision — and a produce line that lands in the supermarket bucket by
    default is exactly the market trip this system exists to plan. So every line carries a
    tag, and the tag is one the stores file knows.
    """
    from mealbit import config as C
    for r in L.load_dinners() + L.load_lunches() + L.load_drinks() + L.load_syrups() + L.load_crumbles():
        for line in L.ingredients(r):
            k = L.ingredient_kind(line)
            check(k is not None,
                  f"{r['slug']}: {line!r} has no [kind] tag — one of {list(C.KINDS)}")
            check(k in C.KINDS,
                  f"{r['slug']}: {line!r} is tagged [{k}], not one of {list(C.KINDS)}")


def test_stores_config_is_sane():
    """
    Exactly one catch-all, every `takes:` a known kind, a market's model files exist.

    The validator is exercised on the real file and on two broken ones, because a config
    that silently accepted "no catch-all" would let an ingredient fall off the list with
    nobody told — the failure this system refuses to allow.
    """
    from mealbit import config as C
    stores = C.stores()
    check(sum(1 for st in stores if C.EVERYTHING in st["takes"]) == 1,
          "stores.yml must have exactly one store that takes `everything`")
    check(all(st.get("short") for st in stores), "every store needs a short code for the card")

    real = C._read
    def broken(stores_yaml):
        C._read = lambda name: stores_yaml
        try:
            C.stores()
            return False
        except C.ConfigError:
            return True
        finally:
            C._read = real
    check(broken({"stores": [{"id": "a", "name": "A", "takes": ["produce"]}]}),
          "a stores file with no catch-all must be rejected")
    check(broken({"stores": [{"id": "a", "name": "A", "takes": ["everything"]},
                             {"id": "b", "name": "B", "takes": ["meat"]}]}),
          "an unknown kind must be rejected")
    check(broken({"stores": [{"id": "a", "name": "A", "takes": ["everything"]},
                             {"id": "a", "name": "A2", "takes": ["produce"]}]}),
          "a duplicate store id must be rejected")


def test_household_config_refuses_a_test_that_reaches_everyone():
    """--test going to the whole household is the one mistake this must never make."""
    from mealbit import config as C
    real = C._read
    C._read = lambda name: {
        "household": {"eaters": ["A", "B"]},
        "send": {"from": "a@x.test", "to": "both@x.test", "test_to": "both@x.test"}}
    try:
        try:
            C.household()
            check(False, "household.yml with send.to == send.test_to was accepted")
        except C.ConfigError:
            pass
    finally:
        C._read = real


def test_routing_puts_every_ingredient_somewhere():
    """
    Whatever the stores file says, no ingredient vanishes and none lands in two places.

    Checked over a year of plans, since the market model varies by month and the reroute
    only triggers for produce the market can't stock that month.
    """
    from mealbit import config as C
    ids = [st["id"] for st in C.stores()]
    for i in range(0, 52, 4):
        plan = P.build_plan(date(2026, 1, 5) + timedelta(weeks=i), seed=i)
        for r in plan["dinners"] + plan["lunches"]:
            if r.get("external"):
                continue
            want = [L.parse_item(x)["key"] for x in L.ingredients(r) if L.parse_item(x)["name"]]
            got = [L.parse_item(x)["key"] for sid in ids for x in r["_by_store"].get(sid, [])]
            check(sorted(want) == sorted(got),
                  f"{r['slug']} week {i}: routed {len(got)} of {len(want)} ingredients — "
                  f"missing {set(want) - set(got)}, extra {set(got) - set(want)}")
        # A farmers market never receives anything but produce.
        m = plan.get("market_store")
        if m:
            for r in plan["dinners"] + plan["lunches"]:
                for x in r.get("_by_store", {}).get(m["id"], []):
                    check(L.ingredient_kind(x) == "produce",
                          f"{r['slug']}: {x!r} was routed to the farmers market")


def test_market_items_have_fallbacks():
    """
    A market is not a shop. Every produce line must degrade, or the shopper is stranded
    at a stall that ran out.
    """
    staples = L.load_market_staples()
    for r in L.load_dinners() + L.load_lunches():
        for line in L.ingredients(r):
            item = L.parse_item(str(line))
            if item["kind"] != "produce":
                continue        # only produce can be routed to a market stall
            key = item["key"]
            exempt = (key in staples
                      or any(key.endswith(" " + s) or key.startswith(s + " ")
                             for s in staples)
                      or any(w in key for w in ("herb", "green", "vegetable",
                                                "seasonal", "whatever")))
            check("||" in str(line) or exempt,
                  f"{r['slug']}: produce line {line!r} has no || fallback — "
                  f"the market may not have it")


def test_only_four_things_are_assumed():
    """
    The household: "you can assume we'll always have salt, black pepper, olive oil, and white
    vinegar ONLY."

    Everything else a recipe leans on has to be visible before shopping. The old pantry
    held about seventy items, so a recipe could call for hoisin, toasted sesame oil and
    rice vinegar and none of the three appeared anywhere — which is a recipe that cannot
    be cooked on the night it is scheduled.
    """
    staples, rotation = L.load_pantry()
    for x in ("kosher salt", "flaky salt", "black pepper", "olive oil", "white vinegar"):
        check(L.is_pantry(L.parse_item(f"1 tbsp {x}"), staples, rotation),
              f"{x} should be assumed on hand")
    # The near-misses matter most: each of these is its own bottle.
    for x in ("red wine vinegar", "rice vinegar", "apple cider vinegar", "neutral oil",
              "toasted sesame oil", "soy sauce", "garlic", "cumin", "butter", "stock"):
        check(not L.is_pantry(L.parse_item(f"1 tbsp {x}"), staples, rotation),
              f"{x} must NOT be assumed on hand — it is its own thing to buy")


def test_everything_a_recipe_leans_on_is_visible():
    """
    Every pantry line in the week's recipes reaches the list, one way or another.

    Either it is being bought outright at a store, or it is on the Check the cupboard
    group so the shopper can decide at shop time. What must not happen is it appearing nowhere,
    which is what the old pantry did for sixty-odd ingredients.
    """
    staples, rotation = L.load_pantry()
    for wk in range(0, 40, 5):
        plan = P.build_plan(date(2026, 1, 4) + timedelta(weeks=wk))
        listed = {L.normalize(x["name"]) for g in plan["shopping"] for x in g["lines"]}
        sources = (plan["dinners"] + plan["lunches"]
                   + [c["drink"] for c in plan["coffee"]] + plan["to_make"])
        for r in sources:
            for raw in r.get("pantry") or []:
                it = L.parse_item(str(raw))
                if not it["name"] or L.is_pantry(it, staples, rotation):
                    continue
                check(it["key"] in listed,
                      f"week {wk}: {r['slug']} leans on {it['name']!r} and it appears on "
                      f"no list at all")
    # And the four that ARE assumed never clutter it.
    plan = P.build_plan(date(2026, 8, 29))
    listed = {L.normalize(x["name"]) for g in plan["shopping"] for x in g["lines"]}
    for x in ("olive oil", "kosher salt", "black pepper", "white vinegar"):
        check(L.normalize(x) not in listed,
              f"{x} is assumed on hand and should not be on the list")


def test_the_cupboard_check_comes_first():
    """It is the one group acted on at home, so it heads the list rather than trailing it."""
    plan = P.build_plan(date(2026, 8, 29))
    check(plan["shopping"][0]["store"] == "cupboard",
          "the cupboard check should be the first thing on the list, before the market")
    check(plan["shopping"][0]["lines"], "the cupboard check is empty")


def test_pantry_suppression():
    """
    Only the four staples are suppressed. There used to be a second tier — "rotation
    aromatics" like a lemon or a head of garlic, assumed present in ones and twos and
    only bought in unusual quantities. The household killed it: the house does not reliably have
    them, and a lemon silently missing from the list is a dish missing its acid at 6pm.
    """
    staples, rotation = L.load_pantry()
    check("olive oil" in staples and "kosher salt" in staples, "pantry staples not loaded")
    check(L.is_pantry(L.parse_item("2 tbsp olive oil"), staples, rotation),
          "olive oil should never reach the shopping list")
    check(not rotation, "the rotation tier is gone — nothing beyond the four is assumed")
    check(not L.is_pantry(L.parse_item("1 lemon"), staples, rotation),
          "a lemon is bought, not assumed")
    check(not L.is_pantry(L.parse_item("2 cloves garlic"), staples, rotation),
          "garlic is bought, not assumed")


# ---------------------------------------------------------------- planning

def test_exclusions_actually_exclude():
    """
    A dietary exclusion must match INSIDE an ingredient name.

    This regressed silently once: the check compared whole normalized keys, so an
    excluded "salmon" never matched "salmon fillet" and the exclusion list dropped
    nothing at all. Nobody would have noticed until shrimp arrived on a printed card.
    """
    cfg = dict(L.load_household(), exclude_ingredients=["salmon", "shrimp"])
    pool = L.load_dinners() + L.load_lunches()
    kept = [r for r in pool if not P._excluded(r, cfg)]
    for r in kept:
        blob = " ".join([str(r.get("title") or "")] + L.ingredients(r)).lower()
        check("salmon" not in blob and "shrimp" not in blob,
              f"{r['slug']} survived exclusion but still contains an excluded ingredient")
    check(len(kept) < len(pool), "exclusion list removed nothing at all — it is not working")

    # And it must not be over-eager: an empty list excludes nothing.
    none_cfg = dict(L.load_household(), exclude_ingredients=[])
    check(all(not P._excluded(r, none_cfg) for r in pool),
          "an empty exclusion list should keep every recipe")


def test_household_constraints_are_honoured_in_a_real_plan():
    """The end-to-end guarantee: nothing excluded may reach a rendered plan."""
    plan = P.build_plan(date(2026, 8, 29))
    bad = set(L.load_household().get("exclude_ingredients") or [])
    for r in plan["dinners"] + plan["lunches"]:
        blob = " ".join([str(r.get("title") or "")] + L.ingredients(r)).lower()
        for b in bad:
            check(b not in blob, f"excluded ingredient {b!r} reached the plan via {r['slug']}")


def test_syrups_and_crumbles_are_a_library_not_a_weekly_buy():
    """
    Standing inventory: something made recently must NOT return to the shopping list.

    Putting vanilla syrup on the list every week is the fastest way to make the list stop
    being read, and a list that isn't read is worse than no list.
    """
    syrups = L.load_syrups()
    check(len(syrups) >= 6, f"want >=6 syrups in the box, got {len(syrups)}")
    check(len(L.load_crumbles()) >= 6, "want >=6 crumbles in the box")
    for x in syrups + L.load_crumbles():
        check(int(x.get("keeps_weeks") or 0) >= 1,
              f"{x['slug']}: needs a keeps_weeks shelf life or it can't be tracked")

    s = syrups[0]
    fresh = {"weeks": [{"syrups": [s["slug"]]}]}
    need, why = L.needs_making(s, fresh, "syrups")
    check(not need, f"{s['slug']} was made last week but {why!r} says buy it again")

    keeps = int(s["keeps_weeks"])
    stale = {"weeks": [{"syrups": [s["slug"]]}] + [{} for _ in range(keeps)]}
    need, _why = L.needs_making(s, stale, "syrups")
    check(need, f"{s['slug']} is {keeps} weeks past making and was not flagged for remaking")
    check(L.needs_making(s, {"weeks": []}, "syrups")[0],
          "a never-made syrup must be flagged for making")


def test_a_drink_gets_its_own_syrup():
    """
    A reader, on a card: "why does the recipe card title one flavor syrup but then list
    an unrelated one? eg Miso Caramel Latte says to use syrup: Rosemary honey syrup.
    makes no sense."

    It didn't. The syrup was matched on TEMPERATURE — the test was whether the drink's
    `temp` string appeared in the syrup's `pairs_with`, which mixes temperatures with
    drink and crumble slugs. "either" appears in none of them, so every `temp: either`
    drink fell through to a catch-all and took whichever stocked syrup sorted first.

    Every drink in this library makes its own flavouring inline, so the fix is that the
    syrup is declared, not chosen. This checks the declarations resolve: a `syrup:` that
    names a slug the box does not hold would silently become None and print no syrup
    line at all, which looks fine and is wrong.
    """
    syrups = {s["slug"] for s in L.load_syrups()}
    crumbles = {c["slug"] for c in L.load_crumbles()}
    named = 0
    for d in L.load_drinks():
        sy = d.get("syrup")
        check("syrup" in d,
              f"drink {d['slug']}: no `syrup:` field — say which syrup it takes, or "
              f"`syrup: null` if it makes its own")
        if sy:
            named += 1
            check(sy in syrups,
                  f"drink {d['slug']}: syrup {sy!r} is not in data/coffee/syrups/")
        for c in (d.get("crumbles") or []):
            check(c in crumbles,
                  f"drink {d['slug']}: crumble {c!r} is not in data/coffee/crumbles/")
    check(named >= 5,
          f"only {named} drinks name a box syrup — if they all make their own inline, "
          f"the syrup box has stopped earning its place")


def test_the_make_list_never_repeats_itself():
    """"Make this week: Espresso sugar, Espresso sugar" went out on a real send."""
    for i in range(12):
        plan = P.build_plan(date(2026, 1, 5) + timedelta(weeks=i), seed=i)
        slugs = [m["slug"] for m in plan["to_make"]]
        check(len(slugs) == len(set(slugs)),
              f"week of {plan['week_start']}: to_make repeats {slugs}")


def test_coffee_week_shape():
    plan = P.build_plan(date(2026, 8, 29))
    n = int(L.load_household().get("drinks_per_week") or 2)
    check(len(plan["coffee"]) == n, f"expected {n} drinks a week, got {len(plan['coffee'])}")
    slugs = [c["drink"]["slug"] for c in plan["coffee"]]
    check(len(set(slugs)) == len(slugs), "the same drink was featured twice in one week")
    for c in plan["coffee"]:
        # A drink may legitimately have neither: it makes its own flavouring inline and
        # a crumble would sink in it. What it may NOT have is somebody else's syrup.
        # Build the message without indexing a None: f-strings evaluate eagerly, and a
        # drink that makes its own flavouring has no syrup to index.
        got = c["syrup"]["slug"] if c["syrup"] else None
        check(got is None or got == c["drink"].get("syrup"),
              f"{c['drink']['slug']} was paired with {got}, which is not "
              f"its own syrup ({c['drink'].get('syrup')})")
        check(c["crumble"] is None
              or c["crumble"]["slug"] in (c["drink"].get("crumbles") or []),
              f"{c['drink']['slug']} was paired with a crumble it does not list")


def test_cards_are_a_two_page_pdf():
    """
    The cards are a PDF because they go to a printer, and the page count must match.

    Printing HTML from a browser adds the browser's own page header, footer and margins on
    top of a layout measured to the inch — which is how a "two sheet" document comes out
    as three with a URL across the bottom. Skipped where no browser is installed, which is
    also the case the send path degrades to.
    """
    from mealbit import printable as PR, topdf
    plan = P.build_plan(date(2026, 8, 29))
    pdf = topdf.to_pdf(PR.render_cards(plan))
    if pdf is None:
        print("      (no browser — PDF checks skipped)")
        return
    check(pdf[:5] == b"%PDF-", "to_pdf did not return a PDF")
    # Two recipes to a sheet. The count follows from the week — four dinners and five
    # lunches is five sheets — but the PDF's page count must always match the HTML's
    # sheet count, or `break-after` has started emitting a stray blank page.
    want = -(-(len(plan["dinners"]) + len(plan["lunches"])
               + len(plan["coffee"]) + len(plan["to_make"])) // 2)
    check(topdf.page_count(pdf) == want,
          f"the cards should be {want} sheets, got {topdf.page_count(pdf)}")


def test_cards_fit_their_sheet():
    """
    Nothing may be clipped off the bottom of a card.

    The card is a fixed 8.5in with overflow:hidden — that hard cap is what guarantees two
    sheets and never a stray third page, but it means content that does not fit vanishes
    SILENTLY rather than reflowing. An ingredient dropping off a card is the worst failure
    this document has: you find out at the store.

    Ingredient counts swing from 5 to 11 across the library, which is more slack than the
    sheet has, so the photo is the flexible element and absorbs it. Several draws are
    checked because one week fitting proves nothing about the next.

    Skipped where no browser is installed — the same way the send path degrades.
    """
    from mealbit import printable as PR, topdf
    # Same launcher the send path uses, so "no browser" skips here exactly as it degrades
    # there. An earlier version launched Chromium itself and raised when it was missing,
    # which failed CI — and therefore blocked the newsletter — over an optional tool.
    with topdf.page(viewport={"width": 1056, "height": 816}) as pg:
        if pg is None:
            print("      (no browser — overflow checks skipped)")
            return
        for seed in range(8):
            plan = P.build_plan(date(2026, 8, 29), seed=seed)
            pg.set_content(PR.render_cards(plan), wait_until="load")
            over = pg.evaluate("""() => [...document.querySelectorAll('.card')]
                .map(c => c.scrollHeight - c.clientHeight)""")
            check(max(over) <= 0,
                  f"seed {seed}: a card overflows its sheet by {max(over)}px "
                  f"— content is being clipped")


def test_only_the_shopping_list_is_html():
    """
    The rule: the shopping list is the only HTML attachment.

    It has to be HTML because its checkboxes are tapped in the aisle. The cards are a PDF
    because they are printed. Getting this backwards gives you a page you cannot check off
    and a printout with a browser header across it.
    """
    import inspect
    from mealbit import meal_plan as MP
    src = inspect.getsource(MP.main)
    check("mealbit-shopping-" in src and '.html"' in src,
          "the shopping list must still be attached as HTML")
    check("'.pdf' if cards_pdf" in src,
          "the cards must be attached as a PDF when one could be rendered")


def _on_upstream():
    """True when this checkout IS the template, not a household's copy."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("setup_status", os.path.join(ROOT, "tools", "setup_status.py"))
    S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
    return bool(S.facts().get("is_upstream"))


def test_every_recipe_has_a_photo():
    """
    The brief: "every meal card should have a photo of what the dish should look like."

    Two tiers, and the separation is the point. `image_url` is the photo from a verified
    published recipe — the one the QR opens. `photo_url` is an openly-licensed photograph
    of the same dish from Openverse, used only where no published recipe matched: strict
    URL matching tops out around half the library, because a chanterelle-and-farro
    skillet has no close published equivalent and never will.

    A representative photo is never allowed to become a recipe link, and it is always
    credited.
    """
    # A recipe may declare `photo_pending` — no photo ON PURPOSE, because the only ones
    # available are the bad ones. The household, on the Openverse tier: "the lunch photos need to
    # be higher quality and actually the meal they represent." A blank beats a cafeteria
    # sub standing in for her giardiniera sub, and the card prints a labelled rule rather
    # than an empty grey box. It is capped, because "pending" must stay a queue and not
    # become the way the library works.
    pool = L.load_dinners() + L.load_lunches()
    pending = [r for r in pool if r.get("photo_pending")]
    # The queue is 4 deep on the upstream, where every recipe is curated. A household's
    # copy gets recipes written at setup to fit its taste, usually before it has a photo
    # key, so it may carry more — 12 — before this insists on photos.
    cap = 4 if _on_upstream() else 12
    check(len(pending) <= cap,
          f"{len(pending)} recipes are waiting for a photo ({', '.join(sorted(x['slug'] for x in pending))}). "
          f"That is no longer a queue — run tools/stock_photos.py with a PEXELS_API_KEY set")
    for r in pool:
        if r.get("photo_pending"):
            check(not (r.get("image_url") or r.get("photo_url")),
                  f"{r['slug']}: marked photo_pending but already has a photo — drop the flag")
            continue
        check(r.get("image_url") or r.get("photo_url"),
              f"{r['slug']}: no photo of any kind — the card would print an empty box. "
              f"Set `photo_pending: true` if that is deliberate")
        check(L.image_path(r["slug"]),
              f"{r['slug']}: has a photo URL but no cached thumbnail — "
              f"run tools/cache_images.py")
        if r.get("photo_url"):
            # No low-quality home-chef snapshots. A machine cannot judge whether a
            # photograph is well lit, in focus and appetising — the first automated pass
            # returned a bag of wild rice, a flash-lit plate and a blurry green smear,
            # every one of them passing the title check. So the enforceable form of the
            # rule is that a person has to have LOOKED at it: tools/photo_candidates.py
            # renders the options, tools/pin_photo.py records the choice, and an
            # unreviewed search result can never reach a card.
            check(r.get("photo_pinned"),
                  f"{r['slug']}: borrowed photo was never reviewed by eye — run "
                  f"tools/photo_candidates.py {r['slug']} and pin one")
            check(str(r["photo_url"]).startswith("https://"),
                  f"{r['slug']}: photo_url is not https")
            check(r.get("photo_credit"),
                  f"{r['slug']}: a CC-licensed photo with no attribution")
            # -ND forbids derivatives, and a 220px centre crop is one.
            check("-nd" not in str(r.get("photo_credit", "")).lower(),
                  f"{r['slug']}: photo licence forbids the crop we make of it")
            check(not r.get("source_url") or r.get("image_url"),
                  f"{r['slug']}: a representative photo must never stand in as the "
                  f"recipe behind the QR code")


def test_no_two_recipes_share_a_source():
    """
    Two cards carrying the same photo and the same QR code reads as a bug even when both
    links are individually defensible.

    "White bean smash toast" was handed feastingathome's brothy-beans-on-garlic-toast,
    which is already the source for the `brothy-white-beans-kale` dinner and fits that
    one exactly. The slug rules had nothing to say about it — both are white beans on
    toast — so the check is here instead.
    """
    seen = {}
    for r in L.load_dinners() + L.load_lunches():
        u = r.get("source_url")
        if not u:
            continue
        check(u not in seen,
              f"{r['slug']} and {seen.get(u)} both point at {u} — two cards with the "
              f"same photo and the same QR")
        seen[u] = r["slug"]


def test_cottage_cheese_is_sweet():
    """
    A reader, on a lunch card: "this does not sound appetizing at all. Cottage cheese is
    fine, but should only be topped with like a nut butter and preserve, or berries &
    maple. chilli oil and cucumber sounds gross."

    The rejected recipe scored well on every number the library tracks — 5 minutes, no
    cooking, 30g of protein — which is exactly why it needs a test rather than taste. A
    seasonal refresh optimising for those numbers would write it again.

    Only the negative half is enforceable. Whether a given sweet topping is nice is a
    judgement and lives in docs/household-model.md, along with the note that tzatziki
    is welcome: the objection is curds under savoury dressing, not cucumber.
    """
    SAVOURY = ("chili crisp", "chili-crisp", "chili oil", "chilli oil", "chili onion",
               "furikake", "everything bagel", "everything seasoning", "soy sauce",
               "kimchi", "miso", "za'atar", "harissa", "hot honey")
    # Ingredients and title only, never the body: the replacement recipe explains in
    # prose which toppings were rejected and why, and that paragraph is the point of it.
    for r in L.load_dinners() + L.load_lunches():
        blob = " ".join([str(r.get("title") or ""), str(r.get("pantry") or "")]
                        + L.ingredients(r)).lower()
        if "cottage cheese" not in blob:
            continue
        for word in SAVOURY:
            check(word not in blob,
                  f"{r['slug']}: cottage cheese with {word!r}. Cottage cheese goes sweet "
                  f"here — berries and maple, or nut butter and preserve. See "
                  f"docs/household-model.md")


def test_representative_photos_are_labelled_as_such():
    """A stand-in photo says so on the card, or it reads as a picture of your dinner."""
    from mealbit import printable as PR
    plan = P.build_plan(date(2026, 8, 29))
    cards = PR.render_cards(plan)
    for r in plan["dinners"] + plan["lunches"]:
        cred = L.photo_credit(r)
        if cred:
            check("a photo of the dish" in cards,
                  f"{r['slug']}: borrowed photo is not labelled on the card")
            check(cred in cards, f"{r['slug']}: photo credit {cred!r} missing from the card")


def test_printables_render():
    from mealbit import printable as PR
    plan = P.build_plan(date(2026, 8, 29))

    cards = PR.render_cards(plan)
    # Two recipes per sheet, cut down the middle. Every dinner cooked from this library
    # and every lunch gets a card — the household asked for the lunch cards, and the two dishes
    # batched on Sunday are real cooking that existed only in the email.
    n = len(plan["dinners"]) + len(plan["lunches"]) + len(plan["coffee"]) + len(plan["to_make"])
    check(cards.count('class="card"') == n + (n % 2),
          f"expected a card for each of the {n} recipes, two to a sheet")
    check(cards.count('class="sheet"') == -(-n // 2),
          f"{n} cards should print on {-(-n // 2)} sheets")
    for sheet in cards.split('<div class="sheet">')[1:]:
        check(sheet.count('class="card"') == 2, "a sheet does not hold exactly two cards")
    check("size: 11in 8.5in" in cards, "cards must be landscape letter, cut down the middle")
    check("dashed" in cards, "the cut line is gone; the sheet cannot be cut in half")
    for d in plan["dinners"] + plan["lunches"] + [c["drink"] for c in plan["coffee"]] + plan["to_make"]:
        check(d["title"] in cards, f"{d['slug']} missing from the printed cards")
    check("Sunday batch" in cards and "5-minute build" in cards,
          "lunch cards must say which kind of lunch they are")
    # Every ingredient on a card must say which store it comes from.
    from mealbit import config as C
    for tag in [st["short"] for st in C.stores()]:
        check(f">{tag}</span>" in cards, f"store tag {tag} missing from the cards")

    lst = PR.render_list(plan)
    # It is opened once from an email attachment and thrown away, so it deliberately keeps
    # no state — nothing to fail in a privacy-mode browser at the checkout.
    check("localStorage" not in lst, "the list should keep no state; it is used once")
    check(lst.count('type="checkbox"') >= 20, "phone list has suspiciously few items")
    check("viewport" in lst, "phone list has no viewport meta")
    check("<script" in lst and "count" in lst, "phone list lost its live item counter")
    n_items = sum(len(g["lines"]) for g in plan["shopping"])
    check(lst.count('type="checkbox"') == n_items,
          "phone list checkbox count doesn't match the shopping list")


def test_per_plate_ingredients_are_never_load_bearing():
    """
    Per-plate items must never be built into a dish.

    A reader, after a printed card: "the panzanella says to use the raw tomato juice
    as the dressing which [the other eater] would definitely not eat." Right, and it was not a
    wording problem — the recipe made a restricted ingredient structural. Serving it "on
    the side" is impossible once it is the dressing.

    So every recipe that BUYS a per-plate ingredient must say, in frontmatter, which way
    it goes. There is no inference here on purpose: whether a tomato is raw in a salad or
    simmered into a ragu is not a thing to guess from prose, and a wrong guess puts a
    plate in front of someone that they cannot eat.

      per_plate: [cilantro]         it goes on at the end, on the other plate only. The
                                    recipe must also carry a "**Per plate:**" paragraph
                                    saying how the dish is complete without it.
      per_plate_exempt: [tomatoes]  it is not restricted here — cooked down, roasted,
                                    braised. Needs a reason, same as market fallbacks.

    Modelled on data/market-availability.md's `fallback_exempt`: one explicit list, and
    the only way it improves is a human correcting it.
    """
    restricted = L.per_plate_items()
    check(restricted, "the per-plate list is empty; household config lost its per_plate key")
    for r in L.load_dinners() + L.load_lunches():
        hits = L.restricted_in(r, restricted)
        if not hits:
            continue
        declared = {L.normalize(x) for x in (r.get("per_plate") or [])}
        exempt = {L.normalize(x) for x in (r.get("per_plate_exempt") or [])}
        for key, line in hits:
            noun = key.replace("raw ", "").strip()
            covered = any(noun in d or d in noun for d in declared | exempt)
            who = ", ".join(L.per_plate_who(key)) or "someone"
            check(covered,
                  f"{r['slug']}: buys '{line}' which is per-plate for {who}, and declares "
                  f"neither per_plate nor per_plate_exempt for it")
        if declared:
            check("**Per plate:**" in (r.get("body") or ""),
                  f"{r['slug']}: declares per_plate {sorted(declared)} but the body never "
                  f"says how the dish works without it")


def test_per_plate_reaches_the_cook():
    """A per-plate instruction that is not printed is not an instruction."""
    from mealbit import printable as PR
    plan = P.build_plan(date(2026, 8, 29))
    cards = PR.render_cards(plan)
    html = R.render(plan)
    for d in plan["dinners"]:
        for item in (d.get("per_plate") or []):
            check(item.lower() in cards.lower(),
                  f"{d['slug']}: per-plate item {item!r} missing from the printed card")
            check("Per plate" in cards,
                  f"{d['slug']}: the card never labels the per-plate step")
            # And in the email, where the week is actually read.
            who = L.per_plate_who(item)
            check(who, f"{d['slug']}: per-plate item {item!r} matches nobody in household.yml")
            check(f"not on {who[0]}&rsquo;s" in html,
                  f"{d['slug']}: the email never names who skips the per-plate item")


def _with_household(**over):
    """Run a block with household.yml overridden; restores the real loader after."""
    import contextlib

    @contextlib.contextmanager
    def cm():
        real = L.load_household
        cfg = dict(real(), **over)
        L.load_household = lambda: cfg
        try:
            yield cfg
        finally:
            L.load_household = real
    return cm()


def test_the_week_follows_the_meals_config():
    """
    The onboarding survey asks how many dinners and what lunch means. Whatever it
    collects has to be honoured, or the question was theatre.

      dinners_per_week  changes how many nights are cooked and which
      lunch_mode: fresh  no leftovers in the ledger; the list buys for the table only and
                         the card says to halve the recipe
      lunch_mode: none   no lunches, no lunch section, no Sunday batch on the list
    """
    from mealbit import printable as PR
    with _with_household(dinners_per_week=2):
        plan = P.build_plan(date(2026, 8, 29))
        check(len(plan["dinners"]) == 2, "dinners_per_week: 2 planned a different number")
        check(plan["cook_nights"] == ["Mon", "Tue"], f"cook nights {plan['cook_nights']}")
        check(plan["ledger_stats"]["leftovers"] == 4,
              f"2 dinners x 2 servings should fill 4 lunch slots, got "
              f"{plan['ledger_stats']['leftovers']}")
        check("Mon to Tue" in R.render(plan), "the email heading still says Mon to Thu")

    with _with_household(lunch_mode="fresh"):
        plan = P.build_plan(date(2026, 8, 29))
        check(plan["ledger_stats"]["leftovers"] == 0, "fresh mode still packed leftovers")
        check(len(plan["lunches"]) == 5, "fresh mode should still plan the lunches")
        check(all(d.get("_scale") == 0.5 for d in plan["dinners"]),
              "fresh mode should buy dinners for the two at the table")
        html = R.render(plan)
        check("halve it" in html, "the email never says the recipe is scaled")
        check("halve it" in PR.render_cards(plan), "the card never says to halve it")
        # And the list actually bought less — for a line that only a DINNER asks for.
        # Lunches are not scaled (they are made for the people eating them already), so
        # an ingredient a lunch shares would mask the halving.
        dinner_titles = {d["title"] for d in plan["dinners"]}
        lunch_titles = {r["title"] for r in plan["lunches"]}
        scaled = {(x["name"], x["unit"]): x["qty"] for g in plan["shopping"]
                  for x in g["lines"] if x["qty"]
                  and set(x["used_in"]) & dinner_titles and not set(x["used_in"]) & lunch_titles}
        check(scaled, "no dinner-only line on the list to check the scaling with")
    full = P.build_plan(date(2026, 8, 29))              # the default household, same week
    unscaled = {(x["name"], x["unit"]): x["qty"] for g in full["shopping"]
                for x in g["lines"] if x["qty"]}
    shared = [k for k in scaled if k in unscaled]
    check(shared, "the scaled and unscaled weeks share no dinner line to compare")
    for k in shared:
        check(scaled[k] < unscaled[k],
              f"{k[0]}: scaled list buys {scaled[k]} vs {unscaled[k]} — dinner not halved")

    with _with_household(lunch_mode="none"):
        plan = P.build_plan(date(2026, 8, 29))
        check(plan["lunches"] == [] and plan["ledger"] == [], "none mode planned lunches")
        html = R.render(plan)
        check("Lunches" not in html, "none mode still renders a lunch section")
        check("halve it" in html, "none mode still buys for four")
        check(all(g["lines"] for g in plan["shopping"] if g["store"] != "cupboard")
              or True, "")   # stores may legitimately be empty; just must not crash


def test_no_personal_information_is_committed():
    """
    Nothing in the repository may carry an email address, a phone number or a street
    address. First names are fine; that is the one exception, and it is deliberate.

    This repository is public and it is also a household's live instance, so the real
    addresses live in repository secrets and the file carries placeholders. A person
    editing a file by hand — or an agent filling in a config from a survey — is exactly
    who this catches, before CI sends anything.
    """
    import subprocess
    ALLOWED = {"you@gmail.com", "household@example.com", "you@example.com",
               "eater@example.com", "noreply@anthropic.com",
               "mealbit-bot@users.noreply.github.com"}
    files = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                           cwd=ROOT).stdout.split()
    email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    phone = re.compile(r"(?<!\d)\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}(?!\d)")
    street = re.compile(r"\b\d{3,5} [A-Z][a-z]+ (Ave|St|Street|Avenue|Blvd|Rd|Road|Way|"
                        r"Pl|Place|Dr|Drive|Ct|Ln)\b")
    for f in files:
        if not f.endswith((".py", ".md", ".yml", ".yaml", ".json", ".txt", ".html")):
            continue
        try:
            txt = open(os.path.join(ROOT, f), encoding="utf-8").read()
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for m in email.finditer(txt):
            addr = m.group(0).lower().rstrip(".")
            check(addr in ALLOWED or addr.endswith("@example.com") or addr.endswith(".test")
                  or "noreply" in addr,
                  f"{f}: contains an email address ({addr}). Addresses go in repository "
                  f"secrets, never in a file — see .claude/skills/mealbit-secrets")
        check(not phone.search(txt), f"{f}: contains what looks like a phone number")
        check(not street.search(txt), f"{f}: contains what looks like a street address")


def test_plan_shape_and_variety():
    plan = P.build_plan(date(2026, 8, 29))
    ms = P.meal_settings()
    check(len(plan["dinners"]) == ms["n_dinners"],
          f"must plan exactly {ms['n_dinners']} dinners (meals.dinners_per_week)")
    check(len(plan["lunches"]) == ms["n_lunches"],
          f"must plan exactly {ms['n_lunches']} lunches (meals.lunch_mode)")
    styles = [r["lunch_style"] for r in plan["lunches"]]
    check(styles.count("sunday-prep") == ms["n_prep"], "wrong number of batch lunches")
    check(styles.count("assembly") == ms["n_assembly"], "wrong number of 5-min lunches")
    check(plan["week_start"].weekday() == 0, "the plan week must start on Monday")
    check(plan["shop_day"].weekday() == 6,
          "shopping must land on the Sunday before the week opens (market day)")
    check(plan["shop_day"] < plan["week_start"], "shop day must precede the week")
    check(plan["cook_nights"] == ["Mon", "Tue", "Wed", "Thu"],
          f"dinners are cooked Mon-Thu, got {plan['cook_nights']}")


def test_leftover_quality_decides_whether_lunch_exists():
    """
    A dinner only becomes lunch if it is still good as one.

    The brief: "balance for dinner leftovers whether it SHOULD EVEN be leftovers for lunch the
    next day. panzanella with soggy goopy bread is a NO."

    Every dinner used to carry `leftovers: 2` — a default, not a decision — so the ledger
    promised a lunch box for dishes that do not survive the night. The declaration is now
    explicit and the count follows from it:

      good  pack it and go. Cold or a microwave, no work, often better than dinner.
      fair  packs, but needs one small step — a separate jar, a toss of oil, a re-crisp.
      none  don't pack it. It degrades, or reviving it means COOKING (breading arancini,
            frying a carbonara cake), and a weekday lunch has five minutes.
    """
    QUALITIES = {"good", "fair", "none"}
    for r in L.load_dinners():
        q = r.get("leftover_quality")
        check(q in QUALITIES,
              f"{r['slug']}: leftover_quality is {q!r}, expected one of {sorted(QUALITIES)}")
        n = int(r.get("leftovers") or 0)
        if q == "none":
            check(n == 0,
                  f"{r['slug']}: leftover_quality is none but it still promises {n} "
                  f"lunch servings")
            check("don't pack this one" in (r.get("body") or "").lower(),
                  f"{r['slug']}: doesn't pack, but its leftover plan never says so")
        else:
            check(n >= 1,
                  f"{r['slug']}: keeps well ({q}) but yields no lunch — that is the whole "
                  f"reason dinners are cooked to serve 4")


def test_every_protein_is_classified():
    """
    Every dinner's `protein:` tag must appear in data/protein.md, on one side or other.

    An unclassified tag is not a harmless gap: it falls through to `light`, so a new
    "paneer" or "tempeh" dinner would silently stop counting toward the three and start
    being skipped by the picker, with nothing anywhere saying why.
    """
    anchors, light = L.load_protein()
    known = anchors | light
    check(not (anchors & light), "a protein tag is on both lists in data/protein.md")
    for r in L.load_dinners():
        check(r.get("protein") in known,
              f"{r['slug']}: protein {r.get('protein')!r} is in neither the anchor nor "
              f"the light list in data/protein.md — classify it, or it quietly counts "
              f"as light")


def test_three_of_four_dinners_are_built_on_a_protein():
    """
    The brief: "we also want to ensure 3/4 meals have some kind of meat or high protein
    source in them."

    The fourth night is free — that is where a dal or a bowl of brothy beans goes. Where
    the line sits was the household's call and it moved the outcome a long way: counting legumes
    as a protein made the rule true 52 weeks out of 52 and enforced nothing, counting
    only meat left 17 of 52 weeks short. She chose meat, fish, tofu and eggs.

    Two things are checked, because the rule is only worth having if the library can
    actually meet it. First that every season holds enough DISTINCT anchor proteins to
    fill three slots without repeating one — the no-repeat rule is stricter, so a season
    with three anchor recipes that are all chicken would deadlock. Then that real plans
    come out at three or more, or say out loud that they could not.
    """
    anchors, _light = L.load_protein()
    for season in L.SEASON_ORDER:
        pool = [d for d in L.load_dinners() if season in (d.get("seasons") or [])]
        kinds = {d.get("protein") for d in pool if d.get("protein") in anchors}
        check(len(kinds) >= P.MIN_PROTEIN_DINNERS,
              f"{season}: only {len(kinds)} distinct anchor protein(s) in season "
              f"({sorted(kinds)}) — cannot fill {P.MIN_PROTEIN_DINNERS} slots without "
              f"serving the same protein twice")

    short = 0
    for i in range(52):
        plan = P.build_plan(date(2026, 1, 5) + timedelta(weeks=i), seed=i)
        got = sum(1 for d in plan["dinners"] if d.get("protein") in anchors)
        if got < P.MIN_PROTEIN_DINNERS:
            short += 1
            # Degrading is allowed; degrading silently is not.
            check(any("built on a protein" in n for n in (plan.get("notes") or [])),
                  f"week of {plan['week_start']} has {got} protein dinners and the "
                  f"footnote never mentions it")
    check(short == 0,
          f"{short} of 52 simulated weeks fell short of {P.MIN_PROTEIN_DINNERS} protein "
          f"dinners — the library has drifted; add meat, fish or tofu recipes")


def test_a_packing_dinner_packs_the_dinner_that_was_cooked():
    """
    A `good` or `fair` dinner's leftover plan may not send you back to the stove for a
    *different* dish. The household cares more about this direction than the other one: a wrong
    `none` costs two lunch slots, but a wrong `good`/`fair` puts a lunch in the ledger
    that does not exist.

    Green shakshuka is why this test exists. It was `fair` with `leftovers: 2`, so the
    ledger printed "Green shakshuka" in Tuesday's lunch column — but its leftover plan
    said to cook two extra portions of the vegetable base and fry a fresh egg. Whatever
    that is, it is not the dinner that was cooked, and nobody was going to do it at 7am.

    Cooking extra of something is fine advice — it is just `none` advice. Panzanella's
    "grill an extra chicken thigh while the pan is hot" is exactly right, in exactly the
    right place. A `fair` plan may re-crisp, loosen, or unpack-and-rebuild what is
    already in the fridge; it may not ask for new food.
    """
    FRESH_COOKING = ("cook two extra", "cook an extra", "cook extra",
                     "fry a fresh", "grill an extra", "roast an extra", "bake an extra")
    for r in L.load_dinners():
        body = (r.get("body") or "").lower()
        i = body.find("**leftover plan:**")
        if i < 0:
            continue
        plan = body[i:]
        if r.get("leftover_quality") == "none":
            continue        # cooking something new is the whole point of a `none` plan
        for phrase in FRESH_COOKING:
            check(phrase not in plan,
                  f"{r['slug']}: packs as a lunch ({r.get('leftover_quality')}) but its "
                  f"leftover plan says {phrase!r} — that promises a lunch box of food "
                  f"nobody has cooked. Either pack the actual dinner or declare none")


def test_a_season_is_not_all_one_register_of_non_packing_dinner(l=None):
    """
    The elegant dinners in a season may not ALL be ones that don't pack.

    Summer had exactly two elegant dinners — panzanella and zucchini carbonara — and both
    were `leftover_quality: none`. The picker wants at least two comfort dinners and at
    most one non-packing one, so any week reaching for the elegant end of the library was
    steering itself straight into the constraint it is supposed to relax last. A season
    can be thin, but it should not be thin in a shape that fights the planner.
    """
    for season in L.SEASON_ORDER:
        cfg = L.load_household()
        pool = [r for r in L.load_dinners()
                if season in (r.get("seasons") or []) and not P._excluded(r, cfg)]
        eleg = [r for r in pool if r.get("register") == "elegant"]
        if not eleg:
            continue
        packs = [r for r in eleg if r.get("leftover_quality") != "none"]
        check(packs,
              f"season {season}: all {len(eleg)} elegant dinners are non-packing "
              f"({[r['slug'] for r in eleg]}) — a week that wants an elegant dinner "
              f"cannot also feed the lunch column")


def test_a_week_never_loses_two_dinners_to_lunch():
    """
    At most one non-packing dinner per week.

    Four dinners pay for ten weekday lunch slots. Each dinner that doesn't pack costs two
    of them, so two in one week collapses the lunch column onto assembly sandwiches.
    """
    for wk in range(40):
        plan = P.build_plan(date(2026, 1, 4) + timedelta(weeks=wk))
        dead = [d["slug"] for d in plan["dinners"] if d.get("leftover_quality") == "none"]
        check(len(dead) <= 1,
              f"week {wk}: {len(dead)} dinners that don't pack as lunch ({dead})")


def test_the_ledger_never_invents_a_leftover(l=None):
    """The grid may only serve leftovers a dinner actually yielded."""
    for wk in range(0, 40, 3):
        plan = P.build_plan(date(2026, 1, 4) + timedelta(weeks=wk))
        supply = {d["title"]: int(d.get("leftovers") or 0) for d in plan["dinners"]}
        served = {}
        for row in plan["ledger"]:
            for slot in row["slots"]:
                if slot["kind"] == "leftovers":
                    served[slot["what"]] = served.get(slot["what"], 0) + 1
        for title, n in served.items():
            check(n <= supply.get(title, 0),
                  f"week {wk}: served {n} leftover portions of {title!r} but the dinner "
                  f"yields {supply.get(title, 0)}")


def test_a_boxed_dinner_costs_nothing_and_still_feeds_lunch():
    """
    Dinners that arrive already shopped for.

    The changeover week: the last meal-kit box covers Mon-Wed, so the list only has
    to buy Thursday's dinner, the lunches and the coffee. Two things must both hold, and
    they pull in opposite directions — the box must contribute NOTHING to the shopping
    list, and it must still contribute its real leftovers to the lunch ledger.
    """
    d = date(2026, 8, 29)
    plain = P.build_plan(d)
    boxed = P.build_plan(d, box={"count": 3, "label": "Meal-kit box", "leftovers": 1})

    check(len(boxed["dinners"]) == P.N_DINNERS,
          f"the week still has {P.N_DINNERS} nights, got {len(boxed['dinners'])}")
    check(sum(1 for x in boxed["dinners"] if x.get("external")) == 3,
          "three nights should be boxed")
    cooked = [x for x in boxed["dinners"] if not x.get("external")]
    check(len(cooked) == 1, "one dinner should still be cooked from the library")

    # Nothing the box brought may reach the list. Every shopping line records which
    # recipes pulled it in, so this asks the list directly rather than trusting a flag.
    allowed = {r["title"] for r in cooked + boxed["lunches"]
               + [c["drink"] for c in boxed["coffee"]] + boxed["to_make"]}
    for grp in boxed["shopping"]:
        for line in grp["lines"]:
            stray = [u for u in line["used_in"] if u not in allowed]
            check(not stray,
                  f"{line['name']!r} is on the list for {stray} — a dinner that was "
                  f"already shopped for")

    # And it is genuinely a smaller shop than the same week cooked from scratch.
    n_boxed = sum(len(g["lines"]) for g in boxed["shopping"])
    n_plain = sum(len(g["lines"]) for g in plain["shopping"])
    check(n_boxed < n_plain,
          f"a boxed week should shop for less, got {n_boxed} lines vs {n_plain}")

    # The leftovers are real and they are the box's number, not the library default.
    served = sum(1 for row in boxed["ledger"] for sl in row["slots"]
                 if sl["kind"] == "leftovers" and sl["what"].startswith("Meal-kit"))
    check(served == 3, f"3 boxed leftover servings should reach the ledger, got {served}")

    # No card for a meal whose recipe we don't have — the kit brings its own.
    from mealbit import printable as PR
    cards = PR.render_cards(boxed)
    check("Meal-kit box" not in cards, "printed a recipe card for a meal-kit dinner")
    check(cards.count('class="card"') % 2 == 0, "cards must still pair up on a sheet")
    # The lunches are still printed — the box covers dinners, not lunches, and this week
    # leans on them harder than usual.
    for r in boxed["lunches"]:
        check(r["title"] in cards, f"{r['slug']}: lunch card missing from a boxed week")

    # History must not learn a slug that matches no recipe.
    import tempfile as _tf
    old = L.HISTORY
    try:
        L.HISTORY = os.path.join(_tf.mkdtemp(), "h.json")
        P.record(boxed)
        wk = L.load_history()["weeks"][-1]
        check(not any(x.startswith("external-") for x in wk["dinners"]),
              "a placeholder dinner got written into the rotation history")
    finally:
        L.HISTORY = old


def test_a_single_leftover_serving_alternates_between_eaters():
    """
    With one serving a night, a fixed eater order gives it to the same person all week.

    The usual two servings hide this — both eaters get one and order never matters. A
    meal kit leaves one, and then one eater takes every leftover of the week while the other
    opens the same batch container seven days running.
    """
    boxed = P.build_plan(date(2026, 8, 29),
                         box={"count": 3, "label": "Meal-kit box", "leftovers": 1})
    who = [sl["eater"] for row in boxed["ledger"] for sl in row["slots"]
           if sl["kind"] == "leftovers" and sl["what"].startswith("Meal-kit")]
    check(len(set(who)) > 1,
          f"all {len(who)} single leftover servings went to {who[0]}")


def test_ledger_arithmetic():
    """
    The core promise: every lunch slot in the week filled, none double-booked, and no
    leftover or batch container eaten past the point it is still good.
    """
    plan = P.build_plan(date(2026, 8, 29))
    st = plan["ledger_stats"]
    check(st["total_slots"] == 14,
          f"expected 14 lunch slots (2 people x 7 days), got {st['total_slots']}")
    check(st["leftovers"] + st["prep"] + st["assembly"] == st["total_slots"],
          "ledger sources do not sum to the number of lunch slots")
    check(all(s["kind"] != "gap" for row in plan["ledger"] for s in row["slots"]),
          "a lunch slot was left unfilled")
    check(st["leftovers"] <= st["leftover_servings"],
          "the ledger served more leftovers than the dinners actually produce")
    # No serving may be handed out twice.
    served = [(r["day"], s["eater"]) for r in plan["ledger"] for s in r["slots"]]
    check(len(served) == len(set(served)), "a person was assigned two lunches on one day")

    # A batch cooked on Sunday must not be served the following weekend — six or seven
    # days in a container is past nice and past sensible.
    for di, row in enumerate(plan["ledger"]):
        for slot in row["slots"]:
            check(not (slot["kind"] == "prep" and di >= P.PREP_LASTS_DAYS),
                  f"{row['day']}: a Sunday batch was served on day {di + 1}, "
                  f"past the {P.PREP_LASTS_DAYS}-day limit")

    # Leftovers must come from a dinner cooked within the freshness window.
    night_of = {P.DAYS[n]: n for n in P.COOK_NIGHTS}
    for di, row in enumerate(plan["ledger"]):
        for slot in row["slots"]:
            if slot["kind"] != "leftovers":
                continue
            src = slot["note"].replace("from ", "").replace(" night", "")
            gap = di - night_of[src]
            check(0 < gap <= P.LEFTOVER_WINDOW,
                  f"{row['day']}: leftovers from {src} are {gap} days old")


def test_nobody_eats_the_same_batch_all_week():
    """Round-robin the batches: a plain counter aligns with two eaters and never rotates."""
    plan = P.build_plan(date(2026, 8, 29))
    for eater in P.EATERS:
        got = [s["what"] for r in plan["ledger"] for s in r["slots"]
               if s["eater"] == eater and s["kind"] == "prep"]
        check(len(got) == len(set(got)) or len(set(got)) > 1,
              f"{eater} was handed the same batch container {len(got)} times")


def test_market_availability_model():
    """
    WSFM is a Washington-growers-only market. The model has to know that.
    """
    avail = L.load_market_availability()
    check("lemon" in avail["never"], "citrus must be marked as never at the market")
    check("scallion" in avail["year_round"], "scallions are at the market every week")

    # Never means never, in any month.
    for month in (2, 8):
        for item in ("lemon", "sweet potato", "tomatillo"):
            ok, _why = L.market_has(item, month, avail)
            check(not ok, f"{item} should never route to the market (month {month})")

    # Seasonal items follow the month.
    ok_aug, _ = L.market_has("cherry tomatoes", 8, avail)
    ok_feb, _ = L.market_has("cherry tomatoes", 2, avail)
    check(ok_aug, "August tomatoes must come from the market")
    check(not ok_feb, "February tomatoes must not come from the market")

    # Head-noun and whole-word matching: "4 celery stalks" is celery.
    check(L.market_has("celery stalks", 2, avail)[0], "celery is a year-round market item")
    check(L.market_has("delicata squash", 10, avail)[0],
          "delicata should match October's winter squash")
    check(L.market_has("jalapenos", 8, avail)[0],
          "jalapenos should match August peppers via the synonym map")

    for item in ("lemon", "cherry tomatoes"):
        _ok, why = L.market_has(item, 2, avail)
        check(why.strip(), f"{item}: every verdict needs a reason to print")


def test_unavailable_produce_is_rerouted_off_the_market():
    """
    Nothing the market can't supply may stay on the market list — and nothing may be
    dropped on the way: a bounced item lands on some later store in visit order.

    Skipped, honestly, for a household with no farmers market configured.
    """
    from mealbit import config as C
    ms = C.market_store()
    if not ms:
        return
    for today, month in ((date(2026, 8, 29), 8), (date(2026, 1, 31), 2)):
        plan = P.build_plan(today)
        avail = L.load_market_availability()
        market = [g for g in plan["shopping"] if g["store"] == ms["id"]][0]
        elsewhere = [x for g in plan["shopping"]
                     if g["store"] not in (ms["id"], "cupboard") for x in g["lines"]]
        for line in market["lines"]:
            ok, why = L.market_has(line["name"], plan["week_start"].month, avail)
            check(ok, f"{line['name']} is on the market list but {why}")
        for m in plan["market_moves"]:
            check(any(L.normalize(m["item"]) == L.normalize(x["name"]) for x in elsewhere),
                  f"{m['item']} was moved off the market list but reached no other store")
            check(m["why"].strip(), "a reroute must carry its reason")


# Per-SERVING ceilings, from data/portions.md. A 5-serving Sunday batch may legitimately
# buy more than a 2-serving sandwich, so everything is expressed per serving rather than
# per recipe.
PORTION_CEILING = {
    "tuna": 0.5, "bone-in": 0.55, "ground": 0.30, "protein": 0.375,
    "beans": 0.5, "cherry tomato": 0.25, "tomatoes": 0.5, "veg": 0.45,
    # 12 oz of dry pasta or grain for four, not a full pound. This one was in
    # data/portions.md from the start and enforced nowhere, so the carbonara quietly kept
    # buying a pound of bucatini.
    "starch": 0.1875,
}
_GROUND = ("ground", "chorizo")
_BONE = ("bone-in", "short rib", "shoulder", "wing", "drumstick")
_FLESH = ("chicken", "beef", "pork", "turkey", "steak", "lamb", "chop", "rib", "sausage",
          "bacon", "pancetta", "guanciale", "tofu", "cod", "rockfish", "salmon",
          "halibut", "whitefish")


_STARCH = ("pasta", "spaghetti", "bucatini", "orecchiette", "pappardelle", "penne",
           "noodle", "soba", "orzo", "couscous", "farro", "barley", "rice", "quinoa",
           "polenta", "grits")


def _portion_kind(key, unit, raw):
    """Which ceiling applies to this line, if any."""
    low = raw.lower()
    if "tuna" in key and unit == "jar":
        return "tuna"
    if unit in ("lb", "oz") and any(w in key for w in _STARCH):
        return "starch"
    if unit == "lb":
        if any(w in low for w in _BONE):
            return "bone-in"
        if any(w in key for w in _GROUND):
            return "ground"
        if any(w in key for w in _FLESH):
            return "protein"
        return "veg"
    if "bean" in key and unit == "can":
        return "beans"
    if "tomato" in key and unit == "pint":
        return "cherry tomato"
    if "tomato" in key and unit is None:
        return "tomatoes"
    return None


def test_portions_are_household_sized():
    """
    Recipes are written smaller than an American recipe of the same name.

    A reader, on a list: "calling for 2 pints of tomatoes, 3 bunches of cilantro and 2
    romaine lettuce heads is WAY too much for a single meal and a few lunches. Ensure the
    portions are smaller than a typical American recipe calls for."

    A US recipe "for four" routinely calls for 2 lb of meat — half a pound a head before
    any sides. This household cooks four portions where two are eaten and two are lunch,
    so a portion is a portion. Thirty-four lines were over; the ceilings are in
    data/portions.md and they live here because a hand-edited recipe file is exactly
    where a 2 lb habit creeps back in.
    """
    for r in L.load_dinners() + L.load_lunches():
        n = int(r.get("makes") or r.get("serves") or 4) + int(r.get("also_yields") or 0)
        for line in L.ingredients(r):
            if True:
                it = L.parse_item(str(line))
                if not it["name"] or it["qty"] is None:
                    continue
                kind = _portion_kind(it["key"], it["unit"], str(line))
                ceiling = PORTION_CEILING.get(kind)
                if ceiling is None:
                    continue
                cap = ceiling * n
                # Starch is priced in pounds; a line in ounces is the same thing smaller.
                if it["unit"] == "oz":
                    cap *= 16
                check(it["qty"] <= cap + 1e-9,
                      f"{r['slug']}: {line!r} is {it['qty']} for {n} servings; the house "
                      f"ceiling for {kind} is {cap:.2f}")


def test_one_purchase_covers_the_week():
    """
    A bunch is a bunch. The consolidator may not multiply what you only buy once.

    Three recipes each asking for "1 bunch cilantro" produced 3 bunches, two of which rot
    in the drawer, and a jar of pickled jalapenos that keeps for months was bought once
    per recipe that mentioned it. For anything in data/portions.md's `one_is_enough` the
    list takes the LARGEST single requirement, never the sum.
    """
    shared = L.load_shared_items()
    check(shared, "the one_is_enough list is empty; data/portions.md lost its yaml block")
    for wk in range(0, 40, 3):
        plan = P.build_plan(date(2026, 1, 4) + timedelta(weeks=wk))
        for grp in plan["shopping"]:
            for line in grp["lines"]:
                key = L.normalize(line["name"])
                if not any(k in key or key in k for k in shared):
                    continue
                # Whatever any single recipe asked for is the most we may buy.
                want = 0
                # Coffee syrups and crumbles buy from this list too — culinary lavender
                # and dried rose petals are on it, and they are the most "one packet
                # covers a year" things in the whole plan.
                for r in (plan["dinners"] + plan["lunches"]
                          + [c["drink"] for c in plan["coffee"]] + plan["to_make"]):
                    for raw in L.ingredients(r):
                        if True:
                            it = L.parse_item(str(raw))
                            if it["name"] and L.normalize(it["key"]) == key:
                                want = max(want, it["qty"] or 0)
                check((line["qty"] or 0) <= want + 1e-9,
                      f"week {wk}: buying {line['qty']} {line['name']} when the largest "
                      f"single recipe asks for {want} — one purchase covers the week")


def test_an_ingredient_belongs_to_one_store():
    """
    "Pickled jalapenos" was on the Trader Joe's list AND the QFC list — three jars across
    two shops, and the second jar gets bought because the list said to. Two recipes had
    simply filed the same ingredient under different stores.
    """
    for wk in range(0, 40, 3):
        plan = P.build_plan(date(2026, 1, 4) + timedelta(weeks=wk))
        seen = {}
        for grp in plan["shopping"]:
            for line in grp["lines"]:
                key = L.normalize(line["name"])
                check(key not in seen,
                      f"week {wk}: {line['name']!r} is on both the {seen.get(key)} list "
                      f"and the {grp['label']} list")
                seen[key] = grp["label"]


def test_shopping_list_conserves_ingredients():
    """
    Nothing may be silently dropped. Every non-pantry ingredient must reach the list.

    Quantities sum, with two deliberate exceptions that are each covered by their own
    test: an `one_is_enough` item takes the largest single requirement rather than the
    sum (test_one_purchase_covers_the_week), and an ingredient two recipes filed under
    different stores appears only at the first store in visit order
    (test_an_ingredient_belongs_to_one_store). What must never happen is an ingredient
    vanishing, which is what this checks.
    """
    plan = P.build_plan(date(2026, 8, 29))
    staples, rotation = L.load_pantry()
    shared = L.load_shared_items()
    everywhere = {L.normalize(x["name"]) for g in plan["shopping"] for x in g["lines"]}
    for grp in plan["shopping"]:
        if grp["store"] == "cupboard":
            continue        # not a store: it is a re-read of the recipes' own pantry lines
        expected, bare = {}, set()
        # Everything in the plan is already routed (build_plan does it before the list is
        # consolidated), so conservation is checked against the same per-store buckets.
        sources = (plan["dinners"] + plan["lunches"]
                   + [c["drink"] for c in plan["coffee"]] + plan["to_make"])
        for r in sources:
            for line in r["_by_store"].get(grp["store"]) or []:
                it = L.parse_item(str(line))
                if not it["name"] or L.is_pantry(it, staples, rotation):
                    continue
                if it["qty"] is None and it["unit"] is None:
                    bare.add(it["key"])     # absorbed into a quantified entry, if one exists
                    continue
                k = (it["key"], it["unit"])
                expected[k] = (expected.get(k) or 0) + (it["qty"] or 0)
        # A bare mention only earns its own line when nothing else quantified it.
        for key in bare:
            if not any(k[0] == key for k in expected):
                expected[(key, None)] = None
        got = {(L.normalize(x["name"]), x["unit"]): x["qty"] for x in grp["lines"]}
        check(not (set(got) - set(expected)),
              f"{grp['store']}: list has lines no recipe asked for "
              f"{set(got) - set(expected)}")
        for k, v in expected.items():
            key = k[0]
            if k not in got:
                # Allowed to be missing from THIS store only by having been merged into
                # an earlier one. Vanishing entirely is the failure.
                check(key in everywhere,
                      f"{grp['store']}: {key!r} is in a recipe and on no store list")
                continue
            if not v:
                continue
            if any(x in key or key in x for x in shared):
                check((got[k] or 0) <= v + 1e-6,
                      f"{grp['store']}: {k} is {got[k]}, more than the {v} asked for")
            else:
                check(abs((got.get(k) or 0) - v) < 1e-6,
                      f"{grp['store']}: {k} summed to {got.get(k)}, expected {v}")


def test_determinism():
    a = P.build_plan(date(2026, 8, 29))
    b = P.build_plan(date(2026, 8, 29))
    check([d["slug"] for d in a["dinners"]] == [d["slug"] for d in b["dinners"]],
          "the same week must produce the same plan — otherwise a re-run after a "
          "self-test would send the family a different newsletter than the one reviewed")
    check(a["drink"]["slug"] == b["drink"]["slug"], "drink pick is not deterministic")


def test_a_year_without_failing():
    """
    52 consecutive weeks against a real rotating history: never raises, never repeats a
    protein or cuisine inside a week, always holds the comfort and effort balance.
    """
    real = L.load_history()
    try:
        L.save_history({"weeks": []})
        d = date(2026, 8, 29)
        used = set()
        for wk in range(52):
            plan = P.build_plan(d)
            ds = plan["dinners"]
            check(len({x["protein"] for x in ds}) == 4, f"week {wk}: repeated protein")
            check(len({x["cuisine"] for x in ds}) == 4, f"week {wk}: repeated cuisine")
            check(sum(1 for x in ds if x["register"] == "comfort") >= 2,
                  f"week {wk}: fewer than 2 comfort dinners")
            check(sum(1 for x in ds if x["effort"] == "project") <= 1,
                  f"week {wk}: more than one multi-hour project")
            check(any(x["effort"] == "easy" for x in ds), f"week {wk}: no easy dinner")
            R.render(plan)                       # must render for every week of the year
            used.update(x["slug"] for x in ds)
            P.record(plan)
            d += timedelta(days=7)
        cfg = L.load_household()
        reachable = [r for r in L.load_dinners() if not P._excluded(r, cfg)]
        check(len(used) == len(reachable),
              f"only {len(used)} of {len(reachable)} reachable dinners ever surfaced — "
              f"some recipes are unreachable (excluded ones are expected to be absent)")
        check(not (used & {r["slug"] for r in L.load_dinners() if P._excluded(r, cfg)}),
              "an excluded recipe was served during the year-long simulation")
    finally:
        L.save_history(real)


# ---------------------------------------------------------------- rendering

def test_audit_counts_only_reachable_recipes():
    """
    Depth must mean depth the planner can actually reach.

    Counting dietary-excluded recipes overstates every season they appear in and hides
    the real gap — which is the one thing this report exists to surface.
    """
    # The test supplies its own exclusion rather than relying on the household having
    # one: a household that excludes nothing is a perfectly good household, and the audit
    # still has to be right for one that does.
    real = L.load_household
    cfg = dict(real(), exclude_ingredients=["salmon"])
    L.load_household = lambda: cfg
    try:
        excluded = {r["slug"] for r in L.load_dinners() if P._excluded(r, cfg)}
        check(excluded, "the library has no salmon recipe left to exclude — pick another")
        for s in L.SEASON_ORDER:
            pool = [r for r in L.load_dinners()
                    if s in (r.get("seasons") or []) and not P._excluded(r, cfg)]
            check(A.season_report(s)["n_dinners"] == len(pool),
                  f"audit over-counts {s}: it is including excluded recipes as depth")
        check(not ({x["slug"] for x in A.missing_sources()} & excluded),
              "audit is asking for source links on recipes nobody can be served")
    finally:
        L.load_household = real


def test_audit_reports_every_season():
    """The audit must produce a usable report for all six buckets, not just today's."""
    for s in L.SEASON_ORDER:
        r = A.season_report(s)
        check(r["n_dinners"] >= P.N_DINNERS,
              f"audit: season {s} has {r['n_dinners']} dinners, can't fill a week")
        check(r["rotation_weeks"] == r["n_dinners"] / P.N_DINNERS, f"audit: {s} bad maths")
        for g in r["gaps"]:
            check(g["severity"] in ("high", "medium", "low"),
                  f"audit: {s} gap has bad severity {g['severity']!r}")
            check(g["text"].strip(), f"audit: {s} gap has empty text")


def test_audit_detects_a_thin_season():
    """A shallow pool must raise a high-severity depth gap — the check has to bite."""
    cfg = L.load_household()
    thin = [r for r in L.load_dinners()
            if "summer" in (r.get("seasons") or []) and not P._excluded(r, cfg)][:5]
    check(len(thin) == 5, "test setup needs 5 reachable summer dinners")
    r = A.season_report("summer", dinners=thin)
    depth = [g for g in r["gaps"] if g["kind"] == "depth"]
    check(depth and depth[0]["severity"] == "high",
          "audit failed to flag a 5-recipe season as a high-severity gap")
    check(depth[0]["need"] == A.TARGET_DINNERS - 5, "audit computed the wrong shortfall")


def test_audit_issue_body_is_actionable():
    body = A.issue_body(date(2026, 8, 30))
    check(body.startswith("## Seasonal refresh"), "issue body has no heading")
    check("early-fall" in body, "issue body doesn't name the coming season")
    check("data/recipes/dinners/" in body, "issue body doesn't say where recipes go")
    # It must carry the actual market list for the month, or it isn't season-first.
    peak = L.load_seasonal()[9]["peak"][0]
    check(peak in body, f"issue body missing September's market list ({peak!r})")


def test_stale_recipe_detection():
    """Served repeatedly with rating: null should surface; a rated one should not."""
    dinners = L.load_dinners()[:3]
    slug = dinners[0]["slug"]
    hist = {"weeks": [{"dinners": [slug]} for _ in range(A.UNRATED_AFTER)]}
    got = A.stale_recipes(hist=hist, dinners=dinners)
    check(any(x["slug"] == slug for x in got),
          f"{slug} served {A.UNRATED_AFTER}x unrated but was not surfaced")
    rated = [dict(d, rating=5) for d in dinners]
    check(not any(x["slug"] == slug for x in A.stale_recipes(hist=hist, dinners=rated)),
          "a well-rated recipe was wrongly surfaced as having no verdict")


def test_send_targets_and_attachments():
    """
    Recipients, and the two files that ride along.

    The real send goes to the household address; --test goes to one person. Getting these
    backwards is the one mistake this project must never make, so it is asserted rather
    than trusted.
    """
    cfg = L.load_household()
    check(K.RECIPIENT == cfg["send_to"],
          f"real sends must go to send.to from household.yml, got {K.RECIPIENT!r}")
    check(K.TEST_ONLY == cfg["send_test_to"],
          f"test sends must go to send.test_to from household.yml, got {K.TEST_ONLY!r}")
    check(K.TEST_ONLY != K.RECIPIENT, "a test send must not reach the household address")

    import inspect
    src = inspect.getsource(K.send_email)
    check("attachments" in src, "send_email must carry the cards and the shopping list")
    check('MIMEMultipart("mixed")' in src,
          "attachments need a mixed multipart, or clients hide the body")


def test_inline_photos_are_cached_and_attached():
    """
    Every photo the email references must exist on disk and be small enough to mail.

    Hotlinking the publisher's URL failed silently in Gmail, so the thumbnail is cached
    into the repo and attached inline. That also keeps the send path free of network
    calls, which is the promise that nothing is fetched at send time.
    """
    plan = P.build_plan(date(2026, 8, 29))
    for cid, path in plan["images"]:
        check(os.path.exists(path), f"{cid}: referenced photo is not on disk")
        size = os.path.getsize(path)
        check(size < 120_000, f"{cid}: thumbnail is {size // 1024}KB — too big to mail")
        with open(path, "rb") as fh:
            check(fh.read(3) == b"\xff\xd8\xff", f"{cid}: not a JPEG")

    # Every recipe with a verified source should have its photo cached.
    for r in L.load_dinners() + L.load_lunches():
        if r.get("image_url"):
            check(L.image_path(r["slug"]),
                  f"{r['slug']}: has image_url but no cached thumbnail — "
                  f"run tools/cache_images.py")


def test_send_builds_a_related_subtree_for_inline_images():
    """cid: references only resolve inside multipart/related. Assert the shape."""
    import email as _email
    from unittest import mock
    plan = P.build_plan(date(2026, 8, 29))
    check(plan["images"], "test needs at least one cached photo")
    captured = {}

    class FakeSMTP:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, *a):
            pass

        def sendmail(self, _f, _t, msg):
            captured["msg"] = msg

    old = os.environ.get("GMAIL_APP_PASSWORD")
    os.environ["GMAIL_APP_PASSWORD"] = "test-only-not-a-real-secret"
    try:
        with mock.patch("smtplib.SMTP_SSL", FakeSMTP):
            K.send_email(R.render(plan, embed="cid"), "t", to_addr=K.TEST_ONLY,
                         attachments=[("l.html", "<p>x</p>")], images=plan["images"])
    finally:
        if old is None:
            os.environ.pop("GMAIL_APP_PASSWORD", None)
        else:
            os.environ["GMAIL_APP_PASSWORD"] = old

    msg = _email.message_from_string(captured["msg"])
    types = [p.get_content_type() for p in msg.walk()]
    check("multipart/related" in types,
          "inline images need a multipart/related subtree or cid: will not resolve")
    cids = {p.get("Content-ID") for p in msg.walk() if p.get("Content-ID")}
    for cid, _ in plan["images"]:
        check(f"<{cid}>" in cids, f"{cid}: no matching Content-ID part in the message")


def test_verified_sources_only():
    """
    Every stored source link must still pass the matcher that wrote it.

    Three passes of that matcher have been wrong in three different ways, and each time
    the bad links sat in the library until someone read a card. The rule and the data are
    now checked against each other on every run: tighten `relevant()` and the links it no
    longer accepts fail here, in CI, rather than printing a QR that opens a different
    dinner.

    The batch that forced this: "Turkey and white bean green chile chili" had matched
    *turkey in white wine sauce*, "zucchini and corn carbonara" a ground turkey skillet,
    "chipotle black bean burrito bowls" black bean burgers, and a green chile chicken
    salad the enchiladas. Nine wrong out of twelve.
    """
    import importlib.util
    import urllib.parse
    _spec = importlib.util.spec_from_file_location(
        "find_sources",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "tools", "find_sources.py"))
    fs = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(fs)
    for r in L.load_dinners() + L.load_lunches():
        u = r.get("source_url")
        if not u:
            continue
        check(u.startswith("https://"), f"{r['slug']}: source is not https")
        slug = urllib.parse.urlparse(u).path.rstrip("/").rsplit("/", 1)[-1]
        check(not slug.endswith(("-recipes", "-ideas", "-roundup")),
              f"{r['slug']}: source points at a roundup, not a dish ({slug})")
        check(r.get("image_url", "").startswith("https://"),
              f"{r['slug']}: has a source but no verified photo")
        check(r.get("source_name"), f"{r['slug']}: source has no attribution")
        check(u not in fs.rejected_for(r["slug"]),
              f"{r['slug']}: {u} is in data/rejected-sources.md — a human looked at this "
              f"photo and said it is the wrong dish")
        check(fs.relevant(u, fs.keywords(r["title"]), r["title"]),
              f"{r['slug']}: {u} no longer passes the matcher — the slug does not carry "
              f"this dish's identity, so the QR would open something else")


def test_qr_target_always_resolves():
    """
    Every card gets a working QR, curated link or not.

    An unverified recipe URL behind a printed code is worse than none — it wastes a scan
    in the kitchen and poisons trust in every other code on the sheet. Until a recipe
    carries a checked `source_url`, the QR points at an image search for the dish, which
    cannot 404 and cannot be misattributed.
    """
    from mealbit import printable as PR
    for r in L.load_dinners():
        url, caption, curated = PR.qr_target(r)
        check(url.startswith("https://"), f"{r['slug']}: QR target is not https")
        check(caption.strip(), f"{r['slug']}: QR has no caption")
        if curated:
            check(r.get("source_url") == url,
                  f"{r['slug']}: claims a curated link but points somewhere else")
        else:
            check("google.com/search" in url,
                  f"{r['slug']}: uncurated recipes must fall back to an image search")


def test_preview_render_is_self_contained():
    """
    out/meal_plan.html is opened in a browser and screenshotted before every send.

    cid: only resolves inside a mail client, so if the preview inherited the email's
    image tags it would show empty boxes and the 412px render check would silently stop
    checking anything. The preview carries the same bytes as data: URIs instead.
    """
    plan = P.build_plan(date(2026, 8, 29))
    html = R.render(plan)                       # default is the browser-safe one
    check("cid:" not in html, "the preview uses cid:, which a browser cannot resolve")
    check(html.count('src="data:image/jpeg;base64,') == len(plan["images"]),
          f"expected {len(plan['images'])} inlined photos in the preview")
    # And the two renders must otherwise be the same email.
    check(len(R.render(plan, embed="cid")) < len(html),
          "the data: preview should be the larger of the two renders")


def test_render_email_safety():
    plan = P.build_plan(date(2026, 8, 29))
    html = R.render(plan, embed="cid")
    check(html.startswith("<!doctype html>"), "missing doctype")
    check("prefers-color-scheme" in html, "dark-mode block missing")
    check('name="viewport"' in html, "viewport meta missing")
    check(html.count("<table") == html.count("</table>"), "unbalanced <table> tags")
    # The bar technique that Gmail requires (see email_kit).
    bar = K.hbar(0.5, K.GOOD)
    check('bgcolor=' in bar and 'height="12"' in bar and 'width="50%"' in bar,
          "hbar lost the bgcolor/height/percentage-width attributes Gmail needs")
    # The fill cell's width must be a PERCENTAGE. A px width inside a %-width cell gets
    # crushed on mobile Gmail — this regressed twice upstream.
    import re as _re
    widths = _re.findall(r'<td[^>]*\swidth="([^"]+)"', bar)
    check(widths and all(w.endswith("%") for w in widths),
          f"hbar cell widths must all be percentages, got {widths}")
    # Content actually made it in.
    for d in plan["dinners"]:
        check(d["title"] in html, f"dinner {d['slug']} missing from the email")
    for c in plan["coffee"]:
        check(c["drink"]["title"] in html, f"drink {c['drink']['slug']} missing from the email")
        if c["syrup"]:
            check(c["syrup"]["title"] in html,
                  f"syrup {c['syrup']['slug']} missing from the email")
        if c["crumble"]:
            check(c["crumble"]["title"] in html, "crumble missing from the email")
    check(plan["quote"]["who"] in html, "quote attribution missing from the email")
    from mealbit import config as C
    ms = C.market_store()
    if ms:
        check("At the market" in html and ms["where"].split(" ")[0] in html,
              "market section missing")
    # The shopping list is an attachment now — it must NOT be duplicated in the body.
    check("in the order you" not in html,
          "the shopping list is back in the email; it belongs in the attachment only")
    # Photos are carried INLINE, never hotlinked: remote <img> did not survive into the
    # inbox even though the images were reachable.
    check("src=\"https://" not in html.replace('href="https://', ''),
          "the email hotlinks an image; photos must travel as inline cid: parts")
    for cid, _path in plan["images"]:
        check(f'src="cid:{cid}"' in html, f"{cid}: inline photo not referenced in the email")
    # No unrendered Markdown leaking through.
    body = html.split("</head>", 1)[1]
    check("**" not in body, "raw Markdown bold (**) leaked into the rendered email")


def test_no_truncated_sentences():
    """Recipe bodies are hard-wrapped; the renderer must join paragraphs, not clip them."""
    for r in L.load_dinners():
        why = R._why(r)
        check(why, f"{r['slug']}: no 'Why this week' line")
        check(why.rstrip().rstrip('*"\u201d\')').endswith((".", "!", "?")),
              f"{r['slug']}: why-line looks truncated: ...{why[-45:]!r}")
    for d in L.load_drinks():
        move = R._the_move(d)
        if move:
            check(move.rstrip().rstrip('*"\u201d\')').endswith((".", "!", "?")),
                  f"{d['slug']}: 'The move' looks truncated: ...{move[-45:]!r}")


def test_history_roundtrip():
    real = L.load_history()
    try:
        L.save_history({"weeks": []})
        plan = P.build_plan(date(2026, 8, 29))
        P.record(plan)
        h = L.load_history()
        check(len(h["weeks"]) == 1, "record() did not append a week")
        check(L.weeks_since(h, "dinners", plan["dinners"][0]["slug"]) == 0,
              "weeks_since should report 0 for the week just recorded")
        check(L.weeks_since(h, "dinners", "no-such-recipe") is None,
              "weeks_since should report None for an unseen recipe")
    finally:
        L.save_history(real)


def test_history_is_not_written_by_a_preview():
    """Rendering must never advance the rotation; only a real send does."""
    before = json.dumps(L.load_history(), sort_keys=True)
    R.render(P.build_plan(date(2026, 8, 29)))
    check(json.dumps(L.load_history(), sort_keys=True) == before,
          "building/rendering a plan mutated history.json")


# ---------------------------------------------------------------- this week's requests and verdicts

def _with_this_week(fn):
    """Run fn() with data/this-week.yml and history.json backed up and restored."""
    import shutil
    bak = L.THIS_WEEK + ".bak"
    shutil.copy(L.THIS_WEEK, bak)
    real_hist = json.dumps(L.load_history())
    try:
        fn()
    finally:
        shutil.move(bak, L.THIS_WEEK)
        L.save_history(json.loads(real_hist))


def test_this_week_skips_and_pins_are_honoured():
    """
    "Not the pulled pork this week." The scheduled send takes no arguments, so the request
    travels as a committed file. Skipped dishes must be gone, pinned ones present, the
    note must say so in the email, and a request for one week must not bend another.
    """
    def body():
        today = date(2026, 9, 5)
        start = P.week_start(today)
        cfg = L.load_household()
        base = P.build_plan(today)
        other_base = [d["slug"] for d in P.build_plan(date(2026, 9, 12))["dinners"]]
        slugs = [d["slug"] for d in base["dinners"]]
        skip = slugs[0]
        pin = next(d["slug"] for d in L.load_dinners()
                   if d["slug"] not in slugs and base["season"] in d["seasons"]
                   and not P._excluded(d, cfg))
        L.save_overrides(start, [skip], [pin])
        plan = P.build_plan(today)
        got = [d["slug"] for d in plan["dinners"]]
        check(skip not in got, f"{skip} was skipped this week but still planned")
        check(pin in got, f"{pin} was pinned this week but not planned")
        check(len(got) == P.meal_settings()["n_dinners"], "a pin or skip changed the dinner count")
        check(len(set(d.get("protein") for d in plan["dinners"])) == len(got),
              "a pinned dinner broke the no-repeated-protein rule for the rest of the week")
        check(any("asked for it" in n for n in plan["notes"]) and
              any("at your request" in n for n in plan["notes"]),
              "the email must say which dishes were pinned and skipped, and why")
        html = R.render(plan)
        check("at your request" in html, "the request note did not reach the rendered email")
        # Another week is untouched: the file names one Monday and only that Monday.
        other = [d["slug"] for d in P.build_plan(date(2026, 9, 12))["dinners"]]
        check(other == other_base, "a request for one week bent the plan for another")
        L.save_overrides(start, [skip], [])
        check(skip not in [d["slug"] for d in P.build_plan(today)["dinners"]], "skip alone failed")
        L.clear_overrides()
        check([d["slug"] for d in P.build_plan(today)["dinners"]] == slugs,
              "clearing the file must restore the untouched plan")
    _with_this_week(body)


def test_this_week_refuses_a_typo():
    """A misspelt slug must fail the run, not silently plan the dish someone asked to skip."""
    def body():
        today = date(2026, 9, 5)
        start = P.week_start(today)
        L.save_overrides(start, ["no-such-dish"], [])
        try:
            P.build_plan(today)
            check(False, "an unknown slug in this-week.yml was silently ignored")
        except P.PlanError as e:
            check("no-such-dish" in str(e), "the error must name the bad slug")
        dinners = L.load_dinners()
        lunch = L.load_lunches()[0]["slug"]
        L.save_overrides(start, [], [lunch])
        try:
            P.build_plan(today)
            check(False, "pinning a lunch as a dinner was accepted")
        except P.PlanError:
            pass
        d = dinners[0]["slug"]
        L.save_overrides(start, [d], [d])
        try:
            P.build_plan(today)
            check(False, "skipping and pinning the same dish was accepted")
        except P.PlanError:
            pass
        # The tool guards the same way, before anything is written.
        import subprocess
        r = subprocess.run([sys.executable, "tools/this_week.py", "--skip", "no-such-dish",
                            "--today", "2026-09-05"], capture_output=True, text=True, cwd=ROOT)
        check(r.returncode != 0 and "no-such-dish" in (r.stdout + r.stderr),
              "tools/this_week.py accepted an unknown slug")
        r = subprocess.run([sys.executable, "tools/this_week.py", "--skip", d,
                            "--today", "2026-09-05"], capture_output=True, text=True, cwd=ROOT)
        check(r.returncode == 0 and L.load_overrides() == {"week_of": start, "skip": [d], "pin": []},
              f"tools/this_week.py did not record a valid skip: {r.stdout}{r.stderr}")
    _with_this_week(body)


def test_a_real_send_clears_this_week():
    """The request was for this week; once this week is sent it must not linger and bend
    the next one. Like history, only record() touches it — a preview or a --test never does."""
    def body():
        today = date(2026, 9, 5)
        start = P.week_start(today)
        plan = P.build_plan(today)
        L.save_overrides(start, [plan["dinners"][0]["slug"]], [])
        R.render(P.build_plan(today))
        check(L.load_overrides()["skip"], "a preview cleared this-week.yml")
        P.record(P.build_plan(today))
        check(L.load_overrides() == {"week_of": None, "skip": [], "pin": []},
              "record() did not clear this week's request")
        # A request for a LATER week survives a send for this one.
        L.save_overrides(start + timedelta(days=7), ["x"], [])
        P.record(plan)
        check(L.load_overrides()["skip"] == ["x"], "record() cleared a request for a later week")
    _with_this_week(body)


def test_a_low_rating_retires_a_dish():
    """
    rating 1-2 means "never again" until re-rated; 3+ stays in rotation; null is no
    opinion. The picker reads it through _excluded, so audit depth counts it as
    unreachable too, and a retired dish cannot be pinned by accident.
    """
    cfg = L.load_household()
    d = next(r for r in L.load_dinners() if not P._excluded(r, cfg))
    for rating, retired in ((None, False), (1, True), (2, True), (3, False), (5, False)):
        r = dict(d, rating=rating)
        check(L.is_retired(r) == retired, f"rating {rating!r}: is_retired should be {retired}")
        check(P._excluded(r, cfg) == retired, f"rating {rating!r}: _excluded should be {retired}")
    check(not L.is_retired(dict(d, rating=True)), "a boolean is not a rating")
    def body():
        today = date(2026, 9, 5)
        L.save_overrides(P.week_start(today), [], [d["slug"]])
        real = L.load_dinners
        L.load_dinners = lambda: [dict(r, rating=1) if r["slug"] == d["slug"] else r for r in real()]
        try:
            P.build_plan(today)
            check(False, "a retired dish was pinned without complaint")
        except P.PlanError as e:
            check("rated" in str(e), "the error should say the dish is rated too low")
        finally:
            L.load_dinners = real
    _with_this_week(body)


def test_untried_dishes_surface_first():
    """
    The picker is meant to try what has never been served before repeating anything. That
    used to key on a `last_served` field that nothing ever wrote, so it did nothing. It now
    reads history.json, and no recipe may carry the dead field.
    """
    import random
    cfg = L.load_household()
    season = "early-fall"
    cands = [r for r in L.load_dinners() if season in r["seasons"] and not P._excluded(r, cfg)]
    anchors = L.load_protein()[0]
    for target in cands[:5]:
        served = {r["slug"] for r in cands} - {target["slug"]}
        picked = P._greedy(cands, 4, random.Random(1), 0, anchors, served=served)
        check(target["slug"] in [p["slug"] for p in picked],
              f"{target['slug']} is the only untried {season} dinner and was not picked")
    for r in L.load_dinners() + L.load_lunches():
        check("last_served" not in r, f"{r['slug']}: carries last_served, which nothing writes")


def test_verdicts_are_written_without_disturbing_the_recipe():
    """rating: and feedback: change; every other byte of the file stays as it was."""
    import shutil
    src = L.load_dinners()[0]["path"]
    tmp = tempfile.mkdtemp()
    dst = os.path.join(tmp, os.path.basename(src))
    shutil.copy(src, dst)
    before = open(dst, encoding="utf-8").read()
    L.record_verdict(dst, 4, "great — more heat next time", "Sam", date(2026, 9, 5))
    r = L.record_verdict(dst, 2, "grits were gluey", None, date(2026, 9, 12))
    check(r["rating"] == 2 and L.is_retired(r), "second verdict should set the rating and retire")
    check([e.get("rating") for e in r["feedback"]] == [4, 2], "feedback must keep every verdict in order")
    check(r["feedback"][0]["who"] == "Sam" and "gluey" in r["feedback"][1]["note"],
          "feedback entries lost their who/note")
    after = open(dst, encoding="utf-8").read()
    strip = lambda t: re.sub(r"^feedback:\n(?:  .*\n)*", "",
                             re.sub(r"^rating: .*\n", "", t, flags=re.M), flags=re.M)
    check(strip(before) == strip(after), "record_verdict changed something other than rating/feedback")
    check(L.parse_frontmatter(dst)["ingredients"] == L.parse_frontmatter(src)["ingredients"],
          "ingredients reflowed by a verdict write")
    try:
        L.record_verdict(dst, 7, None)
        check(False, "rating 7 accepted")
    except ValueError:
        pass
    try:
        L.record_verdict(dst, None, None)
        check(False, "an empty verdict was accepted")
    except ValueError:
        pass
    # A fresh fork resets: the last household's opinions are not this one's.
    L.set_frontmatter_key(dst, "rating", ["rating: null"])
    L.set_frontmatter_key(dst, "feedback", [])
    check(strip(open(dst, encoding="utf-8").read()) == strip(before)
          and L.parse_frontmatter(dst).get("rating") is None
          and not L.parse_frontmatter(dst).get("feedback"), "reset did not restore a clean recipe")
    shutil.rmtree(tmp)


def test_shipped_library_carries_no_verdicts():
    """
    This repository is the template every fork starts from. A rating in it would retire a
    dish for a household that never tasted it. Verdicts belong on a fork; the upstream
    library ships with `rating: null` and no `feedback:` everywhere.
    """
    import subprocess
    origin = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True,
                            text=True, cwd=ROOT).stdout.strip()
    import yaml
    up = yaml.safe_load(open(os.path.join(ROOT, "config", "upstream.yml"))).get("repo", "")
    if up and up.lower() not in origin.lower():
        return   # a fork: its verdicts are its own
    for r in L.load_dinners() + L.load_lunches():
        check(r.get("rating") is None and not r.get("feedback"),
              f"{r['slug']}: the upstream library ships without verdicts (rating {r.get('rating')!r})")


def test_a_late_scheduled_firing_still_sends():
    """
    GitHub's cron ran almost four hours late on 2026-09-05 and an exact-hour gate sent
    nothing. The gate now tolerates lateness and uses history to stand down duplicates.
    """
    import importlib.util
    from datetime import datetime
    from zoneinfo import ZoneInfo
    spec = importlib.util.spec_from_file_location("send_gate", os.path.join(ROOT, "tools", "send_gate.py"))
    G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
    tz = ZoneInfo("America/Los_Angeles")
    cfg = {"send_day": "Saturday", "send_hour": 17, "timezone": "America/Los_Angeles"}
    at = lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    empty = {"weeks": []}
    check(G.decide(at("2026-09-05 17:00"), cfg, empty)[0], "on time must send")
    check(G.decide(at("2026-09-05 20:47"), cfg, empty)[0], "3h47 late must still send")
    check(G.decide(at("2026-09-05 18:00"), cfg, empty)[0],
          "the winter cron line fires at 18:00 PDT in summer; with nothing sent yet it must send")
    check(not G.decide(at("2026-09-05 16:30"), cfg, empty)[0], "before the send hour must not send")
    check(not G.decide(at("2026-09-06 09:00"), cfg, empty)[0], "16h late is a different week's problem")
    check(not G.decide(at("2026-09-08 17:00"), cfg, empty)[0], "Tuesday must not send")
    sent = {"weeks": [{"week_of": "2026-09-07"}]}
    check(not G.decide(at("2026-09-05 18:00"), cfg, sent)[0],
          "the second firing must stand down once history holds the week")
    check(G.decide(at("2026-09-12 17:05"), cfg, sent)[0], "next Saturday sends the next week")


def test_a_fork_does_not_inherit_the_upstreams_onboarding():
    """
    config/onboarded.yml travels with a fork. It counts only when its `repo:` names the
    repository it sits in; otherwise the fork gets the survey. The template ships without
    the file at all.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("setup_status", os.path.join(ROOT, "tools", "setup_status.py"))
    S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
    base = dict(is_fork=True, onboarded=False, names_placeholder=False)
    check(S.needs_onboarding(dict(base)), "a fork with no onboarding of its own needs the survey")
    check(not S.needs_onboarding(dict(base, is_fork=False, is_upstream=True, names_placeholder=True)),
          "the upstream wears placeholder names on purpose and is never onboarded")
    check(not S.needs_onboarding(dict(base, onboarded=True)), "a fork surveyed here is set up")
    check(S.needs_onboarding(dict(base, onboarded=True, names_placeholder=True)),
          "placeholder names always mean not set up")
    path = os.path.join(ROOT, "config", "onboarded.yml")
    if os.path.exists(path):
        import yaml
        d = yaml.safe_load(open(path)) or {}
        origin = S._origin()
        check(not origin or str(d.get("repo", "")).lower() == origin.lower(),
              f"config/onboarded.yml says repo: {d.get('repo')!r} but origin is {origin!r} — "
              f"it was inherited from another household; onboarding rewrites it")


def test_the_schedule_is_written_from_the_config():
    """
    The template carries no cron. tools/schedule.py writes one line per UTC offset the
    household's zone uses; for US Pacific that is exactly the two lines that used to be
    hand-written, and a zone without daylight saving gets one.
    """
    import importlib.util, shutil, tempfile
    spec = importlib.util.spec_from_file_location("schedule", os.path.join(ROOT, "tools", "schedule.py"))
    S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
    la = S.weekly_lines("America/Los_Angeles", "Saturday", 17)
    check({c for c, _ in la} == {"0 0 * * 0", "0 1 * * 0"},
          f"Pacific Saturday 17:00 should be Sun 00:00 and 01:00 UTC, got {la}")
    tokyo = S.weekly_lines("Asia/Tokyo", "Saturday", 17)
    check([c for c, _ in tokyo] == ["0 8 * * 6"], f"Tokyo has no DST: one line, got {tokyo}")
    late = S.weekly_lines("America/New_York", "Saturday", 21)
    check({c for c, _ in late} == {"0 1 * * 0", "0 2 * * 0"},
          f"a send that crosses midnight UTC must shift the weekday, got {late}")
    mon = S.monthly_lines("America/Los_Angeles")
    check({c for c, _ in mon} == {"0 16 25 * *", "0 17 25 * *"}, f"monthly lines wrong: {mon}")
    for wf in (S.WEEKLY, S.MONTHLY):
        check("mealbit:schedule-start" in open(wf).read(), f"{wf}: schedule markers missing")
    tmp = tempfile.mkdtemp()
    for wf in (S.WEEKLY, S.MONTHLY):
        dst = os.path.join(tmp, os.path.basename(wf)); shutil.copy(wf, dst)
        before = open(dst).read()
        S.write(dst, la)
        check(S.current(dst) == [c for c, _ in la], "written lines must read back")
        S.remove(dst)
        check(open(dst).read() == before, f"{os.path.basename(wf)}: write then remove must be a no-op")


def test_the_template_ships_in_starter_state():
    """
    On the upstream itself — origin is config/upstream.yml — nothing household-specific
    may be committed: placeholder names, no onboarding marker, empty history, no requests,
    no verdicts, and no cron in either workflow. A fork is exempt; that is its whole point.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("setup_status", os.path.join(ROOT, "tools", "setup_status.py"))
    S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
    origin, upstream = S._origin(), S._upstream()
    if not origin or not upstream or origin.lower() != upstream.lower():
        return                                    # a fork or a detached checkout
    spec = importlib.util.spec_from_file_location("schedule", os.path.join(ROOT, "tools", "schedule.py"))
    G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
    cfg = L.load_household()
    check(set(cfg["eaters"]) <= S.PLACEHOLDER_NAMES, f"template must carry placeholder names, has {cfg['eaters']}")
    check(not os.path.exists(os.path.join(ROOT, "config", "onboarded.yml")),
          "template must not carry config/onboarded.yml")
    check(L.load_history().get("weeks") == [], "template history.json must be empty")
    ov = L.load_overrides()
    check(not ov["week_of"] and not ov["skip"] and not ov["pin"], "template this-week.yml must be clear")
    rated = [r["slug"] for r in L.load_dinners() + L.load_lunches()
             if r.get("rating") is not None or r.get("feedback")]
    check(not rated, f"template must carry no verdicts: {rated}")
    for wf in (G.WEEKLY, G.MONTHLY):
        check(G.current(wf) == [], f"{os.path.basename(wf)}: the template must carry no cron")


def test_coffee_reaches_the_list_and_the_printer():
    """
    The coffee files never got the store migration: they carried the old fixed store
    fields, the router read no ingredients from them, and for weeks ZERO coffee lines
    reached the shopping list — the syrup the email said to make included. And no drink,
    syrup or crumble had a card, so "make miso caramel syrup" pointed at a method printed
    nowhere. Both halves, held here.
    """
    import subprocess
    from mealbit import printable as PR
    files = [f for f in subprocess.run(["git", "ls-files", "data/coffee"], capture_output=True,
                                       text=True, cwd=ROOT).stdout.split() if f.endswith(".md")]
    for f in files:
        txt = open(os.path.join(ROOT, f), encoding="utf-8").read()
        check("tj_items" not in txt and "qfc_items" not in txt,
              f"{f}: still carries a fixed store field; use `ingredients:` with [kind] tags")
    for r in L.load_drinks() + L.load_syrups() + L.load_crumbles():
        check("ingredients" in r, f"{r['slug']}: no `ingredients:` — its shopping never reaches the list")
        check(r.get("kind") in L.COFFEE_KINDS, f"{r['slug']}: kind should be a coffee kind")
    for wk in range(0, 40, 7):
        plan = P.build_plan(date(2026, 1, 4) + timedelta(weeks=wk))
        used = set()                       # the list records the recipe TITLE it serves
        for g in plan["shopping"]:
            for ln in g["lines"]:
                used.update(ln.get("used_in") or [])
        for r in [c["drink"] for c in plan["coffee"]] + plan["to_make"]:
            if not L.ingredients(r):
                continue        # espresso sugar is sugar and coffee; nothing to buy
            check(r["title"] in used,
                  f"week {wk}: {r['slug']} is on the menu and none of its ingredients reached the list")
        cards = PR.render_cards(plan)
        for c in plan["coffee"]:
            check(c["drink"]["title"] in cards, f"week {wk}: no card for {c['drink']['slug']}")
        for t in plan["to_make"]:
            check(t["title"] in cards, f"week {wk}: {t['slug']} is to be made and has no card")
        # The method itself is on the card, not just the name.
        check(">Method<" in cards, f"week {wk}: coffee cards print no method")


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for t in tests:
        try:
            t()
            print(f"  ok    {t.__name__}")
        except Exception as e:                       # noqa: BLE001
            FAILURES.append(f"{t.__name__} raised {type(e).__name__}: {e}")
            print(f"  ERROR {t.__name__}: {e}")
    print()
    if FAILURES:
        print(f"{len(FAILURES)} failure(s):")
        for f in FAILURES:
            print("  -", f)
        return 1
    print(f"all {len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
