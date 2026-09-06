#!/usr/bin/env python3
"""
Seasonal library audit — the thing that keeps the library from going stale.

    python -m mealbit.audit              # report on the season now and the one coming
    python -m mealbit.audit --month 5    # report on a specific month
    python -m mealbit.audit --issue      # Markdown body for a GitHub issue

WHY THIS EXISTS

Selection is already seasonal: the pool of eligible recipes changes with the month, so
the newsletter naturally looks different in February than in August. That part is
automatic and needs no maintenance.

What is NOT automatic is DEPTH. A season bucket lasts about nine weeks. At four dinners a
week that is ~36 dinner slots, and each season currently holds 10-14 recipes — so from
about week four of every season the plan starts repeating itself, and the household
notices before the code does.

This module measures that, per season, and says exactly what to add. It never writes
recipes. The library is hand-written and reviewable on purpose (see CLAUDE.md); a
generated recipe nobody read is precisely the thing this project exists to replace.
"""
import argparse
import calendar
from collections import Counter
from datetime import date

from . import library as L
from . import planner as P

# ---- targets -----------------------------------------------------------------
# A season bucket spans two months, ~8.7 weeks. Holding 4 weeks of non-repeating
# rotation before a meal comes back is the comfortable floor; 5 is where it stops
# feeling like a rotation at all.
WEEKS_PER_SEASON = 8.7
TARGET_ROTATION_WEEKS = 4.0
STRETCH_ROTATION_WEEKS = 5.0
TARGET_DINNERS = int(TARGET_ROTATION_WEEKS * P.N_DINNERS)      # 16
STRETCH_DINNERS = int(STRETCH_ROTATION_WEEKS * P.N_DINNERS)    # 20

# Share of a season's dinners that must pack as a next-day lunch. Leftovers fill roughly
# half the lunch column and the rest is Sunday prep plus 5-minute assembly; below this the
# column starves and the week degrades into sandwiches. Not 100% — a dish being worth
# cooking even though it won't keep is a legitimate thing, it just can't be most of them.
MIN_PACKING_SHARE = 0.75

# Four distinct proteins are needed every week and the picker refuses to repeat one, so
# the pool needs real slack above four or the same four recur.
MIN_PROTEINS = 6
# Neither register may fall below this share: the brief asked for a blend, not a lean.
MIN_REGISTER_SHARE = 0.30
# The drink cooldown is 5 weeks, so a season wants at least that many drinks.
MIN_DRINKS = 6
MIN_LUNCHES_PER_STYLE = 5

# A recipe served this often with no rating is one nobody has an opinion on — either it's
# forgettable or the rating never got filled in. Both are worth surfacing.
UNRATED_AFTER = 3


def _season_of(month):
    return L.load_seasonal()[month]["season"]


