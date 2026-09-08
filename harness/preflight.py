#!/usr/bin/env python3
"""
Preflight gate. Refuses to start a run whose preconditions are not met.

WHY THIS IS CODE AND NOT A CHECKLIST. A rule a human has to remember is not a rule.
Two runs were lost on 2026-08-28 to an exhausted credit balance, and a third was
nearly lost to a machine that could have slept. Neither was a knowledge problem -
both were remembering problems. Checks that can be automated must be.

Designed for two callers:
  1. pilot_native.py  - imported, runs before the first API call
  2. an agent loop    - `python scripts/preflight.py` exits 0 (go) or 1 (stop),
                        so it can sit in a graph as a blocking gate node

Stdlib only.
"""
import ctypes, json, os, platform, sys, urllib.request, urllib.error

# Per-DRAW token cost, measured across 598 graded draws on 2026-08-29:
#   generation  ~150 in (880 if stamped) / 226 out
#   grading     ~1500 in / 120 out
# The first version of this file guessed 900 output tokens per call and was ~5x too
# conservative, which would have blocked runs that could afford to proceed.
TOK_IN, TOK_OUT = 1650, 350          # one generation + one grading
HEAVY_MULT = 4.0                      # heavy reasoners (seed, glm) emit far more
SAFETY = 1.5                          # require 1.5x the estimate before starting


def _get(url, key, timeout=30):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------------------------------------------------------- checks
HEAVY = ("seed-2-1", "glm-5", "grok-4")   # reasoners that emit several times the mean


def check_credit(base, key, n_calls, models, model_calls=None):
    """Balance versus estimated cost. This is the check that has actually failed.

    TWO COST SHAPES, and conflating them overestimated a panel run by 2.4x on
    2026-08-29, blocking a run that could easily afford to proceed.

      UNIFORM (pilot_native.py)  n_calls = DRAWS, and every draw hits every model
          once: one generation, one grading. Summing the per-model prices and
          multiplying by n_calls is correct.
      SPLIT (panel_grade.py)  148 draws go to gemini AND 148 go to grok. That is
          296 calls, but it is NOT 296 x (gemini + grok). Pass model_calls=
          {slug: n} and each model is priced against its own call count.

    HEAVY_MULT is also applied per model rather than to the whole sum. Grok being a
    heavy reasoner is no reason to quadruple Gemini's bill.
    """
    try:
        d = _get(f"{base}/credits", key)["data"]
        total, used = float(d.get("total_credits", 0)), float(d.get("total_usage", 0))
        avail = total - used
    except Exception as e:
        return None, f"could not read credit balance ({type(e).__name__}) - continuing blind"

    counts = model_calls or {m: n_calls for m in models}
    est, detail = 0.0, []
    try:
        allm = {m["id"]: m for m in _get(f"{base}/models", key)["data"]}
        for slug, n in counts.items():
            p = allm.get(slug, {}).get("pricing", {})
            per = float(p.get("prompt", 0)) * TOK_IN + float(p.get("completion", 0)) * TOK_OUT
            if any(k in slug for k in HEAVY):
                per *= HEAVY_MULT
            est += per * n
            detail.append(f"{slug.split('/')[-1]} {n}x${per:.4f}")
    except Exception:
        est = 0.0025 * sum(counts.values())      # fallback: conservative per-call guess
        detail = ["live prices unavailable, using $0.0025/call"]

    ok = avail >= est * SAFETY
    msg = (f"credit ${avail:,.2f} available, ~${est:,.2f} estimated "
           f"(needs ${est * SAFETY:,.2f} with {SAFETY}x margin)  [{', '.join(detail)}]")
    return ok, msg


def check_power():
    """AC power. A run on battery is a run that may not finish."""
    if platform.system() != "Windows":
        return None, "power state not checked (not Windows)"

    class S(ctypes.Structure):
        _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                    ("BatteryLifePercent", ctypes.c_byte), ("SystemStatusFlag", ctypes.c_byte),
                    ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
    st = S()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(st)):
        return None, "power state unreadable"
    ac = st.ACLineStatus
    if ac == 1:
        return True, "plugged in (AC)"
    if ac == 0:
        pct = st.BatteryLifePercent
        return False, f"ON BATTERY ({pct}%) - plug in before a long run"
    return None, "power state unknown (desktop?)"


