#!/usr/bin/env python3
"""
THE SITE'S CHROME, ONE SOURCE. Stdlib only. Run from the repo root:

    python tools/site_chrome.py            rewrite the header, page search and asset links on every page it owns
    python tools/site_chrome.py --check    say what would change, write nothing

It owns, on every STANDING page (<body class="rd ...">) and every Bench post that is not an issued
document:
  - the header (between <!-- sh:start --> and <!-- sh:end -->): five groups, About always visible,
    a drawer on phones and tablets, the "Latest Calibration" button;
  - the announcement strip (between <!-- topband:start --> and <!-- topband:end -->);
  - the page-search list (var P=[...]);
  - the links to /site.css and /site.js.
It never touches an issued document: Calibration and Log pages, source.html, Bench Vol 001 and its
record, run records, protocol pages. Running it twice changes nothing the second time.

The order of the groups is argued in the PR that introduced it (Oct 09, 2026) and summarised here:
what the program publishes, how it measures, the policy it tracks, why it can be trusted, who it is.
"""
import argparse, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

FROZEN = ("calibration/", "log/", "protocol/", "bench/no-1-complaint/", "bench/something-it-can-check/record/")
POSTS = ("bench/", "writing/marking/", "writing/abstention/")

# 24x24 stroke icons, drawn once here
I = {
 "archive": '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9"/><path d="M10 13h4"/>',
 "gauge": '<path d="M4 15a8 8 0 1 1 16 0"/><path d="M12 15l4-5"/><circle cx="12" cy="15" r="1.2"/>',
 "terminal": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3"/><path d="M12 15h5"/>',
 "book": '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5"/>',
 "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
 "flask": '<path d="M9 3h6"/><path d="M10 3v6L4.5 19a1.5 1.5 0 0 0 1.3 2h12.4a1.5 1.5 0 0 0 1.3-2L14 9V3"/><path d="M7 15h10"/>',
 "list": '<path d="M9 6h11"/><path d="M9 12h11"/><path d="M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
 "proto": '<path d="M8 3h8l5 5v8l-5 5H8l-5-5V8z"/><path d="M9 12h6"/>',
 "db": '<ellipse cx="12" cy="5.5" rx="7" ry="2.5"/><path d="M5 5.5v13c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-13"/><path d="M5 12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5"/>',
 "receipt": '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6"/><path d="M9 12h6"/>',
 "scale": '<path d="M12 3v18"/><path d="M5 7h14"/><path d="M5 7l-3 7a3 3 0 0 0 6 0z"/><path d="M19 7l-3 7a3 3 0 0 0 6 0z"/>',
 "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
 "spark": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6"/>',
 "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
 "fence": '<path d="M5 21V7l2-3 2 3v14"/><path d="M15 21V7l2-3 2 3v14"/><path d="M9 10h6"/><path d="M9 16h6"/>',
 "redo": '<path d="M4 12a8 8 0 1 0 2.3-5.6"/><path d="M4 4v4h4"/>',
 "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
 "heart": '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
 "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
 "page": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6"/><path d="M9 12h6"/><path d="M9 16h4"/>',
 "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6"/><path d="M12 7.5v.5"/>',
 "pen": '<path d="M4 20l4-1 11-11-3-3L5 16z"/><path d="M14 6l3 3"/>',
 "tag": '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="8.5" r="1.3"/>',
}


def svg(name):
    return f'<svg viewBox="0 0 24 24" aria-hidden="true">{I[name]}</svg>'


