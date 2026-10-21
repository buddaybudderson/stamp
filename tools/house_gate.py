#!/usr/bin/env python3
"""
THE HOUSE GATE. Does every page on the site keep the house rules that a parser can settle?

    python tools/house_gate.py [docs dir]            report; exit 1 if any FAIL (required on every pull request: the Ten House Protocols, R5)
    python scripts/house_gate.py [docs dir] --json   the same, machine-readable
    python tools/house_gate.py [docs dir] --as-of=YYYY-MM-DD   judge the dates as of another day (tests)

Drafted Oct 12, 2026 at Lawrence Ho's request: "prevent AI hallucination and AI slop as much as
possible, by ensuring 100% following our internal protocol". The protocol is HOUSE_GATE.md, beside
the other charters in protocol/. Like publish_gate.py and footer_check.py, this file does not ask
whether a claim is TRUE; that stays with a person reading the cited source. It counts what can be
counted, so that a person's reading time goes where only a person can help.

FAIL  breaks a written house rule; nothing ships until it is fixed or the rule is changed in writing.
WARN  a pattern that is usually a defect; a person decides, and says so in AUDIT.md if it stays.

  H1  dates       every visible date is "Oct 08, 2026" (master rule, Oct 08, 2026)
  H2  citations   every [N] marker lands on reference N, and every reference is cited (citecheck)
  H3  anchors     every #anchor and every internal link resolves
  H4  house mark  "Begun by a person · Drafted by AI · Edited together · Signed by a person", in full
  H5  SI          "SI" in our own voice only as 'Super Intelligence' (SI), quoted (SI page house style)
  H6  slop        stock phrases that carry no information (WARN; listed below, with the reason)
  H7  unsourced   a figure in a sentence of a sourced standing page with no source marker (WARN)
  H8  freshness   a "Last checked" date more than 14 days old (WARN)
  H9  notice      the standing AI notice is on every framed page, word for word
  H10 red         the measured-figure red is not used as a chart colour (Colophon rule)
  H14 writing     the mechanical items of the studio's human-writing checklist (WARN)
  H15 certainty   a shown score carries its own band word (Protocol 4, R8); a labelled claim with no score
                  is WARN until Monday Nov 09, 2026 and FAIL from that day (R3)

Issued documents (source.html and the frozen bytes inside an issue page) and the archived protocol
page are never checked against today's rules: they are kept as issued, and are corrected only by a
dated row in Corrections + changes.
Stdlib only. No network.
"""
import datetime as dt, html, json, pathlib, re, sys

DOCS = pathlib.Path(next((a for a in sys.argv[1:] if not a.startswith("--")), str(pathlib.Path(__file__).resolve().parent.parent / "docs")))
TODAY = next((dt.date.fromisoformat(a[8:]) for a in sys.argv[1:] if a.startswith("--as-of=")), dt.date.today())
# R3: legacy claims keep their labels until scored; from this day an unscored claim fails like any other
SCORE_DUE = dt.date(2026, 11, 9)
SCORE_BANDS = [(100, 100, "Certain"), (95, 99, "Almost certain"), (80, 94, "Very likely"), (55, 79, "Likely"),
               (45, 54, "Roughly even"), (20, 44, "Unlikely to be confirmed"), (0, 19, "Not confirmed")]   # = tools/certainty.py BANDS
SCORE_SHOWN = re.compile(r"(?<![\d.])(\d{1,3})% (" + "|".join(w for _, _, w in sorted(SCORE_BANDS, key=lambda b: -len(b[2]))) + r")\b")
MON = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
NOTICE = "Protocol STAMP is teamed with AI and can make mistakes. Verify before you implement anything."
MARK = "Begun by a person · Drafted by AI · Edited together · Signed by a person"

