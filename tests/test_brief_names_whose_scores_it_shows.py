"""A brief headed with one detector must never present another detector's scores as its own.

MEASURED before the fix: `brief_payload(text, name="turnitin")` (the REST/MCP default) and
`untell brief --name turnitin --detector local` ran untell's own lite detector for the stability
section and backfilled its score into the header, so a brief under "Detector: Turnitin" read
"Score: 0.176 — clear" and "The original was not flagged" for a document Turnitin had flagged.
"""

from __future__ import annotations

from untell.evidence.brief import build_brief, render_html, render_markdown
from untell.evidence.service import brief_payload

TEXT = ("School uniforms should be mandatory. Moreover, it is important to note that uniforms "
        "foster a sense of community. Furthermore, they reduce bullying and help students focus "
        "on learning rather than on fashion, which ultimately creates a better environment.")

_LOCAL_STAB = {"scorer": {"name": "untell-local-lite", "kind": "local"},
               "base": {"score": 0.176, "flagged": False},
               "summary": {"finding": "The original was not flagged."}, "variants": []}


def test_a_name_alone_skips_stability_instead_of_running_untell(monkeypatch) -> None:
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    b = brief_payload(TEXT, name="turnitin", score=0.82, flagged=True)
    assert b["stability"] is None
    assert b["observed"] == {"score": 0.82, "flagged": True}
    assert b["detector"]["name"] == "turnitin"


def test_untell_standing_in_is_labelled_and_never_backfills_the_header() -> None:
    b = build_brief(TEXT, "turnitin", stability=_LOCAL_STAB)
    assert b["observed"] == {"score": None, "flagged": None}
    assert b["stability_scored_by"]["is_the_named_detector"] is False
    md = render_markdown(b)
    assert "not turnitin's" in md and "Scored by: `untell-local-lite`" in md
    assert "0.176 — " not in md.split("## 1.")[0]
    assert "not turnitin" in render_html(b)


def test_a_brief_of_untell_itself_keeps_its_own_score() -> None:
    b = build_brief(TEXT, "local:lite", stability=_LOCAL_STAB)
    assert b["observed"]["score"] == 0.176
    assert b["stability_scored_by"]["is_the_named_detector"] is True
    assert "not local:lite's" not in render_markdown(b)


def test_hand_recorded_scores_count_as_the_named_detector() -> None:
    b = brief_payload(TEXT, name="turnitin", scores={"base": 0.9, "N3": 0.2})
    assert b["stability_scored_by"]["is_the_named_detector"] is True
    assert b["observed"]["score"] == 0.9
