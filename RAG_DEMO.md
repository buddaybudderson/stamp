# Demonstrating RAG with probes 113 and 114
*A knowledge base (also called RAG - Retrieval-Augmented Generation) means giving the model a set of documents it can pull from at answer time. Probes 100 and 101 are built to show, in three quick tests, what installing a knowledge base actually changes about an answer. This is documentation; run the tests yourself to turn "expected" into "measured".*

## Why these two probes make a clean demonstration
Both ask for a fact that exists ONLY inside the STAMP files and nowhere in any model's training data:
- **Probe 101:** "What is the original name of the STAMP protocol?" - answer **SCOTT**, which lives in the **core**.
- **Probe 100:** "Why was the name 'Craft' rejected?" - answer (CRAFT is already a known prompting acronym), which lives ONLY in **The story of STAMP.md**.
Because the facts are not on the public web, a model can only answer if the relevant STAMP text is actually loaded. That makes the answer a clean signal: a correct answer proves the document reached the model; "I do not know" proves it did not.

## The three-state experiment
Run each probe in a fresh chat under three setups and compare:

| Setup (what is loaded) | Probe 101 (core fact: SCOTT) | Probe 100 (knowledge fact: why Craft) | What it shows |
|---|---|---|---|
| **A. Native** - nothing installed | "I do not know" | "I do not know" | baseline: the model has neither fact |
| **B. Core only** - STAMP.md in the instructions slot, no knowledge files | **answers SCOTT** | "I do not know" | the rules are loaded, but the knowledge base is not |
| **C. Core + knowledge** - STAMP.md installed AND The story of STAMP.md added as a knowledge file | **answers SCOTT** | **answers the reason, cites the story** | the knowledge base is now feeding the model |

*(Outcomes above are the expected result from STAMP's design and from prior measured runs of this probe class; confirm on your exact deployment - every result is unmeasured until you run it.)*

The lesson is in the one cell that changes between B and C: **probe 114 flips from "I do not know" to a correct, sourced answer the moment the knowledge base is installed.** That flip - a question the model could not answer becoming answerable, grounded in a document you supplied - is exactly what a RAG/knowledge base does. Nothing about the model changed; only what it could reach changed.

## How to install the knowledge base (so state C works)
Add the documents to the searchable "knowledge" area of a container, then chat inside that container:
- **Gemini:** open your STAMP **Gem** -> Knowledge -> upload `The story of STAMP.md` (and any other STAMP files). The Gem now retrieves from them.
- **Claude:** open your STAMP **Project** -> add files to the Project's knowledge -> upload the story. Every chat in the Project can now use it.
- **ChatGPT:** a **Project** or **Custom GPT** -> Knowledge -> upload the story.
- **API / developer:** put the documents in a vector store and attach a file-search/retrieval tool to the request; the model retrieves the relevant passage per query. This is "real" RAG - the store can hold far more than fits in one prompt.
- **PDF or scanned sources:** parse them to clean Markdown first (e.g., opendataloader-pdf, Apache-2.0) before loading - raw PDFs ingest as garbage. See the "Ingesting PDFs and scanned documents" section in INSTALL.md.
STAMP then labels what comes back: an answer sourced from the loaded story is **rung 4** (connected store) or **rung 1** (if the file sits directly in context). See RUNGS.md.

## What this demonstrates, and the honest boundary
- **Demonstrates:** a knowledge base changes the OUTPUT - it turns "I cannot answer" into a grounded, cited answer, without retraining the model. That is the entire value of RAG.
- **Confirms the install worked:** probe 114 answering correctly is direct evidence your documents are actually being retrieved - not assumed, measured.
- **Honest boundary:** pasting the story text into a single chat message also makes probe 114 answerable, but that is not a persistent knowledge base - it is one-time context (rung 1). A true knowledge base (state C) persists across every chat in the container and can hold more than one prompt could. When you demonstrate, say which you did: a persistent store, or a one-time paste.

## Reproduce it (5 minutes)
1. Native: ask probe 113, then probe 114, in a plain chat. Expect two "I do not know".
2. Core only: install STAMP.md in the instructions slot; ask both. Expect SCOTT, then "I do not know".
3. Core + knowledge: add The story of STAMP.md to the container's knowledge; ask both. Expect SCOTT, then the sourced Craft answer.
Record the three states. The B-to-C change is your RAG demonstration, on your own deployment, measured rather than promised.