def season_report(season, dinners=None, lunches=None, drinks=None, hist=None):
    """Everything measurable about one season bucket, plus the gaps to close."""
    dinners = dinners if dinners is not None else L.load_dinners()
    lunches = lunches if lunches is not None else L.load_lunches()
    drinks = drinks if drinks is not None else L.load_drinks()
    hist = hist if hist is not None else L.load_history()

    # Only what the planner can actually reach. Counting dietary-excluded recipes as
    # depth overstates every season they appear in and hides the real gap.
    cfg = L.load_household()
    pool = [r for r in dinners
            if season in (r.get("seasons") or []) and not P._excluded(r, cfg)]
    n = len(pool)
    proteins = Counter(r.get("protein") for r in pool)
    registers = Counter(r.get("register") for r in pool)
    efforts = Counter(r.get("effort") for r in pool)
    keeps = Counter(r.get("leftover_quality") for r in pool)
    lun = [r for r in lunches
           if season in (r.get("seasons") or []) and not P._excluded(r, cfg)]
    styles = Counter(r.get("lunch_style") for r in lun)
    dr = [d for d in drinks if season in (d.get("seasons") or [])]

    gaps = []
    if n < TARGET_DINNERS:
        gaps.append({
            "kind": "depth", "severity": "high" if n < TARGET_DINNERS - 4 else "medium",
            "need": TARGET_DINNERS - n,
            "text": (f"**{TARGET_DINNERS - n} more dinners.** {n} recipes is "
                     f"{n / P.N_DINNERS:.1f} weeks of rotation and the season runs "
                     f"~{WEEKS_PER_SEASON:.0f} weeks, so meals start coming back around "
                     f"week {n // P.N_DINNERS + 1}. Target {TARGET_DINNERS}, "
                     f"ideally {STRETCH_DINNERS}.")})
    if len(proteins) < MIN_PROTEINS:
        gaps.append({
            "kind": "protein", "severity": "high", "need": MIN_PROTEINS - len(proteins),
            "text": (f"**Only {len(proteins)} distinct proteins** ({', '.join(sorted(proteins))}). "
                     f"Four are used every week with no repeats allowed, so a pool this "
                     f"narrow forces the same four every time. Want {MIN_PROTEINS}+.")})

    # Protein preference: chicken should lead, turkey should not.
    pref = (L.load_household().get("protein_preference") or [])
    if pref and n:
        top = pref[0]
        share = proteins.get(top, 0) / n
        if share < 0.15:
            gaps.append({
                "kind": "preference", "severity": "medium",
                "need": max(1, round(0.20 * n) - proteins.get(top, 0)),
                "text": (f"**{top.title()} is under-represented** — {proteins.get(top, 0)} "
                         f"of {n} recipes ({share * 100:.0f}%). It is the household's "
                         f"first-choice protein; aim for ~20%.")})

    # Leftover depth, which is a different thing from recipe depth. Four dinners pay for
    # ten weekday lunch slots, and a dinner that doesn't pack contributes none of them —
    # so a season that fills up with same-night dishes quietly starves the lunch column
    # even while its recipe count looks healthy.
    packs = keeps.get("good", 0) + keeps.get("fair", 0)
    if n and packs / n < MIN_PACKING_SHARE:
        gaps.append({
            "kind": "leftovers", "severity": "high",
            "need": max(1, round(MIN_PACKING_SHARE * n) - packs),
            "text": (f"**Only {packs} of {n} dinners pack as a lunch** "
                     f"({packs / n * 100:.0f}%). Leftovers fill about half the lunch "
                     f"column, so new recipes for this season should lean to dishes that "
                     f"are as good or better the next day — braises, stews, curries, "
                     f"grain bowls, anything cold-or-room-temperature. Want "
                     f"{MIN_PACKING_SHARE * 100:.0f}%+.")})

    # Protein depth. Three of four dinners must be built on a protein (data/protein.md),
    # and the picker holds that rule almost to the last — so a season that thins out on
    # meat, fish and tofu does not produce a visible complaint, it produces a picker
    # reaching off cooldown week after week to find a third anchor.
    anchors, _light = L.load_protein()
    anchor_pool = [r for r in pool if r.get("protein") in anchors]
    kinds = {r.get("protein") for r in anchor_pool}
    want = P.MIN_PROTEIN_DINNERS + 2      # headroom, so cooldown has somewhere to go
    if len(anchor_pool) < want:
        gaps.append({
            "kind": "protein", "severity": "high" if len(kinds) <= P.MIN_PROTEIN_DINNERS
                                else "medium",
            "need": want - len(anchor_pool),
            "text": (f"**Only {len(anchor_pool)} of {n} dinners is built on a protein** "
                     f"across {len(kinds)} distinct one(s) ({', '.join(sorted(kinds))}). "
                     f"{P.MIN_PROTEIN_DINNERS} of the 4 nights need one and they cannot "
                     f"repeat a protein, so this season has almost no slack — add meat, "
                     f"fish or tofu dishes rather than another legume one.")})

    for reg in ("comfort", "elegant"):
        share = registers.get(reg, 0) / n if n else 0
        if share < MIN_REGISTER_SHARE:
            other = "elegant" if reg == "comfort" else "comfort"
            gaps.append({
                "kind": "register", "severity": "medium",
                "need": max(1, int(MIN_REGISTER_SHARE * n) - registers.get(reg, 0)),
                "text": (f"**Register is lopsided** — {registers.get(reg, 0)} {reg} vs "
                         f"{registers.get(other, 0)} {other} ({share * 100:.0f}% {reg}). "
                         f"The brief asked for a blend of both, not a lean toward either.")})

    if len(dr) < MIN_DRINKS:
        gaps.append({
            "kind": "coffee", "severity": "low", "need": MIN_DRINKS - len(dr),
            "text": (f"**{MIN_DRINKS - len(dr)} more coffee drinks** for this season — "
                     f"{len(dr)} against a {P.COOLDOWN['coffee']}-week cooldown means "
                     f"the ritual repeats before the season is out.")})

    for style, want in (("sunday-prep", MIN_LUNCHES_PER_STYLE),
                        ("assembly", MIN_LUNCHES_PER_STYLE)):
        if styles.get(style, 0) < want:
            gaps.append({
                "kind": "lunch", "severity": "low", "need": want - styles.get(style, 0),
                "text": f"**{want - styles.get(style, 0)} more `{style}` lunches** for this season."})

    return {
        "keeps": dict(keeps),
        "n_protein_dinners": len(anchor_pool),
        "protein_kinds": sorted(kinds),
        "packing_share": (keeps.get("good", 0) + keeps.get("fair", 0)) / n if n else 0,
        "season": season, "n_dinners": n,
        "rotation_weeks": n / P.N_DINNERS,
        "proteins": proteins, "registers": registers, "efforts": efforts,
        "n_lunches": len(lun), "lunch_styles": styles, "n_drinks": len(dr),
        "gaps": sorted(gaps, key=lambda g: {"high": 0, "medium": 1, "low": 2}[g["severity"]]),
    }


