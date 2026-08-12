# Audit log

One row per pass. Written by `audit_next.py record`, which refuses malformed rows: a verdict
claiming work must name its commit and leave the suite bigger, a shrinking suite is rejected
outright, and a note too short to say what was measured is rejected. Read the last few rows,
never the whole file.

`audit_next.py` picks each pass's target as the least-audited one, so the rotation cannot
stall and a half-finished pass cannot skip a component permanently.

| # | target | verdict | tests before | tests after | commit | note |
| --- | --- | --- | --- | --- | --- | --- |
