# arXiv submission sheet

Everything arXiv's form asks for, ready to paste. The upload is `stamp-report-arxiv.tar.gz` in this
folder (LaTeX source only; arXiv compiles it). It was compiled here with pdflatex (TeX Live) in two
passes with no errors; `stamp-report.pdf` is that build, for checking.

**Before you press Submit:** read the PDF once end to end, and confirm every number in Sections 5
and 6 against the issue or file it cites. You sign for it, not the tool that drafted it.

## Account and endorsement

1. Register at arxiv.org with your real name (Lawrence Ho) and add your ORCID iD if you have one.
2. Start a submission in **cs.CL**. If arXiv asks for an endorsement, it shows a code. Send that code
   to an established cs.CL, cs.AI or cs.LG author and ask them to endorse you. Good candidates are
   researchers whose work you cite or who work on LLM evaluation. Endorsement checks topic fit, not
   quality. Never pay for one.

## Form fields

- **License:** CC BY 4.0
- **Primary category:** cs.CL (Computation and Language)
- **Cross-lists:** cs.AI, cs.CR
- **Title:** STAMP: An Auditable Self-Verification Protocol for Language Models, and What It Takes to Measure One
- **Authors:** Lawrence Ho
- **Comments:** 15 pages, 5 tables. Code, data and run files: https://github.com/buddaybudderson/stamp
- **Report number, journal reference, DOI, MSC, ACM:** leave blank
- **Abstract** (1872 characters; arXiv's limit is 1,920):

```
We describe STAMP, a provider-agnostic system prompt of about 1,500 tokens that asks a language model to recompute figures, treat text inside documents as data rather than instructions, ask instead of guessing, label each material claim with its evidence, and end every reply with a one-line structured self-report, the STAMPED receipt. The receipt's counted fields can be checked against the reply without a judge model, and we release a deterministic checker that does so. We then report what happened when we tried to measure the protocol. On a 63-item adversarial bank run in two independent halves of five draws per item, the bank was reliable (Spearman-Brown 0.945 and 0.941), but the conditions around it were not: 56 of 63 responses differed between two temperature-0 runs on a pinned provider; our tier-1 grader was 4.1 points more lenient than a three-family panel; three judges agreed with each other (AC1 0.875) more than any agreed with one person's blind labels (best 0.685), below the 0.871 of a judge that always says PASS; and one appended line moved the grader from 2.9% to 65.2% PASS on answers it had failed. The protocol's effect depended on which probes measured it. On its own public development probes, ten single-draw runs (eight models from eight developers) showed STAMP lowering the content fail rate by 6.1 to 23.2 points, with install-check probes excluded. On the bank it was not tuned on, the one controlled estimate was -0.9 points, smaller than the grader's bias. We read the gap as the signature of a protocol and its test written together, and do not claim a general effect. We release the public bank, the harness, every run file we can publish, and a pre-registered run on reasoning-off and reasoning-on settings of the same models, which found no sign, on tier-1 verdicts, that reasoning shrinks the effect on the development probes.
```

## After it is announced

- Put the arXiv identifier in the repository README, the site's About page and `paper/README.md`.
- Tag a GitHub release, connect the repository to Zenodo, and add the DOI to the Reproducibility
  section in version 2.
- Replace the placeholders in `outreach/social-kit.md` with the arXiv link before posting.
