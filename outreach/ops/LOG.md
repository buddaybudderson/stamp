# Ops desk log

Newest entry first. Every run of the ops desk appends one entry. See `OPERATOR.md`.

## 2026-10-14 (Wed): desk opened

**Did:**
- Read the repo, the site's money pages, the Funding Console (rev. 7 Sep), the existing routines, and
  the Drive handoff of 12 Oct.
- Wrote `revenue-critique-2026-10-14.md` and `OPERATOR.md`.
- Set up the twice-daily routine "STAMP ops desk" (08:46 and 17:46 America/Chicago).

**Drafts waiting for Lawrence:**
- The merch brief to paste into ChatGPT (end of the critique).
- A decision on the Judge Audit service and the sponsor tier sheet.

**OPEN:**
- arXiv report not submitted. This blocks the launch, the social kit and most grant credibility.
- SFF Speculation Grant, the P-17 batch, sponsor tiers and access-at-parity letters: all dated
  September, with no sign they went out.
- Foresight AI Safety Nodes deadline is 31 Oct, and NLnet's is 3 Nov. Decide whether to apply or skip
  each one.
- bud.day mail authentication (SPF and DKIM), last checked 7 Sep: not fixed as of that check.
- Bench cadence conflict: the site says Mon and Thu, the code says Sun and Wed.
- The "Jester Mind" banner has no page behind it.
- The Model Radar routine's run on 12 Oct was ABANDONED.
- The Funding Console is stale (payment links, tax ID and bank account changed since 7 Sep).

**Next run:** Thu 15 Oct, 08:46. News sweep (SI, military AI, footprint, data centers), plus triage.

### 2026-10-14, later: ChatGPT merch plan received
- Read Lawrence's ChatGPT share ("Merchandise Strategy Plan", written 10 Oct). Summary and critique
  added as an addendum to the revenue critique.
- **OPEN:** Lawrence to download `Budday_Studio_Merch_Launch_Kit.zip` from that ChatGPT chat into
  Drive (the sandbox files expire).
- **OPEN:** bud.day dead routes (/about/, /shop-coming-soon/ and others) return 404. Fix before any
  shop launch.
- **Decision needed:** the storefront. My recommendation is Stripe Payment Links plus Printify, or
  Etsy, rather than WooCommerce, since bud.day is not WordPress.

### 2026-10-14, later still: decision on merch focus
- **Decision (Lawrence):** sell merch on protocolstamp.com first; bud.day is parked. The critique has
  a new section setting out the storefront design (Stripe Payment Links, no embedded scripts), the
  first drop of three items, and an updated brief for ChatGPT.
- **Next revenue run (Wed 14 Oct, 17:46):** draft `docs/shop/index.html` on this branch, in site
  chrome, with the products marked "coming soon" and no Stripe links yet. Also draft the
  /privacy/, /terms/, /support/ and /corrections/ lines. Nothing goes live until Lawrence approves
  the designs and samples and creates the Stripe products.
- **OPEN:** the routine was created without Gmail or Drive connectors. Lawrence has to add them in
  claude.ai → Routines → "STAMP ops desk" → connectors. Until then, Gmail triage and drafts are
  skipped, and the run says so.
- **Superseded:** the earlier OPEN items about bud.day dead routes and the launch-kit ZIP. Parked with
  bud.day.

### 2026-10-14, evening: /shop/ drafted
- Built `docs/shop/index.html` in site chrome, with three items marked "Not yet / price to be set" and
  no checkout links. Added "Shop" to the Trust menu, page search and sitemap, a Change row in
  /corrections/, and set no reader-ask box on the shop page.
- Gates: house_gate PASS (0 FAIL). The holdout gate could not run in the cloud session (the bank
  is not in the repo); Lawrence runs `python harness/holdout_gate.py --path docs` locally before
  merge. Rendered at 1280px and 390px with no horizontal overflow.
- **Waiting for Lawrence:**
  1. Approve the page text.
  2. Get the designs from ChatGPT (brief in the critique).
  3. Order samples.
  4. Create the 3 Stripe Payment Links with shipping-address collection on.
  5. Add shipping and returns text to /terms/ and the printer line to /privacy/.
  6. Merge.