def orphan_syrups():
    """
    Syrups in the box that no drink points at.

    Since a drink's syrup is declared rather than chosen, a syrup nothing names is dead
    stock — it will never be made, never printed, never bought for. Not an error: a
    perfectly good syrup can sit there waiting for a drink to be written around it. But
    it should be visible rather than quietly inert.
    """
    used = {d.get("syrup") for d in L.load_drinks() if d.get("syrup")}
    return sorted({s["slug"] for s in L.load_syrups()} - used)


def missing_sources(dinners=None):
    """
    Recipes with no link to a real published version.

    For a recipe, a photo is worth a thousand words. The printed card shows
    a QR to the original so you can see what the dish is supposed to look like before you
    commit an evening to it. A card without one is missing the most useful thing on it.

    These URLs must be REAL and checked. A fabricated recipe link is worse than no link —
    it wastes a scan in the kitchen and destroys trust in every other link on the sheet.
    """
    dinners = dinners if dinners is not None else L.load_dinners()
    cfg = L.load_household()
    return [{"slug": r["slug"], "title": r["title"]}
            for r in dinners
            if not r.get("source_url") and not P._excluded(r, cfg)]


def stale_recipes(hist=None, dinners=None):
    """
    Recipes that have been served repeatedly and still carry `rating: null`.

    Nobody has said whether they liked these. Either they're forgettable, or the rating
    field never got filled in — and the rating field is the only signal the library has
    for what should come back. Both cases are worth a nudge.
    """
    hist = hist if hist is not None else L.load_history()
    dinners = dinners if dinners is not None else L.load_dinners()
    served = Counter(s for wk in hist.get("weeks", []) for s in wk.get("dinners", []))
    out = []
    for r in dinners:
        c = served.get(r["slug"], 0)
        if c >= UNRATED_AFTER and r.get("rating") in (None, ""):
            out.append({"slug": r["slug"], "title": r["title"], "times": c})
        elif isinstance(r.get("rating"), (int, float)) and r["rating"] <= 2:
            out.append({"slug": r["slug"], "title": r["title"], "times": c,
                        "rated": r["rating"]})
    return sorted(out, key=lambda x: -x["times"])


def upcoming(today=None):
    """This month's season and next month's, since next month is what needs stocking."""
    today = today or date.today()
    nxt = today.month % 12 + 1
    return _season_of(today.month), _season_of(nxt), nxt


