"""Full-tier detector tests.

Skipped automatically wherever torch is unavailable (e.g. the lite CI job, or a Windows box with
a broken torch DLL). The full-tier CI job installs ``.[full]`` so these run there and exercise the
RoBERTa / MAGE / Fast-DetectGPT / GPT-2-perplexity code paths that the lite tier never touches.
"""

from __future__ import annotations

import pytest

# Every test here loads a real model; see the `slow` marker note in pyproject.toml.
pytestmark = pytest.mark.slow

try:
    # NOTE: a broken torch install raises OSError (Windows DLL load), not ImportError, so
    # importorskip is insufficient — catch everything and skip the whole module.
    import torch  # noqa: F401
    import transformers  # noqa: F401
except Exception as exc:  # pragma: no cover - environment dependent
    pytest.skip(f"torch/transformers unavailable: {exc}", allow_module_level=True)

from untell.detectors.base import load_detectors, resolved_tier  # noqa: E402
from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector  # noqa: E402

AI_TEXT = (
    "Artificial intelligence has fundamentally transformed numerous industries. Moreover, it has "
    "enabled organizations to improve efficiency. Furthermore, it can analyze data quickly. "
    "Overall, the impact continues to grow significantly across various sectors."
)
HUMAN_TEXT = (
    "I almost missed the bus. Rain again — of course. My shoes were soaked through by the time the "
    "8:14 finally rattled up, half-empty, smelling faintly of wet dog and someone's coffee, and I "
    "squeezed into the corner seat I always grab when nobody beats me to it. Worth it."
)


def test_full_tier_loads_supervised_detectors():
    dets = load_detectors("full")
    names = {d.name for d in dets}
    assert resolved_tier(dets) == "full", names
    assert {"roberta_openai", "mage", "fast_detectgpt"} <= names, names


@pytest.mark.parametrize("name", ["roberta_openai", "mage", "fast_detectgpt", "hc3_roberta"])
def test_supervised_detector_scores_in_unit_interval(name):
    det = next(d for d in load_detectors("full") if d.name == name)
    try:
        scores = [det.score(text) for text in (AI_TEXT, HUMAN_TEXT, "short text")]
    except Exception as exc:
        # A detector that can't load (e.g. yaful/MAGE's int-valued id2label is rejected by current
        # huggingface_hub, or a NumPy 2.x / torch mismatch) now RAISES -> it is EXCLUDED from the
        # ensemble rather than folded in as a fake neutral 0.5. That exclusion is the correct,
        # intended behavior, so a load failure here is a skip, not a test failure.
        pytest.skip(f"{name} unavailable in this env (excluded from ensemble): {type(exc).__name__}")
    for s in scores:
        # None == "no signal" (empty/too-short text) and is excluded upstream; otherwise [0,1].
        assert s is None or 0.0 <= s <= 1.0, (name, s)


def test_perplexity_full_path_runs_and_is_bounded():
    det = PerplexityBurstinessDetector()
    assert det._torch_ready()
    for text in (AI_TEXT, HUMAN_TEXT):
        s = det.score(text)
        assert 0.0 <= s <= 1.0


def test_embedding_quality_path_active():
    # When sentence-transformers is installed, the quality gate must use the semantic metric.
    pytest.importorskip("sentence_transformers")
    from untell.scripts.quality import confidence, method, recommended_bar, similarity

    assert method() == "embedding"
    assert confidence() == "high"
    assert recommended_bar() == 0.76
    # Identical text ~1.0; a faithful paraphrase should still clear the semantic bar comfortably.
    assert similarity("The cat sat on the mat.", "The cat sat on the mat.") >= 0.99


def test_fast_detectgpt_actually_discriminates():
    """The inherited calibration (_CAL_MID=1.0) sat outside the observed curvature range and pinned
    EVERY input to ~0.30 — a detector contributing no signal while looking like an immovable wall in
    the ceiling measurements. Pin that it now responds to input and points the right way."""
    import pytest

    torch = pytest.importorskip("torch")  # noqa: F841
    pytest.importorskip("transformers")

    from untell.detectors.fast_detectgpt import FastDetectGPTDetector

    det = FastDetectGPTDetector()
    if not det.available():
        pytest.skip("fast_detectgpt unavailable")

    human = [
        "I went to the store yesterday and forgot my wallet again. Third time this month.",
        "The bus was late so I walked. Rain the whole way. My shoes are still wet by the radiator.",
    ]
    ai = [
        "Furthermore, artificial intelligence has fundamentally transformed numerous industries.",
        "Moreover, organizations increasingly leverage these technologies to optimize efficiency.",
    ]
    try:
        h = [det.score(t) for t in human]
        a = [det.score(t) for t in ai]
    except Exception:
        pytest.skip("fast_detectgpt failed to load")

    assert all(s is not None for s in h + a)
    # The ONLY property that is honestly assertable here: the detector must respond to its input
    # rather than emitting a constant. It must NOT assert that AI scores above human — measured, the
    # curvature distributions overlap so heavily at paragraph length with gpt-neo-125m that the
    # direction flips on small samples (5+5 gave AI 0.577 vs human 0.387, but individual 2+2 subsets
    # reverse it). That weakness is real and documented; the calibration fix only restored the
    # detector's dynamic range, it did not make the statistic discriminative at this size.
    assert max(h + a) - min(h + a) > 0.05


