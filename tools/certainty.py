#!/usr/bin/env python3
"""
THE CERTAINTY SCORE (Protocol 4, with R1, R8 and R9). How sure we are, as a number computed from what was checked.

    python tools/certainty.py claims.jsonl [--as-of YYYY-MM-DD] [--json]
        score every claim that carries an `evidence` record; exit 1 if any record is refused
    python tools/certainty.py --docket entries.jsonl retrieval_log.jsonl [--archive MANIFEST.jsonl] [--as-of YYYY-MM-DD] [--json]
        score Docket or Chronicle entries from what their own records show (legacy claims, R3); the source
        archive's manifest (site_audit/archive_sources.py) supplies the hashed-copy row

The score is never a model's or a writer's feeling: a model's stated confidence is a claim about
itself. Every point below comes from a field someone recorded. A field that was not recorded earns
nothing; a field that is malformed refuses the claim, and a refused claim is unscored, never guessed.

  50  primary     the issuer's own document opened, and the figure, date or quote FOUND in it
  15  second      a second, independent source agrees (R1: its own reporting, not a copy or rewrite)
  10  archived    our own archived copy, hashed (Protocol 1): a SHA-256 is recorded
  10  fresh       checked within the last 30 days
  15  reviewers   both independent reviewers opened the source themselves and agree, nothing
                  unresolved (Protocol 10); agreeing without opening earns nothing (R1)
 +10  further     rung C only: each independent source beyond the second, up to 40 (R9)

  cap 75  no primary source opened          cap 40  two credible sources disagree, unresolved
  cap 20  no source could be opened at all   rung D (memory only): refused, nothing is published
  100 (Certain) only when every row is met and the claim is a fact of record (R8); a forecast,
  an estimate, a count still changing or an opinion stops at 99.

Evidence record (one JSON object per claim, under "evidence"):
  {"rung": "A"|"B"|"C",
   "primary": {"url": ..., "opened": "YYYY-MM-DD", "found": "the words found"} | null,
   "sources": [{"url": ..., "opened": "YYYY-MM-DD"}, ...],   independent sources that agree, the first one included
   "archived": {"sha256": "<64 hex>"} | null,
   "checked": "YYYY-MM-DD",
   "reviewers": [{"model": ..., "opened": true, "agrees": true}, ...],
   "conflict_unresolved": false,
   "kind": "fact" | "forecast" | "estimate" | "count" | "opinion"}

Stdlib only. No network. Written Oct 20, 2026; the order of work (step 5) runs it after the gates.
"""
import datetime as dt, json, pathlib, re, sys

# Bands follow ICD 203, as amended (Jun 12, 2023), D.6.e(2); 100% is ours (R8). (low, high, word)
BANDS = [(100, 100, "Certain"), (95, 99, "Almost certain"), (80, 94, "Very likely"), (55, 79, "Likely"),
         (45, 54, "Roughly even"), (20, 44, "Unlikely to be confirmed"), (0, 19, "Not confirmed")]
WORDS = [w for _, _, w in BANDS]
KINDS = {"fact", "forecast", "estimate", "count", "opinion"}
FRESH_DAYS = 30


class Refused(ValueError):
    """The evidence record cannot be scored as written. The claim stays unscored."""


def band(score):
    for lo, hi, word in BANDS:
        if lo <= score <= hi:
            return word
    raise Refused(f"score {score!r} is outside 0-100")


def _day(v, field, as_of):
    try:
        d = dt.date.fromisoformat(v)
    except (TypeError, ValueError):
        raise Refused(f"{field} {v!r} is not a real date (YYYY-MM-DD)")
    if d > as_of:
        raise Refused(f"{field} {d} is after the scoring date {as_of}: a check cannot be recorded before it happens")
    return d


