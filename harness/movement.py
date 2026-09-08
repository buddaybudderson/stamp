#!/usr/bin/env python3
"""
IS THE CHANGE REAL? The gate a fortnightly series cannot run without.

    python scripts/movement.py nemo_v1 nemo_v1_t0
    python scripts/movement.py <earlier> <later> --floor 0.016

  exit 0 = the movement is reportable    exit 1 = it is noise, say so and move on

THE PROBLEM THIS EXISTS FOR. A Calibration on a fixed cadence has to produce an
issue whether or not anything happened. On a quiet fortnight the temptation is not
to pad - padding is obvious and harmless - it is to promote a 0.7-point wobble to a
finding, because an issue with a finding feels like a better issue. Do that twice
and the series is worthless, because a reader can no longer tell which movements
were real.

So the calendar does not get to decide what counts as movement. This does.

  1. PAIRED AT THE ITEM LEVEL. The two runs share a bank, so comparing the two
     aggregate rates throws away the pairing and inflates the variance. Each item
     is its own comparison and the test is over item-level differences.
  2. AGAINST THE MEASURED NOISE FLOOR, not against zero. reliability.py measures
     what this instrument does when NOTHING changes - nemotron's two halves landed
     1.6 points apart on identical conditions. A gap smaller than that is not a
     small effect, it is the instrument idling.
  3. TWO INTERVALS, AS EVERYWHERE ELSE. On-bank answers "did this model move on
     this bank"; that is the week-on-week question and the one a reading asks.
     Beyond-bank is for claims about the model and is deliberately much wider.

"NOTHING MOVED" IS A COMPLETE ISSUE. It is not a failed one. A reference series
earns its authority from the readings where it reports that the number held, and a
programme that can only publish when something is interesting has stopped measuring
and started looking for stories.
"""
import argparse, collections, importlib.util, json, math, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "pilot_out"
_sp = importlib.util.spec_from_file_location("stats", ROOT / "scripts" / "stats.py")
S = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(S)


def load(cand):
    """Item -> list of 0/1 across every half of a candidate's run."""
    per = collections.defaultdict(list)
    latest, files = {}, []
    for half in ("A", "B", ""):
        p = OUT / (f"pilot_{cand}_{half}.jsonl" if half else f"pilot_{cand}.jsonl")
        if p.exists():
            files.append(p)
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    latest[(p.name, r["item_id"], r["draw"])] = r
    for r in latest.values():
        if r["verdict"] in ("PASS", "FAIL"):
            per[r["item_id"]].append(1 if r["verdict"] == "FAIL" else 0)
    return dict(per), files


def noise_floor(cand):
    """The retest gap this instrument produced on identical conditions."""
    p = OUT / f"reliability_{cand}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))["gap"], str(p.name)
    return None, None


def paired(a, b):
    """Item-level differences over the shared bank, later minus earlier."""
    shared = sorted(set(a) & set(b))
    return shared, [sum(b[i]) / len(b[i]) - sum(a[i]) / len(a[i]) for i in shared]


def boot(diffs, iters=4000, conf=0.95, seed=20260830):
    """Cluster bootstrap over items - the items are the sampling unit, not draws."""
    import random
    rnd = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(iters):
        s = [diffs[rnd.randrange(n)] for _ in range(n)]
        means.append(sum(s) / n)
    means.sort()
    return (means[int((1 - conf) / 2 * iters)], means[int((1 + conf) / 2 * iters) - 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("earlier")
    ap.add_argument("later")
    ap.add_argument("--floor", type=float, default=None,
                    help="noise floor as a rate; default is the measured retest gap")
    a = ap.parse_args()

    A, fa = load(a.earlier)
    B, fb = load(a.later)
    if not A or not B:
        sys.exit(f"no usable draws for {a.earlier if not A else a.later}")

    ra, rb = S.rate(A), S.rate(B)
    shared, diffs = paired(A, B)
    if not shared:
        sys.exit("the two runs share no items - there is nothing to compare")

    # TWO CHANGES, AND THEY ARE NOT THE SAME NUMBER. The item-level mean weights
    # every item equally; the aggregate weights by draws, and items carry 4 or 5.
    # reliability.py's noise floor is an AGGREGATE gap, so it may only be compared
    # with an aggregate change - the first version of this script tested the
    # item-level change against it and was comparing two different estimands.
    delta = sum(diffs) / len(diffs)                      # item-level, matches the CI
    agg_a = sum(sum(A[i]) for i in shared) / sum(len(A[i]) for i in shared)
    agg_b = sum(sum(B[i]) for i in shared) / sum(len(B[i]) for i in shared)
    delta_agg = agg_b - agg_a                            # aggregate, matches the floor
    lo, hi = boot(diffs)
    moved = sum(1 for d in diffs if d > 0), sum(1 for d in diffs if d < 0)

    floor, floor_src = (a.floor, "given on the command line") if a.floor is not None \
        else noise_floor(a.earlier)
    if floor is None:
        floor, floor_src = 0.0, "NONE MEASURED - treating as zero, which is too generous"

    print("=" * 76)
    print(f"MOVEMENT - {a.earlier}  ->  {a.later}")
    print("=" * 76)
    print(f"  {a.earlier:<16} {ra['mean_over_draws']:>7.1%}   "
          f"on bank [{ra['on_bank_low']:.1%}, {ra['on_bank_high']:.1%}]   "
          f"{ra['n_items']} items, {ra['n_draws']} draws")
    print(f"  {a.later:<16} {rb['mean_over_draws']:>7.1%}   "
          f"on bank [{rb['on_bank_low']:.1%}, {rb['on_bank_high']:.1%}]   "
          f"{rb['n_items']} items, {rb['n_draws']} draws")
    print()
    print(f"  paired over {len(shared)} shared items")
    print(f"  change, per item  {delta:+.1%}   95% CI [{lo:+.1%}, {hi:+.1%}]"
          f"   <- tests against zero")
    print(f"  change, aggregate {delta_agg:+.1%}"
          f"                            <- tests against the floor")
    print(f"  items worse {moved[0]}, better {moved[1]}, unchanged "
          f"{len(diffs) - moved[0] - moved[1]}")
    print(f"  noise floor       {floor:.1%}   ({floor_src})")
    print("-" * 76)

    crosses_zero = lo <= 0 <= hi
    under_floor = abs(delta_agg) < floor
    if under_floor or crosses_zero:
        why = []
        if under_floor:
            why.append(f"the change is smaller than the {floor:.1%} the instrument "
                       f"produces when nothing has changed")
        if crosses_zero:
            why.append("the interval contains zero")
        print("NOT REPORTABLE AS MOVEMENT — " + "; and ".join(why) + ".")
        print()
        print("  Report the reading, not a finding: give the rate and its interval and")
        print("  say the number held. That is a complete issue. A series is trusted for")
        print("  the readings where it says nothing happened, and this is one of them.")
        print("-" * 76)
        return 1

    print(f"REPORTABLE. {delta_agg:+.1%} aggregate clears the {floor:.1%} floor, and the"
          f" per-item\n  interval excludes zero. BOTH tests must pass; either alone is a"
          f" half-argument.")
    print("  Publish it with BOTH intervals and the conditions of both runs. A change")
    print("  measured under a different grader or provider is a finding about the")
    print("  harness until proven otherwise.")
    print("-" * 76)
    return 0


if __name__ == "__main__":
    sys.exit(main())
