#!/usr/bin/env bash
# Did a change break how the repository DESCRIBES ITSELF?
#
# These tests are different in kind from the rest of the suite. They do not test a module; they
# assert that the documents' counts, tables and quoted figures still match the code — the detector
# registry, the console-script list, the ROADMAP status table, the census figures, and ruff over
# the whole tree including probes.
#
# So they break for changes that are nowhere near them. Adding one console script made
# why-best-open-repo.md's "29" wrong. Adding an import to a test file broke the tree-wide ruff
# check while `ruff check <that file>` stayed clean. Writing "23 local detection engines" about
# ANOTHER project tripped the detector-count guard.
#
# The failure mode this exists to stop is running the tests for the thing you changed and not the
# tests that describe the whole repo. It takes about six seconds. Run it before every commit.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "ruff, whole tree (this is what test_probe_ruff_policy asserts) ..."
ruff check .
echo "repo-wide claim tests ..."
exec python -m pytest \
    tests/test_docs_claims.py \
    tests/test_roadmap_status.py \
    tests/test_probe_ruff_policy.py \
    -q --tb=short "$@"
