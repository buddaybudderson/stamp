#!/usr/bin/env python3
"""
Merge the three probe files into bank v1 and assign the public/held-out split.

  pilot_v1.jsonl        35  v1.25 discriminating probes (17 intact, 18 rebuilt)
  provenance_v1.jsonl   15  the book-quote ladder T1/T2/T4/T5
  attribution_v1.jsonl  13  misattributed quotes, DOI citations, URL access
  --------------------------------------------------------------------------
                        63

HOLDOUT SPLIT. Half of every category is held back and never published - not the
text, not in a public repo, not in an appendix. Only aggregate scores are released.
When a model's public-half score and held-out-half score diverge, that is the
contamination alarm. The rule is deterministic so it can be audited without seeing
the held-out items: sort by item_id within category, alternate starting with public.
"""
import json, pathlib, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
BANK = ROOT / "bank"
OUT  = BANK / "bank_v1.jsonl"

SRC = [("pilot_v1.jsonl", "v125"), ("provenance_v1.jsonl", "ladder"),
       ("attribution_v1.jsonl", "attribution")]

rows = []
for fname, origin in SRC:
    for line in (BANK / fname).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get("status") == "curator_todo":
            continue                                  # the empty T3 slot
        rows.append({
            "item_id": d["item_id"],
            "bank_version": "v1",
            "category": d["category"],
            "origin": origin,
            "holdout": None,                          # assigned below
            "status": d.get("status", "new"),
            "messages": d["messages"],
            "context": d.get("context"),
            "pass_criterion": d["pass_criterion"],
            "ground_truth": d.get("ground_truth", ""),
            "truth_source": d.get("truth_source", ""),
            "tags": d.get("tags", []),
            "tier": d.get("tier", d.get("subtype", "")),
            "run_condition": d.get("run_condition", ""),
            "v125": d.get("v125"),
            "native_fail_rate": None,
            "provenance": d.get("provenance", {}),
        })

# deterministic stratified split: within each category, sort by id and alternate
bycat = collections.defaultdict(list)
for r in rows:
    bycat[r["category"]].append(r)
for cat in bycat:
    for i, r in enumerate(sorted(bycat[cat], key=lambda x: x["item_id"])):
        r["holdout"] = bool(i % 2)

rows.sort(key=lambda r: (r["category"], r["item_id"]))

# ---- validation ------------------------------------------------------------
seen = set()
for r in rows:
    assert r["item_id"] not in seen, f"duplicate id {r['item_id']}"
    seen.add(r["item_id"])
    assert r["messages"] and r["messages"][-1]["role"] == "user", r["item_id"]
    assert len(r["pass_criterion"]) > 20, r["item_id"]
    assert r["holdout"] in (True, False)

OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

# public copy - safe to commit to a public repo
pub = [r for r in rows if not r["holdout"]]
(BANK / "bank_v1_public.jsonl").write_text(
    "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in pub), encoding="utf-8")

print(f"bank v1: {len(rows)} items -> {OUT.name}")
print(f"  public {len(pub)}   held out {len(rows)-len(pub)}")
print(f"  public copy -> bank_v1_public.jsonl  (safe to publish)")
print()
print(f"{'category':<30}{'n':>4}{'public':>8}{'held':>6}   origin")
print("-" * 62)
for cat in sorted(bycat):
    v = bycat[cat]
    p = sum(1 for r in v if not r["holdout"])
    origins = ",".join(sorted({r["origin"] for r in v}))
    print(f"{cat:<30}{len(v):>4}{p:>8}{len(v)-p:>6}   {origins}")
print("-" * 62)
print(f"{'TOTAL':<30}{len(rows):>4}{len(pub):>8}{len(rows)-len(pub):>6}")
print()
print("multi-turn items:", sum(1 for r in rows if len(r["messages"]) > 1))
print("items with ground truth recorded:", sum(1 for r in rows if r["ground_truth"]))
print("never piloted (new categories):", sum(1 for r in rows if r["origin"] != "v125"))
