"""A flagged sentence can carry checkable markers — and must not claim they are the detector's reason.

Two refereed results made interpretability a requirement rather than a nicety. ExaGPT
(2026.findings-acl.380) argues a detection decision has to let a user "judge how reliably correct its
prediction is", and shows in a human study that per-span evidence helps them do it. DAMASHA
(2026.findings-eacl.326) ships attribution overlays for mixed-authorship segmentation with its own
human study. This repository's round-five finding is why it matters: a bare label changes how a
reader judges text even when the label is wrong, so "a human will review the flag" fails when the
flag is all the human gets.

`score_sentences(evidence=True)` attaches the catalogue tells found inside each sentence. The hard
part is not producing them — it is refusing to overclaim what they are. **The tells catalogue is not
the detector.** ExaGPT's evidence *is* its decision procedure; ours is a separate heuristic run over
the same sentence, and the `ai` score never consults it. Presenting corroboration as explanation
would be a fabricated rationale, which is worse than offering none. These tests pin both halves:
the evidence is there, and it does not lie about itself.
"""

from __future__ import annotations

import inspect

import pytest

from untell.scripts.sentences import score_sentences

TELL_HEAVY = "It is important to note that the framework leverages robust methodology."
PLAIN = "Rain fell."


def test_evidence_is_absent_unless_asked_for():
    """Default output shape is unchanged; every existing consumer keeps working."""
    result = score_sentences(f"{TELL_HEAVY} {PLAIN}", tier="lite")
    assert all("evidence" not in row for row in result["sentences"])
    assert "evidence_note" not in result


def test_evidence_names_the_actual_strings_found():
    """A category count is not checkable by a human. The literal span is."""
    result = score_sentences(TELL_HEAVY, tier="lite", evidence=True)
    matches = result["sentences"][0]["evidence"]["matches"]
    flat = [m for hits in matches.values() for m in hits]
    assert flat, "no markers surfaced for a sentence built from catalogue tells"
    for span in flat:
        assert span.lower() in TELL_HEAVY.lower(), (
            f"{span!r} is offered as evidence but does not appear in the sentence"
        )


def test_a_sentence_with_no_tells_reports_none_rather_than_inventing_some():
    result = score_sentences(PLAIN, tier="lite", evidence=True)
    assert result["sentences"][0]["evidence"]["tells"] == 0
    assert not result["sentences"][0]["evidence"]["matches"]


def test_the_note_refuses_to_call_this_an_explanation():
    """The overclaim this feature is one step away from. If the wording ever says the evidence is
    *why* the detector scored, the tool is fabricating a rationale for a number computed by
    something that never saw the catalogue."""
    note = score_sentences(PLAIN, tier="lite", evidence=True)["evidence_note"].lower()
    assert "corroborate" in note, "the note must say the markers corroborate the score"
    assert "do not explain" in note, "the note must deny that they explain the score"
    assert "never consults" in note or "not as the reason" in note


def test_evidence_is_independent_of_the_score():
    """The claim in the note, tested rather than asserted: a sentence can carry tells while scoring
    low. If evidence and score moved together this feature would be redundant, and the note would be
    the wrong description of it."""
    result = score_sentences(TELL_HEAVY, tier="lite", evidence=True)
    row = result["sentences"][0]
    assert row["evidence"]["tells"] > 0
    # The detector's number is its own; the assertion is only that the two are separately sourced.
    assert isinstance(row["ai"], float)
    from untell.scripts.tells import score_tells
    assert score_tells(TELL_HEAVY)["tells"] == row["evidence"]["tells"], (
        "evidence must be the catalogue's own count, not a value derived from the score"
    )


def test_evidence_rejects_a_non_boolean():
    with pytest.raises(TypeError, match="evidence must be bool"):
        score_sentences(PLAIN, tier="lite", evidence="yes")


def test_the_cli_prints_the_markers_and_the_caveat(capsys):
    from untell.scripts.sentences import main

    assert main([TELL_HEAVY, "--evidence"]) == 0
    out = capsys.readouterr().out
    assert "evidence · " in out, "the CLI should show the markers it found"
    assert "corroborate" in out.lower(), "the CLI must carry the caveat, not just the JSON"


def test_the_cli_stays_quiet_without_the_flag(capsys):
    from untell.scripts.sentences import main

    assert main([TELL_HEAVY]) == 0
    assert "evidence · " not in capsys.readouterr().out


# --- the same feature on every surface -----------------------------------------------------------
#
# `untell/mcp_server.py` carries comments about `tier` and `threshold` having once disagreed between
# REST and MCP: the same named operation answered differently depending on which door a caller used.
# Shipping `--evidence` on the CLI alone would have rebuilt that defect deliberately, three rounds
# after writing it down. These tests hold the three surfaces together.


def _api_client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from untell.api_server import app

    return TestClient(app)


def test_the_rest_endpoint_offers_evidence_too():
    body = {"text": TELL_HEAVY, "evidence": True}
    payload = _api_client().post("/sentences", json=body).json()
    assert "evidence_note" in payload
    matches = payload["sentences"][0]["evidence"]["matches"]
    assert any(hits for hits in matches.values()), "REST returned no markers for a tell-heavy line"


def test_the_rest_response_shape_is_unchanged_by_default():
    """Every caller that predates this feature must see exactly what it saw before."""
    payload = _api_client().post("/sentences", json={"text": TELL_HEAVY}).json()
    assert "evidence_note" not in payload
    assert all("evidence" not in row for row in payload["sentences"])


def test_the_rest_schema_declares_the_note():
    """An undeclared field is the round-25 defect: /score returned `agreement` for releases without
    the schema mentioning it, so a generated client had no entry for it."""
    from untell.api_server import _SENTENCES_RESPONSES

    def walk(node):
        if isinstance(node, dict):
            if "note" in node and "sentences" in node:
                return node
            for value in node.values():
                found = walk(value)
                if found is not None:
                    return found
        return None

    props = walk(_SENTENCES_RESPONSES)
    assert props is not None, "could not find the /sentences property map"
    assert "evidence_note" in props, "the schema must declare `evidence_note`"
    described = props["evidence_note"]["description"].lower()
    assert "corroborate" in described and "not explain" in described


def test_the_mcp_tool_takes_evidence_and_carries_the_caveat():
    mcp = pytest.importorskip("untell.mcp_server")
    source = inspect.getsource(mcp)
    assert "evidence: bool = False" in source, "the MCP sentences tool must accept `evidence`"
    assert "fabricated" in source or "do not explain" in source, (
        "the MCP docstring must carry the corroboration caveat, not just REST and the CLI"
    )
