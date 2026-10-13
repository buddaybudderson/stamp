#!/usr/bin/env python3
"""Suggest plainer wording for a draft. It never rewrites a file.

Adapted from humanize.py in Budday Budderson Studio's book "I Make Because We Make"
(Sep 2026), where it fixed the assembled book mechanically. Here it only reports:
a person reads each suggestion and decides. Three things are never touched:
  - text inside quotation marks (what a source said stays as the source said it),
  - issued and frozen pages (source.html, /record/, /protocol/, issued documents),
  - code, tables of measured figures, and dates (the house gate owns those).

Usage:
  python tools/humanize.py draft.html            # suggestions for one draft
  python tools/humanize.py draft.md --json       # machine-readable, for the reviewer pass
"""
import html, json, re, sys, pathlib

FROZEN = ("source.html", "docs/record/", "docs/protocol/", "docs/bench/no-1-complaint/")

# (pattern, plainer wording, why). Most come from the book's PHRASES list; a few are ours.
PHRASES = [
    (r"\bwhich is to say\b", "that is", "throat-clearing"),
    (r"\bthe whole point\b", "the point", "inflation"),
    (r"\bquietly\b", "(cut)", "hedge-intensifier"),
    (r"\bgenuinely\b", "(cut)", "hedge-intensifier"),
    (r"\btruly\b", "(cut)", "hedge-intensifier"),
    (r"\barguably\b", "(cut, or say who argues it)", "unowned hedge"),
    (r"\bIt is worth (?:noting|saying|stating) that\b", "(cut; state it)", "throat-clearing"),
    (r"\bIn the end, ", "(cut)", "stock connective"),
    (r"\ba kind of\b", "a", "hedge"),
    (r"\bnot merely\b", "not only", "inflation"),
    (r"\bThe result\? ", "(cut; state the result)", "rhetorical device"),
    (r"\bin today's\b", "now / in 2026", "filler"),
    (r"\bnuanced\b", "careful", "AI-favoured adjective"),
    (r"\bintricate\b", "detailed", "AI-favoured adjective"),
    (r"\bmeticulous(?:ly)?\b", "careful", "AI-favoured adjective"),
    (r"\brobust\b", "sturdy / tested (say how)", "AI-favoured adjective"),
    (r"\bseamless(?:ly)?\b", "smooth", "AI-favoured adjective"),
    (r"\bcrucial\b", "essential / say why", "AI-favoured adjective"),
    (r"\bpivotal\b", "decisive", "AI-favoured adjective"),
    (r"\bvibrant\b", "lively", "AI-favoured adjective"),
    (r"\bcomprehensive\b", "full (say what it covers)", "AI-favoured adjective"),
    (r"\bleverag(?:e|es|ed|ing)\b", "use", "jargon"),
    (r"\bfoster(?:s|ed|ing)?\b", "encourage", "jargon"),
    (r"\belevate(?:s|d)?\b", "raise", "jargon"),
    (r"\bempower(?:s|ed|ing)?\b", "enable / let", "jargon"),
    (r"\bunlock(?:s|ed|ing)?\b", "open", "jargon"),
    (r"\bharness the\b", "use the", "jargon"),
    (r"\bnavigat(?:e|es|ing) the\b", "handle the", "jargon"),
    (r"\bembark(?:s|ed|ing)? on\b", "begin", "jargon"),
    (r"\bdelve\b", "look", "AI-favoured verb"),
    (r"\bat its core\b", "at bottom", "inflation"),
    (r"\bat the heart of\b", "at the center of", "inflation"),
    (r"\bserves as\b", "is", "inflated copula"),
    (r"\bstands as\b", "is", "inflated copula"),
    (r"\ba testament to\b", "proof of", "inflation"),
    (r"\bever-evolving\b", "changing", "filler"),
    (r"\bcutting-edge\b", "new (say how new)", "filler"),
    (r"\btransformative\b", "large (measure it)", "unmeasured claim"),
    (r"\bgame-chang(?:er|ing)\b", "decisive", "unmeasured claim"),
    (r"\b(?:landscape|journey|paradigm|synergy|holistic|tapestry)\b", "(name the actual thing)", "abstract noun"),
    (r"\bIt's not about\b", "It is not", "negative framing"),
    (r"\b(?:Moreover|Furthermore|Additionally|Ultimately|In conclusion|In summary), ", "(cut)", "stock connective"),
    (r"\bHere's the thing[:.] ", "(cut)", "throat-clearing"),
    (r"\b[Tt]he truth is[,:] ", "(cut)", "throat-clearing"),
    (r"\bLet that sink in\.", "(cut)", "throat-clearing"),
    (r"\bnot (?:only|just)\b[^.]{0,60}\bbut\b", "(say both plainly, in two sentences)", "checklist 2: not-only-but"),
    (r"\b(?:It|That|This) (?:is|was) not [^.;]{1,50}[;.] (?:It|That|This) (?:is|was)\b", "(say what it is; drop the foil)", "checklist 3: negative parallelism"),
    (r"(?:^|[.!?]\s+)Enter [A-Z]\w+\.", "(introduce it in a sentence)", "'Enter X.' device"),
    (r"\b(?:colour|centre|judgement|whilst|organisation|recognise|towards)\b", "American spelling", "house style is American"),
]


