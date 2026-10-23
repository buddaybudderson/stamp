#!/usr/bin/env python3
"""Tests for tools/certainty.py and house_gate H15. Every check is shown passing good input and firing on a planted fault.

    python tools/test_certainty.py      exit 0 = all pass

Stdlib only. No network. The live site is copied to a temporary folder before anything is planted in it.
"""
import datetime as dt, pathlib, re, shutil, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import certainty as C  # noqa: E402

DAY = dt.date(2026, 10, 12)       # the Patten worked example was scored this day
H = "a" * 64
fails = []


def eq(name, got, want):
    if got != want:
        fails.append(f"{name}: got {got!r}, want {want!r}")


def refuses(name, ev, as_of=DAY):
    try:
        C.score(ev, as_of)
        fails.append(f"{name}: scored, should have been refused")
    except C.Refused:
        pass


def src(*urls):
    return [{"url": u, "opened": "2026-10-12"} for u in urls]


# 1. The worked example (house-protocols/worked-example, Oct 12, 2026), scored by hand that day. The script must agree.
patten = {
    "title, ISBN and date (85%)": ({"rung": "B", "primary": {"url": "penguin", "opened": "2026-10-12", "found": "ISBN 9780141021447"},
                                    "sources": src("guardian", "openlibrary"), "archived": {"sha256": H}, "checked": "2026-10-12"}, 85, "Very likely"),
    "Jacques's own words (70%)": ({"rung": "A", "primary": {"url": "review", "opened": "2026-10-12", "found": "the most tedious section"},
                                   "archived": {"sha256": H}, "checked": "2026-10-12"}, 70, "Likely"),
    "critical of the Iraq war (55%)": ({"rung": "C", "primary": None, "sources": src("r1", "r2", "r3", "r4"),
                                        "archived": {"sha256": H}, "checked": "2026-10-12"}, 55, "Likely"),
    "Prodi Commission term (85%)": ({"rung": "B", "primary": {"url": "ec-archive", "opened": "2026-10-12", "found": "Sep 16, 1999"},
                                     "sources": src("penguin"), "archived": {"sha256": H}, "checked": "2026-10-12"}, 85, "Very likely"),
}
for name, (ev, want, word) in patten.items():
    r = C.score(ev, DAY)
    eq(name, (r["score"], r["band"]), (want, word))

# 2. The faults Protocol 4 exists to catch.
base = {"rung": "A", "primary": {"url": "p", "opened": "2026-10-12", "found": "x"}, "sources": src("s"),
        "archived": {"sha256": H}, "checked": "2026-10-12",
        "reviewers": [{"model": "claude", "opened": True, "agrees": True}, {"model": "xing", "opened": True, "agrees": True}]}
eq("all five rows, a fact of record", C.score(base, DAY)["score"], 100)
eq("100% is Certain", C.score(base, DAY)["band"], "Certain")
eq("a forecast is never Certain (R8)", C.score({**base, "kind": "forecast"}, DAY)["score"], 99)
eq("primary opened but nothing found in it earns 0",
   C.score({**base, "primary": {"url": "p", "opened": "2026-10-12", "found": ""}}, DAY)["score"], 35)
eq("reviewers agreeing without opening earn nothing (R1)",
   C.score({**base, "reviewers": [{"model": "claude", "opened": False, "agrees": True}, {"model": "xing", "opened": True, "agrees": True}]}, DAY)["score"], 85)
eq("one reviewer twice is not two", C.score({**base, "reviewers": [{"model": "claude", "opened": True, "agrees": True}] * 2}, DAY)["score"], 85)
eq("unresolved conflict caps at 40", C.score({**base, "conflict_unresolved": True}, DAY)["score"], 40)
eq("nothing opened caps at 20", C.score({"rung": "C", "primary": None, "archived": {"sha256": H}, "checked": "2026-10-12",
                                         "reviewers": base["reviewers"]}, DAY)["score"], 20)
eq("secondary only caps at 75 however many sources (R9)",
   C.score({"rung": "C", "primary": None, "sources": src(*"abcdefg"), "archived": {"sha256": H}, "checked": "2026-10-12",
            "reviewers": base["reviewers"]}, DAY)["score"], 75)
eq("R9 further sources stop at 40", [p for r, p, _ in C.score({"rung": "C", "sources": src(*"abcdefghij"), "checked": "2026-10-12"}, DAY)["points"] if r == "further"], [40])
eq("R9 is for rung C only", [r for r, _, _ in C.score({**base, "sources": src("s", "t", "u")}, DAY)["points"]].count("further"), 0)
eq("a check 31 days old is not fresh", C.score(base, DAY + dt.timedelta(days=31))["score"], 90)
refuses("rung D (memory only)", {**base, "rung": "D"})
refuses("no rung", {k: v for k, v in base.items() if k != "rung"})
refuses("an impossible date", {**base, "checked": "2026-02-30"})
refuses("a check dated after the scoring day", {**base, "checked": "2026-10-13"})
refuses("the same source twice (a copy is not a second source)", {**base, "sources": src("s", "s")})
refuses("the primary listed again as independent", {**base, "sources": src("p")})
refuses("a hash that is not a SHA-256", {**base, "archived": {"sha256": "abc"}})
refuses("no evidence at all", None)
for lo, hi, w in C.BANDS:
    eq(f"band {lo}", C.band(lo), w)
    eq(f"band {hi}", C.band(hi), w)

