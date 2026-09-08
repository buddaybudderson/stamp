#!/usr/bin/env python3
"""
What do we have, and what can we honestly say with it?

    python scripts/inventory.py

Reads every pilot_out/*.jsonl and classifies it. No network, no cost. Run it
before writing any report, and before quoting any number to anybody.

THE FOUR DISQUALIFIERS, each of which has already spoiled a real run here:

  truncation   >=5% of draws hitting max_tokens. Not random - qwen truncated
               07_live_data_109 five times out of five, so the hardest items
               dropped out of the sample and the score improved by losing them.
  provider     more than one serving provider in one file. Published work puts
               backend choice at up to 16.6pp on identical benchmarks, so a
               multi-provider file measures the router, not the model.
  attrition    >=5% of draws with no usable verdict for any other reason.
  incomplete   fewer draws on disk than the design calls for.

COMPARABILITY is checked separately and matters just as much. Two candidates
measured under different max_tokens, different draw counts, different banks or
different graders cannot be put in the same table, however clean each one is.
"""
import collections, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT  = ROOT / "pilot_out"

DESIGN = {"bank": "bank_v1.jsonl", "draws": 5, "items": 63}
LADDER = ["nemo_v1", "luna_v1", "seed_v1", "glm_v1"]     # the price ladder
TRUNC_LIMIT = 0.05
ATTRITION_LIMIT = 0.05


def load(f):
    latest, prov, mt = {}, collections.Counter(), collections.Counter()
    rows = 0
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            rows += 1
            latest[(r["item_id"], r["draw"])] = r          # last write wins
            if r["verdict"] in ("PASS", "FAIL"):           # only count real attempts
                prov[r.get("served_by", "?")] += 1
            mt[r.get("max_tokens", "?")] += 1
    cfg = f.with_suffix(".config.json")
    return (latest, prov, mt, rows,
            json.loads(cfg.read_text(encoding="utf-8")) if cfg.exists() else {})


def assess(f):
    latest, prov, mt, rows, cfg = load(f)
    if not latest:
        return None
    c = collections.Counter(r["verdict"] for r in latest.values())
    n = len(latest)
    ok = c["PASS"] + c["FAIL"]
    items = len({k[0] for k in latest})
    draws = sorted({k[1] for k in latest})

    # ERROR IS NOT ATTRITION. An ERROR draw was never successfully attempted - the
    # call failed - and the runner re-issues it on the next run. Counting it as lost
    # data marked a live run "UNUSABLE" at 37% while it was still filling in.
    # Attrition is a draw that CAME BACK and could not be used.
    outstanding = c["ERROR"]
    attempted = n - outstanding
    lost = ((attempted - ok) / attempted) if attempted else 0.0

    # REAL vs PHANTOM TRUNCATION. finish_reason="length" is supposed to mean the
    # budget ran out. Three nemotron draws reported it having emitted 1-164 visible
    # characters and ZERO reasoning tokens against a 16,384 cap, which is not a
    # budget problem - it is the serving stack aborting and mislabelling it. Lumping
    # the two together would condemn a clean run for the provider's bookkeeping.
    real_tr = phantom_tr = 0
    headroom = []
    # CONTENT FILTER IS NOT ORDINARY ATTRITION. Measured 2026-08-29: the base rate
    # across 1,610 gradings was 0.5%, but 08_safety_049 hit 9.7% and
    # 14_provenance_020 16.7% - both past Bonferroni. And the filtered responses
    # differed systematically from the graded ones: on the provenance item they
    # averaged 1,709 characters against 1,262. The filter selects on what the model
    # SAID, so the draws it removes are not a random sample of that item's draws.
    # Random loss shrinks a sample; selective loss moves the answer.
    filt = collections.Counter()
    graded_per_item = collections.Counter()
    for r in latest.values():
        used = (r.get("reasoning_tokens") or 0) + (r.get("chars") or 0) // 4
        cap = r.get("max_tokens") or 0
        if r["verdict"] != "ERROR":
            headroom.append(used)
        if r.get("grader_finish") not in (None, "-"):
            graded_per_item[r["item_id"]] += 1
            if r.get("grader_finish") == "content_filter":
                filt[r["item_id"]] += 1
        if r["verdict"] == "TRUNCATED":
            if isinstance(cap, int) and cap and used < cap * 0.5:
                phantom_tr += 1
            else:
                real_tr += 1
    trunc = (real_tr / attempted) if attempted else 0.0

    faults = []
    if trunc >= TRUNC_LIMIT:
        faults.append(f"truncation {trunc:.0%}")
    if len(prov) > 1:
        faults.append(f"{len(prov)} providers")
    if lost >= ATTRITION_LIMIT:
        faults.append(f"attrition {lost:.0%}")
    return {"file": f.name, "n": n, "ok": ok, "items": items, "draws": draws,
            "verdicts": dict(c), "prov": dict(prov), "maxtok": dict(mt),
            "cfg": cfg, "faults": faults, "fail_rate": (c["FAIL"] / ok) if ok else None,
            "running": outstanding > 0, "outstanding": outstanding,
            "trunc": trunc, "lost": lost, "phantom": phantom_tr,
            "filtered": dict(filt), "graded_per_item": dict(graded_per_item),
            "peak_used": max(headroom) if headroom else 0}