def score(ev, as_of=None):
    """{'score', 'band', 'points': [(row, n, why)], 'caps': [(cap, why)]} for one evidence record."""
    as_of = as_of or dt.date.today()
    if not isinstance(ev, dict):
        raise Refused("no evidence record")
    rung = ev.get("rung")
    if rung == "D":
        raise Refused("rung D (memory only): nothing is published from the bottom rung")
    if rung not in ("A", "B", "C"):
        raise Refused(f"rung {rung!r} must be A, B or C (Protocol 2, R7)")
    kind = ev.get("kind", "fact")
    if kind not in KINDS:
        raise Refused(f"kind {kind!r} must be one of {sorted(KINDS)}")
    pts, caps = [], []

    prim = ev.get("primary")
    prim_ok = False
    if prim is not None:
        if not isinstance(prim, dict) or not prim.get("url"):
            raise Refused("primary needs a url")
        _day(prim.get("opened"), "primary.opened", as_of)
        if str(prim.get("found") or "").strip():
            prim_ok = True
            pts.append(("primary", 50, "issuer's own document opened, and the figure, date or quote found in it"))
        else:
            pts.append(("primary", 0, "issuer's document opened, but nothing recorded as found in it"))

    srcs = ev.get("sources") or []
    if not isinstance(srcs, list):
        raise Refused("sources must be a list")
    urls = []
    for i, s in enumerate(srcs):
        if not isinstance(s, dict) or not s.get("url"):
            raise Refused(f"sources[{i}] needs a url")
        _day(s.get("opened"), f"sources[{i}].opened", as_of)
        urls.append(s["url"])
    if len(set(urls)) != len(urls):
        raise Refused("the same source is listed twice: a copy is not a second source (R1)")
    if prim and prim.get("url") in urls:
        raise Refused("the primary document is also listed as an independent source: it counts once")
    n = len(srcs) + (1 if prim_ok else 0)   # the agreeing sources opened, the primary among them
    if n >= 2:
        pts.append(("second", 15, "a second, independent source agrees"))
    if rung == "C" and n > 2:
        extra = min(10 * (n - 2), 40)
        pts.append(("further", extra, f"{n - 2} further independent source(s), R9"))

    arc = ev.get("archived")
    if arc is not None:
        if not isinstance(arc, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(arc.get("sha256", "")).lower()):
            raise Refused("archived needs a 64-hex sha256")
        pts.append(("archived", 10, "our own copy, hashed"))

    c = _day(ev.get("checked"), "checked", as_of)
    if (as_of - c).days <= FRESH_DAYS:
        pts.append(("fresh", 10, f"checked {c}, within {FRESH_DAYS} days"))
    else:
        pts.append(("fresh", 0, f"checked {c}, {(as_of - c).days} days ago"))

    rev = ev.get("reviewers") or []
    if not isinstance(rev, list):
        raise Refused("reviewers must be a list")
    models = {r.get("model") for r in rev if isinstance(r, dict) and r.get("model")}
    unresolved = bool(ev.get("conflict_unresolved"))
    if len(models) >= 2 and all(r.get("opened") is True and r.get("agrees") is True for r in rev) and not unresolved:
        pts.append(("reviewers", 15, "both reviewers opened the source and agree"))
    elif rev:
        pts.append(("reviewers", 0, "reviewers did not both open the source and agree (R1)"))

    total = sum(p for _, p, _ in pts)
    if not prim_ok and n == 0:
        caps.append((20, "no source could be opened at all"))
    if unresolved:
        caps.append((40, "two credible sources disagree, unresolved"))
    if not prim_ok:
        caps.append((75, "no primary source opened"))
    if total >= 100 and kind != "fact":
        caps.append((99, f"a {kind} is never Certain (R8)"))
    for cap, _ in caps:
        total = min(total, cap)
    total = min(total, 100)
    return {"score": total, "band": band(total), "points": pts, "caps": caps}


def from_docket(entry, log, archive=()):
    """The evidence a Docket or Chronicle entry's own records show, and nothing more.

    Earned: the primary row, when a primary source has a successful retrieval record that names what
    was found in it (docket.py fetch records `found`; a WebFetch record its `note`); freshness, from
    `checked`. Not earned, because no legacy record says so: independence of a second source (R1), our
    two reviewers. Those stay at 0 until someone records them. The hashed copy is earned when the source
    archive's manifest holds the source the claim rests on, fetched with HTTP 200 (an error page's hash is
    not a copy of the source)."""
    kept = {r["url"]: r["sha256"] for r in archive if r.get("status") == 200 and r.get("sha256")}
    ok = {}
    for r in log:
        if r.get("ok") and (r.get("found") or r.get("note")):
            ok.setdefault(r["url"], r)
    prim = None
    for s in entry.get("sources") or []:
        r = ok.get(s.get("url"))
        if s.get("primary") and r:
            prim = {"url": s["url"], "opened": r["date"], "found": ", ".join(r.get("found") or []) or r.get("note", "")}
            break
    # with no primary, the first secondary source we opened is recorded, so the claim is not "nothing opened";
    # a second one earns nothing here, because no legacy record says it is independent of the first (R1)
    seen = [] if prim else [{"url": s["url"], "opened": ok[s["url"]]["date"]} for s in entry.get("sources") or [] if s.get("url") in ok][:1]
    rests = prim["url"] if prim else (seen[0]["url"] if seen else next((s.get("url") for s in entry.get("sources") or []), None))
    arc = {"sha256": kept[rests]} if rests in kept else None
    return {"rung": "A" if prim else "C", "primary": prim, "sources": seen, "archived": arc,
            "checked": entry.get("checked"), "reviewers": [], "kind": "fact"}


def _jl(p):
    return [json.loads(l) for l in pathlib.Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def main(argv):
    as_of = dt.date.today()
    if "--as-of" in argv:
        i = argv.index("--as-of")
        as_of = dt.date.fromisoformat(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    archive = []
    if "--archive" in argv:
        i = argv.index("--archive")
        archive = _jl(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if argv[:1] == ["--docket"] and len(argv) == 3:
        log = _jl(argv[2])
        claims = [{"id": e["id"], "label": e.get("label"), "evidence": from_docket(e, log, archive)} for e in _jl(argv[1])]
    elif len(argv) == 1:
        claims = _jl(argv[0])
    else:
        sys.exit(__doc__.split("\n\n")[1])
    out, refused = [], 0
    for c in claims:
        try:
            r = score(c.get("evidence"), as_of)
            out.append({"id": c.get("id"), "label": c.get("label"), "score": r["score"], "band": r["band"],
                        "points": r["points"], "caps": r["caps"]})
        except Refused as ex:
            refused += 1
            out.append({"id": c.get("id"), "label": c.get("label"), "refused": str(ex)})
    if as_json:
        print(json.dumps(out, indent=1, ensure_ascii=False))
    else:
        for o in out:
            if "refused" in o:
                print(f'REFUSED  {o["id"]}: {o["refused"]}')
            else:
                why = " · ".join(f"{w} ({p})" for _, p, w in o["points"] if p) or "nothing earned"
                cap = "".join(f"; capped at {c}: {w}" for c, w in o["caps"])
                print(f'{o["score"]:3d}% {o["band"]:24} {o["id"]}  [{o.get("label") or "-"}]  {why}{cap}')
        print(f"certainty: {len(out)} claims, {refused} refused, as of {as_of.strftime('%b %d, %Y')}")
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
