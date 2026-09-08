#!/usr/bin/env python3
"""
Shared statistics. One implementation, used by every script that publishes a number.

TWO QUESTIONS, TWO INTERVALS, AND THEY ARE NOT INTERCHANGEABLE. Getting this wrong
in either direction is easy; this file exists because it was got wrong in both
directions on 2026-08-29 within an hour.

  ON THE BANK - "nemotron fails 43.3% on bank v1."
      The bank is 63 deliberately chosen items. It is not a random sample of
      anything; it is the instrument. Only the DRAWS are random. Crucially, 38 of
      those 63 items are deterministic - the model fails them 0/10 or 10/10 - and a
      deterministic item contributes EXACTLY ZERO sampling variance.
      Var = (1/N^2) * sum_i m_i * p_i(1-p_i)
      This is the interval for week-on-week comparison, because the bank is fixed.
      It is NARROW, and correctly so - that narrowness is what makes a time series
      able to detect real movement.

  BEYOND THE BANK - "nemotron fails about 43% on probes like these."
      Now the choice of items is itself a source of uncertainty, because you are
      generalising past the 63. Resample ITEMS with replacement.
      This is the interval for any claim about models in general, or any comparison
      between models that is meant to hold beyond this bank. It is WIDE.

  THE NAIVE INTERVAL answers neither. On the real nemotron data it is 1.85x too
  WIDE for the first question - because it charges sampling variance for the 38
  deterministic items that have none - and 2.6x too NARROW for the second, because
  it ignores item choice entirely. Being wrong in both directions at once is what a
  statistic looks like when nobody has said what it is estimating.

Rule for reports: state which question a number answers, or do not publish it.
"""
import collections, math, random, statistics as st


def per_item_from_rows(rows):
    """rows: iterable of dicts with item_id and verdict. -> {item_id: [1/0, ...]}"""
    d = collections.defaultdict(list)
    for r in rows:
        if r.get("verdict") in ("PASS", "FAIL"):
            d[r["item_id"]].append(1 if r["verdict"] == "FAIL" else 0)
    return dict(d)


def se_on_bank(per_item):
    """Draw sampling only, items held fixed. Deterministic items add no variance."""
    sizes = [len(v) for v in per_item.values()]
    N = sum(sizes)
    if not N:
        return 0.0
    var = sum(m * (sum(v)/m) * (1 - sum(v)/m) for m, v in zip(sizes, per_item.values()))
    return math.sqrt(var) / N


def ci_beyond_bank(per_item, conf=0.95, iters=4000, seed=20260829):
    """Percentile bootstrap resampling ITEMS - the unit you are generalising over."""
    items = list(per_item.values())
    k = len(items)
    if k < 3:
        return None, None                 # a bootstrap over two things is theatre
    rnd = random.Random(seed)
    out = []
    for _ in range(iters):
        draws = []
        for _ in range(k):
            draws.extend(items[rnd.randrange(k)])
        if draws:
            out.append(sum(draws) / len(draws))
    out.sort()
    return (out[int((1 - conf) / 2 * len(out))],
            out[min(len(out) - 1, int((1 - (1 - conf) / 2) * len(out)))])


def icc_deff(per_item):
    """ICC and design effect. Explanatory only - they say WHY the beyond-bank
    interval is wide, in a number a reader can argue with. Unequal cluster sizes
    use the corrected mean size, not the plain average."""
    sizes = [len(v) for v in per_item.values()]
    k, M = len(sizes), sum(sizes)
    if k < 2 or M <= k:
        return 0.0, 1.0, float(M)
    rates = [sum(v) / len(v) for v in per_item.values()]
    m_a = (M - sum(s * s for s in sizes) / M) / (k - 1)
    within = st.mean([r * (1 - r) for r in rates])
    between = max(0.0, st.pvariance(rates) - (within / m_a if m_a else 0))
    icc = between / (between + within) if (between + within) > 0 else 0.0
    deff = 1 + (m_a - 1) * icc
    return icc, deff, (M / deff if deff else float(M))


def rate(per_item, conf=0.95):
    sizes = [len(v) for v in per_item.values()]
    N, k = sum(sizes), len(sizes)
    if not N:
        return None
    rates = [sum(v) / len(v) for v in per_item.values()]
    mean = sum(sum(v) for v in per_item.values()) / N
    icc, deff, n_eff = icc_deff(per_item)
    se_b = se_on_bank(per_item)
    z = 1.959964
    lo_g, hi_g = ci_beyond_bank(per_item, conf)
    return {
        "n_draws": N, "n_items": k,
        "mean_over_draws": mean, "mean_over_items": st.mean(rates),
        "sd_across_items": st.stdev(rates) if k > 1 else 0.0,
        "median_item_rate": st.median(rates),
        "at_floor_or_ceiling": sum(1 for r in rates if r in (0.0, 1.0)),
        "probabilistic": sum(1 for r in rates if 0.2 <= r <= 0.8),
        # question 1: this model, this bank. Use for week-on-week.
        "se_on_bank": se_b,
        "on_bank_low": max(0.0, mean - z * se_b),
        "on_bank_high": min(1.0, mean + z * se_b),
        # question 2: generalising past these 63 items.
        "beyond_bank_low": lo_g, "beyond_bank_high": hi_g,
        # explanatory
        "icc": icc, "design_effect": deff, "n_effective": n_eff,
        "se_naive": math.sqrt(max(mean * (1 - mean), 1e-12) / N),
        "conf": conf,
    }


def fmt(r, scope="bank"):
    """One quotable line. `scope` MUST be stated - that is the whole point."""
    if not r:
        return "no data"
    if scope == "bank":
        return (f"{r['mean_over_draws']:.1%} "
                f"[{r['on_bank_low']:.1%}, {r['on_bank_high']:.1%}] on bank v1 "
                f"({r['n_items']} items, {r['n_draws']} draws)")
    if r["beyond_bank_low"] is None:
        return f"{r['mean_over_draws']:.1%} (too few items to generalise)"
    return (f"{r['mean_over_draws']:.1%} "
            f"[{r['beyond_bank_low']:.1%}, {r['beyond_bank_high']:.1%}] "
            f"generalising beyond the bank")


def explain(r, indent="    "):
    if not r:
        return indent + "no data"
    g = ("not estimable" if r["beyond_bank_low"] is None else
         f"[{r['beyond_bank_low']:.1%}, {r['beyond_bank_high']:.1%}]")
    return "\n".join([
        f"{indent}rate {r['mean_over_draws']:.1%}   "
        f"({r['n_items']} items, {r['n_draws']} draws, "
        f"{r['at_floor_or_ceiling']} of them deterministic)",
        f"{indent}  ON bank v1, week-on-week   "
        f"[{r['on_bank_low']:.1%}, {r['on_bank_high']:.1%}]   "
        f"<- use this to compare runs",
        f"{indent}  BEYOND the bank            {g}   "
        f"<- use this for claims about the model",
        f"{indent}  (naive interval would say "
        f"[{max(0,r['mean_over_draws']-1.96*r['se_naive']):.1%}, "
        f"{r['mean_over_draws']+1.96*r['se_naive']:.1%}] - answers neither question)",
        f"{indent}  SD across items {r['sd_across_items']:.3f}   ICC {r['icc']:.2f}   "
        f"design effect {r['design_effect']:.1f}x",
    ])
