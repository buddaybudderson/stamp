"""WHO WINS, BY HOW MUCH, AND IS IT REAL? Two candidates on the same bank, one sentence.

    python scripts/compare.py nemo_v1 luna_v1
    python scripts/compare.py nemo_v1 luna_v1 --public-only

  exit 0 = a difference the data supports    exit 1 = not distinguishable    exit 2 = refused

WHAT IT PRINTS, and the sentence a report may quote:

    luna_v1 fails 9.8 points less than nemo_v1 on bank v1 (95% CI 5.1 to 14.6;
    p = 0.0004, paired over 63 items). Smallest difference this design can detect: 6.0.

movement.py asks "did ONE model move between two runs?" against the measured retest noise.
This asks "is model B better than model A?", which is a different question with a different
null: there is no retest floor between two models, only the chance that the items happened
to favour one of them.

THE UNIT IS THE ITEM. Both candidates answered the same items, so each item is its own
comparison (B's fail rate minus A's on that item) and the bootstrap and the test resample
ITEMS. Resampling draws instead would treat 300 draws of 63 questions as 300 independent
questions and shrink the interval roughly by the square root of the draws per item - the
"2 points on 50 samples" mistake, made in the confident direction.

THE TEST. Sign-flip permutation on the item differences (exact null: under "no difference"
each item's difference is as likely to be negative as positive), 20000 flips, seed fixed.
No normality assumption, nothing to tune.

THE MDE. Minimum detectable effect at 80% power, alpha 0.05, from the SD of the item
differences: 2.8 x SD / sqrt(items). A difference smaller than this is not "no difference";
it is "this bank cannot tell". The script says which.

Stdlib only. No network.
"""
import argparse, collections, importlib.util, json, math, pathlib, random, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "pilot_out"
BANK = ROOT / "bank" / "bank_v1.jsonl"


def load(cand):
    latest = {}
    for half in ("A", "B", ""):
        p = OUT / (f"pilot_{cand}_{half}.jsonl" if half else f"pilot_{cand}.jsonl")
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    latest[(p.name, r["item_id"], str(r["draw"]))] = r["verdict"]
    per = collections.defaultdict(list)
    for (_, item, _), v in latest.items():
        if v in ("PASS", "FAIL"):
            per[item].append(1 if v == "FAIL" else 0)
    return dict(per)


def texts(cand):
    t = {}
    for half in ("A", "B", ""):
        p = OUT / (f"pilot_{cand}_{half}.jsonl" if half else f"pilot_{cand}.jsonl")
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    if r.get("text"):
                        t[(half, r["item_id"], str(r["draw"]))] = r["text"]
    return t


def shared_replies(a, b):
    """Share of keyed replies that are byte-identical. A regrade reuses the replies, so a
    'difference between candidates' is then a difference between GRADERS."""
    ta, tb = texts(a), texts(b)
    keys = set(ta) & set(tb)
    return (sum(ta[k] == tb[k] for k in keys) / len(keys)) if keys else 0.0


def analyse(A, B, iters=20000, seed=20261005):
    shared = sorted(set(A) & set(B))
    if len(shared) < 5:
        return None
    d = [sum(B[i]) / len(B[i]) - sum(A[i]) / len(A[i]) for i in shared]
    n = len(d)
    mean = sum(d) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in d) / (n - 1)) if n > 1 else 0.0
    rnd = random.Random(seed)
    boots = sorted(sum(d[rnd.randrange(n)] for _ in range(n)) / n for _ in range(4000))
    lo, hi = boots[100], boots[3899]
    hits = sum(1 for _ in range(iters)
               if abs(sum(x if rnd.random() < 0.5 else -x for x in d)) / n >= abs(mean) - 1e-12)
    return {"items": n, "diff": mean, "lo": lo, "hi": hi, "p": (hits + 1) / (iters + 1),
            "mde": 2.8 * sd / math.sqrt(n), "sd": sd,
            "worse": sum(x > 0 for x in d), "better": sum(x < 0 for x in d),
            "a_rate": sum(sum(A[i]) for i in shared) / sum(len(A[i]) for i in shared),
            "b_rate": sum(sum(B[i]) for i in shared) / sum(len(B[i]) for i in shared)}


def sentence(a, b, r):
    if r["diff"] == 0:
        return f"{b} and {a} fail at the same rate on these items."
    lead, trail = (b, a) if r["diff"] < 0 else (a, b)
    lo, hi = sorted((abs(r["lo"]), abs(r["hi"]))) if r["lo"] * r["hi"] > 0 else (None, None)
    ci = (f"95% CI {lo * 100:.1f} to {hi * 100:.1f}" if lo is not None else
          f"95% CI {r['lo'] * 100:+.1f} to {r['hi'] * 100:+.1f}, which crosses zero")
    return (f"{lead} fails {abs(r['diff']) * 100:.1f} points less than {trail} "
            f"({ci}; p = {r['p']:.4f}, paired over {r['items']} items). "
            f"Smallest difference this design can detect: {r['mde'] * 100:.1f}.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a"); ap.add_argument("b")
    ap.add_argument("--public-only", action="store_true",
                    help="restrict to holdout:false items, for a figure that can cite items")
    x = ap.parse_args()
    A, B = load(x.a), load(x.b)
    if x.public_only:
        pub = {json.loads(l)["item_id"] for l in BANK.read_text(encoding="utf-8").splitlines()
               if l.strip() and not json.loads(l).get("holdout")}
        A = {k: v for k, v in A.items() if k in pub}; B = {k: v for k, v in B.items() if k in pub}
    r = analyse(A, B)
    if r is None:
        print("REFUSED - fewer than 5 shared items; there is nothing to compare")
        return 2
    print("=" * 78)
    print(f"COMPARE - {x.a} vs {x.b}" + ("   (public items only)" if x.public_only else ""))
    print("=" * 78)
    print(f"  fail rate   {x.a} {r['a_rate']:.1%}   {x.b} {r['b_rate']:.1%}   (pooled draws)")
    print(f"  per-item difference ({x.b} - {x.a})  {r['diff']:+.1%}   "
          f"95% CI [{r['lo']:+.1%}, {r['hi']:+.1%}]   items resampled")
    print(f"  items where {x.b} is worse {r['worse']}, better {r['better']}, "
          f"same {r['items'] - r['worse'] - r['better']}")
    print(f"  sign-flip permutation p = {r['p']:.4f}     MDE (80% power) {r['mde']:.1%}")
    same = shared_replies(x.a, x.b)
    if same > 0.9:
        print(f"  SAME REPLIES - {same:.0%} of keyed replies are byte-identical. This is one")
        print("  set of answers graded twice: the difference below belongs to the GRADERS,")
        print("  not to the candidates. Quote it as a grader difference or not at all.")
    print("-" * 78)
    real = r["p"] < 0.05 and r["lo"] * r["hi"] > 0
    print("  " + sentence(x.a, x.b, r))
    if not real:
        tag = ("smaller than this bank can detect" if abs(r["diff"]) < r["mde"]
               else "not distinguishable from item luck")
        print(f"  NOT A FINDING - the difference is {tag}. Say the two are level here.")
    print("-" * 78)
    return 0 if real else 1


if __name__ == "__main__":
    sys.exit(main())
