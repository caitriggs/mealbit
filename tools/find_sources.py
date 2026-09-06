#!/usr/bin/env python3
"""
Find a real, published version of each dinner — for the photo and a second opinion.

    python tools/find_sources.py            # fill in anything missing
    python tools/find_sources.py --recheck  # re-verify links already on file

Every link is VERIFIED before it is written: the page must return 200, expose an
og:image, and that image must itself return 200. A dead or misattributed link is worse
than none — it wastes a scan in the kitchen and poisons trust in every other code on the
printed sheet. Nothing here is guessed from a search snippet.

Results are written into the recipe's frontmatter as source_url / source_name /
image_url, so they are reviewable in git like everything else in the library.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mealbit import library as L  # noqa: E402

# Sites that publish a real recipe with a real photo, expose a plain ?s= search, and
# don't hide behind a paywall or a JS-rendered results page. A general web search was the
# obvious approach and it does not work: DuckDuckGo rate-limits bulk queries within a
# handful of requests and returns an empty 202. Querying each site directly is both more
# reliable and easier to keep honest.
SITES = [
    "https://smittenkitchen.com/?s=",
    "https://www.budgetbytes.com/?s=",
    "https://www.themediterraneandish.com/?s=",
    "https://cookieandkate.com/?s=",
    "https://www.loveandlemons.com/?s=",
    "https://www.gimmesomeoven.com/?s=",
    "https://www.recipetineats.com/?s=",
    "https://thewoksoflife.com/?s=",
    "https://www.halfbakedharvest.com/?s=",
    "https://www.seriouseats.com/?s=",
    # Second wave, added when 24 of 45 recipes still had no verifiable source. Each was
    # checked for a reachable plain ?s= endpoint from this environment first — food52
    # (429), simplyrecipes (402), thekitchn (403), saveur (403) and 101cookbooks (403)
    # all refuse it and are deliberately absent. Widening the SITE list is the safe way to
    # raise the hit rate; loosening `relevant()` is not, and was tried twice.
    "https://www.epicurious.com/search/?q=",
    "https://pinchofyum.com/?s=",
    "https://minimalistbaker.com/?s=",
    "https://www.feastingathome.com/?s=",
    "https://alexandracooks.com/?s=",
    "https://www.onceuponachef.com/?s=",
    "https://rainbowplantlife.com/?s=",
    "https://www.davidlebovitz.com/?s=",
    "https://www.skinnytaste.com/?s=",
    "https://www.wellplated.com/?s=",
    "https://themodernproper.com/?s=",
]

# Words that carry no identity — a slug matching only these tells us nothing.
# Words that carry no identity. Two groups, both fatal if treated as identifying:
#   - grammar and cooking-method words, which appear in half the library
#   - COLOURS. "Turkey and white bean green chile chili" matched "turkey in white wine
#     sauce" on turkey+white, and "green chile chicken salad" matched green chile chicken
#     ENCHILADAS. A colour is an adjective on the real noun, never the noun.
STOP = {"with", "and", "the", "a", "of", "in", "over", "torn", "fresh", "quick", "easy",
        "best", "simple", "recipe", "recipes", "homemade", "style", "my", "our", "for",
        "charred", "crispy", "roasted", "seared", "grilled", "blistered", "smashed",
        "good", "actual", "real", "sunday", "oven", "fried", "spiced", "marinated",
        "green", "red", "white", "black", "yellow", "brown", "golden",
        "glazed", "braised", "baked", "grilled", "whole", "little", "big", "slow"}
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'


def sh(cmd, timeout=30):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=timeout).stdout
    except Exception:
        return ""


def _title_freq():
    """
    How many recipes in this library use each title word.

    A crude but honest measure of how much a word identifies a dish. "shakshuka" appears
    in one title; "chicken" appears in a dozen. That difference is the whole reason
    "Mongolian beef" must not match on "beef" alone while "green shakshuka" safely can.
    """
    global _FREQ
    if _FREQ is None:
        _FREQ = {}
        for r in L.load_dinners() + L.load_lunches():
            for w in set(re.findall(r"[a-z]+", L.normalize(r["title"]))):
                _FREQ[w] = _FREQ.get(w, 0) + 1
    return _FREQ


_FREQ = None


def keywords(title):
    """
    The words that identify the dish, most-identifying FIRST.

    The old version cut the title at the first "with" or comma, on the theory that what
    follows is garnish. For a title like "Charred eggplant and chickpea curry with
    coconut" that is right. For "Turkey, provolone and giardiniera sub" it left exactly
    ["turkey"], and for "Green shakshuka with asparagus, peas and feta" exactly
    ["shakshuka"] — and since `relevant` needs two terms, those recipes could never match
    anything, ever. Six of the twenty-four photo-less recipes were failing for that reason
    alone rather than for want of a good candidate.

    So: keep the whole title, drop the stop words, and ORDER by how much each word
    identifies the dish. Ordering is what makes requiring "the first two" meaningful —
    "shakshuka, asparagus" is a real fingerprint, "asparagus, peas" is not.
    """
    words, seen = [], set()
    for w in re.findall(r"[a-z]+", L.normalize(title).replace("-", " ")):
        if w in STOP or len(w) <= 2 or w in seen:
            continue
        seen.add(w)
        words.append(w)
    # Rarest first, longer wins a tie: rarity is identity, and a long word is usually the
    # dish rather than an ingredient.
    return sorted(words, key=lambda w: (_title_freq().get(w, 0), -len(w)))


def search(terms):
    """Ask each trusted site's own search, collect candidate post URLs."""
    q = urllib.parse.quote(" ".join(terms))
    out = []
    for base in SITES:
        page = sh(f'curl -sSL --max-time 18 -A "{UA}" "{base}{q}"', timeout=22)
        host = urllib.parse.urlparse(base).netloc
        for u in re.findall(rf'href="(https://{re.escape(host)}/[^"?#]+)"', page):
            if u.rstrip("/").count("/") < 3 or u.endswith((".jpg", ".png", ".css", ".js")):
                continue
            # WordPress plumbing. Every search page links to its own feeds, xmlrpc and
            # REST endpoints, and they were about 95% of what came back — a thousand
            # candidates a query, none of them a recipe.
            if _PLUMBING.search(u):
                continue
            if u not in out:
                out.append(u)
    return out


