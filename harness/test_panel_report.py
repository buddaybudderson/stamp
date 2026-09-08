#!/usr/bin/env python3
"""
Simulates a completed panel run so the REPORT path is exercised before any money
is spent on it. No network. Fabricates judge verdicts over the real nemotron
sample, writes them where a real run would, calls report(), then cleans up.

Three scenarios. The middle one is the dangerous one:

  HEALTHY   every judge answers. AC1 high, attrition zero, nothing to report.
  BROKEN    one judge returns nothing usable on 40% of draws - the J-R failure
            mode from v1.69. It still CLEARS the 0.70 gate, because a judge that
            does not answer removes itself from the draws it broke on and the
            survivors agree fine. Nothing in the agreement table would tell you.
            Only the attrition table does. A panel that hid this would be worse
            than no panel, because it launders a broken judge into a statistic.
  LENIENT   the tier-1 grader is systematically wrong on 15% of draws and the
            other two overrule it. This is what the panel exists to find, and it
            is the only scenario where AC1 itself moves.

    python scripts/test_panel_report.py
"""
import importlib.util, json, pathlib, random, shutil, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("pg", ROOT / "scripts" / "panel_grade.py")
pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pg)

CAND = "nemo_v1"
rows, _ = pg.load_runs(CAND)
if not rows:
    sys.exit(f"needs pilot_out/pilot_{CAND}_[AB].jsonl to simulate against")

SLUG, TIER1 = "nvidia/nemotron-3.5-lightning", "bytedance-seed/seed-2-1-turbo"
items = [json.loads(l) for l in (ROOT / "bank" / "bank_v1.jsonl").read_text(
    encoding="utf-8").splitlines() if l.strip()]
panel, recused, note = pg.load_panel(SLUG)
t1_seat = next(j["id"] for j in panel if j["model"] == TIER1)
sample, why, contested, n_graded = pg.build_sample(rows, items, 0.20, CAND)

# A system temp dir, not a folder inside the project. Two reasons: the simulation
# must never be mistaken for real panel output, and some mounts refuse deletes -
# writing scratch data into the working folder would leave it there permanently.
# Each scenario truncates the same two files, so nothing needs removing in between.
tmp = pathlib.Path(tempfile.mkdtemp(prefix="stamp_panel_sim_"))
pg.OUTDIR = tmp


def simulate(name, disagree, lose_rate, loser, t1_wrong=0.0):
    out = tmp / f"panel_{CAND}.jsonl"
    rnd = random.Random(7)
    done = {}
    with out.open("w", encoding="utf-8") as fh:
        for k in sample:
            t1 = rows[k]["verdict"]
            # A genuinely wrong tier-1 verdict is not two independent coin flips -
            # both other judges see the same true answer and flip TOGETHER. Modelling
            # it as independent noise makes the overrule rate 0.08^2 and the
            # extrapolation path never runs.
            both_flip = rnd.random() < t1_wrong
            for j in panel:
                if j["id"] == t1_seat:
                    continue
                if j["id"] == loser and rnd.random() < lose_rate:
                    v, fin = "UNPARSED", "length"
                else:
                    flip = both_flip or rnd.random() < disagree
                    v = ("FAIL" if t1 == "PASS" else "PASS") if flip else t1
                    fin = "stop"
                    done[(j["id"], k[0], k[1], k[2])] = v
                fh.write(json.dumps({"judge": j["id"], "model": j["model"],
                                     "item_id": k[0], "half": k[1], "draw": k[2],
                                     "verdict": v, "why": "sim", "finish": fin,
                                     "reasoning_tokens": rnd.randint(0, 900),
                                     "served_by": "sim",
                                     "selected_by": why.get(k, "?")}) + "\n")
    for k in sample:
        done[(t1_seat, k[0], k[1], k[2])] = rows[k]["verdict"]

    print("\n" + "#" * 78)
    print(f"# SCENARIO: {name}")
    print("#" * 78)
    pg.report(CAND, SLUG, TIER1, t1_seat, panel, sample, rows, done, why,
              contested, n_graded, note, 0.20, out, "")
    res = json.loads((tmp / f"panel_{CAND}.json").read_text(encoding="utf-8"))
    return res


ok = True
h = simulate("HEALTHY - all three judges answer, ~8% honest disagreement",
             disagree=0.08, lose_rate=0.0, loser=None)
if h["ac1"] < 0.70:
    print("\nFAIL: healthy panel should clear the 0.70 gate"); ok = False
if h["draws_excluded_incomplete"] != 0:
    print("\nFAIL: healthy panel should drop no draws"); ok = False

b = simulate("BROKEN - J-B returns nothing usable on 40% of draws",
             disagree=0.08, lose_rate=0.40, loser="J-B")
lost = b["attrition"].get("J-B", {})
bad = sum(v for k, v in lost.items() if k in ("UNPARSED", "ERROR", "TRUNCATED"))
if bad == 0:
    print("\nFAIL: broken judge's losses were not recorded"); ok = False
if b["draws_excluded_incomplete"] == 0:
    print("\nFAIL: broken run should exclude the draws it lost"); ok = False

w = simulate("LENIENT TIER-1 - the panel overrules the grader on 15% of draws",
             disagree=0.05, lose_rate=0.0, loser=None, t1_wrong=0.15)
if w["tier1_overruled_rate"] < 0.05:
    print("\nFAIL: the overrule path did not fire"); ok = False
if w["ac1"] >= h["ac1"]:
    print("\nFAIL: a systematically lenient tier-1 should LOWER agreement"); ok = False

print("\n" + "=" * 78)
print(f"  healthy: AC1 {h['ac1']:+.3f}, 0 draws dropped, "
      f"tier-1 overruled {h['tier1_overruled_rate']:.1%}")
print(f"  broken : AC1 {b['ac1']:+.3f}, {b['draws_excluded_incomplete']} draws dropped, "
      f"J-B lost {bad}")
print(f"  lenient: AC1 {w['ac1']:+.3f}, tier-1 overruled {w['tier1_overruled_rate']:.1%} "
      f"-> ~{w['tier1_overruled_rate']*(w['graded_draws']-w['sampled']):.0f} verdicts "
      f"would move in the unsampled remainder")
print("\n  The point of the second scenario: a judge that answers 40% of the time still")
print("  CLEARS the 0.70 gate. It does not drag agreement down, because it removes")
print("  itself from the draws it broke on and the survivors agree fine. Nothing in")
print("  the agreement table would tell you. Only the attrition line does - which is")
print("  why it prints ABOVE the agreement table and not below it.")
print("\n  The third is what the panel is FOR: a systematically lenient tier-1 grader")
print("  does move AC1, and produces a number - 'N verdicts would move' - that says")
print("  what the single-grader result is worth.")
print("=" * 78)

shutil.rmtree(tmp, ignore_errors=True)
print("\nALL REPORT-PATH CHECKS PASSED" if ok else "\nCHECKS FAILED")
sys.exit(0 if ok else 1)