# 3. Legacy Docket records: only what the record shows is earned.
log = [{"url": "https://gov/a", "date": "2026-10-05", "ok": True, "found": ["SB 813"]},
       {"url": "https://gov/b", "date": "2026-10-05", "ok": True}]           # ok, but nothing recorded as found
e = {"id": "x", "checked": "2026-10-08", "sources": [{"url": "https://gov/a", "primary": True}]}
eq("legacy: primary opened and found, checked", C.score(C.from_docket(e, log), DAY)["score"], 60)
e2 = {"id": "y", "checked": "2026-10-08", "sources": [{"url": "https://gov/b", "primary": True}]}
eq("legacy: a retrieval that found nothing earns no primary row", C.score(C.from_docket(e2, log), DAY)["score"], 10)
arch = [{"url": "https://gov/a", "status": 200, "sha256": H}, {"url": "https://gov/b", "status": 403, "sha256": H}]
eq("legacy: the archive manifest's copy earns the hash row", C.score(C.from_docket(e, log, arch), DAY)["score"], 70)
eq("legacy: a 403 page's hash is not a copy of the source", C.score(C.from_docket(e2, log, arch), DAY)["score"], 10)

# 4. house_gate H15 on a copy of the live site. The copy is first made unscored, so the test does not depend on
# whether the live pages show scores yet.
docs = HERE.parent / "docs"
SCORE_SPAN = r'<span class="dk-tag certainty[^"]*" data-certainty="\d+"[^>]*>[^<]*</span>'
with tempfile.TemporaryDirectory() as tmp:
    t = pathlib.Path(tmp) / "docs"
    shutil.copytree(docs, t)

    def gate(as_of):
        r = subprocess.run([sys.executable, str(HERE / "house_gate.py"), str(t), f"--as-of={as_of}"], capture_output=True, text=True, encoding="utf-8")
        return r.returncode, [l for l in r.stdout.splitlines() if " H15 " in l]

    def rewrite(f):
        for page in ("docket", "chronicle"):
            p = t / page / "index.html"
            p.write_text(f(p.read_text(encoding="utf-8")), encoding="utf-8")

    rewrite(lambda s: re.sub(SCORE_SPAN, "", s))
    rc, h15 = gate("2026-11-08")
    eq("unscored Docket and Chronicle, Nov 08, 2026: WARN", (rc, sorted(l.split()[0] for l in h15)), (0, ["WARN", "WARN"]))
    rc, h15 = gate("2026-11-09")
    eq("unscored Docket and Chronicle, Nov 09, 2026: FAIL (R3)", (rc, sorted(l.split()[0] for l in h15)), (1, ["FAIL", "FAIL"]))
    # score every entry on the copy: the R3 failure must go away, so it is about the scores and nothing else
    rewrite(lambda s: s.replace('<div class="dk-meta">', '<div class="dk-meta"><span class="dk-tag certainty" data-certainty="60">60% Likely</span>'))
    rc, h15 = gate("2026-11-09")
    eq("every claim scored: no H15", (rc, h15), (0, []))
    # plant a wrong band word on the worked example: 85% is Very likely, not Likely
    w = t / "house-protocols" / "worked-example" / "index.html"
    w.write_text(w.read_text(encoding="utf-8").replace("85% Very likely", "85% Likely", 1), encoding="utf-8")
    rc, h15 = gate("2026-10-20")
    eq("85% Likely is refused", (rc, len(h15), "85% is Very likely, not Likely" in "".join(h15)), (1, 1, True))
    w.write_text(w.read_text(encoding="utf-8").replace("85% Likely", "85% Very likely", 1), encoding="utf-8")
    # a score whose stored number is not the one shown
    p = t / "docket" / "index.html"
    p.write_text(p.read_text(encoding="utf-8").replace('data-certainty="60">60%', 'data-certainty="85">60%', 1), encoding="utf-8")
    rc, h15 = gate("2026-11-09")
    eq("data-certainty 85 shown as 60% is refused", (rc, any('data-certainty="85" but the page shows 60%' in l for l in h15)), (1, True))
    # the labels removed and no score added: every entry is still a claim, so this must fail, not pass for having nothing to check
    rewrite(lambda s: re.sub(r'<span class="dk-tag (Supported|Likely|Unknown)">[^<]*</span>', "", re.sub(SCORE_SPAN, "", s)))
    rc, h15 = gate("2026-11-09")
    eq("labels dropped, nothing scored: still refused",
       (rc, any("/docket/" in l and re.search(r"(\d+) of \1 claims carry no certainty score", l) for l in h15)), (1, True))

print("\n".join("FAIL  " + f for f in fails) or "test_certainty: all pass")
sys.exit(1 if fails else 0)
