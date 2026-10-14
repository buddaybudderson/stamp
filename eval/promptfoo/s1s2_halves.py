#!/usr/bin/env python3
"""READ BOTH HALVES OF THE SYSTEM 1 vs SYSTEM 2 RUN TOGETHER. analyze_s1s2.py reads one half; this adds
what the pre-registration asks of two (paper/PREREG_system1_vs_system2.md):

    python3 s1s2_halves.py results.s1s2.A.json results.s1s2.B.json [--json]

  per row   the STAMP effect in each half, the RETEST GAP |effect A - effect B| (the row's noise floor),
            and the pooled effect: each probe's stamp-minus-native difference averaged over the two
            halves, then the same paired bootstrap and sign-flip test as analyze_s1s2.py
  Q3        pooled (s2 effect) minus (s1 effect), paired by probe, within each model
  Q4        share of STAMP replies failing footer_check.py R1-R10, both halves, and s2 minus s1 within
            each model, paired by probe
  tokens    mean reasoning tokens per reply, per row (a "-s1" row must be 0)

Same rules as analyze_s1s2.py: content criterion only, install canaries dropped, a "-s1" row that
reasoned is refused, seeds fixed. Errored items (failureReason 2, e.g. a provider's HTTP 403) carry no
verdict and drop out of the pairing; they are counted per row. Stdlib only. No network.
"""
import argparse, importlib.util, json, pathlib, random, sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("analyze_s1s2", HERE / "analyze_s1s2.py")
an = importlib.util.module_from_spec(spec)
spec.loader.exec_module(an)


def read(path, fc, version):
    cell, bad, rtok, errored = {}, {}, {}, {}
    for r in an.rows_of(json.loads(pathlib.Path(path).read_text(encoding="utf-8"))):
        label = (r.get("provider") or {}).get("label")
        cond = (r.get("prompt") or {}).get("label")
        v = r.get("vars") or {}
        probe = v.get("_probe")
        if label is None or cond not in ("native", "stamp") or probe is None or an.is_canary(v.get("probe")):
            continue
        if r.get("failureReason") == 2:
            errored[label] = errored.get(label, 0) + 1
            continue
        ok = an.content_pass(r)
        if ok is None:
            continue
        cell.setdefault(label, {}).setdefault(cond, {})[probe] = ok
        rtok.setdefault(label, []).append(an.reasoning_tokens(r))
        if cond == "stamp":
            out = (r.get("response") or {}).get("output")
            if isinstance(out, str):
                bad.setdefault(label, {})[probe] = bool(fc.check(out, None, version))
    return cell, bad, rtok, errored


def diffs(cell, label):
    n, s = cell[label].get("native", {}), cell[label].get("stamp", {})
    return {p: (not s[p]) - (not n[p]) for p in set(n) & set(s)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("half_a")
    ap.add_argument("half_b")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--receipt-version", default="v1.25")
    a = ap.parse_args()
    fc = an.load_footer_check()
    rng = random.Random(an.SEED)
    A = read(a.half_a, fc, a.receipt_version)
    B = read(a.half_b, fc, a.receipt_version)

    reasoned = [lb for H in (A, B) for lb, t in H[2].items() if lb.endswith("-s1") and any(t)]
    if reasoned:
        print("REFUSED - System 1 rows reported reasoning tokens:", sorted(set(reasoned)))
        return 2

    labels = sorted(set(A[0]) & set(B[0]))
    rep = {"rows": {}, "q3": {}, "q4": {}}
    for lb in labels:
        da, db = diffs(A[0], lb), diffs(B[0], lb)
        common = sorted(set(da) & set(db))
        ea = sum(da[p] for p in common) / len(common)
        eb = sum(db[p] for p in common) / len(common)
        nat = [(not A[0][lb]["native"][p]) + (not B[0][lb]["native"][p]) for p in common]
        st = [(not A[0][lb]["stamp"][p]) + (not B[0][lb]["stamp"][p]) for p in common]
        badr = [x for H in (A, B) for x in H[1].get(lb, {}).values()]
        toks = A[2][lb] + B[2][lb]
        rep["rows"][lb] = {
            "probes": len(common),
            "errored_items": A[3].get(lb, 0) + B[3].get(lb, 0),
            "native_fail": sum(nat) / (2 * len(common)),
            "stamp_fail": sum(st) / (2 * len(common)),
            "effect_a": ea, "effect_b": eb, "retest_gap": abs(ea - eb),
            "pooled": an.paired([(da[p] + db[p]) / 2 for p in common], rng),
            "bad_receipt": sum(badr) / len(badr) if badr else None, "receipts_checked": len(badr),
            "mean_reasoning_tokens": sum(toks) / len(toks) if toks else 0,
        }
    for lb in labels:
        if not lb.endswith("-s1") or lb[:-3] + "-s2" not in labels:
            continue
        s2 = lb[:-3] + "-s2"
        e1 = {p: (v + diffs(B[0], lb).get(p, v)) / 2 for p, v in diffs(A[0], lb).items()}
        e2 = {p: (v + diffs(B[0], s2).get(p, v)) / 2 for p, v in diffs(A[0], s2).items()}
        common = sorted(set(e1) & set(e2) & set(diffs(B[0], lb)) & set(diffs(B[0], s2)))
        rep["q3"][lb[:-3]] = an.paired([e2[p] - e1[p] for p in common], rng)
        b1 = {p: (A[1][lb].get(p, 0) + B[1][lb].get(p, 0)) / 2 for p in set(A[1][lb]) & set(B[1][lb])}
        b2 = {p: (A[1][s2].get(p, 0) + B[1][s2].get(p, 0)) / 2 for p in set(A[1][s2]) & set(B[1][s2])}
        cp = sorted(set(b1) & set(b2))
        rep["q4"][lb[:-3]] = an.paired([b2[p] - b1[p] for p in cp], rng)

    if a.json:
        print(json.dumps(rep, indent=1))
        return 0
    f = lambda e: f"{100*e['mean']:+6.1f} [{100*e['lo']:+.1f}, {100*e['hi']:+.1f}] p={e['p']:.3f}"
    print("Both halves. Points = stamp fail rate minus native, paired by probe. Gap = |A - B|.")
    print(f"{'row':17} {'n':>3} {'err':>3} {'native':>7} {'stamp':>7} {'half A':>7} {'half B':>7} {'gap':>5}   pooled [95% CI]                 bad rcpt  reason tok")
    for lb, v in rep["rows"].items():
        print(f"{lb:17} {v['probes']:3} {v['errored_items']:3} {100*v['native_fail']:6.1f}% {100*v['stamp_fail']:6.1f}% "
              f"{100*v['effect_a']:+7.1f} {100*v['effect_b']:+7.1f} {100*v['retest_gap']:5.1f}   {f(v['pooled']):32} "
              f"{100*v['bad_receipt']:5.1f}%  {v['mean_reasoning_tokens']:8.0f}")
    print("\nQ3  pooled STAMP effect with reasoning on minus off (points)")
    for m, e in rep["q3"].items():
        print(f"  {m:10} {f(e)}  n={e['n']}")
    print("\nQ4  bad-receipt share with reasoning on minus off (points)")
    for m, e in rep["q4"].items():
        print(f"  {m:10} {f(e)}  n={e['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
