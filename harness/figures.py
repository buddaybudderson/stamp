#!/usr/bin/env python3
"""
THE FIGURE REGISTRY. Every number that can be published, and the evidence for it.

    python scripts/figures.py build            compute the registry from the data
    python scripts/figures.py list             show every citable figure
    python scripts/figures.py check report.md  verify every citation resolves
    python scripts/figures.py render report.md fill the citations in, to stdout

THE RULE THIS ENFORCES: you do not type numbers into a report. You cite them.

A report is written with placeholders - `[FIG nemo_v1.fail_rate]` - and the renderer
substitutes the value, its interval and its scope from figures.json. A number that
cannot be computed from a file on disk cannot appear in a document, because there is
no way to write it down. Recalled figures, borrowed benchmarks and remembered prices
have no route in.

Every figure carries the SHA-256 of each file it was computed from. If the data
changes, the hash changes, and a stale figure is detectable rather than merely
suspected. That is what makes a published number checkable by a stranger - which is
the entire product an independent evaluator sells.

Figures also carry their CONDITIONS - grader, provider, temperature, bank, draw
count - because 43.3% is not a property of a model. It is a property of a model
measured a particular way, and a rate quoted without its conditions is not evidence.
"""
import collections, hashlib, importlib.util, json, pathlib, re, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
REG = ROOT / "figures.json"
_sp = importlib.util.spec_from_file_location("stats", ROOT / "scripts" / "stats.py")
S = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(S)


def sha(p):
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()[:16]


def source(p):
    return {"path": str(p.relative_to(ROOT)), "sha256_16": sha(p),
            "bytes": p.stat().st_size}


def load_pilot(paths):
    latest = {}
    for p in paths:
        for l in p.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                latest[(p.name, r["item_id"], r["draw"])] = r
    return list(latest.values())


