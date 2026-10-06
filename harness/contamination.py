"""CONTAMINATION, BOTH DIRECTIONS.

    python scripts/contamination.py scan <file-or-dir> [...]       has bank text reached it?
    python scripts/contamination.py divergence <cand> [<cand> ...]  has a model seen the public half?

  exit 0 = clean    exit 1 = contamination found    exit 2 = refused (could not check)

SCAN - OUTBOUND, AND PARAPHRASE-AWARE. holdout_gate.py stops a held-out probe reaching the
site by exact six-word runs, and that is the right gate for a commit. It cannot see a
REWORDED probe: an essay that retells a held-out question in new words leaks the item just
as surely and passes the gate. And it only scans our own tree. This scans any text - a
draft, a fine-tuning corpus, a public dataset someone published - with two detectors:

  exact     8-word runs of a probe's prompt, as the gate does but on any file
  shingle   character 5-gram containment: the share of a probe's shingles found inside
            one window of the corpus the same length as the probe. Survives reordering,
            light rewording and punctuation changes. Flag at >= 0.50.

Only item ids and file offsets are printed. Bank text never is.

DIVERGENCE - INBOUND. The public half of bank v1 went live on 2026-09-03. A model trained
on it after that should start failing the public items less than the held-out ones, by
more than it did before. The two halves differ in difficulty by design, so the raw gap
means nothing on its own; what moves is the gap RELATIVE TO A BASELINE measured on runs
made BEFORE publication. Pre-publication runs (config dated before 2026-09-03) are the
baseline; any later run is tested against it with an item bootstrap of the difference in
gaps. With only pre-publication runs on disk, the script reports the baseline and says it
cannot yet test anything - it does not report "clean".

Stdlib only. No network.
"""
import collections, json, pathlib, random, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
# The scan guards what is held out NOW (v1.1); divergence compares the halves as they were
# when the runs were made, which for every run on disk is v1. See holdout_gate.py.
BANK = ROOT / "bank" / ("bank_v1_1.jsonl" if (ROOT / "bank" / "bank_v1_1.jsonl").exists() else "bank_v1.jsonl")
BANK_V1 = ROOT / "bank" / "bank_v1.jsonl"
OUT = ROOT / "pilot_out"
PUBLISHED = "2026-09-03"
NGRAM, SH, FLAG = 8, 5, 0.50
TEXT_EXT = {".txt", ".md", ".html", ".htm", ".json", ".jsonl", ".csv", ".xml", ".py", ".tsv"}


def bank():
    if not BANK.exists():
        return None
    return [json.loads(l) for l in BANK.read_text(encoding="utf-8").splitlines() if l.strip()]


def norm(t):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9$% ]+", " ", t.lower())).strip()


def prompt_of(it):
    return norm(" ".join(m["content"] for m in it.get("messages", []) if m.get("role") == "user"))


def shingles(t):
    return {t[i:i + SH] for i in range(max(0, len(t) - SH + 1))}


