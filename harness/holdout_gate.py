#!/usr/bin/env python3
"""
THE HOLDOUT GATE. Refuses to let a held-out probe reach a public artefact.

    python scripts/holdout_gate.py            check the working tree
    python scripts/holdout_gate.py --staged   check what git is about to commit
    python scripts/holdout_gate.py --path X   check one file or directory

Exit 0 = safe to publish. Exit 1 = something would leak. Runs offline, costs nothing.

WHY THIS IS THE ONE GATE THAT MATTERS MOST. Every other failure in this project has
been recoverable: a spoiled run is re-run, a wrong verdict is re-graded, a dead key is
replaced. Publishing a held-out probe is **irreversible**. Twenty-eight of the sixty-
three items in bank v1 are held out precisely so that a model vendor cannot train on
them, and the moment one appears in a public repository it is worthless forever - to
this programme and to anyone who would otherwise have cited it. There is no rollback,
because a git history rewrite does not un-scrape a page.

So this gate exists BEFORE the repository does, not after. `git init` is not the first
step of going public; this is.

WHAT LEAKS, AND WHAT DOES NOT
  the PROMPT is the asset            - the question, its framing, the planted error
  the RESPONSE quotes the prompt     - models restate the question constantly
  the grader's `why` quotes both     - "the response names Brian Niccol as CEO..."
  the ITEM ID is not the asset       - "14_provenance_040 failed 5/5" reveals no probe

That distinction is what makes weekly publishing possible at all: results can be
published in full, per item, by id, while the questions stay private.
"""
import argparse, json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BANK = ROOT / "bank" / "bank_v1.jsonl"

# Files that may NEVER be tracked, whatever they contain.
FORBIDDEN_NAMES = {
    "bank_v1.jsonl":      "the full bank - contains all 28 held-out probes",
    "pilot_v1.jsonl":     "source bank - contains held-out probes",
    "provenance_v1.jsonl": "source bank - contains held-out probes",
    "attribution_v1.jsonl": "source bank - contains held-out probes",
}
# Raw run output carries model responses, which quote the prompts back.
FORBIDDEN_GLOBS = ["pilot_out/*.jsonl", "panel_out/*.jsonl"]

# The shortest run of prompt words long enough to be a real match rather than a
# coincidence. Six words of a specific question does not occur by chance.
NGRAM = 6
MIN_CHARS = 40


def split_bank():
    items = [json.loads(l) for l in BANK.read_text(encoding="utf-8").splitlines()
             if l.strip()]
    return ([i for i in items if i.get("holdout")],
            [i for i in items if not i.get("holdout")])


def _grams(it):
    texts = [m["content"] for m in it.get("messages", [])]
    texts.append(it.get("pass_criterion", ""))
    out = set()
    for t in texts:
        w = re.findall(r"[A-Za-z0-9$%'.,-]+", t)
        for i in range(len(w) - NGRAM + 1):
            g = " ".join(w[i:i + NGRAM])
            if len(g) >= MIN_CHARS:
                out.add(g.lower())
    return out


def fingerprints(items, public):
    """Word runs that occur in a held-out probe AND NOWHERE IN THE PUBLIC SET.

    Fingerprinting every 6-word run flagged bank_v1_public.jsonl - the file that is
    deliberately publishable - because pass criteria are formulaic and share whole
    phrases ("states plainly it cannot supply verified..."). Boilerplate is not a
    leak. Only text UNIQUE to a held-out probe can identify it, so the public set's
    own n-grams are subtracted first. This is what keeps the gate from crying wolf,
    and a gate that cries wolf is a gate that gets switched off.
    """
    common = set()
    for it in public:
        common |= _grams(it)
    return {it["item_id"]: (_grams(it) - common) for it in items}


def scan_text(path, fps):
    try:
        body = path.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return []
    hits = []
    for iid, grams in fps.items():
        for g in grams:
            if g in body:
                hits.append((iid, g))
                break
    return hits


def tracked_files(staged):
    if staged:
        r = subprocess.run(["git", "diff", "--cached", "--name-only"],
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            return None
        return [ROOT / p for p in r.stdout.split() if (ROOT / p).exists()]
    r = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        return None
    return [ROOT / p for p in r.stdout.split() if (ROOT / p).exists()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--path", default="")
    a = ap.parse_args()

    items, public = split_bank()
    fps = fingerprints(items, public)
    thin = [i for i, g in fps.items() if not g]
    print("=" * 76)
    print(f"HOLDOUT GATE - {len(items)} held-out probes, "
          f"{sum(len(v) for v in fps.values())} distinctive fingerprints")
    print(f"  ({len(public)} public items' phrasing subtracted as boilerplate)")
    if thin:
        print(f"  WARNING: {len(thin)} held-out probe(s) have NO distinctive phrasing")
        print(f"  and cannot be detected by text: {', '.join(sorted(thin)[:4])}"
              + (" ..." if len(thin) > 4 else ""))
        print(f"  Those rely on the file-level rules below, not on scanning.")
    print("=" * 76)

    if a.path:
        p = pathlib.Path(a.path)
        files = sorted(x for x in (p.rglob("*") if p.is_dir() else [p]) if x.is_file())
        scope = f"path {a.path}"
    else:
        files = tracked_files(a.staged)
        if files is None:
            print("\n  Not a git repository yet - nothing is tracked, so nothing can leak.")
            print("  This gate must be wired in BEFORE the first commit:")
            print("    1. copy the .gitignore this repo ships with")
            print("    2. git init")
            print("    3. python scripts/holdout_gate.py --staged   (must pass)")
            print("    4. only then, git commit")
            print("\n  Checking the working tree as a dry run instead.\n")
            files = [f for f in ROOT.rglob("*") if f.is_file()
                     and ".git" not in f.parts and "_to_delete" not in f.parts]
            scope = "working tree (dry run - nothing is tracked yet)"
        else:
            scope = "staged files" if a.staged else "tracked files"

    print(f"  scope: {scope}, {len(files)} file(s)\n")

    problems = []
    for f in files:
        rel = f.relative_to(ROOT) if ROOT in f.parents or f.is_relative_to(ROOT) else f
        if f.name in FORBIDDEN_NAMES:
            problems.append((rel, "FORBIDDEN FILE", FORBIDDEN_NAMES[f.name]))
            continue
        if any(f.match(g) for g in FORBIDDEN_GLOBS):
            problems.append((rel, "RAW OUTPUT",
                             "model responses quote the prompts back"))
            continue
        if f.suffix.lower() in (".md", ".json", ".jsonl", ".txt", ".html", ".csv", ".yml",
                                ".yaml", ".py"):
            for iid, gram in scan_text(f, fps):
                problems.append((rel, f"LEAKS {iid}", f'"{gram[:60]}..."'))

    if not problems:
        print("  PASS - no held-out probe reaches anything in scope.")
        print("\n  Safe to publish. Item IDs and verdicts may be published freely;")
        print("  it is the prompt text that must never appear.")
        return 0

    seen = set()
    print(f"  {len(problems)} PROBLEM(S):\n")
    for rel, kind, detail in problems:
        k = (str(rel), kind)
        if k in seen:
            continue
        seen.add(k)
        print(f"    {str(rel):<44} {kind}")
        print(f"        {detail}")
    print("\n" + "!" * 76)
    print("BLOCKED. Publishing any of these burns the held-out set permanently.")
    print("  Add them to .gitignore, or publish the redacted results instead:")
    print("    python scripts/publish_results.py     (ids and verdicts, no text)")
    print("!" * 76)
    return 1


if __name__ == "__main__":
    sys.exit(main())
