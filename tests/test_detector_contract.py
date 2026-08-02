"""Contract tests for the Detector protocol — the class-level guard for this repo's #1 bug.

FIVE separate adapters shipped the same defect this session: on a failure or an unexpected response
they returned a fabricated mid-score instead of None.

    mage / hc3_roberta / perplexity_burstiness   returned 0.5 on load failure
    browser_check.check()                        returned 0.5 when it could not parse a percentage
    GPTZeroDetector                              defaulted to 0.5 when both score fields were absent
    ZeroGPTDetector                              defaulted to 50 when the field was absent

Each was fixed individually. That does not stop a sixth: the rule lives in a docstring, so nothing
mechanically enforces it. These tests do.

Why a fabricated score is worse than no score: ``score_text`` EXCLUDES a detector that returns None,
but folds a number into the ensemble. A fake 0.5 therefore enters the numeric list, drives ``max()``
— the value the whole loop optimises against — and suppresses the ``all_checkers_failed`` /
``scored: False`` guards that exist to signal exactly this situation. The loop then optimises
against, and can declare a pass on, a number no detector ever produced.
"""
from __future__ import annotations

import pytest

# (module path, class name) for every adapter whose failure path we can drive without network/models.
COMMERCIAL = [
    ("GPTZeroDetector", "GPTZERO_API_KEY", {"documents": [{"class_probabilities": {"human": 0.9}}]}),
    ("GPTZeroDetector", "GPTZERO_API_KEY", {"documents": [{}]}),
    ("ZeroGPTDetector", "ZEROGPT_API_KEY", {"data": {"unexpected": 1}}),
    ("ZeroGPTDetector", "ZEROGPT_API_KEY", {"data": {}}),
]


@pytest.mark.parametrize("cls_name,env_var,response", COMMERCIAL)
def test_commercial_adapter_returns_none_on_unusable_response(monkeypatch, cls_name, env_var, response):
    """An API response missing its score field has told us NOTHING. Returning a number invents a
    verdict the user is paying for."""
    import untell.detectors.commercial as c

    monkeypatch.setenv(env_var, "test-key")
    monkeypatch.setattr(c, "_post_json", lambda *a, **k: response)

    det = getattr(c, cls_name)()
    result = det.score("some text to score here")
    assert result is None, (
        f"{cls_name} fabricated {result!r} from a response with no score field — it would enter the "
        f"ensemble, drive max(), and suppress the all-failed guard"
    )


@pytest.mark.parametrize("cls_name,env_var", [
    ("GPTZeroDetector", "GPTZERO_API_KEY"),
    ("ZeroGPTDetector", "ZEROGPT_API_KEY"),
    ("OriginalityDetector", "ORIGINALITY_API_KEY"),
    ("WinstonDetector", "WINSTON_API_KEY"),
    ("SaplingDetector", "SAPLING_API_KEY"),
])
def test_commercial_adapter_never_returns_a_number_when_the_call_fails(monkeypatch, cls_name, env_var):
    """A transport/auth failure must not be reported as a low (or any) AI score."""
    import untell.detectors.commercial as c

    monkeypatch.setenv(env_var, "test-key")

    def _boom(*a, **k):
        raise RuntimeError("network is down")

    monkeypatch.setattr(c, "_post_json", _boom)

    det = getattr(c, cls_name)()
    try:
        result = det.score("some text to score here")
    except Exception:
        return  # raising is fine — score_text catches it and EXCLUDES the detector
    assert result is None, f"{cls_name} returned {result!r} instead of None/raise on a failed call"


def test_local_detector_returns_none_for_empty_text():
    """Empty input carries no signal. Returning a number here made score_text("") report an empty
    string as AI-generated with flagged=True."""
    from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector

    det = PerplexityBurstinessDetector()
    for text in ("", "   ", "\n\t "):
        assert det.score(text) is None


def test_score_text_excludes_none_but_would_include_a_number(monkeypatch):
    """Pins WHY the contract matters, so the reason cannot drift out of the docstring.

    A detector returning None is excluded; one returning a number is folded into max(). That is the
    entire mechanism by which a fabricated 0.5 corrupts the loop."""
    import untell.scripts.score as sc

    class _D:
        def __init__(self, name, value):
            self.name, self.tier, self._v = name, "lite", value

        def available(self):
            return True

        def score(self, text):
            return self._v

    monkeypatch.setattr(sc, "load_detectors", lambda tier="lite": [_D("d0", None)])
    r = sc.score_text("some text here", tier="lite")
    assert r["scored"] is False and r["flagged"] is False  # excluded -> no verdict invented

    monkeypatch.setattr(sc, "load_detectors", lambda tier="lite": [_D("d0", 0.5)])
    r = sc.score_text("some text here", tier="lite")
    assert r["max"] == 0.5 and r["flagged"] is True  # a fabricated 0.5 WOULD have pinned the loop


