#!/usr/bin/env python3
"""
Recipe / drink / quote library loader.

Everything the planner reads lives in `data/` as Markdown with YAML frontmatter, so
Anyone in the household can open a file, edit it, and see the change in the next newsletter.
That reviewability is the whole reason this is a library and not a prompt (see the
build brief, section 5).

Ingredient lines are strings, in the form:

    "2 lb chicken thighs || or any dark-meat chicken"
     ^qty ^unit ^name        ^fallback, market items only

The fallback after `||` is what makes market lines degrade gracefully: a farmers
market is seasonal and variable, so no line may promise a specific vegetable.
"""
import os
import re
import json
from datetime import date
import unicodedata

import yaml
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

SEASON_ORDER = ["deep-winter", "early-spring", "late-spring",
                "summer", "early-fall", "late-fall"]

# Units we recognize when consolidating. Anything unrecognized is treated as part of
# the ingredient name and the line is summed as a bare count.
UNITS = {
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    "oz": "oz", "ounce": "oz", "ounces": "oz",
    "g": "g", "kg": "kg",
    "cup": "cup", "cups": "cup",
    "tbsp": "tbsp", "tsp": "tsp",
    "pint": "pint", "pints": "pint", "quart": "quart", "quarts": "quart",
    "bunch": "bunch", "bunches": "bunch",
    "head": "head", "heads": "head",
    "can": "can", "cans": "can", "jar": "jar", "jars": "jar",
    "package": "package", "packages": "package", "pkg": "package",
    "bag": "bag", "bags": "bag", "box": "box", "boxes": "box",
    "bottle": "bottle", "bottles": "bottle",
    "container": "container", "containers": "container",
    "block": "block", "blocks": "block",
    "clove": "clove", "cloves": "clove",
    "stalk": "stalk", "stalks": "stalk",
    "ear": "ear", "ears": "ear",
    "sprig": "sprig", "sprigs": "sprig",
    "loaf": "loaf", "loaves": "loaf",
    "dozen": "dozen", "wedge": "wedge", "stick": "stick", "sticks": "stick",
    "knob": "knob", "tin": "tin", "tins": "tin", "ball": "ball", "balls": "ball",
    "slice": "slice", "slices": "slice", "piece": "piece", "pieces": "piece",
    "pinch": "pinch", "inch": "inch",
    "packet": "packet", "packets": "packet", "tub": "tub", "tubs": "tub",
    "bar": "bar", "bars": "bar", "sheet": "sheet", "sheets": "sheet",
}

VULGAR = {"½": 0.5, "⅓": 1 / 3, "⅔": 2 / 3, "¼": 0.25, "¾": 0.75, "⅛": 0.125}

# Words that describe the SHOPPER's intent rather than the item, and would otherwise
# fragment the consolidated list ("2 lb small potatoes" vs "1 lb potatoes").
_NOISE = re.compile(
    r"\b(small|large|medium|big|ripe|good|quality|mixed|assorted|any|preferably)\b",
    re.I)

# Variety words that describe the same shopping item. "2 bunches flat-leaf parsley" and
# "1 bunch parsley" were two lines for one herb, so the week bought three bunches of it.
_VARIETY = re.compile(r"^(flat-leaf|flat leaf|italian|curly|fresh|baby|young)\s+", re.I)


# ---------------------------------------------------------------- frontmatter

def parse_frontmatter(path):
    """Split a `---`-delimited YAML frontmatter block from its Markdown body."""
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", raw, re.S)
    if not m:
        raise ValueError(f"{path}: no YAML frontmatter block")
    meta = yaml.safe_load(m.group(1)) or {}
    meta["body"] = m.group(2).strip()
    meta["slug"] = os.path.splitext(os.path.basename(path))[0]
    meta["path"] = path
    return meta


def _yaml_block(path):
    """Pull the single fenced ```yaml block out of a prose Markdown file."""
    txt = open(path, encoding="utf-8").read()
    m = re.search(r"```yaml\n(.*?)```", txt, re.S)
    if not m:
        raise ValueError(f"{path}: expected a ```yaml block")
    return yaml.safe_load(m.group(1))


