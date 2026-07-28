"""Tests for io_utils — UTF-8 configuration and stdin helpers."""
from __future__ import annotations

import io
import sys

from untell.scripts.io_utils import configure_utf8_io


class TestConfigureUtf8Io:
    """Must not crash on any platform, and must configure stdout/stderr for UTF-8."""

    def test_returns_none(self):
        assert configure_utf8_io() is None

    def test_does_not_crash_when_stdout_is_bytes(self):
        orig = sys.stdout
        sys.stdout = io.BytesIO()
        try:
            configure_utf8_io()
        finally:
            sys.stdout = orig

    def test_does_not_crash_when_stdout_is_none(self):
        orig = sys.stdout
        sys.stdout = None
        try:
            configure_utf8_io()
        finally:
            sys.stdout = orig

    def test_does_not_crash_when_stderr_is_none(self):
        orig = sys.stderr
        sys.stderr = None
        try:
            configure_utf8_io()
        finally:
            sys.stderr = orig

    def test_idempotent(self):
        assert configure_utf8_io() is None
        assert configure_utf8_io() is None