# Section and index pages, not recipes. "gimmesomeoven.com/proteins/beef-recipes/" is a
# category listing; linking it from a printed card is a dead end for the cook.
_PLUMBING = re.compile(
    r"/(xmlrpc\.php|wp-json|wp-admin|wp-content|wp-includes|feed|rss2?|atom|comments|"
    r"author|privacy|terms|about|contact|shop|cart|account|login|subscribe)(/|$)", re.I)

INDEX_PATHS = re.compile(
    r"/(recipes?|proteins?|categor(y|ies)|tag|topics?|course|cuisine|collections?|"
    r"dinner|lunch|breakfast|desserts?|search|page)(/|$)", re.I)


# What KIND of thing the recipe is. A slug and a title can share every ingredient word and
# still be different dinners — the ingredients are the same because it is the same
# cuisine. The dish noun is the part that says whether you end up with a chili or a sauce.
# Dish nouns come in two kinds, and conflating them is what made this rule wrong a fifth
# time. A FORM is the vessel or format a thing is served in — a wrap, a bowl, a soup, a
# traybake. A NAME is the dish's own identity — katsu, shawarma, carbonara, hummus, slaw.
#
# The distinction matters because a title carries both and they behave differently.
# "Harissa hummus wrap" is a WRAP whose filling is NAMED hummus, and "carrot hummus" is a
# dip. Matching on the shared name accepted it. "Chicken katsu" against
# "chicken-katsu-curry-rice" is the same dish with sides, and matching on the last noun
# rejected it. So: forms must AGREE, names must be PRESENT.
FORMS = {
    "soup", "stew", "chili", "salad", "bowl", "bowls", "jar", "jars", "plate",
    "sandwich", "sando", "sub", "melt", "toast", "burger", "burgers", "wrap", "wraps",
    "taco", "tacos", "burrito", "burritos", "quesadilla", "taquitos", "enchiladas",
    "pizza", "pie", "cake", "casserole", "bake", "gratin", "traybake", "sheetpan",
    "skillet", "noodles", "noodle", "pasta", "soba", "ramen", "risoni", "fries",
    "nachos", "rolls", "buns", "pockets", "dip", "sauce", "dressing", "marinade",
    "porridge", "smash", "crumble", "cobbler", "fritters", "dumplings", "meatballs",
}

# Forms that mean the same thing on a plate. A "farro bowl" and a "farro salad" are the
# same lunch; "tuna jars" and a "tuna salad" are the same lunch in different tupperware;
# a "traybake" and a "sheet pan dinner" are the same Tuesday. What must still conflict is
# soup/bowl, burrito/burger, wrap/dip — different lunches entirely.
SAME_FORM = [
    {"salad", "bowl", "jar", "plate"},
    # Noodles are their OWN class, not a kind of bowl. Grouping them re-admitted
    # "Miso-marinated tofu and soba" -> "honey-miso-carrot-tofu-bowl".
    {"noodle", "soba", "pasta", "ramen", "risoni"},
    {"enchilada", "casserole", "bake", "gratin"},
    {"sandwich", "sando", "sub", "melt", "toast"},
    {"chili", "stew", "soup"},
    {"traybake", "sheetpan", "skillet"},
    {"taco", "burrito", "quesadilla", "taquito"},
    {"wrap", "roll", "pocket"},
]