def scan_text(body, probes):
    """probes: [(item_id, words, shingle set, ngram set)]. -> [(item_id, kind, score, pos)]"""
    b = norm(body)
    hits = []
    for iid, words, sh, grams in probes:
        g = next((g for g in grams if g in b), None)
        if g:
            hits.append((iid, "exact", 1.0, b.find(g)))
            continue
        L = len(" ".join(words))
        if not sh or len(b) < L // 2:
            continue
        best, at = 0.0, -1
        step = max(20, L // 4)
        for s in range(0, max(1, len(b) - L + 1), step):
            w = b[s:s + L + L // 4]
            c = sum(1 for x in sh if x in w) / len(sh)
            if c > best:
                best, at = c, s
        if best >= FLAG:
            hits.append((iid, "shingle", best, at))
    return hits


def cmd_scan(paths):
    items = bank()
    if items is None:
        print(f"REFUSED - no bank at {BANK}; a scan with nothing to look for is not a pass")
        return 2
    public_text = " ".join(prompt_of(i) for i in items if not i.get("holdout"))
    # Templated probes share their frame ("quote the final sentence of ... and tell me
    # whether ...") with public siblings. Shingles of the frame are not evidence of a leak;
    # only what is UNIQUE to a held-out probe is. Same reasoning as holdout_gate.py.
    public_sh = shingles(public_text)
    probes = []
    for it in items:
        p = prompt_of(it)
        w = p.split()
        grams = {" ".join(w[i:i + NGRAM]) for i in range(len(w) - NGRAM + 1)}
        if not it.get("holdout"):
            continue          # the public half is published on purpose
        grams = {g for g in grams if g not in public_text}
        probes.append((it["item_id"], w, shingles(p) - public_sh, grams))
    files = []
    for a in paths:
        p = pathlib.Path(a)
        if not p.exists():
            print(f"REFUSED - {a} does not exist; an unscanned path is not a clean one")
            return 2
        files += [f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in TEXT_EXT] \
            if p.is_dir() else [p]
    if not files:
        print("REFUSED - no readable text files under the paths given")
        return 2
    found = 0
    for f in files:
        body = f.read_text(encoding="utf-8", errors="ignore")
        for iid, kind, score, pos in scan_text(body, probes):
            found += 1
            print(f"  LEAK  {f}  {iid}  {kind}  {score:.2f}  at char {pos}")
    print(f"{len(files)} file(s) scanned against {len(probes)} held-out probes: "
          + ("CLEAN" if not found else f"{found} LEAK(S)"))
    return 1 if found else 0


def run_date(cand):
    for half in ("A", "B"):
        c = OUT / f"pilot_{cand}_{half}.config.json"
        if c.exists():
            d = json.loads(c.read_text(encoding="utf-8"))
            for k in ("started", "date", "ts", "created"):
                if d.get(k):
                    return str(d[k])[:10]
    q = ROOT / "queue_log.jsonl"
    return None


def per_item(cand):
    latest = {}
    for half in ("A", "B"):
        p = OUT / f"pilot_{cand}_{half}.jsonl"
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    latest[(half, r["item_id"], str(r["draw"]))] = r
    per = collections.defaultdict(list)
    for (_, item, _), r in latest.items():
        if r["verdict"] in ("PASS", "FAIL"):
            per[item].append(1 if r["verdict"] == "FAIL" else 0)
    return {k: sum(v) / len(v) for k, v in per.items()}


def gap(rates, hold):
    h = [r for i, r in rates.items() if i in hold]
    p = [r for i, r in rates.items() if i not in hold]
    return (sum(h) / len(h) - sum(p) / len(p)) if h and p else None


def cmd_divergence(cands, dates):
    items = [json.loads(l) for l in BANK_V1.read_text(encoding="utf-8").splitlines() if l.strip()]         if BANK_V1.exists() else None
    if items is None:
        print("REFUSED - no bank, so the two halves cannot be told apart")
        return 2
    hold = {i["item_id"] for i in items if i.get("holdout")}
    base, test = [], []
    print(f"{'candidate':<14}{'run date':>12}{'held-out':>10}{'public':>9}{'gap':>9}   role")
    for c in cands:
        r = per_item(c)
        if not r:
            print(f"{c:<14}   no run files"); continue
        d = dates.get(c) or run_date(c)
        g = gap(r, hold)
        h = sum(v for i, v in r.items() if i in hold) / max(1, sum(1 for i in r if i in hold))
        p = sum(v for i, v in r.items() if i not in hold) / max(1, sum(1 for i in r if i not in hold))
        role = "baseline (pre-publication)" if d and d < PUBLISHED else \
               "TEST (post-publication)" if d else "UNDATED - excluded"
        print(f"{c:<14}{d or '?':>12}{h:>10.1%}{p:>9.1%}{g:>+9.1%}   {role}")
        (base if role.startswith("baseline") else test if role.startswith("TEST") else []).append((c, r))
    print("-" * 70)
    if not base:
        print("REFUSED - no pre-publication run to set the baseline gap")
        return 2
    if not test:
        print("BASELINE ONLY. No post-publication run on disk, so nothing can be tested yet.")
        print("This is not 'clean' - it is 'unmeasured'. Run any bank-v1 candidate now and")
        print("re-run this: a public half that has got easier relative to the held-out half,")
        print("beyond the baseline gap's interval, is the signature of training on it.")
        return 2
    rnd = random.Random(20261005)
    bad = 0
    bg = sum(gap(r, hold) for _, r in base) / len(base)
    for c, r in test:
        ids = list(r)
        obs = gap(r, hold) - bg
        bs = []
        for _ in range(4000):
            s = [ids[rnd.randrange(len(ids))] for _ in ids]
            rr = collections.defaultdict(list)
            for i in s:
                rr[i].append(r[i])
            rb = {i: sum(v) / len(v) for i, v in rr.items()}
            bb = []
            for _, b in base:
                sb = {i: b[i] for i in rb if i in b}
                gb = gap(sb, hold)
                if gb is not None:
                    bb.append(gb)
            gt = gap(rb, hold)
            if gt is not None and bb:
                bs.append(gt - sum(bb) / len(bb))
        bs.sort()
        lo, hi = bs[int(.025 * len(bs))], bs[int(.975 * len(bs)) - 1]
        flag = lo > 0
        bad += flag
        print(f"{c}: gap moved {obs:+.1%} vs baseline  95% CI [{lo:+.1%}, {hi:+.1%}]  "
              + ("<- public half got easier: POSSIBLE CONTAMINATION" if flag else "no divergence"))
    return 1 if bad else 0


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("scan", "divergence"):
        sys.exit(__doc__.split("\n\n")[1])
    if sys.argv[1] == "scan":
        return cmd_scan(sys.argv[2:])
    dates = {}
    args = []
    for a in sys.argv[2:]:
        c, _, d = a.partition("@")          # cand@YYYY-MM-DD when the config has no date
        args.append(c)
        if d:
            dates[c] = d
    return cmd_divergence(args, dates)


if __name__ == "__main__":
    sys.exit(main())
