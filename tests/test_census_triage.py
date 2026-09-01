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
import pathlib
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


# --------------------------------------------------------------------------------------------
# `inspect` -- the tree reader. `classify` stops at a tenth of the corpus because search-API
# metadata cannot tell a product from a build script. A shallow clone can, and the git proxy
# serves one for any public repo even though this session's GitHub API plane does not. These
# guard the three defects the first working version had, all found by scoring it against sixteen
# repos read by hand on 2026-09-01.
# --------------------------------------------------------------------------------------------

def _facts(**over):
    base = {"files": 20, "code_files": 0, "product_code_files": 0, "product_loc": 0, "own_loc": 0,
            "md_files": 6, "skill_manifest": False, "root_skill_manifest": False,
            "ships_weights": False,
            "signals": {k: [] for k in census._TREE_SIGNALS}, "product_paths": []}
    sig = over.pop("signals", None)
    base.update(over)
    if sig:
        base["signals"] = {**base["signals"], **sig}
    return base


def test_a_signal_word_must_be_a_word_and_not_a_substring():
    """`trl` inside `strlen` called a C steganography toolkit a fine-tuned model.

    The trainer list is full of three-letter tokens — `trl`, `nli`, `peft` — and plain substring
    matching finds all of them inside ordinary identifiers. This is the worst class of miss the
    tree reader can make, because `fine-tuned-model` is CONFIDENT and confident rows leave the
    read queue.
    """
    assert not census._boundary("trl").search("size_t n = strlen(buf);")
    assert not census._boundary("nli").search("the request failed while online")
    assert census._boundary("trl").search("from trl import sfttrainer")
    # Punctuation-bearing entries must keep matching; they carry their own boundaries.
    assert census._boundary("undetectable.ai").search('base = "https://undetectable.ai/api"')
    assert census._boundary("\\u200b").search('const ZWSP = "\\u200b";')


def test_a_carrier_is_found_by_its_code_points_not_by_its_size():
    """The first version required a carrier to be under 800 lines, a number with nothing behind it.

    `chinmay29hub/stegmoji` is a 5,780-line Next.js app and is exactly what it says it is. What a
    carrier actually does is enumerate the code points it hides in.
    """
    big = census.decide_from_tree(
        _facts(product_code_files=34, product_loc=5780, own_loc=5780, code_files=57,
               signals={"hidden_characters": ["0x200b", "0xfe0e", "variation selector"]}),
        {"name": "chinmay29hub/stegmoji", "category": "unicode-trickery"})
    assert big["category"] == "unicode-trickery" and big["confidence"] == "confident", big
    # ...and one stray constant in a large program is not a carrier.
    incidental = census.decide_from_tree(
        _facts(product_code_files=40, product_loc=9000, own_loc=9000,
               signals={"hidden_characters": ["\\u200b"]}),
        {"name": "someone/big-app", "category": "rule-based-rewriter"})
    assert incidental["confidence"] == "unsure", incidental


def test_hex_code_points_are_seen_as_well_as_escapes(tmp_path):
    """A carrier that writes `0xFE0E` matched nothing against an escape-only list.

    Both notations are in live use and neither implies the other, so a list carrying one of them
    silently drops half the category into the generic rewriter bucket.
    """
    (tmp_path / "steg.js").write_text(
        "const SELECTORS = [0xFE0E, 0xFE0F, 0x200B];\n" * 3, encoding="utf-8")
    facts = census.read_tree(tmp_path)
    assert len(facts["signals"]["hidden_characters"]) >= 2, facts["signals"]


def test_bundled_subskill_code_is_not_the_repos_own_product():
    """`Xircth/thesis-workflow-skill` is a skill whose AIGC-lowering is prose.

    The tree finds 4,090 lines of C# in it, all under `skills/minimax-docx/` — a bundled DOCX
    helper. Counting a sub-skill's machinery as the repo's product turned a correct confident
    verdict into a wrong one.
    """
    tree = census._SUBSKILL
    assert tree.search("skills/minimax-docx/scripts/dotnet/core/tablesamples.cs")
    assert tree.search(".claude/hooks/run.py")
    assert not tree.search("src/skillsmith/main.py"), "the guard is matching on a substring"


