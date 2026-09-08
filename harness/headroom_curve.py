#!/usr/bin/env python3
"""
Read every pilot_summary_*.json and print the headroom curve.

The curve is the product. "Does STAMP win" is a yes/no that goes stale. "Here is
how much room each model has left, on what kind of task" is a series that compounds
and that nobody else publishes.

A model at ceiling on this bank is a data point, not a dead end.
"""
import json, pathlib, sys

OUT = pathlib.Path(__file__).resolve().parent.parent / "pilot_out"
BASE_2025 = 0.467   # v1.25: 49 native failures / 105 model-item pairs, 3 models

rows = []
for p in sorted(OUT.glob("pilot_summary_*.json")):
    d = json.loads(p.read_text(encoding="utf-8"))
    fr = d["fail_rates"]
    if not fr:
        continue
    cats = {}
    for iid, v in fr.items():
        cats.setdefault(iid.rsplit("_", 1)[0], []).append(v)
    rows.append(dict(
        label=p.stem.replace("pilot_summary_", ""),
        model=d["candidate"],
        mean=sum(fr.values()) / len(fr),
        kept=len(d["kept"]),
        n=len(fr),
        unusable=d.get("unusable", 0),
        providers=d.get("providers", {}),
        cats={c: sum(v) / len(v) for c, v in cats.items()},
    ))

if not rows:
    sys.exit(f"no pilot summaries found in {OUT}")

rows.sort(key=lambda r: -r["mean"])

print("=" * 78)
print("HEADROOM CURVE - native failure rate on the v1.25 discriminating bank")
print("=" * 78)
print(f"\n{'model':<38}{'fail':>8}{'kept':>7}{'of':>5}{'bad':>6}  providers")
print("-" * 78)
for r in rows:
    prov = ",".join(r["providers"]) if len(r["providers"]) <= 2 else f"{len(r['providers'])} DIFFERENT"
    flag = "  <-- PIN" if len(r["providers"]) > 1 else ""
    print(f"{r['model']:<38}{r['mean']:>7.1%}{r['kept']:>7}{r['n']:>5}{r['unusable']:>6}  {prov}{flag}")
print("-" * 78)
print(f"{'2025 baseline (3 models, v1.25)':<38}{BASE_2025:>7.1%}")

allcats = sorted({c for r in rows for c in r["cats"]})
print(f"\n\nBY CATEGORY\n{'category':<28}" + "".join(f"{r['label'][:11]:>12}" for r in rows))
print("-" * (28 + 12 * len(rows)))
for c in allcats:
    line = f"{c:<28}"
    for r in rows:
        v = r["cats"].get(c)
        line += f"{'-':>12}" if v is None else f"{v:>11.0%} "
    print(line)

print("\n\nREADING THIS")
best = rows[0]
if best["mean"] < 0.20:
    print(f"  Every model tested is at or near ceiling (top is {best['model']} at {best['mean']:.1%}).")
    print("  The bank cannot measure a protocol here. Two moves, both cheap:")
    print("    1. harder items - categories 14/15 target the gaps this run exposed")
    print("    2. weaker candidates - if nothing has headroom, the claim has no market")
else:
    print(f"  {best['model']} still fails {best['mean']:.1%}. That is measurable headroom -")
    print("  run the v1.70 arm against it and the comparison will resolve.")
print("\n  A category at 0% across every model is SOLVED. Retire it from the bank and")
print("  say so publicly - a benchmark that keeps scoring solved tasks inflates itself.")
