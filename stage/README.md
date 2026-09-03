# stage/ — issues waiting for Saturday 15:37 Chicago

Put a gated issue here as `stage/<kind>/<slug>.html` + `.pdf` (e.g. `stage/log/log-001-issued-sat20260905.html`).
The release workflow (`.github/workflows/release.yml`) runs `tools/wrap_issue.py` at 15:37
America/Chicago on Saturdays, moves it into `docs/`, flips its row on the home page and the
archive from "Due" to live, and pushes. Only stage a file after the harness gates have passed:
`holdout_gate.py --path log/` (or `reports/`) must print PASS. Anything here is visible in
the public repository from the moment it is committed, so stage on the morning of release.
