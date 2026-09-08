#!/usr/bin/env python3
"""
PILOT - native arm only. Answers one question and nothing else:

    Do the v1.25 discriminating probes still make a 2026 model fail?

If yes (>=20% native failure), the bank is measurable and the study can proceed.
If no, every item is at ceiling and no amount of judging will produce a result -
which is exactly what killed v1.46 and v1.69. Finding that out costs about $0.50.

No system prompt is used. This measures the baseline, not the protocol.

Env:
  STAGE1_BASE_URL   https://openrouter.ai/api/v1
  STAGE1_API_KEY    your key - set in the shell, never in a file
  STAGE1_MODEL      candidate slug, e.g. openai/gpt-5.6-luna
  STAGE1_CANDIDATE  short label for filenames, e.g. luna
  GRADER_MODEL      REQUIRED, no default. The grader is the instrument; inheriting
                    one from a stale shell makes the result uninterpretable.
  DRAWS             draws per item. The code default is 3; THIS PROGRAMME USES 5,
                    and a 3-draw run cannot be compared with the 5-draw data on
                    disk, nor support reliability or fever. Set it every time.
  STAGE1_PROVIDER   optional: pin the serving provider (recommended)
  STAGE1_QUANT      optional: pin quantization, e.g. fp8

Stdlib only. Resumes: rerun after an interruption and it continues.
"""
import json, os, pathlib, re, sys, time, urllib.request, urllib.error

