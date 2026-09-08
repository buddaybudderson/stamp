#!/usr/bin/env python3
"""
VERIFY A RENDERED CALIBRATION AGAINST ITSELF.

    python scripts/check_pdf.py reports/calibration_2026-08-29.pdf

  exit 0 = the issue is internally consistent    exit 1 = do not publish it

make_pdf.py computes the contents page from the render, so the numbers on it are
right by construction - right up until they are not. A layout change moves a
section, the fill runs against the old render, and the contents page stays
perfectly self-consistent while pointing at pages that no longer hold what it
says they hold. Nothing about the document looks wrong. That is the whole danger.

So this reads the FINISHED PDF back, splits each A4 sheet into its two A5 halves,
and checks four things a reader would notice and a renderer would not:

  1. FRONT MATTER  cover, plate, what-this-is, contents - pages 1 to 4, in order.
  2. CONTENTS      every entry's page number actually contains that section.
  3. HEADINGS      no heading split down the middle by a page break.
  4. OVERFLOW      no empty pages.

Stdlib plus poppler (pdftotext, pdfinfo), which is already here for the render.
"""
import re, subprocess, sys, pathlib

A5W = 420          # points; the fold sits here on an A4 landscape sheet
A5H = 596
FRONT = [(1, "The STAMP Protocol"), (2, "From the harness"),
         (3, "What a Calibration is"), (4, "Contents")]
CONTENTS_PAGE = 4