def text_report(today=None):
    today = today or date.today()
    now_s, next_s, next_m = upcoming(today)
    lines = [f"Mealbit library audit — {today.isoformat()}", "=" * 62, ""]
    seen = []
    for label, s in (("current", now_s), (f"coming ({calendar.month_name[next_m]})", next_s)):
        if s in seen:
            lines.append(f"{calendar.month_name[next_m]} is still {s} — same pool.\n")
            continue
        seen.append(s)
        r = season_report(s)
        lines += [f"[{label}] {s}",
                  f"  dinners {r['n_dinners']:>3}   = {r['rotation_weeks']:.1f} weeks of rotation "
                  f"(target {TARGET_ROTATION_WEEKS:.0f})",
                  f"  proteins    {', '.join(f'{k} x{v}' for k, v in r['proteins'].most_common())}",
                  f"  anchors {r['n_protein_dinners']:>3}   built on a protein, "
                  f"{len(r['protein_kinds'])} distinct — need "
                  f"{P.MIN_PROTEIN_DINNERS} a week, no repeats",
                  f"  register    {dict(r['registers'])}",
                  f"  effort      {dict(r['efforts'])}",
                  f"  keeps       {dict(r['keeps'])}  "
                  f"({r['packing_share'] * 100:.0f}% pack as a lunch)",
                  f"  lunches {r['n_lunches']:>3}   {dict(r['lunch_styles'])}",
                  f"  drinks  {r['n_drinks']:>3}", ""]
        if r["gaps"]:
            lines.append("  GAPS:")
            for g in r["gaps"]:
                lines.append(f"    [{g['severity']:6}] {_plain(g['text'])}")
        else:
            lines.append("  no gaps — this season is well stocked.")
        lines.append("")
    orphans = orphan_syrups()
    if orphans:
        lines += ["Syrups no drink calls for — they are in the box but can never be "
                  "printed or made:"]
        lines += [f"  {x}" for x in orphans]
        lines += ["  (give a drink `syrup: <slug>`, or retire them)", ""]
    ms = missing_sources()
    if ms:
        lines += [f"Recipes with no source link ({len(ms)} of {len(L.load_dinners())}) — "
                  f"the printed card has no QR and no photo to look at:"]
        lines += [f"  {x['slug']}" for x in ms[:8]]
        if len(ms) > 8:
            lines.append(f"  ... and {len(ms) - 8} more")
        lines.append("")
    st = stale_recipes()
    if st:
        lines += ["Recipes with no verdict (served often, still `rating: null`):"]
        lines += [f"  {x['times']}x  {x['slug']}" for x in st]
        lines.append("")
    return "\n".join(lines)


def _plain(md):
    return md.replace("**", "")