def visible(path):
    t = pathlib.Path(path).read_text(encoding="utf-8")
    if path.lower().endswith((".html", ".htm")):
        t = re.sub(r"<(style|script|pre|code)\b.*?</\1>", " ", t, flags=re.S | re.I)
        t = re.sub(r"<(p|h[1-6]|li|td|th|div|section|br)\b[^>]*>", "\n", t)
        t = html.unescape(re.sub(r"<[^>]+>", "", t))
    else:
        t = re.sub(r"```.*?```", " ", t, flags=re.S)
    return t


def unquoted(text):
    """Blank out quotations so a source's words are never 'corrected'."""
    blank = lambda m: " " * len(m.group(0))
    text = re.sub(r"“[^”]{0,600}”", blank, text)
    text = re.sub(r"(?<![\w])\"[^\"\n]{0,600}\"", blank, text)
    return re.sub(r"^>.*$", blank, text, flags=re.M)


def suggest(path):
    p = str(path).replace("\\", "/")
    if any(f in p for f in FROZEN):
        return [{"note": "frozen or issued page: no suggestions are made here"}]
    raw = visible(path)
    text = unquoted(raw)
    out = []
    for pat, plain, why in PHRASES:
        for m in re.finditer(pat, text):
            line = text.count("\n", 0, m.start()) + 1
            ctx = raw[max(0, m.start() - 50):m.end() + 50].replace("\n", " ").strip()
            out.append({"line": line, "found": m.group(0).strip(), "try": plain, "why": why, "context": ctx})
    words = max(1, len(text.split()))
    dashes = text.count("—")
    if dashes:
        out.append({"found": f"{dashes} em dashes", "try": "comma, colon or parentheses; none is the target", "why": "checklist 1"})
    semis = text.count(";") * 1000 / words
    if semis > 7:
        out.append({"found": f"{semis:.1f} semicolons per 1,000 words", "try": "split the longest into sentences; about 7 is the book's rate", "why": "one voice"})
    for m in re.finditer(r"\bI (?=\w)", text):
        out.append({"found": "first-person 'I'", "try": "we (the house voice), unless Lawrence Ho is speaking in his own name", "why": "voice", "context": raw[max(0, m.start() - 40):m.end() + 40].replace("\n", " ")})
        break
    return out


def main(argv):
    if not argv:
        print(__doc__); return 2
    as_json = "--json" in argv
    for path in [a for a in argv if not a.startswith("--")]:
        found = suggest(path)
        if as_json:
            print(json.dumps({"file": path, "suggestions": found}, ensure_ascii=False, indent=1)); continue
        print(f"{path}: {len(found)} suggestion(s). Nothing was changed; a person decides each one.")
        for s in found:
            where = f"line {s['line']}: " if "line" in s else ""
            print(f"  {where}{s.get('found', '')!s} -> {s.get('try', s.get('note', ''))}  [{s.get('why', '')}]")
            if s.get("context"):
                print(f"      …{s['context']}…")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
