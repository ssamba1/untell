"""The tracked-text scan excludes the tests/ tree, which holds intentional control bytes.

`_tracked_text_files` feeds the control-character check. Tests carry control characters as
test data on purpose — `test_no_hidden_character_survives_a_scrub.py` embeds a literal U+0001
so the scrubber has something to scrub — so the scan must skip the whole tests/ tree, or
`untell-audit` reports a FAIL for data that is doing its job.

The exclusion used to read `"/tests/" not in line`. That never matched: `git ls-files` emits
repo-relative paths with NO leading slash (`tests/foo.py`, not `/tests/foo.py`), so the guard
silently did nothing, the U+0001 test data was scanned, and the audit exited 1. MEASURED by
running the scan: 0 of 330 tracked test files contained the substring `/tests/`, and
`check_no_control_characters` reported `tests/test_no_hidden_character_survives_a_scrub.py:44
U+0001` as an offender.

Runs against the real repository via `git ls-files`, exactly as the check does, so the test is
the shipped behaviour — not a mock of it.
"""
from __future__ import annotations

import untell.scripts.audit as audit


def test_tracked_text_files_excludes_the_tests_tree():
    tracked = audit._tracked_text_files()
    offenders = [t for t in tracked if t.startswith("tests/")]
    assert not offenders, (
        "the tracked-text scan must not read test data, which intentionally contains "
        f"control bytes: {offenders[:5]}"
    )


def test_control_character_check_passes_on_the_real_repository():
    """The end-to-end property the exclusion exists for: on this repo, the check is clean.

    Without the exclusion this FAILs with the intentional U+0001 in
    test_no_hidden_character_survives_a_scrub.py, which is why the audit exited 1.
    """
    report = audit.Report()
    audit.check_no_control_characters(report)
    finding = report.findings[-1]
    assert finding.ok, finding.detail
