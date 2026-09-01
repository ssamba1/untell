"""A cut-off download must not be cached as if it were a whole volume.

This is a regression test for a defect that produced a *plausible* wrong answer rather than an
error. One run of the survey lost `2025.findings` to an `IncompleteRead` and printed 27,993
abstracts instead of 31,387 — 3,394 short — with the loss visible only as a single warning line
above the JSON. Nothing failed, and the number looked entirely reasonable.

The size floor in `download` could not catch it: a partial read of an 8.7 MB volume is far larger
than 200 bytes. So the fix is a retry, and these tests pin the three behaviours it has to keep —
retry the transient case, do *not* retry a 404, and still reject a body too small to be a volume.
"""

from __future__ import annotations

import http.client
import urllib.error

import pytest

from eval import litreview


class _Response:
    """Minimal stand-in for the context manager `urlopen` returns."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


# A volume the downloader will accept: over the byte floor AND containing a real paper, since
# a paperless file is now rejected (2018.acl returns exactly that with HTTP 200).
VOLUME = (
    b"<collection id='2025.acl'><volume id='long'><paper id='1'>"
    b"<title>A paper about detection</title>"
    b"<abstract>" + b"An abstract sentence. " * 20 + b"</abstract>"
    b"</paper></volume></collection>"
)


def test_a_truncated_transfer_is_retried_rather_than_cached(monkeypatch):
    """The defect itself: without the retry the caller gets None and silently undercounts."""
    calls: list[str] = []

    def flaky(url, timeout=0):  # noqa: ARG001
        calls.append(url)
        if len(calls) == 1:
            raise http.client.IncompleteRead(b"partial", 8_706_613)
        return _Response(VOLUME)

    monkeypatch.setattr(litreview.urllib.request, "urlopen", flaky)
    assert litreview._fetch("http://x/2025.findings.xml", "2025.findings") == VOLUME
    assert len(calls) == 2, "a transient failure must be retried"


def test_a_missing_volume_is_not_retried(monkeypatch):
    """A 404 is an answer, not a hiccup. Retrying it would triple the runtime of every survey for
    volume names that will never resolve — which is how `2025.naacl-srw` and `2026.aacl` behaved
    before they were removed from the list."""
    calls: list[str] = []

    def missing(url, timeout=0):  # noqa: ARG001
        calls.append(url)
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(litreview.urllib.request, "urlopen", missing)
    assert litreview._fetch("http://x/2026.aacl.xml", "2026.aacl") is None
    assert len(calls) == 1, "a 404 must not be retried"


def test_a_transient_failure_that_never_clears_gives_up(monkeypatch):
    calls: list[str] = []

    def always_broken(url, timeout=0):  # noqa: ARG001
        calls.append(url)
        raise TimeoutError("no route")

    monkeypatch.setattr(litreview.urllib.request, "urlopen", always_broken)
    assert litreview._fetch("http://x/v.xml", "v", attempts=3) is None
    assert len(calls) == 3, "it must stop after the configured number of attempts"


def test_a_body_too_small_to_be_a_volume_is_still_rejected(monkeypatch):
    """The floor that survived the rewrite: an error page returned with HTTP 200."""
    monkeypatch.setattr(
        litreview.urllib.request, "urlopen", lambda url, timeout=0: _Response(b"not found")
    )
    assert litreview._fetch("http://x/v.xml", "v") is None


def test_every_configured_volume_name_is_plausible():
    """`2025.naacl-srw` and `2026.aacl` sat in this list never resolving. There is no offline way to
    prove a name exists, but a name that is not even shaped like an Anthology volume id cannot."""
    import re

    bad = [v for v in litreview.VOLUMES if not re.fullmatch(r"[0-9]{4}\.[a-z0-9-]+", v)]
    assert not bad, f"not Anthology volume ids: {bad}"


@pytest.mark.parametrize("dead", ["2025.naacl-srw", "2026.aacl"])
def test_the_two_volumes_that_never_existed_are_gone(dead):
    """Pins the round-fifteen correction so the names cannot drift back in."""
    assert dead not in litreview.VOLUMES


def test_a_volume_that_parses_to_zero_papers_is_rejected(monkeypatch):
    """The byte floor was not enough. `2018.acl` and `2019.acl` return HTTP 200 with a 743-byte stub
    containing no papers at all — the Anthology used the old `P18-1001` id scheme then, in
    differently-named files. Cached, those look like successful downloads forever, and four of them
    sat in the volume list for a full round contributing nothing."""
    stub = b"<collection id='2018.acl'>" + b" " * 400 + b"</collection>"
    monkeypatch.setattr(
        litreview.urllib.request, "urlopen", lambda url, timeout=0: _Response(stub)
    )
    assert litreview._fetch("http://x/2018.acl.xml", "2018.acl") is None


def test_unparseable_xml_is_rejected_rather_than_cached():
    """An error page served with HTTP 200 is longer than the byte floor and is not XML."""
    import unittest.mock as mock

    page = b"<html><body>" + b"Service Unavailable " * 40 + b"</body></html>"
    with mock.patch.object(litreview.urllib.request, "urlopen",
                           lambda url, timeout=0: _Response(page)):
        assert litreview._fetch("http://x/v.xml", "v") is None


def test_a_real_volume_still_passes():
    """Guards the guard: a floor that rejected everything would empty the corpus silently, which is
    the round-thirty-one failure with extra steps."""
    import unittest.mock as mock

    real = VOLUME  # over the byte floor and containing a paper
    with mock.patch.object(litreview.urllib.request, "urlopen",
                           lambda url, timeout=0: _Response(real)):
        assert litreview._fetch("http://x/v.xml", "v") == real


def test_a_body_too_small_to_be_a_real_volume_is_rejected_even_when_it_parses():
    """MUTATION-CHECKED. Dropping the byte floor survived every other test here, because every probe
    used a body that was either unparseable or paperless — both caught by the checks after it. The
    floor's own job is the case those miss: a body that parses AND contains a paper AND is far too
    small to be an Anthology volume, which is what a transfer truncated a few hundred bytes in looks
    like. This one is 94 bytes with a valid paper in it.
    """
    import unittest.mock as mock

    truncated = (b"<collection id='2025.acl'><volume id='long'><paper id='1'>"
                 b"<title>T</title></paper></volume></collection>")
    assert len(truncated) < 200, "the fixture must be under the floor to exercise it"
    with mock.patch.object(litreview.urllib.request, "urlopen",
                           lambda url, timeout=0: _Response(truncated)):
        assert litreview._fetch("http://x/v.xml", "v") is None
