# Revenue critique, 14 Oct 2026

A critic's read of everything on record: the repo, the site, the Funding Console (last revised 7 Sep),
the daily funding monitor, the Drive handoff of 12 Oct and the social kit. It asks one question: what
would bring in money without breaking the rules on /independence/?

## Where things stand

- **Revenue to date: $0** (the Console still shows $0 against the $5,500/month Floor). The three Stripe
  links on /support/ opened on 13 Oct, a day before this was written.
- **The site gives a lot and asks for little.** It has 30-odd pages, four Calibrations, three Logs, six
  Bench posts, a technical report and the policy trackers. The only way to pay is a donation button on
  one page.
- **The launch hasn't happened.** The arXiv report is unsubmitted (`paper/ARXIV_SUBMISSION.md`), and
  every link in `outreach/social-kit.md` is still a placeholder. The kit's Day 0 depends on arXiv, and
  so does nearly every grant reviewer and journalist who might look.
- **The September plan slipped.** The SFF Speculation Grant, the P-17 request batch, the sponsor tier
  sheet, the access-at-parity letters and the 30-day check (4 Oct) were all dated September. Nothing in
  Gmail or the repo shows any of them went out. /independence/ itself still says "Nothing has been
  asked of anyone yet."
- **The mail domain may still be unauthenticated.** The Console's 7 Sep DNS read showed a stale SPF
  record and no DKIM for bud.day. If that is still true, cold letters to funders land in spam and you
  never find out. Fix this before the first letter goes out.

## What's wrong, ranked by how much it costs us

1. **No launch means no audience, and no audience means no money.** Submit the report to arXiv this
   week. If arXiv asks for an endorsement, ask one of the cited LLM-as-judge authors. Then run the
   kit's Day 0 to Day 10 sequence. Reader money and grant money both follow attention, and the judge
   injection result (2.9% to 65.2% PASS) is the finding that earns it.
2. **The asks were written but never sent.** The SFF Speculation Grant is still the fastest cash on
   the list. Manifund is open and public. Re-check both programs' terms, since the Console fetched
   them on 4 Sep. The Foresight AI Safety Nodes deadline is **31 Oct** and NLnet's is **3 Nov**. Both
   were marked low-fit, so decide this week and write the decision down.
3. **There is nothing for a business to buy.** Readers donate, but companies buy services. The program
   already owns the most sellable skill it has: auditing an LLM-as-judge pipeline. Calibration 004
   showed one appended line moves a grader from 2.9% to 65.2% PASS. Sell that as a fixed-price
   **Judge Audit**: we run the injection, test-retest and human-anchor checks on a client's own judge
   and hand back a report.
   - Sell only to companies that *deploy* models (eval-tooling users, fintech, legal tech), never to
     the labs on the measurement list.
   - Reports are private to the client, and no client name or result ever appears in an issue.
   - Add a "Services" section to /independence/ before the first sale, so these terms are published
     before any money arrives, the way the P-17 to P-23 conditions were.
   - Suggested pricing: $2,500 for a 1-day audit of one judge, $7,500 for a full panel audit. This
     single line could cover the Floor.
4. **Workshops and talks.** A paid 90-minute workshop on how to read an AI test score could run off
   the Reader's Kit (eight questions, already written). Offer it to companies, bootcamps and
   libraries at $750 to $2,000. It doubles as outreach.
5. **Open-core tooling.** Ship the receipt checker as `pip install stamp-receipt` (the kit's item 4)
   and a GitHub Action under MIT. Later, a paid hosted dashboard or team support plan. This takes
   longer to pay off, but it is the asset that makes STAMP cited and adopted.
6. **Sponsorship tiers ($150 / $500 / $2,000 a month)** were decided on 7 Sep and never published.
   Publish the tier sheet on /support/. The targets are eval-tooling and observability companies whose
   customers sign contracts with model vendors. If any sponsor also serves models, the P-05 caps apply
   to them.
7. **Merch is small money with real brand value. Do it cheaply.** Use print-on-demand so there is no
   inventory. Keep merch off every issue page. Put merch revenue in the Support ledger as its own line.
   Never imply that buying merch buys influence. The brief for ChatGPT is below.
8. **Grants beyond the Console's list.** Re-verify each before applying, because names and terms move.
   - Coefficient Giving, formerly Open Philanthropy: the technical AI safety RFPs.
   - Schmidt Sciences: the science of AI safety and evaluation program.
   - The UK AI Security Institute's challenge and systemic-safety grants.
   - The AI Safety Fund, administered for the Frontier Model Forum. It is funded by measured labs, so
     it counts against the P-05 caps and needs the P-18 treatment.
   - NSF SBIR Phase I, with the Project Pitch first (the Console has it for January).
   - Lab researcher-access credit programs: development use only, under P-18.
9. **Smaller problems that cost trust, and therefore money:**
   - The home page says The Bench runs "Mon and Thu", while `harness/whats_due.py` and the release
     skill say Sundays and Wednesdays. Pick one.
   - The "Jester Mind, our own aggregated AI model, in the works" banner promises something with no
     page behind it. A grant reviewer will ask what it is. Either give it a one-paragraph page with a
     date, or take it off the strap.
   - The Funding Console hasn't been revised since 7 Sep, while the site moved on (payment links open,
     a new tax ID and bank account). The daily monitor is reporting from stale data.
   - The Model Radar routine's last run (12 Oct) shows ABANDONED.
