#!/usr/bin/env python3
"""
Render a Calibration to PDF - the archival, citable format.

    python scripts/make_pdf.py reports/calibration_2026-08-29.html
    python scripts/make_pdf.py <file.html> --single      one page per sheet

DEFAULT IS A SPREAD. Pages are rendered A5 portrait and composed two-up onto A4
landscape, the way a journal or a magazine is laid out. Two A5 pages are exactly
296 mm wide and an A4 landscape sheet is 297. That fit is not a coincidence - the
ISO series was designed for it - so there is no scaling and no wasted margin.

SHEET 1 IS THE COVER AND ITS INSIDE FACE, which is exactly the leaf you hold when
you pick a magazine up. The inside front cover is the plate: one unedited excerpt
from the harness, one verse, and the house rule. It is the quietest page in the
issue and it faces the loudest one on purpose.

  sheet 1   [ cover  |  plate ]   the harness, a verse, the house rule
  sheet 2   [   3    |    4   ]   what this is  /  contents
  sheet 3   [   5    |    6   ]   the argument begins

FRONT = 2 below is the count of pages that carry no folio - the cover and the
plate. Everything else derives from it, so moving a front page is a one-line
change rather than a hunt through parity arithmetic in two scripts.

FOLIOS AND THE CONTENTS PAGE ARE COMPUTED, NOT TYPED. Chrome does not implement CSS
paged-media margin boxes, so page numbers are stamped onto the rendered pages here,
at the outer corner - verso left, recto right, the way a printed page carries them.
The contents page is then filled by rendering once, reading back which page each
section landed on, and rendering again. It converges in two passes and is checked;
a hand-typed page number is the same class of mistake as a hand-typed statistic.

WHY A PDF AND NOT JUST THE WEB PAGE. A web page changes under the reader. A dated,
versioned PDF is a fixed artifact that can be cited in a footnote and still found in
five years. Standards bodies issue PDFs; so do actuarial tables. For a reference
series that is not a nicety, it is the mechanism.

ONE DOCUMENT, TWO FORMATS, ONE NAME. The PDF is not a separate publication with its
own title - it is the same Calibration, rendered for the archive. Give it a different
name and the two will drift apart within three issues.

AND AN ISSUED PDF IS NOT EDITED. If a number changes, issue a correction under a new
date and leave the old file standing. That constraint is uncomfortable and it is
exactly what makes a series trustworthy: corrections stay visible instead of being
silently absorbed.

Renders with the headless Chromium already on this machine, so the PDF looks like the
page rather than a re-typeset approximation. Light theme is forced - a PDF has no
viewer preference to respect, and dark grounds waste toner and read badly on paper.
"""
import argparse, hashlib, io, pathlib, re, subprocess, sys, tempfile

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
A5 = (419.53, 595.28)          # points, portrait
A4L = (841.89, 595.28)         # points, landscape - exactly two A5 side by side
A4P = (595.28, 841.89)         # points, portrait - the Log prints on one of these
FRONT = 2                      # pages carrying no folio: the cover and the plate

