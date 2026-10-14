# System 1 vs System 2 run, Oct 14, 2026

STAMP v1.25 against no system prompt ("native"), on ten rows: four models with reasoning off ("-s1")
and on ("-s2"), and two models that always reason (System 2 only). Pre-registration, with its three
amendments and what had been seen before each: `paper/PREREG_system1_vs_system2.md` (signed Oct 13, 2026
22:13 CDT). Configuration: `eval/promptfoo/promptfooconfig.system1-vs-system2.yaml` as of Amendment 3.

## Conditions

| | |
|---|---|
| Rows | luna (`openai/gpt-5.6-luna`), nemotron (`nvidia/nemotron-3.5-lightning`), sonnet (`anthropic/claude-sonnet-4.6`), haiku (`anthropic/claude-haiku-4.5`), each -s1 and -s2; gemini-flash (`google/gemini-3.7-flash`) and grok (`x-ai/grok-4.6`), -s2 only |
| Reasoning switch | OpenRouter `reasoning`: `enabled: false` or `effort: none` for -s1, `effort: high` for -s2 |
| Items | 93 chat probes (84 from `tests/PROBES.md`, 9 fixtures); 9 install canaries dropped from every rate, leaving 84; 82 paired per row (80 for grok, below) |
| Draws | two halves, one pass each, `--no-cache`, temperature 0 where the model accepts it (luna and sonnet do not list it) |
| Grader | `bytedance-seed/seed-2-1-turbo`, reasoning off, `max_tokens` 8192, tier 1 only |
| Reasoning text | hidden from the grader and from `footer_check.py` (`showThinking: false`) |
| Harness | promptfoo 0.124.1 through OpenRouter, run Oct 14, 2026 03:45 to 05:50 UTC |
| Spend | study $14.44, pilots $0.85 (`spend_ledger.json`, from the key's own usage counter) |

## Files

- `results.s1s2.A.json`, `results.s1s2.B.json`: the two halves, each the promptfoo exports of the six
  models joined by `eval/promptfoo/merge_s1s2.py`. Each file's `merge` block lists its parts.
- `analysis.A.txt`, `analysis.B.txt`: `analyze_s1s2.py` on each half. `analysis.both.txt`:
  `s1s2_halves.py` on both (retest gap, pooled effect, Q3, Q4). `.json` versions of each.
- `pilots/`: the four pilots behind the amendments. They are not study data.
- `SHA256SUMS.txt`: fingerprints of the data files as committed.

Reproduce: `python3 eval/promptfoo/s1s2_halves.py results.s1s2.A.json results.s1s2.B.json` (stdlib, no network).

## Results (tier-1 grader, content criterion only, paired by probe)

Points are the STAMP fail rate minus the native fail rate; negative means STAMP failed less. The pooled
effect averages each probe's difference over the two halves; the interval is a 95% bootstrap over probes
and p a two-sided sign-flip test. The retest gap is the difference between the two halves' effects.

| Row | n | Native | STAMP | Half A | Half B | Gap | Pooled (95% CI) | p | Bad receipt |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| luna-s1 | 82 | 12.2% | 2.4% | -8.5 | -11.0 | 2.4 | -9.8 (-16.5, -3.7) | 0.006 | 7.3% |
| luna-s2 | 82 | 13.4% | 2.4% | -9.8 | -12.2 | 2.4 | -11.0 (-18.3, -4.9) | 0.002 | 1.2% |
| nemotron-s1 | 82 | 18.3% | 18.9% | -1.2 | +2.4 | 3.7 | +0.6 (-8.5, 9.8) | 1.000 | 65.2% |
| nemotron-s2 | 82 | 7.9% | 3.0% | -6.1 | -3.7 | 2.4 | -4.9 (-11.0, 1.2) | 0.170 | 6.1% |
| sonnet-s1 | 82 | 7.9% | 4.3% | -4.9 | -2.4 | 2.4 | -3.7 (-9.1, 1.2) | 0.247 | 18.3% |
| sonnet-s2 | 82 | 9.1% | 3.0% | -4.9 | -7.3 | 2.4 | -6.1 (-12.2, -1.2) | 0.046 | 17.7% |
| haiku-s1 | 82 | 6.7% | 2.4% | -3.7 | -4.9 | 1.2 | -4.3 (-10.4, 1.2) | 0.218 | 4.9% |
| haiku-s2 | 82 | 6.1% | 1.8% | -4.9 | -3.7 | 1.2 | -4.3 (-9.8, 0.6) | 0.220 | 6.7% |
| gemini-flash-s2 | 82 | 11.6% | 4.3% | -4.9 | -9.8 | 4.9 | -7.3 (-12.8, -2.4) | 0.013 | 5.5% |
| grok-s2 | 80 | 13.8% | 2.5% | -8.8 | -13.8 | 5.0 | -11.2 (-19.4, -3.8) | 0.006 | 0.6% |

Native and STAMP are fail rates over both halves. "Bad receipt" is the share of STAMP replies, both
halves, that fail at least one of `footer_check.py`'s R1 to R10.

**Q1 (System 1 rows).** The interval excludes zero on 1 of 4 rows (luna-s1). The point estimate is
negative on 3 of 4; on nemotron-s1 it is +0.6 points, STAMP no better than native.

**Q2 (System 2 rows).** The interval excludes zero on 4 of 6 rows (luna-s2, sonnet-s2, gemini-flash-s2,
grok-s2); nemotron-s2 and haiku-s2 cannot tell.

**Q3 (effect with reasoning on minus off, same model).** haiku +0.0 (-3.7, 3.7), luna -1.2 (-7.3, 4.9),
nemotron -5.5 (-16.5, 5.5), sonnet -2.4 (-7.3, 2.4). Every interval includes zero. No point estimate
shows a smaller STAMP effect with reasoning on; three lean the other way.

**Q4 (bad receipts, reasoning on minus off).** nemotron -59.1 points (-67.7, -50.0): with reasoning off,
95 of its 168 STAMP replies had no footer at all (R1). luna -6.1 (-11.6, -1.2). haiku +1.8 (-3.7, 6.7)
and sonnet -0.6 (-6.7, 4.9) cannot tell. On Sonnet both settings fail about one receipt in six, mostly
R6 (a `refs` URL that is not in the body, or the reverse).

## Against the decision rules and predictions

The registered rule reports an effect only when its interval excludes zero **and** its size exceeds both
the row's retest gap and the panel-measured grader bias for that row. The panel (tier 2) was not run, so
**no row meets the full rule, and none is reported as an established effect.** Five rows meet the first
two conditions on tier-1 verdicts: luna-s1, luna-s2, sonnet-s2, gemini-flash-s2 and grok-s2 (pooled
effect 6.1 to 11.2 points against gaps of 2.4 to 5.0). The pre-registration also requires a panel before
any effect under 5 points is quoted; all five pooled effects are 6.1 points or more, though sonnet-s2 was
-4.9 in half A alone.

| Prediction | Outcome |
|---|---|
| 1. STAMP lowers the fail rate on at least half of the System 1 rows | **Not supported.** 1 of 4 (luna-s1). |
| 2. The effect is smaller with reasoning on for at least half of the pairs | **Wrong in direction.** 0 of 4 point estimates; none distinguishable from zero. |
| 3. System 2 rows give false or missing receipts less often | **Partly.** Yes for nemotron and luna; haiku and sonnet cannot tell. |
| 4. Removing the receipt lowers the tier-1 PASS share by more than 1 point | **Not tested.** The receipt-stripped regrade was not run. |

## Losses, deviations and what was not done

- **Grok refusals.** xAI returned HTTP 403 ("permission-denied") for probes 45 and 46 in both conditions
  and both halves: 8 of 372 grok items (2.2%), under the 10% line. Both probes drop from grok's pairing
  (80 probes). promptfoo 0.124.1 stops a whole run after one 403, which cut each grok half to 76 items;
  the missing items were run again in smaller batches and then one at a time (Amendment 3's retry, $2.16).
  Every other row: 0 errored items.
- **Reasoning switch.** No -s1 reply reported reasoning tokens. Some -s2 replies reported none: luna 8 of
  336, gemini-flash 12, sonnet 16 (both halves, canaries excluded); they stay in their rows.
- **Not run:** the tier-2 panel on a 20% stratified sample, the receipt-stripped regrade (S1), and
  registration of these numbers in `docs/figures.json` (the registry's build reads the Calibration's
  pilot files, not promptfoo exports). The numbers here are reproducible from the committed files and
  their SHA-256 fingerprints, but they are tier-1 only.
- **Grader settings** differ from Calibration 001 (reasoning off here), so that issue's 4.1-point bias
  measurement does not transfer to this grader.
- **Development probes.** These are the probes STAMP was revised against (report Section 6.1); an effect
  on them is an upper bound on a general effect.