def test_no_detector_load_requires_accelerate():
    """`device_map=` routes model loading through `accelerate`, which the runtime extras do not
    declare — it only appears under the training extra.

    local_judge passed `device_map=device`, so `available()` reported True on any install with
    torch and transformers, and then EVERY `score()` call raised:

        ValueError: Using a `device_map` ... requires `accelerate`

    A detector that advertises itself as available and cannot produce a number is the same failure
    as one that produces a constant: the loop is optimising against a signal that is not there.
    For a single device `.to(device)` places the model identically with no extra dependency.

    Scanned across the WHOLE package, not just detectors/: the first version of this guard looked
    only at `untell/detectors/`, and `untell/rewriter/local_policy.py` was setting
    `device_map="auto"` the entire time. Restricting a guard to where the bug was last found is how
    the next instance survives.

    `local_policy.py` is the one allowed use — a policy model may genuinely not fit one GPU — and
    it earns the exception by checking `accelerate` is importable first and failing with a message
    that names the fix, the way its 4-bit branch already does for bitsandbytes.
    """
    import pathlib

    import untell

    root = pathlib.Path(untell.__file__).parent
    allowed = {"local_policy.py"}
    offenders = []
    for path in sorted(root.rglob("*.py")):
        if path.name in allowed:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "device_map" in stripped:
                offenders.append(f"{path.relative_to(root)}:{i}: {stripped}")
    assert not offenders, (
        "model loading must not use device_map (it hard-requires `accelerate`, which is not a "
        "runtime dependency):\n  " + "\n  ".join(offenders)
    )


def test_local_policy_checks_for_accelerate_before_using_device_map():
    """The allowed exception has to actually be safe: it must detect the missing dependency itself
    rather than letting from_pretrained die with "Using a `device_map` ... requires `accelerate`"."""
    import pathlib

    import untell.rewriter.local_policy as lp

    src = pathlib.Path(lp.__file__).read_text(encoding="utf-8")
    device_map_line = next(
        i for i, line in enumerate(src.splitlines())
        if 'kw["device_map"]' in line
    )
    preceding = "\n".join(src.splitlines()[max(0, device_map_line - 14): device_map_line])
    assert "accelerate" in preceding, (
        "device_map is set without first checking that accelerate is importable"
    )


def _stub(value, raises=False):
    class _D:
        name, tier = "d0", "lite"

        def available(self):
            return True

        def score(self, text):
            if raises:
                raise RuntimeError("boom")
            return value

    return _D()


def test_nan_score_is_excluded_not_folded_in(monkeypatch):
    """NaN is neither < 0 nor > 1, so it slid through the range clamp untouched.

    Downstream that is the most dangerous value a detector can emit: max and mean become NaN,
    `NaN >= threshold` evaluates False so `flagged` reads False — a confident "this text is human"
    manufactured by a broken detector — and json.dumps writes a bare NaN, which no strict JSON
    parser accepts.
    """
    import untell.scripts.score as sc

    monkeypatch.setattr(sc, "load_detectors", lambda tier="lite": [_stub(float("nan"))])
    r = sc.score_text("A reasonably long sentence for scoring purposes here.", tier="lite")

    assert r["detectors"]["d0"] is None
    assert "d0" in r["failed_detectors"]
    assert r["scored"] is False           # no verdict invented
    assert r["max"] == r["max"]           # not NaN
    assert r["flagged"] is False and "warning" in r


def test_non_numeric_score_excludes_the_detector_instead_of_crashing(monkeypatch):
    """`float(val)` sat outside the try that guards `d.score()`, so an adapter returning a string
    (an error message, say) raised ValueError out of score_text and took down the whole call —
    every other detector's work with it."""
    import untell.scripts.score as sc

    monkeypatch.setattr(
        sc, "load_detectors", lambda tier="lite": [_stub("rate limit exceeded"), _stub(0.9)]
    )
    r = sc.score_text("A reasonably long sentence for scoring purposes here.", tier="lite")
    assert r["max"] == 0.9  # the working detector still counted
    assert "d0" in r["failed_detectors"]
