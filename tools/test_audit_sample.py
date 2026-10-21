#!/usr/bin/env python3
"""Tests for tools/audit_sample.py (R4). Each refusal is shown firing on a planted fault, on a draw from the live site.

    python tools/test_audit_sample.py      exit 0 = all pass

Stdlib only. No network. Everything is written to a temporary folder.
"""
import datetime as dt, json, pathlib, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit_sample as A  # noqa: E402

DOCS = HERE.parent / "docs"
fails = []


def eq(name, got, want):
    if got != want:
        fails.append(f"{name}: got {got!r}, want {want!r}")


def refuses(name, fn, why):
    try:
        fn()
        fails.append(f"{name}: passed, should have been refused")
    except A.Refused as ex:
        if why not in str(ex):
            fails.append(f"{name}: refused for the wrong reason: {ex}")


def edit(path, f):
    d = json.loads(path.read_text(encoding="utf-8"))
    f(d)
    path.write_text(json.dumps(d), encoding="utf-8")


def fill(sheet, error_at=None):
    for i, c in enumerate(sheet["claims"]):
        bad = i == error_at
        c["reviewer_1"] = {"model": "claude-opus-5-5", "opened": True, "verdict": "error" if bad else "ok", "note": ""}
        c["reviewer_2"] = {"model": "xing4.0", "opened": True, "verdict": "ok", "note": ""}
        c["person"] = {"name": "Lawrence Ho", "verdict": "error" if bad else "ok", "note": "", "date": "2026-10-24"}


# the bound
eq("0 in 30: rule of three, 9.5%", round(A.upper95(0, 30), 4), 0.095)
eq("0 in 300: about 1%", round(A.upper95(0, 300), 4), 0.0099)
eq("1 in 30 (Clopper-Pearson one-sided)", round(A.upper95(1, 30), 3), 0.149)
refuses("nothing checked has no bound", lambda: A.upper95(0, 0), "nothing checked")

pop = A.population(DOCS)
ids = [c["id"] for c in pop]
eq("the population is not empty, and has both kinds of claim",
   (len(pop) > 200, any(i.startswith("docket/") for i in ids), any(i.startswith("si/") for i in ids)), (True, True, True))
eq("ids are unique", len(ids), len(set(ids)))
eq("the same seed draws the same claims", A.pick(ids, "stamp-audit-2026-10-17", 30), A.pick(list(reversed(ids)), "stamp-audit-2026-10-17", 30))
eq("another seed draws others", A.pick(ids, "stamp-audit-2026-10-17", 30) != A.pick(ids, "stamp-audit-2026-10-24", 30), True)

with tempfile.TemporaryDirectory() as tmp:
    t = pathlib.Path(tmp)
    rec = A.draw(DOCS, t / "w1", dt.date(2026, 10, 17))
    eq("30 drawn, seed recorded", (len(rec["drawn"]), rec["seed"]), (30, "stamp-audit-2026-10-17"))
    refuses("a second draw for the same Saturday", lambda: A.draw(DOCS, t / "w1", dt.date(2026, 10, 17), seed="another"), "exists")
    A.verify(t / "w1")
    refuses("an unfilled worksheet is not an audit", lambda: A.tally([t / "w1"]), "no model")

    # a claim that proved awkward is swapped for an easier one: the seed does not draw it
    import shutil
    shutil.copytree(t / "w1", t / "swap")
    easy = next(i for i in rec["population"] if i not in {c["id"] for c in rec["drawn"]})
    edit(t / "swap" / "draw.json", lambda d: d["drawn"].__setitem__(0, {"id": easy, "page": "", "text": "", "sources": []}))
    refuses("a swapped claim", lambda: A.verify(t / "swap"), "not the ones seed")
    # the population is trimmed after the draw
    shutil.copytree(t / "w1", t / "trim")
    edit(t / "trim" / "draw.json", lambda d: d["population"].pop())
    refuses("a population edited after the draw", lambda: A.verify(t / "trim"), "fingerprint")
    # the worksheet checks a claim that was not drawn
    shutil.copytree(t / "w1", t / "sheet")
    edit(t / "sheet" / "worksheet.json", lambda d: d["claims"][0].__setitem__("id", easy))
    refuses("a worksheet for other claims", lambda: A.verify(t / "sheet"), "worksheet")

    # a complete, clean week
    edit(t / "w1" / "worksheet.json", lambda d: fill(d))
    eq("a clean week: 30 checked, 0 errors, 9.5%", [(r["n"], r["errors"], round(r["bound"], 3)) for r in A.tally([t / "w1"])], [(30, 0, 0.095)])
    for name, f, why in [
        ("a reviewer who did not open the source", lambda d: d["claims"][3]["reviewer_2"].__setitem__("opened", False), "did not open"),
        ("one model as both reviewers", lambda d: d["claims"][3]["reviewer_2"].__setitem__("model", "claude-opus-5-5"), "both reviewers"),
        ("no person", lambda d: d["claims"][3]["person"].__setitem__("name", ""), "person's check is missing"),
        ("an agent signing as the person", lambda d: d["claims"][3]["person"].__setitem__("name", "Claude"), "person's check is missing"),
        ("an overruled error with no note", lambda d: d["claims"][3]["reviewer_1"].__setitem__("verdict", "error"), "overruled"),
    ]:
        shutil.copytree(t / "w1", t / name)
        edit(t / name / "worksheet.json", f)
        refuses(name, lambda: A.tally([t / name]), why)

    # three Saturdays: the error in the second restarts the count (R4)
    A.draw(DOCS, t / "w2", dt.date(2026, 10, 24))
    edit(t / "w2" / "worksheet.json", lambda d: fill(d, error_at=5))
    A.draw(DOCS, t / "w3", dt.date(2026, 10, 31))
    edit(t / "w3" / "worksheet.json", lambda d: fill(d))
    tab = A.tally([t / "w3", t / "w1", t / "w2"])
    eq("weeks in date order, the error restarts the count",
       [(r["date"].isoformat(), r["errors"], r["since_error"]) for r in tab],
       [("2026-10-17", 0, 30), ("2026-10-24", 1, 0), ("2026-10-31", 0, 30)])
    html = A.log_table([t / "w1", t / "w2", t / "w3"])
    eq("The Log table uses house dates", ("Oct 17, 2026" in html, "2026-10-17" in html, "restarted" in html), (True, False, True))

print("\n".join("FAIL  " + f for f in fails) or "test_audit_sample: all pass")
sys.exit(1 if fails else 0)
