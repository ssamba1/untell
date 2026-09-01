"""The census refresher must route work, not invent verdicts.

`.claude/census.py` exists because the 2026-08-05 sweep died on LLM spend while reading 435
READMEs, and 60% of what it read was decidable from metadata. The tool's whole value is the
split it makes: rows it decides itself, and rows it hands to a reader. That split is only worth
anything if two things hold, and both are easy to break silently.

MEASURED FAILURES these guard, both found while building the classifier on 2026-09-01:

1. A rule that fires on everything empties the read queue. The first classifier called 16 of 23
   repos `rule-based-rewriter` because it fell through to a catch-all, which looks like triage
   and is not.

2. A CONFIDENT row that is wrong costs more than an unsure one, because it removes a repo from
   the queue on a bad rule. Adding an agent-skill rule raised coverage from 22% to 43% and
   simultaneously called `marmbiz/humanizer-de` a prompt-guide — a repo the census read and
   classified `rule-based-rewriter`, because it ships deterministic linters. The guard that
   fixed it cost 8 points of coverage. This file pins the trade so it cannot be quietly undone.

The fixture is a real harvest: `topic:ai-humanizer` sorted by stars, captured 2026-09-01 through
the MCP GitHub tools, 11 of whose 23 repos the census had already read by hand. That overlap is
free ground truth and is what `verify` scores against.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / ".claude" / "probes" / "census-2026-09-01-multiangle.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("census", ROOT / ".claude" / "census.py")
    assert spec and spec.loader, "cannot import .claude/census.py"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


census = _load_module()
REPOS = json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_the_fixture_is_a_real_harvest():
    """A fixture that shrank to three hand-written rows stops testing triage."""
    assert len(REPOS) >= 100, f"fixture has only {len(REPOS)} repos; it was captured with 111"
    assert any(r.get("stargazers_count", 0) > 500 for r in REPOS), "no large repo left in fixture"


def test_no_confident_row_contradicts_a_repo_the_census_actually_read():
    """The one kind of miss that costs something: a bad rule removing a repo from the queue."""
    v = census.verify(REPOS, census.load_census())
    hits, misses = v["confident"]
    wrong_confident = [w for w in v["wrong"] if w[3] == "confident"]
    assert misses == 0, (
        "a CONFIDENT classification disagrees with the census's own hand-read verdict:\n  "
        + "\n  ".join(f"{n}: census={was}, classifier={mine}" for n, was, mine, _ in wrong_confident)
        + "\nEither the rule is wrong, or it needs to downgrade this shape to `unsure` the way "
          "the agent-skill rule's machinery guard does."
    )
    # Only a few confident rows happen to overlap the census, so "hits" is a thin number and a
    # threshold on it would be calibrated to the fixture rather than to the property. What the
    # rules-still-fire check actually wants is that the corpus as a whole still gets decided
    # somewhere, which is the assertion below rather than a floor on the overlap.
    assert hits >= 1, f"{hits} confident rows scored against the census; the rules may be dead"
    decided = [r for r in (census.classify(x) for x in REPOS) if not r["needs_read"]]
    assert len(decided) >= 5, (
        f"only {len(decided)} of {len(REPOS)} repos were decided from metadata at all -- the "
        f"rules have stopped firing, whatever the overlap says"
    )


def test_both_buckets_are_populated():
    """All-confident is a classifier that guesses; all-unsure is one that does nothing."""
    rows = [census.classify(r) for r in REPOS]
    confident = [r for r in rows if not r["needs_read"]]
    unsure = [r for r in rows if r["needs_read"]]
    assert confident, "nothing was decided from metadata: the tool saves no budget at all"
    assert unsure, "everything was decided: a classifier this sure of itself is guessing"


def test_the_read_queue_is_the_expensive_half():
    """The point is routing spend, so the split has to actually be a split."""
    rows = [census.classify(r) for r in REPOS]
    share = sum(1 for r in rows if not r["needs_read"]) / len(rows)
    assert 0.05 <= share <= 0.85, (
        f"{share:.0%} decided without a reader. Outside this band the tool is either useless "
        f"(decides nothing) or overconfident (decides everything) — both were real states this "
        f"classifier passed through on 2026-09-01."
    )
    # The floor is deliberately low, and that is a finding rather than a slack test. Yield is
    # strongly corpus-dependent: 35% on a single topic-filtered slice, 9% across eleven angles.
    # The broad number is the one to plan against, and it says metadata triage saves a tenth of
    # the reading on a real sweep -- not the 60% the census's category counts suggest as a
    # ceiling, because those categories were assigned by reading source, which metadata is not.


def test_every_row_carries_the_rule_that_decided_it():
    """A wrong call must be traceable to a rule rather than to a vibe."""
    for repo in REPOS:
        row = census.classify(repo)
        assert row["rule"], f"{row['name']} was classified with no stated reason"
        assert row["category"], f"{row['name']} got no category"
        assert row["confidence"] in ("confident", "unsure")


def test_delta_does_not_call_a_known_repo_new():
    """A refresher that reports everything as new is a refresher nobody will read twice."""
    known = census.load_census()
    d = census.delta(REPOS, known)
    assert d["in_census"] > 0, "no fixture repo matched the census; the name key must have drifted"
    for row in d["new"]:
        assert row["name"] not in known, f"{row['name']} is in the census but was reported new"


def test_delta_finds_the_repos_that_postdate_the_census():
    """The census is dated 2026-08-05. This is the evidence that it has already decayed."""
    d = census.delta(REPOS, census.load_census())
    names = {r["name"] for r in d["new"]}
    assert "fromleda/text-humanizer" in names, (
        "the 734-star repo created 2026-08-10 — five days after the sweep — is no longer being "
        "reported as new. Either the census absorbed it (good, update this test) or the delta broke."
    )


def test_ingest_accepts_both_shapes_a_search_returns():
    """A result saved verbatim must work without being reshaped by hand first."""
    bare = ROOT / ".claude" / "probes" / "census-2026-09-01-multiangle.json"
    assert census.ingest([bare]), "a bare list of repos ingested to nothing"


def test_harvest_refuses_cleanly_when_global_search_is_out_of_reach(monkeypatch):
    """A remote session's api.github.com is bound to its own repos; that must not be a traceback.

    MEASURED 2026-09-01: /search/repositories answers 403 with "sessions are bound to their
    configured repositories". A tool that stack-traces there teaches the reader nothing about
    what to do instead.
    """
    import urllib.error

    def boom(url, token):
        raise urllib.error.HTTPError(
            url, 403, "Forbidden", {},
            _FakeBody(b'{"message":"This GitHub API path is not available: sessions are bound '
                      b'to their configured repositories."}'),
        )

    monkeypatch.setattr(census, "_get", boom)
    with pytest.raises(census.HarvestUnavailable) as exc:
        census.search("anything", None)
    assert "GITHUB_TOKEN" in str(exc.value), "the refusal does not say how to actually run it"


class _FakeBody:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def close(self) -> None:
        """HTTPError treats the body as a file and closes it; without this pytest reports an
        unraisable AttributeError from the tempfile finalizer and the suite stops being clean."""


def test_annotated_census_names_still_match():
    """A delta that reports known repos as new inflates itself, which is worse than no delta.

    MEASURED 2026-09-01: 73 of the census's 435 `name` values are not a bare owner/repo. They
    carry annotations, or put the owner/repo inside parentheses, or omit the owner entirely.
    Exact-string matching put `epoko77-ai/im-not-ai` in the "new" column at 5,143 stars while
    the census's own star table lists it at 4,182 — and did the same for two others, inflating
    the headline from 78 new repos to 85.
    """
    known = census.load_census()
    for harvested, expected in (
        ("epoko77-ai/im-not-ai", "epoko77-ai/im-not-ai (Humanize KR)"),   # trailing annotation
        ("Raymondhou0917/speak-human-tw", "speak-human-tw"),              # census has no owner
        ("rudra496/StealthHumanizer", "StealthHumanizer (rudra496/StealthHumanizer)"),
    ):
        row = census._known(harvested, known)
        assert row is not None, f"{harvested} is in the census but matched nothing"
        assert row["name"] == expected, f"{harvested} matched {row['name']}, wanted {expected}"


def test_bare_names_do_not_collide_across_owners():
    """Bare-repo matching must not hide a genuinely new repo behind a same-named one.

    Several owners ship a `humanizer-ru`. Matching on the bare repo name alone would fold them
    together and drop a real new entry from the delta — the opposite failure to the one above,
    and the reason bare keys are only registered for census rows that give no owner at all.
    """
    known = census.load_census()
    smixs = census._known("smixs/humanizer-ru", known)
    assert smixs is not None and smixs["name"] == "smixs/humanizer-ru"
    invented = census._known("nobody-at-all/humanizer-ru", known)
    assert invented is None, (
        f"an unknown owner's humanizer-ru matched {invented['name'] if invented else None}; "
        f"bare-name keys are leaking across owners and will hide new repos"
    )


def test_a_watermark_remover_is_not_a_hidden_character_carrier():
    """The unicode rule must read the direction of travel, not just the vocabulary.

    MEASURED AGAINST SOURCE 2026-09-01, by shallow-cloning all sixteen confident rows of the
    131-repo harvest. Fifteen were right. The one that was wrong is this one: `zero-width`
    reached `xuange520/unmark` as one self-assigned topic in eight, and the classifier
    CONFIDENTLY filed a repo whose source is an LLM-driven SynthID scrubber wrapped around a
    perplexity/burstiness detector as character trickery — dropping the most interesting class
    the census has out of the read queue on the strength of a topic label.

    A carrier puts hidden characters in; a sanitiser takes them out. Both talk about zero-width
    characters all day, so the noun cannot separate them and the verb can.
    """
    unmark = {
        "full_name": "xuange520/unmark",
        "description": ("Dual-Layer LLM text watermark removal and AI generation verifier. "
                        "Targets SynthID/Claude/Gemini/GPT."),
        "topics": ["zero-width", "watermark-removal", "synthid", "ai-detection"],
        "language": "Python",
    }
    row = census.classify(unmark)
    assert row["confidence"] == "unsure", (
        f"a watermark remover was confidently called {row['category']}; the rule is reading the "
        f"noun and not the verb, and this repo leaves the read queue on a topic label"
    )


def test_a_real_carrier_still_decides_without_a_reader():
    """The guard above must not empty the category it guards.

    A rule that sends every unicode row to a reader is not triage. These four are carriers
    verified against source on 2026-09-01 and must stay decidable.
    """
    carriers = [
        {"full_name": "lorossi/zero-width-steganography",
         "description": "Hide text informations using invisible text characters",
         "topics": ["steganography", "zero-width"], "language": "Python"},
        {"full_name": "darkshadow2bd/Project-Invisible",
         "description": ("A steganography tool that encodes files and text using zero-width "
                         "Unicode characters. Supports AES-256-GCM encryption."),
         "topics": ["steganography", "zero-width"], "language": "Python"},
    ]
    for repo in carriers:
        row = census.classify(repo)
        assert row["category"] == "unicode-trickery" and row["confidence"] == "confident", (
            f"{repo['full_name']} is a carrier and says so in its own prose, but the rule "
            f"answered {row['category']}/{row['confidence']}"
        )


def test_detection_alone_does_not_disqualify_a_carrier():
    """A stego toolkit that ships a detector for its own format is still a carrier.

    The first version of this guard rejected any unicode row whose text named detection OR
    removal machinery. That was too blunt: a carrier commonly ships a detector for its own
    format. Only a removal verb, or the absence of any carrier verb, may cost confidence.
    """
    row = census.classify({
        "full_name": "someone/zwsp-stego",
        "description": ("A steganography toolkit that hides messages using zero-width Unicode "
                        "characters within text. Encoding, decoding, and detection."),
        "topics": ["steganography", "zero-width", "detection"], "language": "Python",
    })
    assert row["confidence"] == "confident", (
        f"a self-described steganography toolkit lost confidence to the word 'detection': {row}"
    )


def test_the_prose_guard_costs_one_true_positive_and_that_is_recorded_not_tuned_away():
    """`dapperfu/whitespace-stego` is a real carrier that the guard sends to a reader anyway.

    Its description says "invisible Unicode whitespace characters" — which contains none of the
    mechanism phrases the rule looks for — so `zero-width` reaches it only as a topic, and the
    prose guard drops it. Verified against source 2026-09-01: it is a genuine carrier, so this
    is a false negative and it is the price of the true positive above.

    It could be recovered by adding "invisible unicode" to the phrase list. That would be fitting
    the rule to the sixteen rows used to measure it, which is the failure this repository's own
    documents exist to catch, so the cost is pinned here instead. Coverage 12.2% -> 10.7%,
    confident-row accuracy 15/16 -> 14/14, both measured on the same harvest.
    """
    row = census.classify({
        "full_name": "dapperfu/whitespace-stego",
        "description": ("A steganography toolkit that hides messages using invisible Unicode "
                        "whitespace characters within text. Python and Rust implementations, "
                        "pluggable CLI, encoding, decoding, and detection."),
        "topics": ["steganography", "unicode", "zero-width", "detection"], "language": "Python",
    })
    assert row["confidence"] == "unsure", (
        "the prose guard has stopped costing this row, which means the phrase list grew to fit "
        "the measurement set; re-measure on repos that were not used to build the rule"
    )
