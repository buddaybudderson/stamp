#!/usr/bin/env python3
"""
WHAT SEARCH ENGINES READ, ONE SOURCE. Stdlib only. Run from the repo root, after tools/site_chrome.py:

    python tools/seo.py            write the structured data, page titles and sitemap
    python tools/seo.py --check    say what would change, write nothing

It owns:
  - the structured data on every page (between <!-- ld:start --> and <!-- ld:end -->): the site and its
    publisher on the home page, an Article on every issue and Bench post, a WebPage everywhere else;
  - the site's name at the end of every page title it is allowed to change (" · Protocol STAMP");
  - docs/sitemap.xml: every page listed once, the home page dated by the newest entry.
It never edits an issued document: on an issue page the structured data goes outside the frozen bytes,
and the title, which is part of those bytes, stays as issued. The archived protocol page keeps its title.
A date, once written, is kept: an issue is dated by its slug, any other page by the day git first saw it,
and after that by what its structured data already says. Running it twice changes nothing the second time.
"""
import argparse, datetime as dt, html, json, pathlib, re, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import house

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
SITE = "https://protocolstamp.com"
NAME = "Protocol STAMP"
SUFFIX = f" · {NAME}"

ISSUE = re.compile(r"^(?:calibration|log)/([0-9]{3})-issued-[a-z]{3}([0-9]{8})/index\.html$")
FROZEN_BYTES = ("bench/no-1-complaint/index.html",)     # an issued document under a post's address
KEEP_TITLE = ("protocol/",)                              # the archived v1.25 page keeps its own design
ARTICLE = ("bench/", "writing/marking/", "writing/abstention/", "calibration/", "log/")

PUBLISHER = {"@type": "Organization", "name": NAME, "url": f"{SITE}/",
             "logo": {"@type": "ImageObject", "url": f"{SITE}/apple-touch-icon.png"},
             "parentOrganization": {"@type": "Organization", "name": house.COMPANY}}


def git_added(p):
    try:
        out = subprocess.run(["git", "log", "--diff-filter=A", "--follow", "--format=%as", "--", str(p)],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        return out[-1] if out else None
    except (OSError, subprocess.CalledProcessError):
        return None


def meta(s, attr, key):
    m = re.search(rf'<meta {attr}="{re.escape(key)}" content="([^"]*)"', s)
    return html.unescape(m.group(1)) if m else None


def frozen(rel, p):
    """The issued bytes this page must keep exactly, or None."""
    if ISSUE.match(rel) or rel in FROZEN_BYTES:
        src = p.parent / "source.html"
        return src.read_text(encoding="utf-8") if src.exists() else None
    return None


def published(rel, s, p):
    m = ISSUE.match(rel)
    if m:
        d = m.group(2); return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    old = re.search(r'"datePublished":\s*"([0-9-]{10})"', s)
    return old.group(1) if old else git_added(p)


def data(rel, s, p, title):
    url = f"{SITE}/{rel[: -len('index.html')]}"
    desc = meta(s, "name", "description")
    if rel == "index.html":
        g = [{"@type": "WebSite", "name": NAME, "url": url, "description": desc, "publisher": PUBLISHER}, PUBLISHER]
        return {"@context": "https://schema.org", "@graph": g}
    head = (meta(s, "property", "og:title") or title).removesuffix(SUFFIX)
    if rel.startswith(ARTICLE):
        d = {"@context": "https://schema.org", "@type": "Article", "headline": head, "url": url,
             "mainEntityOfPage": url, "image": f"{SITE}/og.png", "author": PUBLISHER, "publisher": PUBLISHER,
             "isPartOf": {"@type": "WebSite", "name": NAME, "url": f"{SITE}/"}}
        when = published(rel, s, p)
        if when: d["datePublished"] = when
    else:
        d = {"@context": "https://schema.org", "@type": "WebPage", "name": head, "url": url,
             "isPartOf": {"@type": "WebSite", "name": NAME, "url": f"{SITE}/"}, "publisher": PUBLISHER}
    if desc: d["description"] = desc
    return d


def block(d):
    j = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<!-- ld:start --><script type="application/ld+json">{j}</script><!-- ld:end -->'


def apply(rel, s, p):
    issued = frozen(rel, p) is not None or rel in FROZEN_BYTES
    frag = frozen(rel, p)
    frag = frag if frag and frag in s else None            # enforce containment only where it holds today
    t = re.search(r"<title>(.*?)</title>", s, re.S)
    title = html.unescape(t.group(1).strip()) if t else ""
    # the site's name in the title, where the title is the site's to change
    if t and not issued and rel != "index.html" and not rel.startswith(KEEP_TITLE) and NAME not in title:
        s = s[: t.end(1)] + SUFFIX + s[t.end(1):]
    before = s                                             # read the date written so far, before its block goes
    s = re.sub(r"\n?<!-- ld:start -->.*?<!-- ld:end -->", "", s, count=1, flags=re.S)
    ld = block(data(rel, before, p, title))
    cut = s.index(frag) if frag and frag in s else len(s)
    i = s.find("</head>", 0, cut)
    if i < 0: i = cut                                      # the issue carries the only head: put it just before
    s = s[:i] + ld + "\n" + s[i:]
    if frag and frag not in s:
        sys.exit(f"REFUSED {rel}: the issued bytes would no longer be contained exactly")
    return s, published(rel, before, p)


def sitemap(pages):
    sm = DOCS / "sitemap.xml"; t = sm.read_text(encoding="utf-8")
    have = dict(re.findall(r"<url><loc>([^<]+)</loc><lastmod>([^<]+)</lastmod></url>", t))
    rows = {}
    for rel, when in pages:
        url = f"{SITE}/{rel[: -len('index.html')]}"
        rows[url] = have.get(url) or when or dt.date.today().isoformat()
    for url, when in have.items():                         # an entry for a page that is not an index.html stays
        rows.setdefault(url, when)
    home = f"{SITE}/"; rows[home] = max(rows.values())
    order = [home] + [u for u in have if u != home and u in rows] + sorted(u for u in rows if u not in have and u != home)
    body = "".join(f"<url><loc>{u}</loc><lastmod>{rows[u]}</lastmod></url>\n" for u in order)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + body + "</urlset>\n")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--check", action="store_true"); a = ap.parse_args()
    changed, pages = 0, []
    for p in sorted(DOCS.rglob("index.html")):
        rel = p.relative_to(DOCS).as_posix()
        s = p.read_bytes().decode("utf-8")
        if re.search(r'<meta name="robots" content="[^"]*noindex', s):
            continue
        s2, when = apply(rel, s, p)
        pages.append((rel, when))
        if s2 != s:
            changed += 1
            print(("would change  " if a.check else "changed  ") + rel)
            if not a.check: p.write_bytes(s2.encode("utf-8"))
    sm = DOCS / "sitemap.xml"; new = sitemap(pages)
    if new != sm.read_text(encoding="utf-8"):
        changed += 1
        print(("would change  " if a.check else "changed  ") + "sitemap.xml")
        if not a.check: sm.write_text(new, encoding="utf-8", newline="\n")  # LF on every OS, as committed
    print(f"{changed} file(s) {'would change' if a.check else 'changed'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
