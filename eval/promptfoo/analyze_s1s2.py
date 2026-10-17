#!/usr/bin/env python3
"""READ A SYSTEM 1 vs SYSTEM 2 RUN. promptfoo's results.json in, the four pre-registered answers out.

    python3 analyze_s1s2.py results.s1s2.json
    python3 analyze_s1s2.py results.s1s2.json --json        machine-readable, for figures.json
    python3 analyze_s1s2.py results/2026-07-23_v1.02_gemini.json --receipt-version v1.02

  exit 0 = report printed    exit 2 = refused (nothing to read, or a System 1 row that reasoned)

CANARIES. Install-check probes (questions about STAMP itself, e.g. its original name) can only be
answered from STAMP's own files. They are dropped from every rate by default, because counting them
would credit STAMP for being installed. The report says how many were dropped.

WHAT IT COMPUTES, per provider row (labels "<model>-s1" / "<model>-s2"):
  content   fail rate native vs stamp on the probe's own criterion (llm-rubric / icontains),
            with the STAMPED-footer assertion left out, so the control is never penalised
  Q1/Q2     the STAMP effect: stamp fail rate minus native, PAIRED BY PROBE, 95% bootstrap
            interval over probes and a sign-flip p (the unit is the item, as in harness/compare.py)
  Q3        for each model with both rows: the s2 effect minus the s1 effect, paired by probe
  Q4        receipt truth on every stamp reply: harness/footer_check.py's R1-R10, no judge

WHAT IT REFUSES. A "-s1" row whose replies report reasoning tokens, or return reasoning text
("Thinking:" or a <think> block), is not a System 1 row: the
switch was ignored. The script names the row and exits 2 rather than reporting a contrast that
did not happen. Pass --allow-reasoning-s1 only to read such a run for diagnosis, never to publish.

Stdlib only. No network. Seeds fixed.
"""
import argparse, importlib.util, json, pathlib, random, re, sys

HERE = pathlib.Path(__file__).resolve().parent
FC_PATH = HERE.parents[1] / "harness" / "footer_check.py"
SEED, BOOT, FLIPS = 20261013, 10000, 20000
# Install canaries (tests/PROBES.md section N): answerable ONLY from STAMP's own files, so a native
# model cannot pass them by design. They check that STAMP is loaded; they are not a behaviour effect
# and are left out of every rate unless --include-canaries is given. Probe numbers changed between
# bank versions (v1.02 numbered them 97-101), so a canary is recognised by its text: it is a question
# about STAMP itself. In every bank so far that rule picks out exactly the canaries.
def is_canary(probe_text):
    return "STAMP" in (probe_text or "")


