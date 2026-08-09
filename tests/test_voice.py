"""Tests for voice matching — how far a draft sits from the way you write."""

from __future__ import annotations

import json

import pytest

from untell.scripts.voice import (
    _SCALE,
    MATCHABLE,
    MIN_SAMPLE_WORDS,
    main,
    style_profile,
    voice_distance,
    voice_gaps,
    voice_report,
)

TERSE = (
    "The build broke. I fixed it. Took an hour. The cache was stale, which is always the answer. "
    "I cleared it and moved on. Nobody noticed. That is the job most days. You find the small "
    "thing. You fix it. You write it down so the next person does not lose the hour you lost. "
    "I keep a file of these. It is long now. Some entries are one line. Others run a page."
)
ORNATE = (
    "Following a comprehensive investigation into the underlying causes of the build failure, "
    "which had persisted for a considerable period of time, it became apparent that the caching "
    "layer, having retained obsolete artifacts across successive invocations of the pipeline, was "
    "principally responsible for the observed behaviour, and consequently a full invalidation of "
    "the cache was performed in order to restore the expected functionality of the system."
)


class TestStyleProfile:
    def test_profile_has_a_scale_for_every_feature(self):
        """A feature without a scale constant cannot be turned into a comparable distance."""
        assert set(style_profile(TERSE)) == set(_SCALE)

    def test_matchable_is_a_subset_of_the_profile(self):
        assert set(MATCHABLE) <= set(_SCALE)

    def test_terse_and_ornate_profiles_differ_as_described(self):
        t, o = style_profile(TERSE), style_profile(ORNATE)
        assert o["sent_len"] > t["sent_len"] * 3, "ornate sample should have far longer sentences"
        assert o["comma_per_100w"] > t["comma_per_100w"]
        assert t["first_person_per_100w"] > o["first_person_per_100w"]

    def test_empty_text_does_not_raise(self):
        """Division by a zero word count and a zero mean sentence length are both reachable."""
        p = style_profile("")
        assert p["sent_len"] == 0 and p["burst"] == 0.0

    def test_single_sentence_has_zero_burstiness(self):
        assert style_profile("One single flat sentence with no variation at all.")["burst"] == 0.0


class TestDistance:
    def test_identical_text_is_zero(self):
        assert voice_distance(TERSE, TERSE) == 0.0

    def test_distance_is_not_symmetric_in_sign_but_is_in_magnitude(self):
        """Gaps carry a direction; the distance does not."""
        assert voice_distance(TERSE, ORNATE) == voice_distance(ORNATE, TERSE)
        assert voice_gaps(TERSE, ORNATE)["sent_len"] == pytest.approx(
            -voice_gaps(ORNATE, TERSE)["sent_len"]
        )

    def test_different_voices_are_far_apart(self):
        assert voice_distance(TERSE, ORNATE) > 2.0

    def test_gap_sign_says_which_way(self):
        """Positive = the draft over-does the feature, which is what the report renders."""
        g = voice_gaps(TERSE, ORNATE)
        assert g["sent_len"] > 0, "ornate draft uses longer sentences than the terse sample"
        assert g["first_person_per_100w"] < 0, "ornate draft uses less first person"

    def test_only_matchable_features_move_the_distance(self):
        """A feature the rewriter cannot change must not decide which candidate wins.

        Built by holding the matchable features fixed — the two texts are the same sentences —
        while changing an advisory one, so any movement in the distance is the bug.
        """
        a = "I ran the tests. I fixed the bug. I shipped it."
        b = "We ran the tests. We fixed the bug. We shipped it."
        assert voice_gaps(a, b)["first_person_per_100w"] != 0  # the advisory feature did change
        assert voice_distance(a, b) == 0.0  # ...and the scored distance did not move


class TestReport:
    def test_report_shape(self):
        r = voice_report(TERSE, ORNATE)
        assert set(r["gaps"]) == set(_SCALE)
        assert r["matched_on"] == list(MATCHABLE)
        assert r["distance"] == voice_distance(TERSE, ORNATE)

    def test_short_sample_is_flagged_not_silently_trusted(self):
        r = voice_report("Three words here.", ORNATE)
        assert "warning" in r and str(MIN_SAMPLE_WORDS) in r["warning"]

    def test_long_sample_has_no_warning(self):
        long_sample = TERSE * 6
        assert "warning" not in voice_report(long_sample, ORNATE)


class TestCLI:
    def _files(self, tmp_path):
        s, d = tmp_path / "s.txt", tmp_path / "d.txt"
        s.write_text(TERSE * 6, encoding="utf-8")
        d.write_text(ORNATE, encoding="utf-8")
        return str(s), str(d)

    def test_table_output(self, tmp_path, capsys):
        s, d = self._files(tmp_path)
        assert main(["--sample", s, "--draft", d]) == 0
        out = capsys.readouterr().out
        assert "voice distance:" in out
        for feature in _SCALE:
            assert feature in out, f"{feature} missing from the report"

    def test_json_output_is_valid_and_complete(self, tmp_path, capsys):
        s, d = self._files(tmp_path)
        assert main(["--sample", s, "--draft", d, "--json"]) == 0
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["distance"] > 0 and set(parsed["gaps"]) == set(_SCALE)

    def test_reports_rather_than_gates(self, tmp_path):
        """Exit 0 even for a wildly mismatched draft — this is advice, not a pass/fail check."""
        s, d = self._files(tmp_path)
        assert main(["--sample", s, "--draft", d]) == 0

    def test_has_a_main_guard(self):
        """Every CLI in this package is runnable as a file, not only via its console script."""
        from pathlib import Path

        import untell.scripts.voice as mod

        assert '__name__ == "__main__"' in Path(mod.__file__).read_text(encoding="utf-8")


