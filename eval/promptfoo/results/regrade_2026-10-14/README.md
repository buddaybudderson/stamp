# The Aug 08, 2026 five-model run, re-graded on the answer alone (Oct 14 to Oct 15, 2026)

`2026-08-08_v1.25_freellm-5-models.redacted.json` holds STAMP v1.25 on gpt-oss-120b, GLM-4.7,
DeepSeek V4 Flash, Step 3.7 Flash and Nemotron 3 Super. All 930 replies in it begin with the model's
returned reasoning ("Thinking: ..."): promptfoo's OpenAI-compatible provider puts reasoning in front
of the answer unless `showThinking: false` is set, and the run did not set it. The grader (a Gemini
Flash model) and `harness/footer_check.py` therefore read each model's reasoning as part of its reply.

This folder re-grades those replies. The export itself is not edited; its SHA-256 is unchanged.

## How

1. `../strip_thinking.py` recovers each answer. The export does not mark where the answer begins
   (the join is a blank line, and reasoning has blank lines of its own), so the cut is placed:
   from the reply's reasoning-token count where one was reported (496 replies: the blank line
   nearest the point that count predicts); from planning wording where none was (348); and as an
   empty answer where the reasoning used the whole 1,024-token budget (86). `splits_tokens.csv`
   lists every cut. On replies where both rules apply, the wording rule picks the same blank line
   355 times in 496; the two rules give the same receipt verdict on 155 of 166 STAMP replies.
2. `../regrade_rubric.py grade` re-grades the 800 rubric-graded, non-canary replies with promptfoo's
   own llm-rubric prompt (checked against the `renderedGradingPrompt` stored in the export before any
   call) and each row's own rubric, at temperature 0, twice per grader: `__original` is the reply as
   the first grader saw it, reasoning included; `__stripped` is the answer alone. Holding the grader
   fixed, the difference between the two is the effect of the reasoning.
3. `../regrade_rubric.py apply` writes a promptfoo-shaped copy with the new verdicts (and the 20
   `icontains` checks recomputed on the same text), which `../analyze_s1s2.py` reads unchanged.

Graders, both from developers outside the five: `google/gemini-3.7-flash` (the original grader's
family) and `anthropic/claude-haiku-5.5`, each at its default settings, through OpenRouter. Two others
were tried and dropped on cost or availability before their verdicts were tallied:
`bytedance-seed/seed-2-1-turbo` with reasoning on (1,915 reasoning tokens and $0.0054 a grade; 3 of 44
ran out of tokens before a verdict; `pilot_seed-reasoning-on__stripped.jsonl`), and
`mistralai/mistral-small-2603` (rate-limited upstream after 3 grades). Haiku was chosen, after the
Gemini results had been seen, as the cheapest grader the account's data policy allowed. Total gateway
charge for everything in this folder: $3.05.

    python3 ../strip_thinking.py ../results/2026-08-08_v1.25_freellm-5-models.redacted.json stripped.json
    python3 ../regrade_rubric.py apply ../results/2026-08-08_v1.25_freellm-5-models.redacted.json google_gemini-3.7-flash__stripped.jsonl g.json
    python3 ../analyze_s1s2.py g.json --receipt-version v1.25

## What it found

STAMP minus native content fail rate, percentage points, 95% bootstrap interval over 82 probes,
install canaries removed. A negative number means STAMP lowered the fail rate.

