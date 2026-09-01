"""Standardizing a rate is only meaningful if the rates and the weights describe one population.

Rounds thirty-six and thirty-seven made length the dominant nuisance variable in every false-positive
comparison here: detectors flag short text far more often (30.0% at <=50 words against 13.3% at
200+), so two corpora with different length profiles get different rates from the same detector
before anything about their authors is considered. `eval/length_standardized.py` applies direct
standardization — the method epidemiology uses to compare mortality between an old state and a young
one — to remove that composition difference.

The first version of it was wrong in a way worth keeping a test for. It drew band rates from
`pre_llm_fpr.probe_by_length`, which TRUNCATES every abstract to the top of every band it reaches, so
one 150-word abstract contributes a scored sample to 0-50, 50-100 and 100-200. The weights, meanwhile,
counted each document once, in the band its natural length falls in. Rates from one population,
weights from another: on two halves of a single corpus, which should agree, it reported a crude 20.4%
against a standardized 11.2%.
"""

from __future__ import annotations

import pytest

from eval import length_standardized as ls


def _texts(spec: list[tuple[int, int]]) -> list[str]:
    """`(word_count, how_many)` pairs."""
    return [f"{'word ' * n}end." for n, count in spec for _ in range(count)]


def test_the_profile_puts_each_document_in_exactly_one_band():
    """The weights must sum to one. If a document counted in several bands, the profile would sum
    above one and every standardized figure would be inflated."""
    profile = ls.length_profile(_texts([(30, 5), (75, 5), (150, 5), (400, 5)]))
    assert abs(sum(profile.values()) - 1.0) < 1e-9
    assert profile["100-200"] == pytest.approx(0.25)


def test_standardizing_a_corpus_against_its_own_rates_returns_its_own_rate():
    """The identity case, and the strongest check available without scoring anything: applying a
    corpus's band rates to its own length profile must reproduce its crude rate."""
    band_rates = {"50-100": {"fpr": 0.40, "n": 50}, "100-200": {"fpr": 0.10, "n": 150}}
    profile = {"50-100": 0.25, "100-200": 0.75}
    result = ls.standardize(band_rates, profile)
    assert result["standardized_fpr"] == pytest.approx(0.25 * 0.40 + 0.75 * 0.10)


def test_a_shorter_corpus_standardizes_to_a_higher_rate():
    """The whole point: length composition moves the expected rate, in the direction the length
    curve says it should."""
    band_rates = {"50-100": {"fpr": 0.40, "n": 50}, "100-200": {"fpr": 0.10, "n": 150}}
    short = ls.standardize(band_rates, {"50-100": 0.9, "100-200": 0.1})["standardized_fpr"]
    long_ = ls.standardize(band_rates, {"50-100": 0.1, "100-200": 0.9})["standardized_fpr"]
    assert short > long_


def test_a_band_with_no_measured_rate_is_dropped_and_reported():
    """Silently treating an unmeasured band as 0% would bias every standardized figure downward, and
    the caller could not tell how much of their corpus the number covered."""
    band_rates = {"100-200": {"fpr": 0.10, "n": 150}}
    result = ls.standardize(band_rates, {"50-100": 0.4, "100-200": 0.6})
    assert result["coverage"] == pytest.approx(0.6)
    assert result["bands_dropped"] == ["50-100"]
    assert result["standardized_fpr"] == pytest.approx(0.10)


def test_no_usable_band_refuses_rather_than_returning_zero():
    result = ls.standardize({}, {"50-100": 1.0})
    assert result["standardized_fpr"] is None
    assert "error" in result


def test_low_coverage_is_warned_about_in_the_rendering():
    text = ls._render({
        "tier": "lite", "reference_bands": {"100-200": {"fpr": 0.1}},
        "target_profile": {"50-100": 0.6, "100-200": 0.4},
        "crude_fpr": 0.3, "crude_ci95": [0.2, 0.4], "crude_n": 100,
        "standardized_fpr": 0.1, "coverage": 0.4, "bands_used": ["100-200"],
        "bands_dropped": ["50-100"], "length_explains": 0.2, "note": "n/a",
    })
    assert "only 40% of the corpus" in text
    assert "not a rate for the whole corpus" in text


def test_band_rates_come_from_whole_documents_not_truncated_ones(monkeypatch):
    """The original defect. `rates_by_natural_length` must score each document ONCE, at its own
    length — if it truncated into every band the way `probe_by_length` does, the rates would describe
    a different population from the weights and the comparison would be meaningless."""
    scored: list[int] = []

    def fake_score(text, tier="lite"):
        scored.append(len(text.split()))
        return {"agreement": {"any": False}, "flagged": False}

    import untell.scripts.score as score_module
    monkeypatch.setattr(score_module, "score_text", fake_score)
    ls.rates_by_natural_length(_texts([(150, 3)]), tier="lite")
    assert len(scored) == 3, f"3 documents should produce 3 scorings, got {len(scored)}"
    assert all(n > 100 for n in scored), "documents must be scored whole, not truncated into bands"
