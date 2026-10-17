#!/usr/bin/env python3
"""STRIP THE RETURNED REASONING FROM A PROMPTFOO EXPORT. The committed export is read, never edited.

    python3 strip_thinking.py results/2026-08-08_v1.25_freellm-5-models.redacted.json OUT.json
    python3 strip_thinking.py IN.json OUT.json --splits splits.csv     also write one row per reply

WHY. promptfoo's OpenAI-compatible provider returns `Thinking: <reasoning>\n\n<answer>` whenever the
endpoint sends reasoning and `showThinking: false` is not set. In the Aug 08, 2026 five-model run all
930 replies carry that prefix, so the grader and footer_check.py read each model's reasoning as part
of its reply. This writes a copy in which `response.output` is the answer alone.

WHERE THE ANSWER STARTS. The join is a plain blank line and the reasoning has blank lines of its own,
so the boundary is not marked in the text. Two rules, in order:
  tokens   the reply reports reasoning tokens r of c completion tokens. The reasoning should end
           about r/c of the way through the text (both arms run at ~4 characters per token), and
           the cut is the blank line nearest that point.
  cues     no reasoning count was returned (348 of 930 replies). The cut is the blank line after
           the last paragraph that reads as planning ("the user", "we need", "Final Output",
           "Drafting the response", a draft footer introduced by "Footer:" ...). Agreement with
           the tokens rule, on replies where both apply, is printed so the rule can be judged.
  no-answer  the reply reports reasoning tokens equal to its completion tokens and stopped on the
           token cap: the model spent the whole budget reasoning and returned no answer. The answer
           is empty.
A paragraph after the cut that still reads as planning (some models leak "Thus footer: ..." into the
answer itself) is left in: it is what the endpoint returned as the answer.

WHAT IS KEPT. Every other field, including gradingResult. The verdicts in the copy are the ORIGINAL
ones, given with the reasoning visible; only receipts (footer_check) can be re-read from the copy
without a new grader call. The copy's top-level `stripped_thinking` block says so.

Stdlib only. No network. Deterministic.
"""
import argparse, csv, json, pathlib, re, sys

PREFIX = "Thinking: "
GAP = re.compile(r"\n\n")
# Planning voice. Chosen to be rare in answers addressed to a user: "let me know" is not a cue.
CUE = re.compile(
    r"\b(the user|user's|user is|user asks|user wants|we need|we should|we must|we have to|"
    r"we can(?!not)|i need to|i should|i must|i'll (?:answer|respond|write|provide|give|keep|make)|"
    r"let me (?:verify|check|compute|calculate|think|recall|see|confirm|double|re|count|look|make sure)|"
    r"let's (?:produce|craft|write|answer|compute|check|verify|count|do)|"
    r"now (?:produce|craft|write|output|answer|generate|format)|final (?:answer|output|review|check|polish|response)|"
    r"draft(?:ing)?|output generation|construct(?:ing)? (?:the )?output|self-correction|"
    r"stamp (?:precedence|rules|core|requires|says)|precedence|footer construction|footer:|"
    r"so answer|thus answer|answer accordingly|make sure|ensure (?:the|we|that)|okay,|hmm|wait,)",
    re.I)
FOOTER = re.compile(r"^\s*\[STAMPED\b[^\]]*\]\s*$")


def gaps(body):
    return [m.start() for m in GAP.finditer(body)]


def split_tokens(body, rt, ct):
    cands = gaps(body)
    if not cands or not rt or not ct:
        return None
    target = len(body) * rt / ct
    return min(cands, key=lambda i: (abs(i - target), i))


def split_cues(body):
    cands = gaps(body)
    if not cands:
        return None
    # paragraph k runs from (cands[k-1]+2 or 0) to cands[k] (or end)
    starts = [0] + [c + 2 for c in cands]
    ends = cands + [len(body)]
    last = None
    for k, (s, e) in enumerate(zip(starts, ends)):
        para = body[s:e]
        if FOOTER.match(para):
            continue
        if CUE.search(para) and k < len(cands):     # never cut after the final paragraph
            last = k
    return cands[last] if last is not None else cands[0]


def split(row, rule="tokens"):
    out = (row.get("response") or {}).get("output")
    if not isinstance(out, str) or not out.startswith(PREFIX):
        return None
    body = out[len(PREFIX):]
    tu = (row.get("response") or {}).get("tokenUsage") or {}
    rt = int((tu.get("completionDetails") or {}).get("reasoning") or 0)
    ct = int(tu.get("completion") or 0)
    if rt and ct and rt >= ct - 2:                   # the cap was spent on reasoning: no answer
        return {"body": body, "cut": len(body), "method": "no-answer", "rt": rt, "ct": ct}
    cut, method = (split_tokens(body, rt, ct), "tokens") if rule == "tokens" else (None, "cues")
    if cut is None:
        cut, method = split_cues(body), "cues"
    if cut is None:                                  # one paragraph only: nothing to call an answer
        return {"body": body, "cut": None, "method": "none", "rt": rt, "ct": ct}
    return {"body": body, "cut": cut, "method": method, "rt": rt, "ct": ct}


def answer_at(body, cut):
    return body if cut is None else body[cut:].lstrip("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--splits", help="also write one CSV row per reply: where it was cut and how")
    ap.add_argument("--rule", choices=("tokens", "cues"), default="tokens",
                    help="tokens (default): token-located cut, cues where no count was returned; "
                         "cues: the planning-cue cut everywhere, which strips more. Report both.")
    a = ap.parse_args()

    doc = json.loads(pathlib.Path(a.src).read_text(encoding="utf-8"))
    rows = doc["results"]["results"]
    log, agree, both = [], 0, 0
    for r in rows:
        s = split(r, a.rule)
        if s is None:
            continue
        if s["method"] == "tokens" or (a.rule == "cues" and s["rt"] and s["method"] == "cues"):
            c = split_cues(s["body"])
            both += 1
            agree += (c == (split_tokens(s["body"], s["rt"], s["ct"]) if a.rule == "cues" else s["cut"]))
        ans = answer_at(s["body"], s["cut"])
        r["response"]["output"] = ans
        log.append({
            "id": r.get("id"), "model": (r.get("provider") or {}).get("label"),
            "cond": (r.get("prompt") or {}).get("label"), "probe": (r.get("vars") or {}).get("_probe"),
            "method": s["method"], "reasoning_tokens": s["rt"], "completion_tokens": s["ct"],
            "reasoning_chars": len(s["body"]) - len(ans), "answer_chars": len(ans),
        })
    doc["stripped_thinking"] = {
        "source": pathlib.Path(a.src).name,
        "replies_stripped": len(log),
        "rule": a.rule,
        "by_method": {m: sum(1 for x in log if x["method"] == m) for m in ("tokens", "cues", "no-answer", "none")},
        "finish_reason_length": sum(1 for r in rows if (r.get("response") or {}).get("finishReason") == "length"),
        "cue_rule_agrees_with_token_rule": f"{agree} of {both}",
        "note": "response.output is the answer alone. gradingResult is UNCHANGED: those verdicts were "
                "given with the reasoning visible. Re-read receipts with footer_check; re-grade content "
                "with a grader call.",
    }
    pathlib.Path(a.out).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    if a.splits:
        with open(a.splits, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(log[0]))
            w.writeheader()
            w.writerows(log)
    print(json.dumps(doc["stripped_thinking"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
