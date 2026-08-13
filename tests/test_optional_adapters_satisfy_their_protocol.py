"""The adapters nobody can run in the default configuration still have to satisfy their interface.

FOUND by following Result 178: paths unreachable in the default configuration are the ones that ship
broken, because nothing the author runs touches them. Writing a stub commercial detector for that
result raised `AttributeError: 'Stub' object has no attribute 'tier'`, which is worth tracing rather
than patching around — the attribute is not read by `verify` at all:

    verify.py:66   ->  score.py:314 (score_text)  ->  base.py:300 (load_detectors)

`commercial_detectors()` feeds the ordinary detector registry, so an adapter missing `tier` breaks
`score_text`, the main scoring entry point, for anyone with an API key configured. Nobody without
one would ever see it.

MEASURED, all six adapters against the protocol `load_detectors` requires:

    OriginalityDetector  WinstonDetector  GPTZeroDetector
    SaplingDetector      ZeroGPTDetector  CopyleaksDetector      6/6 conform, tier='commercial'

**No defect.** The interface is satisfied today and held in place by nothing but habit, which is what
this file replaces.

The browser checkers are a different interface and are checked against their own: `verify` drives
them with `available()` and `check()` and keys the row by the site name it was given, never reading
`name`, `tier` or `score`. Measuring them against the detector protocol reports three missing
attributes and means nothing — the first version of this sweep did exactly that.
"""

from __future__ import annotations

import inspect

import pytest

import untell.browser_check as browser_check
import untell.detectors.commercial as commercial

DETECTOR_PROTOCOL = ("name", "tier", "available", "score")
BROWSER_PROTOCOL = ("available", "check")


def _classes(module, suffix: str) -> list[tuple[str, type]]:
    return [
        (name, obj)
        for name, obj in vars(module).items()
        if inspect.isclass(obj) and name.endswith(suffix) and obj.__module__ == module.__name__
    ]


COMMERCIAL = _classes(commercial, "Detector")
BROWSER = _classes(browser_check, "Checker")


def test_the_sweep_found_the_adapters() -> None:
    """Premise. An import that quietly returned nothing would make every assertion below vacuous —
    which is the exact failure mode this file exists to catch in the product."""
    assert len(COMMERCIAL) >= 5, [n for n, _ in COMMERCIAL]
    assert BROWSER, [n for n, _ in BROWSER]


@pytest.mark.parametrize("name,cls", COMMERCIAL, ids=[n for n, _ in COMMERCIAL])
def test_every_commercial_adapter_satisfies_the_detector_protocol(name: str, cls: type) -> None:
    """`load_detectors` reads all four. A missing one is an AttributeError inside `score_text`."""
    missing = [attr for attr in DETECTOR_PROTOCOL if not hasattr(cls, attr)]
    assert not missing, f"{name} is missing {missing}"


@pytest.mark.parametrize("name,cls", COMMERCIAL, ids=[n for n, _ in COMMERCIAL])
def test_every_commercial_adapter_declares_a_usable_tier(name: str, cls: type) -> None:
    """`load_detectors` filters on this value. A typo here removes the detector from every tier
    silently — it does not raise, it simply never runs, which is worse."""
    assert cls.tier in {"lite", "full", "heavy", "commercial"}, (name, cls.tier)


@pytest.mark.parametrize("name,cls", BROWSER, ids=[n for n, _ in BROWSER])
def test_every_browser_checker_satisfies_its_own_protocol(name: str, cls: type) -> None:
    """A different interface, checked against itself: `verify` calls `available()` and `check()` and
    keys the row by the site string it was handed."""
    missing = [attr for attr in BROWSER_PROTOCOL if not hasattr(cls, attr)]
    assert not missing, f"{name} is missing {missing}"


def test_the_check_can_fail() -> None:
    """Vacuity check. The attribute sweep must be able to report a missing member, or a green run
    says only that the loop ran."""

    class _Incomplete:
        name = "incomplete"

        def available(self) -> bool:
            return True

    missing = [attr for attr in DETECTOR_PROTOCOL if not hasattr(_Incomplete, attr)]
    assert missing == ["tier", "score"]


def test_load_detectors_is_what_reads_tier() -> None:
    """Pins the reason, not just the rule. If the registry stopped reading `tier` this file would
    still pass and would be enforcing a requirement that no longer exists."""
    import untell.detectors.base as base

    assert "tier" in inspect.getsource(base.load_detectors)