PRINT_CSS = """
<style>
  :root{ color-scheme: light; }
  @page { size: A5 portrait; margin: 13mm 12mm 14mm 12mm; }
  html,body{ background:#FFFFFF !important; }
  body{ font-size:9pt; line-height:1.55; padding:0 !important; }
  .wrap{ max-width:none }
  .col,.case p,figure,figcaption,.cov-teases,.disclaim{ max-width:none }

  /* THE COVER OWNS EXACTLY ONE HALF-SHEET. Sized to fit, not scaled to fit:
     an A5 page at these margins leaves about 493pt of column, and every element
     below is budgeted against that. The first attempt used the screen sizes and
     spilled its last tease onto the opening page, which is the one place on the
     whole issue where a widow is unmissable. */
  /* THE MEASURE. Screen caps the cover at 56ch; in print the column IS the
     measure, so every element that carried a max-width for the screen gives it
     up here and the accent rule, the issue line and the four hairlines under the
     teases all run from margin to margin. The rule used to stop at 250px against
     a 351pt column - a little over half - which read as a second, narrower page
     sitting on the first. */
  /* THE SLACK IS SPENT WHERE THE CROWDING WAS. An A5 column is 518pt and the
     cover was using 472 of it, so there were about 50pt to give away and no more.
     They went to the tease stack - gap 8->12, rule clearance 8->12 - because that
     is where four findings were stacked tight enough to read as a list. The
     masthead block and the foot gave some back to pay for it, and what is left
     under the imprint is deliberate: ~22pt, so the build has room to move before
     check_front_matter() fails it for spilling onto the plate. */
  .cover{ break-after:page; border-bottom:none; padding:0; gap:11px }
  .cov-top{ max-width:none }
  /* The mark costs the cover no height: the mast block is two lines of 37pt and
     the mark is 46pt beside it. Print sizes it in points so it holds against the
     type rather than against a screen pixel that does not exist here. */
  .cov-brand{ gap:20pt }
  /* (70.3pt of mast minus 46pt of mark) / 2 - the mark is optically centered
     on the two-line wordmark rather than hung off its first line. */
  .cov-mark{ width:46pt; height:46pt; margin-top:12pt }
  .cov-mast{ font-size:37pt; line-height:0.95 }
  .cov-rule{ max-width:none; margin:13px 0 8px; height:2.5px }
  .cov-issue{ max-width:none; font-size:7pt; letter-spacing:.12em }
  .cov-art{ gap:9px }
  /* The grid gave back 14px of width - 11pt of height - to pay for the air
     below. It is still the largest object on the page and still 63 squares. */
  .cov-art svg{ max-width:118px }
  .cov-artcap{ font-size:7pt }
  .tz1{ font-size:14.5pt; line-height:1.16 }
  .tz2{ font-size:10pt; padding-top:12px; line-height:1.26 }
  .cov-teases{ gap:12px } .cov-teases span{ font-size:7.5pt; line-height:1.4;
     margin-top:2px }
  .cov-foot{ font-size:6.5pt; margin-top:4px; gap:4px 14px }

  h1{ font-size:20pt }
  /* FRONT MATTER: ONE PAGE EACH, and the cover before them. Sized against the
     ~518pt an A5 column gives at these margins. The first attempt was 40pt too
     tall and pushed page 2's closing line onto page 3, which shunted the whole
     contents page back one and made every number on it right about the wrong
     layout. check_front_matter() below now fails the build if that recurs. */
  .front{ break-after:page; break-inside:avoid; margin:0 }
  .front .col p{ font-size:8pt; line-height:1.45 }
  .fm-h{ font-size:17pt !important; margin:8pt 0 7pt !important }
  .fm-eyebrow{ font-size:7pt; padding-bottom:6pt }
  .fm-lead{ font-size:9.5pt !important; line-height:1.48 !important }
  .fm-rules{ gap:3.6pt; margin-top:8pt }
  .fm-rule{ font-size:7.5pt; line-height:1.34; gap:6pt }
  .fm-n{ font-size:6.4pt; padding:3pt 3.6pt }
  .fm-close{ font-size:7.3pt; margin-top:6pt; padding-top:5pt }
  /* THE PLATE fills its page rather than sitting at the top of it: the excerpt
     anchors the head, the house rule anchors the foot, and the verse floats on
     auto margins between them. It is the one page in the issue whose whitespace
     is the design rather than a leftover. */
  .plate{ min-height:490pt }
  /* 6.2pt is not a taste decision. The excerpt is captioned "unedited", so the
     type is sized to the longest line in it - 84 characters, 325pt of column,
     0.6em advance in Plex Mono - rather than the excerpt being re-wrapped to
     suit the type. Print a wider line one day and this must come down again. */
  .plate-code{ font-size:6.2pt; line-height:1.75; padding:11pt 12pt; margin-top:18pt;
     white-space:pre }
  .plate-cite{ font-size:6.8pt; margin-top:7pt }
  .plate-verse{ padding:22pt 0 }
  .plate-verse p{ font-size:13.5pt; line-height:1.72 }
  .plate-rule{ padding-top:10pt }
  .plate-rule p{ font-size:10.5pt; line-height:1.5 }
  .plate-rule span{ font-size:6.6pt; margin-top:6pt }

  /* CONTENTS: the space above a group label is what makes the page scannable.
     The entries themselves give a little back so the page still fits one sheet -
     tightening 17 rows by 0.4pt each funds 8pt on each of three transitions. */
  .toc{ margin-top:9pt }
  .toc a{ padding:2.4pt 0 }
  .toc-t{ font-size:9.6pt }
  .toc-n{ font-size:7pt; width:13pt }
  /* qualified for the same specificity reason as the screen rule */
  .toc li.toc-grp{ font-size:7pt; margin:15pt 0 6pt; padding-bottom:5pt }
  .toc li.toc-grp:first-child{ margin-top:0 }
  .toc-p{ font-size:8pt }

  /* A HEADING IS NEVER SPLIT DOWN THE MIDDLE. break-after keeps a heading with
     what follows it; it does nothing about the heading itself, and finding 05's
     two-line title duly broke across the fold - "The grader's safety filter
     deletes" on one page, "specific probes, not random draws" on the next. */
  h2{ margin-top:20pt; font-size:9.5pt; break-after:avoid; break-inside:avoid }
  h3{ font-size:13.5pt; break-after:avoid; break-inside:avoid }
  /* the disclaimer subheads are h4 and were the one heading level with no rule;
     "Independence" alone at the foot of a page is the worst possible orphan in
     the worst possible section. */
  h4{ break-after:avoid }
  .stat .big{ font-size:21pt }
  .stat,.note,.case,figure{ break-inside:avoid }
  /* Crew rows were forced whole so an agent's duties could not be separated from
     the limits on its authority. That stopped working once the presiding judge's
     entry grew to five paragraphs: a row taller than the space left simply jumped
     the page and stranded the section heading above half a blank sheet.

     Relaxing break-inside alone changed nothing, because CHROME DOES NOT FRAGMENT
     A FLEX CONTAINER across pages - it moves the whole box regardless. So in print
     each row becomes a block: name, kind and role on one line, the text flowing
     full width beneath, which fragments the way ordinary prose does. The pieces
     that must not split are protected individually instead. */
  .crew-row{ display:block; break-inside:auto; padding:10pt 0 }
  .crew-who{ display:flex; flex-direction:row; align-items:baseline; gap:8pt;
     margin-bottom:6pt; break-inside:avoid; break-after:avoid }
  .crew-what p{ break-inside:avoid }
  .crew-name{ font-size:11.5pt }
  .crew-kind{ font-size:6.4pt; padding:2.5pt 4pt }
  .crew-role{ font-size:7pt }
  .crew-what p{ font-size:8.4pt; line-height:1.5; margin-bottom:6pt }
  .crew-what code{ font-size:7.6pt; padding:1pt 2.5pt }
  .crew-note{ font-size:8.4pt }
  .finding,.gap{ break-inside:auto }
  p{ orphans:3; widows:3 }

  /* A FINDING'S NUMBER TRAVELS WITH ITS TITLE. "03 PUBLISHABLE" alone at the
     foot of a page, with the claim it labels overleaf, reads as a mistake. */
  .fhead{ break-inside:avoid; break-after:avoid }

  /* TABLES DO NOT STRADDLE A PAGE. Every table in this document is 14 rows or
     fewer and fits a half-sheet whole, so there is nothing to gain from
     splitting one - and two things to lose: a caption that broke mid-sentence
     across the fold, and a one-row orphan under a repeated header. */
  table{ break-inside:avoid; font-size:6.8pt; min-width:0 }
  caption{ break-inside:avoid; break-after:avoid }
  .scroll{ break-inside:avoid }
  tr,td,th{ break-inside:avoid }
  th{ font-size:6.3pt }
  thead{ display:table-header-group }
  .scroll{ overflow:visible }
  a{ color:inherit; text-decoration:none }
  footer{ break-before:avoid; font-size:7.5pt }
  /* the running credit is a screen device; on paper it would repeat under every
     rule and fight the section titles. The cover and colophon carry it. */
  h2::after{ display:none }
</style>
"""


