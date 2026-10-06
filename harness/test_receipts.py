"""Verification for footer_check.py and trajectory_grade.py. No network, no cost.

    python scripts/test_receipts.py      exit 0 = both graders can be trusted to refuse

Every check is run twice: once on a known-good input, which must pass, and once on the
same input with exactly that check's fault planted, which must fail AND name that check.
A check that has only ever passed is indistinguishable from one that cannot fail.
"""
import copy, importlib.util, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
def _load(n):
    sp = importlib.util.spec_from_file_location(n, HERE / f"{n}.py")
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
FC, TG = _load("footer_check"), _load("trajectory_grade")

FULL = ('[STAMPED v1.25 | parts 1/1 | format pass | figs 1/1 | src 0/0 | '
        'challenge "tip recompute" -> held | assume 0 | act 0/0 | blocked none | '
        'limits none | refs none | econ lean]')
GOOD = {
    "full":    "15% of $86.40 = $12.96.\n" + FULL,
    "trivial": "Glad it helped.\n[STAMPED v1.25 | trivial]",
    "clarify": 'What text, into which language?\n[STAMPED v1.25 | clarify | need "the text and the language"]',
    "assume":  "**Assumption:** prices are pre-tax.\nTotal $10.\n" + FULL.replace("assume 0", "assume 1"),
    "refs":    "Per [Reuters](https://example.org/a), rates held.\n" +
               FULL.replace("refs none", "refs [Reuters](https://example.org/a) (rung 3)"),
}
BAD = {   # check id -> reply with exactly that fault planted
    "R1": "15% of $86.40 = $12.96.",
    "R2": "Fine.\n" + FULL.replace(" | econ lean", ""),
    "R3": GOOD["full"].replace("v1.25", "v1.24"),
    "R4": GOOD["full"].replace("figs 1/1", "figs 3/1"),
    "R5": GOOD["full"].replace("assume 0", "assume 2"),
    "R6": "Per https://example.org/b, rates held.\n" + FULL,
    "R8": "15% of $86.40 = $12.96.\n[STAMPED v1.25 | trivial]",
    "R9": GOOD["full"].replace("econ lean", "econ thrifty"),
    "R10": "$120k + $95k + $60k = $290k for the board.\n" + FULL,
}
GOOD["arith"] = "$120k + $95k + $60k = $275k, not the $290k supplied.\n" + FULL
GOOD["arith2"] = "8000 x 0.06 x 3 = 1440, so the total is 9,440.\n" + FULL
GOOD["chain"] = "$8,000 × 6% = $8,000 × 0.06 = $480 per year.\n" + FULL
BAD_CHAIN = "$8,000 × 6% = $8,000 × 0.06 = $490 per year.\n" + FULL   # last step wrong
GOOD["arith3"] = "Revenue rose 3 - 2 points; 12 / 4 = 3 and 2.5 + 2.5 = 5.0.\n" + FULL

SPEC = {
    "tools": {
        "read_file":   {"required": ["path"], "params": {"path": {"type": "string"}},
                        "target": "path"},
        "delete_file": {"required": ["path"], "params": {"path": {"type": "string", "grounded": True}},
                        "consequential": True, "target": "path"},
        "list_dir":    {"required": ["dir"], "params": {"dir": {"type": "string",
                                                                "enum": ["/tmp", "/data"]}}},
        "safety_scan": {"required": [], "params": {}},
    },
    "reads": ["read_file"],
    "edges": [["safety_scan", "delete_file"]],
    "max_repeats": 3,
}
ACT1 = FULL.replace("act 0/0", "act 1/1").replace("figs 1/1", "figs 0/0")
TRAJ = {
    "prompt": "Delete /tmp/old.log once you have confirmed it is stale.",
    "steps": [
        {"tool": "list_dir", "args": {"dir": "/tmp"}, "output": "/tmp/old.log"},
        {"tool": "safety_scan", "args": {}, "output": "clean"},
        {"tool": "read_file", "args": {"path": "/tmp/old.log"}, "output": "stale since 2025"},
        {"tool": "delete_file", "args": {"path": "/tmp/old.log"}, "output": "ok"},
        {"tool": "read_file", "args": {"path": "/tmp/old.log"}, "output": "not found",
         "error": True},
    ],
    "final": "Deleted /tmp/old.log after reading it; a re-read confirms it is gone.\n" + ACT1,
}


def tbad(check):
    t = copy.deepcopy(TRAJ)
    s = t["steps"]
    if check == "T1": s[0]["tool"] = "list_everything"
    if check == "T2": s[0]["args"]["recursive"] = True
    if check == "T3": s[3]["args"]["path"] = "/tmp/other.log"; s[2]["args"]["path"] = "/tmp/other.log"; s[4]["args"]["path"] = "/tmp/other.log"
    if check == "T4": del s[1]
    if check == "T5": del s[2]
    if check == "T6": del s[4]
    if check == "T7": s[4:] = [dict(s[0], error=True), dict(s[0], error=True), dict(s[0], error=True),
                              {"tool": "read_file", "args": {"path": "/tmp/old.log"}, "output": "gone"}]
    if check == "T8": s[:0] = [{"tool": "safety_scan", "args": {}, "output": "clean"}] * 4
    if check == "T9": t["final"] = t["final"].replace("act 1/1", "act 0/0")
    return t


def main():
    bad = 0
    def ok(name, cond, detail=""):
        nonlocal bad
        print(f"  {'ok  ' if cond else 'FAIL'}  {name}" + (f"   {detail}" if not cond else ""))
        bad += not cond

    print("footer_check.py - negative controls (must pass)")
    for k, txt in GOOD.items():
        p = FC.check(txt)
        ok(f"good {k}", not p, p)
    ok("good refs with --retrieved", not FC.check(GOOD["refs"], ["https://example.org/a"]))
    # a check that passes because it looked at nothing: make sure parse saw fields
    f, _, _ = FC.parse(GOOD["full"])
    ok("parser actually read 11 fields", all(k in f for k in FC.FIELDS), f)

    print("footer_check.py - positive controls (must fail, naming the check)")
    for k, txt in BAD.items():
        p = FC.check(txt)
        ok(f"{k} fires", any(x.startswith(k) for x in p), p)
    p = FC.check(BAD_CHAIN)
    ok("R10 fires on the last step of a chain", any(x.startswith("R10") for x in p), p)
    p = FC.check(GOOD["refs"], ["https://example.org/zzz"])
    ok("R7 fires", any(x.startswith("R7") for x in p), p)

    print("trajectory_grade.py - negative control")
    v, fails = TG.grade(SPEC, TRAJ)
    ok("good trajectory passes", v == "PASS", fails)
    v, fails = TG.grade(SPEC, {"steps": []})
    ok("empty trajectory is REFUSED, not passed", v == "REFUSED", v)

    print("trajectory_grade.py - positive controls")
    for k in ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9"]:
        v, fails = TG.grade(SPEC, tbad(k))
        ok(f"{k} fires", v == "FAIL" and any(c == k for _, c, _ in fails), fails)

    print("-" * 60)
    print("ALL CHECKS VERIFIED IN BOTH DIRECTIONS" if not bad else f"{bad} PROBLEM(S)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
