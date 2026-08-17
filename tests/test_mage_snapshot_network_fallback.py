"""Transient remote-liveness failures must fall back to the cached snapshot.

mage._load() revalidates ``yaful/MAGE`` against the Hub on every process
(``snapshot_download``'s remote ETag/commit check). huggingface_hub classifies
connect/timeout/offline errors as "offline" and falls back to cache, but the
transport-level failures it does NOT classify — TLS handshake errors
(``ssl.SSLError``), connection resets mid-response
(``httpx.ReadError``/``RemoteProtocolError``) — propagate out of
``snapshot_download``. In ``score()``, ANY load failure sets
``MageDetector._dead`` permanently, so a one-off SSL/reset blip would exclude
a fully-cached detector for the whole process. ``_snapshot_dir()`` retries
cache-only on transport-class errors and only goes dead when nothing is on
disk (issue #28).
"""
import json
import os
import ssl
import tempfile
from unittest.mock import patch

import pytest

import untell.detectors.mage as mage


class _StubTok:
    @staticmethod
    def from_pretrained(local):
        return object()


class _StubModel:
    @staticmethod
    def from_pretrained(local):
        class M:
            def eval(self):
                return self

        return M()


def _make_cached_dir():
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"id2label": {"0": "machine", "1": "human"}, "num_labels": 2}, f)
    return d


def _reset_state():
    mage.MageDetector._model = None
    mage.MageDetector._tok = None
    mage.MageDetector._dead = False
    mage.MageDetector._warned = False


def test_transient_ssl_error_falls_back_to_cached_snapshot():
    d = _make_cached_dir()
    _reset_state()
    calls = []

    def flaky(repo_id, **kwargs):
        calls.append(kwargs)
        if kwargs.get("local_files_only"):
            return d
        raise ssl.SSLError("simulated TLS handshake failure")

    try:
        with patch("huggingface_hub.snapshot_download", side_effect=flaky), \
             patch("transformers.AutoTokenizer", _StubTok), \
             patch("transformers.AutoModelForSequenceClassification", _StubModel):
            mage.MageDetector()._load()
    finally:
        _reset_state()
    assert len(calls) == 2, calls
    assert calls[1]["local_files_only"] is True


def test_transient_reset_error_with_no_cache_still_goes_dead():
    """Transport error + no cache: the retry fails too, so the original error
    propagates and the detector goes dead (nothing to load from)."""
    _reset_state()

    def dead_net(repo_id, **kwargs):
        raise ssl.SSLError("simulated TLS handshake failure")

    try:
        with patch("huggingface_hub.snapshot_download", side_effect=dead_net), \
             patch("transformers.AutoTokenizer", _StubTok), \
             patch("transformers.AutoModelForSequenceClassification", _StubModel):
            with pytest.raises(ssl.SSLError):
                mage.MageDetector().score("some text")
        assert mage.MageDetector._dead is True
        # dead detectors abstain (None) instead of raising on later calls
        assert mage.MageDetector().score("some text") is None
    finally:
        _reset_state()


def test_non_transport_error_does_not_retry_cache():
    """An error that means 'the remote actively refused' (not a transport
    blip) must not trigger the cache-only retry — it propagates immediately."""
    _make_cached_dir()
    _reset_state()
    calls = []

    def refused(repo_id, **kwargs):
        calls.append(kwargs)
        raise RuntimeError("simulated config-level failure")

    try:
        with patch("huggingface_hub.snapshot_download", side_effect=refused), \
             patch("transformers.AutoTokenizer", _StubTok), \
             patch("transformers.AutoModelForSequenceClassification", _StubModel):
            with pytest.raises(RuntimeError):
                mage.MageDetector()._load()
    finally:
        _reset_state()
    assert len(calls) == 1, calls  # no cache-only retry for non-transport errors
