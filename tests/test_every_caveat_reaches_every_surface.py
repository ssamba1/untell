"""A caveat that reaches one surface and not another is a caveat the reader may never see.

FOUND by asking "which surfaces did this reach?" mechanically instead of one caveat per loop. The
first sweep, over three surfaces:

    caveat             score_text   untell_text   verify
    no prose              yes          yes         NO
    mostly locked         yes          yes         NO
    one sentence/para     yes          yes         NO
    threshold range       yes          yes         yes

Three of four missing, and the one that arrived had been wired into `verify` by hand two loops
earlier. The cause was structural: `verify` re-derived a chosen handful of caveats instead of
forwarding the score's `warning`, so every new caveat had to be remembered there separately.
`untell_text` never had the problem because it forwards `best_score["warning"]`.

Extending the sweep to the two surfaces it had not covered: REST `/score` forwards all three, and
the MCP `score` tool does too — its only transformation, `split_detector_errors`, preserves every
key. So the gap was one surface, and it is closed.

This file is the guard that would have caught all three. Adding a caveat to `score_text` and
forgetting a surface now fails here rather than in a user's terminal.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.run import untell_text
from untell.scripts.score import score_text, split_detector_errors
from untell.scripts.verify import verify

CODE = "```python\n" + "\n".join(f"def f{i}(a, b):\n    return a + b * {i}" for i in range(20)) + "\n```"
QUOTES = (
    'The witness stated: "I arrived at the building shortly before nine and noticed the main door '
    'had been left open, which struck me as unusual given the hour." She continued: "There was '
    'nobody at the desk, and the lights on the upper floor were still off when I walked past."'
)
PER_LINE = "\n\n".join([
    "Salt lowers the freezing point of water, which is why councils spread it on the roads.",
    "It works down to about minus nine degrees, below which other chemicals are needed.",
    "The grit itself does a second job on the surface of the road once it is down.",
    "It gives tyres something to bite on once the ice has gone soft near the kerb.",
    "That matters more on a hill than it ever does on the flat part of the route.",
])
PROSE = (
    "Salt lowers the freezing point of water, which is why councils spread it on roads in winter. "
    "It works down to about minus nine degrees, below which other chemicals are needed instead."
)

# (name, the phrase that identifies it, input, extra kwargs)
CAVEATS = [
    ("no prose", "no prose lines", CODE, {}),
    ("mostly locked", "preserved material", QUOTES, {}),
    ("one sentence per paragraph", "one sentence per paragraph", PER_LINE, {}),
    ("threshold out of range", "probabilities in [0, 1]", PROSE, {"threshold": 45.0}),
]
IDS = [c[0] for c in CAVEATS]


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize("name,mark,text,kwargs", CAVEATS, ids=IDS)
def test_score_text_says_it(name: str, mark: str, text: str, kwargs: dict) -> None:
    """The premise for every surface below: they all read what this one decided to say."""
    assert mark in (score_text(text, tier="lite", **kwargs).get("warning") or "")


@pytest.mark.parametrize("name,mark,text,kwargs", CAVEATS, ids=IDS)
def test_untell_text_forwards_it(name: str, mark: str, text: str, kwargs: dict) -> None:
    result = untell_text(
        text, tier="lite", max_iters=1, rewriter="structural", best_of=1, seed=1,
        threshold=kwargs.get("threshold", 0.3),
    )
    assert mark in (result.get("warning") or "")


@pytest.mark.parametrize("name,mark,text,kwargs", CAVEATS, ids=IDS)
def test_verify_forwards_it(name: str, mark: str, text: str, kwargs: dict) -> None:
    """The surface that exits non-zero, and the one that was missing three of these four."""
    assert mark in (verify(text, tier="lite", **kwargs).get("warning") or "")


@pytest.mark.parametrize("name,mark,text,kwargs", CAVEATS, ids=IDS)
def test_the_mcp_transformation_preserves_it(name: str, mark: str, text: str, kwargs: dict) -> None:
    """The MCP `score` tool returns `split_detector_errors(score_text(...))`, so that helper is the
    entire path between the two. It must not drop a key on the way."""
    raw = score_text(text, tier="lite", **kwargs)
    out = split_detector_errors(raw)
    assert mark in (out.get("warning") or "")
    assert not set(raw) - set(out), sorted(set(raw) - set(out))


@pytest.mark.parametrize("name,mark,text,kwargs", CAVEATS, ids=IDS)
def test_the_rest_surface_forwards_it(name: str, mark: str, text: str, kwargs: dict) -> None:
    """REST is skipped rather than assumed when FastAPI is absent — CI installs the MCP path as
    `.[dev,mcp]` with no web framework, and a hard import would fail the whole file there."""
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from untell.api_server import app

    client = fastapi_testclient.TestClient(app)
    payload = {"text": text, "tier": "lite", **kwargs}
    response = client.post("/score", json=payload)
    # Two honest answers, and REST gives a different one for the threshold case: its schema REFUSES
    # a value outside [0, 1] with a 422 —
    #
    #     {"loc": ["body","threshold"], "msg": "Input should be less than or equal to 1"}
    #
    # — which is stronger than a caveat, because the caller cannot read past it. The library and CLI
    # accept the value and warn, on the ground that the fallback is documented behaviour. What no
    # surface may do is accept it in silence, so that is what this asserts.
    if response.status_code == 422:
        assert "threshold" in response.text
        return
    assert response.status_code == 200, response.text
    assert mark in (response.json().get("warning") or "")


def test_ordinary_prose_reaches_no_caveat_on_any_surface() -> None:
    """Guards the guard. If every surface reported every phrase unconditionally, each assertion
    above would pass without forwarding anything."""
    for mark in (c[1] for c in CAVEATS):
        assert mark not in (score_text(PROSE, tier="lite").get("warning") or "")
        assert mark not in (verify(PROSE, tier="lite").get("warning") or "")
