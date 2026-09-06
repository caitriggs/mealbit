#!/usr/bin/env python3
"""
Should a scheduled firing send the newsletter right now?

    python tools/send_gate.py                 # prints send=true|false for $GITHUB_OUTPUT,
                                              # and the reason on stderr
    python tools/send_gate.py --now "2026-09-05 20:47"   # decide for another local time

WHY THIS IS NOT "IS IT 17:00"

GitHub's cron is best-effort. On 2026-09-05 the two Saturday firings ran at 20:47 and
22:27 Pacific instead of 17:00 and 18:00, the gate asked "is it exactly 17:00?", and the
household got no email before the Sunday market. So the rule is now:

  send if the last scheduled moment (send.day at send.hour, household timezone) was at
  most GRACE_HOURS ago, AND data/history.json does not already hold that week.

History is what makes the DST twin cron and a late duplicate safe: whichever firing
sends first commits the week, and every later one sees it and stands down. The
concurrency group in the workflow serialises the runs so that commit lands before the
next run checks out.
"""
import argparse
import calendar
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mealbit import library as L      # noqa: E402
from mealbit import planner as P      # noqa: E402

# How long after the scheduled moment a firing still counts. Eight hours reaches from a
# 5pm send to 1am, which is later than anyone wants but still before a Sunday market;
# beyond that the week has moved on and a person should trigger the send by hand.
GRACE_HOURS = 8


def last_scheduled(now, day_name, hour):
    """The most recent send.day-at-send.hour at or before `now` (tz-aware)."""
    day_idx = list(calendar.day_name).index(day_name)
    back = (now.weekday() - day_idx) % 7
    cand = now.replace(hour=hour, minute=0, second=0, microsecond=0) - timedelta(days=back)
    if cand > now:
        cand -= timedelta(days=7)
    return cand


def decide(now, cfg, hist):
    """(send: bool, reason: str) for a tz-aware local `now`."""
    day = cfg.get("send_day", "Saturday")
    hour = int(cfg.get("send_hour", 17))
    tz = cfg.get("timezone", "UTC")
    sched = last_scheduled(now, day, hour)
    late = now - sched
    week_of = P.week_start(sched.date()).isoformat()
    when = f"{now:%A %H:%M} in {tz}"
    if any(w.get("week_of") == week_of for w in hist.get("weeks", [])):
        return False, f"{when}: the week of {week_of} is already in data/history.json — sent earlier"
    if late > timedelta(hours=GRACE_HOURS):
        return False, (f"{when}: the last scheduled send was {day} {hour:02d}:00, "
                       f"{late.total_seconds() / 3600:.1f}h ago — more than {GRACE_HOURS}h, "
                       f"so this firing is not it (the DST twin, or the cron lines need editing)")
    return True, (f"{when}: {late.total_seconds() / 60:.0f} min after the scheduled {day} "
                  f"{hour:02d}:00 send, and the week of {week_of} has not been sent")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--now", help='local time to decide for, "YYYY-MM-DD HH:MM"')
    a = ap.parse_args(argv)
    cfg = L.load_household()
    tz = ZoneInfo(cfg.get("timezone", "UTC"))
    now = (datetime.strptime(a.now, "%Y-%m-%d %H:%M").replace(tzinfo=tz)
           if a.now else datetime.now(tz))
    send, why = decide(now, cfg, L.load_history())
    print(why, file=sys.stderr)
    print(f"send={'true' if send else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
