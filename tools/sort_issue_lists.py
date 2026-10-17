#!/usr/bin/env python3
"""
ORDER EVERY ISSUE LIST: what is due next first, then what was issued, newest first.

    python tools/sort_issue_lists.py [docs dir]      (run by the release workflow after each release)

Applies to the tabbed list on the home page and to each section of the archive. A row's date is
read from the text it already shows ("Issued Sat 3 October 2026", "Thu 1 Oct 2026", "Due Sat 10
October 2026"); nothing is typed here. Pending rows come first, soonest due first, undated ones
("Soon") last among them. Issued rows follow, newest first; on the same day the higher volume first.
Rows are moved, never edited. Safe to run any number of times.
"""
import datetime as dt, pathlib, re, sys

DOCS = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent.parent / "docs"
ROW = re.compile(r'<div class="issue[^"]*"[^>]*>.*?</div>', re.S)
DATE = re.compile(r"(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (\d{4})")
DATE_US = re.compile(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (\d{1,2}), (\d{4})")
MON = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}
VOL = re.compile(r"Vol (\d+)")


def key(row):
    text = re.sub(r"<[^>]+>", " ", row)
    m = DATE.search(text)
    d = dt.date(int(m.group(3)), MON[m.group(2)], int(m.group(1))) if m else None
    if d is None:                                      # house style from Oct 05, 2026: "Sat Oct 10, 2026"
        u = DATE_US.search(text)
        d = dt.date(int(u.group(3)), MON[u.group(1)], int(u.group(2))) if u else None
    v = VOL.search(text)
    vol = int(v.group(1)) if v else 0
    if 'issue pending' in row:
        return (0, d or dt.date.max, -vol)            # soonest due first; "Soon" last
    return (1, -(d.toordinal() if d else 0), -vol)    # newest first, then higher volume


def sort_block(block):
    rows = ROW.findall(block)
    if len(rows) < 2:
        return block
    first = block.index(rows[0])
    last = block.rindex(rows[-1]) + len(rows[-1])
    between = block[first:last]
    leftover = ROW.sub("", between).strip()
    if leftover:                                       # something other than rows between them
        raise SystemExit(f"refusing to sort: non-row content between rows: {leftover[:80]!r}")
    sep = "\n" if "\n" in between else ""
    return block[:first] + sep.join(sorted(rows, key=key)) + block[last:]


def main():
    p = DOCS / "index.html"
    s = p.read_bytes().decode("utf-8")
    m = re.search(r'(<div class="list">)(.*?)(</div>\s*<script>document\.querySelectorAll\("\.tabs button"\))', s, re.S)
    if m:
        s = s[:m.start(2)] + sort_block(m.group(2)) + s[m.end(2):]
        p.write_bytes(s.encode("utf-8"))
        print("home: sorted")
    p = DOCS / "archive" / "index.html"
    s = p.read_bytes().decode("utf-8")
    parts = re.split(r"(<h2[^>]*>)", s)
    for i in range(2, len(parts), 2):
        parts[i] = sort_block(parts[i])
    p.write_bytes("".join(parts).encode("utf-8"))
    print("archive: sorted")


if __name__ == "__main__":
    main()
