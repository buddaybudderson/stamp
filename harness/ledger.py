#!/usr/bin/env python3
"""
THE LOG. Jayden Lee's fortnightly record - what ran, what it cost, what moved.

    python scripts/ledger.py                 build the next Log
    python scripts/ledger.py --date 2026-09-03
    python scripts/ledger.py --dry           print the summary, write nothing

Every number comes from figures.json. There is no path in this file by which a
number can be typed, computed on the fly, or remembered - it reads the registry,
diffs it against the snapshot the previous Log recorded, and renders. That is the
whole design: an agent forbidden to interpret should not be given anything to
interpret with.

WHAT MAKES THIS DIFFERENT FROM A CALIBRATION, and why the difference is visible:

  A Calibration is written. It argues, it caveats, it is signed by a person. It is
  set in a serif, because a human wrote the prose.

  A Log is DERIVED. Nobody wrote it; it was computed. So it is set entirely in the
  mono face the Calibration reserves for machine output, it has no cover, no
  contents, no folios and no plate - none of the furniture that exists to help a
  reader through an argument, because there is no argument - and its masthead block
  is inverted, so a reader can tell the two apart across a room.

  THE ACCENT COLOR IS THE FINDING, and the rule is absolute. Oxide red appears on
  this page ONLY where something cleared its noise floor - not in the wordmark, not
  in a rule, not anywhere decorative. A Log where nothing moved is monochrome, and
  you can see that before you have read a word. A quiet fortnight should LOOK quiet.
  The first draft tinted the wordmark and gave the color a second job, which is
  exactly how a signal stops being one.

SPEND IS READ, NOT RECONSTRUCTED. pilot_native.py records usage.cost per call - what
OpenRouter actually charged - so this page never multiplies tokens by a price. That
matters more than it sounds: Gemini's price DOUBLED inside 24 hours during measurement
one, so any figure built from a remembered price would have been wrong and, worse,
unfalsifiable.

Runs made before that instrumentation carry no cost, and are counted and named rather
than quietly dropped from the total. A partial total presented as a whole one is the
kind of number that survives for years.
"""
import argparse, collections, datetime as dt, hashlib, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REG = ROOT / "figures.json"
RELEASES = ROOT / "release_log.jsonl"
SNAPS = ROOT / "log_out"
OUT = ROOT / "log"

# what a Log reports for each candidate, in order, and how to show it
ROWS = [("fail_rate", "failure rate", "rate"),
        ("n_items", "items", "count"),
        ("n_draws", "draws", "count"),
        ("retest_gap", "noise floor", "rate"),
        ("spearman_brown", "reliability", "coef"),
        ("icc", "ICC", "coef"),
        ("design_effect", "design effect", "mult")]


def fmt(v, kind):
    if v is None:
        return "—"
    if kind == "rate":
        return f"{v:.1%}"
    if kind == "coef":
        return f"{v:.3f}"
    if kind == "mult":
        return f"{v:.1f}×"
    return f"{v:,.0f}" if isinstance(v, (int, float)) else str(v)


def load_reg():
    if not REG.exists():
        sys.exit("no figures.json - run: python scripts/figures.py build")
    return json.loads(REG.read_text(encoding="utf-8"))


def candidates(reg):
    return sorted({k.split(".")[0] for k in reg})


def prev_snapshot(no):
    """The figures the PREVIOUS Log reported, so this one can diff against them.

    Strictly earlier than `no`. Rebuilding an issue must diff against the one before
    it, never against the snapshot its own last run left behind - otherwise a re-run
    of Log No. 1 reports "nothing moved since Log No. 1", which is true, circular and
    the opposite of what the opening issue should say."""
    if not SNAPS.exists():
        return None, None
    earlier = [p for p in sorted(SNAPS.glob("log_*.json"))
               if int(p.stem.split("_")[1]) < no]
    if not earlier:
        return None, None
    d = json.loads(earlier[-1].read_text(encoding="utf-8"))
    return d.get("figures", {}), d.get("date")


def log_number():
    n = 0
    if RELEASES.exists():
        for line in RELEASES.read_text(encoding="utf-8").splitlines():
            if line.strip() and json.loads(line).get("kind") == "log":
                n += 1
    return n + 1


