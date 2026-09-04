# stage/ — issues waiting for Saturday 15:37 Chicago

Put a gated issue here as `stage/<kind>/<slug>.html` + `.pdf` (e.g. `stage/log/log-001-issued-sat20260905.html`).
The release workflow (`.github/workflows/release.yml`) runs `tools/wrap_issue.py` at 15:37
America/Chicago on Saturdays, moves it into `docs/`, flips its row on the home page and the
archive from "Due" to live, and pushes. Only stage a file after the harness gates have passed:
`holdout_gate.py --path log/` (or `reports/`) must print PASS. Anything here is visible in
the public repository from the moment it is committed, so stage on the morning of release.

## The dateline

An issue is datelined where the work was done, and that moves. Before you stage an issue, write the
place into a file beside it:

    stage/<kind>/<slug>.dateline        one line, in the form   City, Region, Country

Write it only when the work was NOT done at home. If the file is absent the release uses the home
dateline, **Houston, Texas, USA**, and prints a NOTE
saying so. If the file is present but empty the release refuses, because an empty file is more
likely a mistake than an intention.

The release workflow runs on GitHub's servers at 15:37 Chicago and cannot know where you are, so the
dateline has to be committed with the issue. `python tools/wrap_issue.py --check` prints the dateline
it would use; run it before Saturday if you have travelled.
