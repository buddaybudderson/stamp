#!/usr/bin/env python3
"""
TIER 2 - the panel. Validates the tier-1 grader instead of trusting it.

  python scripts/panel_grade.py <candidate> [--dry] [--rate 0.20]

The tier-1 grader scored 100% of draws alone. That number is only defensible if
somebody checked it. This seats three judges on a stratified sample plus every
contested item, and publishes the agreement - per protocol/PANEL.md.

WHAT IT REPORTS
  Gwet's AC1        the headline. NOT Fleiss' kappa: with defect prevalence low,
                    the prevalence paradox reads 97% raw agreement as kappa ~ 0.1.
                    Fleiss and raw agreement are printed too, so the gap is visible
                    rather than asserted.
  per-judge leniency  each judge's FAIL rate on the SAME draws. A judge 10+ points
                    off the others is flagged. This is the bias that survives in
                    single-response grading; position bias does not apply here.
  tier-1 error rate estimated from how often the majority of three overrules the
                    tier-1 grader, extrapolated to the unsampled remainder with a
                    bootstrap interval.

PRE-REGISTERED THRESHOLDS (protocol/PANEL.md, not negotiable after seeing data)
  AC1 >= 0.70   tier-1 results stand; publish
  0.50 - 0.70   publish with the agreement figure in the headline, not a footnote
  AC1 <  0.50   DO NOT publish per-item verdicts. The criteria are ambiguous.
                Rewrite the disagreed items and re-run. A low AC1 is not a reason
                to add judges. It is a reason to fix the questions.

Resumes. Stdlib only. Env: STAGE1_API_KEY, STAGE1_BASE_URL.
"""
import argparse, ast, collections, hashlib, json, math, os, pathlib, random, re, sys, time
import urllib.request, urllib.error

