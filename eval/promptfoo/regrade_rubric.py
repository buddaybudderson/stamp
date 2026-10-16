#!/usr/bin/env python3
"""RE-GRADE A PROMPTFOO EXPORT'S llm-rubric ROWS WITH A NAMED GRADER, ON STRIPPED OR ORIGINAL REPLIES.

    python3 regrade_rubric.py grade EXPORT --grader google/gemini-3.7-flash --variant stripped --out DIR
    python3 regrade_rubric.py grade EXPORT --grader google/gemini-3.7-flash --variant original --out DIR
    python3 regrade_rubric.py apply EXPORT DIR/<grader>__<variant>.jsonl OUT.json
    python3 analyze_s1s2.py OUT.json --receipt-version v1.25

WHY. In the Aug 08, 2026 five-model run every reply began with the model's returned reasoning
("Thinking: ..."), and the grader read it. `strip_thinking.py` recovers the answer. This grades the
answer alone, and, with --variant original, the reply exactly as the first grader saw it, with the SAME
new grader, so the difference between the two isolates the stripping from the change of grader.

SAME RUBRIC. The prompt is promptfoo's llm-rubric prompt, copied from the renderedGradingPrompt stored
in the export (system text with its two examples, then <Output>..</Output><Rubric>..</Rubric>), with
each row's own rubric text. Temperature 0. Install canaries are skipped (no rate uses them).

`apply` writes a promptfoo-shaped copy in which each llm-rubric verdict is the new grader's and each
icontains check is recomputed on the same text, so analyze_s1s2.py reads it unchanged.

GRADERS USED ON Oct 14 to Oct 15, 2026. google/gemini-3.7-flash and anthropic/claude-haiku-5.5, each at
its default settings. Neither shares a developer with the five graded models. Two others were tried
and dropped on cost or availability, before any of their verdicts were tallied: bytedance-seed/seed-2-1-turbo with its reasoning on averaged
1,915 reasoning tokens and $0.0054 a grade, and 3 of 44 pilot grades ran out of tokens before a
verdict (kept as pilot_seed-reasoning-on__stripped.jsonl); mistralai/mistral-small-2603 was
rate-limited upstream after 3 grades. Their costs count toward the budget. Haiku was chosen as the
cheapest grader the account's data policy allowed, after the Gemini results had been seen.

SPEND. OpenRouter reports each call's cost (usage.include). Every .jsonl in --out is summed before
each call; at --budget dollars (default 12) the run stops. Resumes: rows already graded are skipped.
Env: STAGE1_API_KEY, STAGE1_BASE_URL (default https://openrouter.ai/api/v1). Stdlib only.
"""
import argparse, concurrent.futures as cf, json, os, pathlib, re, sys, threading, time
import urllib.request, urllib.error

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strip_thinking as st                      # noqa: E402
from analyze_s1s2 import is_canary               # noqa: E402

