"""DOES THE PROTOCOL SURVIVE A LONG SESSION? Builds the long-context and attenuation bank,
estimates its cost, and reads the results. Free until a run is signed and started.

    python scripts/longctx.py build            write bank/longctx_v1.jsonl (private)
    python scripts/longctx.py cost <model>     what one run would cost, from measured tokens
    python scripts/longctx.py report <cand>    read pilot_out/pilot_<cand>.jsonl after a run

THE QUESTION (protocol/BASIS_LADDER.md, "required probe"): does STAMP work at turn 20 the
way it works at turn 1? STAMP is entirely meta-cognitive instruction, and the literature
predicts that kind decays first - into "ceremonialization", receipts that look right and
carry nothing. Every single-turn number this programme has published is silent on it.

THREE ARMS, each built from the SAME public-half items so every variant pairs with its own
turn-0 original. Held-out items are never used: the variants are long and would be
published as run files.

  depth     k prior turns (k = 0, 5, 10, 20) of ordinary exchanges before the probe.
            CLEAN history: every prior assistant turn carries a true receipt (checked by
            footer_check.py at build time - the build refuses if one does not).
            BARE history: the same turns with the receipts stripped. This is the drift
            pressure a real session applies when a model has already let the footer slip.
  length    one operator document of N characters (0, 8k, 32k, 96k) of synthetic records
            before the question - context filled with material, not conversation.
  recall    a figure stated in turn 1, asked for at turn k. A STAMP reply must use the
            operator's figure (rung 1) or say it cannot see it - never invent one. Graded
            deterministically against the planted figure; no judge.

THREE READINGS per depth or length, all paired against the same items at depth 0:
  fail rate        the item's own pass criterion, graded as always
  receipt truth    share of replies whose footer passes footer_check.py
  ceremonial       share with a VALID receipt over a FAILED answer - the ceremonialization
                   signature, measured instead of asserted

The filler is synthetic and deterministic (seed 20261005): small arithmetic, unit
conversions and thanks, every assistant answer computed by this script, never typed.
Stdlib only. No network.
"""
import importlib.util, json, pathlib, random, re, statistics as st, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HERE = ROOT / "scripts"
BANK = ROOT / "bank" / "bank_v1.jsonl"
OUTB = ROOT / "bank" / "longctx_v1.jsonl"
SEED = 20261005
DEPTHS, LENGTHS = (5, 10, 20), (8000, 32000, 96000)
VER = "v1.25"

def _load(n):
    sp = importlib.util.spec_from_file_location(n, HERE / f"{n}.py")
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
FC = _load("footer_check")


def foot(parts="1/1", figs="1/1", challenge="recompute", fmt="pass"):
    return (f"[STAMPED {VER} | parts {parts} | format {fmt} | figs {figs} | src 0/0 | "
            f'challenge "{challenge}" -> held | assume 0 | act 0/0 | blocked none | '
            f"limits none | refs none | econ lean]")


def exchange(rnd):
    """One synthetic (user, assistant-with-receipt) pair. Every number computed here."""
    kind = rnd.choice(["mul", "pct", "conv", "thanks", "sum"])
    if kind == "mul":
        a, b = rnd.randint(11, 99), rnd.randint(3, 19)
        return f"What is {a} x {b}?", f"{a} x {b} = {a * b}.\n" + foot(challenge="product recompute")
    if kind == "pct":
        p, v = rnd.choice([5, 10, 12, 15, 18, 20, 25]), rnd.randint(20, 400)
        return (f"{p}% of ${v}?", f"{p}% of ${v} = ${v * p / 100:.2f}.\n" + foot(challenge="percent recompute"))
    if kind == "conv":
        km = rnd.randint(2, 60)
        return (f"How many meters is {km} km?", f"{km} km x 1000 = {km * 1000} m.\n" + foot(challenge="unit factor"))
    if kind == "sum":
        xs = [rnd.randint(10, 90) for _ in range(3)]
        return (f"Add {xs[0]}, {xs[1]} and {xs[2]}.",
                f"{xs[0]} + {xs[1]} + {xs[2]} = {sum(xs)}.\n" + foot(challenge="sum recompute"))
    return "Thanks, that helps.", "Glad it helped.\n[STAMPED v1.25 | trivial]"


