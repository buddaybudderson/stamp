#!/usr/bin/env python3
"""
WHAT IS DUE TODAY? The alternation gate.

    python scripts/whats_due.py
    python scripts/whats_due.py --date 2026-09-10
    python scripts/whats_due.py --schedule 12        next 12 releases

  exit 0 = something is due today    exit 1 = nothing is due, do not publish

THE SHAPE. Everything ships on a Saturday, alternating:

    Sat  The Log          derived, unattended, Jayden Lee
    Sat  Calibration      measured, signed, Lawrence Ho
    Sat  The Log
    ...

A weekday beats a date. "Every other Saturday" is a habit a reader can form;
"the 1st and the 15th" drifts across the week and never becomes one.

WHY SATURDAY. It was drawn, not reasoned about: the seven weekdays were put to a
generator and the draw was made by a pitbull standing on the enter key. There was no
better argument available. Any weekday would have served, and a chosen one would have
carried an implied claim about readership that nothing here has measured. The draw is
recorded in the masthead because a reader is entitled to know that it was arbitrary.

CRON CANNOT SAY "EVERY OTHER SATURDAY". So the cron fires EVERY Saturday and this
decides which of the two is due. That is the right split anyway - a schedule a
person can edit is not a gate.

THE TRAP, and it is a real one: do not derive the alternation from the ISO week
number. Most years have 52 ISO weeks and some have 53, so week-number parity flips
at those year boundaries and the two publications silently swap places forever
after. 2026 and 2032 are 53-week years. Count whole weeks from a fixed anchor date
instead; that cannot drift, because it never consults the calendar's opinion about
what week it is.

RELEASE TIME is 15:37 America/Chicago. The blog keeps its own 07:37 slot - a morning
read - while the two publications and the audio edition go out together in the
afternoon, which is when a thing that is meant to be an event should land.

15:37 has the same property that made 07:37 safe: it exists exactly once on every
calendar day, in every US timezone, forever. The DST hazard is confined to 01:00-03:00
local, where an hour occurs twice in autumn and not at all in spring. Any release time
outside that window needs no special handling; any time inside it needs a great deal.

The publishing window runs from 15:37 to fifty minutes later, asymmetric on purpose:
a firing that is EARLY is the other cron, not a late one. Two crons are needed because
Central Time moves and no single UTC time is 15:37 CT all year:

    37 20 * * 6      # 15:37 CT during CDT
    37 21 * * 6      # 15:37 CT during CST
"""
import argparse, datetime as dt, json, pathlib, sys
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEDGER = ROOT / "release_log.jsonl"

# 2026-09-05, the first Saturday after Calibration No. 1 went out, and a Log week.
ANCHOR = dt.date(2026, 9, 5)
SATURDAY = 5
SUNDAY, WEDNESDAY = 6, 2   # The Bench, added 2026-09-07
FLOOR_DAYS = 12          # minimum between Calibrations, per protocol/channels.json
TZ = "America/Chicago"
RELEASE = dt.time(15, 37)
BENCH_RELEASE = dt.time(7, 37)   # the blog's own morning slot
WINDOW_MIN = 50          # how late a firing may be and still publish

# The Bench is not on the alternation. It is not derived from the harness and carries
# no issue floor, so it has no parity and no minimum gap - only its weekday and its
# own 07:37 slot. Kept in this file so one script answers "what ships today" for
# every channel rather than two scripts disagreeing.
BENCH_DAYS = (SUNDAY, WEDNESDAY)


def due_on(d):
    """'log', 'calibration', 'bench', or None.

    Saturdays alternate Log/Calibration by whole weeks from the anchor, never ISO
    weeks. Sundays and Wednesdays are The Bench, which does not alternate."""
    if d.weekday() in BENCH_DAYS:
        return "bench"
    if d.weekday() != SATURDAY:
        return None
    weeks = (d - ANCHOR).days // 7
    return "log" if weeks % 2 == 0 else "calibration"


KIND_NAME = {"calibration": "Calibration", "log": "The Log", "bench": "The Bench"}
RELEASE_TIME = {"calibration": RELEASE, "log": RELEASE, "bench": BENCH_RELEASE}


def schedule(start, n):
    d, out = start, []
    while len(out) < n:
        what = due_on(d)
        if what:
            out.append((d, what))
        d += dt.timedelta(1)
    return out


