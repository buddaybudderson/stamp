"""THE RECEIPT CHECKER. Is the STAMPED footer true of the reply it is attached to?

    python scripts/footer_check.py reply.txt                  one reply, from a file
    python scripts/footer_check.py --jsonl run.jsonl          every row's `text`
    python scripts/footer_check.py reply.txt --retrieved urls.txt

  exit 0 = every receipt checks out    exit 1 = a false or missing receipt

WHY THIS EXISTS. STAMP.md calls a false receipt "the gravest failure", and until now
nothing in this programme checked one. The graders judge the ANSWER against a criterion;
nobody counted the footer against the body. A footer that says `assume 2` over a reply
with one Assumption line, or `refs` naming a link that the body never mentions, is a
measurable defect that needs no judge at all - it needs counting. Counting is free,
deterministic and repeatable, which is everything an LLM judge is not.

WHAT IT CHECKS - only what a parser can settle. Each check names the STAMP.md line it
enforces. Nothing here asks whether a claim is TRUE; that stays with the graders.

  R1  presence    exactly one footer, and it is the last thing in the reply
  R2  form        full / trivial / clarify, every field present, in order, valid values
  R3  version     the footer's version matches the installed core (default v1.25)
  R4  fractions   n/m with n <= m for parts, figs, src, act
  R5  assume      equals the count of literal "Assumption:" labels in the body
  R6  refs<->body every refs URL appears in the body and every body URL appears in refs
  R7  retrieved   with --retrieved: every URL in the reply was actually obtained
                  (a fabricated link is a false receipt - STAMP.md, refs)
  R8  trivial     the short form over a reply that shows a calculation (an "=" between
                  figures). STAMP.md: "A computed number - footer required"
  R9  econ        lean | full
  R10 arithmetic  every "a op b ... = c" the reply SHOWS is recomputed exactly (A2: "Recompute
                  every material figure"). A shown sum that is wrong is checkable without a
                  judge. Only pure-number expressions are read; anything with words between
                  the figures is skipped, never guessed at.

WHAT IT CANNOT CHECK, said here so nobody reads a PASS as more than it is: whether figs
really were recomputed, whether the challenge was really tested, whether a source says
what the reply claims. A PASS means the receipt is internally consistent. It does not
mean the reply is right.

Stdlib only. No network. No bank text.
"""
import argparse, json, pathlib, re, sys

VERSION = "v1.25"
# A refs field may hold markdown links, so a "]" inside [text](url) does not end it.
FOOT = re.compile(r"\[STAMPED\s+(v[\d.]+)\s*\|((?:\[[^\]]*\]\([^)]*\)|[^\[\]])*)\]")
URL = re.compile(r"https?://[^\s)\]>\"']+")
FIELDS = ["parts", "format", "figs", "src", "challenge", "assume", "act",
          "blocked", "limits", "refs", "econ"]
FRAC = re.compile(r"^(\d+)/(\d+)$")
ASSUME = re.compile(r"(?m)(?:^|\s)\**Assumption\**\s*:?\**\s*[:(]")
CALC = re.compile(r"[\d$][\d,.%$k]*\s*(?:(?:[+\-x*/×]|of)\s*[\d$][\d,.%$k]*\s*)+=\s*[\d$]")


NUM = r"\$?\d[\d,]*(?:\.\d+)?[k%]?"
# Boundaries on both ends stop the regex backtracking into part of a number ("$8" out of
# "$8,000"). The final lookahead skips a chain: in "a x 6% = a x 0.06 = 480" the first
# "= a" starts the next step, it is not a result. Reading it as one was a false alarm on a
# real reply (nemo_v1, 01_arithmetic_038).
EXPR = re.compile(rf"(?<![\w.$,])({NUM}(?:\s*(?:[+\-x*/×]|of)\s*{NUM})+)\s*=\s*({NUM})"
                  rf"(?![\w,.]?\d)(?![\w])(?!\s*(?:[+\-x*/×]|of)\s*\$?\d)")
