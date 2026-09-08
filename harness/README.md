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
files here, and refuses when a bank builder is placed among them.

---
*Published by Budday Budderson Studio LLC, a New Mexico company*
*Begun by a person · Drafted by AI · Edited together · Signed by a person*