def test_long_document_is_scored_past_the_context_window():
    """GPT-2 stops at 1024 tokens; a document does not.

    The scorer used to truncate, so everything after roughly the first 750 words went unmeasured —
    an essay could carry an untouched AI tail and still be reported on its opening alone. The text
    is now walked in overlapping windows, each carrying real preceding context.
    """
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector

    det = PerplexityBurstinessDetector()
    if not det._torch_ready():
        pytest.skip("torch/transformers not importable")

    long_text = ("The committee reviewed the proposal and asked for three specific changes "
                 "before the vote. ") * 120  # comfortably over 1024 tokens
    nll, offsets = det._token_nll(long_text)
    assert nll is not None
    assert len(nll) > 1024, f"only {len(nll)} tokens scored — the tail was truncated away"
    assert len(offsets) >= len(nll)


def test_score_is_finite_and_in_range_for_a_long_document():
    pytest.importorskip("torch")
    from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector

    det = PerplexityBurstinessDetector()
    if not det._torch_ready():
        pytest.skip("torch/transformers not importable")
    text = ("Regular exercise offers benefits for physical and mental health. "
            "It reduces the risk of chronic disease and improves mood. ") * 90
    s = det.score(text)
    assert s is not None and 0.0 <= s <= 1.0 and s == s


def test_windowed_max_scores_the_whole_document():
    """Pure logic, no model: windows cover every sentence and the highest score wins."""
    from untell.detectors.base import windowed_max

    seen = []

    def fake(window):
        seen.append(window)
        return 0.9 if "MARKER" in window else 0.1

    long_text = " ".join(f"This is filler sentence number {i}." for i in range(200))
    long_text += " MARKER sentence sits right at the very end of the document."
    assert windowed_max(long_text, fake, window_words=50) == 0.9
    assert len(seen) > 1, "long text was not split into windows"
    assert any("MARKER" in w for w in seen), "the tail was never scored"

    short = "One short sentence only."
    seen.clear()
    assert windowed_max(short, fake, window_words=50) == 0.1
    assert seen == [short], "short text must be scored in a single call, unchanged"


def test_windowed_max_ignores_none_windows():
    from untell.detectors.base import windowed_max

    text = " ".join(f"Sentence number {i} here." for i in range(120))
    assert windowed_max(text, lambda w: None, window_words=20) is None
    calls = {"n": 0}

    def sometimes(w):
        calls["n"] += 1
        return None if calls["n"] % 2 else 0.42

    assert windowed_max(text, sometimes, window_words=20) == 0.42


@pytest.mark.parametrize("name", ["roberta_openai", "hc3_roberta", "fast_detectgpt"])
def test_long_document_tail_is_not_invisible(name):
    """Every supervised adapter truncates at 512 tokens - roughly the first 380 words.

    Measured before windowing, appending 1113 words of AI text to 797 words of human text moved
    nothing at all:

        roberta_openai   human alone 0.000   human + AI 0.000
        hc3_roberta      human alone 0.000   human + AI 0.000
        fast_detectgpt   human alone 0.418   human + AI 0.418

    An essay with a human-written opening scored clean whatever followed it.
    """
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    det = next((d for d in load_detectors("full") if d.name == name), None)
    if det is None:
        pytest.skip(f"{name} unavailable")

    prefix = ("I went to the store yesterday and forgot my wallet again, third time this month. "
              "The guy at the counter waved me off and said bring it next time. ") * 30
    ai = ("Furthermore, artificial intelligence has fundamentally transformed numerous industries. "
          "Moreover, organizations increasingly leverage these technologies to optimize efficiency. "
          "In conclusion, this represents a pivotal shift in the modern business landscape. ") * 30

    # The invariant, independent of how AI-ish the prefix happens to read: a section cannot be
    # hidden by putting other text in front of it. Under truncation the tail scored 0.000 while the
    # same text alone scored 1.000.
    ai_alone = det.score(ai)
    with_prefix = det.score(prefix + " " + ai)
    assert ai_alone is not None and with_prefix is not None
    assert with_prefix >= ai_alone - 0.05, (
        f"{name}: {len(ai.split())} words of AI text scored {ai_alone:.3f} alone but only "
        f"{with_prefix:.3f} behind a {len(prefix.split())}-word prefix — the tail is invisible"
    )
