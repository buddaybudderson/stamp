#!/usr/bin/env python3
"""
Test-retest reliability between two independent halves of the same arm.

This is the number almost no public benchmark reports about itself. It answers:
if we ran the identical thing again, how much would the answer move?

Run after both halves complete:  python scripts/reliability.py <candidate>
"""
import importlib.util, json, math, pathlib, sys, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT  = ROOT / "pilot_out"

# Shared statistics - one implementation, so a rate published here and a rate
# published anywhere else carry the same interval computed the same way.
_sp = importlib.util.spec_from_file_location("stats", ROOT / "scripts" / "stats.py")
S = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(S)


def _per_item(raw, items):
    d = collections.defaultdict(list)
    for r in raw.values():
        if r["verdict"] in ("PASS", "FAIL") and r["item_id"] in items:
            d[r["item_id"]].append(1 if r["verdict"] == "FAIL" else 0)
    return dict(d)

def load(p):
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    latest = {}
    for r in rows:
        latest[(r["item_id"], r["draw"])] = r
    d = collections.defaultdict(list)
    for r in latest.values():
        if r["verdict"] in ("PASS", "FAIL"):
            d[r["item_id"]].append(r["verdict"])
    return {k: (sum(1 for x in v if x == "FAIL"), len(v)) for k, v in d.items()}, latest

cand = sys.argv[1] if len(sys.argv) > 1 else "nemo_v1"
A, rawA = load(OUT / f"pilot_{cand}_A.jsonl")
B, rawB = load(OUT / f"pilot_{cand}_B.jsonl")
items = sorted(set(A) & set(B))

fa = sum(A[i][0] for i in items) / sum(A[i][1] for i in items)
fb = sum(B[i][0] for i in items) / sum(B[i][1] for i in items)

print("=" * 68)
print(f"TEST-RETEST RELIABILITY - {cand}, bank v1, {len(items)} items")
print("=" * 68)
sa = S.rate(_per_item(rawA, set(items)))
sb = S.rate(_per_item(rawB, set(items)))
pooled = _per_item(rawA, set(items))
for k, v in _per_item(rawB, set(items)).items():
    pooled.setdefault(k, []).extend(v)
sp_ = S.rate(pooled)

print(f"\n  half A failure rate   {fa:.1%}   on-bank 95% CI "
      f"[{sa['on_bank_low']:.1%}, {sa['on_bank_high']:.1%}]")
print(f"  half B failure rate   {fb:.1%}   on-bank 95% CI "
      f"[{sb['on_bank_low']:.1%}, {sb['on_bank_high']:.1%}]")
print(f"  aggregate gap         {abs(fa-fb):.1%}   <- the noise floor")
print(f"\n  POOLED, and this is what a report quotes:")
print(S.explain(sp_, "    "))
print("    NOTE the two intervals answer different questions. Week-on-week")
print("    comparison uses ON BANK. Any claim about the model uses BEYOND.")

# per-item stability against the >=20% threshold
flip = [i for i in items if (A[i][0]/A[i][1] >= 0.2) != (B[i][0]/B[i][1] >= 0.2)]
stable_fail = [i for i in items if A[i][0]/A[i][1] >= 0.2 and B[i][0]/B[i][1] >= 0.2]
stable_pass = [i for i in items if A[i][0]/A[i][1] < 0.2 and B[i][0]/B[i][1] < 0.2]
print(f"\n  items failing in BOTH halves   {len(stable_fail):>3}  <- the usable bank")
print(f"  items passing in BOTH halves   {len(stable_pass):>3}  <- solved, retire or keep as control")
print(f"  items that FLIP                {len(flip):>3}  = {len(flip)/len(items):.0%} unstable")

# pooled estimate and a binomial interval per item
print(f"\n  mean |per-item shift|  "
      f"{sum(abs(A[i][0]/A[i][1] - B[i][0]/B[i][1]) for i in items)/len(items):.1%}")

# Pearson correlation of the two halves' item rates
xs = [A[i][0]/A[i][1] for i in items]; ys = [B[i][0]/B[i][1] for i in items]
mx, my = sum(xs)/len(xs), sum(ys)/len(ys)
num = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
den = math.sqrt(sum((x-mx)**2 for x in xs) * sum((y-my)**2 for y in ys))
r = num/den if den else 0
print(f"  half-to-half correlation  r = {r:.3f}   (Spearman-Brown full-test r = {2*r/(1+r):.3f})")

if flip:
    print(f"\n  the {len(flip)} unstable items - do NOT publish a per-item verdict for these:")
    for i in flip:
        print(f"    {i:<34} A {A[i][0]}/{A[i][1]}   B {B[i][0]}/{B[i][1]}")

print("\n" + "-" * 68)
print("PUBLISHABLE BANK: items whose verdict repeats across both halves")
print(f"  {len(stable_fail)} discriminating + {len(stable_pass)} solved = {len(stable_fail)+len(stable_pass)} of {len(items)}")
print("-" * 68)

pathlib.Path(OUT / f"reliability_{cand}.json").write_text(json.dumps({
    "candidate": cand, "n_items": len(items),
    "half_a_rate": fa, "half_b_rate": fb, "gap": abs(fa-fb),
    "pooled": sp_, "half_a_stats": sa, "half_b_stats": sb,
    "correlation": r, "spearman_brown": 2*r/(1+r) if r else 0,
    "stable_fail": stable_fail, "stable_pass": stable_pass, "unstable": flip,
}, indent=2), encoding="utf-8")
print(f"wrote reliability_{cand}.json")
