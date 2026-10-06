"""COST AGAINST QUALITY. Which candidates are worth their price on this bank?

    python scripts/pareto.py nemo_v1 luna_v1 [...]          table + reports/pareto.svg
    python scripts/pareto.py nemo_v1 luna_v1 --by-category  the frontier per probe family

  exit 0 = table written    exit 2 = refused (no usable runs)

THE AXES. Quality is the fail rate on bank v1 with its ON-BANK interval (stats.py) - the
right interval for "this model, this bank". Cost is dollars per 1,000 answers for
GENERATION ONLY. Grading is the instrument's cost, not the model's, and is reported
beside it, never inside it.

WHERE THE DOLLARS COME FROM, and every row says which:

  measured    usage.cost recorded per call (pilot_native.py since 2026-09; regrade.py and
              panel_grade.py since 2026-10-05). What was actually charged.
  estimated   price-sheet x tokens. Used only when a run predates cost recording. Output
              tokens come from the run (reasoning_tokens + chars/4); prices come from
              cost_estimate.py's PRICE table, which is dated and goes stale - Gemini's
              price doubled in 24 hours during measurement one. An estimated row is
              marked, and the chart draws it hollow.

A candidate is ON THE FRONTIER if no other candidate is both cheaper and fails less. With
intervals that overlap, "dominates" is a reading of two point estimates; the table prints
whether compare.py would call the quality difference real, so the chart is not read as
more than the data says.

"Per tenant" in a product is "per probe family" here: --by-category repeats the frontier
for each category, because a model can be the value pick on arithmetic and the worst
buy on provenance.

Stdlib only. No network.
"""
import ast, collections, importlib.util, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HERE = ROOT / "scripts"
OUT = ROOT / "pilot_out"
_sp = importlib.util.spec_from_file_location("stats", HERE / "stats.py")
S = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(S)


def price_table():
    """PRICE from cost_estimate.py, read as data - importing it would run its report."""
    tree = ast.parse((HERE / "cost_estimate.py").read_text(encoding="utf-8"))
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "PRICE" for t in n.targets):
            return ast.literal_eval(n.value)
    return {}


def load(cand):
    rows, model = [], None
    for half in ("A", "B"):
        p = OUT / f"pilot_{cand}_{half}.jsonl"
        c = OUT / f"pilot_{cand}_{half}.config.json"
        if c.exists() and not model:
            model = json.loads(c.read_text(encoding="utf-8")).get("model")
        if p.exists():
            last = {}
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    last[(r["item_id"], str(r["draw"]))] = r
            rows += list(last.values())
    return rows, model


def cost_per_1000(rows, model, prices):
    measured = [r["cost_model"] for r in rows if r.get("cost_model") is not None]
    if measured and len(measured) >= 0.9 * len(rows):
        return 1000 * sum(measured) / len(measured), "measured"
    if model not in prices:
        return None, "no price"
    pin, pout = prices[model]
    tin = 150                                    # native arm: the prompt alone, measured mean
    tout = [int(r.get("reasoning_tokens") or 0) + int(r.get("chars") or 0) / 4 for r in rows]
    per = (tin * pin + (sum(tout) / len(tout)) * pout) / 1e6
    return 1000 * per, "estimated"


def frontier(points):
    """points: [(name, cost, fail)] -> set of names no other point beats on both axes."""
    out = set()
    for n, c, f in points:
        if not any((c2 <= c and f2 <= f) and (c2 < c or f2 < f) for n2, c2, f2 in points if n2 != n):
            out.add(n)
    return out


