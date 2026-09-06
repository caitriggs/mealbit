#!/usr/bin/env python3
"""
Write the GitHub Actions schedule from config/household.yml.

    python tools/schedule.py            # the cron lines the config implies, and what the workflows hold
    python tools/schedule.py --write    # write them into both workflow files
    python tools/schedule.py --remove   # strip them — the state the public template ships in

WHY THE TEMPLATE HAS NO CRON

The upstream repository is a template. It must never send from itself, and a scheduled
run on a public repository with placeholder config would be a red run every Saturday. So
the template ships with `workflow_dispatch` only, and onboarding writes the schedule for
the household's own timezone, day and hour. That also removes the old chore of editing
two cron lines by hand for anyone not on US Pacific time.

GitHub cron is UTC and has no idea about daylight saving, so one line is written per
distinct UTC offset the zone uses across the year — two for most of North America and
Europe, one for zones without DST. tools/send_gate.py lets the first firing after the
send hour go and stands later ones down, so two lines never mean two emails.

The lines live between two marker comments in each workflow file; nothing else in the
file is touched.
"""
import argparse
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKLY = os.path.join(ROOT, ".github", "workflows", "meal-plan.yml")
MONTHLY = os.path.join(ROOT, ".github", "workflows", "seasonal-refresh.yml")
START, END = "  # mealbit:schedule-start", "  # mealbit:schedule-end"
REFRESH_DAY, REFRESH_HOUR = 25, 9     # the seasonal audit: the 25th, 09:00 local


def _cron_dow(u):
    return (u.weekday() + 1) % 7        # cron: Sunday = 0


def weekly_lines(tz, day, hour):
    """[(cron, label)] for `day` at `hour` local, one per distinct UTC offset in the year."""
    z, y, out = ZoneInfo(tz), date.today().year, []
    for m in (1, 7):
        d = date(y, m, 15)
        d += timedelta(days=(DAYS.index(day) - d.weekday()) % 7)
        local = datetime(d.year, d.month, d.day, int(hour), tzinfo=z)
        u = local.astimezone(timezone.utc)
        out.append((f"{u.minute} {u.hour} * * {_cron_dow(u)}",
                    f"{day[:3]} {int(hour):02d}:00 {local.tzname()} == {u.strftime('%a %H:%M')} UTC"))
    return list(dict(out).items())


def monthly_lines(tz, dom=REFRESH_DAY, hour=REFRESH_HOUR):
    z, y, out = ZoneInfo(tz), date.today().year, []
    for m in (1, 7):
        local = datetime(y, m, dom, hour, tzinfo=z)
        u = local.astimezone(timezone.utc)
        out.append((f"{u.minute} {u.hour} {u.day} * *",
                    f"the {dom}th {hour:02d}:00 {local.tzname()} == {u.strftime('%H:%M')} UTC on the {u.day}th"))
    return list(dict(out).items())


def _split(path):
    txt = open(path, encoding="utf-8").read()
    m = re.search(rf"^{re.escape(START)}\n(.*?)^{re.escape(END)}\n", txt, re.S | re.M)
    if not m:
        raise SystemExit(f"{path}: no '{START.strip()}' / '{END.strip()}' markers under on:")
    return txt[:m.start(1)], m.group(1), txt[m.end(1):]


def current(path):
    """The cron expressions the file holds now."""
    _, block, _ = _split(path)
    return re.findall(r'cron:\s*"([^"]+)"', block)


def write(path, lines):
    head, _, tail = _split(path)
    block = "  schedule:\n" + "".join(f'    - cron: "{c}"    # {label}\n' for c, label in lines)
    open(path, "w", encoding="utf-8").write(head + block + tail)


def remove(path):
    head, _, tail = _split(path)
    open(path, "w", encoding="utf-8").write(head + tail)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--write", action="store_true")
    g.add_argument("--remove", action="store_true")
    a = ap.parse_args(argv)

    from mealbit import config as C
    cfg = C.household()
    tz, day, hour = cfg["timezone"], cfg.get("send_day", "Saturday"), int(cfg.get("send_hour", 17))
    if day not in DAYS:
        raise SystemExit(f"send.day is {day!r}; it has to be a full weekday name")
    weekly, monthly = weekly_lines(tz, day, hour), monthly_lines(tz)

    if a.remove:
        remove(WEEKLY); remove(MONTHLY)
        print("removed the schedule from both workflows — the template state; nothing will "
              "send on its own until `tools/schedule.py --write` is run and committed")
        return 0
    if a.write:
        write(WEEKLY, weekly); write(MONTHLY, monthly)
        print(f"wrote {len(weekly)} weekly line(s) for {day} {hour:02d}:00 {tz} and "
              f"{len(monthly)} monthly line(s) — commit both workflow files")
    print(f"config says: {day} {hour:02d}:00 {tz}")
    for c, label in weekly:
        print(f"  weekly   {c:14s} {label}")
    for c, label in monthly:
        print(f"  monthly  {c:14s} {label}")
    have_w, have_m = current(WEEKLY), current(MONTHLY)
    print(f"meal-plan.yml holds:        {have_w or 'no schedule (template state)'}")
    print(f"seasonal-refresh.yml holds: {have_m or 'no schedule (template state)'}")
    if not a.write and set(have_w) != {c for c, _ in weekly}:
        print("  -> out of step with the config; run with --write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
