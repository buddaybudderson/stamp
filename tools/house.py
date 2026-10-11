#!/usr/bin/env python3
"""
WHO PUBLISHES, IN ONE PLACE. Stdlib only.

Every line that names the publisher is written from here: the site map at the foot of every page
and the footer of every standing page (tools/site_chrome.py), the footer of every Log
(harness scripts/ledger.py) and of every Calibration (harness scripts/build_calNNN.py). To change
the company, its charter or its address, change this file, run tools/site_chrome.py, and the next
issue carries it. Issued documents are never rewritten: each keeps the footer it was issued with.

    python tools/house.py FILE...     exit 1 if a file does not carry the current publisher line
"""
import re, sys

COMPANY = "Budday Budderson Studio LLC"
CHARTER = "a New Mexico company"
ADDRESS = "2105 Vista Oeste NW, Suite #E3993, Albuquerque, NM 87120"
UNDER = ("Protocol STAMP", "bud.day")

LINE = f"{' and '.join(UNDER)} are under {COMPANY}, {CHARTER}"   # the publisher line
FOOTER = f"{LINE}<br>{ADDRESS}"                                  # two footer lines, no trailing <br>
SHORT = f"{' and '.join(UNDER)} are under {COMPANY} · {ADDRESS}"  # one line, for the site map

# every earlier form of the publisher line, so a template copied from an older issue is brought up to date
OLD = re.compile(r"Published by Budday Budderson Studio LLC, a New Mexico company"
                 r"|Protocol STAMP and bud\.day are under Budday Budderson Studio LLC, a New Mexico company(?:<br>\s*[^<\n]*Albuquerque, NM \d{5})?")


def stamp(html):
    """The publisher line in html, made current. Returns (html, how many were replaced)."""
    return OLD.subn(lambda m: FOOTER, html)


def missing(html):
    """What a document to be issued lacks, as a list of strings; empty when it is right."""
    return [x for x in (LINE, ADDRESS) if x not in html]


if __name__ == "__main__":
    bad = 0
    for f in sys.argv[1:]:
        m = missing(open(f, encoding="utf-8").read())
        if m: bad += 1; print(f"{f}: lacks {' and '.join(repr(x) for x in m)}")
    print("house line:", "MISSING in %d file(s)" % bad if bad else "present")
    sys.exit(1 if bad else 0)
