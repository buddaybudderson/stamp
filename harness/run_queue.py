#!/usr/bin/env python3
"""
THE LOOP. Runs the whole work queue unattended, in order, resumably.

    python scripts/run_queue.py plan       free. Shows the queue and what is left.
    python scripts/run_queue.py run        executes. Asks for the key once.
    python scripts/run_queue.py run --phase 1-validate
    python scripts/run_queue.py run --only panel_nemo,nemo_t0_A

WHY THIS EXISTS. Every job on 2026-08-29 was launched by hand from a shell that
remembered the last job's variables, and three separate runs were spoiled by it:
a 3-draw run that should have been 5, a full run of judge J-A graded by judge J-B,
and a grader inherited from a command typed twenty minutes earlier. None were
knowledge problems - they were remembering problems, and a person cannot be
patched. So:

  EVERY JOB GETS A CLEAN ENVIRONMENT. The runner strips every STAGE1_*, GRADER_*,
  HALF and DRAWS variable out of the environment it hands to a child, then sets
  exactly what protocol/queue.json says. A stale variable cannot reach a run,
  because nothing is inherited.

  THE KEY IS ASKED FOR ONCE AND NEVER WRITTEN DOWN. It lives in this process's
  memory and is passed to children through their environment. It is not echoed,
  not logged, not saved. Setting STAGE1_API_KEY beforehand also works.

  SLEEP IS DISABLED FOR THE DURATION AND RESTORED AFTERWARDS. A standing rule of
  this project, and a rule a human has to remember is not a rule.

  A DEAD KEY STOPS THE QUEUE. pilot_native.py aborts on the first 401; the runner
  sees the exit code and stops rather than marching the remaining jobs into the
  same wall.

Stdlib only. Safe to interrupt: every job resumes from disk.
"""
import argparse, getpass, json, os, pathlib, platform, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
QUEUE = ROOT / "protocol" / "queue.json"
LOG = ROOT / "queue_log.jsonl"

# Variables the runner OWNS. Every one is stripped from the child environment and
# then set explicitly, so nothing survives from the parent shell or a previous job.
OWNED = ("STAGE1_MODEL", "STAGE1_CANDIDATE", "STAGE1_PROVIDER", "STAGE1_QUANT",
         "STAGE1_MAX_TOKENS", "STAGE1_TEMP", "GRADER_MODEL", "GRADER_PROVIDER",
         "HALF", "DRAWS", "STAMP_CORE", "BANK_FILE", "PREFLIGHT_CALLS")


# ------------------------------------------------------------------ state
def out_path(job):
    """Where a pilot job writes, mirroring pilot_native.py's naming exactly."""
    t = job.get("temp", 0.7)
    tag = "" if abs(t - 0.7) < 1e-9 else f"_t{t:g}".replace(".", "")
    h = job.get("half", "")
    stem = f"{job['candidate']}{tag}" + (f"_{h}" if h else "")
    return ROOT / "pilot_out" / f"pilot_{stem}.jsonl"


def pilot_state(job):
    """(done, total) usable draws for a pilot job."""
    p = out_path(job)
    bank = ROOT / "bank" / job.get("bank", "bank_v1.jsonl")
    n_items = sum(1 for l in bank.read_text(encoding="utf-8").splitlines() if l.strip())
    total = n_items * job.get("draws", 5)
    if not p.exists():
        return 0, total
    latest = {}
    for l in p.read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            latest[(r["item_id"], r["draw"])] = r["verdict"]
    done = sum(1 for k, v in latest.items()
               if v in ("PASS", "FAIL") and k[1] < job.get("draws", 5))
    return done, total


def job_state(job):
    k = job["kind"]
    if k == "pilot":
        d, t = pilot_state(job)
        return ("done" if d >= t else "partial" if d else "todo"), f"{d}/{t} draws"
    if k == "panel":
        p = ROOT / "panel_out" / f"panel_{job['candidate']}.json"
        return ("done" if p.exists() else "todo"), "panel report"
    if k == "fever":
        p = ROOT / "pilot_out" / f"pilot_{job['candidate']}_t0_A.jsonl"
        return ("todo" if not p.exists() else "ready"), "needs both temperatures"
    if k == "regrade":
        p = ROOT / "pilot_out" / f"pilot_{job['label']}_A.jsonl"
        return ("done" if p.exists() else "todo"), f"-> {job['label']}"
    if k == "reliability":
        p = ROOT / f"reliability_{job['candidate']}.json"
        return ("done" if p.exists() else "todo"), "A vs B"
    return "todo", ""


# ------------------------------------------------------------------ power
def sleep_guard(disable=True):
    """A run that starts on a machine allowed to sleep is a run that may not finish."""
    if platform.system() != "Windows":
        return "not Windows - sleep unchanged"
    try:
        if disable:
            subprocess.run(["powercfg", "/change", "standby-timeout-ac", "0"],
                           capture_output=True, timeout=20)
            subprocess.run(["powercfg", "/change", "monitor-timeout-ac", "0"],
                           capture_output=True, timeout=20)
            return "standby and monitor timeouts set to 0 (never) on AC"
        subprocess.run(["powercfg", "/change", "standby-timeout-ac", "30"],
                       capture_output=True, timeout=20)
        subprocess.run(["powercfg", "/change", "monitor-timeout-ac", "10"],
                       capture_output=True, timeout=20)
        return "standby restored to 30 min, monitor to 10 min"
    except Exception as e:
        return f"could not change power settings ({type(e).__name__}) - check manually"


