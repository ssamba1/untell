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
