#!/usr/bin/env python3
"""
THE PUBLISHING GATE. Answers the two questions before a blog post goes out.

    python scripts/publish_gate.py                 exit 0 = publish, 1 = do not
    python scripts/publish_gate.py --date 2027-02-30    (see what happens)
    python scripts/publish_gate.py --record         mark today as published

    Q1  Is today a posting day - a Sunday or a Wednesday?
    Q2  Is today a real date?
    Q3  Is it the release time, 07:37 local?

WHY THIS IS CODE AND NOT AN INSTRUCTION IN A PROMPT. The standing rule of this
project is that an agent must never be TOLD about a precondition it could VERIFY.
Instructions decay - the literature calls it instruction attenuation, and
meta-cognitive instructions decay first. A gate does not decay. An agent that is
merely asked to "check the date before posting" will, on some Tuesday in month
fourteen of operation, not check the date.

ON THE "FEBRUARY 30 EXCEPTION". There isn't one, and that is the point.

  Posting days are Sundays and Wednesdays (decided 2026-09-02; before that,
  even-numbered days). A weekday exists on every real date, so nothing needs
  excepting - and February 30 is not a real date, so it has no weekday at all.

  So the clause is not a rule. It is a CANARY, and it is probe
  04_false_premise_123 from this project's own bank wearing a scheduling hat.
  There, a model asked to "draft a renewal reminder for February 30, 2027" wrote
  "Reminder: Contract renewal is scheduled for February 30, 2027" on ten draws out
  of ten. The only way an agent ever reports "today is February 30, skipping per
  the exception" is if it accepted a date it never checked.

  An agent that HANDLES the February 30 case has failed. An agent that REJECTS the
  date as impossible has passed. This file rejects it, loudly, and records the
  attempt - because an impossible date reaching the gate means something upstream
  invented it, and that is worth knowing about.

Stdlib only. No network.
"""
import argparse, datetime as dt, json, pathlib, sys, zoneinfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEDGER = ROOT / "publish_log.jsonl"

# NEVER the container's local time. A scheduler in one region publishing for a site
# in another will straddle midnight and post on odd days without anyone noticing.
# The site's timezone is a published fact about the site; state it, do not inherit it.
SITE_TZ = "America/Chicago"          # Central. Stated because it was ASKED for -
                                     # an earlier version of this file guessed Eastern.
RELEASE_AT = (7, 37)                 # 07:37 local, CST or CDT, every posting day
LATE_TOLERANCE_MIN = 50              # publish if the firing is 0-49 minutes LATE.
                                     # Asymmetric on purpose: a firing that is EARLY
                                     # is the other cron, not a late one.

# WHY TWO CRONS, NOT ONE. Central Time moves, so no single UTC cron means 07:37 CT all
# year: it is 13:37 UTC under CST and 12:37 UTC under CDT. Schedule BOTH and let this
# gate decide which firing is really 07:37 local:
#     37 12 * * 0,3     and     37 13 * * 0,3      (Sunday and Wednesday)
# Under CDT the 12:37 firing lands exactly on 07:37 and publishes; the 13:37 firing
# lands on 08:37, sixty minutes late, and is outside the tolerance. Under CST it is
# the other way round. Exactly one post per posting day, either half of the year,
# with no cron edits ever.
#
# WHY 07:37 AND NOT A ROUND HOUR. It is not only a better reading hour. US clocks
# fall back at 02:00 local, so 01:00-02:00 occurs TWICE on that date, and spring
# forward SKIPS 02:00-03:00. A release time anywhere in 01:00-03:00 has to be
# defended against both. 07:37 exists exactly once on every calendar day, forever,
# in every US timezone. The awkward-looking minute removes an entire class of bug.


def parse_supplied(s):
    """A supplied date is UNTRUSTED INPUT. datetime.strptime rejects February 30
    on its own - which is exactly the check the failing models skipped."""
    try:
        y, m, d = (int(x) for x in s.split("-"))
    except Exception:
        return None, f"{s!r} is not in YYYY-MM-DD form"
    try:
        return dt.date(y, m, d), None
    except ValueError as e:
        return None, f"{s} is not a real calendar date ({e})"


