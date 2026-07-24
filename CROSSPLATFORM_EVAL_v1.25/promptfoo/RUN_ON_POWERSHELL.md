# Running the STAMP eval on Windows PowerShell — step by step

Yes, this runs on PowerShell. promptfoo is a Node.js CLI, so everything is cross-platform;
the only Windows-specific bit is how you set the API key (shown below). Do a cheap
Gemini-only run first, confirm the matrix looks right, then add the other models.

---

## Step 0 — Unzip the bundle
Unzip `STAMP_v1.25_promptfoo_bundle.zip` somewhere simple, e.g. `C:\STAMP`.
You should end up with:
```
C:\STAMP\STAMP_v1.25\...
C:\STAMP\12_CROSSPLATFORM_EVAL_v1.25\promptfoo\...
```
Keep those two folders side by side — the config reads the STAMP files by relative path.

## Step 1 — Install Node.js 24 LTS (once)
Check if you already have it. Open PowerShell and run:
```powershell
node -v
npm -v
```
If `node -v` shows v24 (or v22.22+), skip ahead. Otherwise install Node 24 LTS — easiest:
```powershell
winget install OpenJS.NodeJS.LTS
```
(or download the LTS installer from https://nodejs.org). **Close and reopen PowerShell**
after installing, then re-run `node -v` to confirm.
> Node 20 reaches end-of-life on July 30, 2026, so go straight to 24 LTS.

## Step 2 — Install promptfoo
```powershell
npm install -g promptfoo
promptfoo --version
```
If PowerShell says *"running scripts is disabled on this system"* when you run promptfoo,
either allow local scripts once:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
…or skip the global install entirely and prefix every command with `npx`, e.g.
`npx promptfoo@latest eval`.

## Step 3 — Go to the eval folder
```powershell
cd C:\STAMP\12_CROSSPLATFORM_EVAL_v1.25\promptfoo
```

## Step 4 — (Recommended first run) trim to Gemini only
Open `promptfooconfig.yaml` in Notepad:
```powershell
notepad promptfooconfig.yaml
```
Under `providers:`, put a `#` in front of every line for claude, openai, grok,
perplexity, and kimi — leave only the `gemini` block active. Save and close.
(You can re-enable them later by deleting the `#`s.)

## Step 5 — Set your Gemini API key (this PowerShell window only)
```powershell
$env:GEMINI_API_KEY = "PASTE_YOUR_KEY_HERE"
```
This keeps the key in memory for this session only — nothing is written to disk.
- To confirm it's set: `echo $env:GEMINI_API_KEY`
- If you'd rather set it permanently for future terminals: `setx GEMINI_API_KEY "YOUR_KEY"`
  then open a NEW PowerShell window (setx does not affect the current one).
> Never paste a key into the config file or a chat. If a key was ever exposed, revoke it
> in Google AI Studio and mint a new one.

## Step 6 — Run the eval
```powershell
promptfoo eval
```
It sends each probe twice (native vs STAMP) to Gemini and grades the replies. It writes
`results.html` and `results.json` in the folder. A Gemini-only run is 71 probes x 2 = 142
calls, so it takes a few minutes on the free tier (rate-limited).

## Step 7 — View + screenshot the results
```powershell
promptfoo view
```
This opens the results table in your browser: rows = probes, columns = native vs stamp,
green = passed. Screenshot this for a visual exhibit. `results.html` is the same table as
a standalone file you can open or share; `results.json` is the full machine-readable
transcript (inputs, outputs, tokens, latency, pass/fail + reasons).

Optional shareable snapshot URL:
```powershell
promptfoo share
```

## Step 8 — Add the other five models
When the Gemini run looks right, edit `promptfooconfig.yaml` again, un-comment the
providers you want, set each key in the SAME window, then re-run `promptfoo eval`:
```powershell
$env:ANTHROPIC_API_KEY  = "..."   # Claude
$env:OPENAI_API_KEY     = "..."   # OpenAI
$env:XAI_API_KEY        = "..."   # Grok
$env:PERPLEXITY_API_KEY = "..."   # Perplexity
$env:MOONSHOT_API_KEY   = "..."   # Kimi
promptfoo eval
```
All six providers = 71 x 2 x 6 = 852 calls plus grading, so expect it to run longer and
cost more.

---

## What to expect in the matrix
- **#101 (original name of STAMP)**: native RED (can't know "SCOTT"), stamp GREEN. The
  split is the point — proof STAMP is grounding on its own document.
- **#100 (why "Craft" was rejected)**: native RED, stamp GREEN (the story doc is loaded
  into the STAMP condition).
- **#102 (Tokyo + link)**: models with live search (Grok, Perplexity) may give a real
  link; models without must not fabricate one.

## Quick troubleshooting
- `promptfoo: command not found` → reopen PowerShell after `npm install -g`, or use `npx promptfoo`.
- `Cannot find module` / path errors → make sure you `cd`'d into the `promptfoo` folder and
  that `STAMP_v1.25` sits one level up beside `12_CROSSPLATFORM_EVAL_v1.25`.
- Auth / 401 / "API key" errors → the `$env:...` key isn't set in THIS window; set it again.
- Rate-limit errors on free tier → normal; promptfoo retries. Run fewer providers at a time.