BASE = os.environ.get("STAGE1_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
KEY = os.environ.get("STAGE1_API_KEY", "")
SYSTEM = ('You are grading output according to a user-specified rubric. If the statement in the rubric is '
          'true, then the output passes the test. You respond with a JSON object with this structure: '
          '{reason: string, pass: boolean, score: number}\n\nExamples:\n\n<Output>Hello world</Output>\n'
          '<Rubric>Content contains a greeting</Rubric>\n{"reason": "the content contains the word \'Hello\'", '
          '"pass": true, "score": 1.0}\n\n<Output>Avast ye swabs, repel the invaders!</Output>\n'
          '<Rubric>Does not speak like a pirate</Rubric>\n{"reason": "\'avast ye\' is a common pirate term", '
          '"pass": false, "score": 0.0}')
USER = "<Output>\n{output}\n</Output>\n<Rubric>\n{rubric}\n</Rubric>"


def reply_text(row, variant):
    if variant == "original":
        return row["response"]["output"]
    s = st.split(row, "tokens")
    return row["response"]["output"] if s is None else st.answer_at(s["body"], s["cut"])


def check_template(rows):
    """Refuse to run if the stored prompt is not the one this script sends."""
    for r in rows:
        for c in r["gradingResult"]["componentResults"]:
            meta = c.get("metadata") or {}
            if c["assertion"]["type"] == "llm-rubric" and "renderedGradingPrompt" in meta:
                msgs = json.loads(meta["renderedGradingPrompt"])
                want = USER.format(output=r["response"]["output"], rubric=c["assertion"]["value"])
                if msgs[0]["content"] != SYSTEM or msgs[1]["content"] != want:
                    sys.exit("REFUSED - the stored grading prompt differs from this script's template")
                return


def parse(text):
    for m in reversed(list(re.finditer(r"\{[^{}]*\"pass\"\s*:\s*(true|false)[^{}]*\}", text or "", re.S))):
        try:
            v = json.loads(m.group(0))
            return bool(v["pass"]), str(v.get("reason", ""))[:400]
        except Exception:
            p = m.group(1) == "true"
            return p, "(reason not parsed)"
    return None, (text or "<empty>")[:200]


def call(grader, output, rubric, max_tokens, reasoning_off=False):
    body = {"model": grader, "temperature": 0, "max_tokens": max_tokens, "usage": {"include": True},
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": USER.format(output=output, rubric=rubric)}]}
    if reasoning_off:                     # as the Section 6.5 grader: OpenRouter's reasoning switch
        body["reasoning"] = {"enabled": False}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                j = json.loads(resp.read())
            ch = (j.get("choices") or [{}])[0]
            u = j.get("usage") or {}
            return {"text": (ch.get("message") or {}).get("content") or "", "finish": ch.get("finish_reason"),
                    "cost": float(u.get("cost") or 0), "prompt_tokens": u.get("prompt_tokens"),
                    "completion_tokens": u.get("completion_tokens"),
                    "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                    "served_by": j.get("provider"), "model_served": j.get("model")}
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 7:
                wait = e.headers.get("Retry-After") if e.headers else None
                time.sleep(float(wait) if wait and wait.replace(".", "").isdigit() else min(60, 2 ** attempt * 2))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < 7:
                time.sleep(min(60, 2 ** attempt * 2))
                continue
            raise


def spent(outdir):
    total = 0.0
    for f in pathlib.Path(outdir).glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                total += json.loads(line).get("cost") or 0
    return total


def grade(a):
    if not KEY:
        sys.exit("STAGE1_API_KEY is empty")
    rows = json.loads(pathlib.Path(a.export).read_text(encoding="utf-8"))["results"]["results"]
    check_template(rows)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{a.grader.replace('/', '_')}__{a.variant}.jsonl"
    done = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            x = json.loads(line)
            if x.get("pass") is not None:
                done.add(x["key"])
    jobs = []
    for r in rows:
        if is_canary((r.get("vars") or {}).get("probe")):
            continue
        for i, c in enumerate(r["gradingResult"]["componentResults"]):
            if c["assertion"]["type"] != "llm-rubric":
                continue
            key = f"{r['id']}#{i}"
            if key not in done:
                jobs.append((key, r, c["assertion"]["value"]))
    lock = threading.Lock()
    state = {"spent": spent(out), "stopped": False, "n": 0}
    print(f"{len(jobs)} to grade, {len(done)} already done, ${state['spent']:.4f} spent so far in {out}")

    def work(job):
        key, r, rubric = job
        with lock:
            if state["stopped"] or state["spent"] >= a.budget:
                state["stopped"] = True
                return
        text = reply_text(r, a.variant)
        try:
            res = call(a.grader, text, rubric, a.max_tokens, a.reasoning_off)
        except Exception as e:                  # left ungraded; the next run resumes it
            print(f"  skipped {key}: {e}", flush=True)
            return
        ok, why = parse(res["text"])
        rec = {"key": key, "id": r["id"], "model": r["provider"]["label"], "cond": r["prompt"]["label"],
               "probe": r["vars"]["_probe"], "variant": a.variant, "grader": a.grader,
               "grader_reasoning": "off" if a.reasoning_off else "default", "pass": ok,
               "reason": why, "reply_chars": len(text), **{k: v for k, v in res.items() if k != "text"}}
        with lock:
            state["spent"] += rec["cost"]
            state["n"] += 1
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if state["n"] % 50 == 0:
                print(f"  {state['n']}/{len(jobs)}  ${state['spent']:.4f}", flush=True)

    with cf.ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(work, jobs))
    print(f"done: {state['n']} graded this run, ${state['spent']:.4f} total in {out}"
          + ("  STOPPED AT BUDGET" if state["stopped"] else ""))
    return 3 if state["stopped"] else 0


def apply(a):
    doc = json.loads(pathlib.Path(a.export).read_text(encoding="utf-8"))
    verdicts, variant = {}, None
    for line in pathlib.Path(a.verdicts).read_text(encoding="utf-8").splitlines():
        x = json.loads(line)
        if x.get("pass") is not None:
            verdicts[x["key"]] = x["pass"]
            variant = x["variant"]
    missing = 0
    for r in doc["results"]["results"]:
        text = reply_text(r, variant)
        for i, c in enumerate(r["gradingResult"]["componentResults"]):
            t = c["assertion"]["type"]
            if t == "llm-rubric":
                key = f"{r['id']}#{i}"
                if key in verdicts:
                    c["pass"] = verdicts[key]
                elif not is_canary(r["vars"].get("probe")):
                    missing += 1
                    c.pop("pass", None)
                    r["gradingResult"]["componentResults"] = [
                        x for x in r["gradingResult"]["componentResults"] if x is not c]
            elif t == "icontains":
                c["pass"] = str(c["assertion"]["value"]).lower() in text.lower()
        r["response"]["output"] = text
    doc["regraded"] = {"verdicts": pathlib.Path(a.verdicts).name, "variant": variant,
                       "rubric_rows_without_a_verdict": missing}
    pathlib.Path(a.out).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(doc["regraded"]))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("grade")
    g.add_argument("export")
    g.add_argument("--grader", required=True)
    g.add_argument("--variant", choices=("stripped", "original"), required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--budget", type=float, default=12.0)
    g.add_argument("--workers", type=int, default=8)
    g.add_argument("--max-tokens", type=int, default=8192)
    g.add_argument("--reasoning-off", action="store_true",
                   help="send reasoning {enabled: false}, as the Section 6.5 grader did")
    p = sub.add_parser("apply")
    p.add_argument("export")
    p.add_argument("verdicts")
    p.add_argument("out")
    a = ap.parse_args()
    return grade(a) if a.cmd == "grade" else apply(a)


if __name__ == "__main__":
    sys.exit(main())
