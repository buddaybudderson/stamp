"""SILENT DRIFT. Same model id, later run: did anything change underneath it?

    python scripts/drift.py <baseline cand> <recheck cand>
    python scripts/drift.py luna_v1 luna_recheck_20261017

  exit 0 = no drift detected    exit 1 = drift    exit 2 = refused

A product watches live traffic for decay. STAMP has no traffic; what it has is a model id
that a provider can quietly re-serve - a new quantisation, a new host, a new default - while
the name stays the same. protocol/BASIS_LADDER.md calls this out as the deliverable nobody
publishes. The recheck is a scheduled re-run of the PUBLIC half (cheap, publishable, and it
never touches the held-out items' secrecy); this reads it against the baseline.

FOUR FINGERPRINTS, because the fail rate is the last thing to move:

  quality     movement.py's test, unchanged: paired over shared items, against the measured
              retest noise floor. Reportable only if both tests pass.
  serving     which providers served the calls (served_by). A new host is a new instrument
              condition even if no number moved - Finding 01 was exactly this.
  shape       median reply length and its ratio. A 30% change in length on the same items is
              a behaviour change whether or not the grader noticed.
  failure     truncation and error rates. A rise means the comparison itself is suspect.

Runs nothing. Scheduling the recheck is a paid run and needs Lawrence's OK each time
(release rules); this script only reads what a run left on disk.
Stdlib only. No network.
"""
import collections, importlib.util, json, pathlib, statistics as st, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "pilot_out"
HERE = pathlib.Path(__file__).resolve().parent
SHAPE, FAILRISE = 0.30, 0.02


def rows(cand):
    out = []
    for half in ("A", "B", ""):
        p = OUT / (f"pilot_{cand}_{half}.jsonl" if half else f"pilot_{cand}.jsonl")
        if p.exists():
            last = {}
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    last[(r["item_id"], str(r["draw"]))] = r
            out += list(last.values())
    return out


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__.split("\n\n")[1])
    a, b = sys.argv[1], sys.argv[2]
    ra, rb = rows(a), rows(b)
    if not ra or not rb:
        print(f"REFUSED - no run files for {a if not ra else b}")
        return 2
    drift = []
    print("=" * 72)
    print(f"DRIFT CHECK - {a} -> {b}")
    print("=" * 72)
    m = subprocess.run([sys.executable, str(HERE / "movement.py"), a, b],
                       capture_output=True, text=True, encoding="utf-8")
    q = [l for l in m.stdout.splitlines() if "REPORTABLE" in l or "NOT REPORTABLE" in l]
    print("  quality   " + (q[0].strip() if q else "movement.py gave no verdict"))
    if m.returncode == 0:
        drift.append("quality")

    sa = collections.Counter(r.get("served_by", "?") for r in ra)
    sb = collections.Counter(r.get("served_by", "?") for r in rb)
    new = set(sb) - set(sa)
    print(f"  serving   before {dict(sa)}  after {dict(sb)}" + ("   <- NEW HOST" if new else ""))
    if new:
        drift.append("serving")

    la = [int(r.get("chars") or 0) for r in ra if r.get("verdict") in ("PASS", "FAIL")]
    lb = [int(r.get("chars") or 0) for r in rb if r.get("verdict") in ("PASS", "FAIL")]
    if la and lb and st.median(la):
        ratio = st.median(lb) / st.median(la)
        bad = abs(ratio - 1) > SHAPE
        print(f"  shape     median reply {st.median(la):.0f} -> {st.median(lb):.0f} chars ({ratio:.2f}x)"
              + ("   <- SHIFT" if bad else ""))
        if bad:
            drift.append("shape")

    def frate(rs):
        return sum(r.get("verdict") in ("TRUNCATED", "ERROR", "UNPARSED") for r in rs) / len(rs)
    fa, fb = frate(ra), frate(rb)
    bad = fb - fa > FAILRISE
    print(f"  failure   truncated/error/unparsed {fa:.1%} -> {fb:.1%}" + ("   <- RISE" if bad else ""))
    if bad:
        drift.append("failure")
    print("-" * 72)
    if drift:
        print("DRIFT: " + ", ".join(drift) + ". Same id, different behaviour - say which, with both runs' conditions.")
        return 1
    print("NO DRIFT DETECTED on any fingerprint. Report the reading: the model held.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
