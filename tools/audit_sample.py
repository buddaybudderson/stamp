#!/usr/bin/env python3
"""
THE SATURDAY AUDIT (R4). Draws 30 published claims at random, by a recorded seed, for both reviewers and then
the person to check again; counts what they found; and gives the 95% upper bound on the error rate.

    python tools/audit_sample.py draw DOCS OUT_DIR --date YYYY-MM-DD [--seed S] [--n 30]
        write OUT_DIR/draw.json (seed, population, the claims drawn) and OUT_DIR/worksheet.json
    python tools/audit_sample.py verify OUT_DIR [--docs DOCS]
        draw again from the recorded population and seed; refuse if a claim was swapped, added or dropped
    python tools/audit_sample.py tally OUT_DIR [OUT_DIR ...]
        refuse unless every claim has two reviewers' verdicts and the person's; print checked, errors, bound
    python tools/audit_sample.py log-table OUT_DIR [OUT_DIR ...]
        the table for The Log (HTML), one row per Saturday and the running count since the last error

What counts as a published claim: every Docket and Chronicle entry (docs/docket/docket.json and
docs/chronicle/chronicle.json), and every passage on every other page (a paragraph, list item or table
cell) that carries a source link or a citation marker. Issued pages are read from their frozen bytes. The
archived protocol and Corrections + changes are left out: the first is history, the second is the record
of errors itself. Each claim's id is its page and a fingerprint of its words, so the same claim keeps the same id.

The seed is recorded before the draw and defaults to "stamp-audit-YYYY-MM-DD". The whole population (ids
and fingerprint) is kept with the draw, so anyone can draw again and get the same 30.

The bound: one-sided 95% (Clopper-Pearson). With no errors in n it is 1 - 0.05^(1/n), about 3/n, the
"rule of three": 9.5% for 30 claims, about 1% for 300. Every error found restarts the running count (R4).

Stdlib only. No network. Written Oct 20, 2026; the first Saturday due was Oct 17, 2026, and it did not run.
"""
import datetime as dt, hashlib, html, json, pathlib, random, re, sys

N = 30
PERSONS = ("Lawrence Ho",)        # the person named on the About page who signs (Protocol 10)
SKIP = ("protocol/", "corrections/", "docket/", "chronicle/")
VERDICTS = ("ok", "error")


class Refused(Exception):
    pass


