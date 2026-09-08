#!/usr/bin/env python3
"""
The fever measurement.

    fever = failure rate at temperature 0.7  -  failure rate at temperature 0

Temperature is the thermometer, not the fever. The reading is the GAP between what
a model does at its best (greedy, temp 0) and what it does when sampled the way it
is actually deployed (temp 0.7).

  low fever   what you see on a leaderboard is what users get
  high fever  the model tops the board and then misbehaves for a share of real users

Nobody publishes this. It requires both temperatures to exist, which is why it is
worth the extra 20% of run cost.

THE ASSUMPTION THIS TOOL WAS BUILT ON IS FALSE, AND MEASURING IT IS WHY.

  Designed on 2026-08-29 believing temperature 0 gives "the model's modal answer,
  its best behaviour" - a fixed point to measure the 0.7 rate against. Then two
  temp-0 runs of the same 63 prompts, same pinned provider, same model:

      56 of 63 responses (89%) DIFFERED
      median shared prefix 92 characters before diverging
      failure rate 44.3% in one run, 41.0% in the other - 3.4 points apart

  Temperature 0 is not a fixed point on a production endpoint. It is a
  lower-variance sampling regime. So this tool now measures temp 0's OWN run-to-run
  spread first and refuses to report a fever smaller than it: a gap of 0.7 points
  against a baseline that moves 3.4 points is not a reading, it is arithmetic.

  Two temp-0 runs whose TEXT differs are the serving stack - floating point,
  batching, MoE routing. Two whose text is IDENTICAL but whose verdicts differ are
  the grader. The stored response text separates them, and the split matters: on
  nemotron it was 5 serving-stack against 1 grader.

  One alternative this cannot rule out from the client side: a provider may
  implement temperature=0 as near-zero sampling rather than true argmax, and no
  seed parameter is sent. Either way the practical consequence is identical - a
  temp-0 score is not reproducible by re-running it.

  python scripts/fever.py <candidate> [<candidate> ...]
"""
import collections, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "pilot_out"


def load(stem):
    """Pool both halves. Returns {item: (fails, n)} and the raw rows."""
    per = collections.defaultdict(list)
    raw = []
    for half in ("A", "B"):
        p = OUT / f"pilot_{stem}_{half}.jsonl"
        if not p.exists():
            continue
        latest = {}
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                latest[(r["item_id"], r["draw"])] = r
        for (iid, _), r in latest.items():
            raw.append(r)
            if r["verdict"] in ("PASS", "FAIL"):
                per[iid].append(r["verdict"])
    return {k: (sum(1 for x in v if x == "FAIL"), len(v)) for k, v in per.items()}, raw


def _half_rate(stem, half):
    """Failure rate of ONE temp-0 half, so the two can be compared with each other."""
    p = OUT / f"pilot_{stem}_{half}.jsonl"
    if not p.exists():
        return None
    latest = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            latest[(r["item_id"], r["draw"])] = r
    v = [r["verdict"] for r in latest.values() if r["verdict"] in ("PASS", "FAIL")]
    return (sum(1 for x in v if x == "FAIL") / len(v)) if v else None


def rate(d):
    tot = sum(n for _, n in d.values())
    return (sum(f for f, _ in d.values()) / tot) if tot else None


cands = sys.argv[1:]
if not cands:
    sys.exit("usage: python scripts/fever.py <candidate> [<candidate> ...]")

print("=" * 74)
print("FEVER CHART - deployed behaviour minus best behaviour")
print("=" * 74)
print(f"\n{'model':<24}{'temp 0':>9}{'temp 0.7':>10}{'FEVER':>9}{'items':>7}   reading")
print("-" * 74)

