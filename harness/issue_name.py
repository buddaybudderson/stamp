#!/usr/bin/env python3
"""
THE NAME OF AN ISSUE. One string, generated, never typed.

    python scripts/issue_name.py calibration 1 2026-08-30
    python scripts/issue_name.py log 1 2026-09-03
    python scripts/issue_name.py --verify calibration-001-issued-sat20260830

Every publication is named the same way:

    display   The Calibration Vol 001 · Sat20260830
    slug      calibration-001-issued-sat20260830

WHY THE WEEKDAY IS IN THE NAME, when the date already implies it. Because it makes
the cadence visible without opening anything. Everything ships on a Saturday, so
every scheduled issue reads SAT and an anomaly reads otherwise - as Calibration 001
does, reading SUN, because its release stamp was taken in UTC twenty minutes before
local midnight on a Saturday and landed on the following day. A name that contradicts
itself is a name you can check, and `--verify` does exactly that: it recomputes the
weekday from the date and refuses a mismatch.

WHY "ISSUED" AND NOT "STAMPED". "Stamped" was the first choice and it is a good pun -
STAMP Protocol, date-stamped. It is also already taken: in this programme STAMPED
names the arm that runs WITH the protocol's system prompt, against NATIVE without it.
The runner prints `arm = STAMPED`, and Calibration 001 discusses "the stamped arm" in
finding 02. A publication called "The Calibration 001 STAMPED ..." would read, to
anyone who has read the methodology, as a claim about which arm it reports.

"ISSUED" costs nothing and gains something: the protocol's central promise is that an
issued Calibration is never edited, so the word in the title states the commitment
that makes the series worth citing.

ZERO-PADDED TO THREE. 001 sorts correctly against 010 and 100; 1 does not.
LOWERCASE AND HYPHENATED for the slug: no quoting, no shell surprises, and it is a
usable URL path unchanged.
"""
import argparse, datetime as dt, re, sys

KINDS = {"calibration": "The Calibration", "log": "The Log"}
DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
SCHEDULED_DAY = "SAT"


def stamp(date):
    """SAT20260830 - weekday token plus compact date."""
    return DAYS[date.weekday()] + date.strftime("%Y%m%d")


def display(kind, no, date):
    """The Calibration Vol 001 · Sun20260830. Decided 2026-09-03: 'Vol' before the
    number, weekday in title case, no ISSUED word - the commitment lives in the
    colophon and the fingerprint, not the title. The slug (and so every URL) keeps
    the older 'issued' form: an issued URL is permanent. Calibration 001's own cover
    still reads 'The Calibration 001 · ISSUED SUN20260830' because that file is
    frozen; the site refers to it by the new form."""
    return f"{KINDS[kind]} Vol {no:03d} · {stamp(date).title()}"


def slug(kind, no, date):
    return f"{kind}-{no:03d}-issued-{stamp(date).lower()}"


SLUG_RE = re.compile(r"^(calibration|log)-(\d{3})-issued-([a-z]{3})(\d{8})$")


def verify(s):
    """Refuse a name whose weekday token does not match its own date."""
    m = SLUG_RE.match(s.lower().removesuffix(".pdf").removesuffix(".html"))
    if not m:
        return False, f"not a well-formed issue name: {s}"
    kind, no, day, ymd = m.groups()
    try:
        d = dt.datetime.strptime(ymd, "%Y%m%d").date()
    except ValueError:
        return False, f"{ymd} is not a real date"
    actual = DAYS[d.weekday()]
    if actual != day.upper():
        return False, (f"{ymd} is a {actual}, but the name says {day.upper()} - "
                       f"one of the two is wrong and the name cannot say which")
    note = ("" if actual == SCHEDULED_DAY else
            f"  (off-cycle: scheduled issues are {SCHEDULED_DAY})")
    return True, f"{kind} {int(no)}, {d.isoformat()}, a {actual}{note}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", nargs="?", choices=list(KINDS))
    ap.add_argument("no", nargs="?", type=int)
    ap.add_argument("date", nargs="?")
    ap.add_argument("--verify", default="")
    a = ap.parse_args()

    if a.verify:
        ok, msg = verify(a.verify)
        print(("  [  ok  ] " if ok else "  [ STOP ] ") + msg)
        return 0 if ok else 1

    if not (a.kind and a.no and a.date):
        sys.exit("usage: issue_name.py <calibration|log> <no> <YYYY-MM-DD>")
    d = dt.date.fromisoformat(a.date)
    print(f"  display   {display(a.kind, a.no, d)}")
    print(f"  slug      {slug(a.kind, a.no, d)}")
    print(f"  files     {slug(a.kind, a.no, d)}.html / .pdf")
    if DAYS[d.weekday()] != SCHEDULED_DAY:
        print(f"\n  NOTE: {a.date} is a {DAYS[d.weekday()]}. Scheduled issues ship "
              f"{SCHEDULED_DAY}; this one is off-cycle and the name will say so.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
