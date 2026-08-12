# Audit log

One row per pass. Written by `audit_next.py record`, which refuses malformed rows: a verdict
claiming work must name its commit and leave the suite bigger, a shrinking suite is rejected
outright, and a note too short to say what was measured is rejected too. Read the last few
rows, never the whole file.

`audit_next.py` assigns the lane from a fixed schedule and the target as the least-worked one
in that lane, so the rotation cannot stall and a half-finished pass cannot skip a component
permanently.

| # | lane | target | verdict | before | after | commit | note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | L1 | T01 | clean | 5736 | 5736 | - | fleet collection test, probe ran and held |