def band(a):
    if a["running"]:
        return "IN PROGRESS"        # judged when it finishes, not while it fills
    if a["faults"]:
        return "UNUSABLE"
    if a["cfg"].get("bank") != DESIGN["bank"] or a["items"] != DESIGN["items"] \
            or len(a["draws"]) != DESIGN["draws"]:
        return "OFF-DESIGN"
    return "USABLE"


rows = [a for a in (assess(f) for f in sorted(OUT.glob("pilot_*.jsonl"))
                    if f.stat().st_size) if a]
if not rows:
    sys.exit("no pilot data found")

print("=" * 92)
print("INVENTORY - every dataset on disk, and what it is good for")
print(f"design: bank {DESIGN['bank']}, {DESIGN['items']} items, {DESIGN['draws']} draws, "
      f"one pinned provider")
print("=" * 92)

groups = collections.defaultdict(list)
for a in rows:
    groups[band(a)].append(a)

for g in ("USABLE", "IN PROGRESS", "OFF-DESIGN", "UNUSABLE"):
    if g not in groups:
        continue
    print(f"\n{g}")
    print("-" * 92)
    for a in sorted(groups[g], key=lambda x: x["file"]):
        fr = f"{a['fail_rate']:.1%}" if a["fail_rate"] is not None else "-"
        print(f"  {a['file']:<32} {a['ok']:>4}/{a['n']:<4} usable   "
              f"{a['items']:>3} items x {len(a['draws'])} draws   fail {fr:>6}")
        bits = []
        if a["cfg"].get("model"):
            bits.append(f"model {a['cfg']['model']}")
        if a["cfg"].get("grader"):
            bits.append(f"grader {a['cfg']['grader']}")
        if a["cfg"].get("reconstructed"):
            bits.append("CONFIG RECONSTRUCTED - settings asserted after the fact")
        if not a["cfg"]:
            bits.append("no config file - settings unrecorded")
        if bits:
            print(f"      {'; '.join(bits)}")
        print(f"      providers {a['prov']}   max_tokens {a['maxtok']}")
        if a["outstanding"]:
            print(f"      {a['outstanding']} draws outstanding - re-issued on the next run")
        if a["filtered"]:
            n = sum(a["filtered"].values())
            print(f"      {n} CONTENT_FILTER event(s) - the grader REFUSED to judge:")
            for iid, c in sorted(a["filtered"].items(), key=lambda kv: -kv[1]):
                g = a["graded_per_item"].get(iid, 0)
                print(f"        {iid:<34} {c}/{g} gradings refused ({c/g:.0%})")
            print(f"        Selective loss, not random loss - see the pooled test below.")
        if a["phantom"]:
            print(f"      {a['phantom']} PHANTOM truncation(s): finish_reason=length with"
                  f" almost nothing emitted.")
            print(f"        Not a budget problem - the serving stack aborting and"
                  f" mislabelling it.")
        if a["faults"]:
            print(f"      DISQUALIFIED: {', '.join(a['faults'])}")

# ---------------------------------------------------------------- comparability
print("\n" + "=" * 92)
print("THE PRICE LADDER - can these four go in one table?")
print("=" * 92)
ok_rows = {a["cfg"].get("model", a["file"]): a for a in rows if band(a) == "USABLE"}
ladder = []
for cand in LADDER:
    halves = [a for a in rows if a["file"].startswith(f"pilot_{cand}_")]
    got = sum(a["ok"] for a in halves)
    want = DESIGN["items"] * DESIGN["draws"] * 2
    state = ("not started" if not halves else
             f"{got}/{want} usable draws ({got/want:.0%})")
    ladder.append((cand, halves, got, want, state))
    mark = "complete" if got >= want * 0.95 else "INCOMPLETE"
    print(f"  {cand:<12} {state:<34} {mark}")

