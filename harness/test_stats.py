#!/usr/bin/env python3
"""
Verification for scripts/stats.py. No network, no cost.

    python scripts/test_stats.py     exit 0 = the intervals can be published

A confidence interval is a claim about how often you would be right. The only honest
way to check one is to simulate worlds where the truth is known and count how often
the interval covers it.

A coverage test has to aim at the right target, and the first version of this one did
not: it compared intervals from fresh banks against the rate of one PARTICULAR other
bank, and every method came out at 87% - which looked like broken statistics and was
really a broken test. The generating process below has an exact mean, and that is what
a "beyond the bank" interval is estimating. Being vague about the target is the same
error as publishing a rate without saying what it estimates.
"""
import collections, importlib.util, pathlib, random, statistics as st, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("stats", ROOT / "scripts" / "stats.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

fails = []


def check(name, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {name:<50} {detail}")
    if not ok:
        fails.append(name)


# --------------------------------------------------------------- 1. degenerate
print("1. EDGE CASES - a statistic that crashes on real data is not a statistic")
check("all items always fail", S.rate({f"i{i}": [1]*10 for i in range(20)})
      ["mean_over_draws"] == 1.0)
check("all items never fail", S.rate({f"i{i}": [0]*10 for i in range(20)})
      ["mean_over_draws"] == 0.0)
check("deterministic items -> zero on-bank SE",
      S.rate({f"i{i}": [1]*10 for i in range(20)})["se_on_bank"] == 0.0,
      "10/10 every time cannot be a sampling accident")
check("two items -> no beyond-bank interval",
      S.rate({"a": [1, 0], "b": [0, 1]})["beyond_bank_low"] is None)
r3 = S.rate({"a": [1, 0], "b": [0, 1], "c": [1, 1]})
check("three items -> beyond-bank appears", r3["beyond_bank_low"] is not None,
      f"[{r3['beyond_bank_low']:.0%}, {r3['beyond_bank_high']:.0%}]")
check("empty input returns None", S.rate({}) is None)

# ------------------------------------------------- 2. does the ICC behave right
print("\n2. ICC - near 0 when draws are independent, near 1 when clustered")
rnd = random.Random(1)
indep = {f"i{i}": [1 if rnd.random() < 0.4 else 0 for _ in range(10)] for i in range(60)}
clust = {f"i{i}": [1 if i < 24 else 0] * 10 for i in range(60)}
ri, rc = S.rate(indep), S.rate(clust)
check("independent draws -> ICC near 0", ri["icc"] < 0.15, f"ICC {ri['icc']:.3f}")
check("perfectly clustered -> ICC near 1", rc["icc"] > 0.90, f"ICC {rc['icc']:.3f}")

# ------------------------------------------------------------ 3. COVERAGE TEST
print("\n3. COVERAGE - two questions, so two separate coverage tests.")
print("   Each simulates 400 worlds where the truth is known and counts hits.")
print("   A 95% interval that does not cover ~95% of the time is not a 95% interval.\n")
rnd = random.Random(7)

def world():
    """63 items, each with its own true failure probability. U-shaped like nemotron."""
    out = []
    for _ in range(63):
        u = rnd.random()
        out.append(0.0 if u < 0.38 else 1.0 if u < 0.60 else rnd.uniform(0.15, 0.85))
    return out

# Q1's target: ONE fixed bank, reused every trial - the real situation, since bank
# v1 is 63 chosen items and not a sample of anything.
POP = world()
pop_rate = st.mean(POP)

# Q2's target: the EXACT mean of the generating process, not any one bank's rate.
#   0.38 x 0  +  0.22 x 1  +  0.40 x E[U(0.15,0.85)]  =  0.22 + 0.20  =  0.42
POP_MEAN = 0.42

hit_bank = hit_naive = 0
for _ in range(400):
    per = {f"i{j}": [1 if rnd.random() < p else 0 for _ in range(10)]
           for j, p in enumerate(POP)}
    r = S.rate(per)
    hit_bank += r["on_bank_low"] <= pop_rate <= r["on_bank_high"]
    n = 1.96 * r["se_naive"]
    hit_naive += abs(r["mean_over_draws"] - pop_rate) <= n
print(f"   Q1 ON THE BANK  (same 63 items every time, only draws resampled)")
print(f"      on-bank interval covered   {hit_bank/400:.1%}")
print(f"      naive interval covered     {hit_naive/400:.1%}   <- over-covers: too wide")
check("on-bank interval covers ~95%", 0.90 <= hit_bank/400 <= 0.99)
check("naive over-covers for this question", hit_naive/400 >= hit_bank/400)

hit_gen = hit_naive2 = 0
for _ in range(400):
    truth = world()                       # a NEW bank each time - generalising
    per = {f"i{j}": [1 if rnd.random() < p else 0 for _ in range(10)]
           for j, p in enumerate(truth)}
    r = S.rate(per)
    if r["beyond_bank_low"] is None:
        continue
    hit_gen += r["beyond_bank_low"] <= POP_MEAN <= r["beyond_bank_high"]
    n = 1.96 * r["se_naive"]
    hit_naive2 += abs(r["mean_over_draws"] - POP_MEAN) <= n
print(f"\n   Q2 BEYOND THE BANK  (a fresh draw of 63 items every time)")
print(f"      beyond-bank interval covered  {hit_gen/400:.1%}")
print(f"      naive interval covered        {hit_naive2/400:.1%}   <- under-covers: too narrow")
check("beyond-bank interval covers ~95%", 0.91 <= hit_gen/400 <= 0.99)
check("naive under-covers for this question", hit_naive2/400 < hit_gen/400)

# ------------------------------------------------------- 4. against real data
print("\n4. AGAINST THE REAL NEMOTRON RUN")
import json
per = collections.defaultdict(list)
ok_data = True
for h in ("A", "B"):
    p = ROOT / "pilot_out" / f"pilot_nemo_v1_{h}.jsonl"
    if not p.exists():
        ok_data = False
        break
    latest = {}
    for l in p.read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            latest[(r["item_id"], r["draw"])] = r
    for r in latest.values():
        if r["verdict"] in ("PASS", "FAIL"):
            per[r["item_id"]].append(1 if r["verdict"] == "FAIL" else 0)
if ok_data:
    r = S.rate(per)
    print(S.explain(r, "   "))
    check("on-bank is narrower than beyond-bank",
          (r["on_bank_high"] - r["on_bank_low"]) <
          (r["beyond_bank_high"] - r["beyond_bank_low"]))
else:
    print("   (nemotron data not present here - skipped)")

print("\n" + "=" * 66)
if fails:
    print(f"{len(fails)} CHECK(S) FAILED: {', '.join(fails)}")
    sys.exit(1)
print("ALL CHECKS PASSED - these intervals are safe to publish, WITH their scope.")