10. **Measure the funnel without analytics.** The site rightly runs no analytics. Count from the
    systems you already have: the EmailOctopus subscriber total, Stripe payments, GitHub stars and
    forks, and referrer-free arXiv download counts. Log those numbers weekly in `LOG.md` so the
    effect of each launch step can be seen.

## Not worth doing

- Paywalling issues, offering early access, or selling a "supporter badge". /support/ promises none of
  these, and breaking that promise costs more than it would earn.
- Ads on issues. They are already refused. AdSense is allowed on the home page and Bench only, and it
  pays very little.
- Paid press-release sites, bought followers, vote rings, and anything sponsored by gambling, crypto or
  "AI detection" companies.

## Merch brief, to paste into ChatGPT

> I run Protocol STAMP (protocolstamp.com), an independent AI-evaluation publication. Its signature is a
> one-line receipt models print at the end of an answer: `[STAMPED v1.25 | parts n/n | figs n/n | ...]`.
> House style: IBM Plex Serif/Sans/Mono, paper `#F8EED3`, ink `#131E29`, stamp red `#A8432A`, a paw mark.
> Design a print-on-demand merch line (no inventory) of 6 items, each with: product, the exact text or
> art, colors, placement, and a 2-sentence product description. Ideas to start from, keep the best and
> add your own: a tee printing a full STAMPED receipt; a mug reading "February 30 does not exist."; a
> sticker "temperature 0 is not a measurement"; a sticker "One line moved our judge from 2.9% to 65.2%
> PASS"; a tote "Show your work."; a postcard set of the Reader's Kit's eight questions.
> Rules: never use another company's name or logo; no claims that STAMP "stops hallucinations"; no
> price tiers framed as support levels. Then recommend a print-on-demand provider that can sell through
> a Stripe Payment Link or a hosted storefront with no site tracking scripts, and price each item at
> roughly 2x base cost.

Bring ChatGPT's output back here. The ops desk will turn it into a `/shop/` page with one link per
product and the disclosure lines, plus a ledger entry. Creating Stripe products, publishing the page
and ordering samples all wait for Lawrence's approval.

## Addendum: ChatGPT's "Merchandise Strategy Plan" (shared 14 Oct, written 10 Oct)

**What it recommends:**
- Make the merch line *Budday Studio Editions* on bud.day, not STAMP merch.
- Launch three SKUs first: Family Story Interview Cards at $29, Family Stories Starter Kit (digital)
  at $19, and Preserve First Journal at $24.
- Hold back the rest: Sprint Planner $27, Desk Pad $22, Tote $25, Listening Notebook $22, art print
  $19.
- Sell through WooCommerce on bud.day, with Etsy for discovery and Pinterest for marketing. Use
  Printify for fulfillment, after proofs.
- Its scenarios are $360, $1,350 and $4,500 a month, explicitly "not forecasts".
- It built a 7-file launch kit (catalog CSV, calendar, copy, playbook, economics, checklist). That kit
  is stuck in ChatGPT's sandbox, so Lawrence has to download it and put it in Drive before the desk
  can use it.

**Where I agree:**
- Keep STAMP's merch separate and restrained. Its readers buy because they identify with the
  mission, not to solve a problem.
- Launch three products, not thirty.
- Order samples before listing anything.
- No paid ads until margins are proven.
- Go or no-go at day 90, judged on at least 10 independent paid orders.

**Where it's wrong, or misses something:**
1. **bud.day is not WordPress.** Checked live on 14 Oct: it is a static site behind Cloudflare.
   `/wp-json/` returns 404, and so do `/about/` and `/shop-coming-soon/`. WooCommerce would mean new
   hosting, plugins, a tax setup and ongoing maintenance. The cheaper route uses what already exists:
   - the static site, with one Stripe Payment Link per product (the Stripe account is already live)
   - Printify orders placed by hand at first, which is fine at 15 orders a month
   - or Etsy as the storefront for the physical goods, linked from bud.day
2. **Fix bud.day's dead links first.** Its own audit says so: About, Library, Resources and Shop all
   404 today. Pinterest won't approve a merchant with dead routes, and readers who follow the studio
   link from protocolstamp.com land on them now.
3. **"Analytics including UTM attribution and purchase events"** is fine on bud.day, but must never
   reach protocolstamp.com, which runs no analytics by policy. Links from STAMP to the shop stay
   plain, with no UTM tags.
4. **Scale.** Even its middle scenario ($1,350 gross a month) is under a quarter of STAMP's $5,500
   Floor before costs. Merch is a brand and studio play. The Judge Audit service and grants remain
   what can fund the program.

**For STAMP itself:** two or three restrained items at most (the receipt tee, the "February 30 does
not exist." mug, a sticker). Sell them from bud.day's shop, with a single "Merch" line on /support/.
Put the revenue in the ledger as its own line, and disclose that buying merch buys no influence.
