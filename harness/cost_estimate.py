#!/usr/bin/env python3
"""
Programme cost estimate, built from MEASURED token usage in pilot_out/, not guesses.

Measured 2026-08-29 across 598 graded draws:
  generation output   226 tokens mean (nemotron 254-270, luna 311, all light reasoners)
  generation input    ~150 native, ~880 stamped (the v1.70 core is 726 tokens)
  grading input       ~1500 (criterion + question + response capped at 6000 chars)
  grading output      ~120 (a short JSON object)

Heavy reasoners are budgeted separately: seed-2-1-turbo was observed spending the
entire 4096-token budget on reasoning alone, so it gets 4x the output allowance.
"""
PRICE = {   # $ per 1M tokens, verified on OpenRouter 2026-08-28/29
    "nvidia/nemotron-3.5-lightning": (0.08, 0.20),
    "bytedance-seed/seed-2-1-turbo": (0.50, 2.50),
    "openai/gpt-5.6-luna":           (0.20, 1.20),
    "z-ai/glm-5.3":                  (1.40, 4.40),
    "qwen/qwen3.5-9b":               (0.10, 0.15),
    "allenai/olmo-3-7b-instruct":    (0.10, 0.20),   # ESTIMATED - page did not list
    "google/gemini-3.7-flash":       (0.375, 1.875),
    "x-ai/grok-4.6":                 (2.00, 6.00),
}
HEAVY = {"bytedance-seed/seed-2-1-turbo", "z-ai/glm-5.3"}   # observed heavy reasoning

GEN_IN, GEN_OUT = 150, 226
GRD_IN, GRD_OUT = 1500, 120

def gen_cost(model, n, stamped=False):
    pi, po = PRICE[model]
    tin = (880 if stamped else GEN_IN)
    tout = GEN_OUT * (4 if model in HEAVY else 1)
    return n * (tin*pi + tout*po) / 1e6

def grade_cost(model, n):
    pi, po = PRICE[model]
    tout = GRD_OUT * (4 if model in HEAVY else 1)
    return n * (GRD_IN*pi + tout*po) / 1e6

ITEMS, DRAWS = 63, 10
CANDIDATES = ["nvidia/nemotron-3.5-lightning", "bytedance-seed/seed-2-1-turbo",
              "openai/gpt-5.6-luna", "z-ai/glm-5.3"]
ANCHORS    = ["qwen/qwen3.5-9b", "allenai/olmo-3-7b-instruct"]
PANEL      = ["google/gemini-3.7-flash", "x-ai/grok-4.6", "bytedance-seed/seed-2-1-turbo"]
TIER1      = "google/gemini-3.7-flash"

n = ITEMS * DRAWS
rows, total = [], 0.0
print(f"{'component':<44}{'draws':>7}{'cost':>9}")
print("-"*62)
for m in CANDIDATES + ANCHORS:
    c = gen_cost(m, n)
    total += c; rows.append((m, n, c))
    print(f"  generate  {m:<32}{n:>7}{c:>9.2f}")
g1 = grade_cost(TIER1, n*len(CANDIDATES+ANCHORS))
total += g1
print(f"  grade     tier 1, {TIER1:<23}{n*6:>7}{g1:>9.2f}")
gp = sum(grade_cost(j, int(n*6*0.20)) for j in PANEL)
total += gp
print(f"  grade     panel of 3 on 20% sample{'':<10}{int(n*6*0.20)*3:>7}{gp:>9.2f}")
print("-"*62)
print(f"{'NATIVE ARM, ALL SIX MODELS':<51}{total:>9.2f}")

# the two extra arms, run only where native discriminates (~30 of 63 items)
disc = 30
extra = 0.0
for label, stamped in [("naive control", True), ("STAMP v1.70", True)]:
    c = sum(gen_cost(m, disc*DRAWS, stamped) for m in CANDIDATES)
    c += grade_cost(TIER1, disc*DRAWS*len(CANDIDATES))
    extra += c
    print(f"  {label:<49}{c:>9.2f}")
print("-"*62)
print(f"{'FULL FIRST REPORT':<51}{total+extra:>9.2f}")
print()
print(f"  weekly monitor thereafter (30 items, 3 draws, 6 models):  ~${total*0.09:.2f}")
print(f"  preflight should require 1.5x -> have at least ${(total+extra)*1.5:.0f} on the key")