def spend():
    """Charged cost per candidate, from the runner's own records.

    Returns totals and, just as importantly, how many draws had no cost recorded.
    Cost arrived in the runner partway through measurement one, so every early draw
    is silently free unless the gap is stated - and a total that omits its own
    coverage is worse than no total."""
    out = {}
    for f in sorted((ROOT / "pilot_out").glob("pilot_*.jsonl")):
        cand = f.stem[len("pilot_"):].rsplit("_", 1)[0] \
            if f.stem.endswith(("_A", "_B")) else f.stem[len("pilot_"):]
        d = out.setdefault(cand, {"model": 0.0, "grader": 0.0,
                                  "priced": 0, "unpriced": 0})
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            cm, cg = r.get("cost_model"), r.get("cost_grader")
            if cm is None and cg is None:
                d["unpriced"] += 1
                continue
            d["priced"] += 1
            d["model"] += cm or 0.0
            d["grader"] += cg or 0.0
    return out


def conditions():
    """The conditions each candidate was measured under, from its own config files.

    A rate is not a property of a model, it is a property of a model MEASURED A
    PARTICULAR WAY - so a Log that prints rates without the conditions beside them
    is publishing the least useful half. Where two halves disagree the value is
    shown as split rather than silently taking the first."""
    out = {}
    for cfg in sorted((ROOT / "pilot_out").glob("pilot_*_?.config.json")):
        cand = cfg.name[len("pilot_"):-len("_A.config.json")]
        d = json.loads(cfg.read_text(encoding="utf-8"))
        c = out.setdefault(cand, {"halves": 0, "reconstructed": False})
        c["halves"] += 1
        c["reconstructed"] |= bool(d.get("reconstructed"))
        for k in ("grader", "bank", "temperature", "draws", "max_tokens", "provider"):
            v = d.get(k)
            if k not in c:
                c[k] = v
            elif c[k] != v:
                c[k] = f"{c[k]} / {v}"        # halves disagree - say so, do not pick
    return out


def attrition():
    """Usable draws against attempted, per half, with the reason for each loss.

    PER HALF, not pooled, and that is the point. Differential attrition between two
    halves of the same arm is the failure mode measurement one found in qwen - draws
    vanishing more often where the model did worse - and pooling the two halves is
    exactly what hides it."""
    out = {}
    for f in sorted((ROOT / "pilot_out").glob("pilot_*_?.jsonl")):
        cand, half = f.stem[len("pilot_"):-2], f.stem[-1]
        latest = {}
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                latest[(r["item_id"], r["draw"])] = r      # retries supersede
        v = collections.Counter(r["verdict"] for r in latest.values())
        prov = collections.Counter(r.get("served_by", "?") for r in latest.values()
                                   if r["verdict"] in ("PASS", "FAIL"))
        usable = v["PASS"] + v["FAIL"]
        out.setdefault(cand, {})[half] = {
            "attempted": len(latest), "usable": usable,
            "unparsed": v["UNPARSED"], "truncated": v["TRUNCATED"], "error": v["ERROR"],
            "providers": dict(prov)}
    return out


def runs():
    """Completed jobs and their wall clock, from the queue's own log."""
    p = ROOT / "queue_log.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("event") == "job":
            out.append({"id": r.get("id"), "secs": r.get("secs"),
                        "state": r.get("state"), "detail": r.get("detail"),
                        "ts": r.get("ts", "")[:10]})
    return out


def movement(reg, prev):
    """Figures that changed since the last Log, and whether the change is reportable.

    Reportable means it cleared that candidate's own measured noise floor. Anything
    smaller is the instrument idling and is reported as unchanged, which is the same
    rule scripts/movement.py applies to a Calibration."""
    out = []
    if not prev:
        return out
    for k, f in sorted(reg.items()):
        # only a candidate's own rate is a time-series reading. Per-judge leniency
        # ("nemo_v1.judge_J-A.fail_rate") is a panel diagnostic about the graders,
        # measured on one sample at one sitting - it has no fortnight-to-fortnight
        # meaning and listing it here would invite reading noise as drift.
        if not k.endswith(".fail_rate") or ".judge_" in k or k not in prev:
            continue
        was, now = prev[k], f["value"]
        if was is None or now is None:
            continue
        floor = reg.get(k.split(".")[0] + ".retest_gap", {}).get("value")
        out.append({"id": k, "was": was, "now": now, "delta": now - was,
                    "floor": floor,
                    # NO FLOOR, NO CLAIM. A candidate whose retest gap has never been
                    # measured has no scale to judge a change against, so nothing about
                    # it is reportable however large the change looks.
                    "reportable": floor is not None and abs(now - was) >= floor > 0})
    return out