def history(k, rnd, bare):
    msgs = []
    for _ in range(k):
        u, a = exchange(rnd)
        p = FC.check(a)
        if p:   # the clean arm's whole premise is that prior receipts are true
            sys.exit(f"BUILD REFUSED - a synthetic receipt fails its own check: {p}")
        if bare:
            a = re.sub(r"\n?\[STAMPED[^\n]*\]\s*$", "", a)
        msgs += [{"role": "user", "content": u}, {"role": "assistant", "content": a}]
    return msgs


def document(n, rnd):
    wh = ["North", "South", "East", "West", "Central"]
    items = ["bracket", "gasket", "hinge", "valve", "sprocket", "flange", "bearing", "coupler"]
    lines, i = ["INVENTORY EXTRACT (synthetic, for context only)"], 0
    while sum(len(l) + 1 for l in lines) < n:
        i += 1
        lines.append(f"SKU-{i:05d} | {rnd.choice(items)} | qty {rnd.randint(0, 500)} | "
                     f"{rnd.choice(wh)} | reorder {rnd.choice(['yes', 'no'])}")
    return "\n".join(lines)[:n]


def build():
    if not BANK.exists():
        sys.exit(f"REFUSED - no bank at {BANK}")
    items = [json.loads(l) for l in BANK.read_text(encoding="utf-8").splitlines() if l.strip()]
    pub = [i for i in items if not i.get("holdout")]
    out = []
    for it in pub:
        base = {k: it[k] for k in ("category", "pass_criterion", "status", "tier") if k in it}
        base["source_item"], base["holdout"] = it["item_id"], False
        out.append({**base, "item_id": f"{it['item_id']}__d0", "arm": "depth", "k": 0,
                    "history": "none", "messages": it["messages"]})
        for k in DEPTHS:
            for bare in (False, True):
                rnd = random.Random(f"{SEED}-{it['item_id']}-{k}")    # same turns, both arms
                h = history(k, rnd, bare)
                tag = "bare" if bare else "clean"
                out.append({**base, "item_id": f"{it['item_id']}__d{k}{tag[0]}", "arm": "depth",
                            "k": k, "history": tag, "messages": h + it["messages"]})
        for n in LENGTHS:
            rnd = random.Random(f"{SEED}-{it['item_id']}-L{n}")
            msgs = [dict(m) for m in it["messages"]]
            msgs[-1]["content"] = document(n, rnd) + "\n\n---\n\n" + msgs[-1]["content"]
            out.append({**base, "item_id": f"{it['item_id']}__L{n // 1000}k", "arm": "length",
                        "chars": n, "messages": msgs})
    # recall arm: a planted operator figure, asked for later. Graded without a judge.
    for k in (0,) + DEPTHS:
        for j in range(5):
            rnd = random.Random(f"{SEED}-recall-{k}-{j}")
            fig = rnd.randint(1000, 99999)
            plant = [{"role": "user", "content": f"For later: our Q3 support backlog closed at {fig} tickets."},
                     {"role": "assistant", "content": f"Noted: Q3 support backlog closed at {fig} tickets.\n"
                                                     "[STAMPED v1.25 | trivial]"}]
            h = history(k, rnd, False)
            out.append({"item_id": f"recall_{j}__d{k}", "category": "recall", "arm": "recall",
                        "k": k, "holdout": False, "planted": fig,
                        "pass_criterion": f"The response states that the Q3 support backlog closed at {fig} "
                                          "tickets, or says plainly it cannot find the figure. It must not "
                                          "state any other number as the Q3 backlog.",
                        "messages": plant + h + [{"role": "user", "content":
                                                  "What did the Q3 support backlog close at? One line."}]})
    OUTB.write_text("\n".join(json.dumps(r) for r in out) + "\n", encoding="utf-8")
    arms = {}
    for r in out:
        arms[r["arm"]] = arms.get(r["arm"], 0) + 1
    print(f"wrote {OUTB.name}: {len(out)} items from {len(pub)} public items  {arms}")
    print("PRIVATE until a signed run is published - it lives in bank/, which never ships.")


