# Protocol STAMP — the harness

The instrument is open. The bank is not.

This directory holds the code that runs a measurement: the candidate runner, the
graders, the release gates, the statistics and the figure generation. It does not
hold the probe bank, and it never will — 28 of the 63 probes in the evaluation
bank are held out and never published, because an instrument that can be trained
against stops measuring anything.

Four scripts are absent from this directory for that reason. `build_attribution_bank.py`,
`build_pilot_bank.py`, `build_provenance_bank.py` and `patch_bank_v1a.py` construct the
bank and carry probe text inline, so they live in the private repository alongside it.
A bank builder belongs with the bank.

## What you can do with this

Point it at your own probes and run it. That is the whole reason it is here: a score
you cannot reproduce is a claim, and this is the difference between asking you to
believe our numbers and letting you generate your own.

The public portion of our bank — 35 of the 63 probes, every row flagged
`holdout: false` — is published at `docs/data/bank_v1_public.jsonl` in this repository.

## Added 2026-10-05 — checks that need no judge, and tests of the judges

Each was shown to pass known-good input and to refuse a deliberately planted fault before
it was published here; `test_receipts.py` repeats that for the receipt and trajectory
checks on every run.

| Script | What it answers |
|---|---|
| `footer_check.py` | Is a reply's STAMPED footer true of the reply? Counts, forms, refs against body, fabricated links, and every `a + b = c` the reply shows (R1–R10). |
| `trajectory_grade.py` | Did an agent run follow its spec step by step — no invented tools or parameters, no skipped safety step, A3's read-before and verify-after, one retry, no loops — and does its `act` count match? Names the first step that broke. |
| `compare.py` | Is model B better than model A on the same items? Paired by item, sign-flip test, minimum detectable effect, and a guard against one set of replies graded twice. |
| `verbosity_bias.py` | Does a judge reward length? Within items, by permutation, with a human-label anchor where one exists. |
| `contamination.py` | Has held-out text reached a file, reworded or not (`scan`)? Has a model started passing the public half more than the held-out half since it was published (`divergence`)? |
| `eval_gate.py` | Does a protocol change regress quality, latency, cost or receipt truth? Run in CI by `.github/workflows/eval-gate.yml`; it checks committed results and never calls a model. |
| `drift.py` | Same model id, later run: did quality, serving host, reply shape or failure rate move? |
| `pareto.py` | Cost against fail rate, overall and per probe family; measured spend where recorded, marked estimates where not. |
| `longctx.py` | Builds the long-session variants of the public items (prior turns, long documents, a planted figure) and reads receipt truth and "ceremonial" receipts by depth. |
| `probe_forge.py` | Drafts candidate probes — conflicting documents, injection canaries, tone-flip pairs, attacks on the grader — for a person to review. Nothing it writes enters a bank unreviewed. |

`regrade.py` and `panel_grade.py` now record what each grading call cost, and `pilot_native.py`
records each answer's latency.

## The gate

`harness_gate.py` refuses to publish any file carrying bank text. It is the same
discipline as `holdout_gate.py`, applied to this repository instead of the site.

    python3 harness_gate.py --bank <private>/bank/bank_v1.jsonl --paths .
    python3 harness_gate.py --bank <private>/bank/bank_v1.jsonl --staged   # pre-commit

Exit codes: `0` clean, `1` bank text found, `2` the gate could not do its job.
**Two is not success.** A gate with no bank to compare against, or no files to scan,
refuses rather than reporting a pass — a check that passes because it asked nothing is
worse than no check at all.

Install the hook:

    cp pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
    export STAMP_BANK=/path/to/private/bank/bank_v1.jsonl

Both directions were verified before this code was published: the gate passes the 27
files here, and refuses when a bank builder is placed among them. Re-verified 2026-10-05
with the additions above: it passes the 41 files now here and still refuses a planted builder.

---
*Published by Budday Budderson Studio LLC, a New Mexico company*
*Begun by a person · Drafted by AI · Edited together · Signed by a person*