rows = []
for c in cands:
    hot, hot_raw = load(c)              # temp 0.7 keeps the bare stem
    cold, cold_raw = load(f"{c}_t0")    # temp 0 carries the _t0 suffix
    rh, rc = rate(hot), rate(cold)
    if rh is None or rc is None:
        missing = "temp 0.7" if rh is None else "temp 0"
        print(f"{c:<24}{'':>9}{'':>10}{'':>9}{'':>7}   no {missing} data yet")
        continue
    fev = rh - rc
    # THE FLOOR IS NOT FIXED, SO MEASURE HOW MUCH IT MOVES. The two temp-0 halves
    # are two runs of the same prompts; their gap is the smallest fever this
    # instrument can distinguish from its own noise.
    floor_noise = None
    ra = _half_rate(f"{c}_t0", "A")
    rb = _half_rate(f"{c}_t0", "B")
    if ra is not None and rb is not None:
        floor_noise = abs(ra - rb)
    if floor_noise is not None and abs(fev) <= floor_noise:
        read = (f"NOT MEASURABLE - temp 0 itself moves {floor_noise:.1%} between "
                f"runs, more than this gap")
    else:
        read = ("normal" if abs(fev) < 0.05 else
                "MILD" if abs(fev) < 0.15 else
                "HIGH - sampled behaviour diverges sharply")
        if fev < -0.05:
            read = "INVERTED - worse at its best than when sampled"
    rows.append((c, rc, rh, fev, len(hot)))
    print(f"{c:<24}{rc:>8.1%}{rh:>10.1%}{fev:>+9.1%}{len(hot):>7}   {read}")
    if floor_noise is not None:
        print(f"{'':<24}{'':>8}{'':>10}{'':>9}{'':>7}   temp-0 halves: "
              f"{ra:.1%} vs {rb:.1%}, spread {floor_noise:.1%}")

# --- infrastructure nondeterminism: temp-0 draws that disagree ---------------
print("\n" + "-" * 74)
print("INFRASTRUCTURE NONDETERMINISM - temp-0 draws of the same item that disagree")
print("  greedy decoding has no sampling, so any disagreement here is the serving")
print("  stack, not the model: floating point, batching, or MoE routing.")
print("-" * 74)
for c in cands:
    cold, cold_raw = load(f"{c}_t0")
    if not cold:
        continue
    split = [(i, f, n) for i, (f, n) in cold.items() if n > 1 and 0 < f < n]
    provs = collections.Counter(r.get("served_by", "?") for r in cold_raw)
    flag = "  <-- pin the provider" if len(provs) > 1 else ""

    # A VERDICT FLIP IS NOT PROOF OF SERVING-STACK DRIFT. Identical text graded
    # differently is the GRADER. Separate them with the stored response, and count
    # the text changes too - most differing responses never flip a verdict, so
    # counting only flips understates the instability by an order of magnitude.
    texts = collections.defaultdict(dict)
    for r in cold_raw:
        texts[r["item_id"]][r.get("_half", "?")] = r.get("text") or ""
    ta, tb = {}, {}
    for half, d in (("A", ta), ("B", tb)):
        p = OUT / f"pilot_{c}_t0_{half}.jsonl"
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    d[r["item_id"]] = (r.get("text") or "", r["verdict"])
    both = set(ta) & set(tb)
    changed = [i for i in both if ta[i][0] != tb[i][0]]
    flip_stack = [i for i in both if ta[i][1] != tb[i][1]
                  and ta[i][1] in ("PASS", "FAIL") and tb[i][1] in ("PASS", "FAIL")
                  and ta[i][0] != tb[i][0]]
    flip_grader = [i for i in both if ta[i][1] != tb[i][1]
                   and ta[i][1] in ("PASS", "FAIL") and tb[i][1] in ("PASS", "FAIL")
                   and ta[i][0] == tb[i][0]]
    print(f"  {c:<22} providers: {dict(provs)}{flag}")
    if both:
        print(f"      RESPONSES THAT DIFFER between two greedy runs   "
              f"{len(changed):>3} of {len(both):>3} ({len(changed)/len(both):.0%})")
        print(f"        this is the real instability figure - most text changes")
        print(f"        never flip a verdict, so counting flips alone hides it")
        print(f"      verdict flips WITH a text change (serving stack) {len(flip_stack):>3}")
        print(f"      verdict flips with IDENTICAL text (the grader)   {len(flip_grader):>3}")
        for i in flip_grader:
            print(f"          {i:<40} same text, different verdict")

print("\n" + "=" * 74)
print("A fever is not a defect. It is a property, and it is one nobody else records.")
print("Track it per model per week; the interesting signal is when it CHANGES.")