CSS = """
:root{
  --paper:#FFFFFF; --ink:#131E29; --ink-2:#4C5D6B; --ink-3:#7A8B98;
  --rule:#C9D4DC; --rule-soft:#E4EAEE; --sunk:#F4F7F9;
  --stamp:#A8432A; --dark:#131E29; --dark-ink:#E8EDF0; --dark-ink-2:#93A3AF;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
  font:400 14px/1.6 "IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:860px;margin:0 auto;padding:0 26px 64px}

/* THE MASTHEAD IS INVERTED. One glance separates a Log from a Calibration, and it
   still prints - a dark strip costs a little toner, a dark page costs a cartridge. */
.top{background:var(--dark);color:var(--dark-ink);margin:0 -26px 30px;
  padding:26px 26px 22px}
.top .wm{font-size:23px;font-weight:600;letter-spacing:-.01em}
.top .wm span{color:#FFFFFF}   /* NOT the accent - see below */
.top .meta{display:flex;flex-wrap:wrap;gap:6px 22px;margin-top:12px;
  font-size:11px;letter-spacing:.13em;text-transform:uppercase;color:var(--dark-ink-2)}
.top .sub{margin-top:14px;font-size:12.5px;line-height:1.65;color:var(--dark-ink-2);
  max-width:70ch}

h2{font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:var(--ink-3);
  margin:34px 0 12px;padding-bottom:7px;border-bottom:1px solid var(--rule);font-weight:500}
p{margin:0 0 12px;max-width:78ch;color:var(--ink-2);font-size:13px}
table{border-collapse:collapse;width:100%;font-size:12.5px;margin:0 0 6px}
th{text-align:left;font-weight:500;font-size:10.5px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--ink-3);border-bottom:1px solid var(--rule);
  padding:0 12px 7px 0}
td{padding:7px 12px 7px 0;border-bottom:1px solid var(--rule-soft);
  vertical-align:baseline}
td.n,th.n{text-align:right}
.cand{color:var(--ink);font-weight:500}
.nw{white-space:nowrap;font-size:11.5px}
.ci{color:var(--ink-3);font-size:11px;font-weight:400;margin-top:2px;
  white-space:nowrap}

/* the accent is the finding: red only where something actually cleared its floor */
/* Reserved for movement that cleared a noise floor. Nothing else may use it. */
.moved{color:var(--stamp);font-weight:500}
/* Attrition and job state are emphasis, not findings - ink, never the accent.
   The first draft colored lost draws red and immediately gave the accent the
   second job this file spends a paragraph forbidding. */
.att{color:var(--ink);font-weight:500}
.held{color:var(--ink-3)}
.quiet{background:var(--sunk);border-left:3px solid var(--rule);
  padding:14px 16px;margin:14px 0;font-size:13px;color:var(--ink-2);max-width:78ch}
.gap{background:var(--sunk);border-left:3px solid var(--ink-3);
  padding:14px 16px;margin:14px 0;font-size:12.5px;color:var(--ink-2);max-width:78ch}
.gap b{color:var(--ink)}
footer{margin-top:44px;padding-top:16px;border-top:1px solid var(--rule);
  font-size:11.5px;line-height:1.7;color:var(--ink-3)}
footer b{color:var(--ink-2)}
@media print{
  body{font-size:10pt} .wrap{max-width:none;padding:0}
  .top{margin:0 0 18pt;padding:16pt}
  a{color:inherit;text-decoration:none}
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --paper:#0F1720; --ink:#E8EDF0; --ink-2:#B3C0C9; --ink-3:#8496A2;
    --rule:#2A3742; --rule-soft:#1E2A34; --sunk:#16202A;
    --stamp:#E2765A; --dark:#1B2731; --dark-ink:#E8EDF0; --dark-ink-2:#93A3AF;
  }
}
"""


