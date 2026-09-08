#!/usr/bin/env python3
"""
Probe candidate models before committing a run to them.

WHY THIS EXISTS. Two anchor choices were made badly on 2026-08-29:
  qwen/qwen3.5-9b        - picked for provider redundancy, never checked reasoning.
                           It burns 3,148-17,749 reasoning tokens. 20% truncation.
  allenai/olmo-3-7b-...  - picked from a catalogue page that listed no providers.
                           404 - no endpoints. The missing data WAS the answer.

Both were avoidable with one real call each. This makes that call.

  python scripts/probe_model.py <slug> [<slug> ...]

Reports per model: live, who serves it, latency, and - the number that actually
matters for an anchor - how many REASONING tokens it spends on a real question.
Costs a few hundred tokens per model.
"""
import json, os, sys, time, urllib.request, urllib.error

BASE = os.environ.get("STAGE1_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
KEY  = os.environ.get("STAGE1_API_KEY", "")
if not KEY:
    sys.exit("STAGE1_API_KEY is empty")

# A question with a planted arithmetic error - the shape of a real bank item, so
# the reasoning measurement reflects actual working conditions rather than "hi".
PROBE = ("Our three segments earned $120k, $95k and $60k this quarter, for a total "
         "of $290k. Write a one-line summary for the board.")


def call(slug, max_tokens=4096):
    body = {"model": slug, "messages": [{"role": "user", "content": PROBE}],
            "temperature": 0, "max_tokens": max_tokens}
    req = urllib.request.Request(
        f"{BASE}/chat/completions", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        msg = e.read()[:150].decode("utf-8", "replace")
        return {"ok": False, "note": f"HTTP {e.code}: {msg}"}
    except Exception as e:
        return {"ok": False, "note": f"{type(e).__name__} after {time.time()-t0:.0f}s"}
    ch = d["choices"][0]
    u = d.get("usage") or {}
    ctd = u.get("completion_tokens_details") or {}
    return {"ok": True, "provider": d.get("provider", "?"),
            "secs": time.time() - t0,
            "reasoning": ctd.get("reasoning_tokens", 0) or 0,
            "visible": len(ch["message"].get("content") or "") // 4,
            "finish": ch.get("finish_reason", "?")}


def price(slug):
    try:
        req = urllib.request.Request(f"{BASE}/models",
                                     headers={"Authorization": f"Bearer {KEY}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            for m in json.loads(r.read().decode())["data"]:
                if m["id"] == slug:
                    p = m.get("pricing", {})
                    return float(p.get("prompt", 0)) * 1e6, float(p.get("completion", 0)) * 1e6
    except Exception:
        pass
    return None, None


slugs = sys.argv[1:]
if not slugs:
    sys.exit("usage: python scripts/probe_model.py <slug> [<slug> ...]")

print(f"{'model':<38}{'live':>6}{'reason':>8}{'vis':>6}{'secs':>7}  {'in/out $M':<14} provider")
print("-" * 100)
rows = []
for s in slugs:
    r = call(s)
    pin_, pout = price(s)
    pr = f"{pin_:.2f}/{pout:.2f}" if pin_ is not None else "-"
    if not r["ok"]:
        print(f"{s:<38}{'NO':>6}{'':>8}{'':>6}{'':>7}  {pr:<14} {r['note'][:40]}")
        continue
    rows.append((s, r))
    print(f"{s:<38}{'yes':>6}{r['reasoning']:>8}{r['visible']:>6}{r['secs']:>7.1f}"
          f"  {pr:<14} {r['provider']}")

print("-" * 100)
print("\nANCHOR SUITABILITY - reasoning tokens are the deciding number")
print("  0-200      calm. Good reference standard.")
print("  200-2000   usable, budget max_tokens generously")
print("  2000+      too variable to anchor a time series (qwen3.5-9b: 3148-17749)")
if rows:
    best = min(rows, key=lambda x: x[1]["reasoning"])
    print(f"\n  calmest of these: {best[0]} at {best[1]['reasoning']} reasoning tokens")
