"""Per-sentence scoring tests (lite tier)."""

from __future__ import annotations

import json

from untell.scripts.sentences import main, score_sentences, split_sentences


def test_split_sentences():
    assert split_sentences("One. Two! Three? Done.") == ["One.", "Two!", "Three?", "Done."]
    assert split_sentences("") == []


def test_score_sentences_shape():
    r = score_sentences(
        "Furthermore, the system operates predictably and uniformly. It broke. Twice.",
        tier="lite",
        threshold=0.30,
    )
    assert len(r["sentences"]) >= 2
    for row in r["sentences"]:
        assert 0.0 <= row["ai"] <= 1.0
        assert isinstance(row["flagged"], bool)
        assert row["text"]
    assert isinstance(r["flagged"], list)
    assert all(isinstance(s, str) for s in r["flagged"])


def test_cli_json(capsys):
    rc = main(["Furthermore, the formulaic system operates predictably throughout.", "--tier", "lite", "--json"])
    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    assert "sentences" in parsed and "flagged" in parsed


def test_cli_empty_returns_2(capsys):
    assert main(["   "]) == 2


def test_flagging_is_relative_not_a_flood():
    # Regression: per-sentence targeting must not flag EVERY sentence on short text (the old
    # absolute-threshold + single-sentence burstiness degeneracy). It caps to the worst ~third.
    text = "One. Two. Three. Four. Five. Six. Seven. Eight. Nine."
    r = score_sentences(text, tier="lite", threshold=0.30)
    n = len(r["sentences"])
    assert n == 9
    assert len(r["flagged"]) <= (n + 2) // 3  # at most the worst third
    assert "note" in r


def test_top_caps_flagged_count():
    text = "Moreover, the system performs. Furthermore, it operates. Additionally, it functions. Also, it runs."
    r = score_sentences(text, tier="lite", threshold=0.0, top=1)  # threshold 0 => all eligible
    assert len(r["flagged"]) <= 1


def test_single_short_sentence_not_auto_max():
    """A single short sentence has undefined burstiness; it must not be auto-scored ~AI.

    It now returns None outright rather than a low number. On a handful of words the common-word
    ratio is decided entirely by a 120-word stoplist and is returned at full confidence in both
    directions — measured: "a" -> 1.0, "the of and" -> 1.0, "xylophone" -> 0.0. None is the
    protocol's "no signal", so score_text excludes it and reports scored: False.
    """
    from untell.detectors.perplexity_burstiness import lite_score

    assert lite_score("The cat sat.") is None
    # Long enough to carry signal -> a real number, and not an automatic ~1.0.
    score = lite_score("The cat sat on the mat and watched the rain fall outside.")
    assert score is not None and score < 0.9


def test_all_three_splitters_are_the_same_implementation():
    r"""`(?<=[.!?])\s+` was written out three times - in this module, the structural rewriter and
    the perplexity detector - so fixing the abbreviation bug in one left the other two wrong:

        scorer     scored the fragment "Dr." as a sentence and flagged it as AI
        rewriter   merged the halves back as "Dr, though smith published the results"
        detector   computed per-sentence surprisal over a one-token "sentence"

    Pinning the shared behaviour is what stops the copies drifting apart again.
    """
    from untell.detectors.perplexity_burstiness import _sentences
    from untell.rewriter.structural import _split_sentences
    from untell.scripts.sentences import split_sentences
    from untell.scripts.tells import _sentences as tells_sentences

    text = "Dr. Smith published the results in 2020. The study enrolled 240 patients."
    expected = ["Dr. Smith published the results in 2020.", "The study enrolled 240 patients."]
    assert split_sentences(text) == expected
    assert _split_sentences(text) == expected
    assert _sentences(text) == expected
    # tells feeds its split into the burstiness CV, which the loop uses to tie-break candidates,
    # so a stray one-word "Dr." sentence lands directly in a selection decision.
    assert tells_sentences(text) == expected


