#!/usr/bin/env python3
"""
RELEASE AN ISSUE INTO docs/ FROM stage/. Stdlib only. Run by the release workflow at
15:37 America/Chicago on a Saturday, or by hand:

    python tools/wrap_issue.py                 release everything found in stage/
    python tools/wrap_issue.py --check         say what would be released, write nothing

WHAT IT EXPECTS IN stage/:
    stage/<kind>/<slug>.html      the issue, byte-frozen (kind = calibration | log)
    stage/<kind>/<slug>.pdf       its PDF
where slug looks like  log-001-issued-sat20260905 . The weekday token in the slug must
match the date, or nothing is released (issue_name.py's rule, repeated here because
this file runs where issue_name.py does not).

WHAT IT WRITES:
    docs/<kind>/<slug-without-kind>/source.html   the frozen bytes, verbatim
    docs/<kind>/<slug-without-kind>/index.html    the same bytes wrapped in the site shell,
                                                  pinned to the finish of its issue weekday
    docs/<kind>/<slug-without-kind>.pdf
and it flips the matching "pending" row on the home page and the archive to a live row.
The frozen bytes are never modified: the wrapper is head + bytes + foot, and the script
refuses to finish if the bytes it wrote back do not hash to the bytes it read.

WHY THE GATES ARE NOT HERE. holdout_gate.py needs the private bank; check_pdf.py and
figures.py need the registry. Those run on the harness BEFORE a file is staged. This
script's only gates are the ones it can verify without secrets: the weekday in the name,
the presence of both files, and the hash round-trip.
"""
import argparse, datetime as dt, hashlib, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
STAGE, DOCS = ROOT / "stage", ROOT / "docs"
KINDS = {"calibration": "The Calibration", "log": "The Log"}
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
FINISH = {"mon": "moon", "tue": "mars", "wed": "mercury", "thu": "jupiter",
          "fri": "venus", "sat": "saturn", "sun": "sun"}
SLUG_RE = re.compile(r"^(calibration|log)-(\d{3})-issued-([a-z]{3})(\d{8})$")

# THE DATELINE MOVES. A dateline names where the work was done, and this programme is run from
# wherever its investigator happens to be that Saturday. Write the place into
#     stage/<kind>/<slug>.dateline
# as a single line -- "City, Region, Country" -- before staging. The release workflow runs on GitHub's
# servers and cannot know where you are, so a missing file falls back to HOME and says so loudly.
DATELINE_HOME = "Houston, Texas, USA"


def sha(b): return hashlib.sha256(b).hexdigest()


def display(kind, no, date):
    return f"{KINDS[kind]} Vol {no:03d} · {DAYS[date.weekday()].title()}{date:%Y%m%d}"


def shell(title, desc, canon, pin, frag, pdf_href, src_href, pages_note, year, dateline, date):
    head = f'''<!doctype html>
<html lang="en" data-pin="{pin}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{desc}">
<link rel="canonical" href="{canon}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="The STAMP Protocol">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canon}">
<meta property="og:image" content="https://thestampprotocol.com/og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="stylesheet" href="/finish.css">
<script src="/finish.js"></script>
</head>
<body>
<nav style="max-width:820px;margin:0 auto;padding:18px 20px 0;font:500 11.5px/1 'IBM Plex Mono',ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase"><a href="/" style="color:var(--stamp);text-decoration:none">&larr; The STAMP Protocol</a> &nbsp;·&nbsp; <a href="/archive/" style="color:var(--stamp);text-decoration:none">Archive</a></nav>
'''.encode()
    foot = f'''<p style="max-width:820px;margin:28px auto 40px;padding:0 20px;font:400 11.5px/1.7 'IBM Plex Mono',ui-monospace,monospace;color:var(--ink-3)">Source of this page, byte-exact: <a href="{src_href}" style="color:var(--stamp)">{src_href.rsplit('/',2)[-2]}/source</a> &middot; sha256 {sha(frag)[:12]}&hellip; &middot; {len(frag):,} bytes &middot; <a href="{pdf_href}" style="color:var(--stamp)">PDF{pages_note}</a></p>
<p style="max-width:820px;margin:-24px auto 40px;padding:0 20px;font:400 11.5px/1.7 'IBM Plex Mono',ui-monospace,monospace;color:var(--ink-3)">Issued from {dateline} at 15:37 America/Chicago on {date:%A %-d %B %Y}. The dateline names where the work was done; it moves with the investigator, and each issue keeps its own.</p>
<p style="max-width:820px;margin:-24px auto 40px;padding:0 20px;font:400 11.5px/1.7 'IBM Plex Mono',ui-monospace,monospace;color:var(--ink-3)">To cite: The STAMP Protocol. <i>{title}</i>. Budday Budderson Studio LLC, {year}. {canon} &middot; build {sha(frag)[:12]}. See <a href="/definitions/#cite" style="color:var(--stamp)">Definitions</a> for the form.</p>
</body>
</html>
'''.encode()
    return head + frag + foot