# ---------------------------------------------------------------- ingredients

# Words that are already singular but end in "s" — stripping it produces nonsense
# ("asparagu", "hummu", "molasse").
_NOT_PLURAL = {"asparagus", "hummus", "couscous", "molasses"}


def normalize(name):
    """Fold an ingredient name to a consolidation key."""
    n = unicodedata.normalize("NFKD", name.lower().strip())
    n = "".join(c for c in n if not unicodedata.combining(c))   # jalapeño -> jalapeno
    n = _NOISE.sub(" ", n)
    n = re.sub(r"\([^)]*\)", " ", n)          # drop parentheticals
    n = re.sub(r"[^a-z0-9\s'-]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    if not n:
        return n
    head = n.rsplit(" ", 1)[-1]
    if head in _NOT_PLURAL:
        return n
    # Naive singularization, enough for a grocery list. Order matters: the -es rules must
    # come before the bare -s rule or "radishes" becomes "radishe".
    for suf, rep in (("ies", "y"), ("oes", "o"), ("ches", "ch"), ("shes", "sh"),
                     ("xes", "x"), ("zes", "z"), ("sses", "ss"), ("ses", "s"), ("s", "")):
        if n.endswith(suf) and len(head) > len(suf) + 1:
            return n[: -len(suf)] + rep
    return n


def parse_item(line):
    """
    Parse one ingredient string into a dict.

    Returns qty (float or None), unit (str or None), name, fallback, raw.
    A missing quantity is normal ("olive oil") and consolidates as a bare mention.
    """
    raw = line.strip()
    # A trailing [kind] tag says what the ingredient IS — produce, protein, dairy... — so
    # the household's stores.yml can decide who sells it. It is not part of the name.
    kind = None
    m_kind = re.search(r"\s*\[([a-z]+)\]\s*$", raw)
    if m_kind:
        kind, raw = m_kind.group(1), raw[:m_kind.start()].rstrip()
    # A `{use}` amount is what the RECIPE uses, as opposed to what is bought: "1 bag
    # stone-ground grits {1 cup}". The list buys the bag; the card says a cup. `{whole}`
    # says the whole purchase goes in. A card that read "1 dozen eggs" for a katsu that
    # takes three is what this fixes.
    use = None
    m_use = re.search(r"\s*\{([^}]*)\}\s*", raw)
    if m_use:
        use = m_use.group(1).strip() or None
        raw = (raw[:m_use.start()] + " " + raw[m_use.end():]).strip()
    fallback = None
    if "||" in raw:
        raw, fallback = [p.strip() for p in raw.split("||", 1)]
        fallback = re.sub(r"^or\s+", "", fallback, flags=re.I).strip()

    rest = raw
    qty = None
    # A MIXED numeral first: "1½ lb", with or without a space. fmt_qty renders halves as
    # "1½", so anyone editing a recipe by hand will naturally type it back that way — and
    # before this, "1½ lb eggplant" parsed as one unit of an ingredient literally named
    # "½ lb eggplant", which then printed on the shopping list exactly like that.
    mixed = re.match(rf"^\s*(\d+)\s*([{''.join(VULGAR)}])\s*(.*)$", rest)
    m = None if mixed else re.match(
        r"^\s*(\d+\s+\d+/\d+|\d+/\d+|\d*\.\d+|\d+)\s*(.*)$", rest)
    if mixed:
        qty = float(mixed.group(1)) + VULGAR[mixed.group(2)]
        rest = mixed.group(3)
    elif m:
        tok, rest = m.group(1), m.group(2)
        try:
            qty = float(sum(Fraction(p) for p in tok.split()))
        except (ValueError, ZeroDivisionError):
            qty = None
    elif rest and rest[0] in VULGAR:
        qty, rest = VULGAR[rest[0]], rest[1:].strip()

    # Leading descriptors ("large", "ripe", "fresh") sit between the number and the unit
    # and would otherwise split one ingredient across two lines of the shopping list.
    while True:
        m = re.match(r"^([A-Za-z-]+)\s+(.+)$", rest)
        if m and _NOISE.fullmatch(m.group(1)):
            rest = m.group(2)
            continue
        break

    unit = None
    m = re.match(r"^([A-Za-z]+)\.?\s+(.*)$", rest)
    if m and m.group(1).lower() in UNITS:
        unit, rest = UNITS[m.group(1).lower()], m.group(2)

    name = _VARIETY.sub("", rest.strip(" ,")).strip()
    return {"kind": kind, "qty": qty, "unit": unit, "name": name, "use": use,
            "key": normalize(name), "fallback": fallback, "raw": line.strip()}


# Bought in a package that is bigger than the recipe's use. A line with one of these as
# its unit has to say what the recipe takes out of it, or the card lies about amounts.
PACKAGE_UNITS = {"bag", "jar", "block", "container", "bottle", "can", "tub", "box",
                 "package", "carton", "stick", "loaf", "dozen", "tin", "packet", "bar",
                 "tablet", "half-gallon", "four-pack", "jug", "wedge", "tube"}


def is_package(item):
    """True when the buy unit is a package the recipe only partly uses."""
    unit = (item.get("unit") or "").lower()
    if unit in PACKAGE_UNITS:
        return True
    # "1 half-gallon whole milk", "1 four-pack tonic water": the unit did not parse as a
    # word because of the hyphen, so it is the first word of the name.
    first = (item.get("name") or "").split(" ")[0].lower()
    return first in PACKAGE_UNITS



def ingredients(recipe):
    """
    The recipe's buyable lines, as written — each one carrying its [kind] tag.

    This is the single place the field name lives. Before, three fixed fields
    (three fixed store fields) filed every ingredient under a shop at authoring
    time, so adding a shop or moving house meant re-filing 358 lines. Now a recipe says
    what a thing is and config/stores.yml says who sells it.
    """
    return [str(x) for x in (recipe.get("ingredients") or [])]


def ingredient_kind(line):
    """The [kind] on one ingredient line, or None if it has none."""
    return parse_item(str(line))["kind"]


_UNIT_PLURAL = {"bunch": "bunches", "box": "boxes", "loaf": "loaves", "inch": "inches",
                "pinch": "pinches", "dozen": "dozen", "oz": "oz", "lb": "lb",
                "g": "g", "kg": "kg", "tbsp": "tbsp", "tsp": "tsp"}


def fmt_unit(unit, qty):
    """Pluralize a unit for display: 2 balls, 3 bunches, but still 2 lb and 3 oz."""
    if not unit:
        return ""
    if qty is None or qty <= 1:
        return unit
    return _UNIT_PLURAL.get(unit, unit + "s")


def fmt_name(name, qty, unit):
    """Pluralize a bare countable item for display: 4 cucumbers, not 4 cucumber."""
    if unit or qty is None or qty <= 1 or not name:
        return name
    # "2 sub rolls or a baguette" already names its own plural; pluralizing the tail
    # produces "a baguettes". Leave any compound or already-plural phrase alone.
    if " or " in name.lower() or re.search(r"\b\w+s\b", name.split(",")[0]):
        return name
    head = name.split(",")[0].split(" (")[0]
    # -o plurals are irregular enough that guessing produces "tomatos" one way and
    # "avocadoes" the other. The ones this library actually uses are listed.
    for sing, plural in (("tomato", "tomatoes"), ("potato", "potatoes")):
        if head.lower().endswith(sing):
            return name[:len(head) - len(sing)] + plural + name[len(head):]
    # Some things are already their own plural on a shopping list. "4 naans" is not how
    # anyone writes it down.
    if head.lower() in ("naan", "pita", "roti", "tofu", "rice", "couscous", "orzo"):
        return name
    if head.endswith(("s", "x", "z", "ch", "sh")):
        return name
    if head.endswith("y") and head[-2:-1] not in "aeiou":
        return name[:len(head) - 1] + "ies" + name[len(head):]
    return name[:len(head)] + "s" + name[len(head):]


def fmt_qty(qty):
    """Render a float quantity the way a shopper would write it."""
    if qty is None:
        return ""
    if abs(qty - round(qty)) < 1e-6:
        return str(int(round(qty)))
    for frac, glyph in ((0.25, "¼"), (0.5, "½"), (0.75, "¾"), (1 / 3, "⅓"), (2 / 3, "⅔")):
        whole = int(qty)
        if abs((qty - whole) - frac) < 0.02:
            return f"{whole}{glyph}" if whole else glyph
    return f"{qty:g}"


# ---------------------------------------------------------------- pantry

def load_pantry():
    """
    Read pantry.md into two sets.

    `staples`  — always suppressed from the shopping list. Four things, in practice:
                 salt, black pepper, olive oil, white vinegar. The household's list, verbatim.
    `rotation` — kept for the file format's sake; empty now. It used to hold garlic,
                 onions and citrus as "always in the house", which was the same optimism
                 that hid a missing bottle of rice vinegar on a Tuesday night.
    """
    path = os.path.join(DATA, "pantry.md")
    staples, rotation, in_rotation = set(), set(), False
    for line in open(path, encoding="utf-8"):
        if line.startswith("##"):
            in_rotation = "rotation" in line.lower()
            continue
        if line.startswith("- "):
            key = normalize(line[2:])
            (rotation if in_rotation else staples).add(key)
    return staples, rotation


# Above this many units, a rotation aromatic earns a line on the list anyway.
ROTATION_THRESHOLD = 2


def is_pantry(item, staples, rotation):
    if item["key"] in staples:
        return True
    if item["key"] in rotation:
        return not (item["qty"] and item["qty"] > ROTATION_THRESHOLD)
    return False


# ---------------------------------------------------------------- seasons

def _split_top_level(text):
    """Split on commas that are not inside parentheses ("tomatoes (the real ones, finally)")."""
    out, depth, buf = [], 0, ""
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            out.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        out.append(buf.strip())
    return [x for x in out if x]


def photo_credit(recipe):
    """
    Whose picture this is, when it isn't the recipe's own.

    A verified `image_url` comes from the published recipe the QR points at, and the
    card already names that site. A `photo_url` is somebody else's photograph of the
    same dish, used under a CC licence that requires attribution — so it gets a credit
    line, and the card says plainly that it is a photo of the dish rather than of this
    recipe.
    """
    if recipe.get("image_url") or not recipe.get("photo_url"):
        return ""
    return str(recipe.get("photo_credit") or "").strip()


def image_path(slug):
    """Cached thumbnail for a recipe, or None. Written by tools/cache_images.py."""
    p = os.path.join(DATA, "images", f"{slug}.jpg")
    return p if os.path.exists(p) else None


def load_shared_items():
    """
    Ingredients where ONE purchase covers the whole week, from data/portions.md.

    The consolidator sums, which is right for anything consumed in proportion to how much
    you cook and wrong for everything else. Three recipes each asking for "1 bunch
    cilantro" produced 3 bunches; a jar of pickled jalapeños that keeps for months was
    bought three times. For these, the list takes the LARGEST single requirement.
    """
    d = _yaml_block(os.path.join(DATA, "portions.md"))
    return [normalize(x) for x in (d.get("one_is_enough") or [])]


def load_protein():
    """
    Which `protein:` tags count as a protein dinner, from data/protein.md.

    Returns (anchor, light) as sets of tags. The brief: "3/4 meals have some kind of meat or
    high protein source in them." Asked where the line sat, she put meat, fish, tofu and
    eggs on the counting side and legumes on the other — the reading that actually
    enforces something. Counting legumes made the rule true 52 weeks out of 52 by
    construction; counting only meat left it short in 17 of them.
    """
    d = _yaml_block(os.path.join(DATA, "protein.md"))
    return set(d.get("anchor") or []), set(d.get("light") or [])


def _market_file(key):
    """Path of the configured farmers market's `availability:` or `tips:` file, or None."""
    from . import config as C
    m = C.market_store()
    return os.path.join(ROOT, m[key]) if m and m.get(key) else None


def load_market_availability():
    """
    What the household's farmers market can actually supply, from the model its store
    entry points at (config/stores.yml -> availability:). Empty sets if there is no market.
    """
    path = _market_file("availability")
    if not path:
        return {"never": set(), "year_round": set(), "fallback_exempt": set()}
    d = _yaml_block(path)
    return {"never": {normalize(x) for x in d.get("never") or []},
            "year_round": {normalize(x) for x in d.get("year_round") or []},
            "fallback_exempt": {normalize(x) for x in d.get("fallback_exempt") or []},
            "synonyms": {normalize(k): [normalize(v) for v in vals]
                         for k, vals in (d.get("synonyms") or {}).items()}}


def _head(key):
    return key.rsplit(" ", 1)[-1] if key else key


def load_market_staples():
    """
    Produce exempt from the `|| fallback` rule.

    Either it is at the market every week (nothing to fall back from) or it always routes
    to QFC (nothing to fall back to). Single source of truth: market-availability.md.
    """
    a = load_market_availability()
    return a["fallback_exempt"] | a["year_round"] | a["never"]


def market_has(item_key, month, avail=None, seasonal=None):
    """
    Can the household's farmers market credibly supply this, in this month?

    Returns (True, reason) or (False, reason). The reason is printed in the newsletter,
    because the only way this model gets better is a person correcting it after a market run.

    Matching is on the HEAD NOUN — "delicata squash" against a month listing "winter
    squash" — because that is how produce is actually named on a stall sign. Anything
    unrecognised defaults to QFC: sending someone to a stall that hasn't got it is worse
    than buying it at the shop they were driving past.
    """
    avail = avail or load_market_availability()
    seasonal = seasonal or load_seasonal()
    key = normalize(item_key)
    if key in avail["never"] or _head(key) in avail["never"]:
        return False, "not a Washington crop — the market never has it"
    # Check every word, not just the head: "4 celery stalks" keys to "celery stalk", whose
    # head noun is "stalk". The ingredient is celery.
    words = set(key.split())
    if key in avail["year_round"] or words & avail["year_round"]:
        return True, "at the market year-round"

    head = _head(key)
    wanted = set(avail["synonyms"].get(head, [head])) | {head}
    peak = seasonal.get(month, {}).get("peak", [])
    for entry in peak:
        words = set(normalize(entry).split())
        if wanted & words:
            return True, f"in season this month ({entry.split(' (')[0]})"
    return False, "not in season at the market this month"


def load_seasonal():
    """Parse seasonal-pnw.md into {month_number: {"season": bucket, "peak": [...]}}."""
    path = os.path.join(DATA, "seasonal-pnw.md")
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    out, cur = {}, None
    for line in open(path, encoding="utf-8"):
        s = line.strip()
        if s.startswith("## ") and s[3:] in months:
            cur = months.index(s[3:]) + 1
            out[cur] = {"season": None, "peak": []}
        elif cur and s.startswith("season:"):
            out[cur]["season"] = s.split(":", 1)[1].strip()
        elif cur and s.startswith("peak:"):
            out[cur]["_buf"] = s.split(":", 1)[1].strip()
        elif cur and out[cur].get("_buf") is not None and s and not s.startswith("#"):
            out[cur]["_buf"] += " " + s
        elif cur and s == "":
            if out[cur].get("_buf"):
                out[cur]["peak"] = _split_top_level(out[cur].pop("_buf"))
    for m in out:
        if out[m].get("_buf"):
            out[m]["peak"] = _split_top_level(out[m].pop("_buf"))
    return out


def adjacent_seasons(season, steps=1):
    """Seasons within `steps` of the given one, on the cyclical PNW calendar."""
    i = SEASON_ORDER.index(season)
    n = len(SEASON_ORDER)
    return [SEASON_ORDER[(i + d) % n] for d in range(-steps, steps + 1)]


# ---------------------------------------------------------------- loading

def _load_dir(sub, kind=None):
    d = os.path.join(DATA, sub)
    out = [parse_frontmatter(os.path.join(d, f))
           for f in sorted(os.listdir(d)) if f.endswith(".md")]
    if kind:
        for r in out:
            r.setdefault("kind", kind)
    return out


def load_dinners():
    return _load_dir("recipes/dinners", "dinner")


def load_lunches():
    return _load_dir("recipes/lunches", "lunch")


def load_drinks():
    return _load_dir("coffee/drinks", "drink")


def load_syrups():
    return _load_dir("coffee/syrups", "syrup")


def load_crumbles():
    return _load_dir("coffee/crumbles", "crumble")


COFFEE_KINDS = ("drink", "syrup", "crumble")


def needs_making(item, hist, kind):
    """
    Is this syrup or crumble actually out?

    Syrups and crumbles are standing inventory, not a weekly shop. A syrup made on the 1st
    is still in the fridge on the 25th. So its ingredients belong on the shopping list only
    when it has expired or was never made — putting vanilla syrup on the list every week is
    the fastest way to make the list stop being read, and a list that isn't read is worse
    than no list.
    """
    ago = weeks_since(hist, kind, item["slug"])
    if ago is None:
        return True, "never made"
    keeps = int(item.get("keeps_weeks") or 4)
    if ago >= keeps:
        return True, f"made {ago} weeks ago, keeps {keeps}"
    return False, f"made {ago} week(s) ago — still good for {keeps - ago} more"


def load_quotes():
    path = os.path.join(DATA, "coffee/quotes.md")
    txt = open(path, encoding="utf-8").read()
    m = re.search(r"```yaml\n(.*?)```", txt, re.S)
    quotes = yaml.safe_load(m.group(1))
    for i, q in enumerate(quotes):
        q["id"] = f"q{i:02d}"
    return quotes


def load_market_vendors():
    """Sourcing notes for the configured market (stores.yml -> tips:), or {} without one."""
    path = _market_file("tips")
    return _yaml_block(path) if path else {}


def load_coffee_economics():
    """
    Library-level drink costs from data/coffee/economics.md, with the household's own
    coffee-shop spend (config/household.yml -> coffee.monthly_coffee_spend / visits) laid
    over the top. avg_per_visit is derived, never typed.
    """
    econ = _yaml_block(os.path.join(DATA, "coffee/economics.md"))
    cfg = load_household()
    spend = cfg.get("monthly_coffee_spend")
    visits = cfg.get("monthly_visits")
    econ["monthly_coffee_spend"] = float(spend) if spend else None
    econ["monthly_visits"] = int(visits) if visits else None
    econ["avg_per_visit"] = (float(spend) / int(visits)) if spend and visits else None
    return econ


def load_household():
    """
    The household's knobs, from config/household.yml — flattened to the shape the planner
    has always consumed. See mealbit/config.py for the file and its validation.
    """
    from . import config as C
    cfg = C.household()
    for k in ("exclude_tags", "exclude_ingredients"):
        cfg[k] = [normalize(x) for x in (cfg.get(k) or [])]
    cfg["per_plate"] = {who: [normalize(x) for x in (items or [])]
                        for who, items in (cfg.get("per_plate") or {}).items()}
    return cfg

def per_plate_who(item, cfg=None):
    """
    The eaters who do NOT get this ingredient, from `per_plate:` in household.yml.

    "cilantro" -> the eater whose per_plate list names it. The card and the email
    name the person, because "one plate only" without a name is a coin toss at the stove.
    """
    cfg = cfg or load_household()
    key = normalize(str(item)).replace("raw ", "")
    out = []
    for who, items in (cfg.get("per_plate") or {}).items():
        for i in items:
            noun = i.replace("raw ", "")
            if noun and (noun in key or key in noun):
                out.append(who)
                break
    return out


def per_plate_items(cfg=None):
    """
    Ingredients that must never be built into a dish, flattened across eaters.

    A HARD EXCLUSION removes the recipe from the pool. A PER-PLATE item leaves the recipe
    in but forbids it from being load-bearing: it goes on one plate at the end, and the
    dish has to be complete without it. The two are not interchangeable — treating
    cilantro as an exclusion would delete a third of the library.

    This distinction was documented from the start and enforced nowhere, which is how
    panzanella shipped with raw tomato juice AS THE DRESSING. The person who skips raw tomato
    cannot eat that plate, and no amount of "add tomatoes to the other one" fixes a dressing.
    """
    cfg = cfg if cfg is not None else load_household()
    out = []
    for items in (cfg.get("per_plate") or {}).values():
        for x in items:
            if x not in out:
                out.append(x)
    return out


def restricted_in(recipe, restricted):
    """
    Which per-plate ingredients this recipe buys, as (restricted_key, ingredient_line).

    Substring both ways, for the same reason `_excluded` is: a restriction on "raw
    tomatoes" has to catch a line reading "3 lb ripe tomatoes, mixed", and one on
    "cilantro" has to catch "1 bunch cilantro".
    """
    hits = []
    for line in ingredients(recipe):
        if True:
            name = normalize(parse_item(str(line))["name"])
            if not name:
                continue
            for key in restricted:
                # "raw tomatoes" -> match on the noun; the raw/cooked question is what
                # the recipe answers explicitly, via per_plate or per_plate_exempt.
                noun = key.replace("raw ", "").strip()
                if noun and (noun in name or name in noun):
                    hits.append((key, str(line)))
                    break
    return hits


# ---------------------------------------------------------------- history

HISTORY = os.path.join(DATA, "history.json")


def load_history():
    if not os.path.exists(HISTORY):
        return {"weeks": []}
    try:
        return json.load(open(HISTORY, encoding="utf-8"))
    except json.JSONDecodeError:
        return {"weeks": []}


def save_history(hist):
    with open(HISTORY, "w", encoding="utf-8") as f:
        json.dump(hist, f, indent=2)
        f.write("\n")


def weeks_since(hist, kind, slug):
    """How many weeks back `slug` was last used, or None if never. 0 = most recent week."""
    for i, wk in enumerate(reversed(hist.get("weeks", []))):
        got = wk.get(kind)
        got = got if isinstance(got, list) else ([got] if got else [])
        if slug in got:
            return i
    return None


def ever_served(hist, kind):
    """Every slug of `kind` that has ever appeared in history. The picker puts what is NOT
    in this set first, so an untried recipe surfaces before a repeat."""
    out = set()
    for wk in hist.get("weeks", []):
        got = wk.get(kind)
        got = got if isinstance(got, list) else ([got] if got else [])
        out.update(got)
    return out


# ---------------------------------------------------------------- this week's overrides
#
# "Not the pulled pork this week." The scheduled send takes no arguments, so a request
# made on Tuesday has to reach Saturday's run through a committed file. The planner reads
# it for the week it names and the real send clears it. Written by tools/this_week.py.

THIS_WEEK = os.path.join(DATA, "this-week.yml")

_THIS_WEEK_TEMPLATE = """\
# This week's overrides. Written by the agent (tools/this_week.py) when someone says
# "not the pulled pork this week" or "put the katsu on the menu"; read by the planner for
# the week starting `week_of`; cleared by the real send. Slugs are file names under
# data/recipes/ without the .md. Nothing here is permanent — a dish you never want again
# is a verdict (tools/verdict.py), not a skip.
week_of: {week_of}
skip: {skip}
pin: {pin}
"""


def load_overrides():
    """{"week_of": date|None, "skip": [slugs], "pin": [slugs]} — empty when nothing is set."""
    empty = {"week_of": None, "skip": [], "pin": []}
    if not os.path.exists(THIS_WEEK):
        return empty
    raw = yaml.safe_load(open(THIS_WEEK, encoding="utf-8")) or {}
    week_of = raw.get("week_of")
    if isinstance(week_of, str):
        week_of = date.fromisoformat(week_of)
    return {"week_of": week_of,
            "skip": [str(x) for x in (raw.get("skip") or [])],
            "pin": [str(x) for x in (raw.get("pin") or [])]}


def save_overrides(week_of, skip=(), pin=()):
    def _list(xs):
        xs = list(dict.fromkeys(xs))
        return "[" + ", ".join(xs) + "]"
    with open(THIS_WEEK, "w", encoding="utf-8") as f:
        f.write(_THIS_WEEK_TEMPLATE.format(
            week_of=week_of.isoformat() if week_of else "null",
            skip=_list(skip), pin=_list(pin)))


def clear_overrides():
    save_overrides(None)


# ---------------------------------------------------------------- verdicts
#
# The household's opinion of a dish, kept on the recipe itself so the library stays the
# product. `rating:` 1-5 is what the picker reads; `feedback:` is the why, kept for later.
# A dish rated at or below RETIRE_AT_OR_BELOW is never planned again until re-rated.

RETIRE_AT_OR_BELOW = 2


def is_retired(recipe):
    r = recipe.get("rating")
    return isinstance(r, (int, float)) and not isinstance(r, bool) and r <= RETIRE_AT_OR_BELOW


def set_frontmatter_key(path, key, value_lines):
    """
    Replace (or add) one top-level key in a file's frontmatter, leaving every other line
    exactly as it was. `value_lines` is the already-rendered YAML for the key, e.g.
    ["rating: 4"] or ["feedback:", "  - date: 2026-09-05", "    note: great"].
    Dumping the whole block through PyYAML would reflow every ingredient list in the
    library; this touches one key.
    """
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", raw, re.S)
    if not m:
        raise ValueError(f"{path}: no YAML frontmatter block")
    lines = m.group(1).split("\n")
    out, i, placed = [], 0, False
    while i < len(lines):
        ln = lines[i]
        if re.match(rf"^{re.escape(key)}:", ln):
            i += 1
            while i < len(lines) and (lines[i].startswith((" ", "-")) or lines[i] == ""):
                # a block value continues while indented; stop at the next top-level key
                if lines[i] == "" and i + 1 < len(lines) and not lines[i + 1].startswith((" ", "-")):
                    break
                i += 1
            out.extend(value_lines)
            placed = True
            continue
        out.append(ln)
        i += 1
    if not placed:
        out.extend(value_lines)
    body = m.group(2)
    open(path, "w", encoding="utf-8").write("---\n" + "\n".join(out) + "\n---\n" + body)


def record_verdict(path, rating=None, note=None, who=None, on=None):
    """
    Write a household verdict onto a recipe: `rating:` (1-5, or leave as is) and one
    appended `feedback:` entry. Returns the parsed recipe afterwards.
    """
    if rating is not None and not (isinstance(rating, int) and 1 <= rating <= 5):
        raise ValueError(f"rating must be a whole number 1-5, got {rating!r}")
    if rating is None and not note:
        raise ValueError("a verdict needs a rating, a note, or both")
    rec = parse_frontmatter(path)
    on = on or date.today()
    if rating is not None:
        set_frontmatter_key(path, "rating", [f"rating: {rating}"])
    entries = list(rec.get("feedback") or [])
    entry = {"date": on.isoformat()}
    if rating is not None:
        entry["rating"] = rating
    if who:
        entry["who"] = str(who)
    if note:
        entry["note"] = str(note)
    entries.append(entry)
    lines = ["feedback:"]
    for e in entries:
        first = True
        for k in ("date", "rating", "who", "note"):
            if k not in e:
                continue
            v = e[k]
            v = str(v) if k != "note" else json.dumps(str(v), ensure_ascii=False)
            lines.append(("  - " if first else "    ") + f"{k}: {v}")
            first = False
    set_frontmatter_key(path, "feedback", lines)
    return parse_frontmatter(path)