LOG_CSS = """
<style>
  :root{ color-scheme: light; }
  /* A LOG IS ONE SHEET, NOT A SPREAD. There is no cover to face, no contents to
     consult and no argument to walk a reader through, so none of the Calibration's
     apparatus applies - A4 portrait, single flow, and it ends when it ends. */
  @page { size: A4 portrait; margin: 16mm 17mm 16mm 17mm; }
  html,body{ background:#FFFFFF !important; }
  body{ font-size:8.6pt; line-height:1.55 }
  .wrap{ max-width:none; padding:0 !important }

  /* the inverted masthead has to survive print, or the one thing that tells a Log
     from a Calibration at a glance is the one thing the printer drops */
  .top{ margin:0 0 12pt; padding:11pt 13pt;
        -webkit-print-color-adjust:exact; print-color-adjust:exact;
        break-inside:avoid; break-after:avoid }
  .top .wm{ font-size:15pt }
  .top .meta{ font-size:6.6pt; margin-top:7pt; gap:4pt 16pt }
  .top .sub{ font-size:7.4pt; margin-top:8pt; line-height:1.5 }

  h2{ font-size:7pt; margin:13pt 0 6pt; padding-bottom:4pt;
      break-after:avoid; break-inside:avoid }
  p{ font-size:8pt; orphans:3; widows:3 }
  table{ font-size:7.6pt; break-inside:avoid }
  th{ font-size:6.6pt; padding-bottom:5pt }
  td{ padding:3.6pt 10pt 3.6pt 0 }
  .ci{ font-size:6.8pt }
  .quiet,.gap{ font-size:7.4pt; padding:8pt 10pt; margin:9pt 0; break-inside:avoid }
  p{ margin-bottom:8pt }
  footer{ font-size:6.8pt; margin-top:14pt; padding-top:8pt; break-before:avoid }
  a{ color:inherit; text-decoration:none }
</style>
"""