# The dish's own identity, independent of what it is served in.
NAMES = {
    "carbonara", "risotto", "shakshuka", "frittata", "omelette", "scramble", "hash",
    "katsu", "adobo", "shawarma", "larb", "curry", "dal", "ragu", "ragù", "hummus",
    "salsa", "slaw", "chowder", "pilaf", "paella", "biryani", "congee", "tamale",
    "tamales", "grits", "panzanella", "shepherds", "meatloaf", "tonkatsu",
}

DISH_NOUNS = FORMS | NAMES


def _class(w, groups):
    """Fold a noun to its synonym class so equivalents compare equal."""
    w = w.rstrip("s")
    for g in groups:
        if w in g:
            return min(g)
    return w


def _head(words):
    """Everything before "with" — what follows is garnish, not identity."""
    # "sheet pan dinner" is a traybake written as three words. Joining it here is the
    # difference between keeping and losing the shawarma traybake's real source.
    words = list(words)
    for i in range(len(words) - 1):
        if words[i] == "sheet" and words[i + 1] == "pan":
            words[i:i + 2] = ["sheetpan"]
            break
    out = []
    for w in words:
        if w in ("with", "topped", "served", "over"):
            break
        out.append(w)
    return out or list(words)


def form_of(words):
    """
    The LAST form among these words, folded to its class.

    Last, not first: English food titles put the filling before the container — "hummus
    wrap", "slaw wrap", "noodle salad". The first form noun is what is IN the dish; the
    last one is what the dish IS.
    """
    for w in reversed(_head(words)):
        if w in FORMS:
            return _class(w, SAME_FORM)
    return None


def names_in(words):
    """Every dish name present, folded — order does not matter for these."""
    return {_class(w, []) for w in _head(words) if w in NAMES}


def title_words(title):
    """The title's own words, in the order written — form_of depends on the order."""
    return re.findall(r"[a-z]+", L.normalize(title).replace("-", " "))


