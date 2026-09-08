#!/usr/bin/env python3
"""harness_gate.py - refuse to publish any file that carries bank text.

Companion to holdout_gate.py. That gate guards the SITE; this one guards the
HARNESS repository, which is a different surface with the same failure mode:
a probe reaching a public place cannot be un-published, and nothing breaks
visibly when it happens - models simply start passing that probe.

Usage
  python harness_gate.py --bank <bank_v1.jsonl> --paths <file-or-dir> [...]
  python harness_gate.py --bank bank/bank_v1.jsonl --staged      # pre-commit

Exit codes
  0  clean
  1  bank text found - refuse
  2  the gate could not do its job (missing bank, no files, no comparable
     fragments). NEVER exits 0 in this case: a check that passes because it
     asked nothing is worse than no check at all.
"""
import argparse, json, os, subprocess, sys

MIN_FRAGMENT = 40          # shorter strings collide by chance and mean nothing
SCAN_SUFFIXES = {'.py', '.md', '.txt', '.json', '.jsonl', '.yaml', '.yml',
                 '.html', '.js', '.csv', '.ipynb', ''}

def load_fragments(bank_path, holdout_only):
    if not os.path.exists(bank_path):
        print(f"GATE ERROR: bank not found at {bank_path}\n"
              f"The gate cannot run without it. Refusing (exit 2).", file=sys.stderr)
        sys.exit(2)
    rows = [json.loads(l) for l in open(bank_path, encoding='utf-8') if l.strip()]
    frags = []
    for r in rows:
        if holdout_only and r.get('holdout') is not True:
            continue
        item = r.get('item_id', '<unknown>')
        texts = []
        msgs = r.get('messages')
        if isinstance(msgs, list):
            for m in msgs:
                c = m.get('content') if isinstance(m, dict) else None
                if isinstance(c, str):
                    texts.append(c)
        for k in ('context', 'prompt', 'ground_truth'):
            v = r.get(k)
            if isinstance(v, str):
                texts.append(v)
        for t in texts:
            t = t.strip()
            if len(t) >= MIN_FRAGMENT:
                frags.append((item, t[:120]))
    return rows, frags

def gather(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for dp, dn, fn in os.walk(p):
                dn[:] = [d for d in dn if d not in ('.git', '__pycache__', 'node_modules')]
                out += [os.path.join(dp, f) for f in fn]
        elif os.path.isfile(p):
            out.append(p)
    return [f for f in out if os.path.splitext(f)[1].lower() in SCAN_SUFFIXES]

def staged_files():
    try:
        r = subprocess.run(['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
                           capture_output=True, text=True, check=True)
    except Exception as e:
        print(f"GATE ERROR: could not read the git index ({e}). Refusing (exit 2).", file=sys.stderr)
        sys.exit(2)
    return [f for f in r.stdout.split('\n') if f.strip() and os.path.exists(f)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bank', default='bank/bank_v1.jsonl')
    ap.add_argument('--paths', nargs='*', default=[])
    ap.add_argument('--staged', action='store_true')
    ap.add_argument('--all-probes', action='store_true',
                    help='check against every probe, not only the held-out ones')
    a = ap.parse_args()

    rows, frags = load_fragments(a.bank, holdout_only=not a.all_probes)
    scope = 'all probes' if a.all_probes else 'held-out probes'
    if not frags:
        print(f"GATE ERROR: no comparable text found in {a.bank} ({scope}).\n"
              f"The gate would pass everything. Refusing (exit 2).", file=sys.stderr)
        sys.exit(2)

    files = staged_files() if a.staged else gather(a.paths)
    if not files:
        print("GATE ERROR: no files to scan. A gate with nothing to check "
              "must not report success. Refusing (exit 2).", file=sys.stderr)
        sys.exit(2)

    hits = {}
    for f in files:
        try:
            txt = open(f, encoding='utf-8', errors='ignore').read()
        except Exception:
            continue
        found = sorted({i for i, t in frags if t in txt})
        if found:
            hits[f] = found

    held = sum(1 for r in rows if r.get('holdout') is True)
    print(f"harness_gate: {len(files)} file(s) scanned against "
          f"{len(frags)} fragment(s) from {len(rows)} bank rows "
          f"({held} held out) - scope: {scope}")

    if hits:
        print("\nREFUSED - bank text found in files bound for a public repository:\n")
        for f, items in hits.items():
            print(f"  {f}")
            for i in items:
                print(f"      {i}")
        print(f"\n{len(hits)} file(s) must not be published. "
              f"Move them to the private repository beside the bank.")
        return 1

    print("PASS - no bank text in any scanned file.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
