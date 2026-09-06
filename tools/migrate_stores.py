#!/usr/bin/env python3
"""
One-time migration: store-filed ingredients -> kind-tagged ingredients.

    python tools/migrate_stores.py            # dry run: print the classification
    python tools/migrate_stores.py --write    # rewrite every recipe

Before, every recipe filed each ingredient under one of three fixed shops:

    market_items: [1 bunch cilantro]
    tj_items:     [1 lb chicken thighs]
    qfc_items:    [2 limes]

which meant adding a shop, dropping one, or shopping a different market was a change to
358 lines across 46 files. After, a recipe says what an ingredient IS and the household's
config/stores.yml says who sells it:

    ingredients:
      - 1 bunch cilantro [produce]
      - 1 lb chicken thighs [protein]
      - 2 limes [produce]

The market bucket was 100% produce, so that side is mechanical. The other two are
classified by the keyword table below, then a human reads the dry run. Anything the table
cannot place is tagged `pantry` and listed so it can be looked at — pantry is the safe
default because every supermarket has a pantry aisle.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mealbit import library as L  # noqa: E402

# Order matters: first match wins, so the more specific lists come first.
RULES = [
    ("wine", r"\b(wine|hard cider|shaoxing|sherry|mirin|sake|vermouth)\b"),
    ("bakery", r"\b(bread|sourdough|ciabatta|baguette|tortillas?|pita|naan|flatbread|"
               r"buns?|rolls?|milk bread)\b"),
    ("dairy", r"\b(parmigiano|parmesan|pecorino|feta|cotija|cheddar|jack|mozzarella|"
              r"queso|provolone|cottage cheese|butter|cream|crema|yogurt|ricotta|"
              r"halloumi|paneer|gruy[eè]re|goat cheese|burrata|mascarpone)\b"),
    ("protein", r"\b(chicken|thighs?|breasts?|drumsticks?|beef|steak|short ribs?|pork|"
                r"chops?|shoulder|chorizo|sausage|pancetta|guanciale|bacon|turkey|"
                r"salmon|cod|rockfish|halibut|fish fillet|fillets?|shrimp|prawns?|tofu|"
                r"eggs?|tuna|ground|pulled pork|lamb)\b"),
    ("specialty", r"\b(chili crisp|chili onion crunch|crunchy chili oil|preserved lemon|"
                  r"tonkatsu|saffron|harissa|gochujang|miso|tahini|hoisin|fish sauce|"
                  r"salsa macha|ancho|guajillo|arbol|chipotles? in adobo|dried chipotle|"
                  r"everything bagel|giardiniera|za'?atar|sumac|pomegranate molasses|"
                  r"furikake|kimchi|curry paste|lemongrass|kaffir|galangal|culinary lavender|"
                  r"cardamom pods|urfa|aleppo|sambal|chili garlic sauce|oyster sauce|"
                  r"black bean sauce|doubanjiang|tamarind|dukkah|orzo)\b"),
    ("produce", r"\b(lemons?|limes?|oranges?|avocados?|ginger|onions?|shallots?|garlic|"
                r"tomato(es)?|spinach|carrots?|fennel|fresno|jalape[nñ]os?|scallions?|"
                r"cilantro|parsley|basil|mint|dill|thyme|rosemary|sage|chiles?|peppers?|"
                r"cucumbers?|cabbage|kale|potato(es)?|apples?|peach(es)?|berries|"
                r"mushrooms?|celery|leeks?|corn|zucchini|squash|eggplant|broccoli|"
                r"cauliflower|beans?(?! *,)|peas|lettuce|romaine|arugula|radish|"
                r"rhubarb|asparagus|herbs?)\b"),
]
# Words that would otherwise trip the produce rule from inside a pantry item.
PANTRY_OVERRIDES = re.compile(
    r"\b(canned|can|cans|dried|frozen|jar|jarred|powder|paste|stock|broth|flakes?|"
    r"seeds?|oil|vinegar|sauce|pickled|roasted red|sun-dried|black beans?|cannellini|"
    r"chickpeas?|white beans?|kidney beans?|refried|lentils?|coconut milk|corn tortilla|"
    r"frozen corn|whole peeled)\b", re.I)
# ...except these, which the override should not rescue into pantry.
PANTRY_OVERRIDE_EXCEPT = re.compile(r"\b(pickled jalape|salsa verde|salsa)\b", re.I)


def classify(line, source_field):
    if source_field == "market_items":
        return "produce"
    import unicodedata
    text = str(line).split("||")[0].lower()
    text = "".join(c for c in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(c))          # árbol -> arbol
    # A few things the general rules get wrong, settled first.
    if re.search(r"\b(grits|polenta|cornmeal)\b", text):
        return "pantry"                     # "stone-GROUND grits" is not a protein
    if re.search(r"\btuna\b", text):
        return "protein"                    # jarred or tinned, it is the dish's protein
    if PANTRY_OVERRIDES.search(text) and not PANTRY_OVERRIDE_EXCEPT.search(text):
        # A canned/dried/jarred thing is pantry even if it names a vegetable — but a
        # dried CHILE is specialty, and pickled jalapeños are a jar of pantry too.
        for kind, rx in RULES:
            if kind in ("specialty", "wine") and re.search(rx, text):
                return kind
        return "pantry"
    for kind, rx in RULES:
        if re.search(rx, text):
            return kind
    return "pantry"


def convert(recipe_path):
    txt = open(recipe_path, encoding="utf-8").read()
    fm_end = txt.index("\n---", 4)
    fm, body = txt[:fm_end], txt[fm_end:]
    out_lines, tagged, unplaced = [], [], []
    field = None
    for ln in fm.split("\n"):
        m = re.match(r"^(market_items|tj_items|qfc_items):\s*(\[\s*\])?\s*$", ln)
        if m:
            field = m.group(1)
            continue
        if field and re.match(r"^\s+-\s+", ln):
            item = re.sub(r"^\s+-\s+", "", ln).strip()
            kind = classify(item, field)
            tagged.append(f"  - {item} [{kind}]")
            if kind == "pantry" and field != "market_items" and not re.search(
                    r"\b(rice|beans?|pasta|noodle|oil|vinegar|sugar|flour|stock|broth|"
                    r"canned|can|jar|dried|frozen|nuts?|peanuts?|almonds?|seeds?|sauce|"
                    r"salsa|couscous|farro|grits|lentils?|chickpeas?|coconut|tortilla|"
                    r"panko|honey|maple|syrup|spice|paprika|cumin|oregano|cinnamon|"
                    r"crackers?|pickled|mustard|mayo|ketchup|capers|olives?|anchov|"
                    r"tomato paste|bucatini|spaghetti|orecchiette|pappardelle|soba|"
                    r"wheat noodle|basmati|jasmine|arborio|carnaroli|pearl|polenta|"
                    r"cornmeal|oats?|granola|breadcrumbs?|cornstarch|gelatin|chocolate|"
                    r"cocoa|espresso|coffee|tea|vanilla|extract|salt|pepper|condensed|"
                    r"evaporated|peanut butter|tahini|jam|preserve)\b", item.lower()):
                unplaced.append(item)
            continue
        field = None
        out_lines.append(ln)
    # Insert the new block where the old ones were: right before `pantry:` if present,
    # else before `rating:`.
    block = "ingredients:\n" + "\n".join(tagged) + "\n"
    new_fm = "\n".join(out_lines)
    for anchor in ("\npantry:", "\nsource_url:", "\nimage_url:", "\nphoto_url:",
                   "\nphoto_pending:", "\nrating:"):
        i = new_fm.find(anchor)
        if i >= 0:
            new_fm = new_fm[:i + 1] + block + new_fm[i + 1:]
            break
    else:
        new_fm = new_fm.rstrip("\n") + "\n" + block
    return new_fm + body, tagged, unplaced


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    from collections import Counter
    counts, review = Counter(), []
    for r in L.load_dinners() + L.load_lunches():
        if "ingredients" in r and not any(r.get(f) for f in
                                          ("market_items", "tj_items", "qfc_items")):
            continue
        new, tagged, unplaced = convert(r["path"])
        for t in tagged:
            counts[t.rsplit("[", 1)[1].rstrip("]")] += 1
        review += [(r["slug"], u) for u in unplaced]
        if a.write:
            open(r["path"], "w", encoding="utf-8").write(new)
    print("kinds:", dict(counts.most_common()))
    if review:
        print(f"\n{len(review)} tagged `pantry` by default — worth a look:")
        for slug, u in review:
            print(f"  {slug:40} {u}")
    print("\n" + ("WRITTEN." if a.write else "dry run — pass --write to apply."))


if __name__ == "__main__":
    main()