print("\n  Instrument settings, which must match across the whole table:")
seen = collections.defaultdict(set)
for cand, halves, *_ in ladder:
    for a in halves:
        seen["max_tokens"].add(tuple(sorted(a["maxtok"])))
        seen["grader"].add(a["cfg"].get("grader", "?"))
        seen["bank"].add(a["cfg"].get("bank", "?"))
        seen["draws"].add(len(a["draws"]))
for k, v in seen.items():
    flag = "" if len(v) <= 1 else "   <-- DIFFERS ACROSS CANDIDATES"
    print(f"    {k:<12} {sorted(v, key=str)}{flag}")

# A DIFFERENCE IS ONLY A PROBLEM IF IT BOUND ANYTHING. A cap that nothing came near
# cannot have shaped the result, so settle it with the measurement rather than by
# arguing from the setting.
if len(seen["max_tokens"]) > 1:
    peak = max((a["peak_used"] for cand, halves, *_ in ladder for a in halves), default=0)
    lowest = min((c for t in seen["max_tokens"] for c in t if isinstance(c, int)),
                 default=0)
    print(f"\n    Does the max_tokens difference bind? Heaviest draw anywhere in the")
    print(f"    ladder used {peak:,} tokens against a lowest cap of {lowest:,}"
          f" - {lowest/peak:.0f}x headroom." if peak else "")
    print(f"    IMMATERIAL: no draw came close to either cap, so the two settings"
          if peak and peak < lowest * 0.5 else
          f"    MATERIAL: draws approached the lower cap - the candidates are NOT")
    print(f"    produced the same data and the candidates remain comparable."
          if peak and peak < lowest * 0.5 else
          f"    comparable until the lower-cap runs are repeated.")

# ------------------------------------------------- filter-prone items, pooled
allf, allg = collections.Counter(), collections.Counter()
for a in rows:
    allf.update(a["filtered"]); allg.update(a["graded_per_item"])
if allf:
    import math
    tot_f, tot_g = sum(allf.values()), sum(allg.values())
    base = tot_f / tot_g if tot_g else 0
    thresh = 0.05 / max(1, len(allg))
    print("\n" + "=" * 92)
    print("FILTER-PRONE ITEMS - probes the grader refuses to judge")
    print(f"  {tot_f} refusals in {tot_g} gradings = {base:.3%} base rate. An item well")
    print(f"  above that is not unlucky; the grader's filter is reading the same")
    print(f"  content the probe is testing. Bonferroni threshold p < {thresh:.1e}.")
    print("=" * 92)
    print(f"  {'item':<34}{'refused':>9}{'graded':>8}{'rate':>8}{'p':>12}   verdict")
    flagged = []
    for iid, k in allf.most_common():
        n = allg.get(iid, 0)
        if not n:
            continue
        p_ = sum(math.comb(n, i) * base**i * (1-base)**(n-i) for i in range(k, n+1))
        sig = p_ < thresh
        flagged += [iid] if sig else []
        print(f"  {iid:<34}{k:>9}{n:>8}{k/n:>8.1%}{p_:>12.1e}   "
              f"{'FILTER-PRONE' if sig else 'consistent with chance'}")
    if flagged:
        print(f"\n  {len(flagged)} item(s) cannot be reliably graded by this grader.")
        print("  Options, in order of preference:")
        print("    1. move to Tier 0 - a mechanical check needs no judge and cannot be")
        print("       refused. PANEL.md: every item out of judgment is a permanent gain.")
        print("    2. grade with a provider whose filter does not fire on it, and say so.")
        print("    3. exclude and disclose. Never leave it silently thinned.")

print("\n" + "=" * 92)
print("WHAT IS NOT MEASURED AT ALL")
print("=" * 92)
notes = []
if not (ROOT / "panel_out").exists():
    notes.append("PANEL: no tier-2 run exists. Every verdict on disk comes from ONE\n"
                 "         grader that nobody has checked. Until panel_grade.py runs,\n"
                 "         no per-item verdict should be published.")
t0 = list(OUT.glob("pilot_*_t0_*.jsonl"))
if not t0:
    notes.append("FEVER: no temperature-0 pass exists for any model, so no fever\n"
                 "         reading can be computed.")
notes.append("ANCHOR: nemotron is the anchor AND a candidate. There is no second\n"
             "         anchor, so harness drift cannot be separated from model drift.")
for n in notes:
    print(f"  - {n}")