def build():
    figs = {}

    def add(fid, value, unit, sources, conditions, interval=None, scope=None, note=""):
        figs[fid] = {"value": value, "unit": unit, "interval": interval,
                     "scope": scope, "conditions": conditions,
                     "sources": sources, "note": note,
                     "computed_at": time.strftime("%Y-%m-%dT%H:%M:%S")}

    # ---------------------------------------------------------- candidate rates
    for cfgp in sorted((ROOT / "pilot_out").glob("pilot_*_A.config.json")):
        cand = cfgp.name[len("pilot_"):-len("_A.config.json")]
        cfg = json.loads(cfgp.read_text(encoding="utf-8"))
        paths = [p for h in ("A", "B")
                 if (p := ROOT / "pilot_out" / f"pilot_{cand}_{h}.jsonl").exists()]
        if not paths:
            continue
        rows = load_pilot(paths)
        per = S.per_item_from_rows(rows)
        if not per:
            continue
        st = S.rate(per)
        outstanding = sum(1 for r in rows if r["verdict"] == "ERROR")
        prov = sorted({r.get("served_by") for r in rows
                       if r["verdict"] in ("PASS", "FAIL")})
        cond = {"model": cfg.get("model"), "grader": cfg.get("grader"),
                "bank": cfg.get("bank"), "draws": cfg.get("draws"),
                "temperature": cfg.get("temperature", 0.7),
                "max_tokens": cfg.get("max_tokens"),
                "providers_observed": prov,
                "config_reconstructed": bool(cfg.get("reconstructed")),
                "incomplete_draws_outstanding": outstanding}
        srcs = [source(p) for p in paths] + [source(cfgp)]
        add(f"{cand}.fail_rate", st["mean_over_draws"], "rate", srcs, cond,
            [st["on_bank_low"], st["on_bank_high"]], "on bank v1",
            "week-on-week comparison uses this interval")
        add(f"{cand}.fail_rate_general", st["mean_over_draws"], "rate", srcs, cond,
            [st["beyond_bank_low"], st["beyond_bank_high"]], "beyond the bank",
            "any claim about the model uses this interval")
        for k, u in (("n_items", "count"), ("n_draws", "count"),
                     ("at_floor_or_ceiling", "count"), ("probabilistic", "count"),
                     ("icc", "coefficient"), ("design_effect", "factor"),
                     ("sd_across_items", "sd")):
            add(f"{cand}.{k}", st[k], u, srcs, cond)

    # ------------------------------------------------------------------- panel
    for p in sorted((ROOT / "panel_out").glob("panel_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        cand = d["candidate"]
        jl = p.with_suffix(".jsonl")
        srcs = [source(p)] + ([source(jl)] if jl.exists() else [])
        cond = {"tier1_grader": d["tier1_grader"],
                "panel": [j["model"] for j in d["panel"]],
                "sampled_draws": d["sampled"], "of_graded": d["graded_draws"],
                "recusal": d.get("recusal")}
        add(f"{cand}.panel_ac1", d["ac1"], "coefficient", srcs, cond,
            d.get("ac1_ci"), "sampled draws", d["gate"])
        add(f"{cand}.panel_fleiss", d["fleiss_kappa"], "coefficient", srcs, cond)
        add(f"{cand}.tier1_overruled", d["tier1_overruled_rate"], "rate", srcs, cond,
            d.get("tier1_overruled_ci"), "sampled draws",
            "rate at which a majority of three overturned the tier-1 grader")
        for jid, fr in d["per_judge_fail_rate"].items():
            add(f"{cand}.judge_{jid}.fail_rate", fr, "rate", srcs, cond, None,
                "sampled draws", "leniency: same draws, so spread is the judge")

    # ------------------------------------------------------------ reliability
    for p in sorted((ROOT / "pilot_out").glob("reliability_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        cand = d["candidate"]
        srcs = [source(p)]
        cond = {"halves": "A vs B, independent replications of the whole bank",
                "n_items": d["n_items"]}
        add(f"{cand}.half_a", d["half_a_rate"], "rate", srcs, cond)
        add(f"{cand}.half_b", d["half_b_rate"], "rate", srcs, cond)
        add(f"{cand}.retest_gap", d["gap"], "rate", srcs, cond, None, None,
            "the noise floor - no effect smaller than this is reportable")
        add(f"{cand}.retest_r", d["correlation"], "correlation", srcs, cond)
        add(f"{cand}.spearman_brown", d["spearman_brown"], "correlation", srcs, cond)
        add(f"{cand}.items_unstable", len(d["unstable"]), "count", srcs, cond, None,
            None, "per-item verdicts for these must not be published")

    REG.write_text(json.dumps(figs, indent=2, sort_keys=True), encoding="utf-8")
    return figs


def fmt(f):
    v, u = f["value"], f["unit"]
    s = f"{v:.1%}" if u == "rate" else (f"{v:.3f}" if isinstance(v, float) else str(v))
    if f.get("interval") and f["interval"][0] is not None:
        lo, hi = f["interval"]
        s += (f" [{lo:.1%}, {hi:.1%}]" if u == "rate" else f" [{lo:.3f}, {hi:.3f}]")
    if f.get("scope"):
        s += f" ({f['scope']})"
    return s


CITE = re.compile(r"\[FIG ([A-Za-z0-9_.\-]+)\]")


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "build"
    if action == "build":
        figs = build()
        print(f"wrote {REG.relative_to(ROOT)} - {len(figs)} citable figures")
        print("\nEvery one carries its sources' SHA-256 and the conditions it was")
        print("measured under. Cite them in a report as [FIG <id>]; nothing else"
              " may be typed.")
        return 0
    if not REG.exists():
        sys.exit("no figures.json - run: python scripts/figures.py build")
    figs = json.loads(REG.read_text(encoding="utf-8"))

    if action == "list":
        for k in sorted(figs):
            f = figs[k]
            print(f"  [FIG {k}]".ljust(44) + fmt(f))
            if f.get("note"):
                print(f"      {f['note']}")
        print(f"\n{len(figs)} figures. Sources are recorded per figure in figures.json.")
        return 0

    if action in ("check", "render"):
        if len(sys.argv) < 3:
            sys.exit(f"usage: python scripts/figures.py {action} <file>")
        doc = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")
        cited = CITE.findall(doc)
        missing = sorted({c for c in cited if c not in figs})
        if action == "render":
            if missing:
                sys.exit("REFUSING TO RENDER - unknown figure(s): " + ", ".join(missing))
            print(CITE.sub(lambda m: fmt(figs[m.group(1)]), doc))
            return 0
        print(f"{len(cited)} citation(s), {len(set(cited))} distinct")
        if missing:
            print("\nUNKNOWN FIGURES - these cite nothing that exists:")
            for m in missing:
                print(f"    [FIG {m}]")
            print("\nA number that cannot be computed from a file on disk cannot be")
            print("published. Either add it to figures.py or delete the claim.")
            return 1
        # a bare number next to a citation is a number somebody typed
        stray = re.findall(r"(?<!\[FIG )\b\d+\.\d+%", doc)
        print("all citations resolve.")
        if stray:
            print(f"\nWARNING: {len(stray)} hand-typed percentage(s) found: "
                  f"{', '.join(stray[:6])}")
            print("  Hand-typed numbers are the ones that go stale. Cite them instead.")
        return 0

    sys.exit(f"unknown action {action!r}")


if __name__ == "__main__":
    sys.exit(main())
