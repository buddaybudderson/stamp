# Pre-registration: STAMP on System 1 and System 2 configurations

**Status: SIGNED Oct 13, 2026 22:13 CDT.** No model call for this study may be made until this file is signed below
and committed. A change after signing is an amendment: it is numbered, dated, signed, and says what had
been seen before it was made.

## Why this study

The one controlled estimate of STAMP's effect so far (-0.9 points, internal v1.70, nemotron, Calibration
Vol 001) is smaller than the measured bias of the grader that produced it (+4.1 points). It is not an
effect. Reasoning models add a second open question: if a model already deliberates before answering, a
prompt that tells it to check its work may add nothing, or may only add a receipt.

## Design

- **Conditions.** native (no system prompt) and stamp (STAMP v1.25 core in the system slot), built by
  `eval/promptfoo/prompts.js` from the shipped files.
- **Rows.** Each model that allows it runs twice through OpenRouter's `reasoning` switch: off ("-s1") and
  effort high ("-s2"). Models that always reason run as "-s2" only. The rows are fixed in
  `promptfooconfig.system1-vs-system2.yaml`; every model id is checked against the live catalog on the
  run date, and any substitution is recorded here before the run.
- **Items.** The 93 runnable chat probes (84 generated from `tests/PROBES.md`, 9 hand-authored fixtures).
  Agent probes 81 to 90 are out of scope (see `REA_agent_eval.md`).
- **Draws.** Two independent halves. Each half is one full pass at temperature 0 where the model accepts
  it, run as a separate `promptfoo eval --no-cache` writing `results.s1s2.A.json` and `results.s1s2.B.json`.
  The retest gap between halves is the noise floor for each row.
- **Grader.** Tier 1: `bytedance-seed/seed-2-1-turbo` (no ByteDance model is a candidate). Tier 2: the
  three-family panel (`harness/panel_grade.py`) on a 20% stratified sample of both conditions, plus every
  item whose tier-1 verdict differs between halves.

## Questions and primary analysis

| | Question | Analysis |
|---|---|---|
| Q1 | Does STAMP change the fail rate on System 1 rows? | stamp minus native, paired by probe, 95% bootstrap CI over probes, sign-flip p (`analyze_s1s2.py`) |
| Q2 | Does it change the fail rate on System 2 rows? | as Q1 |
| Q3 | Is the STAMP effect different with reasoning on? | (s2 effect) minus (s1 effect), paired by probe, within each model |
| Q4 | Is receipt truth different between System 1 and System 2? | share of stamp replies failing `harness/footer_check.py` R1 to R10, per row |

**Secondary (still pre-registered).**

- **S1, receipt influence on the grader.** Regrade every stamp reply with its receipt line removed. The
  difference in tier-1 PASS share (receipt present minus removed), paired by reply, measures how much the
  receipt itself moves the grader. If it exceeds the row's noise floor, Q1 to Q3 are reported on the
  receipt-stripped verdicts.
- **S2, cost.** Input, output and reasoning tokens per reply, and charged cost as the gateway reports it.

## Decision rules, fixed now

- An effect is reported as an effect only when its 95% interval excludes zero **and** its size exceeds
  both the row's retest gap and the panel-measured grader bias for that row. Otherwise it is reported as
  "this design cannot tell", with the minimum detectable effect.
- A "-s1" row whose replies report reasoning tokens is dropped with its pair, and the drop is reported.
  (`analyze_s1s2.py` refuses to proceed otherwise.)
- A row losing more than 10% of draws (empty, truncated or refused) is reported, and its rate is not
  compared until the loss is explained.
- No row is added or dropped after the first call except under the two rules above.
- Every number in the report is computed from the committed `results.s1s2.json` and registered in
  `docs/figures.json` with its source hash.

## Predictions (recorded so they can be wrong)

1. Q1: STAMP lowers the fail rate on at least half of the System 1 rows.
2. Q3: the STAMP effect is smaller with reasoning on for at least half of the paired models.
3. Q4: System 2 rows produce false or missing receipts less often than System 1 rows.
4. S1: removing the receipt lowers the tier-1 PASS share by more than 1 point.

## Model-id check (Oct 14, 2026, before any paid call)

Every id in `promptfooconfig.system1-vs-system2.yaml` was checked against
`https://openrouter.ai/api/v1/models` (462 models listed on Oct 14, 2026). All seven are present and all
list `reasoning` in `supported_parameters`. **No substitution was made.**

| Row(s) | Id | Present | Lists `temperature` |
|---|---|---|---|
| gemini-flash-s1, -s2 | `google/gemini-3.7-flash` | yes | yes |
| luna-s1, -s2 | `openai/gpt-5.6-luna` | yes | no |
| nemotron-s1, -s2 | `nvidia/nemotron-3.5-lightning` | yes | yes |
| sonnet-s1, -s2 | `anthropic/claude-sonnet-5.5` (marked VERIFY) | yes | no |
| grok-s2 | `x-ai/grok-4.6` | yes | yes |
| haiku-s2 | `anthropic/claude-haiku-4.5` (marked VERIFY) | yes | yes |
| grader | `bytedance-seed/seed-2-1-turbo` | yes | yes |

Two rows (luna, sonnet) do not list `temperature`, so "temperature 0 where the model accepts it" means the
provider default for those rows; the retest gap between halves measures what that costs. The catalog also
lists `anthropic/claude-haiku-5.5`; the registered row stays `claude-haiku-4.5` because that id exists.

## Signature

Signed: Lawrence Ho  Date and time (America/Chicago): Oct 13, 2026 22:13 CDT

## Amendment 1 (Oct 13, 2026 22:22 CDT, before any study call)

**What had been seen.** A pilot of the Sonnet pair on the first 10 probes (spend $0.145, OpenRouter key
usage; not part of the study data) and one-line reachability calls to every row. No study reply had been
graded or analysed. Two faults:

1. OpenRouter rejected reasoning off for `anthropic/claude-sonnet-5.5` and `google/gemini-3.7-flash`
   with: "Reasoning is mandatory for this endpoint and cannot be disabled." Neither can be a System 1
   row. `anthropic/claude-haiku-4.5` accepted reasoning off (0 reasoning tokens), so the registered note
   that it always reasons does not hold on this gateway.
2. The grader stopped at promptfoo's default 1,024-token limit on 6 of 20 pilot grades, all 1,024 tokens
   spent on reasoning, giving "Could not extract JSON from llm-rubric response".

**Change.** Rows, still 10: pairs luna, nemotron, sonnet (`anthropic/claude-sonnet-4.6`, substituted for
`claude-sonnet-5.5`; it accepts reasoning off), haiku (`claude-haiku-4.5`, gains a "-s1" row); System 2
only: grok-4.6, gemini-3.7-flash (registered rule for models that always reason). Grader unchanged except
`max_tokens: 8192`. Questions, analysis and decision rules are unchanged.

Signed: Lawrence Ho (chose this option when asked, Oct 13, 2026 22:22 CDT)