ROOT   = pathlib.Path(__file__).resolve().parent.parent
OUTDIR = ROOT / "panel_out"
BASE   = os.environ.get("STAGE1_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
KEY    = os.environ.get("STAGE1_API_KEY", "")
MAXTOK = int(os.environ.get("PANEL_MAX_TOKENS") or 16384)
SLEEP  = float(os.environ.get("SLEEP") or 0.6)

# ---------------------------------------------------------------------------
# ONE SOURCE OF TRUTH FOR THE INSTRUMENT.
# The panel must grade with the identical prompt and the identical verdict parser
# as the tier-1 grader, or the agreement statistic measures the harness rather than
# the judges. Both are lifted out of pilot_native.py's SOURCE - the template by
# literal_eval, the parser by exec'ing that one pure function - so no second copy
# exists to drift. If pilot_native.py changes shape, this fails at startup.
# ---------------------------------------------------------------------------
PARSER_EXPORT = "parse_verdict"

def _lift_from_runner():
    src = (ROOT / "scripts" / "pilot_native.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    tmpl = None
    fn_node = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "GRADE_TMPL" for t in node.targets):
            tmpl = ast.literal_eval(node.value)
        if isinstance(node, ast.FunctionDef) and node.name == PARSER_EXPORT:
            fn_node = node
    if tmpl is None:
        sys.exit("panel_grade: could not find GRADE_TMPL in pilot_native.py - "
                 "the panel refuses to invent its own grading prompt.")
    if fn_node is None:
        sys.exit(f"panel_grade: could not find {PARSER_EXPORT}() in pilot_native.py - "
                 "the panel refuses to invent its own verdict parser.")
    ns = {"json": json, "re": re}
    exec(compile(ast.Module(body=[fn_node], type_ignores=[]), "<pilot_native>", "exec"), ns)
    return tmpl, ns[PARSER_EXPORT]

GRADE_TMPL, parse_verdict = _lift_from_runner()

# Proof the lifted parser behaves, checked every run against cases taken from real
# grader output. A silent parser change would move every rate in the report.
for _text, _finish, _want in [
    ('{"verdict": "FAIL", "why": "invented a price"}', "stop", "FAIL"),
    ('{"verdict":"PASS","why":"declined correctly"}',  "stop", "PASS"),
    ('{"verdict": "FAIL", "why": "the response asserts a figure it cannot',
                                                        "stop", "FAIL"),   # unterminated
    ("", "length", "UNPARSED"),
    ("I think this one is fine, really.", "stop", "UNPARSED"),
]:
    _got = parse_verdict(_text, _finish, 0, None)[0]
    if _got != _want:
        sys.exit(f"panel_grade: lifted parser returned {_got!r}, expected {_want!r}. "
                 f"pilot_native.parse_verdict has changed behaviour - stop and check.")


# ------------------------------------------------------------------ judges
def load_panel(candidate_slug):
    """Seat the panel, applying the recusal rule. Returns (seated, recused, note)."""
    cfg = json.loads((ROOT / "protocol" / "judges.json").read_text(encoding="utf-8"))
    seated, reserve = cfg["seated"], cfg["reserve"]
    # A judge must not grade its own lineage. Matching on judges.json's `family`
    # ALONE is not enough and the test caught it: x-ai/grok-4.6 has family "grok",
    # so a grok candidate did not recuse J-B - a judge would have graded itself and
    # nothing would have complained. Compare the union of {vendor prefix, family} on
    # both sides, with prefix matching so 'bytedance-seed' still meets 'bytedance'.
    def tokens(slug, family=None):
        t = {(slug.split("/")[0] or "").lower()}
        if family:
            t.add(family.lower())
        return {x for x in t if len(x) >= 4}

    cand_t = tokens(candidate_slug)

    def clashes(j):
        if j["model"].lower() == candidate_slug.lower():
            return True                       # a model may never grade itself
        jt = tokens(j["model"], j.get("family"))
        return any(a.startswith(b) or b.startswith(a) for a in cand_t for b in jt)
    recused = [j for j in seated if clashes(j)]
    panel = [j for j in seated if not clashes(j)]
    note = ""
    if recused:
        if not reserve:
            sys.exit("recusal needed but no reserve judge is configured")
        panel.append(reserve[0])
        note = (f"{recused[0]['id']} ({recused[0]['model']}) RECUSED - same family as the "
                f"candidate. {reserve[0]['id']} ({reserve[0]['model']}) seated in its place.")
    if len(recused) > 1:
        sys.exit("more than one judge recused - the panel design assumes at most one")
    return panel, recused, note


# ------------------------------------------------------------------ data
def load_runs(cand):
    """Pool halves A and B at temp 0.7. Returns rows keyed (item_id, half, draw)."""
    rows, cfgs = {}, {}
    for half in ("A", "B"):
        p = ROOT / "pilot_out" / f"pilot_{cand}_{half}.jsonl"
        if not p.exists():
            continue
        c = p.with_suffix(".config.json")
        if c.exists():
            cfgs[half] = json.loads(c.read_text(encoding="utf-8"))
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                rows[(r["item_id"], half, r["draw"])] = r      # last write wins
    return rows, cfgs


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
            last = f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"
            if e.code in (400, 401, 402, 404):
                break
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(2 * (attempt + 1))
    return {"text": "", "finish": "error", "reasoning_tokens": 0,
            "served_by": "?", "err": last}


# ------------------------------------------------------------------ sampling
def build_sample(rows, items, rate, cand):
    """THE SAMPLING RULE, published with every report so it can be checked.

    Unit          one draw.
    Stratum       (category, tier-1 verdict). Stratifying on the verdict too keeps
                  PASS and FAIL draws both represented; a 20% simple random sample of
                  a 63%-PASS dataset can starve the FAIL side, which is the side that
                  carries the finding.
    Selection     deterministic - sha256(candidate|item|half|draw), lowest hashes
                  first. No RNG state, no seed to lose, reproducible by a third party
                  from this file alone.
    Augmentation  every CONTESTED item (tier-1 not unanimous across its draws) gets at
                  least one PASS draw and one FAIL draw in the sample. Disagreement
                  within an item is the signature of an ambiguous criterion, which is
                  what the panel is for.
    """
    cat_of = {i["item_id"]: i.get("category", "?") for i in items}
    graded = {k: r for k, r in rows.items() if r["verdict"] in ("PASS", "FAIL")}

    def h(k):
        return hashlib.sha256(f"{cand}|{k[0]}|{k[1]}|{k[2]}".encode()).hexdigest()

    strata = collections.defaultdict(list)
    for k, r in graded.items():
        strata[(cat_of.get(k[0], "?"), r["verdict"])].append(k)

    chosen, why = set(), {}
    for st, keys in strata.items():
        keys.sort(key=h)
        take = max(1, math.ceil(len(keys) * rate))
        for k in keys[:take]:
            chosen.add(k); why[k] = "stratified"

    # contested items
    by_item = collections.defaultdict(list)
    for k, r in graded.items():
        by_item[k[0]].append((k, r["verdict"]))
    contested = []
    for iid, lst in by_item.items():
        vs = {v for _, v in lst}
        if len(vs) > 1:
            contested.append(iid)
            for want in ("PASS", "FAIL"):
                side = sorted([k for k, v in lst if v == want], key=h)
                if side and not any(k in chosen for k in side):
                    chosen.add(side[0]); why[side[0]] = "contested"
    return sorted(chosen), why, contested, len(graded)


# ------------------------------------------------------------------ statistics
def gwet_ac1(ratings):
    """ratings: list of lists, one inner list of category labels per subject.
    Gwet (2008). k=2 here but written for general k."""
    cats = sorted({c for r in ratings for c in r})
    k = len(cats)
    if k < 2:
        return 1.0, 0.0, 1.0            # everyone agreed on everything
    n = len(ratings)
    pa = 0.0
    pi = {c: 0.0 for c in cats}
    for r in ratings:
        ri = len(r)
        if ri < 2:
            continue
        cnt = collections.Counter(r)
        pa += sum(v * (v - 1) for v in cnt.values()) / (ri * (ri - 1))
        for c in cats:
            pi[c] += cnt[c] / ri
    pa /= n
    for c in cats:
        pi[c] /= n
    pe = sum(pi[c] * (1 - pi[c]) for c in cats) / (k - 1)
    return ((pa - pe) / (1 - pe) if pe < 1 else 1.0), pa, pe


def fleiss_kappa(ratings):
    """Printed only to make the prevalence paradox visible next to AC1."""
    cats = sorted({c for r in ratings for c in r})
    if len(cats) < 2:
        return float("nan")
    n = len(ratings)
    r0 = len(ratings[0])
    if any(len(r) != r0 for r in ratings) or r0 < 2:
        return float("nan")             # Fleiss needs a constant rater count
    pj = {c: sum(collections.Counter(r)[c] for r in ratings) / (n * r0) for c in cats}
    pbar = sum(
        (sum(v * v for v in collections.Counter(r).values()) - r0) / (r0 * (r0 - 1))
        for r in ratings) / n
    pe = sum(v * v for v in pj.values())
    return (pbar - pe) / (1 - pe) if pe < 1 else float("nan")


def boot_ci(ratings, stat, iters=2000, seed=20260829):
    rnd = random.Random(seed)
    n = len(ratings)
    if n < 3:
        return None, None
    vals = []
    for _ in range(iters):
        s = [ratings[rnd.randrange(n)] for _ in range(n)]
        try:
            vals.append(stat(s))
        except Exception:
            pass
    if not vals:
        return None, None
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--rate", type=float, default=0.20)
    ap.add_argument("--dry", action="store_true",
                    help="build the sample, price it, grade nothing")
    ap.add_argument("--model", default="", help="candidate slug, if no .config.json exists")
    ap.add_argument("--grader", default="", help="tier-1 grader slug, if no .config.json exists")
    ap.add_argument("--bank", default="", help="bank file, if no .config.json exists")
    a = ap.parse_args()
    cand = a.candidate

    rows, cfgs = load_runs(cand)
    if not rows:
        sys.exit(f"no pilot_out/pilot_{cand}_[AB].jsonl found")
    cfg = next(iter(cfgs.values()), {})

    # RUNS PREDATING THE CONFIG GUARD HAVE NO CONFIG FILE. Do not guess: the
    # candidate slug and the tier-1 grader decide which judges are recused and whose
    # verdicts the panel is validating. Getting either wrong produces a report that
    # looks fine and means nothing. Demand them, then RECORD them as reconstructed so
    # the assumption is on the file rather than in somebody's memory.
    slug  = a.model  or cfg.get("model", "")
    tier1 = a.grader or cfg.get("grader", "")
    bankf = a.bank   or cfg.get("bank", "bank_v1.jsonl")
    if not slug or not tier1:
        miss = [f for f, v in (("--model", slug), ("--grader", tier1)) if not v]
        sys.exit(
            f"pilot_out/pilot_{cand}_[AB].config.json does not record "
            f"{' and '.join(x.lstrip('-') for x in miss)}.\n"
            f"This run predates the config guard, so the settings are not on disk.\n"
            f"Pass them explicitly and they will be written down as reconstructed:\n\n"
            f"  python scripts/panel_grade.py {cand} "
            f"{' '.join(m + ' <slug>' for m in miss)} --dry\n\n"
            f"The candidate slug decides recusal; the grader slug decides whose\n"
            f"verdicts are being validated. Neither is safe to assume.")
    if not cfg or (a.model or a.grader or a.bank):
        rec = {"model": slug, "grader": tier1, "bank": bankf,
               "reconstructed": True,
               "note": ("supplied on the command line to panel_grade.py; this run "
                        "predates the config guard, so these values were NOT recorded "
                        "at run time and are an assertion, not evidence")}
        for half in ("A", "B"):
            p = ROOT / "pilot_out" / f"pilot_{cand}_{half}.jsonl"
            if p.exists() and not p.with_suffix(".config.json").exists():
                p.with_suffix(".config.json").write_text(
                    json.dumps(rec, indent=2), encoding="utf-8")
        print(f"  NOTE  config reconstructed from the command line and written to disk,")
        print(f"        flagged \"reconstructed\": true. Every report built on it must")
        print(f"        say so.\n")
    items  = [json.loads(l) for l in (ROOT / "bank" / bankf).read_text(
                encoding="utf-8").splitlines() if l.strip()]
    by_id  = {i["item_id"]: i for i in items}

    panel, recused, note = load_panel(slug)
    ids = [j["id"] for j in panel]

    # Is the tier-1 grader on the panel? PANEL.md: it MUST be, or the agreement
    # statistic says nothing about the draws it scored alone.
    t1_seat = next((j["id"] for j in panel if j["model"] == tier1), None)
    t1_conflict = ""
    if t1_seat is None:
        # Was it recused? Then the tier-1 grader shares the candidate's lineage and
        # graded its own family for every draw in the dataset. The panel cannot fix
        # that by seating it anyway; it can only report it.
        if any(j["model"] == tier1 for j in recused):
            t1_conflict = (
                f"THE TIER-1 GRADER IS RECUSED. {tier1} graded all "
                f"{len(rows)} draws of {slug}, which is its own lineage. The panel "
                f"will report the disagreement, but this dataset's tier-1 verdicts "
                f"carry a conflict that no agreement statistic removes. PANEL.md: "
                f"the reserve should have graded tier 1 for this candidate.")
        panel.append({"id": "T1", "model": tier1, "family": tier1.split("/")[0],
                      "role": "tier-1 grader, seated so the panel can validate it"})
        t1_seat = "T1"
        ids = [j["id"] for j in panel]

    sample, why, contested, n_graded = build_sample(rows, items, a.rate, cand)

    print("=" * 78)
    print(f"TIER 2 PANEL - {cand}   ({slug})")
    print("=" * 78)
    print(f"  tier-1 grader   {tier1}   seat {t1_seat}")
    print(f"  panel           " + ", ".join(f"{j['id']}={j['model']}" for j in panel))
    if note:
        print(f"  RECUSAL         {note}")
    if t1_conflict:
        import textwrap
        print("\n  " + "!" * 74)
        for ln in textwrap.wrap(t1_conflict, 70):
            print(f"  ! {ln}")
        print("  " + "!" * 74 + "\n")
    print(f"  graded draws    {n_graded}")
    print(f"  sample          {len(sample)} draws = {len(sample)/n_graded:.1%} "
          f"(target {a.rate:.0%} + contested augmentation)")
    print(f"  contested items {len(contested)} of {len({k[0] for k in rows})}")
    print(f"  calls to make   {len(sample)} x {len(panel)-1} unseated judges "
          f"= {len(sample) * (len(panel)-1)}")

    # COST, before spending it. Prices come from protocol/judges.json, which carries
    # the date they were verified; a live lookup happens in preflight below.
    # Per grading call, measured over 598 draws on 2026-08-29: ~1500 in / 120 out.
    # Reasoning judges emit several times that, so the estimate is shown x1 and x4.
    TOK_IN, TOK_OUT = 1500, 120
    # LIVE PRICES WHEN A KEY IS AVAILABLE. judges.json carries prices "verified
    # 2026-08-28/29", and on 2026-08-29 they were already ~19% below what OpenRouter
    # actually charged - which is exactly the recall-versus-verify failure this
    # project keeps re-learning. The catalogue is the authority; the file is a cache.
    live = {}
    if KEY:
        try:
            req = urllib.request.Request(f"{BASE}/models",
                                         headers={"Authorization": f"Bearer {KEY}"})
            with urllib.request.urlopen(req, timeout=30) as r:
                for m in json.loads(r.read().decode())["data"]:
                    p = m.get("pricing", {})
                    live[m["id"]] = (float(p.get("prompt", 0)) * 1e6,
                                     float(p.get("completion", 0)) * 1e6)
        except Exception as e:
            print(f"\n  (live prices unavailable: {type(e).__name__} - using judges.json)")

    total_lo = 0.0
    print("\n  ESTIMATED COST" + ("   [live catalogue]" if live else
                                  "   [judges.json - STALE, verify before trusting]"))
    for j in panel:
        if j["id"] == t1_seat:
            print(f"    {j['id']:<4} {j['model']:<34} $0.0000   already graded (tier 1)")
            continue
        pi, po = live.get(j["model"], (j.get("price_in"), j.get("price_out")))
        was = (j.get("price_in"), j.get("price_out"))
        if live.get(j["model"]) and was[0] is not None and abs(pi - was[0]) > 0.001:
            print(f"    {j['id']:<4} {'':<34} PRICE MOVED: judges.json says "
                  f"${was[0]}/${was[1]}, catalogue says ${pi}/${po} - update the file")
        if pi is None or po is None:
            print(f"    {j['id']:<4} {j['model']:<34} price unknown - VERIFY")
            continue
        c = len(sample) * (TOK_IN * pi + TOK_OUT * po) / 1e6
        total_lo += c
        print(f"    {j['id']:<4} {j['model']:<34} ${c:6.3f}   (${c*4:.2f} if it reasons heavily)")
    print(f"    {'':<4} {'TOTAL':<34} ${total_lo:6.3f}   worst case ${total_lo*4:.2f}")
    print(f"    NOTE: each call RESERVES its full {MAXTOK:,} max_tokens against your")
    print(f"    balance up front, so you need headroom well above the estimate.")

    if a.dry:
        print("\n--dry: nothing graded. Drop --dry to run.")
        return

    if not KEY:
        sys.exit("STAGE1_API_KEY is empty. Set it in this shell and re-run.")

    # PREFLIGHT. Judge slugs move; a dead one fails every call in the run. The
    # standing rule is that slugs are verified against the live catalogue, not
    # recalled - so this is a gate, not a reminder.
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from preflight import preflight
        judges = [j["model"] for j in panel if j["id"] != t1_seat]
        # Each judge grades each sampled draw once - so len(sample) calls PER JUDGE,
        # not len(sample)*len(judges) calls costing every judge's price. Passing the
        # product overestimated by 2.4x and blocked a run with $13.56 in the account.
        if not preflight(BASE, KEY, judges, len(sample), pin=None,
                         model_calls={m: len(sample) for m in judges}):
            sys.exit("panel_grade: preflight blocked the run.")
    except ImportError:
        print("  WARNING: scripts/preflight.py not found - running unchecked.")

    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = OUTDIR / f"panel_{cand}.jsonl"
    done = {}
    if out.exists():
        for l in out.read_text(encoding="utf-8").splitlines():
            if l.strip():
                d = json.loads(l)
                if d["verdict"] in ("PASS", "FAIL"):
                    done[(d["judge"], d["item_id"], d["half"], d["draw"])] = d["verdict"]

    todo = [(j, k) for j in panel if j["id"] != t1_seat for k in sample
            if (j["id"], k[0], k[1], k[2]) not in done]
    print(f"  already done    {len(done)}   to grade now {len(todo)}\n")

    t0 = time.time()
    with out.open("a", encoding="utf-8") as fh:
        for n, (j, k) in enumerate(todo, 1):
            iid, half, draw = k
            item, row = by_id[iid], rows[k]
            prompt = GRADE_TMPL.format(crit=item["pass_criterion"],
                                       ask=item["messages"][-1]["content"],
                                       resp=(row.get("response") or row.get("text") or "")[:6000])
            r = call(j["model"], prompt)
            v, wy, fin = parse_verdict(r["text"], r["finish"], r["reasoning_tokens"], r["err"])
            fh.write(json.dumps({"judge": j["id"], "model": j["model"], "item_id": iid,
                                 "half": half, "draw": draw, "verdict": v, "why": wy,
                                 "finish": fin, "reasoning_tokens": r["reasoning_tokens"],
                                 "served_by": r["served_by"],
                                 "selected_by": why.get(k, "?")}) + "\n")
            fh.flush()
            if v in ("PASS", "FAIL"):
                done[(j["id"], iid, half, draw)] = v
            if n % 10 == 0 or n == len(todo):
                el = time.time() - t0
                print(f"    {n}/{len(todo)}  {el/n:.1f}s/call  "
                      f"eta {(len(todo)-n)*el/n/60:.0f}m")
            time.sleep(SLEEP)

    # tier-1 verdicts fill that judge's column
    for k in sample:
        done[(t1_seat, k[0], k[1], k[2])] = rows[k]["verdict"]

    report(cand, slug, tier1, t1_seat, panel, sample, rows, done, why,
           contested, n_graded, note, a.rate, out, t1_conflict)


def report(cand, slug, tier1, t1_seat, panel, sample, rows, done, why,
           contested, n_graded, note, rate, out, t1_conflict=""):
    ids = [j["id"] for j in panel]
    ratings, complete = [], []
    for k in sample:
        col = [done.get((i, k[0], k[1], k[2])) for i in ids]
        if all(c in ("PASS", "FAIL") for c in col):
            ratings.append(col); complete.append(k)

    # ATTRITION FIRST. A judge that fails to return a parseable verdict does not
    # error - it silently drops that draw from the panel, and the AC1 is then computed
    # on whatever survived. J-R was 79% unparseable at the old 400-token cap. If that
    # is not printed, a shrinking n looks like a small sample rather than a broken
    # judge, and the agreement statistic is computed over a biased remnant.
    print("\n" + "=" * 78)
    print("JUDGE ATTRITION - who actually answered")
    print("=" * 78)
    att = collections.defaultdict(collections.Counter)
    burn = collections.defaultdict(list)
    if out.exists():
        for l in out.read_text(encoding="utf-8").splitlines():
            if l.strip():
                d = json.loads(l)
                att[d["judge"]][d["verdict"]] += 1
                burn[d["judge"]].append(d.get("reasoning_tokens", 0))
    for j in panel:
        i = j["id"]
        if i == t1_seat:
            print(f"  {i:<4} {j['model']:<34} tier-1 verdicts, already on file")
            continue
        c = att[i]
        n = sum(c.values())
        bad = c["UNPARSED"] + c["ERROR"] + c["TRUNCATED"]
        rb = bad / n if n else 0
        rt = burn[i]
        mx = max(rt) if rt else 0
        flag = "   <-- UNRELIABLE JUDGE, see below" if rb > 0.10 else ""
        print(f"  {i:<4} {j['model']:<34} {n:>4} calls  "
              f"PASS {c['PASS']:>3}  FAIL {c['FAIL']:>3}  lost {bad:>3} ({rb:.0%})"
              f"  max reasoning {mx:,}{flag}")
        if rb > 0.10:
            print(f"       {bad} of {n} draws returned nothing usable. Raise the budget"
                  f" (PANEL_MAX_TOKENS, now {MAXTOK:,}) and re-run - the script")
            print(f"       resumes, so only the failed draws are re-issued. Do NOT"
                  f" report an AC1 computed around a judge that did not answer.")

    print("\n" + "=" * 78)
    print("AGREEMENT")
    print("=" * 78)
    if t1_conflict:
        print(f"  CONFLICT: {t1_conflict}\n")
    dropped = len(sample) - len(ratings)
    if dropped:
        print(f"  {dropped} of {len(sample)} sampled draws lack a complete panel and are"
              f" excluded.")
    if len(ratings) < 5:
        print(f"  only {len(ratings)} draws have a complete panel - not enough to report.")
        return

    ac1, pa, pe = gwet_ac1(ratings)
    lo, hi = boot_ci(ratings, lambda s: gwet_ac1(s)[0])
    fk = fleiss_kappa(ratings)
    unan = sum(1 for r in ratings if len(set(r)) == 1) / len(ratings)

    print(f"  complete panel on {len(ratings)} of {len(sample)} sampled draws")
    print(f"\n  Gwet's AC1            {ac1:+.3f}"
          + (f"   95% CI [{lo:+.3f}, {hi:+.3f}]" if lo is not None else ""))
    print(f"  Fleiss' kappa         {fk:+.3f}   <- prevalence paradox: read AC1, not this")
    print(f"  raw exact agreement   {unan:.1%}   <- overstates agreement by 33-41 points")
    print(f"  observed pa {pa:.3f}   chance pe {pe:.3f}")

    verdict = ("PUBLISH - tier-1 results stand" if ac1 >= 0.70 else
               "PUBLISH WITH AC1 IN THE HEADLINE, not a footnote" if ac1 >= 0.50 else
               "DO NOT PUBLISH PER-ITEM VERDICTS - rewrite the disagreed criteria and re-run")
    print(f"\n  PRE-REGISTERED GATE -> {verdict}")

    print("\n" + "-" * 78)
    print("PER-JUDGE LENIENCY - same draws, so any spread is the judge, not the sample")
    print("-" * 78)
    fails = {}
    for n, i in enumerate(ids):
        f = sum(1 for r in ratings if r[n] == "FAIL")
        fails[i] = f / len(ratings)
    mean = sum(fails.values()) / len(fails)
    for j in panel:
        d = fails[j["id"]] - mean
        flag = "  <-- 10+ points off the panel mean" if abs(d) >= 0.10 else ""
        seat = "  [tier-1]" if j["id"] == t1_seat else ""
        print(f"  {j['id']:<4} {j['model']:<34} FAIL {fails[j['id']]:>6.1%}  "
              f"{d:+.1%} vs mean{flag}{seat}")

    print("\n" + "-" * 78)
    print("TIER-1 ERROR RATE - how often the majority of three overrules the grader")
    print("  that scored the other draws alone. This is the number that licenses")
    print("  reporting the unsampled remainder.")
    print("-" * 78)
    t1i = ids.index(t1_seat)
    overruled = []
    for k, r in zip(complete, ratings):
        maj = collections.Counter(r).most_common(1)[0][0]
        if maj != r[t1i]:
            overruled.append((k, r[t1i], maj))
    er = len(overruled) / len(ratings)
    elo, ehi = boot_ci(ratings, lambda s: sum(
        1 for r in s if collections.Counter(r).most_common(1)[0][0] != r[t1i]) / len(s))
    print(f"  overruled on {len(overruled)} of {len(ratings)} = {er:.1%}"
          + (f"   95% CI [{elo:.1%}, {ehi:.1%}]" if elo is not None else ""))
    unsampled = n_graded - len(sample)
    print(f"  extrapolated to the {unsampled} unsampled draws: "
          f"~{er*unsampled:.0f} verdicts would move"
          + (f" (CI {elo*unsampled:.0f}-{ehi*unsampled:.0f})" if elo is not None else ""))
    for (k, was, now) in overruled[:12]:
        print(f"      {k[0]:<34} {k[1]}{k[2]}  tier-1 {was} -> panel {now}   [{why.get(k,'?')}]")
    if len(overruled) > 12:
        print(f"      ... and {len(overruled)-12} more")

    res = {"candidate": cand, "model": slug, "tier1_grader": tier1, "tier1_seat": t1_seat,
           "panel": [{"id": j["id"], "model": j["model"]} for j in panel],
           "recusal": note or None, "tier1_conflict": t1_conflict or None,
           "attrition": {k: dict(v) for k, v in att.items()},
           "draws_excluded_incomplete": dropped,
           "sampling_rate_target": rate,
           "graded_draws": n_graded, "sampled": len(sample),
           "complete_panel": len(ratings), "contested_items": contested,
           "ac1": ac1, "ac1_ci": [lo, hi], "fleiss_kappa": fk,
           "raw_exact_agreement": unan, "pa": pa, "pe": pe,
           "per_judge_fail_rate": fails,
           "tier1_overruled_rate": er, "tier1_overruled_ci": [elo, ehi],
           "gate": verdict}
    p = OUTDIR / f"panel_{cand}.json"
    p.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
