# STAMP v1.25 - promptfoo evaluation (native vs STAMP, six models)

Reproducible, provider-agnostic eval. Each probe runs **twice** - native (no system
prompt / control) and STAMP-added (STAMP v1.25 core in the system slot + the STAMP
"story" doc loaded as an in-context knowledge base) - across up to six models, graded
automatically.

Matrix size: **2 conditions x 6 providers x 71 probes = 852 model calls**, plus the
llm-rubric grading calls. Start with one provider to keep it cheap, then add the rest.

## What this proves (the evidence model)
promptfoo is API-based, so it does not screenshot a chat window. It produces something
stronger and more STAMP-aligned:

1. A **re-runnable config** (this folder) - anyone can reproduce the run byte-for-byte.
2. An **exported transcript** (`results.json` / `results.html`): per cell, the exact
   input sent (including the full STAMP system prompt), the model output, token usage,
   latency, cost, every assertion's pass/fail + reason, and the raw request/response
   bodies (including provider response IDs where the API returns them).
3. A **results web UI** you can screenshot as a visual exhibit (`promptfoo view`), and
   a shareable snapshot URL (`promptfoo share`).

## Files
- `promptfooconfig.yaml` - the matrix: 2 prompts x providers x tests, grader, outputs.
- `prompts.js` - builds both conditions from the REAL shipped files. `stamp` reads the
  core between the CORE START/END markers in `../../STAMP_v1.25/STAMP.md` AND appends
  `The story of STAMP.md` as a KNOWLEDGE BASE block, so the two-tier canary works.
- `assert.js` - automated STAMPED-receipt grader. On STAMP outputs it requires a well-formed
  `[STAMPED ...]` footer and flags a likely FALSE RECEIPT; native passes automatically.
- `tests.yaml` - AUTO-GENERATED (66 probes) by `gen_tests.py` from
  `../../STAMP_v1.25/tests/PROBES.md`. Each probe's own "Pass:" line becomes an
  llm-rubric criterion. Regenerate anytime: `python3 gen_tests.py`.
- `tests_fixtures.yaml` - 5 hand-authored concrete versions of high-value probes that
  appear in PROBES.md only as fixture descriptions (false-total #76, injection doc #41,
  dual-use #45, RAG-with-doc #92, RAG-without-doc #93).
- `gen_tests.py` - the generator. Skips agent probes 81-90 (need a tool-using deployment)
  and pure descriptions with no literal prompt.

Keep the layout: `.../12_CROSSPLATFORM_EVAL_v1.25/promptfoo/` next to `.../STAMP_v1.25/`.

## Setup (on your machine - keys never leave it)
1. `npm install -g promptfoo`  (or run everything with `npx promptfoo@latest ...`).
2. Set the key(s) for the providers you want, as environment variables - NOT in any file:
   - Gemini: `GEMINI_API_KEY`   (also used as the grader)
   - Claude: `ANTHROPIC_API_KEY`
   - OpenAI: `OPENAI_API_KEY`
   - Grok:   `XAI_API_KEY`
   - Perplexity: `PERPLEXITY_API_KEY`
   - Kimi/Moonshot: `MOONSHOT_API_KEY`
   Windows: `setx GEMINI_API_KEY "..."` (reopen the terminal after).
   > Security: keys live only in your shell env. If you ever pasted one into a chat, revoke it.
3. **Pick your providers.** In `promptfooconfig.yaml`, comment out any provider row you
   don't have a key for, and adjust each model string to one your key can access (the
   defaults are reasonable but change over time).

## Run
```
cd 12_CROSSPLATFORM_EVAL_v1.25/promptfoo
promptfoo eval        # runs the matrix; writes results.html + results.json
promptfoo view        # opens the results UI (screenshot this for a visual exhibit)
promptfoo share       # optional: shareable snapshot URL
```
Tip: start cheap. Comment out five providers, leave Gemini, run once, confirm the matrix
looks right, then add the others.

## Reading the matrix
Each row = one probe; columns = native vs stamp, per provider. Green = assertions passed.

- **Probe #101 ("original name of STAMP")** is a grounding canary graded strictly on the
  word SCOTT: **native is EXPECTED to be red** (a model with no STAMP knowledge cannot
  know "SCOTT"); **stamp is green**. That red/green split is the demonstration, not a bug.
- **Probe #100 ("why was 'Craft' rejected")** is the knowledge-layer canary: it passes
  only because `prompts.js` loads the story doc into the STAMP condition. Native red,
  stamp green.
- **Probe #102 (Tokyo + link)** is the citation-honesty / Perplexity contrast: a model
  with live retrieval (Grok, Perplexity) may give a real link; a model without must NOT
  fabricate one. The assertion fails only a fabricated link with no sign of retrieval.
- The STAMPED grader (`assert.js`) runs on every cell but only bites on STAMP outputs.

## Extend / adjust
- Add or edit probes: change `PROBES.md`, rerun `python3 gen_tests.py`, re-eval.
- Add a provider: copy a row in `promptfooconfig.yaml`, set its env key. Grok/Perplexity/
  Kimi/Sakana are all OpenAI-compatible via `apiBaseUrl`.
- Grading model: `defaultTest.options.provider` (default Gemini) grades every llm-rubric.

## Limits (stated plainly)
- No chat screenshots (API, not a browser). Screenshot the results UI instead.
- Response IDs appear only where the provider's API returns them.
- Agent probes 81-90 are excluded (they need a tool-using deployment to be meaningful).
- This config was validated for YAML/JS syntax here but NOT executed (no keys in this
  environment, by design) - the first real run happens on your machine with your keys.
