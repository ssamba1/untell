"""A corpus builder that returns nothing must fail loudly, not publish a stale number.

Round thirty-one: `eval/pre_llm_fpr.py` selects Anthology text published no later than 2021, and
`eval.litreview.VOLUMES` began at 2023. The builder returned **zero** abstracts. The number it had
produced — "15.8% of 120 pre-LLM abstracts", which `ROADMAP.md` called the most defensible
false-positive figure in the repository — stayed published as reproducible for many rounds while
nobody could reproduce it, because **every test of that module used synthetic text.** The unit tests
were all green. The corpus was gone.

So this file tests the one thing those did not: that the shipped configuration can still build the
corpora the published measurements rest on. It skips when the cache is absent — a contributor without
a 180 MB download should not see red — but when the cache *is* present and a builder returns nothing,
that is the round-thirty-one failure and it fails.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eval import litreview

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / ".anthology-cache"

needs_corpus = pytest.mark.skipif(
    not (CACHE.exists() and any(CACHE.glob("*.xml"))),
    reason="Anthology corpus not cached (run `python -m eval.litreview --download`)",
)


@needs_corpus
def test_the_survey_corpus_is_not_empty():
    papers = litreview.load_abstracts(CACHE)
    assert len(papers) > 1000, f"only {len(papers)} abstracts parsed from the cache"


@needs_corpus
def test_the_pre_llm_corpus_is_not_empty():
    """The exact round-thirty-one failure. `pre_llm_abstracts` filters to <= 2021 and the volume list
    has to contain volumes from then, or the false-positive probe silently measures nothing."""
    from eval.pre_llm_fpr import pre_llm_abstracts

    texts = pre_llm_abstracts(CACHE)
    assert texts, (
        "no pre-LLM abstracts: `eval.litreview.VOLUMES` has no volume published in or before the "
        "cut-off year, so `eval/pre_llm_fpr.py` and `eval/outlier_fairness.py` cannot run and every "
        "number they published is unreproducible"
    )
    assert len(texts) > 100, f"only {len(texts)} pre-LLM abstracts — too few to sample 120 from"


def test_the_volume_list_actually_spans_the_pre_llm_cut_off():
    """Runs with no cache at all, because the defect was in the CONFIGURATION, not the download. The
    cut-off is read from the function's own default so the two cannot drift apart."""
    import inspect

    from eval.pre_llm_fpr import pre_llm_abstracts

    cut_off = inspect.signature(pre_llm_abstracts).parameters["max_year"].default
    years = sorted({int(v.split(".")[0]) for v in litreview.VOLUMES})
    assert min(years) <= cut_off, (
        f"VOLUMES starts at {min(years)} but pre_llm_abstracts wants text from {cut_off} or "
        f"earlier — the pre-LLM corpus will be empty"
    )


def test_enough_pre_llm_volumes_to_survive_one_going_missing():
    """One volume 404ing should not empty the corpus. Two names in this list turned out never to
    have existed (round fifteen), so a single point of failure here is not hypothetical."""
    import inspect

    from eval.pre_llm_fpr import pre_llm_abstracts

    cut_off = inspect.signature(pre_llm_abstracts).parameters["max_year"].default
    old = [v for v in litreview.VOLUMES if int(v.split(".")[0]) <= cut_off]
    assert len(old) >= 5, f"only {len(old)} pre-LLM volume(s) configured: {old}"


@needs_corpus
def test_the_outlier_arm_can_build_its_own_corpus():
    from eval.outlier_fairness import probe_by_distance
    from eval.pre_llm_fpr import pre_llm_abstracts

    texts = pre_llm_abstracts(CACHE)[:12]
    result = probe_by_distance(texts, tier="lite")
    assert "error" not in result, result
    assert result["margin"]["n"] + result["centre"]["n"] > 0


@needs_corpus
def test_every_configured_volume_that_downloaded_actually_parsed():
    """A volume can be cached and still contribute nothing — an error page saved as XML, or a schema
    change. Counting files is not counting data."""
    cached = {p.stem for p in CACHE.glob("*.xml")}
    parsed = {p["id"].rsplit("-", 1)[0].rsplit(".", 1)[0] for p in litreview.load_abstracts(CACHE)}
    silent = {v for v in cached if not any(v.startswith(p) or p.startswith(v) for p in parsed)}
    assert not silent, f"cached but yielded no abstracts: {sorted(silent)}"
