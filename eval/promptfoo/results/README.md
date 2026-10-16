# Earlier promptfoo runs, Jul 23 to Aug 17, 2026

Six exports from runs made on the author's own machine with this harness, recovered from the studio's
Google Drive (copies uploaded Sep 07, 2026) on Oct 13, 2026 and committed unchanged. `SHA256SUMS.txt`
fingerprints them as committed. A seventh, `results_freellm.json` (18 MB), exceeded the connector's download limit; the author
uploaded it zipped on Oct 14, 2026. It is published as
`2026-08-08_v1.25_freellm-5-models.redacted.json` with one change: the gateway's server address
(an IP and port, 5 occurrences, all in the provider settings) is replaced with `<FREELLM_ENDPOINT>`.
No model output or verdict was touched. SHA-256 of the file as received:
`876d57b1a04a50d1ddb4c09f6b4ea4b26a337b8770e3eff6f1b17929ad083f43`.

| File | promptfoo evalId | STAMP | Model as configured | Grader | Probes |
|---|---|---|---|---|---|
| `2026-07-23_v1.02_gemini.json` | eval-d4e-2026-07-23T06:05:58 | v1.02 | google:gemini-2.5-flash | google:gemini-2.5-flash | 71 |
| `2026-07-23_v1.21_gemini.json` | eval-q3b-2026-07-23T23:36:47 | v1.21 | google:gemini-flash-latest | google:gemini-flash-latest | 89 |
| `2026-07-24_v1.25_gemini.json` | eval-HnL-2026-07-24T00:48:58 | v1.25 | google:gemini-flash-latest | google:gemini-flash-latest | 93 |
| `2026-08-06_v1.25_perplexity.json` | eval-TJl-2026-08-06T00:15:17 | v1.25 | perplexity:sonar | google:gemini-flash-latest | 93 |
| `2026-08-07_v1.25_mistral.json` | eval-Nxw-2026-08-07T05:01:08 | v1.25 | mistral:mistral-large-latest | google:gemini-flash-latest | 93 |
| `2026-08-08_v1.25_freellm-5-models.redacted.json` | eval-qn1-2026-08-08T02:26:34 | v1.25 | openai/gpt-oss-120b, zai-glm-4.7, nvidia/nemotron-3-super-120b-a12b, deepseek-ai/deepseek-v4-flash, stepfun-ai/step-3.7-flash (through a free OpenAI-compatible gateway) | google:gemini-flash-latest | 93 |
| `2026-08-17_v1.46_gpt-4o-mini_UNGRADED.json` | eval-j7U-2026-08-17T04:40:05 | v1.46 | openrouter:openai/gpt-4o-mini | none | 144 |