def profile_of(html):
    """Which document is this? A Log carries the inverted masthead and no cover."""
    if 'class="cover"' in html:
        return "calibration"
    if 'class="top"' in html and "The Log" in html:
        return "log"
    return "calibration"


def render(src_html, out, page_css):
    head, body = src_html.split('<div class="wrap">', 1)
    doc = ('<!doctype html><html data-theme="light"><head><meta charset="utf-8">'
           + head + page_css + "</head><body>"
           + '<div class="wrap">' + body + "</body></html>")
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td) / "render.html"
        tmp.write_text(doc, encoding="utf-8")
        r = subprocess.run(
            [CHROME, "--headless", "--disable-gpu", "--no-sandbox",
             "--no-pdf-header-footer", "--virtual-time-budget=8000",
             f"--print-to-pdf={out}", tmp.as_uri()],
            capture_output=True, text=True, timeout=180)
        if not out.exists():
            sys.exit(f"chrome did not produce a PDF:\n{r.stderr[-800:]}")


def page_texts(pdf):
    """The text of each page, whitespace-normalized, for locating sections."""
    out = []
    n = int(subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True
                           ).stdout.split("Pages:")[1].split()[0])
    for i in range(1, n + 1):
        r = subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), str(pdf), "-"],
                           capture_output=True, text=True)
        out.append(re.sub(r"\s+", " ", r.stdout))
    return out


def check_front_matter(texts):
    """The front matter is a fixed shape, so assert it rather than trust it.

    Page 1 cover, page 2 what-this-is, page 3 contents. If page 2 overruns, the
    contents page slides to 4 and every folio it lists is still correct - which is
    what makes the fault so easy to ship. Cheaper to fail the build."""
    want = [(1, "The STAMP Protocol"), (2, "From the harness"),
            (3, "What a Calibration is"), (4, "Contents")]
    bad = []
    for idx, label in want:
        if idx - 1 >= len(texts) or _norm(label) not in _norm(texts[idx - 1]):
            on = next((i + 1 for i, t in enumerate(texts[:8])
                       if _norm(label) in _norm(t)), None)
            bad.append(f"'{label}' should be page {idx}"
                       + (f", it is on page {on}" if on else ", and was not found"))
    return bad


