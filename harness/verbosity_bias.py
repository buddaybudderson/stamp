"""DOES A JUDGE REWARD LENGTH? Verbosity bias, measured on verdicts already on disk.

    python scripts/verbosity_bias.py luna_v1
    python scripts/verbosity_bias.py nemo_v1

  exit 0 = no length effect the data can detect    exit 1 = a judge's verdicts track length
  exit 2 = refused (too few contested items to test anything)

WHY THIS AND NOT A REGRESSION ON LENGTH. Long answers and short answers are not asked the
same questions: a provenance probe draws long replies and an arithmetic probe short ones,
and the items differ in how often they fail. Pool them and "length predicts PASS" is just
"which item it was". So the test runs WITHIN ITEMS: on an item where the same judge passed
some draws and failed others, were the passed draws longer? Items a judge called the same
way on every draw carry no information about length and are dropped, and the count kept is
printed - a test over three items is not a finding and the script refuses it.

THE STATISTIC. For each contested item: mean log-length of PASS draws minus FAIL draws.
Averaged over items. Its null distribution comes from shuffling the verdicts WITHIN each
item (same number of PASS per item, lengths fixed), 4000 times, seed fixed. Log length
because a 2,000-character reply is not ten times the evidence of a 200-character one.

THE HUMAN ANCHOR. Where Calibration Vol 003's blind human labels exist, the sharper
question is asked too: on draws where judge and person disagree, is the judge's PASS on
the longer reply? That is verbosity bias in the only sense that matters - leniency the
person did not share - rather than "longer answers are better", which can be true.

Position bias does not apply: every judge here grades one response at a time.
Self-preference is handled by recusal in panel_grade.py, not measured here.
Stdlib only. No network. No bank text is printed.
"""
import collections, json, math, pathlib, random, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT, PANEL = ROOT / "pilot_out", ROOT / "panel_out"
HUMAN = ROOT / "reports" / "human_labels_cal003.jsonl"
HUMAN_CAND = "luna_v1"   # the labels were made on panel_luna_v1's sample and on nothing else
MIN_ITEMS = 6