class TestLoopIntegration:
    """The voice term is a tie-break only: it must never displace tells or cost evasion."""

    def test_no_sample_is_a_constant_so_the_default_path_is_unchanged(self):
        from untell.scripts.run import _voice_key

        assert _voice_key("anything at all", None) == 0.0
        assert _voice_key("something else entirely, much longer", None) == 0.0

    def test_sentinels_are_stripped_before_scoring(self):
        """A sentinel is one token to the word regex but stands for a span of any length, so
        leaving it in would score candidates against a phantom vocabulary."""
        from untell.scripts.run import _voice_key

        with_sentinel = _voice_key("A short one. \u27e6HZ0001\u27e7 Another.", TERSE * 6)
        without = _voice_key("A short one.   Another.", TERSE * 6)
        assert with_sentinel == without

    def test_untell_text_accepts_a_voice_sample(self):
        """Pin the parameter name — three other surfaces restate this signature."""
        import inspect

        from untell.scripts.run import untell_text

        assert "voice_sample" in inspect.signature(untell_text).parameters

    def test_cli_exposes_the_flag(self):
        """--voice must reach untell_text; a flag the parser accepts but drops is worse than none."""
        from pathlib import Path

        import untell.scripts.run as run_mod

        src = Path(run_mod.__file__).read_text(encoding="utf-8")
        assert '"--voice-sample"' in src, "run.py does not define the --voice-sample flag"
        assert "voice_sample=voice_sample" in src, "--voice-sample is parsed but never passed on"

    def test_short_voice_sample_warns_but_still_runs(self, tmp_path, capsys, monkeypatch):
        """Refusing the flag the user passed would be worse than ranking on noisier statistics."""
        import untell.scripts.run as run_mod

        sample = tmp_path / "v.txt"
        sample.write_text("Three words only.", encoding="utf-8")
        captured = {}

        def fake_untell_text(text, **kw):
            captured.update(kw)
            return {"error": "stopped before running the loop"}

        monkeypatch.setattr(run_mod, "untell_text", fake_untell_text)
        run_mod.main(["some input text here", "--voice-sample", str(sample)])
        out = capsys.readouterr().out
        assert "WARNING" in out and str(MIN_SAMPLE_WORDS) in out
        assert captured.get("voice_sample") == "Three words only."


class TestADegenerateVoiceSampleIsInertNotInverted:
    """A blank `--voice-sample` did not disable voice matching, it reversed it.

    `_voice_key` guarded `not voice_sample`, which is False for "   " — whitespace is truthy. So a
    blank or near-empty sample file reached `voice_distance`, produced an all-zero style profile,
    and the tie-break then ranked candidates by how close they were to zero commas, zero
    contractions and the shortest possible sentences. MEASURED on three candidates:

        rich prose  2.5225
        medium      0.8329
        terse       0.1282   <- "It works." wins

    The user supplied a file, believed it was shaping the output, and it was shaping it backwards
    with nothing on screen to say so.
    """

    CANDIDATES = {
        "rich": "I've been running these experiments for months, and honestly, the results "
                "keep surprising me.",
        "terse": "It works.",
        "medium": "The system processed the input and returned a result within the expected time.",
    }
    REAL_SAMPLE = (
        "I think it's fine, mostly. I've seen worse, honestly, and I've seen a lot better too, "
        "over the years of doing this."
    )

    def _scores(self, sample):
        from untell.scripts.run import _voice_key

        return {k: _voice_key(v, sample) for k, v in self.CANDIDATES.items()}

    @pytest.mark.parametrize(
        "sample", [None, "", "   ", "\n\t ", "It works fine.", "Three word sample"],
        ids=["none", "empty", "spaces", "newline-tab", "three-words", "three-words-2"],
    )
    def test_a_sample_too_thin_to_profile_ranks_nothing(self, sample):
        """Inert means every candidate scores identically, so the tie-break falls through to the
        criteria that do have signal. Anything else is the tie-break voting on noise."""
        scores = self._scores(sample)
        assert set(scores.values()) == {0.0}, f"{sample!r} produced a preference: {scores}"

    def test_a_real_sample_still_ranks(self):
        """The guard must switch voice matching off for unusable input, not off in general."""
        scores = self._scores(self.REAL_SAMPLE)
        assert len(set(scores.values())) > 1, "voice matching became inert for a real sample"
        assert min(scores, key=scores.get) == "rich", (
            f"a casual, contraction-heavy sample should prefer the casual candidate: {scores}"
        )

    def test_the_user_is_told_the_sample_was_ignored(self, caplog):
        """Silence is the actual defect. Dropping the sample quietly leaves the user believing it
        worked."""
        import logging

        import untell.scripts.run as run

        run._WARNED_VOICE_SAMPLE = False
        with caplog.at_level(logging.WARNING):
            run._voice_key(self.CANDIDATES["rich"], "far too short")
        assert any("voice sample" in r.message for r in caplog.records), caplog.text

    def test_the_floor_is_stated_not_magic(self):
        from untell.scripts.run import _MIN_VOICE_SAMPLE_WORDS

        assert _MIN_VOICE_SAMPLE_WORDS >= 10, (
            "a style profile estimates six features; a floor below ~10 words profiles noise"
        )