def check_slugs(base, key, models):
    """A dead slug fails every call. Catch it before spending anything."""
    try:
        live = {m["id"] for m in _get(f"{base}/models", key)["data"]}
    except Exception as e:
        return None, f"could not fetch the model list ({type(e).__name__})"
    missing = [m for m in models if m and m not in live]
    if missing:
        return False, "NOT ON OPENROUTER: " + ", ".join(missing)
    return True, f"all {len(models)} slugs live: " + ", ".join(models)


def check_smoke(base, key, model, pin=None, timeout=45):
    """One tiny real call. Catches an endpoint that accepts the request and then
    never answers - which a slug check cannot see, because the slug is live; it is
    the pinned PROVIDER that is dead. Without this, a hung first call grinds through
    4 retries x 180s before reporting anything."""
    body = {"model": model, "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 8, "temperature": 0}
    if pin:
        body["provider"] = pin
    req = urllib.request.Request(
        f"{base}/chat/completions", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    import time as _t
    t0 = _t.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode())
        who = d.get("provider", "?")
        return True, f"{model} answered in {_t.time()-t0:.1f}s via {who}"
    except urllib.error.HTTPError as e:
        return False, f"{model} -> HTTP {e.code}: {e.read()[:120].decode('utf-8','replace')}"
    except Exception as e:
        hint = " - the PIN is probably wrong; drop STAGE1_PROVIDER" if pin else ""
        return False, f"{model} did not answer within {timeout}s ({type(e).__name__}){hint}"


# ---------------------------------------------------------------- gate
def preflight(base, key, models, n_calls, strict=True, pin=None, model_calls=None):
    """Return True to proceed. Prints a report either way.

    model_calls: {slug: n} when different models get different numbers of calls.
    Omit it when every unit of work hits every model once."""
    base = base.rstrip("/")
    results = [
        ("slugs  ", check_slugs(base, key, models)),
        ("credit ", check_credit(base, key, n_calls, models, model_calls)),
        ("power  ", check_power()),
        ("smoke  ", check_smoke(base, key, models[0], pin) if models else (None, "no model")),
    ]
    print("=" * 66)
    print("PREFLIGHT")
    print("=" * 66)
    blocked = []
    for name, (ok, msg) in results:
        mark = {True: "  ok  ", False: " STOP ", None: " warn "}[ok]
        print(f"  [{mark}] {name} {msg}")
        if ok is False:
            blocked.append(name.strip())

    if blocked and strict:
        print("-" * 66)
        print(f"BLOCKED on: {', '.join(blocked)}")
        if "power" in blocked:
            print("\n  Plug the machine in, then also stop it sleeping mid-run:")
            print("    powercfg /change standby-timeout-ac 0")
            print("    powercfg /change monitor-timeout-ac 0")
            print("  (afterwards:  powercfg /change standby-timeout-ac 30)")
        if "smoke" in blocked:
            print("\n  The model accepted no request. If you pinned a provider, that")
            print("  provider probably cannot serve this model right now:")
            print("    Remove-Item Env:\\STAGE1_PROVIDER")
            print("  Run unpinned once, read 'serving providers seen:', then pin that one.")
        if "credit" in blocked:
            print("\n  Top up at https://openrouter.ai/settings/credits")
            print("  Note: each call RESERVES its full max_tokens budget up front,")
            print("  so you need more balance available than the run will actually use.")
        print("-" * 66)
        return False

    print("-" * 66)
    print("PREFLIGHT PASSED" if not blocked else "PREFLIGHT PASSED WITH WARNINGS")
    print("-" * 66)
    return True


if __name__ == "__main__":
    # standalone gate for an agent loop: exit 0 = go, exit 1 = stop
    base   = os.environ.get("STAGE1_BASE_URL", "https://openrouter.ai/api/v1")
    key    = os.environ.get("STAGE1_API_KEY", "")
    models = [m for m in (os.environ.get("STAGE1_MODEL"), os.environ.get("GRADER_MODEL")) if m]
    n      = int(os.environ.get("PREFLIGHT_CALLS") or 630)
    if not key:
        sys.exit("PREFLIGHT: STAGE1_API_KEY is empty")
    sys.exit(0 if preflight(base, key, models, n) else 1)