def relevant(url, terms, title=None):
    """
    The slug must carry the dish's WHOLE identity, not one word of it.

    Site search is loose, and a permissive check here is actively dangerous. Three passes
    have now been wrong in three different ways:

      1. len(terms)-1 matches -> "Mongolian beef" got a beef-recipes CATEGORY page and
         "turkey taquitos" got Italian breakfast roll-ups.
      2. splitting the title on "and" -> "Seared beef and cabbage" collapsed to ["beef"].
      3. requiring the top TWO words, with colours counted as words -> "Turkey and white
         bean green chile chili" matched "turkey in white wine sauce", and 8 others like
         it in a batch of 12.

    So: colours are stop-words, the top THREE identifying words must all appear, and index
    pages are rejected outright. A confidently wrong link is worse than no link at all —
    it wastes a scan mid-cook and discredits every other code on the sheet.
    """
    path = urllib.parse.urlparse(url).path.lower()
    if INDEX_PATHS.search(path):
        return False
    slug = path.rstrip("/").rsplit("/", 1)[-1]
    # "sweet-potato-recipes" is a roundup, not a dish. The path check above only catches
    # /recipes/ as its own segment, so catch the suffix form here too.
    if re.search(r"-(recipes|ideas|roundup|guide|menus?)$", slug):
        return False
    if len(slug) < 6 or not terms:
        return False

    # Match WORDS in the slug, not substrings of it. Raw substring matching let
    # "miso-butter squash" match "butternut-squash-miso-..." — "butter" is inside
    # "butternut" — which is a different dish with a very similar shopping list.
    words = [w for w in re.split(r"[-_]+", slug) if w]

    def has(t):
        t = t.rstrip("s")
        return any(w.rstrip("s") == t for w in words)

    # THREE identifying words, not two. Two was measured against a batch of 12 and got 9
    # of them wrong: "zucchini and corn carbonara" -> a ground turkey skillet with zucchini
    # and corn; "chipotle black bean burrito bowls" -> spicy black bean burgers with
    # chipotle; "miso-marinated tofu and soba" -> a honey miso carrot tofu bowl. In every
    # case the third word was the dish itself — carbonara, burrito, soba — and every one of
    # those matches dies the moment it is required.
    #
    # This does lose real matches: "charred sweet potato and black bean tacos" no longer
    # finds a sweet-potato taco post, because that post says nothing about beans. That is
    # the correct trade. A card with no QR is a card with no QR; a card with a QR that goes
    # to the wrong dinner is worse than that, and it discredits the other three on the
    # sheet.
    # Two identifying words, PLUS a check that the page isn't a different dish.
    #
    # Requiring three words alone was too blunt in the other direction: it threw away
    # "Green shakshuka with asparagus and peas" -> green-shakshuka-recipe, which is
    # exactly right, because the post doesn't name the vegetables in its slug. What every
    # bad match had in common was not a missing word — it was naming a DIFFERENT DISH.
    # chili matched a sauce, carbonara matched a skillet, burrito bowls matched burgers,
    # a chicken salad matched enchiladas, smash toast matched hummus. So compare the dish
    # nouns directly and reject a disagreement outright.
    # `terms` is ordered by RARITY, which destroys the title order form_of needs, so our
    # own dish is read off the title when the caller passes one.
    ours = title_words(title) if title else terms
    my_form, their_form = form_of(ours), form_of(words)
    my_names, their_names = names_in(ours), names_in(words)

    # A form we declare must be a form they declare: "Harissa hummus WRAP" against
    # "carrot-hummus" shares the name, and the target is a dip in a bowl.
    if my_form and my_form != their_form:
        return False
    # The reverse does NOT hold in general, and requiring it was measured and rejected:
    # publishers add form words we didn't write, and all four of "brothy beans on garlic
    # TOAST", "SKILLET chicken thighs", "tomato panzanella SALAD" and "SHEET PAN teriyaki
    # salmon" are correct links to recipes whose titles here name no form at all.
    #
    # It holds for one class. A soup, stew or chili is not a qualifier, it is a different
    # dish: liquid, eaten with a spoon, and — since the photo is the entire point of the
    # link — it photographs as a bowl of broth. "Roasted squash, kale and wild rice"
    # matched a chicken shiitake and wild rice SOUP on three shared ingredients.
    if their_form in ("chili",) and my_form != their_form:      # the soup/stew/chili class
        # If THIS recipe names what it is, the target has to name the same thing. Letting
        # a missing dish noun pass was still admitting the whole original failure class:
        # "zucchini and corn carbonara" matched sheet-pan chicken drumsticks with zucchini
        # and corn, "chipotle black bean burrito bowls" matched Mexican chipotle pork and
        # beans, "green chile chicken salad" matched green chile chicken TAMALES. Every
        # one shares two ingredient words with the dish and is not the dish.
        return False
    # And a name we declare must be a name they declare. This is the older half of the
    # rule and it stays: "zucchini and corn carbonara" matched sheet-pan chicken
    # drumsticks with zucchini and corn, "green chile chicken salad" matched green chile
    # chicken TAMALES. Each shares two ingredient words with the dish and is not the dish.
    if my_names and not (my_names & their_names):
        return False
    # ANY TWO of the title's identifying words.
    #
    # Not one, however distinctive it looks: rarity measured against a 45-recipe library
    # calls "shakshuka", "carbonara", "risotto" and "saffron" unique, and on the open web
    # they are anything but. Allowing a solo match on those matched a TOMATO shakshuka, a
    # TOMATO carbonara, a TOMATO risotto and a bowl of mussels — 8 wrong out of 10, each
    # one the right technique applied to the wrong dish.
    #
    # Nor "terms[0] plus any other": that treats the rarity ordering as exact, and the
    # rarest word in a title is often the one a publisher leaves out of the URL. It threw
    # away ten links that were correct — steak-chimichurri, short-rib-ragu, chicken
    # shawarma — because their headline word ranked second.
    #
    # Two independent words, wherever they land, plus the dish-noun and index checks
    # above. What no slug rule can see is a photo of the right dish made with the wrong
    # main ingredient; those go in data/rejected-sources.md by hand.
    if sum(1 for t in terms if has(t)) < 2:
        return False
    # And one of them has to come from the title's HEAD — the words before the first
    # "with", "over" or "on". That is the dish; what follows is what it sits on or under.
    # "BBQ pulled pork over cheesy grits with chard and pickled Fresnos" matched PICKLED
    # CHARD stems, a condiment: its two rarest words were both garnish, and the slug
    # carried both. The sixth wrong match, and the first where every earlier rule held.
    if title:
        head = []
        for w in title_words(title):
            if w in ("with", "over", "on", "topped", "atop"):
                break
            head.append(w)
        head = [w for w in head if w not in STOP and len(w) > 2]
        if head and not any(has(w) for w in head):
            return False
    return True