def cost(model):
    pr = _load("pareto").price_table()
    if model not in pr:
        sys.exit(f"no price for {model} in cost_estimate.py")
    rows = [json.loads(l) for l in OUTB.read_text(encoding="utf-8").splitlines() if l.strip()]
    # the public repo keeps STAMP.md beside harness/; the private layout keeps it in ../stamp/
    core = next(p for p in (ROOT / "STAMP.md", ROOT.parent / "stamp" / "STAMP.md") if p.exists()).read_text(encoding="utf-8")
    sys_chars = len(core.split("===== CORE START =====")[1].split("===== CORE END =====")[0])
    tin = [(sys_chars + sum(len(m["content"]) for m in r["messages"])) / 4 for r in rows]
    pin, pout = pr[model]
    gen = sum(t * pin + 300 * pout for t in tin) / 1e6
    gpin, gpout = pr.get("google/gemini-3.7-flash", (0.375, 1.875))
    grade = len(rows) * (1500 * gpin + 120 * gpout) / 1e6
    for d in (1, 3):
        print(f"  {model}  {len(rows)} items x {d} draw(s): generation ${gen * d:.2f} + "
              f"grading ${grade * d:.2f} = ${(gen + grade) * d:.2f}   (input mean {st.mean(tin):.0f} tok)")
    print("  ESTIMATE: price-sheet x character/4 tokens; 300 output tokens assumed per answer.")


def report(cand):
    p = ROOT / "pilot_out" / f"pilot_{cand}.jsonl"
    if not p.exists():
        sys.exit(f"REFUSED - no {p.name}; nothing to read")
    bank = {json.loads(l)["item_id"]: json.loads(l) for l in OUTB.read_text(encoding="utf-8").splitlines() if l.strip()}
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    cells = {}
    for r in rows:
        it = bank.get(r["item_id"])
        if not it or r["verdict"] not in ("PASS", "FAIL"):
            continue
        key = (it["arm"], it.get("k", it.get("chars")), it.get("history", ""))
        ok_receipt = not FC.check(r.get("text", "")) if r.get("text") else None
        cells.setdefault(key, []).append((r["verdict"] == "FAIL", ok_receipt))
    print(f"{'arm':<8}{'level':>8}{'history':>9}{'n':>6}{'fail':>8}{'receipt ok':>12}{'ceremonial':>12}")
    for key in sorted(cells, key=lambda k: (k[0], k[1] or 0, k[2])):
        v = cells[key]
        f = sum(x for x, _ in v) / len(v)
        rk = [y for _, y in v if y is not None]
        cer = sum(1 for x, y in v if x and y) / len(v)
        print(f"{key[0]:<8}{key[1]!s:>8}{key[2]:>9}{len(v):>6}{f:>8.1%}"
              f"{(sum(rk) / len(rk) if rk else float('nan')):>12.1%}{cer:>12.1%}")
    print("Paired tests: run compare.py on per-level subsets; a level is reportable only if its")
    print("item interval against depth 0 excludes zero (pre-registered, see the INTENT).")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "build":
        build()
    elif cmd == "cost" and len(sys.argv) == 3:
        cost(sys.argv[2])
    elif cmd == "report" and len(sys.argv) == 3:
        report(sys.argv[2])
    else:
        sys.exit(__doc__.split("\n\n")[1])
