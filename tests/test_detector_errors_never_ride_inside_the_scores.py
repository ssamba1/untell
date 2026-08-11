"""A map of numbers must not contain a string, on any surface that returns one.

Internally a score result carries a failed detector's message inside the same mapping as the scores
— `{"hc3_roberta": None, "hc3_roberta__error": "..."}` — a deliberate convention every in-repo
consumer knows. `api_server._numeric_detectors` existed to strip it before answering an HTTP client,
with a docstring naming the exact failure: `max(detectors.values())` raises `TypeError: '>' not
supported between instances of 'str' and 'float'`, and the field looks like a map of numbers because
in every other response it is one.

It was called on `/score` and nowhere else. MEASURED with three detectors broken on purpose:

    /score      detectors all numeric-or-null, detector_errors populated
    /humanize   post.detectors -> {'perplexity_burstiness': 0.1111, 'roberta_openai': None,
                'roberta_openai__error': 'broken on purpose', ...}, detector_errors None
                — mixed float / NoneType / str, and TWO such dicts per response (`pre` and `post`)
    MCP         no normalisation at all, on either tool

So the endpoint returning two score dicts normalised neither, and the surface with no HTTP layer to
hide behind had nothing. The helper moved to `untell/scripts/score.py`, recurses into `pre` and
`post`, and all three surfaces read it.

The LIBRARY shape is unchanged on purpose: `__error` sidecars are the internal convention, in-repo
consumers filter on the suffix, and changing it would be a breaking change for a problem the network
boundary is the right place to solve.
"""

from __future__ import annotations

import logging

import pytest

import untell.scripts.score as score_module
from untell.scripts.score import DETECTOR_ERROR_SUFFIX, split_detector_errors

TEXT = (
    "It is worth noting that this pivotal approach leverages a robust framework for delivery "
    "today, and the comprehensive solution underscores a seamless outcome for every stakeholder."
)


class _Boom:
    tier = "full"

    def __init__(self, name: str) -> None:
        self.name = name

    def score(self, text: str) -> float:
        raise RuntimeError("broken on purpose")


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture
def _broken_models(monkeypatch):
    real = score_module.load_detectors
    monkeypatch.setattr(
        score_module,
        "load_detectors",
        lambda tier: [
            d if d.name == "perplexity_burstiness" else _Boom(d.name) for d in real(tier)
        ],
    )


def _assert_clean(scores: dict, errors: dict | None) -> None:
    assert scores, "premise: there must be detectors to check"
    assert not any(k.endswith(DETECTOR_ERROR_SUFFIX) for k in scores), scores
    assert all(v is None or isinstance(v, (int, float)) for v in scores.values()), scores
    assert errors, "premise: a detector must actually have failed"


def test_the_library_keeps_its_internal_convention(_broken_models) -> None:
    """Guards the guard, and the scope of the fix. The sidecars stay where in-repo consumers expect
    them; only the network boundary normalises."""
    result = score_module.score_text(TEXT, tier="full")
    assert any(k.endswith(DETECTOR_ERROR_SUFFIX) for k in result["detectors"])


def test_the_helper_splits_a_flat_result(_broken_models) -> None:
    cleaned = split_detector_errors(score_module.score_text(TEXT, tier="full"))
    _assert_clean(cleaned["detectors"], cleaned.get("detector_errors"))


def test_the_helper_reaches_nested_score_dicts() -> None:
    """`pre` and `post` are the two that were going out raw."""
    raw = {
        "final": "x",
        "pre": {"detectors": {"a": None, "a__error": "boom", "b": 0.5}},
        "post": {"detectors": {"a": None, "a__error": "boom", "b": 0.4}},
    }
    cleaned = split_detector_errors(raw)
    for key in ("pre", "post"):
        _assert_clean(cleaned[key]["detectors"], cleaned[key].get("detector_errors"))
    assert raw["pre"]["detectors"].get("a__error") == "boom", "must not mutate the caller's dict"


def test_a_healthy_result_is_returned_unchanged() -> None:
    """No `detector_errors` key when nothing failed — an always-present empty map would read as
    'these detectors reported errors' to anyone scanning for the field."""
    healthy = {"detectors": {"a": 0.5, "b": 0.1}}
    assert split_detector_errors(healthy) is healthy


def test_the_humanize_endpoint_normalises_both_score_dicts(_broken_models) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from untell.api_server import app

    body = TestClient(app).post(
        "/humanize",
        json={"text": TEXT, "tier": "full", "rewriter": "structural",
              "max_iters": 1, "best_of": 1},
    ).json()
    for key in ("pre", "post"):
        _assert_clean(body[key]["detectors"], body[key].get("detector_errors"))


def test_every_surface_reads_one_definition() -> None:
    """Three copies of this rule is how the second surface came to be missing it."""
    import inspect

    from untell import mcp_server
    from untell.api_server import _numeric_detectors

    assert "split_detector_errors" in inspect.getsource(_numeric_detectors)
    assert inspect.getsource(mcp_server).count("split_detector_errors") >= 3