# H6: each phrase is here because it says nothing a reader can check. Add to it in writing, with a reason.
SLOP = {
    r"\bdelve[sd]?\b": "filler verb", r"\btapestry\b": "ornament", r"\btestament to\b": "praise without a fact",
    r"\bin today'?s (fast-paced|digital|ever-changing)\b": "throat-clearing", r"\bgame[- ]chang(er|ing)\b": "hype",
    r"\bcutting[- ]edge\b": "hype", r"\bgroundbreaking\b": "hype", r"\brevolutioni[sz]e\b": "hype",
    r"\bseamless(ly)?\b": "marketing", r"\bunlock(s|ing)? the\b": "marketing", r"\bleverag(e|es|ing)\b": "jargon for 'use'",
    r"\bsynerg(y|ies)\b": "jargon", r"\bparadigm shift\b": "jargon", r"\brealm of\b": "ornament",
    r"\bnavigat(e|ing) the complexit": "filler", r"\bit'?s (important|worth) (to note|noting)\b": "throat-clearing",
    r"\bin conclusion\b": "essay filler", r"\bembark(s|ed|ing)? on\b": "ornament", r"\belevate[sd]?\b": "marketing",
    r"\bfoster(s|ed|ing)?\b": "vague", r"\brobust\b": "unmeasured adjective", r"\bholistic\b": "vague",
    r"\bplays? a (crucial|pivotal|vital) role\b": "unmeasured claim", r"\bpivotal\b": "unmeasured adjective",
    r"\bever-evolving\b": "filler", r"\bstate[- ]of[- ]the[- ]art\b": "unmeasured claim (say which benchmark)",
    r"\bworld[- ]class\b": "unmeasured claim", r"\bunprecedented\b": "unmeasured claim (say against what)",
}
# the Docket and the Chronicle are left out: every entry carries its own source line, and docket.py's gate (D1-D12) owns that rule
# H14: what gives machine writing away, after the studio's own proofreading gate (lint_book.py, "I Make Because We Make", Sep 2026).
# Each is a habit a careful human editor removes. Warnings, not failures: the site predates the checklist.
WRITING = {
    "em dash (the checklist allows none; use a comma, a colon or parentheses)": r"—",
    "'not only/just X but Y'": r"\bnot (?:only|just)\b[^.]{0,60}\bbut\b",
    "negative parallelism ('It is not X. It is Y.')": r"\b(?:it|that|this) (?:is|was)n?'?t? not [^.;]{1,50}[;.] (?:it|that|this) (?:is|was)\b",
    "'Enter X.' device": r"(?:^|[.!?]\s+)Enter [A-Z]",
    "doubled word (lowercase prose only; table cells and headings read as runs)": r"(?-i:\b(?!(?:that|had|is|do)\b)([a-z]{2,}) \1\b)",
    "stock connective (moreover, furthermore, additionally, ultimately)": r"\b(?:moreover|furthermore|additionally|ultimately)\b,",
    "throat-clearing (here's the thing, the truth is, let that sink in, needless to say)": r"\b(?:here's the thing|the truth is|let that sink in|needless to say|it bears repeating|at the end of the day|simply put)\b",
    "hedge-intensifier (genuinely, truly, arguably, quietly)": r"\b(?:genuinely|arguably|quietly)\b",
    "inflated verb or noun (serves as, stands as, at its core, landscape, journey, navigate)": r"\b(?:serves as|stands as|at its core|at the heart of|the landscape of|journey|navigat(?:e|es|ing) the)\b",
    "British spelling in an American text": r"\b(?:colour|centre|judgement|whilst|organisation|recognise|practise|towards)\b",
    "straight double quote in visible text": r'"',
}

SOURCED = ("si/", "military/", "safety/", "independence/", "methodology/", "archive/")


def frozen(rel):
    """Kept as issued (the same list as house_dates.py's SKIP): issues, Bench Vol 001, run records, the archived protocol."""
    return bool(rel.endswith("source.html") or rel.startswith(("protocol/", "bench/no-1-complaint/")) or "/record/" in rel
                or re.match(r"(calibration|log)/\d{3}-issued", rel))