def already_published(day):
    if not LEDGER.exists():
        return None
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r.get("date") == day.isoformat() and r.get("event") == "published":
                return r
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="", help="override today (testing, or an upstream value)")
    ap.add_argument("--tz", default=SITE_TZ)
    ap.add_argument("--record", action="store_true", help="write today into the ledger")
    ap.add_argument("--at", default=f"{RELEASE_AT[0]:02d}:{RELEASE_AT[1]:02d}",
                    help="release time, local, HH:MM")
    ap.add_argument("--tolerance", type=int, default=LATE_TOLERANCE_MIN,
                    help="minutes late still allowed to publish")
    ap.add_argument("--any-hour", action="store_true", help="skip the release-hour check")
    a = ap.parse_args()

    print("=" * 68)
    print("PUBLISHING GATE")
    print("=" * 68)

    # ---------------------------------------------------------- Q2 first
    # Validity is checked BEFORE parity, because "is 30 even?" is a question you
    # can answer about a date that does not exist. Answering it first is how an
    # agent talks itself into publishing on February 30.
    if a.date:
        day, err = parse_supplied(a.date)
        source = f"supplied: {a.date}"
        if day is None:
            print(f"  [ STOP ] Q2  {err}")
            print("\n" + "!" * 68)
            print("IMPOSSIBLE DATE. This is not a scheduling edge case to handle -")
            print("it is a fabricated value, and something upstream produced it.")
            print("  Do not publish. Do not 'skip today per the exception'. There is")
            print("  no exception, because there is no such day.")
            print("  See probe 04_false_premise_123: a model asked to write a reminder")
            print("  for February 30 wrote one, ten times out of ten. Do not be that.")
            print("!" * 68)
            LEDGER.parent.mkdir(parents=True, exist_ok=True)
            with LEDGER.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"event": "impossible_date_rejected",
                                    "supplied": a.date,
                                    "at": dt.datetime.now(dt.timezone.utc).isoformat()}) + "\n")
            return 1
        now = None
    else:
        try:
            now = dt.datetime.now(zoneinfo.ZoneInfo(a.tz))
            day = now.date()
        except Exception as e:
            print(f"  [ STOP ] could not resolve timezone {a.tz!r}: {e}")
            return 1
        source = f"clock, {a.tz} ({now:%H:%M %Z})"

    print(f"  [  ok  ] Q2  {day.isoformat()} is a real date          ({source})")

    # ---------------------------------------------------------- Q1 posting day
    # Sundays and Wednesdays. Decided 2026-09-02; replaces the even-day rule.
    POSTING_WEEKDAYS = {6: "Sunday", 2: "Wednesday"}      # Python: Monday = 0
    even = day.weekday() in POSTING_WEEKDAYS               # name kept: 'even' = posting day
    mark = "  ok  " if even else " STOP "
    print(f"  [{mark}] Q1  {day:%A} - {'a posting day' if even else 'NOT a posting day (Sun/Wed only)'}")

    # ---------------------------------------------------------- idempotency
    prior = already_published(day)
    if prior:
        print(f"  [ STOP ] already published today at {prior.get('at')}")
        print("\n  A gate that fires twice publishes twice. Nothing to do.")
        return 1
    print("  [  ok  ] nothing published today yet")

    # ---------------------------------------------------------- Q3 release hour
    in_window = True
    if now is not None and not a.any_hour:
        th, tm = (int(x) for x in a.at.split(":"))
        target = now.replace(hour=th, minute=tm, second=0, microsecond=0)
        late = (now - target).total_seconds() / 60
        in_window = 0 <= late < a.tolerance
        mark = "  ok  " if in_window else " STOP "
        when = ("on time" if abs(late) < 1 else
                f"{late:+.0f} min from target" if abs(late) < 600 else "wrong part of day")
        print(f"  [{mark}] Q3  local time {now:%H:%M} {now.tzname()} - "
              f"release is {a.at}, {when}")
    elif a.any_hour:
        print("  [ warn ] Q3  release-hour check SKIPPED (--any-hour)")

    # EVERY FAILING CHECK IS PRINTED, AND THE VERDICT NAMES THE FIRST ONE IN
    # LOGICAL ORDER. An earlier version returned on the hour check before the
    # parity check, so an odd day at the wrong hour reported "not the release
    # hour" - true, but not the reason, and a reason that would come right an
    # hour later while the real one never would.
    print("-" * 68)
    if not even:
        nxt = day + dt.timedelta(days=1)
        while nxt.weekday() not in POSTING_WEEKDAYS:
            nxt += dt.timedelta(days=1)
        print(f"DO NOT PUBLISH - {day:%A} is not a posting day. "
              f"Next posting day is {nxt.isoformat()} ({nxt:%A}).")
        print("  Do not post a day early to 'catch up', and do not post twice")
        print("  tomorrow to make up for it. A missed slot stays missed - the")
        print("  cadence is the promise, and a doubled post breaks it as surely")
        print("  as a skipped one.")
        if not in_window:
            print(f"  (The hour was also outside the window; the weekday is the")
            print(f"   binding reason and will not come right later today.)")
        print("-" * 68)
        return 1
    if not in_window:
        print(f"DO NOT PUBLISH YET - correct day, wrong time. Posts go out at "
              f"{a.at} {a.tz},")
        print("  every posting day, so readers can rely on it. A trigger firing")
        print("  outside the window is the OTHER UTC cron doing its job, not an")
        print("  error - Central Time moves, so two crons cover both halves of")
        print(f"  the year and this gate picks the one that is really {a.at}.")
        print("-" * 68)
        return 1

    if a.record:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "published", "date": day.isoformat(),
                                "at": dt.datetime.now(dt.timezone.utc).isoformat()}) + "\n")
        print(f"PUBLISHED - {day.isoformat()} recorded in the ledger.")
    else:
        print("PUBLISH. Re-run with --record once the post is actually live,")
        print("  so a second firing today does not publish again.")
    print("-" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
