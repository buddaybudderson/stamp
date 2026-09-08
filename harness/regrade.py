#!/usr/bin/env python3
"""
Re-grade responses that are already on disk, with a different grader.

    python scripts/regrade.py <candidate> <new-grader> [--label X] [--dry]
    python scripts/regrade.py nemo_v1 google/gemini-3.7-flash --label nemo_v1g

WHY THIS EXISTS. Generation and grading are separate costs, and only one of them
has to be repeated when you change your mind about the grader. Every response is
already stored in the run files. Swapping Seed for Gemini across the whole ladder
means re-grading ~1,300 stored responses, not re-generating them.

WHY IT MATTERS MORE THAN IT SOUNDS. The panel measured Gemini failing 48.0% where
Seed failed 43.2% ON IDENTICAL DRAWS. Grade nemotron with Seed and glm with Gemini
and glm looks five points worse for no reason but the instrument - a difference
larger than most findings worth reporting. **A ladder must be graded by one grader.**
Changing grader mid-programme without re-grading the earlier rungs does not save
money; it destroys the comparison the money was spent on.

WHAT YOU GET FOR FREE. Two independent gradings of the same 1,300 responses, rather
than the 148-draw panel sample. That is a far larger grader-comparison dataset than
the panel could afford, at no extra generation cost.

OUTPUT is a normal candidate under a new label, so reliability.py, panel_grade.py,
figures.py and inventory.py all work on it unchanged. The config records
`generation_from`, so the provenance of the responses is never lost.

ONE HONEST LIMITATION, reported every run: pilot_native stores text[:4000] while the
grader sees response[:6000]. About 2.7% of responses are longer than the store, so
those are re-graded on slightly less text than the original grader saw. They are
counted and listed rather than waved away.
"""
import argparse, ast, importlib.util, json, os, pathlib, re, sys, time
import urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "pilot_out"
BASE = os.environ.get("STAGE1_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
KEY = os.environ.get("STAGE1_API_KEY", "")
MAXTOK = int(os.environ.get("REGRADE_MAX_TOKENS") or 16384)
SLEEP = float(os.environ.get("SLEEP") or 0.4)
STORE_LIMIT = 4000          # what pilot_native.py wrote
GRADER_WINDOW = 6000        # what the grader was shown


def lift():
    """Template and parser out of pilot_native.py's source - one copy, no drift."""
    src = (ROOT / "scripts" / "pilot_native.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    tmpl = fn = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "GRADE_TMPL" for t in node.targets):
            tmpl = ast.literal_eval(node.value)
        if isinstance(node, ast.FunctionDef) and node.name == "parse_verdict":
            fn = node
    if tmpl is None or fn is None:
        sys.exit("regrade: could not lift GRADE_TMPL/parse_verdict from pilot_native.py")
    ns = {"json": json, "re": re}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<pn>", "exec"), ns)
    return tmpl, ns["parse_verdict"]


GRADE_TMPL, parse_verdict = lift()


def call(model, prompt, timeout=180):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": MAXTOK}
    req = urllib.request.Request(
        f"{BASE}/chat/completions", data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read().decode("utf-8"))
            ch = d["choices"][0]
            ctd = (d.get("usage") or {}).get("completion_tokens_details") or {}
            return {"text": ch["message"].get("content") or "",
                    "finish": ch.get("finish_reason", "?"),
                    "reasoning_tokens": ctd.get("reasoning_tokens", 0) or 0,
                    "served_by": d.get("provider", "?"), "err": None}
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read()[:200].decode('utf-8','replace')}"
            if e.code in (400, 401, 402, 404):
                break
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(2 * (attempt + 1))
    return {"text": "", "finish": "error", "reasoning_tokens": 0,
            "served_by": "?", "err": last}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("grader")
    ap.add_argument("--label", default="", help="new candidate label (default <cand>g)")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    label = a.label or (a.candidate + "g")

    bank_file = "bank_v1.jsonl"
    srcs = sorted(OUT.glob(f"pilot_{a.candidate}_*.jsonl")) + \
           sorted(OUT.glob(f"pilot_{a.candidate}_t*_*.jsonl"))
    srcs = [p for p in dict.fromkeys(srcs) if ".config" not in p.name]
    if not srcs:
        sys.exit(f"no pilot_{a.candidate}_*.jsonl found")

    work = []
    truncated = []
    for p in srcs:
        cfgp = p.with_suffix(".config.json")
        cfg = json.loads(cfgp.read_text(encoding="utf-8")) if cfgp.exists() else {}
        bank_file = cfg.get("bank", bank_file)
        # the suffix after the candidate name: "_A", "_t0_A", ...
        suffix = p.stem[len(f"pilot_{a.candidate}"):]
        latest = {}
        for l in p.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                latest[(r["item_id"], r["draw"])] = r
        for r in latest.values():
            if r["verdict"] not in ("PASS", "FAIL"):
                continue          # nothing to re-grade: no response was produced
            if (r.get("chars") or 0) > STORE_LIMIT:
                truncated.append((r["item_id"], r["draw"], r["chars"]))
            work.append((suffix, cfg, r))

    items = {json.loads(l)["item_id"]: json.loads(l)
             for l in (ROOT / "bank" / bank_file).read_text(encoding="utf-8").splitlines()
             if l.strip()}

    print("=" * 78)
    print(f"RE-GRADE  {a.candidate}  ->  {label}")
    print("=" * 78)
    print(f"  new grader        {a.grader}")
    print(f"  source files      {len(srcs)}: " + ", ".join(p.name for p in srcs))
    print(f"  responses to grade {len(work)}   (generation NOT repeated)")
    if truncated:
        print(f"\n  {len(truncated)} response(s) ({len(truncated)/len(work):.1%}) are longer "
              f"than the {STORE_LIMIT:,}-char store,")
        print(f"  so they are re-graded on less text than the original grader saw "
              f"(it had {GRADER_WINDOW:,}).")
        print(f"  Longest: {max(c for _,_,c in truncated):,} chars. These are recorded "
              f"per row as text_truncated.")
    if a.dry:
        print("\n--dry: nothing graded.")
        return 0
    if not KEY:
        sys.exit("STAGE1_API_KEY is empty.")

    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from preflight import preflight
        if not preflight(BASE, KEY, [a.grader], len(work),
                         model_calls={a.grader: len(work)}):
            sys.exit("regrade: preflight blocked the run.")
    except ImportError:
        pass

    by_suffix = {}
    for suffix, cfg, r in work:
        by_suffix.setdefault(suffix, []).append((cfg, r))

    t0 = time.time()
    done_n = 0
    agree = disagree = 0
    for suffix, rows in by_suffix.items():
        out = OUT / f"pilot_{label}{suffix}.jsonl"
        cfgp = out.with_suffix(".config.json")
        cfg0 = rows[0][0]
        if not cfgp.exists():
            cfgp.write_text(json.dumps({
                **{k: v for k, v in cfg0.items() if k != "grader"},
                "grader": a.grader, "generation_from": a.candidate,
                "regraded": True,
                "note": ("responses were generated under candidate "
                         f"'{a.candidate}' and re-graded by {a.grader}; "
                         "generation was not repeated"),
            }, indent=2), encoding="utf-8")
        seen = set()
        if out.exists():
            for l in out.read_text(encoding="utf-8").splitlines():
                if l.strip():
                    d = json.loads(l)
                    if d["verdict"] in ("PASS", "FAIL"):
                        seen.add((d["item_id"], d["draw"]))
        todo = [(c, r) for c, r in rows if (r["item_id"], r["draw"]) not in seen]
        print(f"\n  {out.name}: {len(rows)} rows, {len(seen)} already done, "
              f"{len(todo)} to grade")
        with out.open("a", encoding="utf-8") as fh:
            for n, (cfg, r) in enumerate(todo, 1):
                it = items[r["item_id"]]
                prompt = GRADE_TMPL.format(crit=it["pass_criterion"],
                                           ask=it["messages"][-1]["content"],
                                           resp=(r.get("text") or "")[:GRADER_WINDOW])
                g = call(a.grader, prompt)
                v, why, fin = parse_verdict(g["text"], g["finish"],
                                            g["reasoning_tokens"], g["err"])
                if v in ("PASS", "FAIL"):
                    agree += (v == r["verdict"])
                    disagree += (v != r["verdict"])
                fh.write(json.dumps({**r, "verdict": v, "why": why,
                                     "grader_finish": fin,
                                     "grader_reasoning_tokens": g["reasoning_tokens"],
                                     "grader_served_by": g["served_by"],
                                     "prior_verdict": r["verdict"],
                                     "prior_grader": cfg.get("grader"),
                                     "text_truncated": (r.get("chars") or 0) > STORE_LIMIT},
                                    ensure_ascii=False) + "\n")
                fh.flush()
                done_n += 1
                if done_n % 25 == 0:
                    el = time.time() - t0
                    print(f"    {done_n}/{len(work)}  {el/done_n:.1f}s/call  "
                          f"eta {(len(work)-done_n)*el/done_n/60:.0f}m", flush=True)
                time.sleep(SLEEP)

    tot = agree + disagree
    print("\n" + "=" * 78)
    print("TWO GRADERS ON THE SAME RESPONSES")
    print("=" * 78)
    if tot:
        print(f"  agreed on {agree} of {tot} = {agree/tot:.1%}")
        print(f"  the {disagree} disagreements are the grader, not the model - the")
        print(f"  responses are byte-identical. Run panel_grade.py on '{label}' for")
        print(f"  the chance-corrected version of this number.")
    print(f"\n  new candidate '{label}' is ready for reliability.py / figures.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