def test_no_module_keeps_its_own_sentence_splitter():
    """Grep-level guard. Six copies of `(?<=[.!?])\\s+` existed; four were fixed one at a time and
    the remaining two were still splitting "Dr." apart. Pinning the count is what stops the seventh.

    `untell/text_split.py` owns the pattern. `targeted.py` is the one allowed exception: it must
    reassemble the document byte-for-byte, so it keeps a whitespace-preserving variant — but it
    defers to `ends_with_abbreviation` from the shared module for the part that was wrong.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parent.parent
    pattern = re.compile(r"re\.compile\(r?\"\(\?<=\[\.!\?\]\)|re\.split\(r\"\(\?<=\[\.!\?\]\)")
    offenders = []
    for path in sorted((root / "untell").rglob("*.py")):
        if path.name in ("text_split.py", "targeted.py"):
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(root)}:{i}: {line.strip()}")
    assert not offenders, (
        "sentence splitting belongs in untell/text_split.py — these re-implement it and will drift:"
        "\n  " + "\n  ".join(offenders)
    )


def test_stdlib_path_warns_that_sentence_targeting_is_near_chance(monkeypatch, caplog):
    """Per-sentence AUROC on real labelled data (150 human / 150 ChatGPT sentences from HC3):

        hc3_roberta   1.000     full (GPT-2)     0.968
        fast_detect   0.940     roberta_openai   0.886
        lite (stdlib) 0.493  <- a coin flip

    On the zero-dependency path the flagged sentences are close to arbitrary, and a caller cannot
    see that from the output — the scores look like scores. Said once, not per call.
    """
    import logging

    import untell.scripts.sentences as s
    from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector

    monkeypatch.setattr(s, "_WARNED_UNINFORMATIVE", False)
    monkeypatch.setattr(PerplexityBurstinessDetector, "_torch_ready", lambda self: False)

    text = ("Furthermore, AI has transformed industry today. I forgot my wallet again this "
            "morning. Moreover, organizations leverage these tools daily.")
    with caplog.at_level(logging.WARNING, logger="untell.scripts.sentences"):
        s.score_sentences(text, tier="lite")
        s.score_sentences(text, tier="lite")

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1, f"expected exactly one warning, got {len(warnings)}"
    assert "0.493" in warnings[0].getMessage()


def test_no_warning_when_a_model_backed_detector_will_do_the_ranking(monkeypatch, caplog):
    """With torch present, "lite" upgrades to GPT-2 perplexity, which ranks sentences at 0.968 —
    there is nothing to warn about, and a warning nobody needs is how warnings get ignored."""
    import logging

    import untell.scripts.sentences as s
    from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector

    monkeypatch.setattr(s, "_WARNED_UNINFORMATIVE", False)
    monkeypatch.setattr(PerplexityBurstinessDetector, "_torch_ready", lambda self: True)

    with caplog.at_level(logging.WARNING, logger="untell.scripts.sentences"):
        s.score_sentences("One sentence here today. Another sentence follows it now.", tier="lite")

    # Filter by logger NAME. `caplog.at_level(..., logger=...)` sets the level for that logger but
    # caplog still records everything that reaches the root handler, so this asserted "no warnings
    # from anywhere" — and failed on huggingface_hub's unrelated "set a HF_TOKEN to enable higher
    # rate limits" notice, which fires whenever a model loads without a token. The subject here is
    # the targeting warning, so that is what must be absent.
    ours = [r for r in caplog.records
            if r.levelno >= logging.WARNING and r.name == "untell.scripts.sentences"]
    assert not ours, [r.getMessage() for r in ours]


class TestTheResultKeysAreWhatCallersExpect:
    """Pin the shape of what `score_sentences` returns.

    Three different result dicts in this codebase have now been misread in the same way while
    probing it: `untell_text` returns the rewrite under `final` (not `text`), `score_text` returns
    per-detector values under `detectors` (not `scores`), and this one puts the per-sentence
    probability under `ai` (not `score`). Each mistake produced a plausible-looking wrong answer
    rather than a KeyError — the sentence-targeting probe reported AUROC "None" on 0 of 40 matched
    sentences and looked like a broken scorer, when the scorer was fine.

    A caller cannot guess these and there is no one place that lists them, so each surface pins its
    own contract where the reader will be.
    """

    TEXT = (
        "Moreover, the framework leverages a robust approach to deliver outcomes. "
        "The kettle boiled while I read the last few pages of the book."
    )

    def test_top_level_keys(self):
        from untell.scripts.sentences import score_sentences

        result = score_sentences(self.TEXT, tier="lite", threshold=0.30)
        assert set(result) >= {"sentences", "flagged", "tier", "threshold"}

    def test_each_sentence_carries_text_ai_and_flagged(self):
        from untell.scripts.sentences import score_sentences

        result = score_sentences(self.TEXT, tier="lite", threshold=0.30)
        assert result["sentences"], "no sentences returned"
        for entry in result["sentences"]:
            assert set(entry) >= {"text", "ai", "flagged"}, sorted(entry)
            assert isinstance(entry["text"], str) and entry["text"].strip()
            assert entry["ai"] is None or 0.0 <= float(entry["ai"]) <= 1.0
            assert isinstance(entry["flagged"], bool)

    def test_there_is_no_score_key_to_mistake_for_ai(self):
        """If a `score` key appears later it is either the same number under two names or a
        different one under a confusing name. Both are worth stopping at."""
        from untell.scripts.sentences import score_sentences

        result = score_sentences(self.TEXT, tier="lite", threshold=0.30)
        for entry in result["sentences"]:
            assert "score" not in entry, (
                "a 'score' key appeared alongside 'ai' — decide which one callers should read"
            )

    def test_flagged_is_a_list_of_sentence_strings(self):
        """Not indices, not dicts. A caller filtering their own text needs the text back."""
        from untell.scripts.sentences import score_sentences

        result = score_sentences(self.TEXT, tier="lite", threshold=0.30)
        assert isinstance(result["flagged"], list)
        for item in result["flagged"]:
            assert isinstance(item, str)
            assert item in self.TEXT, f"flagged sentence is not from the input: {item!r}"

    def test_flagged_agrees_with_the_per_sentence_verdicts(self):
        """Two views of one decision. They drifting apart is silent and would make either one
        untrustworthy without saying which."""
        from untell.scripts.sentences import score_sentences

        result = score_sentences(self.TEXT, tier="lite", threshold=0.30)
        from_entries = {e["text"].strip() for e in result["sentences"] if e["flagged"]}
        assert {f.strip() for f in result["flagged"]} == from_entries
