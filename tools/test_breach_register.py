#!/usr/bin/env python3
"""Tests for house gate H16, the breach register on Corrections + changes (Protocol 10, R12).

    python tools/test_breach_register.py      exit 0 = all pass

The live Corrections page is copied to a temporary folder, and each fault is planted in the copy.
"""
import pathlib, re, shutil, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
DOCS = HERE.parent / "docs"
fails = []
ROW = ('<tr><td>{d}</td><td>{m}</td><td>A figure in the draft was not in the page cited for it.</td>'
       '<td>Corrected the same day; stood down from drafting for 30 days; its drafts since its last clean audit rechecked; audit count restarted.</td></tr>')
HEAD = '<tr><th>Date</th><th>Model</th><th>What happened</th><th>What was done</th></tr>'

live = (DOCS / "corrections" / "index.html").read_text(encoding="utf-8")
reg = re.search(r'<section id="register">.*?</section>', live, flags=re.S).group(0)
if 'class="breaches"' in reg:
    fails.append("the breach table sits inside #register, where the page's counts would read it as corrections")

with tempfile.TemporaryDirectory() as tmp:
    t = pathlib.Path(tmp) / "docs"
    shutil.copytree(DOCS, t)
    page = t / "corrections" / "index.html"

    def gate(html):
        page.write_text(html, encoding="utf-8")
        r = subprocess.run([sys.executable, str(HERE / "house_gate.py"), str(t)], capture_output=True, text=True, encoding="utf-8")
        return [l for l in r.stdout.splitlines() if " H16 " in l], r.returncode

    def rows(*rs):
        return live.replace(HEAD + "</table>", HEAD + "".join(rs) + "</table>")

    def expect(name, html, why):
        h16, rc = gate(html)
        if why is None:
            if h16 or rc:
                fails.append(f"{name}: should pass, got rc={rc} {h16}")
        elif rc != 1 or not any(why in l for l in h16):
            fails.append(f"{name}: should FAIL with {why!r}, got rc={rc} {h16}")

    assert HEAD + "</table>" in live, "the live register's empty table was not found"
    expect("the live page", live, None)
    expect("two good rows, newest first", rows(ROW.format(d="Oct 20, 2026", m="Claude Opus 5.5"), ROW.format(d="Oct 13, 2026", m="Xing 4.0")), None)
    expect("the register removed", re.sub(r'<section id="breaches">.*?</section>', "", live, flags=re.S), "is missing")
    expect("a column renamed", live.replace("<th>What was done</th>", "<th>Status</th>"), "columns are")
    expect("a column dropped", live.replace("<th>Model</th>", ""), "columns are")
    expect("what was done left empty", rows(ROW.format(d="Oct 20, 2026", m="Claude Opus 5.5").replace(
        "<td>Corrected the same day; stood down from drafting for 30 days; its drafts since its last clean audit rechecked; audit count restarted.</td>", "<td> </td>")), "empty or missing cell")
    expect("a model with no version", rows(ROW.format(d="Oct 20, 2026", m="Claude")), "without a version")
    expect("an ISO date", rows(ROW.format(d="2026-10-20", m="Claude Opus 5.5")), "not a house date")
    expect("oldest first", rows(ROW.format(d="Oct 13, 2026", m="Xing 4.0"), ROW.format(d="Oct 20, 2026", m="Claude Opus 5.5")), "not newest first")

print("\n".join("FAIL  " + f for f in fails) or "test_breach_register: all pass")
sys.exit(1 if fails else 0)
