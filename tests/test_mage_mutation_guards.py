"""Killing tests for the mage.py mutation survivors (2026-08-14 sweep).

Testable without loading the model: the env gate, the dead latch, the empty-text
abstain. Label-resolution is only reachable through a live model load.
"""

from __future__ import annotations

from untell.detectors.mage import MageDetector


class TestAvailableEnvGate:
    def test_disabled_by_env(self, monkeypatch) -> None:
        monkeypatch.setenv("UNTELL_DISABLE_MAGE", "1")
        assert MageDetector().available() is False

    def test_enabled_without_env(self, monkeypatch) -> None:
        monkeypatch.delenv("UNTELL_DISABLE_MAGE", raising=False)
        assert MageDetector().available() is True


class TestDeadLatch:
    def test_dead_returns_none(self) -> None:
        old = MageDetector._dead
        MageDetector._dead = True
        try:
            assert MageDetector().score("some text here") is None
        finally:
            MageDetector._dead = old

    def test_empty_text_returns_none(self) -> None:
        old = MageDetector._dead
        MageDetector._dead = False
        try:
            assert MageDetector().score("   ") is None
        finally:
            MageDetector._dead = old