def _visible(s):
    s = re.sub(r"<(script|style|svg)\b.*?</\1>", " ", s, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _own(s):
    for a, b in (("<!-- sh:start -->", "<!-- sh:end -->"), ("<!-- topband:start -->", "<!-- topband:end -->"),
                 ("<!-- sf:start -->", "<!-- sf:end -->"), ("<!-- sai:start -->", "<!-- sai:end -->"),
                 ("<!-- sx:start -->", "<!-- sx:end -->")):
        s = re.sub(re.escape(a) + ".*?" + re.escape(b), " ", s, flags=re.S)
    return re.sub(r"<(header|nav|footer)\b.*?</\1>", " ", s, flags=re.S | re.I)


def _fp(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def population(docs):
    """Every published claim, sorted by id: [{"id", "page", "text", "sources"}]."""
    docs = pathlib.Path(docs)
    out = {}
    for kind in ("docket", "chronicle"):
        f = docs / kind / f"{kind}.json"
        if f.exists():
            for e in json.loads(f.read_text(encoding="utf-8"))["entries"]:
                out[f"{kind}/#{e['id']}"] = {"id": f"{kind}/#{e['id']}", "page": f"/{kind}/#{e['id']}",
                                             "text": f"{e['title']}. {e['summary']}", "sources": [s["url"] for s in e.get("sources", [])]}
    for p in sorted(docs.rglob("index.html")):
        rel = p.relative_to(docs).as_posix()
        if rel.startswith(SKIP):
            continue
        raw = p.read_text(encoding="utf-8", errors="replace")
        src = p.parent / "source.html"
        if src.exists():
            raw = src.read_text(encoding="utf-8", errors="replace")     # an issue: its frozen bytes
        for _, inner in re.findall(r"<(p|li|td)\b[^>]*>(.*?)</\1>", _own(raw), flags=re.S):
            if not re.search(r'href="#(?:r|m|ref)\d+|class="src"|<sup|<a href="https?://', inner):
                continue
            text = _visible(inner)
            if len(text) < 20:
                continue
            page = "/" + rel[:-len("index.html")]
            cid = f"{page.strip('/') or 'home'}/#{_fp(text)}"
            out.setdefault(cid, {"id": cid, "page": page, "text": text[:1200],
                                 "sources": re.findall(r'href="(https?://[^"]+|#(?:r|m|ref)\d+)"', inner)})
    return [out[k] for k in sorted(out)]


def fingerprint(ids):
    return hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()


def pick(ids, seed, n):
    if len(ids) < n:
        raise Refused(f"only {len(ids)} claims in the population; {n} are needed")
    return sorted(random.Random(seed).sample(sorted(ids), n))


def draw(docs, out, date, seed=None, n=N):
    out = pathlib.Path(out)
    if (out / "draw.json").exists():
        raise Refused(f"{out / 'draw.json'} exists: a draw is made once, and never made again until it suits")
    seed = seed or f"stamp-audit-{date.isoformat()}"
    pop = population(docs)
    if not pop:
        raise Refused("no published claims found; nothing would be checked")
    ids = [c["id"] for c in pop]
    chosen = pick(ids, seed, n)
    byid = {c["id"]: c for c in pop}
    try:   # the site's commit, so the population can be rebuilt from the same bytes
        import subprocess
        commit = subprocess.run(["git", "-C", str(docs), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or None
    except OSError:
        commit = None
    rec = {"date": date.isoformat(), "drawn_on": dt.date.today().isoformat(), "seed": seed, "n": n, "site_commit": commit,
           "population_size": len(ids),
           "population_sha256": fingerprint(ids), "population": ids, "drawn": [byid[i] for i in chosen]}
    blank = lambda: {"model": "", "opened": None, "verdict": "", "note": ""}
    sheet = {"date": date.isoformat(), "seed": seed, "claims": [
        {"id": i, "page": byid[i]["page"], "reviewer_1": blank(), "reviewer_2": blank(),
         "person": {"name": "", "verdict": "", "note": "", "date": ""}} for i in chosen]}
    out.mkdir(parents=True, exist_ok=True)
    (out / "draw.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "worksheet.json").write_text(json.dumps(sheet, indent=1, ensure_ascii=False), encoding="utf-8")
    return rec


def _load(out):
    out = pathlib.Path(out)
    try:
        return (json.loads((out / "draw.json").read_text(encoding="utf-8")),
                json.loads((out / "worksheet.json").read_text(encoding="utf-8")))
    except FileNotFoundError as ex:
        raise Refused(f"{ex.filename} is missing")


def verify(out, docs=None):
    """The draw is the one the seed gives, and the worksheet checks exactly those claims."""
    rec, sheet = _load(out)
    if fingerprint(rec["population"]) != rec["population_sha256"]:
        raise Refused("the recorded population does not match its own fingerprint: it was edited after the draw")
    if len(rec["population"]) != rec["population_size"]:
        raise Refused("the recorded population size does not match the list")
    want = pick(rec["population"], rec["seed"], rec["n"])
    got = [c["id"] for c in rec["drawn"]]
    if got != want:
        swapped = sorted(set(got) ^ set(want))
        raise Refused(f"the claims drawn are not the ones seed {rec['seed']!r} gives: {len(swapped)} differ, first {swapped[0] if swapped else '(order)'}")
    if sorted(c["id"] for c in sheet["claims"]) != want or sheet.get("seed") != rec["seed"]:
        raise Refused("the worksheet does not check the claims that were drawn")
    if docs is not None:
        now = {c["id"] for c in population(docs)}
        gone = [i for i in want if i not in now]
        if gone:
            print(f"note: {len(gone)} drawn claim(s) have changed or left the site since the draw, first {gone[0]}")
    return rec


def upper95(k, n):
    """One-sided 95% Clopper-Pearson upper bound on the error rate, k errors in n."""
    if n <= 0:
        raise Refused("nothing checked: no bound")
    if k >= n:
        return 1.0
    from math import comb
    cdf = lambda p: sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))
    lo, hi = k / n, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if cdf(mid) > 0.05 else (lo, mid)
    return hi


def checked(out):
    """(date, n, errors, [error ids]) for one Saturday; refuses an unfinished or ill-kept worksheet."""
    rec = verify(out)
    _, sheet = _load(out)
    errors = []
    for c in sheet["claims"]:
        r1, r2, pe = c.get("reviewer_1") or {}, c.get("reviewer_2") or {}, c.get("person") or {}
        for k, r in (("reviewer_1", r1), ("reviewer_2", r2)):
            if not r.get("model"):
                raise Refused(f"{c['id']}: {k} has no model")
            if r.get("opened") is not True:
                raise Refused(f"{c['id']}: {k} ({r['model']}) did not open the source; a re-check without the source checks nothing")
            if r.get("verdict") not in VERDICTS:
                raise Refused(f"{c['id']}: {k} has no verdict (ok or error)")
        if r1["model"] == r2["model"]:
            raise Refused(f"{c['id']}: both reviewers are {r1['model']}; they must be two")
        if pe.get("name") not in PERSONS:
            raise Refused(f"{c['id']}: the person's check is missing (name must be one of {', '.join(PERSONS)})")
        if pe.get("verdict") not in VERDICTS:
            raise Refused(f"{c['id']}: the person has no verdict")
        try:
            dt.date.fromisoformat(pe.get("date"))
        except (TypeError, ValueError):
            raise Refused(f"{c['id']}: the person's check has no date")
        if pe["verdict"] == "ok" and "error" in (r1["verdict"], r2["verdict"]) and not pe.get("note", "").strip():
            raise Refused(f"{c['id']}: a reviewer found an error and the person overruled it without a note")
        if pe["verdict"] == "error":
            errors.append(c["id"])
    return dt.date.fromisoformat(rec["date"]), len(sheet["claims"]), len(errors), errors


def tally(outs):
    rows = sorted(checked(o) for o in outs)
    run_n = 0
    table = []
    for d, n, k, errs in rows:
        run_n = 0 if k else run_n + n          # an error restarts the count (R4)
        table.append({"date": d, "n": n, "errors": k, "error_ids": errs, "bound": upper95(k, n),
                      "since_error": run_n, "since_error_bound": upper95(0, run_n) if run_n else None})
    return table


def hd(d):
    return d.strftime("%b %d, %Y")


def pct(x):
    return f"{x * 100:.1f}%"


def log_table(outs):
    t = tally(outs)
    rows = "".join(
        f"<tr><td>{hd(r['date'])}</td><td>{r['n']}</td><td>{r['errors']}</td><td>{pct(r['bound'])}</td>"
        f"<td>{r['since_error'] or 'restarted'}</td><td>{pct(r['since_error_bound']) if r['since_error_bound'] else '-'}</td></tr>"
        for r in t)
    return ('<table class="audit"><tr><th>Saturday</th><th>Claims checked</th><th>Errors found</th>'
            '<th>95% upper bound on the error rate</th><th>Claims checked since the last error</th><th>Its 95% upper bound</th></tr>'
            + rows + "</table>")


def main(argv):
    def opt(name, default=None):
        if name in argv:
            i = argv.index(name)
            v = argv[i + 1]
            del argv[i:i + 2]
            return v
        return default
    try:
        cmd = argv.pop(0) if argv else ""
        if cmd == "draw":
            date, seed, n = opt("--date"), opt("--seed"), int(opt("--n", N))
            if not date or len(argv) != 2:
                raise Refused("usage: draw DOCS OUT_DIR --date YYYY-MM-DD [--seed S] [--n 30]")
            rec = draw(argv[0], argv[1], dt.date.fromisoformat(date), seed, n)
            print(f"drew {rec['n']} of {rec['population_size']} claims, seed {rec['seed']!r}, population {rec['population_sha256'][:16]}")
            for c in rec["drawn"]:
                print(f"  {c['id']}")
        elif cmd == "verify":
            docs = opt("--docs")
            rec = verify(argv[0], docs)
            print(f"verified: the {rec['n']} claims are the ones seed {rec['seed']!r} draws from {rec['population_size']}")
        elif cmd == "tally":
            for r in tally(argv):
                print(f"{hd(r['date'])}: {r['n']} checked, {r['errors']} error(s), 95% upper bound {pct(r['bound'])}; "
                      f"{r['since_error']} since the last error" + (f", bound {pct(r['since_error_bound'])}" if r["since_error_bound"] else ""))
        elif cmd == "log-table":
            print(log_table(argv))
        else:
            sys.exit(__doc__.split("\n\n")[1])
    except Refused as ex:
        print(f"REFUSED - {ex}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