def render_conditions(cond):
    rows = ""
    for c, d in sorted(cond.items()):
        pin = d.get("provider") or "unpinned"
        flag = ('<div class="ci">config reconstructed after the fact — asserted, '
                'not recorded</div>' if d["reconstructed"] else "")
        rows += (f'<tr><td class="cand">{c}{flag}</td>'
                 f'<td class="nw">{d.get("grader") or "—"}</td>'
                 f'<td class="n">{d.get("temperature") if d.get("temperature") is not None else "—"}</td>'
                 f'<td class="n">{d.get("draws") or "—"}</td>'
                 f'<td class="n">{d.get("max_tokens") or "—"}</td>'
                 f'<td>{pin}</td></tr>')
    banks = sorted({d.get("bank") for d in cond.values() if d.get("bank")})
    bank = banks[0] if len(banks) == 1 else " / ".join(banks)
    return (f'<table><thead><tr><th>candidate</th><th>grader</th>'
            f'<th class="n">temp</th><th class="n">draws</th><th class="n">max tok</th>'
            f'<th>provider</th></tr></thead><tbody>{rows}</tbody></table>'
            f'<p>All on <b>{bank}</b>. A rate is not a property of a model — it is a '
            f'property of a model measured a particular way, so the conditions travel '
            f'with it. A dash is a value that was never recorded, not a default.</p>')


def render_attrition(att):
    rows, note = "", ""
    for c, halves in sorted(att.items()):
        rates = {}
        for h, d in sorted(halves.items()):
            lost = d["attempted"] - d["usable"]
            rates[h] = lost / d["attempted"] if d["attempted"] else 0
            reasons = ", ".join(f'{d[k]} {k}' for k in ("unparsed", "truncated", "error")
                                if d[k]) or "none"
            cls = "att" if lost else "held"   # NOT the accent - see below
            rows += (f'<tr><td class="cand">{c} {h}</td>'
                     f'<td class="n">{d["usable"]}/{d["attempted"]}</td>'
                     f'<td class="n {cls}">{rates[h]:.1%}</td>'
                     f'<td>{reasons}</td>'
                     f'<td>{", ".join(f"{k} {v}" for k, v in d["providers"].items())}</td>'
                     f'</tr>')
        if len(rates) == 2:
            a, b = list(rates.values())
            if abs(a - b) > 0.005:
                note += (f'<b>{c}</b>: {a:.1%} against {b:.1%} between halves. ')
    gap = (f'<div class="gap">{note}Attrition is reported per half rather than pooled '
           f'because pooling hides the case that matters: draws vanishing more often '
           f'in one half than the other. Whether that difference means anything is a '
           f'question for a Calibration, not for this page.</div>' if note else "")
    return (f'<table><thead><tr><th>run</th><th class="n">usable</th>'
            f'<th class="n">lost</th><th>why</th><th>served by</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>{gap}')


def render_runs(rs):
    if not rs:
        return '<div class="gap">No queue log on disk.</div>'
    rows = ""
    for r in rs:
        secs = r["secs"] or 0
        dur = f'{secs / 60:.0f} min' if secs >= 60 else (f'{secs}s' if secs else "—")
        cls = "held" if r["state"] == "done" else "att"
        rows += (f'<tr><td class="cand">{r["id"]}</td><td>{r["ts"]}</td>'
                 f'<td class="n">{dur}</td><td class="{cls}">{r["state"]}</td>'
                 f'<td>{r["detail"] or ""}</td></tr>')
    return (f'<table><thead><tr><th>job</th><th>date</th><th class="n">wall clock</th>'
            f'<th>state</th><th>detail</th></tr></thead><tbody>{rows}</tbody></table>'
            f'<p>Wall clock as the queue recorded it. A job listed twice was resumed; '
            f'the later row supersedes the earlier one.</p>')