def groups(latest_cal, latest_log):
    """(key, label, hub, [(title, desc, href, icon) | None for a rule])"""
    return [
        ("pub", "Publications", "/archive/", [
            ("The Calibration", "Our own measurements, pre-registered and signed", latest_cal, "gauge"),
            ("The Log", "What ran, what it cost, what moved", latest_log, "terminal"),
            ("The Bench", "What we read and argue with · Mon and Thu", "/writing/", "book"),
            ("Archive", "Every issue, by number and date", "/archive/", "archive"),
            None,
            ("Subscribe", "One email per issue", "/subscribe/", "mail"),
        ]),
        ("method", "Method", "/methodology/", [
            ("Methodology", "How a rate is produced", "/methodology/", "flask"),
            ("Definitions", "What each term means here", "/definitions/", "list"),
            ("The protocol, v1.25", "The instruction layer as measured", "/protocol/v1.25/", "proto"),
            ("Run files", "Every draw we can publish", "/data/runs/", "db"),
            ("figures.json", "Every citable number and its fingerprints", "/figures.json", "receipt"),
        ]),
        ("policy", "AI policy", "/docket/", [
            ("The Docket", "Rules that bear on how AI is tested", "/docket/", "scale"),
            ("The Chronicle", "Dated events in AI governance", "/chronicle/", "clock"),
            ("Super Intelligence (SI)", "The US rename of AI, traced", "/si/", "spark"),
            ("Militaries and AI", "Country by country", "/military/", "fence"),
        ]),
        ("trust", "Trust", "/independence/", [
            ("Independence", "Who pays, and the rules on it", "/independence/", "shield"),
            ("Corrections + changes", "What we got wrong, dated", "/corrections/", "redo"),
            ("AI Safety + Governance", "What our agents may and may not do", "/safety/", "eye"),
            ("Support", "How the program is paid for", "/support/", "heart"),
            None,
            ("Privacy", "What we keep, and for how long", "/privacy/", "lock"),
            ("Terms", "The terms of use", "/terms/", "page"),
        ]),
        ("about", "About", "/about/", [
            ("About Protocol STAMP", "What this is, who makes it, how to check it", "/about/", "info"),
            ("Colophon", "How the site is made, and the seven finishes", "/colophon/", "pen"),
            ("Other STAMPs", "Unrelated things with the same name", "/other-stamps/", "tag"),
        ]),
    ]


def section_of(rel):
    for key, pref in (("pub", ("archive/", "writing/", "bench/", "subscribe/")), ("method", ("methodology/", "definitions/", "data/")),
                      ("policy", ("docket/", "chronicle/", "si/", "military/")),
                      ("trust", ("independence/", "corrections/", "safety/", "support/", "privacy/", "terms/")),
                      ("about", ("about/", "colophon/", "other-stamps/"))):
        if rel.startswith(pref):
            return key
    return ""


CHEV = '<svg class="chev" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 3.5l3 3 3-3"/></svg>'
MARK = ('<svg viewBox="0 0 100 100" aria-hidden="true"><g stroke="currentColor" stroke-width="7" fill="none"><line x1="15" y1="50" x2="85" y2="50"/>'
        '<line x1="15" y1="31" x2="15" y2="69"/><line x1="85" y1="31" x2="85" y2="69"/></g>'
        '<line x1="38.11" y1="17" x2="38.11" y2="83" stroke="var(--stamp)" stroke-width="13"/></svg>')
SEARCH = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>'
BURGER = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>'


def header(rel, latest_cal, latest_log):
    here = section_of(rel)
    nav, drawer = [], []
    for key, label, hub, entries in groups(latest_cal, latest_log):
        cur = ' aria-current="true"' if key == here else ""
        links = "".join('<span class="sep"></span>' if e is None else
                        f'<a href="{e[2]}"><span class="i">{svg(e[3])}</span><b>{e[0]}</b><small>{e[1]}</small></a>' for e in entries)
        nav.append(f'<div class="sh-item"><a class="sh-top" href="{hub}"{cur}>{label}</a>'
                   f'<button class="sh-top sh-x" type="button" aria-expanded="false" aria-label="{label}: show pages" style="padding:0 6px;margin-left:-6px">{CHEV}</button>'
                   f'<div class="sh-panel" role="menu">{links}</div></div>')
        drawer.append(f'<h4>{label}</h4>' + "".join(f'<a href="{e[2]}">{e[0]}<small>{e[1]}</small></a>' for e in entries if e))
    return ('<!-- sh:start -->'
            f'<header class="sh"><div class="sh-in"><a class="sh-brand" href="/">{MARK}Protocol STAMP</a>'
            f'<nav class="sh-nav" aria-label="Site">{"".join(nav)}</nav>'
            f'<div class="sh-tools"><button class="sh-search" type="button" data-pal aria-label="Search pages">{SEARCH}<span>Search</span><kbd>Ctrl K</kbd></button>'
            f'<a class="sh-cta sh-hide-s" href="{latest_cal}">Latest Calibration</a>'
            f'<button class="sh-menu" type="button" aria-expanded="false" aria-controls="sh-drawer">{BURGER}<span class="lab" style="position:absolute;left:-9999px">Menu</span></button></div></div></header>'
            f'<div class="sh-drawer" id="sh-drawer"><button class="sh-search" type="button" data-pal style="width:100%;height:44px;margin-top:6px">{SEARCH}Search pages and issues</button>'
            f'{"".join(drawer)}<a class="sh-cta" href="{latest_cal}">Latest Calibration</a></div>'
            '<!-- sh:end -->')


