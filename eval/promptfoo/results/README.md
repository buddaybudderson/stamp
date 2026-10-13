# Earlier promptfoo runs, Jul 23 to Aug 17, 2026

Six exports from runs made on the author's own machine with this harness, recovered from the studio's
Google Drive (copies uploaded Sep 07, 2026) on Oct 13, 2026 and committed unchanged. `SHA256SUMS.txt`
fingerprints them as committed. A seventh, `results_freellm.json` (18 MB), exceeded the download limit
of the tool used and is not here yet.

| File | promptfoo evalId | STAMP | Model as configured | Grader | Probes |
|---|---|---|---|---|---|
| `2026-07-23_v1.02_gemini.json` | eval-d4e-2026-07-23T06:05:58 | v1.02 | google:gemini-2.5-flash | google:gemini-2.5-flash | 71 |
| `2026-07-23_v1.21_gemini.json` | eval-q3b-2026-07-23T23:36:47 | v1.21 | google:gemini-flash-latest | google:gemini-flash-latest | 89 |
| `2026-07-24_v1.25_gemini.json` | eval-HnL-2026-07-24T00:48:58 | v1.25 | google:gemini-flash-latest | google:gemini-flash-latest | 93 |
| `2026-08-06_v1.25_perplexity.json` | eval-TJl-2026-08-06T00:15:17 | v1.25 | perplexity:sonar | google:gemini-flash-latest | 93 |
| `2026-08-07_v1.25_mistral.json` | eval-Nxw-2026-08-07T05:01:08 | v1.25 | mistral:mistral-large-latest | google:gemini-flash-latest | 93 |
| `2026-08-17_v1.46_gpt-4o-mini_UNGRADED.json` | eval-j7U-2026-08-17T04:40:05 | v1.46 | openrouter:openai/gpt-4o-mini | none | 144 |

The three six-model configurations list six providers, but each file contains results for Gemini
only. All runs are one draw per cell at temperature 0. The v1.46 file has no assertions ("No
assertions" on every row): it holds outputs but no verdicts, and it is not used for any rate.

## Re-scored, content only, paired by probe

promptfoo's own pass column includes the STAMPED-footer assertion, which passes the native condition
automatically, so it overstates STAMP. The table below uses only each probe's own criterion
(llm-rubric or icontains), paired by probe, from `analyze_s1s2.py`:

    python3 ../analyze_s1s2.py 2026-07-24_v1.25_gemini.json --receipt-version v1.25

| Run | Paired probes | Native fail | STAMP fail | STAMP minus native, 95% CI | Sign-flip p | STAMP replies with a false or missing receipt |
|---|---|---|---|---|---|---|
| v1.02, Gemini 2.5 Flash | 70 | 21.4% | 8.6% | -12.9 pts [-24.3, -1.4] | 0.048 | 28.6% |
| v1.21, Gemini Flash (latest) | 87 | 20.7% | 3.4% | -17.2 pts [-27.6, -8.0] | 0.001 | 26.4% |
| v1.25, Gemini Flash (latest) | 91 | 22.0% | 0.0% | -22.0 pts [-30.8, -13.2] | < 0.001 | 4.4% |
| v1.25, Perplexity Sonar | 91 | 26.4% | 11.0% | -15.4 pts [-23.1, -8.8] | < 0.001 | 23.1% |
| v1.25, Mistral Large | 91 | 34.1% | 5.5% | -28.6 pts [-38.5, -18.7] | < 0.001 | 18.7% |

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