def jl(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def lengths(cand):
    """(item, half, draw) -> chars of the candidate's reply, latest row wins."""
    L = {}
    for half in ("A", "B"):
        p = OUT / f"pilot_{cand}_{half}.jsonl"
        if p.exists():
            for r in jl(p):
                n = r.get("chars") or len(r.get("text") or "")
                L[(r["item_id"], half, str(r["draw"]))] = int(n)
    return L


def verdict_sets(cand, L):
    """judge label -> list of (item, key, PASS?) . Tier-1 grader plus every panel judge."""
    out = collections.defaultdict(list)
    meta = PANEL / f"panel_{cand}.json"
    t1 = json.loads(meta.read_text(encoding="utf-8")).get("tier1_grader") if meta.exists() else None
    TIER1 = f"tier-1 ({t1})" if t1 else "tier-1 (grader not recorded)"
    for half in ("A", "B"):
        p = OUT / f"pilot_{cand}_{half}.jsonl"
        if p.exists():
            last = {}
            for r in jl(p):
                last[(r["item_id"], half, str(r["draw"]))] = r["verdict"]
            for k, v in last.items():
                if v in ("PASS", "FAIL") and k in L:
                    out[TIER1].append((k[0], k, v == "PASS"))
    for name in (f"panel_{cand}.jsonl", f"decision_jev_{cand}.jsonl", f"decision_laya_{cand}.jsonl"):
        p = PANEL / name
        if not p.exists():
            continue
        for r in jl(p):
            if str(r.get("rep", "0")) != "0":
                continue
            k = (r["item_id"], r["half"], str(r["draw"]))
            if r.get("verdict") in ("PASS", "FAIL") and k in L:
                out[f"{r['judge']} ({r['model']})"].append((k[0], k, r["verdict"] == "PASS"))
    return out


def within_item(rows, L, iters=4000, seed=20261005):
    by = collections.defaultdict(list)
    for item, k, p in rows:
        by[item].append((math.log1p(L[k]), p))
    groups = [g for g in by.values() if 0 < sum(p for _, p in g) < len(g)]
    if len(groups) < MIN_ITEMS:
        return None, len(groups)

    def stat(gs):
        d = []
        for g in gs:
            a = [x for x, p in g if p]; b = [x for x, p in g if not p]
            d.append(sum(a) / len(a) - sum(b) / len(b))
        return sum(d) / len(d)

    obs = stat(groups)
    rnd = random.Random(seed)
    hits = 0
    for _ in range(iters):
        sh = []
        for g in groups:
            ps = [p for _, p in g]; rnd.shuffle(ps)
            sh.append([(x, p) for (x, _), p in zip(g, ps)])
        if abs(stat(sh)) >= abs(obs) - 1e-12:
            hits += 1
    return {"effect": obs, "ratio": math.exp(obs), "p": (hits + 1) / (iters + 1),
            "items": len(groups), "draws": sum(len(g) for g in groups)}, len(groups)


def human_check(sets, L, cand):
    # Keys are (item, half, draw) and every candidate's run reuses them, so labels made on
    # one candidate's replies would silently join to another's. Only the labelled run counts.
    if cand != HUMAN_CAND or not HUMAN.exists():
        return {}
    hum = {(r["item_id"], r["half"], str(r["draw"])): r["label"] == "PASS" for r in jl(HUMAN)}
    res = {}
    for judge, rows in sets.items():
        lenient, strict = [], []
        for item, k, p in rows:
            if k in hum and p != hum[k]:
                (lenient if p else strict).append(L[k])
        if lenient or strict:
            res[judge] = (lenient, strict)
    return res


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__.split("\n\n")[1])
    cand = sys.argv[1]
    L = lengths(cand)
    if not L:
        print(f"REFUSED - no pilot_{cand}_A/B run files with reply lengths")
        return 2
    sets = verdict_sets(cand, L)
    print("=" * 78)
    print(f"VERBOSITY BIAS - {cand}   ({len(L)} replies with a known length)")
    print("=" * 78)
    print(f"  {'judge':<44}{'items':>6}{'draws':>7}{'PASS/FAIL len':>15}{'p':>8}")
    flagged, tested = [], 0
    for judge, rows in sorted(sets.items()):
        r, n = within_item(rows, L)
        if r is None:
            print(f"  {judge[:43]:<44}{n:>6}{'':>7}{'too few contested items':>23}")
            continue
        tested += 1
        mark = "  <- tracks length" if r["p"] < 0.05 else ""
        print(f"  {judge[:43]:<44}{r['items']:>6}{r['draws']:>7}{r['ratio']:>14.2f}x"
              f"{r['p']:>8.3f}{mark}")
        if r["p"] < 0.05:
            flagged.append((judge, r))
    hc = human_check(sets, L, cand)
    if hc:
        print("-" * 78)
        print("  AGAINST THE PERSON (Calibration Vol 003 blind labels) - where they disagree:")
        print(f"  {'judge':<44}{'lenient n':>10}{'median len':>11}{'strict n':>9}{'median len':>11}")
        med = lambda xs: sorted(xs)[len(xs) // 2] if xs else float("nan")
        for judge, (le, st) in sorted(hc.items()):
            print(f"  {judge[:43]:<44}{len(le):>10}{med(le):>11.0f}{len(st):>9}{med(st):>11.0f}")
        print("  lenient = judge PASS where the person said FAIL. If lenient replies run long")
        print("  and strict ones short, the judge's leniency is a length effect.")
    print("-" * 78)
    if not tested:
        print("REFUSED - no judge had enough contested items to test. Unmeasured, not clean.")
        return 2
    if flagged:
        print("LENGTH EFFECT DETECTED for: " + ", ".join(j for j, _ in flagged))
        print("  Within the same item, this judge's PASS draws are longer than its FAIL draws")
        print("  by more than shuffling produces. Not yet bias: check the human column first.")
        return 1
    print(f"NO LENGTH EFFECT DETECTED across {tested} judge(s), within items, p >= 0.05.")
    print("  'Not detected' is bounded by the contested-item counts above; it is not 'absent'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
