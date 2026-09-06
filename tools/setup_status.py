#!/usr/bin/env python3
"""
Is this copy of Mealbit set up for the household using it?

    python tools/setup_status.py          # a checklist a person (or Claude) can read
    python tools/setup_status.py --ci     # exit 1 with a plain-English reason if a send
                                          # would go nowhere; used by the workflow
    python tools/setup_status.py --json   # the same facts, machine-readable

This exists so that an agent opening a freshly forked repository can tell, in one command
and without guessing, whether to start the onboarding survey (.claude/skills/
mealbit-onboarding) or get on with the week. The signals:

  fork         `origin` points at a different owner than config/upstream.yml
  onboarded    config/onboarded.yml exists AND names this repository in `repo:` — the
               survey was completed here, not inherited from the fork's upstream
  addresses    the three send addresses are real, either in the file or in the
               environment (MEALBIT_SEND_FROM / _TO / _TEST_TO from repository secrets)
  password     GMAIL_APP_PASSWORD is in the environment (only checkable where it runs)

Nothing here reads secrets' values or prints them.
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PLACEHOLDER_ADDRESSES = {"you@gmail.com", "household@example.com", "you@example.com",
                         "eater@example.com"}
PLACEHOLDER_NAMES = {"Ada", "Sam"}


def _origin():
    try:
        url = subprocess.run(["git", "-C", ROOT, "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return None
    m = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else None


def _onboarded_repo():
    """The `repo:` an onboarded.yml was written for; "" if the file predates that field;
    None if there is no file."""
    path = os.path.join(ROOT, "config", "onboarded.yml")
    if not os.path.exists(path):
        return None
    try:
        import yaml
        d = yaml.safe_load(open(path)) or {}
        return str(d.get("repo") or "")
    except Exception:
        return ""


def _upstream():
    try:
        import yaml
        d = yaml.safe_load(open(os.path.join(ROOT, "config", "upstream.yml"))) or {}
        return d.get("repo")
    except Exception:
        return None


def facts():
    from mealbit import config as C
    try:
        cfg = C.household()
        cfg_error = None
    except SystemExit as e:
        cfg, cfg_error = {}, str(e)
    try:
        stores = C.stores()
        stores_error = None
    except SystemExit as e:
        stores, stores_error = [], str(e)

    origin, upstream = _origin(), _upstream()
    is_fork = bool(origin and upstream and origin.lower() != upstream.lower())
    is_upstream = bool(origin and upstream and origin.lower() == upstream.lower())
    onboarded_for = _onboarded_repo()
    # A fork inherits the upstream's onboarded.yml. That file counts only if it was
    # written FOR this repository; one written for another household's copy means the
    # survey has not happened here.
    onboarded = onboarded_for is not None and (
        onboarded_for == "" or not origin or onboarded_for.lower() == origin.lower())
    addresses_real = bool(cfg) and not any(
        str(cfg.get(k, "")).lower() in PLACEHOLDER_ADDRESSES
        for k in ("send_from", "send_to", "send_test_to"))
    addresses_from_env = any(os.environ.get(v) for v in
                             ("MEALBIT_SEND_FROM", "MEALBIT_SEND_TO", "MEALBIT_SEND_TEST_TO"))
    names_placeholder = bool(cfg) and set(cfg.get("eaters") or []) <= PLACEHOLDER_NAMES
    return {
        "origin": origin, "upstream": upstream, "is_fork": is_fork, "is_upstream": is_upstream,
        "onboarded": onboarded,
        "onboarded_for": onboarded_for,
        "config_ok": cfg_error is None and stores_error is None,
        "config_error": cfg_error or stores_error,
        "names_placeholder": names_placeholder,
        "eaters": cfg.get("eaters") if cfg else None,
        "addresses_real": addresses_real,
        "addresses_from_env": addresses_from_env,
        "password_in_env": bool(os.environ.get("GMAIL_APP_PASSWORD")),
        "stores": [s["name"] for s in stores],
        "dinners_per_week": cfg.get("dinners_per_week") if cfg else None,
        "lunch_mode": cfg.get("lunch_mode") if cfg else None,
    }


def needs_onboarding(f):
    """
    A fork nobody has surveyed yet, or any copy still wearing placeholder names. The
    upstream itself is the template: it wears placeholder names on purpose and is never
    onboarded — it is where the product is developed, not a household.
    """
    if f.get("is_upstream"):
        return False
    return (f["is_fork"] and not f["onboarded"]) or f["names_placeholder"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ci", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    f = facts()
    if a.json:
        print(json.dumps(dict(f, needs_onboarding=needs_onboarding(f)), indent=1))
        return 0

    def tick(ok):
        return "✅" if ok else "⬜"
    print(f"Mealbit setup status  ({f['origin'] or 'no git remote'})\n")
    print(f"  {tick(f['config_ok'])} config files load"
          + (f" — {f['config_error']}" if f['config_error'] else ""))
    print(f"  {tick(not f['names_placeholder'])} household names set"
          + (f" ({', '.join(f['eaters'])})" if f['eaters'] else ""))
    print(f"  {tick(f['stores'])} stores set" + (f" ({' → '.join(f['stores'])})" if f['stores'] else ""))
    print(f"  {tick(f['addresses_real'] or f['addresses_from_env'])} send addresses "
          + ("real, in the file" if f['addresses_real'] else
             "from environment/secrets" if f['addresses_from_env'] else
             "still placeholders and no MEALBIT_SEND_* in the environment"))
    print(f"  {tick(f['password_in_env'])} GMAIL_APP_PASSWORD in this environment"
          + ("" if f['password_in_env'] else "  (normal on a laptop; it lives in GitHub secrets)"))
    print(f"  {tick(f['onboarded'])} onboarding recorded (config/onboarded.yml)"
          + (f"  — written for {f['onboarded_for']}, not this repository"
             if f["onboarded_for"] and not f["onboarded"] else ""))
    print(f"\n  week shape: {f['dinners_per_week']} dinners, lunches = {f['lunch_mode']}")
    if f["is_fork"]:
        print(f"  this is a FORK of {f['upstream']}")
    print()
    if f["is_upstream"]:
        print("TEMPLATE. This is the upstream itself — the product is developed here and no "
              "household lives here. Nothing to onboard; it must stay in starter state "
              "(placeholder names, no schedule, empty history) and a test holds that.")
    elif needs_onboarding(f):
        print("NOT SET UP. Start the onboarding survey now — "
              ".claude/skills/mealbit-onboarding/SKILL.md — before doing anything else.")
    else:
        print("Set up. Carry on with the week.")

    if a.ci:
        if not (f["addresses_real"] or f["addresses_from_env"]):
            print("\nSTOPPING: the send addresses are placeholders and the three MEALBIT_SEND_* "
                  "secrets are not set, so this email would go to nobody. In the repository: "
                  "Settings → Secrets and variables → Actions → add "
                  "MEALBIT_SEND_FROM, MEALBIT_SEND_TO, MEALBIT_SEND_TEST_TO. "
                  "(.claude/skills/mealbit-secrets/SKILL.md walks through it.)")
            return 1
        if not f["config_ok"]:
            print(f"\nSTOPPING: {f['config_error']}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
