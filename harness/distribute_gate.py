#!/usr/bin/env python3
"""
THE DISTRIBUTION GATE. Decides whether a post may go out, on which channel, today.

    python scripts/distribute_gate.py --list
    python scripts/distribute_gate.py x --figure nemo_v1.panel_ac1 --text post.txt
    python scripts/distribute_gate.py x --figure nemo_v1.panel_ac1 --text post.txt --record
    python scripts/distribute_gate.py reddit --figure nemo_v1.fail_rate --text d.md --community LocalLLaMA

  exit 0 = send it     exit 1 = do not send

SIX CHECKS, and every one exists because a person would eventually forget it:

  1. CANONICAL SOURCE. The finding must exist in figures.json. Nothing leaves this
     building that cannot be computed from a file on disk. This is the rule the
     whole programme rests on and it is the easiest one to erode - a social post is
     exactly where a remembered number slips back in.
  2. PUBLISHED FIRST. The blog or a Calibration carries it before any platform does.
     A claim living only on a platform we cannot version or correct is the failure
     the reference series exists to prevent.
  3. FREQUENCY. Each channel's minimum gap, from its own ledger. Hacker News is 90
     days because a flagged submission costs more than five good ones earn.
  4. AUTONOMY. auto / draft / human, per protocol/channels.json. An agent may send
     only where a bad post is cheap AND the content is mechanically derived. It may
     never send to Hacker News, and never to Reddit - which obliges you to answer
     replies, and an agent that posts without replying is worse than silence.
  5. HOLDOUT. The text is scanned for held-out probes. A leaked probe on a platform
     cannot be unpublished.
  6. BYLINE. The account is the PUBLICATION, never a persona. Jayden Lee is a role
     name in the masthead; a signature asserts a speaker, and an agent is not one.
     An AI evaluator caught inventing a spokesperson loses the only thing it sells.

Stdlib only. No network - this decides, it does not post.
"""
import argparse, datetime as dt, json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHANNELS = ROOT / "protocol" / "channels.json"
FIGURES = ROOT / "figures.json"
LEDGER = ROOT / "distribution_log.jsonl"


def load_channels():
    d = json.loads(CHANNELS.read_text(encoding="utf-8"))
    return {c["id"]: c for c in d["channels"]}, d.get("cutting_order", [])


def last_post(channel, community=None):
    if not LEDGER.exists():
        return None
    best = None
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("event") != "sent" or r.get("channel") != channel:
            continue
        if community and r.get("community") != community:
            continue
        if best is None or r["date"] > best["date"]:
            best = r
    return best