def _norm(s):
    """Down to letters and digits. Section headings are set in small caps with
    letter-spacing and carry curly apostrophes, so the string in the HTML never
    matches the string pdftotext gives back. Comparing only the letters does."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def locate(texts, needles, after):
    """First page (1-based) at or after `after` whose text contains each needle."""
    flat = [_norm(t) for t in texts]
    found = {}
    for nd in needles:
        key = _norm(nd)
        for i in range(after, len(flat)):
            if key in flat[i]:
                found[nd] = i + 1
                break
    return found


CITE_TOC = re.compile(r'(<span class="toc-p" data-find="([^"]+)">)([^<]*)(</span>)')


def fill_toc(html, pages):
    return CITE_TOC.sub(
        lambda m: m.group(1) + str(pages.get(m.group(2), "")) + m.group(4), html)


# A percentage is "transcribed" when it stands in the prose without a citation to
# the registry beside it.
#
# THE FIRST VERSION OF THIS COUNTED THE WRONG THING, and the way it was wrong is
# worth keeping written down. It matched `\d+\.\d+%` over the raw file: decimals
# only, markup included. That let CSS and SVG attributes in, and - far worse - it
# let every whole-number percentage out. The issue's single most quoted figure is
# 89%, which has no decimal point, so the number the document offered as the
# guarantee on its own provenance did not cover its own headline. An exception
# that excludes the thing most likely to be quoted is not an exception; it is a
# way of looking careful. It agreed with the printed 48 exactly, which is how it
# survived: a gate can be precise, self-consistent, and measuring nothing.
#
# So: visible prose only, and any percentage, decimal or whole.
TAGS = re.compile(r"<style.*?</style>|<script.*?</script>|<svg.*?</svg>", re.S)
PCT = re.compile(r"\d+(?:\.\d+)?%")
PCT_CITED = re.compile(r"\d+(?:\.\d+)?%\s*\[FIG [^\]]+\]")
TYPED_CLAIM = re.compile(r'<span class="fig-typed">(\d+)</span>')


def prose(html):
    """The text a reader actually sees, with markup and drawings removed."""
    t = TAGS.sub(" ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


def check_typed_count(html):
    """Refuse the build when the document's own count of transcribed figures is wrong.

    The issue prints how many of its percentages were typed rather than substituted.
    That count is itself a typed number - the most self-referential staleness risk in
    the document - and it is load-bearing: it is the exception attached to a claim
    about provenance. A provenance claim whose stated exception is wrong is worse than
    no claim, because a reader who checks one number and finds it right will assume
    the rest. So it is counted here rather than remembered, and it is a gate rather
    than a note, because a note is something somebody has to have read."""
    claimed = set(int(m) for m in TYPED_CLAIM.findall(html))
    if not claimed:
        return None                       # the document makes no such claim
    t = prose(html)
    total = len(PCT.findall(t))
    cited = len(PCT_CITED.findall(t))
    actual = total - cited
    if claimed == {actual}:
        return None
    return (f"the document says {' and '.join(str(c) for c in sorted(claimed))} "
            f"transcribed percentage(s); there are {actual} "
            f"({total} in the prose, {cited} carrying a citation)")


def stamp_build(src_pdf, out_pdf, text, pagesize):
    """Draw one line at the foot of every page. Used by the Log, which has no
    folio machinery to hang the watermark off."""
    from reportlab.pdfgen import canvas
    from pypdf import PdfReader, PdfWriter
    src = PdfReader(str(src_pdf))
    w = PdfWriter()
    for page in src.pages:
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=pagesize)
        c.setFont("Helvetica", 6.2)
        c.setFillColorRGB(0.62, 0.68, 0.72)
        c.drawString(48, 26, text)
        c.save()
        buf.seek(0)
        page.merge_page(PdfReader(buf).pages[0])
        w.add_page(page)
    with open(out_pdf, "wb") as fh:
        w.write(fh)
    return out_pdf


def stamp_folios(flat, issue, build=""):
    """Draw the page number at the OUTER bottom corner of every page but the cover.

    Verso (even) sits left, recto (odd) sits right, so the numbers land at the
    open edge of the spread where a thumb finds them. Chrome cannot do this - it
    has no @page margin boxes - so it happens here, from the real page index
    rather than from anything anybody counted."""
    from reportlab.pdfgen import canvas
    from pypdf import PdfReader, PdfWriter
    src = PdfReader(str(flat))
    w = PdfWriter()
    IN, OUT_ = 34, 30          # points from the spine-ward and outer edges
    for i, page in enumerate(src.pages):
        n = i + 1
        if n > FRONT:          # the cover and the plate carry no folio
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=A5)
            c.setFillColorRGB(0.48, 0.55, 0.60)
            # sheet 1 is [1|2], so odd pages sit LEFT and even pages sit RIGHT.
            # The outer edge - where a thumb finds the number - is the far side.
            recto = (n % 2 == 0)
            c.setFont("Helvetica-Bold", 8)
            c.drawRightString(A5[0] - OUT_, 26, str(n)) if recto else \
                c.drawString(OUT_, 26, str(n))
            # THE WATERMARK. The foot carries the SHA-256 prefix of the source
            # this page was printed from, so a single sheet - photographed,
            # photocopied, pulled out of a binder - still names the build it
            # belongs to. It is checkable rather than decorative: hash the
            # published HTML and compare. The issue name says which issue; only
            # this says which version of it, which is the thing a never-edited
            # publication most needs a reader to be able to pin down.
            c.setFont("Helvetica", 6.2)
            c.setFillColorRGB(0.62, 0.68, 0.72)
            foot = f"{issue} · {build}" if build else issue
            c.drawString(IN + 8, 26, foot) if recto else \
                c.drawRightString(A5[0] - IN - 8, 26, foot)
            c.save()
            buf.seek(0)
            page.merge_page(PdfReader(buf).pages[0])
        w.add_page(page)
    out = flat.with_name("folioed.pdf")
    with open(out, "wb") as fh:
        w.write(fh)
    return out


def two_up(single, spread):
    """Compose A5 portrait pages two to an A4 landscape sheet, left then right.

    Sheet 1 is the cover and the plate - the two faces of the outer leaf. A
    trailing odd page gets a blank right half rather than a stretched one; the
    grid stays constant, which is the entire reason for laying out in spreads."""
    from pypdf import PdfReader, PdfWriter, Transformation
    from pypdf.generic import RectangleObject
    src = PdfReader(str(single))
    w = PdfWriter()
    pages = list(src.pages)
    for i in range(0, len(pages), 2):
        sheet = w.add_blank_page(width=A4L[0], height=A4L[1])
        sheet.merge_transformed_page(pages[i], Transformation())
        if i + 1 < len(pages):
            sheet.merge_transformed_page(pages[i + 1],
                                         Transformation().translate(A5[0], 0))
        sheet.mediabox = RectangleObject((0, 0, A4L[0], A4L[1]))
    with open(spread, "wb") as fh:
        w.write(fh)
    return len(pages), (len(pages) + 1) // 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("out", nargs="?", default="")
    ap.add_argument("--single", action="store_true",
                    help="one page per sheet instead of the default spread")
    ap.add_argument("--profile", default="", choices=["", "calibration", "log"],
                    help="document type; detected from the file when omitted")
    a = ap.parse_args()

    src = pathlib.Path(a.html).resolve()
    if not src.exists():
        sys.exit(f"no such file: {src}")
    out = pathlib.Path(a.out).resolve() if a.out else src.with_suffix(".pdf")
    html = src.read_text(encoding="utf-8")
    prof = a.profile or profile_of(html)

    if prof == "log":
        # No cover, no contents, no folios, no spread. A Log is a record sheet:
        # rendering it like a magazine would say it is one. It does carry the
        # watermark, though, and it needs it more than the Calibration does: a
        # single record sheet is exactly the kind of page that gets photographed
        # and forwarded on its own, with nothing else around it to say which
        # build it came from.
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        issue = re.sub(r"\s+", " ", m.group(1)).strip() if m else "The Log"
        build = hashlib.sha256(html.encode("utf-8")).hexdigest()[:12]
        with tempfile.TemporaryDirectory() as td:
            raw = pathlib.Path(td) / "log.pdf"
            render(html, raw, LOG_CSS)
            stamp_build(raw, out, f"{issue} · {build}", A4P)
        n = len(page_texts(out))
        kb = out.stat().st_size / 1024
        print(f"wrote {out.name}   {n} page(s), {kb:,.0f} KB   [log]  build {build}")
        print("  One sheet, A4 portrait. The masthead prints inverted, which is the")
        print("  only thing that tells a Log from a Calibration across a desk.")
        print("  An issued record is not edited. Corrections get a new date.")
        return

    # THE RUNNING FOOT COMES FROM THE <title>, which carries the canonical issue
    # name. It used to be scraped from two spans on the cover; renaming the issue
    # broke both regexes at once, the foot silently degraded to "Calibration", and
    # check_pdf.py then read that bare word as a contents entry pointing at page 4.
    # One source, and it is the one the document already has to get right.
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    issue = re.sub(r"\s+", " ", m.group(1)).strip() if m else "Calibration"

    # The build fingerprint is taken from the source BEFORE the contents page is
    # filled, so it identifies the document that was written rather than an
    # intermediate the renderer made and threw away. That is the artifact a
    # reader can obtain and hash for themselves.
    build = hashlib.sha256(html.encode("utf-8")).hexdigest()[:12]

    wrong = check_typed_count(html)
    if wrong:
        sys.exit("THE TRANSCRIBED-FIGURE COUNT IS WRONG - not writing a PDF:\n"
                 f"    {wrong}\n\n"
                 "  This issue publishes that count as the stated exception to its own\n"
                 "  provenance claim. Shipping it wrong turns a statement of honesty\n"
                 "  into a false one, in a document that is never edited. Update the\n"
                 "  <span class=\"fig-typed\"> figures, or convert the percentages.")

    wanted = CITE_TOC.findall(html)
    with tempfile.TemporaryDirectory() as td:
        flat = pathlib.Path(td) / "flat.pdf"
        doc, pages, passes = html, {}, 0

        # TWO PASSES, AND THE SECOND IS CHECKED. Filling the contents page changes
        # the contents page, which could in principle move everything after it. So
        # render, read the page each section landed on, fill, render again - and if
        # the second pass disagrees with the first, fill and try once more rather
        # than shipping numbers that point at the wrong pages.
        for passes in range(1, 4):
            render(doc, flat, PRINT_CSS)
            texts = page_texts(flat)
            # ANCHOR ON THE CONTENTS HEADING, not on any sentence near it. This
            # used to key off a closing paragraph on the contents page; deleting
            # that paragraph silently dropped the anchor to a default, the search
            # then began ON the contents page, and every entry resolved to the
            # contents page itself - which the checker could not see, because a
            # contents page trivially contains every title it lists.
            after = next((i for i, t in enumerate(texts)
                          if _norm("Contents") in _norm(t)
                          and _norm("Bottom line") in _norm(t)), 2) + 1
            got = locate(texts, [w[1] for w in wanted], after)
            if got == pages and passes > 1:
                break
            pages = got
            doc = fill_toc(html, pages)

        missing = [w[1] for w in wanted if w[1] not in pages]
        if missing:
            print("  WARNING: contents entry not found in the rendered pages: "
                  + "; ".join(missing[:3]))
        # FRONT MATTER IS DIAGNOSED FIRST, and the order is the point. The spill
        # check below asks whether the contents entries are on page 4; if an
        # earlier page overran, page 4 is no longer the contents page and every
        # entry "spills" at once. Run the other way round and a one-line overflow
        # on page 3 reports itself as "18 of 18 contents entries did not fit",
        # which sends you to tighten a list that was never the problem. The first
        # failure to print should be the first thing that went wrong.
        bad = check_front_matter(texts)
        if bad:
            sys.exit("FRONT MATTER IS OUT OF SHAPE - not writing a PDF:\n    "
                     + "\n    ".join(bad)
                     + "\n\n  Cover, then what-this-is, then contents, one page each."
                       "\n  A page that overruns slides everything after it, and the"
                       "\n  contents page stays internally consistent while pointing"
                       "\n  at a layout that no longer exists. Shorten the page that"
                       "\n  overran, or reduce its type in PRINT_CSS.")
        spilled = [w[1] for w in wanted
                   if _norm(w[1]) not in _norm(texts[3])] if len(texts) > 3 else []
        if spilled:
            sys.exit("THE CONTENTS PAGE OVERFLOWED - not writing a PDF:\n"
                     f"    {len(spilled)} of {len(wanted)} entries did not fit on page 4:\n"
                     + "\n".join(f"      {s}" for s in spilled[:4])
                     + "\n\n  A contents page that runs onto a second page shifts every"
                       "\n  folio after it AND stops listing what it spilled. Tighten"
                       "\n  .toc in PRINT_CSS, or shorten the list.")

        flat = stamp_folios(flat, issue, build)
        n = len(page_texts(flat))
        if a.single:
            out.write_bytes(flat.read_bytes())
            sheets = None
        else:
            n, sheets = two_up(flat, out)

    kb = out.stat().st_size / 1024
    if sheets:
        print(f"wrote {out.name}   {n} pages on {sheets} sheets, {kb:,.0f} KB")
        print("  sheet 1: cover / the plate.  sheet 2: what this is / contents.")
    else:
        print(f"wrote {out.name}   {n} pages, {kb:,.0f} KB")
    print(f"  contents resolved in {passes} pass(es); "
          f"{len(pages)}/{len(wanted)} entries numbered from the render.")
    print("  An issued PDF is not edited. Corrections get a new date.")


if __name__ == "__main__":
    main()