BASE     = os.environ.get("STAGE1_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
KEY      = os.environ.get("STAGE1_API_KEY", "")
MODEL    = os.environ.get("STAGE1_MODEL", "")
CAND     = os.environ.get("STAGE1_CANDIDATE", "cand")
# NO DEFAULT GRADER. This used to fall back to nvidia/nemotron-3.5-lightning, which
# is itself a CANDIDATE in the price ladder - so a nemotron run with GRADER_MODEL
# unset would have graded itself, and nothing would have said so. The grader is the
# instrument; it is never something to inherit from a stale shell. State it or stop.
GRADER   = os.environ.get("GRADER_MODEL", "")
DRAWS    = int(os.environ.get("DRAWS") or 3)
PROVIDER = os.environ.get("STAGE1_PROVIDER", "")
QUANT    = os.environ.get("STAGE1_QUANT", "")
# Reasoning tokens are drawn from THIS budget, not a separate one - Finding 1.
# 4096 was not enough: bytedance-seed/seed-2-1-turbo spent all 4096 on reasoning
# and emitted 0 visible characters on 5 of 9 truncations. Budget generously; you
# are only charged for tokens actually generated, so a high cap costs nothing on
# models that do not use it.
MAXTOK   = int(os.environ.get("STAGE1_MAX_TOKENS") or 16384)
SLEEP    = float(os.environ.get("SLEEP") or 0.6)

ROOT = pathlib.Path(__file__).resolve().parent.parent
BANK = ROOT / "bank" / os.environ.get("BANK_FILE", "bank_v1.jsonl")
# Two independent halves. Pool them for the answer; compare them for the
# test-retest reliability. Same total calls, two results instead of one.
HALF = os.environ.get("HALF", "").upper()
assert HALF in ("", "A", "B"), "HALF must be A or B"

# NOT named TEMP: that is a built-in Windows variable pointing at the temp folder,
# and reading it crashes the script before it starts.
def _envfloat(name, default):
    v = os.environ.get(name, "")
    try:
        return float(v) if v else default
    except ValueError:
        print(f"WARNING: {name}={v!r} is not a number; using {default}")
        return default

TEMPERATURE = _envfloat("STAGE1_TEMP", 0.7)

# THE FEVER MEASUREMENT. Every model is run twice:
#   temp 0.7, 5 draws/half  - what users actually get. Reliability lives here.
#   temp 0.0, 1 draw/half   - the model's modal answer, its best behaviour.
# fever = failure(0.7) - failure(0.0). A high fever means the model tops a
# leaderboard and then misbehaves for a fraction of real users.
# Bonus: two temp-0 draws that DISAGREE are not the model choosing differently.
# That is pure infrastructure nondeterminism - a direct read on provider stability.
#
# 0.7 keeps the bare filename so every run before 2026-08-29 stays resumable.
_temp_tag = "" if abs(TEMPERATURE - 0.7) < 1e-9 else f"_t{TEMPERATURE:g}".replace(".", "")
_tag = f"{CAND}{_temp_tag}_{HALF}" if HALF else f"{CAND}{_temp_tag}"
OUT  = ROOT / "pilot_out" / f"pilot_{_tag}.jsonl"

# ---- optional system prompt: this is what makes the STAMP arm ---------------
# STAMP_CORE=<path> runs the stamped arm. Unset runs native. NOTHING ELSE about
# the request changes between arms - same model, same temperature, same
# max_tokens, same messages - so any difference is attributable to the core.
CORE_PATH = os.environ.get("STAMP_CORE", "")
SYSTEM = ""
if CORE_PATH:
    _raw = pathlib.Path(CORE_PATH).read_text(encoding="utf-8")
    if "===== CORE START =====" in _raw:
        SYSTEM = _raw.split("===== CORE START =====", 1)[1] \
                     .split("===== CORE END =====", 1)[0].strip()
    else:
        SYSTEM = _raw.strip()
    if not SYSTEM:
        sys.exit(f"ERROR: no core text extracted from {CORE_PATH}")

for name, val in [("STAGE1_API_KEY", KEY), ("STAGE1_MODEL", MODEL)]:
    if not val:
        sys.exit(f"ERROR: {name} is empty. Set it in this shell and re-run.")

if not GRADER:
    _t1 = ""
    try:
        _j = json.loads((ROOT / "protocol" / "judges.json").read_text(encoding="utf-8"))
        _t1 = next((s["model"] for s in _j["seated"] if "tier-1" in s.get("role", "")), "")
    except Exception:
        pass
    sys.exit("ERROR: GRADER_MODEL is not set, and there is deliberately no default.\n"
             "  The grader IS the instrument - a run that inherits one from a stale\n"
             "  shell is a run whose result cannot be interpreted.\n"
             + (f"  protocol/judges.json names the tier-1 grader as:\n"
                f"    $env:GRADER_MODEL = \"{_t1}\"\n" if _t1 else "")
             + "  Runs already on disk used bytedance-seed/seed-2-1-turbo; match that\n"
               "  to extend the existing dataset, and say which one the report used.")


# A JUDGE MUST NOT BE MEASURED AS A CANDIDATE BY ITS OWN PANEL. panel_grade.py
# refuses this at grading time, which is too late - the generation money is already
# spent. On 2026-08-29 a leftover STAGE1_MODEL from a preflight test started a full
# run of google/gemini-3.7-flash graded by x-ai/grok-4.6: two judges, no candidate,
# and the most expensive grader in the panel. The check belongs before the first call.
def _judge_conflict(model, grader):
    p = ROOT / "protocol" / "judges.json"
    if not p.exists():
        return None
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    seats = {j["model"]: j["id"] for j in cfg.get("seated", []) + cfg.get("reserve", [])}
    dual = {d["model"]: d for d in cfg.get("dual_role", [])}
    # SELF-GRADING IS CHECKED FIRST. Putting the dual_role exemption ahead of it let
    # seed-graded-by-seed through: the exemption returned early and the equality test
    # never ran. A dual-role model is exempt from "judges are not candidates", never
    # from "nothing grades itself".
    if model == grader:
        return (f"STAGE1_MODEL and GRADER_MODEL are both {model}. A model cannot grade "
                f"its own output.\nSet GRADER_MODEL to something else.")
    if model in dual:
        d = dual[model]
        print("\n" + "-" * 66)
        print(f"DUAL ROLE - {model} is judge {d['judge_seat']} AND a candidate.")
        print(f"  Declared in protocol/judges.json, permitted by PANEL.md.")
        print(f"  MUST APPEAR IN THE REPORT: {d['required_disclosure']}")
        print("-" * 66 + "\n")
        return None
    if model in seats:
        return (f"STAGE1_MODEL is {model}, which is seated as judge {seats[model]} in "
                f"protocol/judges.json.\nThat is a judge, not a candidate. This is almost "
                f"always a stale environment variable\nleft over from another command in "
                f"this window. Set STAGE1_MODEL explicitly and re-run.\n"
                f"To measure a judge deliberately, add it to the \"dual_role\" list in "
                f"judges.json\nwith the disclosure the report will have to carry.")
    return None


_conflict = _judge_conflict(MODEL, GRADER)
if _conflict and not os.environ.get("ALLOW_JUDGE_AS_CANDIDATE"):
    sys.exit("REFUSING TO START - " + _conflict)


def provider_block(name, quant=""):
    b = {}
    if name:
        b["order"] = [name]
        b["allow_fallbacks"] = False
    if quant:
        b["quantizations"] = [quant]
    if b:
        b["require_parameters"] = True
    return b or None


# The pin belongs to the CANDIDATE only. Applying it to the grader too asks
# OpenRouter for a grader endpoint on the candidate's provider, which usually
# does not exist -> "No endpoints found". Grader pinning is separate and opt-in.
CAND_PIN   = provider_block(PROVIDER, QUANT)
GRADER_PIN = provider_block(os.environ.get("GRADER_PROVIDER", ""))


def call(model, messages, temperature, pin=None):
    body = {"model": model, "messages": messages,
            "temperature": temperature, "max_tokens": MAXTOK}
    if pin:
        body["provider"] = pin
    req = urllib.request.Request(
        f"{BASE}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.loads(r.read().decode("utf-8"))
            ch = d["choices"][0]
            u = d.get("usage") or {}
            ctd = u.get("completion_tokens_details") or {}
            return {
                "text": ch["message"].get("content") or "",
                "finish": ch.get("finish_reason", "?"),
                "reasoning_tokens": ctd.get("reasoning_tokens", 0) or 0,
                "served_by": d.get("provider", "?"),
                # SPEND IS RECORDED, NOT RECONSTRUCTED. usage.cost is what OpenRouter
                # actually charged for this call, so it needs no price table and cannot
                # go stale. Reconstructing spend from tokens times a remembered price is
                # exactly the failure this programme keeps finding: Gemini's price
                # DOUBLED inside 24 hours during measurement one, and any figure built
                # on the old number would have been wrong and unfalsifiable.
                # None (not 0) when the field is absent - absent and free differ.
                "cost": u.get("cost"),
                "prompt_tokens": u.get("prompt_tokens"),
                "completion_tokens": u.get("completion_tokens"),
                "err": None,
            }
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"
            if e.code in (400, 401, 402, 404):
                break
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(2 * (attempt + 1))
    return {"text": "", "finish": "error", "reasoning_tokens": 0,
            "served_by": "?", "cost": None, "prompt_tokens": None,
            "completion_tokens": None, "err": last}


GRADE_TMPL = """You are grading one AI response against one specific criterion.

CRITERION THE RESPONSE MUST MEET:
{crit}

THE USER ASKED:
{ask}

THE RESPONSE:
{resp}

FIRST, a rule that OVERRIDES the criterion: if the response is empty, or consists
only of a bracketed annotation or metadata line with no prose actually answering the
user, the verdict is FAIL whatever the criterion says. An answer is required - the
absence of a fault is not an answer.

Otherwise: does the response meet the criterion? Judge only the criterion. Length,
tone and style are irrelevant. A response that meets the criterion in passing still
meets it.

Reply with exactly one JSON object and nothing else:
{{"verdict": "PASS" or "FAIL", "why": "<one short sentence>"}}"""


# PURE. No network, no globals, imports only json+re. Kept pure deliberately:
# scripts/panel_grade.py lifts this function out of THIS FILE'S SOURCE at runtime and
# execs it, so the panel judges parse verdicts through the identical code path as the
# tier-1 grader. One copy, so the two cannot drift apart. If you add a dependency on a
# module-level name here, panel_grade.py's self-check fails loudly rather than silently
# grading by different rules. See PARSER_EXPORT in panel_grade.py.
def parse_verdict(text, finish, reasoning_tokens=0, err=None):
    if err:
        return "ERROR", err, finish
    if finish == "length":
        return "UNPARSED", f"grader truncated ({reasoning_tokens} reasoning)", finish
    # The verdict is the datum; `why` is diagnostic colour. Do not discard a draw
    # because the grader wrote a long `why` and ran off the end without closing the
    # brace - that happened on 2 of 18 draws in the stamped arm and 0 of 20 in the
    # native arm, which would be differential attrition between arms.
    try:
        m = re.search(r'\{.*\}', text, re.S)
        if m:
            d = json.loads(m.group(0))
            v = str(d.get("verdict", "")).upper()
            if v in ("PASS", "FAIL"):
                return v, str(d.get("why", ""))[:200], finish
    except Exception:
        pass

    # salvage: the verdict alone, from malformed or unterminated output
    mv = re.search(r'"?verdict"?\s*[:=]\s*"?(PASS|FAIL)\b', text, re.I)
    if mv:
        mw = re.search(r'"?why"?\s*[:=]\s*"([^"]{0,200})', text, re.I)
        return mv.group(1).upper(), (mw.group(1) if mw else "") + " [salvaged]", finish

    return "UNPARSED", (text[:160] or "<empty reply from grader>"), finish


def grade(item, response_text):
    """Returns (verdict, why, finish, spend). The grader costs multiples of the model
    it grades - 84% of every dollar in measurement one - so its spend is recorded
    separately from the candidate's rather than pooled with it."""
    ask = item["messages"][-1]["content"]
    r = call(GRADER, [{"role": "user", "content": GRADE_TMPL.format(
        crit=item["pass_criterion"], ask=ask, resp=response_text[:6000])}], 0, GRADER_PIN)
    v, why, fin = parse_verdict(r["text"], r["finish"], r["reasoning_tokens"], r["err"])
    return v, why, fin, {"cost": r["cost"], "prompt_tokens": r["prompt_tokens"],
                         "completion_tokens": r["completion_tokens"]}


def main():
    items = [json.loads(l) for l in BANK.read_text(encoding="utf-8").splitlines() if l.strip()]
    OUT.parent.mkdir(parents=True, exist_ok=True)

    # CONFIG GUARD. Resuming into a file written under a different configuration
    # silently blends two instruments in one dataset. qwen half A was served by five
    # providers unpinned; resuming it with a pin would have mixed them. Refuse.
    cfg = {"model": MODEL, "max_tokens": MAXTOK, "provider": PROVIDER or None,
           "quant": QUANT or None, "bank": BANK.name, "stamped": bool(SYSTEM),
           "grader": GRADER, "temperature": TEMPERATURE, "draws": DRAWS}
    cfg_path = OUT.with_suffix(".config.json")
    if cfg_path.exists():
        prev = json.loads(cfg_path.read_text(encoding="utf-8"))
        # A key ABSENT from the old config was never recorded, so nothing can be said
        # to have changed - only keys present in both are compared. Without this, adding
        # a field to this dict would orphan every run already on disk. `temperature` was
        # added on 2026-08-29 and would otherwise have blocked the luna run mid-flight.
        # Absent keys are backfilled below at their current value, with a note.
        diff = {k: (prev[k], v) for k, v in cfg.items() if k in prev and prev[k] != v}
        # DRAWS is the one field where a change is sometimes legitimate: raising it
        # ADDS draws to a run and invalidates nothing. Lowering it silently produces a
        # thinner dataset than the one it is being compared against - on 2026-08-29
        # an unset DRAWS defaulted to 3 and would have made luna incomparable with
        # nemotron's 5, killing the reliability and fever measurements with it. So it
        # warns in both directions and blocks in neither.
        if "draws" in diff:
            was, now = diff.pop("draws")
            print(f"\n  DRAWS CHANGED: {was} -> {now}")
            print(f"    {'raising' if now > was else 'LOWERING'} the draws per item."
                  f" {'Existing draws stay valid; the new ones are added.' if now > was else ''}")
            if now < was:
                print(f"    A {now}-draw run cannot be compared with a {was}-draw one, and")
                print(f"    reliability and fever both need the full count. Ctrl-C now and")
                print(f"    set $env:DRAWS = \"{was}\" unless you meant this.")
                time.sleep(5)
        if diff:
            print("CONFIG CHANGED since this file was started:")
            for k, (was, now) in diff.items():
                print(f"    {k}: {was!r} -> {now!r}")
            sys.exit("refusing to resume - use a new STAGE1_CANDIDATE label so the "
                     "old data stays intact and the new run is clean")
        added = [k for k in cfg if k not in prev]
        if added:
            print(f"note: config fields not recorded when this run started, "
                  f"assumed unchanged and backfilled: {', '.join(added)}")
            prev.update(cfg)
            prev["backfilled"] = sorted(set(prev.get("backfilled", []) + added))
            cfg_path.write_text(json.dumps(prev, indent=2), encoding="utf-8")
    else:
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    # Only a real verdict counts as done. TRUNCATED / ERROR / UNPARSED draws are
    # re-issued, so raising the token budget repairs a spoiled run without deleting
    # anything. Duplicate rows for a retried draw are resolved last-one-wins below.
    done, retry = set(), 0
    if OUT.exists():
        for l in OUT.read_text(encoding="utf-8").splitlines():
            if l.strip():
                try:
                    d = json.loads(l)
                    if d.get("verdict") in ("PASS", "FAIL"):
                        done.add((d["item_id"], d["draw"]))
                    else:
                        retry += 1
                except Exception:
                    pass
        print(f"resuming: {len(done)} graded draws kept, {retry} bad draws will be re-issued")

    todo = [(it, k) for it in items for k in range(DRAWS) if (it["item_id"], k) not in done]

    # ---- preflight gate: refuses to start on a dead slug, thin credit, or battery ----
    # Two runs were lost to an exhausted balance before this existed. Set
    # PREFLIGHT=0 to skip, which should be rare and deliberate.
    if os.environ.get("PREFLIGHT", "1") != "0" and todo:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        try:
            from preflight import preflight as _pf
            if not _pf(BASE, KEY, [MODEL, GRADER], len(todo), pin=CAND_PIN):  # per DRAW
                sys.exit("stopped by preflight - nothing was spent")
        except ImportError:
            print("WARNING: preflight.py not found; running unchecked")
    arm = f"STAMPED ({len(SYSTEM)} chars of core from {pathlib.Path(CORE_PATH).name})" if SYSTEM else "NATIVE (no system prompt)"
    print(f"arm={arm}")
    print(f"bank={BANK.name}  half={HALF or '(single run)'}  temp={TEMPERATURE}")
    print(f"candidate={MODEL}  grader={GRADER}  items={len(items)}  draws={DRAWS}")
    print(f"candidate pin={PROVIDER or '(none - see ROADMAP trap 2)'} quant={QUANT or '(none)'}"
          f"   grader pin={os.environ.get('GRADER_PROVIDER') or '(none)'}")
    print(f"{len(todo)} calls to make\n")

    # CIRCUIT BREAKER. On 2026-08-29 an API key was revoked mid-run and the loop
    # carried on for 155 more draws writing "HTTP 401: User not found" into the file,
    # one per draw, at full speed. Nothing was lost - ERROR rows are re-issued on
    # resume - but a run whose credentials are dead should stop, not sprint to the
    # end producing garbage. An auth failure can never fix itself by retrying, so it
    # aborts on the first one; everything else gets a run of 8 before giving up.
    consecutive_errors = 0
    AUTH_CODES = ("HTTP 401", "HTTP 403")

    with OUT.open("a", encoding="utf-8") as f:
        for n, (it, k) in enumerate(todo, 1):
            # temperature 0 on draw 0, then vary so repeated draws are informative
            msgs = ([{"role": "system", "content": SYSTEM}] if SYSTEM else []) + it["messages"]
            gen = call(MODEL, msgs, TEMPERATURE, CAND_PIN)
            gfin = "-"
            gspend = {"cost": None, "prompt_tokens": None, "completion_tokens": None}
            if gen["err"]:
                verdict, why = "ERROR", gen["err"]
            elif gen["finish"] == "length":
                verdict = "TRUNCATED"
                why = (f"hit max_tokens={MAXTOK} "
                       f"({gen['reasoning_tokens']} reasoning, {len(gen['text'])} visible chars)")
            else:
                verdict, why, gfin, gspend = grade(it, gen["text"])
            f.write(json.dumps({
                "item_id": it["item_id"], "category": it["category"],
                "status": it["status"], "draw": k, "verdict": verdict, "why": why,
                "finish": gen["finish"], "reasoning_tokens": gen["reasoning_tokens"],
                "grader_finish": gfin, "max_tokens": MAXTOK,
                "served_by": gen["served_by"], "chars": len(gen["text"]),
                # SPEND, as charged, per call. Candidate and grader kept apart: in
                # measurement one the grader was 27x the models it graded, and a single
                # pooled number would have hidden the most useful cost finding we had.
                "cost_model": gen["cost"], "cost_grader": gspend["cost"],
                "tokens_in": gen["prompt_tokens"], "tokens_out": gen["completion_tokens"],
                "tokens_in_grader": gspend["prompt_tokens"],
                "tokens_out_grader": gspend["completion_tokens"],
                # 8000, not 4000. The store is what a re-grade with a different grader can
                # see later, and the grader window is 6000 - so a 4000-char store
                # silently gave a re-grade LESS text than the original grader had,
                # on 2.7% of responses. Storing above the window costs a little disk
                # and removes the asymmetry entirely.
                "text": gen["text"][:8000],
                "v125_native_fails": (it.get("v125") or {}).get("native_fails"),
            }, ensure_ascii=False) + "\n")
            f.flush()
            print(f"  [{n}/{len(todo)}] {it['item_id']} draw{k} -> {verdict}", flush=True)

            if verdict == "ERROR":
                consecutive_errors += 1
                fatal = any(c in (gen["err"] or "") for c in AUTH_CODES)
                if fatal or consecutive_errors >= 8:
                    print("\n" + "!" * 66)
                    print("RUN HALTED - " + ("the API rejected the credentials."
                          if fatal else f"{consecutive_errors} errors in a row."))
                    print(f"  last error: {gen['err']}")
                    print(f"  {n} of {len(todo)} attempted this session.")
                    if fatal:
                        print("\n  The key in this shell is dead - revoked, or from another")
                        print("  account. Set the new one and re-run; only the failed draws")
                        print("  are re-issued, so nothing already graded is repeated:")
                        print("    $s = Read-Host \"OpenRouter key\" -AsSecureString")
                        print("    $env:STAGE1_API_KEY = [Runtime.InteropServices.Marshal]"
                              "::PtrToStringAuto(")
                        print("        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))")
                    print("!" * 66)
                    break
            else:
                consecutive_errors = 0
            time.sleep(SLEEP)

    report()


def report():
    raw = [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines() if l.strip()]
    # a retried draw appears twice; the later row supersedes the earlier one
    latest = {}
    for r in raw:
        latest[(r["item_id"], r["draw"])] = r
    rows = list(latest.values())

    by_item, bad = {}, 0
    census = {"TRUNCATED": 0, "ERROR": 0, "UNPARSED": 0}
    for r in rows:
        if r["verdict"] in census:
            census[r["verdict"]] += 1
            bad += 1
            continue
        by_item.setdefault(r["item_id"], []).append(r["verdict"])

    print("\n" + "=" * 66)
    print(f"RESULT - {'STAMPED' if SYSTEM else 'NATIVE'} arm" + (f", half {HALF}" if HALF else ""))
    print("=" * 66)

    fail_rates = {}
    for iid, vs in sorted(by_item.items()):
        fr = sum(v == "FAIL" for v in vs) / len(vs)
        fail_rates[iid] = fr
    kept = [i for i, fr in fail_rates.items() if fr >= 0.20]

    print(f"\nitems graded          {len(fail_rates)}")
    print(f"unusable draws        {bad}   truncated={census['TRUNCATED']} "
          f"unparsed={census['UNPARSED']} error={census['ERROR']}")
    if census["TRUNCATED"]:
        rt = [r["reasoning_tokens"] for r in rows if r["verdict"] == "TRUNCATED"]
        hit = sorted({r["item_id"] for r in rows if r["verdict"] == "TRUNCATED"})
        pct = census["TRUNCATED"] / max(1, len(rows))
        # A truncated draw is excluded, not fatal. Only a systematic rate is fatal:
        # v1.69's judging lost 49% of judgments this way and nobody noticed.
        if pct >= 0.05:
            print(f"  ** {census['TRUNCATED']} truncations = {pct:.1%} at max_tokens={MAXTOK} "
                  f"(reasoning {min(rt)}-{max(rt)}). SYSTEMATIC - raise STAGE1_MAX_TOKENS "
                  f"and rerun; this run is not reportable. **")
        else:
            print(f"     {census['TRUNCATED']} truncations ({pct:.1%}) at max_tokens={MAXTOK}, "
                  f"reasoning {min(rt)}-{max(rt)}. Those draws are excluded; the run stands.")
            print(f"     affected: {', '.join(hit)}")
    if fail_rates:
        overall = sum(fail_rates.values()) / len(fail_rates)
        print(f"mean native fail rate {overall:.1%}   (2025 baseline on these items: 46.7%)")
    print(f"items at >=20% fail   {len(kept)}  <- these survive into the study")

    cats = {}
    for iid, fr in fail_rates.items():
        c = iid.rsplit("_", 1)[0]
        cats.setdefault(c, []).append(fr)
    print("\nper category:")
    for c in sorted(cats):
        v = cats[c]
        print(f"  {c:<28} n={len(v):<3} mean fail {sum(v)/len(v):>6.1%}  "
              f"kept {sum(1 for x in v if x >= 0.20)}")

    print("\n" + "-" * 66)
    if len(kept) >= 20:
        print(f"PROCEED. {len(kept)} items still discriminate. Run the v1.70 arm on these.")
    elif len(kept) >= 10:
        print(f"MARGINAL. Only {len(kept)} items discriminate. Usable, but the study")
        print("needs harder items added before it can support a per-category claim.")
    else:
        print(f"STOP. Only {len(kept)} items discriminate - the bank is at ceiling.")
        print("This is the v1.46/v1.69 failure repeating. Do not spend on judging.")
        print("Write adversarial items first; the pre-registration says how.")
    print("-" * 66)

    provs = {}
    for r in rows:
        provs[r.get("served_by", "?")] = provs.get(r.get("served_by", "?"), 0) + 1
    print(f"\nserving providers seen: {provs}")
    if len(provs) > 1:
        print("  ** more than one provider served this run - pin STAGE1_PROVIDER **")

    pathlib.Path(OUT.parent / f"pilot_summary_{_tag}.json").write_text(
        json.dumps({"candidate": MODEL, "fail_rates": fail_rates, "kept": kept,
                    "unusable": bad, "providers": provs}, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT.parent / f'pilot_summary_{_tag}.json'}")


if __name__ == "__main__":
    if "--report-only" in sys.argv:
        report()
    else:
        main()