| Model | As published (Gemini Flash, reasoning shown) | Gemini 3.7 Flash, reasoning shown | Gemini 3.7 Flash, answer alone | Haiku 5.5, reasoning shown | Haiku 5.5, answer alone |
|---|---|---|---|---|---|
| gpt-oss-120b | -22.0 [-31.7, -12.2] | -18.3 [-26.8, -9.8] | -13.4 [-23.2, -3.7] | -23.5 [-33.3, -13.6] | -19.5 [-30.5, -9.8] |
| GLM-4.7 | -17.1 [-28.0, -6.1] | -13.4 [-23.2, -3.7] | -18.3 [-29.3, -8.5] | -22.2 [-33.3, -11.1] | -23.2 [-34.1, -12.2] |
| DeepSeek V4 Flash | -12.2 [-22.0, -2.4] | -11.0 [-20.7, -1.2] | -6.1 [-15.9, +3.7] | -14.8 [-24.7, -4.9] | -15.9 [-28.0, -3.7] |
| Step 3.7 Flash | -11.0 [-20.7, -1.2] | -13.4 [-20.7, -6.1] | -8.5 [-18.3, 0.0] | -24.7 [-34.6, -16.0] | -20.7 [-30.5, -11.0] |
| Nemotron 3 Super | -9.8 [-20.7, +1.2] | -14.6 [-24.4, -4.9] | -7.3 [-17.1, +2.4] | -19.8 [-29.6, -9.9] | -13.6 [-24.7, -2.5] |

- **The reasoning flattered STAMP, on the point estimate.** With the grader held fixed, removing it
  reduced the STAMP effect, pooled over the five models, by 3.4 points with Gemini (95% CI -0.2 to
  6.8) and by 2.0 points with Haiku (-2.2 to 6.4). Both intervals include zero. With Gemini, 53 of
  800 verdicts changed: 28 STAMP passes and 14 native passes became fails; 4 and 7 went the other way.
- **Replies with no answer had been passed.** In 62 scored replies the reasoning used the whole token
  budget and no answer was returned. The original grader passed 18 of them; shown the reasoning, Gemini
  passed 25 of 62 and Haiku 25 of the 60 it graded; shown the empty answer, they passed 2 and 1.
  Probe 64's `icontains "480"` check passed 3 native replies only because "480" was in the reasoning.
- **The graders disagree on size.** They agreed on 764 of 819 answer-alone verdicts (93.3%), but
  Haiku's estimates are 4.9 to 12.2 points more favourable to STAMP than Gemini's; for DeepSeek V4
  Flash, -15.9 against -6.1. Under Gemini, three of five intervals include or reach zero; under
  Haiku, none does. The paper's table uses Gemini, the original grader's family.
- **Receipts.** On the answer alone, 22.0% to 31.7% of STAMP receipts fail `footer_check.py`
  (gpt-oss-120b 26.8% [18.4, 37.3], GLM-4.7 28.0% [19.5, 38.6], DeepSeek V4 Flash 31.7% [22.6, 42.4],
  Step 3.7 Flash 22.0% [14.4, 32.1], Nemotron 3 Super 22.0% [14.4, 32.1]; Wilson intervals), against
  81.7% to 87.8% as published. 55 of the 410 STAMP replies stopped at the token limit before writing a
  receipt, every one a failure; among replies that finished, 9.9% to 22.2% fail. The wording rule,
  which strips more, gives 28.0% for DeepSeek V4 Flash and 19.5% for Nemotron 3 Super.

## Limits

The cut is an estimate: the provider's own boundary between reasoning and answer was not kept.
Content was re-graded on the token rule's cut only. Haiku's provider returned no verdict on probe 45
for 7 replies (content filter on the grader side), so those rows pair 81 probes. One draw per cell at
temperature 0, development probes, single graders without a panel: everything listed under "Why
these are not the paper's headline" in `../README.md` still applies.

## Files

| File | What |
|---|---|
| `google_gemini-3.7-flash__original.jsonl`, `__stripped.jsonl` | 800 verdicts each, Oct 14, 2026 |
| `anthropic_claude-haiku-5.5__original.jsonl`, `__stripped.jsonl` | 800 rows each plus retries, Oct 15, 2026 |
| `pilot_seed-reasoning-on__stripped.jsonl`, `mistralai_mistral-small-2603__stripped.jsonl` | dropped graders, kept for the cost record |
| `splits_tokens.csv` | where each of the 930 replies was cut, and by which rule |

Each verdict row records the grader's reason, its cost, its token use and the model that served it.
`SHA256SUMS.txt` fingerprints this folder as committed.