def load_footer_check():
    spec = importlib.util.spec_from_file_location("footer_check", FC_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rows_of(doc):
    r = doc.get("results", doc)
    if isinstance(r, dict):
        r = r.get("results", [])
    return r if isinstance(r, list) else []


def content_pass(row):
    """Pass on the probe's own criterion, ignoring the STAMPED-footer javascript assertion."""
    comps = (row.get("gradingResult") or {}).get("componentResults") or []
    comps = [c for c in comps if (c.get("assertion") or {}).get("type") != "javascript"]
    if not comps:
        return None
    return all(bool(c.get("pass")) for c in comps)


def reasoning_tokens(row):
    tu = (row.get("response") or {}).get("tokenUsage") or {}
    det = tu.get("completionDetails") or {}
    return int(det.get("reasoning") or 0)


def shows_reasoning(row):
    """True if the reply reports reasoning tokens or carries returned reasoning in its text.
    The Aug 08, 2026 gateway run reported no count on 348 of 930 replies that began "Thinking:"."""
    if reasoning_tokens(row) > 0:
        return True
    out = (row.get("response") or {}).get("output")
    return isinstance(out, str) and (out.lstrip().startswith("Thinking:") or "<think>" in out)


def paired(diffs, rng):
    """Mean of per-probe differences, 95% bootstrap CI over probes, two-sided sign-flip p."""
    n = len(diffs)
    if n == 0:
        return None
    mean = sum(diffs) / n
    boots = sorted(sum(rng.choice(diffs) for _ in range(n)) / n for _ in range(BOOT))
    lo, hi = boots[int(0.025 * BOOT)], boots[int(0.975 * BOOT) - 1]
    obs = abs(mean)
    hits = sum(1 for _ in range(FLIPS)
               if abs(sum(d if rng.random() < 0.5 else -d for d in diffs) / n) >= obs - 1e-12)
    return {"mean": mean, "lo": lo, "hi": hi, "p": (hits + 1) / (FLIPS + 1), "n": n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--allow-reasoning-s1", action="store_true")
    ap.add_argument("--include-canaries", action="store_true",
                    help="keep install canaries (questions about STAMP itself) in the rates; diagnosis only")
    ap.add_argument("--receipt-version", default="v1.25",
                    help="the STAMP version the run installed; footer_check R3 compares against it")
    a = ap.parse_args()

    rows = rows_of(json.loads(pathlib.Path(a.results).read_text(encoding="utf-8")))
    if not rows:
        print("REFUSED - no result rows in the file; nothing was read")
        return 2
    fc = load_footer_check()
    rng = random.Random(SEED)

    # cell[label][cond][probe] = pass (bool) ; receipts[label] = [problems...]
    cell, receipts, reasoned, dropped = {}, {}, {}, set()
    for r in rows:
        label = (r.get("provider") or {}).get("label") or (r.get("provider") or {}).get("id")
        cond = (r.get("prompt") or {}).get("label")
        probe = (r.get("vars") or {}).get("_probe")
        ok = content_pass(r)
        if label is None or cond not in ("native", "stamp") or probe is None or ok is None:
            continue
        if not a.include_canaries and is_canary((r.get("vars") or {}).get("probe")):
            dropped.add(probe)
            continue
        cell.setdefault(label, {}).setdefault(cond, {})[probe] = ok
        if label.endswith("-s1") and shows_reasoning(r):
            reasoned[label] = reasoned.get(label, 0) + 1
        if cond == "stamp":
            out = (r.get("response") or {}).get("output")
            if isinstance(out, str):
                receipts.setdefault(label, []).append(bool(fc.check(out, None, a.receipt_version)))

    if reasoned and not a.allow_reasoning_s1:
        for k, v in sorted(reasoned.items()):
            print(f"REFUSED - {k} showed reasoning (tokens or returned text) on {v} replies; it is not a System 1 row")
        return 2

    report = {"rows": {}, "q3": {}, "canaries_dropped": sorted(dropped, key=int)}
    for label in sorted(cell):
        nat, st = cell[label].get("native", {}), cell[label].get("stamp", {})
        common = sorted(set(nat) & set(st))
        diffs = [(not st[p]) - (not nat[p]) for p in common]   # +1 = STAMP failed where native passed
        rc = receipts.get(label, [])
        report["rows"][label] = {
            "probes": len(common),
            "native_fail": sum(not nat[p] for p in common) / len(common) if common else None,
            "stamp_fail": sum(not st[p] for p in common) / len(common) if common else None,
            "effect": paired(diffs, rng),
            "false_or_missing_receipt": (sum(rc) / len(rc)) if rc else None,
            "receipts_checked": len(rc),
        }
    for label in sorted(cell):
        if not label.endswith("-s1"):
            continue
        s2 = label[:-3] + "-s2"
        if s2 not in cell:
            continue
        def eff(lb):
            n, s = cell[lb].get("native", {}), cell[lb].get("stamp", {})
            return {p: (not s[p]) - (not n[p]) for p in set(n) & set(s)}
        e1, e2 = eff(label), eff(s2)
        common = sorted(set(e1) & set(e2))
        report["q3"][label[:-3]] = paired([e2[p] - e1[p] for p in common], rng)

    if a.json:
        print(json.dumps(report, indent=1))
        return 0

    pct = lambda x: "  -  " if x is None else f"{100 * x:5.1f}%"
    if dropped:
        print(f"Install canaries left out of every rate: probes {sorted(dropped, key=int)}\n")
    print("Content fail rate (probe's own criterion; footer graded separately), paired by probe")
    print(f"{'row':22} {'probes':>6} {'native':>7} {'stamp':>7}   effect (stamp - native) [95% CI]  p      bad receipts")
    for label, v in report["rows"].items():
        e = v["effect"]
        es = "  -" if not e else f"{100*e['mean']:+6.1f} pts [{100*e['lo']:+.1f}, {100*e['hi']:+.1f}]  p={e['p']:.3f}"
        print(f"{label:22} {v['probes']:6} {pct(v['native_fail'])} {pct(v['stamp_fail'])}   {es:42} "
              f"{pct(v['false_or_missing_receipt'])} of {v['receipts_checked']}")
    if report["q3"]:
        print("\nQ3  STAMP effect with reasoning on, minus with reasoning off (same model, paired by probe)")
        for m, e in report["q3"].items():
            if e:
                print(f"  {m:20} {100*e['mean']:+6.1f} pts [{100*e['lo']:+.1f}, {100*e['hi']:+.1f}]  p={e['p']:.3f}  n={e['n']}")
    print("\nA negative effect means STAMP lowered the fail rate. An interval that crosses zero is"
          "\n'this bank cannot tell', not 'no difference'. Tier-1 grader verdicts only until a panel sits.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