def norm(s):
    """Down to letters and digits. Headings are set in small caps with
    letter-spacing and carry curly apostrophes, so the string on the contents
    page never matches the string pdftotext returns. Only the letters do."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def npages(pdf):
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    return int(out.split("Pages:")[1].split()[0])


def half(pdf, sheet, side, layout=False):
    cmd = ["pdftotext", "-f", str(sheet), "-l", str(sheet),
           "-x", "0" if side == "L" else str(A5W + 1), "-y", "0",
           "-W", str(A5W), "-H", str(A5H)]
    if layout:
        cmd.append("-layout")
    return subprocess.run(cmd + [str(pdf), "-"], capture_output=True, text=True).stdout


def page(pdf, folio):
    """Text of a single numbered page. Sheet 1 is [cover | plate], so pages pair
    up straight: page n sits on sheet ceil(n/2), odd left (verso), even right."""
    return half(pdf, (folio + 1) // 2, "L" if folio % 2 else "R")


WORD = re.compile(r'<word xMin="[\d.]+" yMin="([\d.]+)" xMax="[\d.]+" '
                  r'yMax="([\d.]+)">([^<]*)</word>')


def first_words(pdf, folio, n=6):
    """(text, glyph height, median glyph height) for the top of a page.

    Read off the word boxes rather than the flat text, because glyph height is
    the only thing that separates a heading from a paragraph after the fact."""
    sheet = (folio + 1) // 2
    xml = subprocess.run(["pdftotext", "-bbox-layout", "-f", str(sheet),
                          "-l", str(sheet), str(pdf), "-"],
                         capture_output=True, text=True).stdout
    left = folio % 2 == 1
    words = []
    for m in WORD.finditer(xml):
        y0, y1, w = float(m.group(1)), float(m.group(2)), m.group(3)
        # the x bounds are not captured, so split the sheet by re-reading xMin
        words.append((y0, y1 - y0, w))
    # re-parse with x so the correct half is taken
    xs = re.findall(r'<word xMin="([\d.]+)"', xml)
    if len(xs) != len(words):
        return None
    side = [(y0, h, w) for (y0, h, w), x in zip(words, xs)
            if (float(x) < A5W) == left]
    if not side:
        return None
    heights = sorted(h for _, h, _ in side)
    body = heights[len(heights) // 2] or 1
    top = min(y0 for y0, _, _ in side)
    head = [(y0, h, w) for y0, h, w in side if y0 < top + 2]
    if not head:
        return None
    text = " ".join(w for _, _, w in head[:n])
    return text, max(h for _, h, _ in head), body


def parse_contents(txt):
    """Entries off the contents page. pdftotext emits the title and its folio on
    separate lines, so pair each title with the next bare number under it."""
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    out, pending = [], None
    for l in lines:
        if re.fullmatch(r"\d{1,3}", l):
            if pending:
                out.append((pending, int(l)))
                pending = None
        elif re.fullmatch(r"\d\d", l.strip()):
            continue
        elif (l.isupper() or len(l) < 8 or l.startswith("Contents")
              or "Calibration No." in l or "ISSUED" in l.upper()
              or l.startswith(("The Calibration", "The Log"))):
            # the last of those is the running foot, which sits directly above
            # the folio and otherwise reads as an entry pointing at its own page
            pending = None
        else:
            pending = l
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/check_pdf.py <file.pdf>")
    pdf = pathlib.Path(sys.argv[1]).resolve()
    if not pdf.exists():
        sys.exit(f"no such file: {pdf}")
    sheets = npages(pdf)
    folios = sheets * 2

    print("=" * 76)
    print(f"CALIBRATION CHECK - {pdf.name}   {sheets} sheets")
    print("=" * 76)
    fails = []

    # 1 ------------------------------------------------------------ front matter
    for folio, label in FRONT:
        if norm(label) in norm(page(pdf, folio)):
            print(f"  [  ok  ] front     '{label}' is page {folio}")
        else:
            on = next((f for f in range(1, 9) if norm(label) in norm(page(pdf, f))), None)
            print(f"  [ STOP ] front     '{label}' is not page {folio}"
                  + (f" - it is on page {on}" if on else " - not found at all"))
            fails.append(f"{label} moved off page {folio}")

    # 2 --------------------------------------------------------------- contents
    entries = parse_contents(page(pdf, CONTENTS_PAGE))
    good = 0
    for title, folio in entries:
        if folio == CONTENTS_PAGE:
            # A section cannot live on the contents page. Accepting this is how a
            # broken locator passes: page 4 contains every title it lists, so
            # "the title is on the page it names" is true and meaningless.
            print(f"  [ STOP ] contents  p{folio} IS the contents page - "
                  f"{title[:38]} resolved to itself")
            fails.append(f"contents entry points at the contents page: {title[:34]}")
            continue
        if folio < 1 or folio > folios:
            print(f"  [ STOP ] contents  p{folio} does not exist - {title[:44]}")
            fails.append(f"contents points off the end: {title[:40]}")
            continue
        if norm(title[:36]) in norm(page(pdf, folio)):
            good += 1
        else:
            print(f"  [ STOP ] contents  p{folio} does not contain - {title[:44]}")
            fails.append(f"contents wrong for {title[:40]}")
    if entries and good == len(entries):
        print(f"  [  ok  ] contents  all {good} entries land on the page they name")
    elif not entries:
        print("  [ STOP ] contents  no entries parsed from the contents page")
        fails.append("contents page is empty")

    # 3 --------------------------------------------------------------- headings
    # A split heading and a paragraph running over the fold look identical in
    # plain text - both leave a lowercase fragment at the top of the next page -
    # and the first version of this check duly failed the build over an ordinary
    # paragraph. So judge by GLYPH SIZE instead: the first words on a page, set
    # at heading height and beginning lowercase, can only be the tail of a
    # heading that started on the page before.
    split = []
    for f in range(CONTENTS_PAGE + 1, folios + 1):
        head = first_words(pdf, f)
        if not head:
            continue
        text, size, body = head
        if size > body * 1.35 and text[:1].islower():
            prev = [l.strip() for l in page(pdf, f - 1).splitlines() if l.strip()]
            split.append((f, (prev[-1][-34:] if prev else "?"), text[:38]))
    if split:
        for f, a, b in split:
            print(f"  [ STOP ] heading   split across p{f-1}/p{f}: ...{a} | {b}...")
            fails.append(f"heading split at page {f}")
    else:
        print("  [  ok  ] heading   none split across a page break")

    # 4 --------------------------------------------------------------- overflow
    over = [f for f in range(1, folios + 1) if not page(pdf, f).strip()]
    if over:
        print(f"  [ warn ] blank     empty page(s): {', '.join(map(str, over))}")
    else:
        print("  [  ok  ] blank     no empty pages")

    print("-" * 76)
    if fails:
        print("DO NOT PUBLISH: " + "; ".join(fails[:4]))
        print("  An issued Calibration is never edited, so a layout fault shipped")
        print("  once is in the record for good. Fix it and re-render.")
        print("-" * 76)
        return 1
    print(f"PUBLISHABLE. {folios} pages, {len(entries)} contents entries, all verified")
    print("  against the finished PDF rather than against the render that made it.")
    print("-" * 76)
    return 0


if __name__ == "__main__":
    sys.exit(main())