NOTE = ('<!-- topband:start --><div class="sh-note"><b>New</b><a href="/si/">Super Intelligence (SI): the US rename of AI, traced</a>'
        ' &nbsp;·&nbsp; <a href="/military/">Militaries and AI, country by country</a></div><!-- topband:end -->')

# page search: every page a reader might look for, newest issue first. Pages that do not exist yet are skipped.
PALETTE = [
    ("Home", "/"), ("About", "/about/"), ("Archive of issues", "/archive/"),
    ("The Calibration Vol 004", "/calibration/004-issued-sat20261010/"),
    ("The Calibration Vol 003", "/calibration/003-issued-sat20261003/"),
    ("The Calibration Vol 002", "/calibration/002-issued-sat20261003/"),
    ("The Calibration Vol 001", "/calibration/001-issued-sun20260830/"),
    ("The Log Vol 003", "/log/003-issued-sat20261003/"),
    ("The Log Vol 002", "/log/002-issued-thu20261001/"),
    ("The Log Vol 001", "/log/001-issued-sat20260905/"),
    ("The Bench", "/writing/"),
    ("Bench Vol 006 · A Name Is Not a Test", "/bench/a-name-is-not-a-test/"),
    ("Bench Vol 005 · Judges Who Agree With Each Other", "/bench/judges-who-agree-with-each-other/"),
    ("Bench Vol 004 · What a New Judge Has to Beat", "/bench/what-a-new-judge-has-to-beat/"),
    ("Bench Vol 003 · Five Cases", "/bench/five-cases/"),
    ("Bench Vol 002 · Something It Can Check", "/bench/something-it-can-check/"),
    ("Bench Vol 001 · The No. 1 Complaint", "/bench/no-1-complaint/"),
    ("Essay · Stop marking it like a student", "/writing/marking/"),
    ("Essay · Why “I don’t know” can be a lie", "/writing/abstention/"),
    ("The Docket", "/docket/"), ("The Chronicle", "/chronicle/"),
    ("Super Intelligence (SI)", "/si/"), ("Militaries and AI", "/military/"),
    ("Methodology", "/methodology/"), ("Definitions", "/definitions/"), ("The protocol, v1.25", "/protocol/v1.25/"),
    ("Run files", "/data/runs/"), ("figures.json, the registry", "/figures.json"),
    ("Independence", "/independence/"), ("Corrections + changes", "/corrections/"),
    ("AI Safety + Governance", "/safety/"), ("Support", "/support/"),
    ("Colophon", "/colophon/"), ("Subscribe", "/subscribe/"), ("Other STAMPs", "/other-stamps/"),
    ("Privacy", "/privacy/"), ("Terms", "/terms/"), ("RSS feed", "/feed.xml"),
]


def exists(href):
    p = DOCS / href.strip("/")
    return href == "/" or (p / "index.html").exists() or p.exists()


def palette_js():
    import json
    return "var P=" + json.dumps([[t, h] for t, h in PALETTE if exists(h)]) + ";"


PAL_BLOCK = ('<div class="pal" role="dialog" aria-label="Search pages"><div class="pal-box"><input type="text" placeholder="Search pages and issues" '
             'aria-label="Search pages and issues"><ul></ul></div></div>')
ASSETS = '<link rel="stylesheet" href="/site.css"><script src="/site.js" defer></script>'