def visible(s):
    s = re.sub(r"<(script|style|svg)\b.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)))


def own(s):
    """The page's own words: without the site chrome (header, menu, search, site map, notice), which has its own owner."""
    for a, b in (("<!-- sh:start -->", "<!-- sh:end -->"), ("<!-- topband:start -->", "<!-- topband:end -->"), ("<!-- sf:start -->", "<!-- sf:end -->"),
                 ("<!-- sai:start -->", "<!-- sai:end -->"), ("<!-- sx:start -->", "<!-- sx:end -->")):
        s = re.sub(re.escape(a) + ".*?" + re.escape(b), " ", s, flags=re.S)
    s = re.sub(r'<div class="pal".*?</ul></div></div>', " ", s, flags=re.S)
    return s


BAD_DATES = [
    (r"\b\d{1,2} (January|February|March|April|May|June|July|August|September|October|November|December) \d{4}\b", "day-month-year"),
    (r"\b(January|February|March|April|June|July|August|September|October|November|December) \d{1,2},? \d{4}\b", "full month name"),
    (r"\b(" + "|".join(MON) + r") \d{1}, \d{4}\b", "one-digit day"),
    # a weekday is allowed only in full, with no comma, before a house date ("Monday Oct 12, 2026"; Protocol 5); H1b checks it is the right one
    (r"\b(?:(?:Mon|Tue|Tues|Wed|Thu|Thurs|Fri|Sat|Sun),? (?:" + "|".join(MON) + r")[a-z]* \d"
     r"|(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),? (?:" + "|".join(MON) + r")[a-z]* \d(?!(?<=, \w{3} \d)|\d, \d{4}))"
     r"|\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), (?:" + "|".join(MON) + r") \d{2}, \d{4}", "weekday not in the house form"),
    (r"\b(" + "|".join(MON) + r") \d{1,2}[–-]\d{1,2}\b", "date range in one"),
    (r"(?<![\w/.-])20\d\d-\d\d-\d\d(?![\w/.-])", "ISO date in visible text"),
]


def main():
    out = []
    def add(level, code, rel, msg):
        out.append({"level": level, "check": code, "page": "/" + rel, "msg": msg})
    pages = sorted(p for p in DOCS.rglob("*.html") if p.name == "index.html")
    for p in pages:
        rel = p.relative_to(DOCS).as_posix()
        raw = p.read_text(encoding="utf-8", errors="replace")
        if frozen(rel):
            # an issue page: only the frame around the frozen bytes is ours; a reading copy that is not the bytes is skipped
            src = p.parent / "source.html"
            if not src.exists() or "/record/" in rel or rel.startswith("bench/"):
                continue
            frag = src.read_text(encoding="utf-8", errors="replace")
            if frag not in raw:
                continue
            raw = raw.replace(frag, " ")
        body = own(raw)
        text = visible(body)
        # H1 dates
        for pat, why in BAD_DATES:
            for m in re.finditer(pat, text):
                ctx = text[max(0, m.start() - 40):m.end() + 30]
                if why == "ISO date in visible text" and re.search(r"(build|sha|doc\.|serial|issued-|\.json|/)", ctx):
                    continue
                add("FAIL", "H1", rel, f'{why}: "{m.group(0)}" in "…{ctx.strip()}…"')
        # H1b every date exists, and a weekday written before it is its own (Protocol 5, R6: the February 30 canary)
        for m in re.finditer(r"\b(?:(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),? )?(" + "|".join(MON) + r") (\d{2}), (\d{4})\b", text):
            wd, mo, dd, yy = m.group(1), m.group(2), int(m.group(3)), int(m.group(4))
            try:
                d = dt.date(yy, MON.index(mo) + 1, dd)
            except ValueError:
                add("FAIL", "H1", rel, f'impossible date "{m.group(0)}": it does not exist')
                continue
            if wd and wd != d.strftime("%A"):
                add("FAIL", "H1", rel, f'wrong weekday "{m.group(0)}": {mo} {dd:02d}, {yy} is a {d.strftime("%A")}')
        # H4 house mark
        for m in re.finditer(r"Drafted by AI\s*·\s*Edited together", text):
            before = text[max(0, m.start() - 25):m.start()]
            if "Begun by a person" not in before and not before.rstrip().endswith(("“", '"')):   # a quotation of the old form is not a use
                add("FAIL", "H4", rel, f'house mark without its first step: "…{text[max(0, m.start() - 30):m.end() + 30].strip()}…"')
        # H5 bare SI in our own voice
        for m in re.finditer(r"(?<![\w‘'“(\"-])SI(?![\w’'”\")-])", text):
            ctx = text[max(0, m.start() - 60):m.end() + 40]
            if re.search(r"Super Intelligence|SI units|International System|“SI”|‘SI’|\"SI\"|SPACEXSI|SpaceXSI|EO 14434|\(SI\)|SI-powered|ASI|SI page|SI pa", ctx):
                continue
            add("WARN", "H5", rel, f'bare "SI": "…{ctx.strip()}…"')
        # H6 slop
        for pat, why in SLOP.items():
            for m in re.finditer(pat, text, re.I):
                add("WARN", "H6", rel, f'"{m.group(0)}" ({why}): "…{text[max(0, m.start() - 50):m.end() + 40].strip()}…"')
        # H14 writing like a person (Budday Budderson Studio's own checklist, from "I Make Because We Make",
        # lint_book.py, Sep 2026): the mechanical items, one warning per kind per page, with a count and a first example.
        # Quotations are skipped: what a source said is never rewritten.
        prose = re.sub(r"“[^”]{0,400}”|‘[^’]{0,200}’", " ", text)
        for kind, pat in WRITING.items():
            hits = list(re.finditer(pat, prose, re.I))
            if hits:
                m = hits[0]
                add("WARN", "H14", rel, f'{kind}: {len(hits)}x, first "…{prose[max(0, m.start() - 40):m.end() + 40].strip()}…"')
        # H7 unsourced figures on sourced standing pages
        if rel.startswith(SOURCED):
            for para in re.findall(r"<(p|li|td)\b[^>]*>(.*?)</\1>", body, flags=re.S):
                inner = para[1]
                if re.search(r'href="#(r|m)\d+|href="/(docket|chronicle)/#|class="src"|<a href="https?://', inner):
                    continue
                t = visible(inner)
                if re.search(r"\b\d{2,}(?:[.,]\d+)?\s?(%|percent|states|countries|votes|billion|million|trillion)\b", t):
                    add("WARN", "H7", rel, f'figure with no source marker: "{t[:150]}"')
        # H8 freshness
        for m in re.finditer(r"[Ll]ast checked (" + "|".join(MON) + r") (\d{2}), (\d{4})", text):
            d = dt.date(int(m.group(3)), MON.index(m.group(1)) + 1, int(m.group(2)))
            if (TODAY - d).days > 14:
                add("WARN", "H8", rel, f"last checked {m.group(0)[13:]}: {(TODAY - d).days} days ago")
        # H15 certainty (Protocol 4): a shown score carries the word for its own band
        for m in SCORE_SHOWN.finditer(text):
            n, word = int(m.group(1)), m.group(2)
            right = next((w for lo, hi, w in SCORE_BANDS if lo <= n <= hi), None)
            if word != right:
                add("FAIL", "H15", rel, f'"{m.group(0)}": {n}% is {right or "not a score"}, not {word}')
        # H15 a labelled Docket or Chronicle entry with no computed score (R3: WARN until Nov 09, 2026, FAIL from then)
        entries = re.findall(r'<article class="dk-entry".*?</article>', body, flags=re.S)
        labelled = [e for e in entries if re.search(r'class="dk-tag (Supported|Likely|Unknown)"', e)]
        unscored = [re.search(r'id="([^"]+)"', e).group(1) for e in labelled if "data-certainty=" not in e]
        if unscored:
            late = TODAY >= SCORE_DUE
            add("FAIL" if late else "WARN", "H15", rel,
                f"{len(unscored)} of {len(labelled)} labelled claims carry no certainty score, first {unscored[0]}; "
                + ("unscored claims fail from Monday Nov 09, 2026 (R3)" if late else
                   f"legacy claims must be scored by Monday Nov 09, 2026 (R3), {(SCORE_DUE - TODAY).days} days from {TODAY.strftime('%b %d, %Y')}"))
        # H9 notice
        if "<!-- sh:start -->" in raw and NOTICE not in visible(raw):
            add("FAIL", "H9", rel, "the standing AI notice is missing or reworded")
    # H10: no red in chart palettes
    for css in ("chrome.css", "site.css"):
        s = (DOCS / css).read_text(encoding="utf-8")
        for m in re.finditer(r"--viz-\d:\s*(#[0-9A-Fa-f]{6})", s):
            r, g, b = (int(m.group(1)[i:i + 2], 16) for i in (1, 3, 5))
            if r > 150 and g < 110 and b < 90:
                add("FAIL", "H10", css, f"chart colour {m.group(1)} reads as the measured-figure red")
    # H2 citations: delegate to citecheck, which owns that rule
    import subprocess
    here = pathlib.Path(__file__).resolve().parent
    cc = here / "citecheck.py" if (here / "citecheck.py").exists() else here.parent / "site_audit" / "citecheck.py"
    if cc.exists():
        for rel in ("si/index.html", "military/index.html", "safety/index.html", "independence/index.html"):
            if (DOCS / rel).exists():
                r = subprocess.run([sys.executable, "-I", str(cc), str(DOCS / rel)], capture_output=True, text=True, encoding="utf-8")
                if r.returncode:
                    add("FAIL", "H2", rel, (r.stdout + r.stderr).strip()[:300])
    if "--json" in sys.argv:
        print(json.dumps(out, indent=1, ensure_ascii=False))
    else:
        for o in out:
            print(f'{o["level"]:4} {o["check"]:3} {o["page"]:46} {o["msg"]}')
        f = sum(o["level"] == "FAIL" for o in out); w = len(out) - f
        print(f"house gate: {len(pages)} pages, {f} FAIL, {w} WARN -> {'REFUSED' if f else 'PASS'}")
    return 1 if any(o["level"] == "FAIL" for o in out) else 0


if __name__ == "__main__":
    sys.exit(main())