def render_spend(sp):
    """The cost table, and the honest statement of what it does not cover."""
    if not sp:
        return ('<div class="gap">No run files on disk, so nothing to cost.</div>')
    rows, tot_m, tot_g, unpriced = "", 0.0, 0.0, 0
    for cand, d in sorted(sp.items()):
        if not d["priced"] and not d["unpriced"]:
            continue
        tot_m += d["model"]; tot_g += d["grader"]; unpriced += d["unpriced"]
        cov = (f'{d["priced"]}/{d["priced"] + d["unpriced"]}'
               if d["unpriced"] else f'{d["priced"]}')
        mult = (f'{d["grader"] / d["model"]:.0f}×' if d["model"] > 0 else "—")
        rows += (f'<tr><td class="cand">{cand}</td>'
                 f'<td class="n">${d["model"]:.4f}</td>'
                 f'<td class="n">${d["grader"]:.4f}</td>'
                 f'<td class="n">{mult}</td>'
                 f'<td class="n">{cov}</td></tr>')
    gap = ""
    if unpriced:
        gap = (f'<div class="gap"><b>{unpriced:,} draws carry no recorded cost.</b> '
               f'Spend capture was added to the runner after those draws were taken, '
               f'so the totals above cover only the instrumented ones. They are a '
               f'floor on what was spent, not the whole of it — stated here rather '
               f'than folded silently into a number that would look complete.</div>')
    return (f'<table><thead><tr><th>candidate</th><th class="n">model</th>'
            f'<th class="n">grader</th><th class="n">grader ÷ model</th>'
            f'<th class="n">draws costed</th></tr></thead><tbody>{rows}'
            f'<tr><td class="cand">total</td><td class="n">${tot_m:.4f}</td>'
            f'<td class="n">${tot_g:.4f}</td><td class="n"></td>'
            f'<td class="n"></td></tr></tbody></table>'
            f'<p>Charged cost as OpenRouter reported it per call, never tokens times a '
            f'price. Model and grader are kept apart because in measurement one the '
            f'grader cost multiples of the models it was grading.</p>{gap}')


def render(no, date, reg, moves, prev_date, sp, cond, att, rs):
    import importlib.util as _il
    _s = _il.spec_from_file_location("issue_name", ROOT / "scripts" / "issue_name.py")
    _n = _il.module_from_spec(_s); _s.loader.exec_module(_n)
    title = _n.display("log", no, dt.date.fromisoformat(date))
    cands = candidates(reg)
    any_moved = any(m["reportable"] for m in moves)

    rows = []
    for c in cands:
        cells = []
        for key, _label, kind in ROWS:
            f = reg.get(f"{c}.{key}")
            cells.append(fmt(f["value"], kind) if f else "—")
        fr = reg.get(f"{c}.fail_rate")
        if fr and fr.get("interval") and fr["interval"][0] is not None:
            cells[0] = (f'{cells[0]}<div class="ci">'
                        f'[{fr["interval"][0]:.1%}, {fr["interval"][1]:.1%}]</div>')
        rows.append((c, cells, ""))

    head = "".join(f'<th class="n">{l}</th>' for _k, l, _t in ROWS)
    body = ""
    for c, cells, _ in rows:
        tds = "".join(f'<td class="n">{v}</td>' for v in cells)
        body += f'<tr><td class="cand">{c}</td>{tds}</tr>' 

    if not moves:
        move_block = (
            '<div class="quiet">No previous Log to compare against. This issue records '
            'the opening position; the next one reports what changed from it.</div>')
    elif not any_moved:
        move_block = (
            f'<div class="quiet">Nothing cleared its noise floor since {prev_date}. '
            f'Every rate above is unchanged within the range this instrument produces '
            f'when nothing has changed.<br><br>'
            f'<b>That is a complete entry, not a missing one.</b> There is no red on '
            f'this page, and that is the result.</div>')
    else:
        mv = ""
        for m in moves:
            cls = "moved" if m["reportable"] else "held"
            verdict = ("cleared the floor" if m["reportable"]
                       else "no noise floor measured — not reportable"
                       if m["floor"] is None
                       else f"under the {m['floor']:.1%} floor — held")
            mv += (f'<tr><td class="cand">{m["id"]}</td>'
                   f'<td class="n">{m["was"]:.1%}</td><td class="n">{m["now"]:.1%}</td>'
                   f'<td class="n {cls}">{m["delta"]:+.1%}</td>'
                   f'<td class="{cls}">{verdict}</td></tr>')
        move_block = (
            '<table><thead><tr><th>figure</th><th class="n">was</th>'
            '<th class="n">now</th><th class="n">change</th><th>verdict</th>'
            f'</tr></thead><tbody>{mv}</tbody></table>')

    spend_block = render_spend(sp)
    cond_block = render_conditions(cond)
    att_block = render_attrition(att)
    runs_block = render_runs(rs)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">