### 2026-10-14, late: grants researched and the grants post written
- **Grants:** checked 25+ programs, using official pages where reachable and Manifund's AI Safety
  Funder Bulletin (updated Oct 1). Published as the essay `/writing/grants/`
  (buddaybudderson/stamp PR #57), on Lawrence's instruction to post it publicly.
  - Eight to apply to, none asking above $60,000: Foresight (Oct 31), SFF Speculation, Lightcone
    Commons, EA Funds TAIF, Manifund, FLOSS/fund, BlueDot Rapid, NSF SBIR pitch.
  - Not applying, with reasons on the page: Humanity AI (needs a 501(c)(3) lead), Amazon Research
    Awards, NLnet, Middle Powers, Mercor, and the closed calls.
- **Corrections to the critique:**
  - SFF's 2026 main round is closed. Speculation grants are rolling via the SFF rolling form.
  - Coefficient Giving's technical AI safety RFP, Schmidt Sciences and UK AISI are all closed.
- **Gmail drafts created (b@bud.day, not sent):**
  1. Foresight application answers.
  2. Letter of interest to California's Government Operations Agency (SB 813 IVOs / N-9-26
     convening, roughly mid-November).
- **Evaluation:** the S1 vs S2 pre-registration is UNSIGNED, so no model calls until Lawrence signs.
  The cost estimate for the first full report is $19.24, and preflight wants $29 on the key.
- **Bench cadence resolved:** the site is right (Mon and Thu since Sep 10). `harness/whats_due.py`
  still says Sun and Wed and needs fixing.
- **OPEN, in deadline order:**
  - Foresight, Oct 31: file.
  - SFF rolling form: file.
  - Lightcone: next answer around Jan 23, 2027.
  - TAIF: ask about for-profit eligibility, then file.
  - Manifund: post the project.
  - BlueDot Rapid: file.
  - FLOSS/fund: confirm 2026 intake.
  - NSF: pitch.

### 2026-10-14: grants post live
- Merged buddaybudderson/stamp PR #57 with Lawrence's approval; Eval gate and Cloudflare Pages both
  green. https://protocolstamp.com/writing/grants/ is served with status 200.
- **OPEN, site-wide, not caused by this PR:** Cloudflare injects its bot-detection script
  (`/cdn-cgi/challenge-platform/...`) before `</body>` on every HTML page checked: /, /support/ and
  /writing/grants/. That breaks the house rule that nothing rewrites HTML at the edge, and the
  promise of no third-party scripts.
  - Frozen issue `source` files are NOT affected; Calibration 004's source is served clean.
  - Fix, in the Cloudflare dashboard: Security → Bots → turn off "JavaScript Detections" (and
    Bot Fight Mode, if it is on). Then purge the cache.
  - The Cloudflare connector is not authorized in this session, so this needs Lawrence.

### 2026-10-14: DECISION, Cloudflare bot detection stays ON
- Lawrence's decision: keep it. It is already disclosed on /privacy/: Cloudflare inserts a
  bot-detection script on web pages, Bot Fight Mode is off, and no setting on the plan removes it.
  Issue sources are served clean.
- The OPEN item above is withdrawn; I flagged it without reading /privacy/ first. **Do not raise
  this again** unless Cloudflare's behaviour changes, for example if the script appears on an
  issue's source file.

### 2026-10-14: Foresight application finalised, except the reference
- Lawrence's answers, given one question at a time:
  - Bay Area node, two one-week sprints in 2027, travelling from Houston.
  - Open source: yes, except the held-out probes (reason stated in the application).
  - Workshop: yes, Bay Area or Berlin.
  - Lightcone Commons sharing: yes.
  - Ask: $60,000, as published.
- Gmail draft "Foresight Nodes application, ready except the reference" (b@bud.day) is mapped field
  by field to the real Airtable form. Every figure was checked against `paper/stamp-report.md`.
- **OPEN, due Oct 31, 23:59 PDT:** Lawrence to supply a reference (name and email), then file.
  Remind him on every run until it is filed. When he says it's filed, add the filing date to
  `/writing/grants/`.