The three six-model configurations list six providers, but each file contains results for Gemini
only. All runs are one draw per cell at temperature 0. The v1.46 file has no assertions ("No
assertions" on every row): it holds outputs but no verdicts, and it is not used for any rate.

## Re-scored, content only, paired by probe, install canaries removed

promptfoo's own pass column includes the STAMPED-footer assertion, which passes the native condition
automatically, so it overstates STAMP. The table below uses only each probe's own criterion
(llm-rubric or icontains), paired by probe, from `analyze_s1s2.py`.

It also leaves out the **install canaries**: questions about STAMP itself (its original name, its
rule A5, its token cap), which only a model with STAMP's files can answer. They are probes 113-119,
121 and 122 in the v1.21 and v1.25 banks and 97-101 in v1.02. They check installation, not
behaviour, and the script drops them by default (`--include-canaries` puts them back, for diagnosis).
An earlier version of this table, and of the paper, included them and overstated every effect by 5 to
9 points; corrected Oct 13, 2026.

    python3 ../analyze_s1s2.py 2026-07-24_v1.25_gemini.json --receipt-version v1.25

| Run | Paired probes | Native fail | STAMP fail | STAMP minus native, 95% CI | Sign-flip p | Better / worse | False or missing receipt |
|---|---|---|---|---|---|---|---|
| v1.02, Gemini 2.5 Flash | 65 | 16.9% | 9.2% | -7.7 pts [-18.5, 3.1] | 0.26 | 9 / 4 | 30.8% |
| v1.21, Gemini Flash (latest) | 79 | 12.7% | 3.8% | -8.9 pts [-17.7, 0.0] | 0.09 | 10 / 3 | 27.8% |
| v1.25, Gemini Flash (latest) | 82 | 13.4% | 0.0% | -13.4 pts [-20.7, -6.1] | < 0.001 | 11 / 0 | 3.7% |
| v1.25, Perplexity Sonar | 82 | 18.3% | 11.0% | -7.3 pts [-13.4, -2.4] | 0.03 | 6 / 0 | 22.0% |
| v1.25, Mistral Large | 82 | 26.8% | 3.7% | -23.2 pts [-32.9, -13.4] | < 0.001 | 21 / 2 | 20.7% |
| v1.25, gpt-oss-120b* | 82 | 29.3% | 15.9% | -13.4 pts [-23.2, -3.7] | 0.02 | 15 / 4 | 26.8% |
| v1.25, GLM-4.7* | 82 | 36.6% | 18.3% | -18.3 pts [-29.3, -8.5] | 0.002 | 18 / 3 | 28.0% |
| v1.25, DeepSeek V4 Flash* | 82 | 20.7% | 14.6% | -6.1 pts [-15.9, +3.7] | 0.36 | 12 / 7 | 31.7% |
| v1.25, Step 3.7 Flash* | 82 | 24.4% | 15.9% | -8.5 pts [-18.3, 0.0] | 0.12 | 11 / 4 | 22.0% |
| v1.25, Nemotron 3 Super 120B* | 82 | 22.0% | 14.6% | -7.3 pts [-17.1, +2.4] | 0.20 | 11 / 5 | 22.0% |

\* Corrected Oct 15, 2026. These five models returned their reasoning with every reply, and promptfoo
put it in front of the answer ("Thinking: ..."), so the first grader and `footer_check.py` read it as
part of the reply. The rows above are graded on the answer alone by `google/gemini-3.7-flash`, with
receipts checked on the answer alone. The verdicts as first published were: gpt-oss-120b -22.0 pts
[-31.7, -12.2], GLM-4.7 -17.1 [-28.0, -6.1], DeepSeek V4 Flash -12.2 [-22.0, -2.4], Step 3.7 Flash
-11.0 [-20.7, -1.2], Nemotron 3 Super -9.8 [-20.7, +1.2], with 81.7% to 87.8% bad receipts. See
`regrade_2026-10-14/README.md` for the method, a second grader, and what the reasoning did to the
verdicts. The committed export is unchanged.

"Better / worse" counts probes STAMP passed and native failed, and the reverse. The two Mistral
probes STAMP made worse (49 and 112) are quoted in the paper, Section 6.2.

Receipts were checked with `harness/footer_check.py` (R1 to R10, no judge) against the version each
run installed.

## Why these are not the paper's headline

1. **The probes and the protocol were written together.** `tests/PROBES.md` is public, and the
   protocol's rules were revised so that it passes them ("every real failure becomes a new probe").
   These are development probes, not held-out ones. On the Calibration bank, which the protocol was
   not tuned on, the one controlled estimate is -0.9 points.
2. **On the Gemini runs, Gemini graded Gemini.** The programme's later rule forbids a judge from
   grading its own model family.
3. **The grader reads STAMP's labels and receipt.** Calibration 004 shows one appended line can move a
   grader from 2.9% to 65.2% PASS; whether a receipt has a smaller version of that effect is untested.
4. **One draw at temperature 0.** Calibration 001 found 56 of 63 temperature-0 responses changed
   between two runs on a pinned provider.
5. **"gemini-flash-latest" is an alias.** The underlying model is not recorded.

## System 1 vs System 2 run, Oct 14, 2026

`2026-10-14_s1s2/` holds the pre-registered System 1 vs System 2 run (ten rows, two halves, 93 probes,
STAMP v1.25), its four pilots, the analysis outputs and a write-up (`2026-10-14_s1s2/README.md`). Its files
are fingerprinted in `2026-10-14_s1s2/SHA256SUMS.txt`.