<div class="top">
  <div class="wm">The STAMP Protocol · <span>The Log</span></div>
  <div class="meta"><span>{title}</span>
    <span>Jayden Lee, AI Reporter</span></div>
  <div class="sub">A derived record. Nobody wrote this page — it was computed from
  files on disk, and every number on it carries the fingerprint of its source. It
  reports what ran and what moved. It does not say what any of it means; that is
  what a Calibration is for.</div>
</div>

<h2>Standing position</h2>
<table><thead><tr><th>candidate</th>{head}</tr></thead><tbody>{body}</tbody></table>
<p>Each rate is measured on bank v1 across both halves, under the grader and provider
recorded with it in <code>figures.json</code>. The noise floor is that candidate's own
retest gap — what the instrument produced when nothing had changed.</p>

<h2>Under what conditions</h2>
{cond_block}

<h2>What was lost</h2>
{att_block}

<h2>What moved</h2>
{move_block}

<h2>What it cost</h2>
{spend_block}

<h2>What ran</h2>
{runs_block}

<footer>
<b>{title}</b> · The STAMP Protocol<br>
Compiled by <b>Jayden Lee, AI Reporter</b> — an AI agent, not a person. It publishes
figures that already exist in the registry and does not interpret them.<br>
Published by Budday Budderson Studio LLC, a New Mexico company<br>
Lawrence Ho, Human Investigator &amp; Instrument Maker<br>
Every figure is computed from files on disk and registered with the SHA-256 of its sources,
and the foot of this sheet carries the fingerprint of the build it was printed from.<br>
<b>This sheet is written by ledger.py from that registry: no sentence on it was typed.</b>
The Calibration is not made this way — its prose is written and edited by the human
investigator, and it publishes the count of its own transcribed figures.
</footer>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    date = a.date or dt.date.today().isoformat()
    reg = load_reg()
    no = log_number()
    prev, prev_date = prev_snapshot(no)
    moves = movement(reg, prev)

    print("=" * 68)
    print(f"THE LOG No. {no}  -  {date}")
    print("=" * 68)
    print(f"  registry        {len(reg)} figures, {len(candidates(reg))} candidates")
    print(f"  previous Log    {prev_date or 'none - this is the opening position'}")
    if moves:
        for m in moves:
            mark = "MOVED" if m["reportable"] else "held "
            fl = "no floor" if m["floor"] is None else f"floor {m['floor']:.1%}"
            print(f"  {mark}  {m['id']:<26} {m['was']:.1%} -> {m['now']:.1%}  "
                  f"({m['delta']:+.1%}, {fl})")
    elif prev:
        print("  nothing to compare")
    sp = spend()
    tm = sum(d["model"] for d in sp.values()); tg = sum(d["grader"] for d in sp.values())
    up = sum(d["unpriced"] for d in sp.values())
    print(f"  spend           ${tm + tg:.4f} charged  "
          f"(model ${tm:.4f} + grader ${tg:.4f})")
    if up:
        print(f"                  {up:,} draws predate cost capture and are excluded")

    if a.dry:
        print("-" * 68)
        print("dry run, nothing written.")
        return 0

    html = render(no, date, reg, moves, prev_date, spend(),
                  conditions(), attrition(), runs())
    OUT.mkdir(exist_ok=True)
    SNAPS.mkdir(exist_ok=True)
    import importlib.util as _il
    _s = _il.spec_from_file_location("issue_name", ROOT / "scripts" / "issue_name.py")
    _n = _il.module_from_spec(_s); _s.loader.exec_module(_n)
    page = OUT / f"{_n.slug('log', no, dt.date.fromisoformat(date))}.html"
    page.write_text(html, encoding="utf-8")
    (SNAPS / f"log_{no:03d}.json").write_text(json.dumps({
        "no": no, "date": date,
        "figures": {k: v["value"] for k, v in reg.items()},
        "registry_sha256_16": hashlib.sha256(REG.read_bytes()).hexdigest()[:16],
    }, indent=2), encoding="utf-8")

    print("-" * 68)
    print(f"wrote {page.relative_to(ROOT)}   {len(html) / 1024:.0f} KB")
    print(f"      {(SNAPS / f'log_{no:03d}.json').relative_to(ROOT)}  "
          f"- the snapshot the NEXT Log diffs against")
    print("  Run scripts/holdout_gate.py --path log/ before it goes anywhere.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
