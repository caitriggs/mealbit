"""
The two files that make this someone's newsletter rather than a library of recipes.

    config/household.yml   who eats, what they won't eat, where it's sent, what's on the
                           coffee counter
    config/stores.yml      where they shop, in visit order, and what each shop is for

Everything in mealbit/ reads through here. Nothing in the package should carry a name, an
email address or a shop name of its own — if it does, a fork has to edit code, and a fork
that edits code can't take upstream fixes.

Both loaders fail loudly and early if a file is missing or malformed. A send with a
half-read config is a send to the wrong address.
"""
import os

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONFIG = os.path.join(ROOT, "config")

# What a recipe may tag an ingredient with. Mirrors the comment in stores.yml.
KINDS = ("produce", "protein", "dairy", "bakery", "pantry", "specialty", "wine")
EVERYTHING = "everything"

# What lunch means for this household:
#   leftovers  dinners are cooked to serve 4 and two portions become tomorrow's lunches;
#              the rest of the week's lunch slots come from two Sunday batches and
#              five-minute builds. The original design.
#   fresh      dinners are cooked for the people at the table only; every lunch comes from
#              the Sunday batches and the five-minute builds.
#   none       no lunch planning at all. Dinners only, cooked for the table.
LUNCH_MODES = ("leftovers", "fresh", "none")


class ConfigError(SystemExit):
    pass


def _read(name):
    path = os.path.join(CONFIG, name)
    if not os.path.exists(path):
        raise ConfigError(f"{path} is missing. Copy the one from the template and edit it "
                          f"— see SETUP.md.")
    try:
        data = yaml.safe_load(open(path, encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"{path} is not valid YAML: {e}")
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping at the top level")
    return data


def household():
    """
    config/household.yml as a FLAT dict, because that is the shape the planner has always
    consumed: cfg["eaters"], cfg["gear"], cfg["exclude_ingredients"], cfg["per_plate"]...

    The file is nested for people; the code is flat for history. Keys from later sections
    never shadow earlier ones — a collision here is a bug in the template, so it raises.
    """
    raw = _read("household.yml")
    flat = {}
    for section in ("household", "send", "diet", "coffee", "meals"):
        block = raw.get(section) or {}
        if not isinstance(block, dict):
            raise ConfigError(f"household.yml: `{section}:` must be a mapping")
        for k, v in block.items():
            if k in flat and section != "send":
                raise ConfigError(f"household.yml: `{k}` appears in two sections")
            # The send block's keys are generic ("to", "from"); prefix them.
            flat[f"send_{k}" if section == "send" else k] = v
    # The three addresses may come from the environment instead of the file, so a
    # household can keep this repository PUBLIC: the file carries placeholders, the real
    # addresses sit in repository secrets and reach the send step as env vars. An env
    # value always wins over the file, and the same validation applies to it.
    for var, key in (("MEALBIT_SEND_FROM", "send_from"), ("MEALBIT_SEND_TO", "send_to"),
                     ("MEALBIT_SEND_TEST_TO", "send_test_to")):
        v = os.environ.get(var, "").strip()
        if v:
            flat[key] = v
    eaters = flat.get("eaters") or []
    if not isinstance(eaters, list) or not all(isinstance(e, str) and e for e in eaters):
        raise ConfigError("household.yml: `household.eaters` must be a list of names")
    if not eaters:
        raise ConfigError("household.yml: `household.eaters` is empty")
    for k in ("send_from", "send_to", "send_test_to"):
        if not flat.get(k) or "@" not in str(flat[k]):
            raise ConfigError(f"household.yml: `send.{k[5:]}` must be an email address")
    if flat["send_to"] == flat["send_test_to"] and len(eaters) > 1:
        # A one-person household legitimately tests to itself. Otherwise a test that
        # reaches the real address is the one mistake this must never make.
        raise ConfigError("household.yml: `send.to` and `send.test_to` are the same "
                          "address, so --test would reach the whole household")
    flat.setdefault("gear", ["espresso", "moka", "aeropress", "french-press"])
    flat.setdefault("exclude_tags", [])
    flat.setdefault("exclude_ingredients", [])
    flat.setdefault("per_plate", {})
    flat.setdefault("drinks_per_week", 2)
    flat.setdefault("timezone", "America/Los_Angeles")
    flat.setdefault("send_subject", "Mealbit")
    # How many dinners, and what lunch is. Defaults reproduce the original household.
    n = flat.get("dinners_per_week", 4)
    if not isinstance(n, int) or not 2 <= n <= 5:
        raise ConfigError("household.yml: `meals.dinners_per_week` must be a whole number "
                          "from 2 to 5 (cooked Monday onward)")
    mode = flat.get("lunch_mode", "leftovers")
    if mode not in LUNCH_MODES:
        raise ConfigError(f"household.yml: `meals.lunch_mode` must be one of "
                          f"{list(LUNCH_MODES)}, got {mode!r}")
    flat["dinners_per_week"], flat["lunch_mode"] = n, mode
    for who in flat["per_plate"]:
        if who not in eaters:
            raise ConfigError(f"household.yml: per_plate names {who!r}, who is not in "
                              f"`eaters` {eaters}")
    return flat


def stores():
    """
    config/stores.yml as an ordered list of dicts, validated.

    Exactly one store declares `everything`; every `takes:` entry is a known kind; a
    farmers market names an availability model that exists. Returns the list in visit
    order, which is the order the shopping list prints.
    """
    raw = _read("stores.yml")
    out = raw.get("stores")
    if not isinstance(out, list) or not out:
        raise ConfigError("stores.yml: `stores:` must be a non-empty list")
    ids, catch_all = set(), []
    for s in out:
        if not isinstance(s, dict) or not s.get("id") or not s.get("name"):
            raise ConfigError(f"stores.yml: every store needs an `id` and a `name`: {s}")
        if s["id"] in ids:
            raise ConfigError(f"stores.yml: duplicate store id {s['id']!r}")
        ids.add(s["id"])
        takes = s.get("takes")
        if not isinstance(takes, list) or not takes:
            raise ConfigError(f"stores.yml: {s['id']}: `takes:` must be a non-empty list")
        for k in takes:
            if k != EVERYTHING and k not in KINDS:
                raise ConfigError(f"stores.yml: {s['id']}: unknown kind {k!r}; "
                                  f"choose from {list(KINDS)} or {EVERYTHING!r}")
        if EVERYTHING in takes:
            catch_all.append(s["id"])
        s.setdefault("short", s["id"].upper()[:3])
        s.setdefault("sub", "")
        if s.get("kind") == "farmers_market":
            for key in ("availability", "tips"):
                p = s.get(key)
                if not p or not os.path.exists(os.path.join(ROOT, p)):
                    raise ConfigError(f"stores.yml: {s['id']}: `{key}:` must point at a "
                                      f"file that exists, got {p!r}")
    if len(catch_all) != 1:
        raise ConfigError(f"stores.yml: exactly one store must take `everything` (the "
                          f"catch-all), found {len(catch_all)}: {catch_all}")
    return out


def market_store():
    """The farmers market, if this household shops one. None otherwise."""
    return next((s for s in stores() if s.get("kind") == "farmers_market"), None)


def takes(store, kind):
    return EVERYTHING in store["takes"] or kind in store["takes"]
