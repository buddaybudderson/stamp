#!/usr/bin/env python3
"""
Verification for the Tier-2 panel. No network, no cost - run it before every panel
run and after any edit to panel_grade.py, judges.json or pilot_native.py.

    python scripts/test_panel.py       exit 0 = safe to spend money

Three things are checked, each of which has already gone wrong at least once in
this programme or was one edit away from doing so:

  1. RECUSAL. Matching judges on judges.json's `family` alone let x-ai/grok-4.6
     grade itself, because its family string is "grok" and its vendor prefix is
     "x-ai". A judge grading its own lineage is the one failure that invalidates
     an independence claim outright, and nothing in the run would have raised it.
  2. THE STATISTICS. AC1 must be 1.0 on perfect agreement and must NOT collapse
     when defects are rare. Fleiss must collapse - that is the prevalence paradox
     PANEL.md is built around, and it is asserted here rather than believed.
  3. THE LIFTED INSTRUMENT. panel_grade.py takes its grading prompt and its
     verdict parser out of pilot_native.py's source so the panel cannot drift from
     the tier-1 grader. If the lift breaks, importing panel_grade.py dies - so
     importing it at all is the test.
"""
import importlib.util, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("pg", ROOT / "scripts" / "panel_grade.py")
pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pg)          # check 3 happens here, at import

fails = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {name:<52} {got}")
    if not ok:
        fails.append(f"{name}: got {got!r}, wanted {want!r}")


print("1. RECUSAL - a judge must never grade its own lineage")
CASES = [
    # candidate slug,                    seats expected,        recused
    ("nvidia/nemotron-3.5-lightning", ["J-A", "J-B", "J-C"], None),
    ("openai/gpt-5.6-luna",           ["J-A", "J-B", "J-C"], None),
    ("z-ai/glm-5.3",                  ["J-A", "J-B", "J-C"], None),
    ("qwen/qwen3.5-9b",               ["J-A", "J-B", "J-C"], None),
    ("allenai/olmo-3-7b-instruct",    ["J-A", "J-B", "J-C"], None),
    # these three MUST recuse
    ("bytedance-seed/seed-2-1-turbo", ["J-A", "J-B", "J-R"], "J-C"),
    ("google/gemini-3.7-flash",       ["J-B", "J-C", "J-R"], "J-A"),
    ("x-ai/grok-4.6",                 ["J-A", "J-C", "J-R"], "J-B"),
    ("deepseek/deepseek-v4-pro-0813", ["J-A", "J-B", "J-C"], None),   # reserve unused
]
for slug, want_seats, want_rec in CASES:
    panel, rec, note = pg.load_panel(slug)
    check(slug, sorted(j["id"] for j in panel), sorted(want_seats))
    got_rec = rec[0]["id"] if rec else None
    check(f"    recused for {slug.split('/')[0]}", got_rec, want_rec)
    if want_rec:
        check("    panel is still three", len(panel), 3)

print("\n  note: deepseek is the RESERVE, not seated. A deepseek candidate recuses")
print("  nobody, so the reserve is free - which is the point of holding one back.")

print("\n2. STATISTICS - AC1 holds where Fleiss collapses")
perfect = [["PASS"] * 3] * 50 + [["FAIL"] * 3] * 50
skew    = [["PASS"] * 3] * 97 + [["PASS", "PASS", "FAIL"]] * 3
ac1_p = pg.gwet_ac1(perfect)[0]
ac1_s, _, _ = pg.gwet_ac1(skew)
fk_s = pg.fleiss_kappa(skew)
check("AC1 = 1.000 on perfect agreement", round(ac1_p, 6), 1.0)
check("AC1 stays high when defects are rare", ac1_s > 0.90, True)
check("Fleiss collapses on the same data", fk_s < 0.50, True)
print(f"       same 97%-agreement data: AC1 {ac1_s:+.3f} vs Fleiss {fk_s:+.3f} "
      f"- a {ac1_s - fk_s:.2f} gap.")
check("coin-flip judges score at or below zero", pg.gwet_ac1(
    [["PASS", "FAIL", "PASS"], ["FAIL", "PASS", "FAIL"]] * 25)[0] <= 0, True)

print("\n3. LIFTED INSTRUMENT - one grading prompt, one parser, no second copy")
check("GRADE_TMPL lifted from pilot_native.py",
      "CRITERION THE RESPONSE MUST MEET" in pg.GRADE_TMPL, True)
check("template still has all three slots",
      all(f"{{{s}}}" in pg.GRADE_TMPL for s in ("crit", "ask", "resp")), True)
check("lifted parser reads a clean verdict",
      pg.parse_verdict('{"verdict":"FAIL","why":"x"}', "stop", 0, None)[0], "FAIL")
check("lifted parser salvages unterminated JSON",
      pg.parse_verdict('{"verdict": "PASS", "why": "the response correctly decl',
                       "stop", 0, None)[0], "PASS")
check("lifted parser refuses to guess",
      pg.parse_verdict("looks fine to me", "stop", 0, None)[0], "UNPARSED")

print("\n" + "=" * 70)
if fails:
    print(f"{len(fails)} CHECK(S) FAILED - do not run the panel:")
    for f in fails:
        print("   ", f)
    sys.exit(1)
print("ALL CHECKS PASSED - safe to spend money on a panel run.")
