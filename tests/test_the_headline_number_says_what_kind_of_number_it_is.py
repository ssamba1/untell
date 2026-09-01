"""The headline score must declare that it is a score, not a rate.

Rounds twenty to twenty-two of `docs/research-verification.md` found four published studies that
reported a **mean per-document detector score** inside a table of **false-positive rates**. Bohler's
"8.6%" is the average percentage of text within a manuscript that a detector marks AI; Popkov's
"27.2%" is a median proportion of text; Stern's "83.8% human" is a mean GPTZero score across
statements, which reads irresistibly as "16% of applicants used AI". Every one of those numbers was
quoted correctly from a paper that reports it. The error was in what kind of number it was taken to
be, and no provenance check can see that.

This repository criticises that conflation, so it must not commit it. `max`, `mean` and `ai_percent`
are per-document scores, and the surfaces that publish them say so. These tests pin that, because a
description is exactly the kind of thing a later edit trims for brevity.
"""

from __future__ import annotations

import inspect
import re

import pytest

# The two misreadings the wording exists to block, as (name, pattern) pairs.
_MUST_DENY = (
    ("a proportion of the text", re.compile(r"fraction of the text|percentage OF THE TEXT", re.I)),
    ("a proportion of documents", re.compile(r"share of (a corpus|documents)"
                                             r"|percentage OF DOCUMENTS", re.I)),
)


def _score_schema() -> dict:
    """The property map behind POST /score.

    Walked rather than indexed: the exact nesting
    (`[200]['content']['application/json']['schema']['properties']`) is an OpenAPI detail that has no
    business being duplicated in a test about wording. Searching for the map that declares both
    `max` and `ai_percent` survives a restructure of the envelope.
    """
    from untell.api_server import _SCORE_RESPONSES

    def walk(node):
        if isinstance(node, dict):
            if "ai_percent" in node and "max" in node:
                return node
            for value in node.values():
                found = walk(value)
                if found is not None:
                    return found
        return None

    found = walk(_SCORE_RESPONSES)
    if found is None:
        pytest.fail("could not locate the /score response property map in api_server")
    return found


@pytest.mark.parametrize("field", ["max", "ai_percent"])
def test_the_headline_fields_are_called_scores_not_rates(field):
    prop = _score_schema()[field]
    description = prop.get("description", "")
    assert description, f"{field} has no description at all"
    assert re.search(r"per-document score|score, not a rate|PER-DOCUMENT", description, re.I), (
        f"/score's `{field}` description must say it is a per-document score rather than a rate. "
        f"Got: {description!r}"
    )


@pytest.mark.parametrize("field", ["max", "ai_percent"])
@pytest.mark.parametrize("label,pattern", _MUST_DENY, ids=[n for n, _ in _MUST_DENY])
def test_the_description_rules_out_both_misreadings(field, label, pattern):
    """Saying what it *is* is not enough. The two wrong readings are specific and both common, so
    the wording names them."""
    description = _score_schema()[field].get("description", "")
    assert pattern.search(description), (
        f"/score's `{field}` description should rule out reading it as {label}. Got: {description!r}"
    )


def test_mean_is_disambiguated_too():
    """`mean` is the field most likely to be read as an average over a corpus, because that is what
    a mean usually is. Here it averages detectors over one document."""
    description = _score_schema()["mean"].get("description", "")
    assert "this document" in description.lower() or "per-document" in description.lower(), (
        f"`mean` must say it averages detectors for one document, not documents. Got: {description!r}"
    )


def test_the_mcp_surface_carries_the_same_warning():
    """Two surfaces returned different answers for the same operation once before, which is why the
    MCP tool's docstring exists. A caveat on one surface only is the same class of defect."""
    mcp = pytest.importorskip("untell.mcp_server")
    source = inspect.getsource(mcp)
    assert "PER-DOCUMENT SCORES" in source, (
        "the MCP `score` tool must carry the same score-versus-rate warning as the REST schema"
    )


def test_the_repo_still_reports_pre_llm_false_positives_as_a_rate():
    """The other half of the invariant. If the score is a score, the false-positive measurement has
    to be a genuine rate — documents flagged over documents scored — or the distinction this file
    defends is cosmetic."""
    from eval import pre_llm_fpr

    source = inspect.getsource(pre_llm_fpr.probe)
    assert "len(" in source, "probe should divide by a count of documents"
    doc = inspect.getdoc(pre_llm_fpr.probe) or ""
    assert re.search(r"rate|fpr|flagged", doc, re.I), (
        "pre_llm_fpr.probe should document that it returns a rate over documents"
    )