def latest(kind):
    s = (DOCS / "index.html").read_text(encoding="utf-8")
    if kind == "calibration":
        m = re.search(r'href="(/calibration/[^"]+/)"[^>]*>(?:<[^>]+>)*\s*Latest Calibration', s)
        return m.group(1) if m else "/archive/"
    live = sorted(p.parent.name for p in (DOCS / "log").glob("*/index.html"))
    return f"/log/{live[-1]}/" if live else "/archive/"


def owned(rel, s):
    if rel.startswith(FROZEN):
        return None
    if re.search(r'<body class="rd\b', s):
        return "standing"
    if rel.startswith(POSTS):
        return "post"
    return None


def apply(rel, s, kind, cal, log, pal_src):
    s0 = s
    hdr = header(rel, cal, log)
    if "<!-- sh:start -->" in s:
        s = re.sub(r"<!-- sh:start -->.*?<!-- sh:end -->", lambda m: hdr, s, count=1, flags=re.S)
    elif '<header class="bar">' in s:
        s = re.sub(r'<header class="bar">.*?</header>', lambda m: hdr, s, count=1, flags=re.S)
    else:                                               # a Bench post: straight after <body>
        s = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + "\n" + hdr, s, count=1)
    # body classes
    want = ["has-sh"] + (["sh-post"] if kind == "post" else [])
    def body(m):
        cls = (m.group(1) or "").split()
        cls += [w for w in want if w not in cls]
        return f'<body class="{" ".join(cls)}"{m.group(2)}>'
    s = re.sub(r'<body(?: class="([^"]*)")?([^>]*)>', body, s, count=1)
    # the announcement strip, standing pages only
    if kind == "standing":
        if "<!-- topband:start -->" in s:
            s = re.sub(r"<!-- topband:start -->.*?<!-- topband:end -->", lambda m: NOTE, s, count=1, flags=re.S)
        else:
            s = s.replace("<!-- sh:end -->", "<!-- sh:end -->\n" + NOTE, 1)
    # page search: posts had none
    if 'class="pal"' not in s:
        s = s.replace("<!-- sh:end -->", "<!-- sh:end -->\n" + PAL_BLOCK + pal_src, 1)
    s = re.sub(r"var P=\[.*?\];", lambda m: palette_js(), s, count=1, flags=re.S)
    # assets, once, after redesign.css when a page has it (site.css must win over it)
    if 'href="/site.css"' not in s:
        if '<link rel="stylesheet" href="/redesign.css">' in s:
            s = s.replace('<link rel="stylesheet" href="/redesign.css">', '<link rel="stylesheet" href="/redesign.css">' + ASSETS, 1)
        else:
            s = s.replace("<!-- sh:end -->", "<!-- sh:end -->" + ASSETS, 1)
    # the footer's "Public bank" is the current public half
    s = s.replace('<a href="/data/bank_v1_public.jsonl">Public bank</a>', '<a href="/data/bank_v1_1_public.jsonl">Public bank</a>')
    return s, s != s0


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--check", action="store_true")
    ap.add_argument("--skip", default="", help="comma-separated page prefixes to leave alone, e.g. docket/,chronicle/")
    a = ap.parse_args()
    skip = tuple(x for x in a.skip.split(",") if x)
    home = (DOCS / "index.html").read_text(encoding="utf-8")
    m = re.search(r'(<script>\(function\(\)\{var P=\[.*?</script>)', home, re.S)
    pal_src = m.group(1) if m else ""
    cal, log = latest("calibration"), latest("log")
    changed = 0
    for p in sorted(DOCS.rglob("index.html")):
        rel = p.relative_to(DOCS).as_posix()
        b = p.read_bytes(); s = b.decode("utf-8")
        kind = owned(rel, s)
        if not kind or (skip and rel.startswith(skip)):
            continue
        s2, ch = apply(rel, s, kind, cal, log, pal_src)
        if ch:
            changed += 1
            print(("would change  " if a.check else "changed  ") + f"{kind:8} {rel}")
            if not a.check:
                p.write_bytes(s2.encode("utf-8"))      # bytes in, bytes out: no line-ending rewrite
    print(f"{changed} page(s) {'would change' if a.check else 'changed'}; Latest Calibration = {cal}; latest Log = {log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