def issued(scheduled_only=False):
    """Dates already released, by kind, from the ledger.

    scheduled_only drops releases flagged as the anchor. THE FLOOR GOVERNS THE GAP
    BETWEEN SCHEDULED ISSUES, and the anchor is by definition not one: Calibration
    No. 1 went out on a Sunday, before the cadence existed. Its gap to No. 2 is 11
    days, one short of the floor, and refusing No. 2 over that would enforce a rule
    about cadence drift against the one issue that had no cadence to drift from.

    This exemption can apply exactly once and cannot recur, because every release
    after the anchor is on-cycle and therefore 14 days from its neighbour."""
    out = {"calibration": [], "log": [], "bench": []}
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if scheduled_only and r.get("anchor"):
                    continue
                out.setdefault(r["kind"], []).append(dt.date.fromisoformat(r["date"]))
    for v in out.values():
        v.sort()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="", help="YYYY-MM-DD, defaults to today")
    ap.add_argument("--schedule", type=int, default=0, help="print the next N releases")
    ap.add_argument("--record", default="", help="record a release: calibration|log|bench")
    ap.add_argument("--ignore-time", action="store_true",
                    help="skip the release-window check (planning, not publishing)")
    a = ap.parse_args()

    now = (dt.datetime.now(ZoneInfo(TZ)) if ZoneInfo and not a.date
           else dt.datetime.now())
    today = dt.date.fromisoformat(a.date) if a.date else now.date()

    if a.schedule:
        print("=" * 62)
        print(f"NEXT {a.schedule} RELEASES  -  Saturdays alternate; The Bench Sun & Wed")
        print("=" * 62)
        prev = {}
        for d, what in schedule(today, a.schedule):
            gap = f"  +{(d - prev[what]).days}d" if what in prev else ""
            print(f"  {d}  {d.strftime('%a')}   "
                  f"{KIND_NAME[what]:<12}{gap}")
            prev[what] = d
        return 0

    what = due_on(today)
    print("=" * 62)
    print(f"WHAT IS DUE  -  {today} ({today.strftime('%A')})")
    print("=" * 62)

    if not what:
        nxt = schedule(today, 1)[0]
        print(f"  [ STOP ] nothing is due today. The Calibration and The Log alternate")
        print(f"           on Saturdays; The Bench runs Sundays and Wednesdays.")
        print(f"           next: {nxt[0]} ({KIND_NAME[nxt[1]]})")
        print("-" * 62)
        return 1

    name = KIND_NAME[what]
    if what == "bench":
        print(f"  [  ok  ] weekday   {today.strftime('%A')}, a Bench day")
    else:
        print(f"  [  ok  ] weekday   Saturday, week {((today - ANCHOR).days // 7)} from anchor")
    print(f"  [  ok  ] due       {name}")

    # release window - only when this is a real publish, not a date lookup.
    #
    # The window polices a CRON, not a person. It exists because Central Time moves
    # and the Saturday release is fired by two crons (one for CDT, one for CST); the
    # window is how the wrong one is caught - "an early firing is the OTHER cron".
    # The Bench is written, signed and posted by a person, so there is no second
    # firing to catch and nothing for the window to protect against. A person does
    # not miss a slot; they publish when they have finished checking. Scoped to the
    # cron-fired channels 2026-09-07, the day the rule was found objecting to a
    # finished, verified Bench issue at 20:43 CT on its own release day.
    if what == "bench":
        print(f"  [  ok  ] window    n/a - The Bench is hand-published; the window "
              f"polices the cron")
    elif not a.date and not a.ignore_time:
        if ZoneInfo is None:
            print("  [ warn ] window    no zoneinfo; cannot check the release time")
        else:
            slot = RELEASE_TIME[what]
            target = now.replace(hour=slot.hour, minute=slot.minute,
                                 second=0, microsecond=0)
            late = (now - target).total_seconds() / 60
            if late < 0:
                print(f"  [ STOP ] window    {-late:.0f} min early - release is "
                      f"{slot.strftime('%H:%M')} {TZ}")
                print("           An early firing is the OTHER cron, not a late one.")
                print("-" * 62)
                return 1
            if late > WINDOW_MIN:
                print(f"  [ STOP ] window    {late:.0f} min late, window is {WINDOW_MIN}")
                print("           A missed slot stays missed. No catch-up releases.")
                print("-" * 62)
                return 1
            print(f"  [  ok  ] window    {late:.0f} min after {slot.strftime('%H:%M')} "
                  f"{TZ}, window {WINDOW_MIN}")

    log, sched = issued(), issued(scheduled_only=True)
    if sched[what]:
        last = sched[what][-1]
        gap = (today - last).days
        if what == "calibration" and gap < FLOOR_DAYS:
            print(f"  [ STOP ] floor     last Calibration {gap}d ago, floor is {FLOOR_DAYS}d")
            print("-" * 62)
            return 1
        print(f"  [  ok  ] floor     {gap}d since the last scheduled {name}")
    elif log[what]:
        gap = (today - log[what][-1]).days
        print(f"  [  ok  ] floor     {gap}d since the off-cycle anchor "
              f"({log[what][-1]}); the floor governs scheduled issues only")
    else:
        print(f"  [  ok  ] floor     no {name} recorded yet")

    if any(d == today for d in log[what]):
        print(f"  [ STOP ] once      a {name} is already recorded for today")
        print("-" * 62)
        return 1

    print("-" * 62)
    if what == "calibration":
        print("RELEASE A CALIBRATION. Lawrence Ho signs it; no agent may issue one.")
        print("  Before it goes: scripts/check_pdf.py, scripts/holdout_gate.py,")
        print("  and scripts/movement.py for any claim that a model moved.")
    elif what == "bench":
        print("RELEASE A BENCH POST. Written and signed by a person.")
        print("  Before it goes: scripts/holdout_gate.py --path docs, always.")
        print("  check_pdf.py applies only to a Bench post issued in the")
        print("  Calibration shape (frozen source + PDF); a working note has none.")
    if a.record:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": a.record, "date": today.isoformat(),
                                 "at": dt.datetime.now(dt.timezone.utc).isoformat()}) + "\n")
        print("  recorded.")
    print("-" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