def svg(points, path):
    """A small, theme-neutral scatter. Hollow = estimated cost. Labelled directly."""
    W, H, L, B, T, R = 560, 340, 64, 44, 20, 140
    xs = [p["cost"] for p in points]; ys = [p["fail"] for p in points]
    xmax = max(xs) * 1.15 or 1; ymax = min(1.0, max(p["hi"] for p in points) * 1.15)
    X = lambda v: L + (W - L - R) * v / xmax
    Y = lambda v: H - B - (H - B - T) * v / ymax
    g = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="system-ui,sans-serif" font-size="12">',
         '<style>.ax{stroke:currentColor;opacity:.35}.t{fill:currentColor}.m{fill:currentColor;opacity:.7}</style>',
         f'<line class="ax" x1="{L}" y1="{H-B}" x2="{W-R}" y2="{H-B}"/>',
         f'<line class="ax" x1="{L}" y1="{T}" x2="{L}" y2="{H-B}"/>',
         f'<text class="m" x="{(L+W-R)/2}" y="{H-8}" text-anchor="middle">$ per 1,000 answers (generation only)</text>',
         f'<text class="m" transform="translate(16 {(T+H-B)/2}) rotate(-90)" text-anchor="middle">fail rate on bank v1</text>']
    for i in range(5):
        v = ymax * i / 4
        g.append(f'<text class="m" x="{L-8}" y="{Y(v)+4}" text-anchor="end">{v:.0%}</text>')
        v = xmax * i / 4
        g.append(f'<text class="m" x="{X(v)}" y="{H-B+16}" text-anchor="middle">{v:.2f}</text>')
    for p in points:
        x, y = X(p["cost"]), Y(p["fail"])
        g.append(f'<line class="t" stroke="currentColor" x1="{x}" y1="{Y(p["lo"])}" x2="{x}" y2="{Y(p["hi"])}" opacity=".5"/>')
        fill = "currentColor" if p["src"] == "measured" else "none"
        g.append(f'<circle cx="{x}" cy="{y}" r="5" fill="{fill}" stroke="currentColor" stroke-width="1.5"/>')
        g.append(f'<text class="t" x="{x+9}" y="{y+4}">{p["name"]}{" *" if p["front"] else ""}</text>')
    g.append(f'<text class="m" x="{W-R+8}" y="{T+10}">* on the frontier</text>')
    g.append(f'<text class="m" x="{W-R+8}" y="{T+26}">hollow = estimated $</text>')
    g.append("</svg>")
    path.write_text("\n".join(g), encoding="utf-8")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    by_cat = "--by-category" in sys.argv
    if not args:
        sys.exit(__doc__.split("\n\n")[1])
    prices = price_table()
    pts = []
    for cand in args:
        rows, model = load(cand)
        if not rows:
            print(f"  {cand}: no run files - skipped"); continue
        cost, src = cost_per_1000(rows, model, prices)
        if cost is None:
            print(f"  {cand}: no measured cost and no price for {model} - skipped"); continue
        per = S.per_item_from_rows(rows)
        r = S.rate(per)
        cats = collections.defaultdict(list)
        for row in rows:
            if row["verdict"] in ("PASS", "FAIL"):
                cats[row.get("category", "?")].append(row["verdict"] == "FAIL")
        pts.append({"name": cand, "model": model, "cost": cost, "src": src,
                    "fail": r["mean_over_draws"], "lo": r["on_bank_low"], "hi": r["on_bank_high"],
                    "cats": {k: sum(v) / len(v) for k, v in cats.items()}})
    if not pts:
        print("REFUSED - no candidate had both a run and a cost")
        return 2
    fr = frontier([(p["name"], p["cost"], p["fail"]) for p in pts])
    for p in pts:
        p["front"] = p["name"] in fr
    print(f"{'candidate':<14}{'model':<34}{'$/1000':>9}  {'source':<10}{'fail':>7}  on-bank 95% CI      frontier")
    for p in sorted(pts, key=lambda p: p["cost"]):
        print(f"{p['name']:<14}{(p['model'] or '?')[:33]:<34}{p['cost']:>9.3f}  {p['src']:<10}"
              f"{p['fail']:>7.1%}  [{p['lo']:.1%}, {p['hi']:.1%}]   {'yes' if p['front'] else ''}")
    if any(p["src"] == "estimated" for p in pts):
        print("  estimated = price-sheet x measured output tokens; the run predates cost recording.")
    if by_cat:
        print("-" * 90)
        cats = sorted({c for p in pts for c in p["cats"]})
        for c in cats:
            cp = [(p["name"], p["cost"], p["cats"][c]) for p in pts if c in p["cats"]]
            f = frontier(cp)
            print(f"  {c:<26}" + "   ".join(f"{n} {v:.0%}{'*' if n in f else ''}" for n, _, v in cp))
    out = ROOT / "reports" / "pareto.svg"
    svg(pts, out)
    print(f"chart: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
