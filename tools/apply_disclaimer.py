#!/usr/bin/env python3
"""Add the standing fallibility disclaimer to the site.

Idempotent: run it twice and the second run changes nothing. It refuses
rather than guesses if a page does not have the shape it expects.

  python apply_disclaimer.py <path-to-repo>/docs
"""
import sys, pathlib

DISC = ('This program can be wrong, and has been. Every figure names the file it came from; '
        'check one before you act on it, and see <a href="/corrections/">Corrections &amp; changes</a> '
        'for what we have already got wrong.')
NAV = '<a href="/methodology/">Methodology</a>'
NOTSTAMP = '  Not the only STAMP — <a href="/other-stamps/">see who else uses the name</a>.<br>\n'

HOME_NOTE = ('  <p class="note" style="margin-top:16px"><b>A receipt is not a warranty.</b> The line says a '
             'model could not stand behind a claim; its absence does not say the rest is true. A model running '
             'this protocol still makes mistakes, and can be wrong in a sentence that carries no line at all. '
             'Verify anything you would act on.</p>\n')
HOME_ANCHOR = ('  defect labels.</p>\n')

TERMS_ANCHOR = '<section><p class="eyebrow">Use</p><h2>What you may do with this</h2>'
TERMS_SECTION = """<section><p class="eyebrow">Fallibility</p><h2>This program can be wrong, and has been</h2>
<p>Every part of this is capable of error, and the parts are worth separating because they fail differently.</p>
<p><b>A model running the protocol can be wrong.</b> The receipt line says the model could not stand behind a
particular claim. Its absence does not certify the rest. A model can state something false in a sentence that
carries no line at all, and the protocol makes that outcome less frequent rather than impossible. Nothing here
is a substitute for checking a fact you intend to rely on.</p>
<p><b>A published figure can be wrong.</b> The numbers are computed from files rather than typed, the graders are
audited by a panel rather than trusted, and the gates refuse rather than warn — and none of that makes a figure
correct. It makes an error findable. Five of the six findings in the first issue were about instruments rather
than models, which is what a young program's errors look like.</p>
<p><b>The prose can be wrong.</b> Issues are drafted with AI assistance and edited and signed by a person, who
answers for them. That is accountability, not infallibility.</p>
<p>So: <b>verify before you implement anything.</b> Every figure names the file it was computed from and the
conditions it was measured under; every issue publishes the SHA-256 of its own bytes so you can confirm you are
reading what was issued. Use those. If you find an error, write to <a href="mailto:s@bud.day">s@bud.day</a> —
every report is answered, and a confirmed error is issued in the
<a href="/corrections/">register</a> under its own date, because a program that hides its mistakes has no
standing to measure anyone else's.</p></section>
"""

CORR_ANCHOR = 'Vol 001 of The Calibration carries the old wording on its cover and stands as issued.</td><td>Corrected on the site; Vol 001 unedited</td></tr>\n'
CORR_ROW = ('<tr><td>2026-09-04</td><td>Change</td><td>The website</td><td>Nothing here was wrong. A standing '
            'statement of fallibility was added — in the foot of every page, beside the receipt on the front page, '
            'and in full under <a href="/terms/">Terms</a> — because the site had been describing the checks it '
            'runs without ever saying plainly that a model running the protocol can be wrong, that a published '
            'figure can be wrong, and that a reader should verify anything they intend to act on. The checks were '
            'already there; the sentence was not.</td><td>Added; no figure or issue changed</td></tr>\n')

def main(root):
    root = pathlib.Path(root)
    if not (root / "index.html").exists():
        print(f"REFUSED: {root} is not the docs directory"); return 1
    changed = []
    for p in sorted(root.rglob("*.html")):
        s = orig = p.read_text(encoding="utf-8")
        rel = p.relative_to(root).as_posix()

        # 1. the footer line, on every page that has the standing footer
        if NAV in s and DISC not in s:
            if rel == "index.html":
                if NOTSTAMP not in s:
                    print(f"REFUSED {rel}: expected the 'Not the only STAMP' footer line"); return 1
                s = s.replace(NOTSTAMP, NOTSTAMP + "  <br>\n  " + DISC + "<br>\n", 1)
            else:
                if s.count(NAV) != 1:
                    print(f"REFUSED {rel}: expected exactly one nav row, found {s.count(NAV)}"); return 1
                s = s.replace(NAV, DISC + "<br><br>" + NAV, 1)

        # 2. the front-page note beside the receipt
        if rel == "index.html" and "A receipt is not a warranty" not in s:
            if HOME_ANCHOR not in s:
                print("REFUSED index.html: could not find the receipt section"); return 1
            s = s.replace(HOME_ANCHOR, HOME_ANCHOR + HOME_NOTE, 1)

        # 3. the Terms section
        if rel == "terms/index.html" and "eyebrow\">Fallibility<" not in s:
            if TERMS_ANCHOR not in s:
                print("REFUSED terms: could not find the 'What you may do' section"); return 1
            s = s.replace(TERMS_ANCHOR, TERMS_SECTION + TERMS_ANCHOR, 1)

        # 4. the register entry
        if rel == "corrections/index.html" and "statement of fallibility was added" not in s:
            if CORR_ANCHOR not in s:
                print("REFUSED corrections: could not find the last register row"); return 1
            s = s.replace(CORR_ANCHOR, CORR_ANCHOR + CORR_ROW, 1)

        if s != orig:
            p.write_text(s, encoding="utf-8"); changed.append(rel)

    print(f"{len(changed)} file(s) changed" if changed else "nothing to do (already applied)")
    for c in changed: print("  " + c)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "docs"))