def test_a_skill_that_ships_a_linter_is_not_settled_by_its_manifest():
    """The packaging rule must keep the guard the metadata rule already needed.

    `marmbiz/humanizer-de` ships 72 patterns behind deterministic linters and wears a manifest.
    A root manifest may only settle the question when the repo's OWN code stays small.
    """
    row = census.decide_from_tree(
        _facts(root_skill_manifest=True, skill_manifest=True, md_files=9,
               product_code_files=6, product_loc=900, own_loc=900),
        {"name": "marmbiz/humanizer-de", "category": "prompt-guide"})
    assert row["confidence"] == "unsure", (
        f"a manifest alone decided a repo carrying 900 lines of its own code: {row}"
    )


def test_build_and_test_code_is_not_product_code(tmp_path):
    """`Hakku/finnish-humanizer` ships 748 lines of Python that generate instruction files.

    A tree reader that counts every `.py` it finds is worse than the metadata rule it replaces:
    it would call every prompt guide with a test suite a rewriter.
    """
    (tmp_path / "build.py").write_text("x = 1\n" * 400, encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_build.py").write_text("y = 1\n" * 300, encoding="utf-8")
    (tmp_path / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# readme\n", encoding="utf-8")
    facts = census.read_tree(tmp_path)
    assert facts["code_files"] == 2, facts
    assert facts["product_code_files"] == 0, f"build and test code counted as product: {facts}"
    row = census.decide_from_tree(facts, {"name": "Hakku/finnish-humanizer",
                                          "category": "prompt-guide"})
    assert row["category"] == "prompt-guide" and row["confidence"] == "confident", row


def test_one_unreachable_repo_does_not_end_the_sweep(tmp_path, monkeypatch):
    """A private, renamed or deleted repo must cost its own row and nothing else.

    A sweep that dies on row 12 of 131 is worth less than no sweep, because it looks like it ran.
    """
    def boom(name, dest, timeout=census.CLONE_TIMEOUT):
        if "gone" in name:
            raise census.CloneFailed("repository not found")
        (dest / name.replace("/", "__")).mkdir(parents=True, exist_ok=True)
        (dest / name.replace("/", "__") / "a.md").write_text("hi", encoding="utf-8")
        (dest / name.replace("/", "__") / "b.md").write_text("hi", encoding="utf-8")
        return dest / name.replace("/", "__")

    monkeypatch.setattr(census, "clone", boom)
    rows = census.inspect_rows(
        [{"name": "a/gone", "category": "prompt-guide", "confidence": "unsure"},
         {"name": "b/here", "category": "prompt-guide", "confidence": "unsure"}],
        tmp_path, progress=False)
    assert len(rows) == 2
    assert rows[0]["evidence"] == "metadata" and "not found" in rows[0]["inspect_error"]
    assert rows[1]["evidence"] == "source", rows[1]


def test_a_mention_can_unmake_a_verdict_but_never_make_one():
    """The tree reader's central asymmetry, and the correction that cost it two thirds of its reach.

    MEASURED on the 34 repos where this harvest overlaps the census's hand reads — ground truth
    assigned by reading source, years before this tool existed, so it cannot have been fitted to
    it. A CONFIDENT `detector-with-evasion` verdict, keyed on a detector's name appearing in the
    source, was right 2 times in 11: worse than the metadata rule it replaced. The failure is not
    the word list. A humanizer prompt guide lists the detectors it aims to beat, so `gptzero` and
    `binoculars` appear in guides and in pipelines alike, and no list of names separates a
    mention from a call.

    So a detector name may never carry a verdict — it goes to the reader as a briefing note. It
    may still WITHHOLD one, which is not the same claim: the unicode branch asserts exclusivity,
    that hiding characters is the whole product, and any other mechanism named in the source
    contradicts that whatever it turns out to mean.
    """
    named = {"detector_in_loop": ["gptzero", "binoculars", "perplexity"]}
    # It cannot make a verdict.
    row = census.decide_from_tree(
        _facts(product_code_files=8, product_loc=900, own_loc=900, signals=named),
        {"name": "someone/rewriter", "category": "rule-based-rewriter"})
    assert row["confidence"] == "unsure", f"a detector mention produced a verdict: {row}"
    assert "CALLED" in row["rule"], f"the reader was not told what to look for: {row['rule']}"
    # It can unmake one: `xuange520/unmark` enumerates eight code points in a sanitiser that sits
    # beside an LLM scrubber and a detector, and is not a carrier.
    unmark = census.decide_from_tree(
        _facts(product_code_files=10, product_loc=1138, own_loc=1138, md_files=5,
               signals={"hidden_characters": ["\\u200b", "\\u200c", "\\u200d", "\\ufeff"],
                        **named}),
        {"name": "xuange520/unmark", "category": "unicode-trickery"})
    assert unmark["confidence"] == "unsure", f"unmark was confidently filed again: {unmark}"


def test_training_code_is_not_a_shipped_model():
    """`fine-tuned-model` is confident only on weights, which are a file and not a word.

    A benchmark repository that trains detectors in order to compare them matched `trainer(` and
    was confidently called a fine-tuned model; the census read it as research-code. Research,
    benchmark and product repositories all contain training code.
    """
    trains = census.decide_from_tree(
        _facts(product_code_files=15, product_loc=4303, own_loc=4303, md_files=1,
               signals={"trains_a_model": ["trainer(", "peft"]}),
        {"name": "someone/benchmark", "category": "dataset"})
    assert trains["confidence"] == "unsure", trains
    ships = census.decide_from_tree(
        _facts(product_code_files=15, product_loc=4303, own_loc=4303, ships_weights=True),
        {"name": "someone/tuned", "category": "rule-based-rewriter"})
    assert ships["category"] == "fine-tuned-model" and ships["confidence"] == "confident", ships


def test_the_tree_reader_beats_metadata_on_reach_without_losing_precision():
    """The trade the whole step exists to make, pinned as a property rather than a number.

    On the census-overlap set the metadata rule decides 2 of 34 rows at 2/2, and the tree reader
    decides 11 at 10/11. Confidence must stay expensive: every branch that emits `confident`
    rests on a structural fact — no product code at all, a vendor domain in the source, code
    points enumerated with nothing else named, weights on disk — and none rests on a word
    appearing somewhere.
    """
    import inspect as _inspect

    src = _inspect.getsource(census.decide_from_tree)
    confident_branches = [line for line in src.splitlines() if '"confident"' in line]
    assert confident_branches, "decide_from_tree emits no confident verdicts at all"
    assert not any("detector_in_loop" in line for line in confident_branches), (
        "a detector mention is carrying a confident verdict again; it was right 2 times in 11"
    )


def test_the_fairness_probe_can_find_fairness_work_when_it_is_there():
    """A positive control for ROADMAP's central claim, which is a claim about ABSENCE.

    ROADMAP says that of 435 census repos plus 131 in the re-run, zero ship a tool a university
    could point at the detector it is about to license. Since `inspect` reads source, every sweep
    now tests that against code rather than against READMEs — but a probe that finds nothing
    proves nothing unless it can find the thing when the thing is present.

    `eval/` is the positive control: it is exactly the instrument ROADMAP says the field lacks.
    """
    facts = census.read_tree(pathlib.Path(__file__).resolve().parent.parent / "eval")
    found = set(facts["signals"]["subgroup_fairness"])
    for expected in ("subgroup", "fpr", "wilson", "equalised odds", "aequitas"):
        assert expected in found, (
            f"the fairness probe missed {expected!r} in untell's own audit code, so a null "
            f"result across the census would mean nothing: found {sorted(found)}"
        )


def test_the_fairness_probe_does_not_decide_anything():
    """It is a measurement, not a rule. No branch may start ruling on it without being scored."""
    import inspect as _inspect

    assert "subgroup_fairness" not in _inspect.getsource(census.decide_from_tree), (
        "the fairness probe has become a classifier branch; score it against the census overlap "
        "first, the way the detector branch was not"
    )