# ------------------------------------------------------------------ execution
def child_env(key, job):
    """A brand-new environment. Nothing about a job is inherited - that is the point."""
    env = {k: v for k, v in os.environ.items() if k not in OWNED}
    env["STAGE1_API_KEY"] = key
    if job["kind"] != "pilot":
        return env
    env["STAGE1_MODEL"]      = job["model"]
    env["STAGE1_CANDIDATE"]  = job["candidate"]
    env["GRADER_MODEL"]      = job["grader"]
    env["STAGE1_MAX_TOKENS"] = str(job.get("max_tokens", 16384))
    env["DRAWS"]             = str(job.get("draws", 5))
    env["STAGE1_TEMP"]       = str(job.get("temp", 0.7))
    if job.get("half"):
        env["HALF"] = job["half"]
    if job.get("provider"):
        env["STAGE1_PROVIDER"] = job["provider"]
    return env


def command(job):
    c = job["candidate"]
    if job["kind"] == "regrade":
        return ["python", "scripts/regrade.py", c, job["grader"],
                "--label", job["label"]]
    return {"pilot":       ["python", "scripts/pilot_native.py"],
            "panel":       ["python", "scripts/panel_grade.py", c],
            "fever":       ["python", "scripts/fever.py", c],
            "reliability": ["python", "scripts/reliability.py", c]}[job["kind"]]


def log(rec):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **rec}) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["plan", "run"])
    ap.add_argument("--phase", default="", help="run only this phase")
    ap.add_argument("--only", default="", help="comma-separated job ids")
    a = ap.parse_args()

    q = json.loads(QUEUE.read_text(encoding="utf-8"))
    jobs = []
    for ph in q["phases"]:
        if a.phase and ph["phase"] != a.phase:
            continue
        for j in ph["jobs"]:
            if a.only and j["id"] not in a.only.split(","):
                continue
            jobs.append((ph, j))

    print("=" * 84)
    print(f"WORK QUEUE - {len(jobs)} job(s)")
    print("=" * 84)
    todo = []
    cur = None
    for ph, j in jobs:
        if ph["phase"] != cur:
            cur = ph["phase"]
            print(f"\nPHASE {cur}")
            for line in _wrap(ph["why"], 78):
                print(f"  {line}")
            print()
        st, detail = job_state(j)
        mark = {"done": "  done ", "partial": "PARTIAL", "todo": "  todo ",
                "ready": " ready "}[st]
        print(f"  [{mark}] {j['id']:<14} {j['kind']:<12} {detail}")
        if j.get("note"):
            for line in _wrap("note: " + j["note"], 66):
                print(f"                            {line}")
        if st != "done":
            todo.append(j)

    if a.action == "plan":
        print(f"\n{len(todo)} job(s) to run. Nothing was spent.")
        print("  python scripts/run_queue.py run")
        return

    if not todo:
        print("\nnothing to do - every job in scope is already complete.")
        return

    key = os.environ.get("STAGE1_API_KEY", "")
    if not key:
        print(f"\n{len(todo)} job(s) to run.")
        key = getpass.getpass("OpenRouter key (not echoed, not saved): ").strip()
    if not key:
        sys.exit("no key given - nothing run.")
    print(f"key accepted: {len(key)} characters")

    print("\n" + sleep_guard(True))
    log({"event": "queue_start", "jobs": [j["id"] for j in todo]})

    t0 = time.time()
    try:
        for n, j in enumerate(todo, 1):
            print("\n" + "=" * 84)
            print(f"[{n}/{len(todo)}] {j['id']}   ({j['kind']})")
            if j["kind"] == "pilot":
                print(f"    model {j['model']}   grader {j['grader']}")
                print(f"    half {j.get('half','-')}  draws {j.get('draws',5)}  "
                      f"temp {j.get('temp',0.7)}  provider {j.get('provider') or '(unpinned)'}")
            print("=" * 84, flush=True)
            js = time.time()
            r = subprocess.run(command(j), cwd=ROOT, env=child_env(key, j))
            secs = time.time() - js
            st, detail = job_state(j)
            log({"event": "job", "id": j["id"], "rc": r.returncode,
                 "secs": round(secs), "state": st, "detail": detail})
            print(f"\n  -> {j['id']} exit {r.returncode} after {secs/60:.1f} min; "
                  f"now {st} ({detail})")
            if r.returncode != 0:
                print("\n" + "!" * 84)
                print(f"QUEUE STOPPED - {j['id']} exited {r.returncode}.")
                print("  Remaining jobs were NOT started. Fix the cause above and re-run;")
                print("  every job resumes from disk, so nothing already done is repeated.")
                print("!" * 84)
                log({"event": "queue_stop", "id": j["id"], "rc": r.returncode})
                break
        else:
            print(f"\nQUEUE COMPLETE in {(time.time()-t0)/60:.0f} min.")
            log({"event": "queue_complete", "mins": round((time.time() - t0) / 60)})
    except KeyboardInterrupt:
        print("\ninterrupted - safe. Re-run to continue where it stopped.")
        log({"event": "interrupted"})
    finally:
        print(sleep_guard(False))
        print(f"log: {LOG}")


def _wrap(s, w):
    words, line, out = s.split(), "", []
    for x in words:
        if len(line) + len(x) + 1 > w:
            out.append(line); line = x
        else:
            line = f"{line} {x}".strip()
    if line:
        out.append(line)
    return out


if __name__ == "__main__":
    main()