def rejected():
    """
    URLs a human looked at and said no to, from data/rejected-sources.md.

    Some wrong matches are invisible to any rule that reads a URL. "Zucchini and corn
    carbonara" against a garlic-herb-roasted-CHERRY-TOMATO carbonara shares two real
    words and the same dish noun; the only thing that knows it is wrong is a person
    looking at the photo. Rather than contort the matcher until it happens to exclude
    each one — which is how the last three versions of this rule got worse — the
    judgement is written down and kept.

    A rejection is PER RECIPE, not global, and conflating the two broke a good link: the
    same feastingathome brothy-beans-on-garlic-toast page is wrong for `white-bean-smash-
    toast` (ours are smashed, and the dinner already has it) and exactly right for
    `brothy-white-beans-kale`. So each entry names the slug it was rejected for, in the
    "— for `slug`" that every entry already carried as prose. An entry that names no slug
    is rejected everywhere, which is the older and still useful shape.

    Returns {url: {slugs}}, where an empty set means "wrong for everything".
    """
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "rejected-sources.md")
    if not os.path.exists(path):
        return {}
    txt = open(path, encoding="utf-8").read()
    out = {}
    for m in re.finditer(r"^\s*-\s*<(https?://[^>]+)>(.*?)(?=^\s*-\s*<|\Z)", txt,
                         re.M | re.S):
        url, body = m.group(1), m.group(2)
        out.setdefault(url, set()).update(re.findall(r"for `([a-z0-9-]+)`", body))
    return out


def rejected_for(slug):
    """The URLs ruled out for this particular recipe, plus those ruled out everywhere."""
    return {u for u, slugs in rejected().items() if not slugs or slug in slugs}


def _meta(html, prop):
    m = (re.search(rf'<meta[^>]+property=["\']{prop}["\'][^>]+content=["\']([^"\']+)', html)
         or re.search(rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{prop}["\']', html))
    return m.group(1) if m else None


def status(url):
    return sh(f'curl -sSL -o /dev/null -w "%{{http_code}}" --max-time 20 -A "{UA}" "{url}"').strip()[-3:]


def probe(url):
    """Live page + a real, loading photo, or nothing."""
    if status(url) != "200":
        return None
    html = sh(f'curl -sSL --max-time 25 -A "{UA}" "{url}"')
    img = _meta(html, "og:image")
    if not img or status(img) != "200":
        return None
    return {"source_url": url,
            "image_url": img,
            "source_name": urllib.parse.urlparse(url).netloc.replace("www.", "")}





def write_back(path, found):
    txt = open(path, encoding="utf-8").read()
    for key in ("source_url", "source_name", "image_url"):
        txt = re.sub(rf"^{key}:.*\n", "", txt, flags=re.M)
    block = "".join(f"{k}: {v}\n" for k, v in found.items())
    txt = re.sub(r"^(rating:)", block + r"\1", txt, count=1, flags=re.M)
    open(path, "w", encoding="utf-8").write(txt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recheck", action="store_true", help="re-verify links already on file")
    ap.add_argument("--only", help="substring match on slug")
    a = ap.parse_args()

    ok = miss = kept = 0
    for r in L.load_dinners() + L.load_lunches():
        if a.only and a.only not in r["slug"]:
            continue
        if r.get("source_url") and not a.recheck:
            kept += 1
            continue
        if r.get("source_url") and a.recheck:
            got = probe(r["source_url"])
            print(f"{'OK   ' if got else 'DEAD '} {r['slug']}")
            if got:
                write_back(r["path"], got)
                ok += 1
            continue
        terms = keywords(r["title"])
        found = None
        # A source already used by another recipe is not a source for this one. The two
        # cards would carry the same photo and the same QR, which reads as a bug even
        # when both links are individually defensible: "White bean smash toast" was
        # handed brothy-beans-on-garlic-toast, which is already — and exactly — the
        # brothy-white-beans-kale dinner.
        no = rejected_for(r["slug"]) | {x.get("source_url") for x in L.load_dinners() + L.load_lunches()
                           if x.get("source_url") and x["slug"] != r["slug"]}
        for cand in search(terms):
            if cand in no or not relevant(cand, terms, r["title"]):
                continue
            found = probe(cand)
            if found:
                break
        if found:
            write_back(r["path"], found)
            print(f"OK    {r['slug']:44} {found['source_name']}")
            ok += 1
        else:
            print(f"MISS  {r['slug']:44} (no verifiable source)")
            miss += 1
    print(f"\nverified {ok}, no source {miss}, already had one {kept}")


if __name__ == "__main__":
    main()
