# The verification ladder, in plain language
*STAMP labels every fact with the "rung" it came from. This page explains what that means, so the labels in the STAMPED footer make sense. It is documentation - it is not part of the core the model reads, so it costs no tokens at run time.*

## What "ladder" and "rung" mean
A **rung** is a step on a ladder - the bar you put your foot on. STAMP treats checking a fact like climbing a ladder: it starts on the lowest, most trustworthy step (something already in front of it) and **climbs higher only when the lower step cannot answer.** Each step is a rung, numbered 1 to 5. When STAMP labels a claim with a rung, it is telling you *how* it knows the thing - so you can judge how much to trust it.

## The five rungs (lowest and most trusted first)
1. **Rung 1 - you gave it.** The file, data, or instructions you provided in this conversation. Most trustworthy, because the material is right there. Example: you paste a spreadsheet and ask about a number in it.
2. **Rung 2 - its own memory.** The model's trained knowledge - what it "remembers" from training. It cannot point to a live source and may be out of date or simply wrong. **This is where guessing risk is highest.** Example: "What is the capital of France?" answered from memory.
3. **Rung 3 - live web.** It ran a real web search just now and read current pages; you can check the link. Example: "What is today's exchange rate?"
4. **Rung 4 - your connected store.** Documents you loaded into a searchable place (a Gemini Gem's Knowledge, a Claude Project's files, a vector database), or earlier messages in this same chat. Example: "Per our handbook, what is the travel policy?" when the handbook is uploaded.
5. **Rung 5 - ask you.** When it genuinely cannot find the answer any other way, it stops and asks you to supply the material instead of inventing it.

## Why the number matters
The rung is printed in the STAMPED footer's `refs` field, like `refs Reuters (rung 3)` or `refs your handbook (rung 4)`. It lets you see at a glance whether an answer was **looked up** (rungs 3-4, checkable) or **recalled from memory** (rung 2, treat with care). Most other assistants do not tell you this - they present every answer with the same confidence whether they checked or guessed. STAMP makes the difference visible on every claim.

## How this connects to retrieval ("the library card")
Without a search tool connected, the model can only use rung 1 (what you gave it), rung 2 (memory - the risky one), or rung 5 (ask you). Connecting a tool unlocks the higher, checkable rungs:
- Turn on **web search** -> unlocks **rung 3**.
- Connect **your documents** -> unlocks **rung 4**.
So "giving the AI a library card" literally means enabling the rungs where answers can be verified. STAMP does not do the retrieving itself - it names and grades honestly whatever the tool returns. See INSTALL.md and NATIVE_VS_STAMP.md for setup.