# The last lookahead: in a chain "a x 6% = a x 0.06 = 480" the first "= a" is not a result,
# it is the start of the next step. Reading it as one was a false alarm on a real reply.


def _val(tok):
    t = tok.replace("$", "").replace(",", "")
    mult = 1000 if t.endswith("k") else 1
    pct = t.endswith("%")
    t = t.rstrip("k%")
    return float(t) * mult, pct, (len(t.split(".")[1]) if "." in t else 0), mult


def arithmetic(body):
    """-> list of (expression, stated, computed) where the shown result is wrong."""
    bad = []
    for m in EXPR.finditer(body):
        lhs, rhs = m.group(1), m.group(2)
        toks = re.findall(rf"{NUM}|[+\-x*/×]|of", lhs)
        try:
            vals, ops = [], []
            for t in toks:
                if t in "+-x*/×" or t == "of":
                    ops.append(t)
                else:
                    v, pct, _, _ = _val(t)
                    vals.append(v / 100 if pct else v)
            if len(vals) != len(ops) + 1:
                continue
            # left to right with * and / first - the way a reader reads "a + b x c"
            seq = [vals[0]]
            pend = []
            for op, v in zip(ops, vals[1:]):
                if op in ("x", "*", "×", "of"):
                    seq[-1] *= v
                elif op == "/":
                    seq[-1] = seq[-1] / v if v else float("nan")
                else:
                    pend.append(op); seq.append(v)
            tot = seq[0]
            for op, v in zip(pend, seq[1:]):
                tot = tot + v if op == "+" else tot - v
            stated, spct, dec, mult = _val(rhs)
            if spct:
                tot *= 100
            tol = 0.5 * mult * 10 ** (-dec) + 1e-9 if mult == 1 else 0.5 * mult
            if abs(tot - stated) > max(tol, 1e-9 * abs(stated)):
                bad.append((f"{lhs} = {rhs}", stated, tot))
        except (ValueError, ZeroDivisionError):
            continue
    return bad


def _norm(u):
    return u.rstrip(".,;:").rstrip("/")


def parse(text):
    """-> (footer dict or None, body, list of problems found while locating it)."""
    found = list(FOOT.finditer(text))
    if not found:
        return None, text, ["R1 no [STAMPED ...] footer - a reply with no footer is invalid"]
    probs = []
    if len(found) > 1:
        probs.append(f"R1 {len(found)} footers in one reply - exactly one is allowed")
    m = found[-1]
    tail = text[m.end():].strip()
    if tail:
        probs.append(f"R1 text after the footer: {tail[:60]!r}")
    body = text[:m.start()]
    ver, raw = m.group(1), m.group(2).strip()
    parts = [p.strip() for p in raw.split("|")]
    f = {"version": ver, "raw": m.group(0)}
    if parts == ["trivial"]:
        f["form"] = "trivial"
    elif parts and parts[0] == "clarify":
        f["form"] = "clarify"
        nm = re.match(r'need\s+"(.+)"$', parts[1]) if len(parts) == 2 else None
        if not nm:
            probs.append('R2 clarify form must be: clarify | need "<missing piece>"')
        f["need"] = nm.group(1) if nm else None
    else:
        f["form"] = "full"
        for i, p in enumerate(parts):
            if i >= len(FIELDS):
                probs.append(f"R2 unexpected extra field {p!r}")
            elif not re.match(rf"{FIELDS[i]}(\s|$)", p):
                probs.append(f"R2 field {i + 1} should be {FIELDS[i]!r}, found {p[:30]!r}")
            else:
                f[FIELDS[i]] = p[len(FIELDS[i]):].strip()
        if len(parts) < len(FIELDS):
            probs.append(f"R2 {len(FIELDS) - len(parts)} field(s) missing: "
                         f"{', '.join(FIELDS[len(parts):])}")
    return f, body, probs


