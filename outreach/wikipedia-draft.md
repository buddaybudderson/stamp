# Wikipedia draft: STAMP (prompt protocol)

**Do not submit yet.** As of Oct 13, 2026 there are no independent, reliable sources about STAMP, so an
article would fail Wikipedia's general notability guideline and be declined. Keep this draft and add
sources as they appear. Submit through Articles for Creation only when there are at least three
independent sources from different publishers that discuss STAMP in depth (see "Sources needed" below).

**Conflict of interest.** You are the developer. Before you edit, disclose the connection on your user
page, put `{{Connected contributor|User1=<your username>|U1-declared=yes}}` on the draft's talk page,
and never move the draft to the main article space yourself. After acceptance, suggest changes on the
talk page with `{{Edit COI}}` instead of editing the article.

**Rules this draft follows.** Neutral wording, no claims of effectiveness unless an independent source
makes them, the project's own pages used only for plain facts (licence, release, what the files
contain), and a hatnote to the unrelated safety-engineering STAMP.

---

## Wikitext (paste into Draft:STAMP (prompt protocol))

```wikitext
{{Short description|System prompt for language model self-verification}}
{{Distinguish|System-Theoretic Accident Model and Processes}}
{{Draft topics|computing|software}}

'''STAMP''' is an open-source [[system prompt]] for [[large language model]]s, released under the [[MIT License]] by Budday Budderson Studio LLC in 2026.<ref name="repo">{{cite web |title=buddaybudderson/stamp |url=https://github.com/buddaybudderson/stamp |website=GitHub |access-date=<!-- date -->}}</ref> It instructs a model to recompute figures before repeating them, to treat instructions found inside documents as data rather than commands, to ask a clarifying question when a request is under-specified, and to end each reply with a one-line structured self-report called a "STAMPED" footer.<ref name="repo" />

<!-- LEAD SENTENCE ON SIGNIFICANCE: add only when an independent source supports it, e.g.
"STAMP has been described by <publication> as ..." with that source cited. -->

== Design ==
The protocol defines six rules, a five-step process (Scope, Tackle, Audit, Mark, Present) and a five-level scale for labelling the source of a claim, from material supplied by the user to live web retrieval.<ref name="repo" /> The footer records counts such as the number of requested parts answered and figures recomputed, which can be compared with the reply.<ref name="repo" /> The developers describe the footer as a self-report that does not prove a claim is true.<ref name="repo" />

== Evaluation ==
<!-- ONLY independent evaluations belong here. Examples of acceptable sources: a peer-reviewed paper
that tests STAMP; a replication by researchers not connected to the studio; coverage in a technical
publication with editorial oversight. Do NOT cite the studio's own Calibration issues as evidence of
effectiveness. If the arXiv report is the only evaluation, say "its developer reported ..." and cite it. -->

== Reception ==
<!-- Independent coverage only. Leave out if there is none. -->

== See also ==
* [[Prompt engineering]]
* [[Prompt injection]]
* [[Hallucination (artificial intelligence)]]

== References ==
{{reflist}}

== External links ==
* {{Official website|https://protocolstamp.com}}
```

---

## Sources needed before submission

| Kind | Counts toward notability? | Status |
|---|---|---|
| Your GitHub repository, site, Calibration issues | No (not independent) | have |
| Your arXiv report | No (self-published), but citable for plain facts | to do |
| A peer-reviewed paper of yours | Weak (independent review, but written by you) | to do |
| A paper by others that evaluates or cites STAMP in depth | Yes | none yet |
| Coverage in a technical publication with editorial oversight | Yes | none yet |
| Blog posts, social posts, Hacker News, Reddit, press releases | No | n/a |

## The faster route

Once an independent, reliable source discusses STAMP, a one-sentence mention in an existing article
(for example the defences section of "Prompt injection") may be accepted before a standalone article
would be. Propose it on that article's talk page with `{{Edit COI}}`, cite the independent source, and
let another editor decide.