def published_findings():
    """Figure ids that already appear in a published Calibration or Bench post.
    A social post may only carry a finding the canonical record already carries."""
    out = set()
    for p in list((ROOT / "reports").glob("*.html")) + list((ROOT / "bench").glob("*.html")):
        try:
            t = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for tok in t.split("[FIG ")[1:]:
            out.add(tok.split("]")[0].strip())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channel", nargs="?", default="")
    ap.add_argument("--figure", default="", help="figure id the post is built on")
    ap.add_argument("--text", default="", help="file holding the post text")
    ap.add_argument("--community", default="", help="subreddit, for reddit")
    ap.add_argument("--approved-by", default="", help="name of the human who approved a draft")
    ap.add_argument("--record", action="store_true", help="log it as sent")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    chans, cutting = load_channels()

    if a.list or not a.channel:
        print("=" * 76)
        print("CHANNELS")
        print("=" * 76)
        for c in chans.values():
            lp = last_post(c["id"])
            since = ("never" if not lp else
                     f"{(dt.date.today() - dt.date.fromisoformat(lp['date'])).days}d ago")
            ready = "ready" if (not lp or
                    (dt.date.today() - dt.date.fromisoformat(lp["date"])).days >= c["min_gap_days"]) else "waiting"
            print(f"  {c['name']:<14} every {c['min_gap_days']:>3}d min   "
                  f"{c['autonomy']:<6} last {since:<10} {ready}")
            print(f"                 {c['form']}")
        print(f"\n  cutting order when time is short: {' -> '.join(cutting)}")
        print("  X and the blog are last: cheapest to maintain, and canonical.")
        return 0

    c = chans.get(a.channel)
    if not c:
        sys.exit(f"unknown channel {a.channel!r}. Known: {', '.join(chans)}")

    print("=" * 76)
    print(f"DISTRIBUTION GATE - {c['name']}"
          + (f" / r/{a.community}" if a.community else ""))
    print("=" * 76)
    blocked = []

    # 1 -------------------------------------------------- canonical source
    figs = json.loads(FIGURES.read_text(encoding="utf-8")) if FIGURES.exists() else {}
    if not a.figure:
        print("  [ STOP ] source   no --figure given")
        blocked.append("no figure cited")
    elif a.figure not in figs:
        print(f"  [ STOP ] source   {a.figure} is not in figures.json")
        blocked.append("figure does not exist")
    else:
        f = figs[a.figure]
        v = f["value"]
        shown = (f"{v:.1%}" if f["unit"] == "rate"
                 else f"{v:.3f}" if isinstance(v, float) else str(v))
        print(f"  [  ok  ] source   {a.figure} = {shown}  "
              f"({len(f['sources'])} source file(s), hashed)")

    # 2 -------------------------------------------------- published first
    pub = published_findings()
    if a.figure and a.figure not in pub:
        print(f"  [ STOP ] canon    {a.figure} has not appeared in a Calibration or on The Bench")
        blocked.append("not published on the canonical record first")
    elif a.figure:
        print("  [  ok  ] canon    already published on the canonical record")

    # 3 -------------------------------------------------- frequency
    lp = last_post(c["id"], a.community or None)
    if lp:
        days = (dt.date.today() - dt.date.fromisoformat(lp["date"])).days
        if days < c["min_gap_days"]:
            nxt = dt.date.fromisoformat(lp["date"]) + dt.timedelta(days=c["min_gap_days"])
            print(f"  [ STOP ] cadence  last post {days}d ago, minimum gap "
                  f"{c['min_gap_days']}d - next {nxt.isoformat()}")
            blocked.append("too soon for this channel")
        else:
            print(f"  [  ok  ] cadence  {days}d since last, minimum {c['min_gap_days']}d")
    else:
        print(f"  [  ok  ] cadence  nothing sent here yet")

    # 4 -------------------------------------------------- autonomy
    auto = c["autonomy"]
    if auto == "auto":
        print("  [  ok  ] autonomy an agent may send this unattended")
    elif a.approved_by:
        print(f"  [  ok  ] autonomy {auto} channel, approved by {a.approved_by}")
    else:
        print(f"  [ STOP ] autonomy {auto} - a person must approve. Pass --approved-by")
        if auto == "human":
            print("           Hacker News is human end to end. No agent, no draft, no")
            print("           schedule. A misjudged submission cannot be withdrawn.")
        if c["id"] == "reddit":
            print("           Reddit obliges you to answer replies. An agent that posts")
            print("           and does not reply is worse than not posting at all.")
        blocked.append(f"{auto} channel without approval")

    # 5 -------------------------------------------------- holdout
    if a.text:
        tp = pathlib.Path(a.text)
        if not tp.exists():
            print(f"  [ STOP ] holdout  {a.text} not found")
            blocked.append("text file missing")
        else:
            r = subprocess.run([sys.executable, "scripts/holdout_gate.py", "--path", str(tp)],
                               cwd=ROOT, capture_output=True, text=True)
            if r.returncode == 0:
                print("  [  ok  ] holdout  no held-out probe in the text")
            else:
                print("  [ STOP ] holdout  the text contains a held-out probe")
                blocked.append("holdout leak")
            body = tp.read_text(encoding="utf-8")
            lim = c.get("max_chars")
            if lim and len(body) > lim:
                print(f"  [ STOP ] length   {len(body)} chars, {c['name']} allows {lim}")
                blocked.append("too long")
            elif lim:
                print(f"  [  ok  ] length   {len(body)}/{lim} chars")
    else:
        print("  [ warn ] holdout  no --text given, nothing scanned")

    # 6 -------------------------------------------------- byline
    # The account is the publication, never a persona. Jayden Lee is a role name
    # in the masthead; a signature asserts a speaker, and an agent is not one. A
    # post signed by an agent is the one distribution mistake that cannot be
    # walked back, because it is evidence rather than opinion.
    ident = json.loads(CHANNELS.read_text(encoding="utf-8")).get("identity", {})
    acct = c.get("account", {})
    if acct:
        print(f"  [ note ] identity posts as {acct['posts_as']}")
        print(f"                 {acct['requires']}")
    if a.text and pathlib.Path(a.text).exists():
        body = pathlib.Path(a.text).read_text(encoding="utf-8")
        signed = [n for n in ident.get("forbidden_bylines", [])
                  if re.search(r"(^|[-—–]\s*|by\s+)" + re.escape(n) + r"\s*$",
                               body.strip(), re.I | re.M)]
        if signed:
            print(f"  [ STOP ] byline   signed by {', '.join(signed)} - "
                  f"that name is a role, not a speaker")
            blocked.append("post is signed by an agent persona")
        else:
            print("  [  ok  ] byline   not signed by an agent persona")

    print("-" * 76)
    if blocked:
        print("DO NOT SEND: " + "; ".join(blocked))
        print(f"\n  {c['name']}: {c['rule']}")
        print("-" * 76)
        return 1

    print(f"SEND. {c['name']} — {c['form']}")
    print(f"  {c['rule']}")
    if a.record:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"event": "sent", "channel": c["id"],
                                 "community": a.community or None,
                                 "figure": a.figure,
                                 "date": dt.date.today().isoformat(),
                                 "approved_by": a.approved_by or "auto",
                                 "at": dt.datetime.now(dt.timezone.utc).isoformat()}) + "\n")
        print("  recorded in the ledger.")
    else:
        print("  Re-run with --record once it is actually live.")
    print("-" * 76)
    return 0


if __name__ == "__main__":
    sys.exit(main())