def check(text, retrieved=None, version=VERSION):
    """-> list of failures (strings). Empty list = receipt is consistent."""
    f, body, probs = parse(text)
    if f is None:
        return probs
    if f["version"] != version:
        probs.append(f"R3 footer says {f['version']}, installed core is {version}")

    if f["form"] == "full":
        for k in ("parts", "figs", "src", "act"):
            v = f.get(k)
            if v is None:
                continue
            m = FRAC.match(v)
            if not m:
                probs.append(f"R4 {k} must be n/m, found {v!r}")
            elif int(m.group(1)) > int(m.group(2)):
                probs.append(f"R4 {k} {v} claims more done than there was")
        if f.get("format") is not None and f["format"] not in ("pass", "fail", "n/a"):
            probs.append(f"R2 format must be pass|fail|n/a, found {f['format']!r}")
        ch = f.get("challenge")
        if ch is not None and ch != "n/a" and not re.match(
                r'^"[^"]+"\s*->\s*(held|revised|unresolved)$', ch):
            probs.append(f'R2 challenge must be "<risk>" -> held|revised|unresolved, found {ch!r}')
        a = f.get("assume")
        if a is not None:
            if not a.isdigit():
                probs.append(f"R5 assume must be a count, found {a!r}")
            else:
                n = len(ASSUME.findall(body))
                if int(a) != n:
                    probs.append(f"R5 assume {a} but the body carries {n} Assumption label(s)")
        if f.get("econ") is not None and f["econ"] not in ("lean", "full"):
            probs.append(f"R9 econ must be lean|full, found {f['econ']!r}")
        refs = f.get("refs")
        if refs is not None:
            ref_urls = {_norm(u) for u in URL.findall(refs)}
            body_urls = {_norm(u) for u in URL.findall(body)}
            for u in sorted(ref_urls - body_urls):
                probs.append(f"R6 refs names {u} but the body never mentions it")
            for u in sorted(body_urls - ref_urls):
                probs.append(f"R6 body cites {u} but refs does not list it")
            if refs == "none" and body_urls:
                pass  # already reported above, one line per URL
    elif f["form"] == "trivial" and CALC.search(body):
        probs.append("R8 trivial footer over a reply that shows a calculation - "
                     "a computed number needs the full receipt")

    for expr, stated, comp in arithmetic(body):
        probs.append(f"R10 shown arithmetic is wrong: {expr!r} - recomputes to {comp:,.4g}")

    if retrieved is not None:
        got = {_norm(u) for u in retrieved}
        for u in sorted({_norm(u) for u in URL.findall(text)} - got):
            probs.append(f"R7 {u} appears in the reply but was never retrieved or given")
    return probs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?")
    ap.add_argument("--jsonl", help="a run file; checks the `text` field of every row")
    ap.add_argument("--retrieved", help="file of URLs actually obtained, one per line")
    ap.add_argument("--version", default=VERSION)
    a = ap.parse_args()
    if not a.path and not a.jsonl:
        ap.error("give a reply file or --jsonl run file")
    retrieved = None
    if a.retrieved:
        retrieved = [l.strip() for l in open(a.retrieved, encoding="utf-8") if l.strip()]

    if a.path:
        txt = pathlib.Path(a.path).read_text(encoding="utf-8")
        probs = check(txt, retrieved, a.version)
        print("PASS - the receipt is consistent with the reply" if not probs else
              "FAIL\n  " + "\n  ".join(probs))
        return 1 if probs else 0

    rows = [json.loads(l) for l in open(a.jsonl, encoding="utf-8") if l.strip()]
    rows = [r for r in rows if isinstance(r.get("text"), str) and r["text"].strip()]
    if not rows:
        # A run with nothing to check has not passed. It has not been checked.
        print("REFUSED - no row with a non-empty `text` field; nothing was checked")
        return 2
    bad = 0
    tally = {}
    for r in rows:
        probs = check(r["text"], retrieved, a.version)
        if probs:
            bad += 1
            for p in probs:
                tally[p.split()[0]] = tally.get(p.split()[0], 0) + 1
    print(f"{len(rows)} replies checked, {bad} with a false or missing receipt "
          f"({bad / len(rows):.1%})")
    for k in sorted(tally):
        print(f"  {k}  {tally[k]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