def flip_rows(html, name, links_html, meta_html):
    """Turn the pending row for this issue into a live row. Pending rows carry the short
    name ("The Log Vol 001"); the live row gets the full display name with its date.
    Works on both the home page (multi-line row) and the archive (single-line row)."""
    short_name = name.split(" · ")[0]
    pat = re.compile(r'<div class="issue pending">\s*<span class="name">' + re.escape(short_name) +
                     r'(?: · [A-Za-z]{3}\d{8})?</span>\s*<span class="links due">[^<]*</span>\s*<span class="meta">[^<]*</span>\s*</div>')
    new = (f'<div class="issue">\n    <span class="name">{name}</span>\n    <span class="links">{links_html}</span>\n'
           f'    <span class="meta">{meta_html}</span>\n  </div>')
    out, n = pat.subn(new, html)
    return out, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    found = sorted(STAGE.glob("*/*.html"))
    if not found:
        print("stage/ is empty - nothing to release"); return 0
    released = 0
    for html in found:
        slug = html.stem
        m = SLUG_RE.match(slug)
        if not m:
            print(f"REFUSED {slug}: not a well-formed issue name"); return 1
        kind, no, day, ymd = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        date = dt.datetime.strptime(ymd, "%Y%m%d").date()
        if DAYS[date.weekday()] != day:
            print(f"REFUSED {slug}: {ymd} is a {DAYS[date.weekday()].upper()} but the name says {day.upper()}"); return 1
        pdf = html.with_suffix(".pdf")
        if not pdf.exists():
            print(f"REFUSED {slug}: no PDF beside it"); return 1
        dl_file = html.with_suffix(".dateline")
        if dl_file.exists():
            dateline = dl_file.read_text(encoding="utf-8").strip()
            if not dateline:
                print(f"REFUSED {slug}: {dl_file.name} is empty. Write the place, or delete the file to use {DATELINE_HOME}."); return 1
        else:
            dateline = DATELINE_HOME
            print(f"  NOTE  no {dl_file.name}; using the home dateline {DATELINE_HOME}")
        frag = html.read_bytes()
        short = slug[len(kind) + 1:]                      # 001-issued-sat20260905
        name = display(kind, no, date)
        print(f"{'would release' if a.check else 'releasing'}  {name}   {slug}  sha {sha(frag)[:12]}  {len(frag):,} bytes")
        print(f"        dateline: {dateline}")
        if a.check:
            continue
        out = DOCS / kind / short; out.mkdir(parents=True, exist_ok=True)
        (out / "source.html").write_bytes(frag)
        (DOCS / kind / f"{short}.pdf").write_bytes(pdf.read_bytes())
        canon = f"https://thestampprotocol.com/{kind}/{short}/"
        desc = {"log": "What ran, what it cost and what moved - the derived record, written by the harness.",
                "calibration": "The dated record of what was measured, written and signed by a person."}[kind]
        title = name
        pin = FINISH[day]
        wrapped = shell(title, desc, canon, pin, frag, f"/{kind}/{short}.pdf", f"/{kind}/{short}/source", "", date.year, dateline, date)
        (out / "index.html").write_bytes(wrapped)
        assert frag in (out / "index.html").read_bytes() and sha((out / "source.html").read_bytes()) == sha(frag)
        # flip the pending rows
        links = f'<a href="/{kind}/{short}/">Read</a> · <a href="/{kind}/{short}.pdf">PDF</a> · <a href="/{kind}/{short}/source">Source</a>'
        meta = f"Issued {date:%a %-d %B %Y} from {dateline.split(',')[0].strip()} · build {sha(frag)[:12]}"
        for page in ("index.html", "archive/index.html"):
            p = DOCS / page; s = p.read_text(encoding="utf-8")
            s2, n = flip_rows(s, name, links, meta)
            if n == 0:
                print(f"  note: no pending row named '{name}' on {page}; leaving it unchanged")
            p.write_text(s2, encoding="utf-8")
        # sitemap
        sm = DOCS / "sitemap.xml"; t = sm.read_text(encoding="utf-8")
        if canon not in t:
            t = t.replace("</urlset>", f"<url><loc>{canon}</loc><lastmod>{date.isoformat()}</lastmod></url>\n</urlset>")
            sm.write_text(t, encoding="utf-8")
        # RSS: one item at the top of the channel
        fx = DOCS / "feed.xml"
        if fx.exists():
            f = fx.read_text(encoding="utf-8")
            if canon not in f:
                pub = dt.datetime.combine(date, dt.time(15, 37)).strftime("%a, %d %b %Y %H:%M:%S -0500")
                esc = lambda x: x.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                item = (f"<item>\n<title>{esc(name)}</title>\n<link>{canon}</link>\n<guid isPermaLink=\"true\">{canon}</guid>\n"
                        f"<pubDate>{pub}</pubDate>\n<description>{esc(desc)} Build {sha(frag)[:12]}.</description>\n</item>\n")
                f = re.sub(r"<lastBuildDate>[^<]*</lastBuildDate>", f"<lastBuildDate>{pub}</lastBuildDate>", f, count=1)
                f = f.replace("<item>", item + "<item>", 1) if "<item>" in f else f.replace("</channel>", item + "</channel>", 1)
                fx.write_text(f, encoding="utf-8")
        html.unlink(); pdf.unlink()
        if dl_file.exists(): dl_file.unlink()
        released += 1
    print(f"{released} issue(s) released" if not a.check else "check only, nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
