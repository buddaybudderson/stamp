"""THE REGRESSION GATE. Blocks a protocol change that makes the protocol worse.

    python scripts/eval_gate.py <baseline run> <candidate run>     a pair of run files
    python scripts/eval_gate.py --pr <changed-files.txt> [--evals evals/]   CI mode

  exit 0 = merge may proceed    exit 1 = blocked    exit 2 = refused (cannot judge)

WHAT IT BLOCKS. A change to STAMP.md or a variant is a change to the instrument's subject;
it ships only with a measurement showing it did not regress. Thresholds, fixed here and
not after seeing a result:

  quality   the fail rate rose by more than 2.0 points AND the paired item interval
            (compare.py's) excludes zero. Both: a 2.1-point rise inside the noise is not
            a regression, and a significant 0.5-point rise is not worth blocking.
  latency   median seconds per answer rose by more than 25%   (when both runs record it)
  cost      mean $ per answer rose by more than 25%            (when both runs record it)
  receipts  the share of replies with a false or missing STAMPED footer rose at all
            (footer_check.py) - a protocol change may not make receipts less true

"No baseline, no claim": a dimension neither run recorded is printed UNMEASURED and does
not pass or block. Quality is never optional - a pair with no shared graded items is
refused.

WHY CI NEVER RUNS THE MODELS. A paid run needs a signed pre-registration and Lawrence's
OK (release rules), and the held-out half can never be in a public runner. So the run is
made locally, on the PUBLIC half, redacted the usual way, and committed with the PR under
evals/<anything>/{baseline,candidate}.jsonl. CI checks the arithmetic, not the models.

In --pr mode: if no protocol file changed, the gate passes and says why. If one did and no
evals/ pair is committed, the gate BLOCKS - an unmeasured protocol change is the failure.

Stdlib only. No network.
"""
import argparse, importlib.util, json, pathlib, statistics as st, sys

HERE = pathlib.Path(__file__).resolve().parent
def _load(n):
    sp = importlib.util.spec_from_file_location(n, HERE / f"{n}.py")
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m

PROTOCOL = ("STAMP.md", "variants/")
Q_POINTS, LAT_PCT, COST_PCT = 0.020, 0.25, 0.25


def rows(p):
    last = {}
    for line in pathlib.Path(p).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            last[(r.get("half", ""), r["item_id"], str(r.get("draw", 0)))] = r
    return list(last.values())


def per_item(rs):
    d = {}
    for r in rs:
        if r.get("verdict") in ("PASS", "FAIL"):
            d.setdefault(r["item_id"], []).append(1 if r["verdict"] == "FAIL" else 0)
    return d


def judge(base, cand):
    CMP, FC = _load("compare"), _load("footer_check")
    out, block = [], False
    a = CMP.analyse(per_item(base), per_item(cand))
    if a is None:
        return None, ["REFUSED - fewer than 5 shared graded items; quality cannot be judged"]
    rise = a["b_rate"] - a["a_rate"]
    q_bad = rise > Q_POINTS and a["lo"] > 0
    block |= q_bad
    out.append(f"  quality   fail {a['a_rate']:.1%} -> {a['b_rate']:.1%} ({rise:+.1%}); per-item "
               f"95% CI [{a['lo']:+.1%}, {a['hi']:+.1%}], {a['items']} items   "
               + ("BLOCK" if q_bad else "ok"))

    for label, key, pct, unit in (("latency", "latency_s", LAT_PCT, "s"),
                                  ("cost", "cost_model", COST_PCT, "$")):
        xa = [r[key] for r in base if isinstance(r.get(key), (int, float))]
        xb = [r[key] for r in cand if isinstance(r.get(key), (int, float))]
        if not xa or not xb:
            out.append(f"  {label:<9} UNMEASURED - not recorded in both runs"); continue
        f = st.median if key == "latency_s" else st.mean
        va, vb = f(xa), f(xb)
        bad = va > 0 and (vb - va) / va > pct
        block |= bad
        out.append(f"  {label:<9} {va:.4g}{unit} -> {vb:.4g}{unit} ({(vb - va) / va if va else 0:+.0%})   "
                   + ("BLOCK" if bad else "ok"))

    ta = [r["text"] for r in base if isinstance(r.get("text"), str) and r["text"].strip()]
    tb = [r["text"] for r in cand if isinstance(r.get("text"), str) and r["text"].strip()]
    if ta and tb:
        fa = sum(bool(FC.check(t)) for t in ta) / len(ta)
        fb = sum(bool(FC.check(t)) for t in tb) / len(tb)
        bad = fb > fa
        block |= bad
        out.append(f"  receipts  false or missing {fa:.1%} -> {fb:.1%}   " + ("BLOCK" if bad else "ok"))
    else:
        out.append("  receipts  UNMEASURED - reply text not in both runs (redacted or absent)")
    return block, out


def pr_mode(changed_file, evals):
    changed = [l.strip() for l in open(changed_file, encoding="utf-8") if l.strip()]
    touched = [c for c in changed if c == PROTOCOL[0] or c.startswith(PROTOCOL[1])]
    if not touched:
        print(f"PASS - no protocol file changed ({len(changed)} file(s) in the PR); "
              "nothing for the regression gate to measure")
        return 0
    print("protocol changed: " + ", ".join(touched))
    pairs = [d for d in sorted(pathlib.Path(evals).glob("*"))
             if (d / "baseline.jsonl").exists() and (d / "candidate.jsonl").exists()]
    if not pairs:
        print(f"BLOCK - the protocol changed and no measured pair is committed under {evals}/.")
        print("  Make the run locally on the public half (signed pre-registration first),")
        print("  redact it, and commit evals/<name>/baseline.jsonl and candidate.jsonl.")
        return 1
    worst = 0
    for d in pairs:
        print(f"{d.name}:")
        block, lines = judge(rows(d / "baseline.jsonl"), rows(d / "candidate.jsonl"))
        print("\n".join(lines))
        worst = max(worst, 2 if block is None else int(block))
    print("BLOCKED" if worst == 1 else "REFUSED" if worst == 2 else "PASS - no regression")
    return worst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline", nargs="?"); ap.add_argument("candidate", nargs="?")
    ap.add_argument("--pr"); ap.add_argument("--evals", default="evals")
    a = ap.parse_args()
    if a.pr:
        return pr_mode(a.pr, a.evals)
    if not (a.baseline and a.candidate):
        ap.error("give two run files, or --pr <changed files list>")
    block, lines = judge(rows(a.baseline), rows(a.candidate))
    print("\n".join(lines))
    if block is None:
        return 2
    print("BLOCKED" if block else "PASS - no regression")
    return int(block)


if __name__ == "__main__":
    sys.exit(main())