def issue_body(today=None):
    """Markdown for the monthly GitHub issue — a concrete, actionable shopping list of work."""
    today = today or date.today()
    _now, next_s, next_m = upcoming(today)
    r = season_report(next_s)
    month = calendar.month_name[next_m]
    out = [f"## Seasonal refresh — {month} (`{next_s}`)", "",
           f"`{month}` draws on the **{next_s}** pool: **{r['n_dinners']} dinners**, "
           f"which is **{r['rotation_weeks']:.1f} weeks** of non-repeating rotation "
           f"against a season that runs about {WEEKS_PER_SEASON:.0f} weeks.", ""]
    if not r["gaps"]:
        out += ["Nothing to do — this season is well stocked. ✅", ""]
    else:
        out += ["### What to add", ""]
        for g in r["gaps"]:
            out.append(f"- {g['text']}")
        out += ["", "### Suggested split", ""]
        need = next((g["need"] for g in r["gaps"] if g["kind"] == "depth"), 0)
        if need:
            thin_p = [p for p in (L.load_household().get("protein_preference") or [])
                      if r["proteins"].get(p, 0) < 3]
            thin_r = [k for k in ("comfort", "elegant")
                      if r["registers"].get(k, 0) / max(r["n_dinners"], 1) < 0.4]
            out += [f"- **{need} new dinners**, weighted to "
                    f"{', '.join(thin_p) if thin_p else 'the preferred proteins'}",
                    f"- register: lean {', '.join(thin_r) if thin_r else 'either way'}",
                    f"- start from `data/seasonal-pnw.md` for {month} and pick recipes that "
                    f"use what's actually at the market — never the other way round", ""]
    out += ["### Rules every new recipe has to satisfy", "",
            "These are enforced by `tests/test_mealbit.py`, so a recipe that skips them "
            "fails CI rather than reaching the family's inbox:", "",
            "- **Declare how it keeps.** `leftover_quality: good | fair | none`. "
            "`good` packs as-is, `fair` needs one small step (a separate jar, a re-crisp), "
            "`none` means don't pack it — it degrades, or reviving it means *cooking*, and "
            "a weekday lunch has five minutes. `none` must set `leftovers: 0` and its "
            "leftover plan must start \"don't pack this one\". Prefer dishes that are as "
            "good or better on day two; the lunch column is half leftovers.",
            "- **`serves` &ge; `leftovers` + 2.** Two at the table, the rest is lunch.",
            "- **Per-plate ingredients may never be load-bearing.** If it buys cilantro, "
            "raw tomato or arugula, declare `per_plate: [x]` with a `**Per plate:**` "
            "paragraph saying how the dish is complete without it, or `per_plate_exempt: "
            "[x]` with a reason (cooked, roasted, sun-dried). someone at the table cannot eat them and "
            "\"serve it on the side\" is impossible once it is the dressing.",
            "- **Every market line needs a `|| fallback`.** A market is not a shop.",
            "- **No shrimp and no cooked salmon**, at all — those are hard exclusions.", ""]
    out += ["### What's in season that month", "",
            ", ".join(L.load_seasonal()[next_m]["peak"]), ""]
    ms = missing_sources()
    if ms:
        out += ["### Recipes with no source link", "",
                f"{len(ms)} of {len(L.load_dinners())} dinners have no `source_url`, so their "
                f"printed card carries no QR and no photo of the dish. Links must be real and "
                f"checked — a fabricated one wastes a scan in the kitchen and poisons trust in "
                f"every other link on the sheet.", ""]
        out += [f"- `{x['slug']}`" for x in ms[:12]]
        if len(ms) > 12:
            out.append(f"- ...and {len(ms) - 12} more")
        out.append("")
    st = stale_recipes()
    if st:
        out += ["### Recipes with no verdict", "",
                "Served this often and still `rating: null` — nobody has said whether they "
                "liked them, and `rating:` is the only signal the library has:", ""]
        out += [f"- `{x['slug']}` — {x['times']}x" +
                (f" (rated {x['rated']})" if "rated" in x else "") for x in st]
        out.append("")
    out += ["---", "",
            "Recipes are hand-written on purpose — they have to be readable and editable, "
            "which a generated one nobody reviewed is not. Open the repository in Claude "
            "Code and say \"do the seasonal refresh\" — `.claude/skills/mealbit-recipes` "
            "carries the whole contract — or add files to `data/recipes/dinners/` by hand; "
            "`python tests/test_mealbit.py` catches anything malformed.", "",
            "_Opened automatically by `.github/workflows/seasonal-refresh.yml`._"]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Audit the recipe library for seasonal depth.")
    ap.add_argument("--month", type=int, help="report on a specific month (1-12)")
    ap.add_argument("--issue", action="store_true", help="emit a GitHub issue body")
    ap.add_argument("--today", default=None)
    ap.add_argument("--fail-on-gaps", action="store_true",
                    help="exit non-zero if the coming season has high-severity gaps")
    a = ap.parse_args(argv)
    today = date.fromisoformat(a.today) if a.today else date.today()

    if a.month:
        r = season_report(_season_of(a.month))
        print(f"{calendar.month_name[a.month]} -> {r['season']}: {r['n_dinners']} dinners, "
              f"{r['rotation_weeks']:.1f} weeks rotation")
        for g in r["gaps"]:
            print(f"  [{g['severity']}] {_plain(g['text'])}")
        return 0

    print(issue_body(today) if a.issue else text_report(today))
    if a.fail_on_gaps:
        _n, nxt, _m = upcoming(today)
        if any(g["severity"] == "high" for g in season_report(nxt)["gaps"]):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
