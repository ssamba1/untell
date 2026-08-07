"""Detector contract tests — run in the lite tier with zero ML installed."""

from __future__ import annotations

import pytest

from untell.detectors.base import clamp01, load_detectors, resolved_tier
from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector, lite_score

AI_TEXT = (
    "Artificial intelligence has fundamentally transformed numerous industries. Moreover, it has "
    "enabled organizations to improve efficiency. Furthermore, it can analyze data quickly. "
    "Overall, the impact continues to grow significantly across various sectors."
)
HUMAN_TEXT = (
    "I almost missed the bus. Rain again — of course. My shoes were soaked through by the time "
    "the 8:14 finally rattled up, half-empty, smelling faintly of wet dog and someone's coffee, "
    "and I squeezed into the corner seat I always grab when nobody beats me to it. Worth it."
)


def test_lite_detector_always_available():
    d = PerplexityBurstinessDetector()
    assert d.available() is True
    assert d.tier == "lite"


def test_scores_in_unit_interval():
    d = PerplexityBurstinessDetector()
    for text in (AI_TEXT, HUMAN_TEXT):
        s = d.score(text)
        assert s is not None and 0.0 <= s <= 1.0
    # "x" is below the minimum word count: the answer is None (no signal), not a number. It used
    # to score 0.0 — a confident "definitely human" for a single character.
    assert d.score("x") is None


def test_empty_text_returns_none_not_a_number():
    """Protocol (base.py): empty/too-short input must return None so the ensemble EXCLUDES it.

    This previously returned 0.5, which is not "neutral" — it is a fabricated score folded into the
    max/mean aggregation, and score_text("") duly reported flagged=True for an empty string.
    """
    d = PerplexityBurstinessDetector()
    for text in ("", "   ", "\n\t "):
        assert d.score(text) is None


def test_empty_text_is_not_flagged_by_the_ensemble():
    from untell.scripts.score import score_text

    r = score_text("", tier="lite")
    assert r["flagged"] is False
    assert r["detectors"]["perplexity_burstiness"] is None  # excluded, not scored


def test_single_sentence_can_reach_below_the_threshold():
    """Single-sentence inputs used to have a hard floor of exactly 0.30 — the detection threshold —
    because an "undefined" burstiness contributed a fixed 0.6 * 0.5. Every single sentence therefore
    sat on the decision boundary regardless of content. The lower range must be reachable."""
    plain = lite_score("Mitochondrial ribosomes synthesize hydrophobic peptides.")
    formulaic = lite_score("It is important to note that this is the best way to do the thing.")
    assert plain < 0.30              # was pinned at exactly 0.30
    assert formulaic > plain         # and the signal still discriminates on one sentence


def test_ai_scores_higher_than_human_lite():
    # The lite heuristic is weak, but should still rank formulaic AI text above bursty human text.
    assert lite_score(AI_TEXT) > lite_score(HUMAN_TEXT)


def test_load_detectors_never_empty_and_lite_present():
    dets = load_detectors("lite")
    assert dets, "lite tier must always yield at least the heuristic detector"
    assert any(d.name == "perplexity_burstiness" for d in dets)
    assert resolved_tier(dets) == "lite"


def test_full_tier_degrades_to_available():
    # Without torch installed, requesting 'full' still only returns available detectors.
    dets = load_detectors("full")
    for d in dets:
        assert d.available()


def test_clamp01():
    assert clamp01(-1.0) == 0.0
    assert clamp01(2.0) == 1.0
    assert clamp01(0.5) == 0.5
    assert clamp01(float("nan")) == 0.5


def test_new_detectors_registered():
    from untell.detectors.base import all_detectors

    names = {d.name for d in all_detectors()}
    assert "hc3_roberta" in names
    assert "radar" in names


def test_radar_is_opt_in_gated(monkeypatch):
    # RADAR is non-commercial licensed -> excluded unless UNTELL_ENABLE_RADAR is set, even with torch.
    from untell.detectors.radar import RadarDetector

    monkeypatch.delenv("UNTELL_ENABLE_RADAR", raising=False)
    assert RadarDetector().available() is False


def test_mage_direct_load_scores():
    # Heavy: downloads yaful/MAGE (~600MB). Opt-in via UNTELL_TEST_MAGE=1. Verifies the pipeline-free
    # direct load works on a modern transformers/numpy stack (the fix that un-breaks MAGE).
    import os

    import pytest

    if os.environ.get("UNTELL_TEST_MAGE") != "1":
        pytest.skip("set UNTELL_TEST_MAGE=1 to load yaful/MAGE (~600MB)")
    from untell.detectors.mage import MageDetector

    MageDetector._dead = False  # reset any prior-session failure latch
    d = MageDetector()
    s = d.score("Furthermore, this underscores a pivotal and transformative paradigm shift.")
    assert s is not None and 0.0 <= s <= 1.0
    assert MageDetector._dead is False


# --- single-sentence scoring was perfectly inverted -------------------------------------------
# On a lone sentence, burstiness is undefined, so the score fell back to the common-word ratio
# alone. That ratio was calibrated for an older kind of AI text: modern model prose reaches for
# inflated vocabulary ("leverage", "transformative"), which drives the ratio DOWN, while casual
# human speech is almost entirely common words, which drives it UP. Measured AUROC over the pairs
# below was 0.000 — every AI sentence ranked below every human one.
#
# It mattered because sentences.py scores each sentence in isolation: per-sentence targeting was
# pointing the rewriter at whichever sentences read most human.

_AI_SENTENCES = [
    "Furthermore, artificial intelligence has fundamentally transformed numerous industries.",
    "Moreover, organizations increasingly leverage these technologies to optimize efficiency.",
    "This robust framework enables stakeholders to seamlessly navigate complex challenges.",
    "In today's rapidly evolving landscape, businesses must delve into innovative solutions.",
    "It is important to note that this underscores the importance of robust solutions.",
]
_HUMAN_SENTENCES = [
    "I went to the store and forgot the milk again.",
    "The build broke because someone bumped the pinned version.",
    "She said it was fine, but her face said otherwise.",
    "We tried it twice and it still didn't work.",
    "He emailed me back three days later with one line.",
]


def test_single_sentence_scoring_is_not_inverted():
    """The whole point: AI single sentences must outrank human ones. AUROC was 0.000."""
    ai = [lite_score(s) for s in _AI_SENTENCES]
    human = [lite_score(s) for s in _HUMAN_SENTENCES]
    pairs = [(a, h) for a in ai for h in human]
    auroc = sum((a > h) + 0.5 * (a == h) for a, h in pairs) / len(pairs)
    assert auroc > 0.9, f"single-sentence AUROC {auroc:.3f} — was 0.000 (perfectly inverted)"


def test_ordinary_human_sentences_are_not_flagged():
    """The common-word term is the one measured to be backwards, so it is capped below the default
    0.30 threshold. At a 0.35 cap every plain human sentence landed on exactly 0.350 and flagged."""
    from untell.scripts.score import DEFAULT_THRESHOLD

    for s in _HUMAN_SENTENCES:
        assert lite_score(s) < DEFAULT_THRESHOLD, f"false positive on human sentence: {s!r}"


def test_ai_single_sentences_are_flagged():
    from untell.scripts.score import DEFAULT_THRESHOLD

    for s in _AI_SENTENCES:
        assert lite_score(s) >= DEFAULT_THRESHOLD, f"AI sentence not flagged: {s!r}"


def test_tells_failure_does_not_restore_the_inverted_ratio(monkeypatch):
    """If tells raises, the fallback must stay capped — never hand the verdict back to the term
    that was measured backwards."""
    import untell.detectors.perplexity_burstiness as pb

    def boom(*a, **k):
        raise RuntimeError("tells exploded")

    monkeypatch.setattr("untell.scripts.tells.score_tells", boom)
    # A sentence of almost entirely common words: the inverted ratio would score this very high.
    assert pb.lite_score("We tried it twice and it still did not work.") <= pb._RATIO_CEILING


def _torch_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("torch") is not None


@pytest.mark.skipif(not _torch_available(), reason="full GPT-2 path needs torch")
def test_full_gpt2_path_is_not_inverted_on_single_sentences():
    """The lite fix left this broken, and a lite-only test did not notice.

    With torch installed the detector takes the GPT-2 path, where a lone sentence had no burstiness
    and fell back to perplexity alone — measured human_mean 0.224 vs ai_mean 0.154, inverted. The
    logistic midpoint is fitted to paragraph-length text, and at sentence length the quantity flips
    sign for this distribution: casual human speech is highly predictable, modern formal AI prose
    reaches for rarer words that GPT-2 finds more surprising.

    This test is deliberately run through the detector object, not `lite_score`, so it exercises
    whichever backend is actually installed.
    """
    det = PerplexityBurstinessDetector()
    if not det._torch_ready():
        pytest.skip("torch present but the GPT-2 path did not initialise")

    ai = [det.score(s) for s in _AI_SENTENCES]
    human = [det.score(s) for s in _HUMAN_SENTENCES]
    assert all(v is not None for v in ai + human)
    pairs = [(a, h) for a in ai for h in human]
    auroc = sum((a > h) + 0.5 * (a == h) for a, h in pairs) / len(pairs)
    assert auroc > 0.9, f"full-path single-sentence AUROC {auroc:.3f} (was inverted)"


# A bland, predictable sentence in the HC3 register: zero AI tells, but exactly the kind of text
# GPT-2 perplexity is good at. It is the case that exposed a regression where a 0.25 cap was
# applied to the GPT-2 path as well as the lite one.
_BLAND_AI_SENTENCE = "There are several factors that can affect the performance of a computer system."


def test_bland_sentence_has_no_tells():
    """Guard the guard: if this ever gains a tell, the two tests below stop testing the cap."""
    from untell.scripts.tells import score_tells

    assert score_tells(_BLAND_AI_SENTENCE)["tells"] == 0


@pytest.mark.skipif(not _torch_available(), reason="GPT-2 path needs torch")
def test_gpt2_single_sentence_is_not_capped_at_the_lite_ceiling():
    """Ranking and calibration fail independently, and only ranking was checked the first time.

    Capping the GPT-2 path at _RATIO_CEILING left AUROC at 0.971 — ordering intact — while pinning
    every real HC3 AI sentence to exactly 0.250, below the 0.30 threshold. `sentences.py` flags the
    worst third AND requires >= threshold, so per-sentence targeting flagged 0 of 46 sentences
    across six AI paragraphs. The cap belongs only to the lite term, which is genuinely backwards.
    """
    from untell.detectors.perplexity_burstiness import _RATIO_CEILING

    det = PerplexityBurstinessDetector()
    if not det._torch_ready():
        pytest.skip("torch present but the GPT-2 path did not initialise")
    score = det.score(_BLAND_AI_SENTENCE)
    assert score > _RATIO_CEILING, (
        f"GPT-2 single-sentence score {score} is at or below the lite cap {_RATIO_CEILING} — "
        "per-sentence flagging cannot fire"
    )


def test_lite_single_sentence_keeps_the_ceiling():
    """The lite term stays capped: it is the one measured backwards, and must not flag alone."""
    from untell.detectors.perplexity_burstiness import _RATIO_CEILING

    # A tell-free sentence can never exceed the ceiling on the lite path.
    for s in _HUMAN_SENTENCES + [_BLAND_AI_SENTENCE]:
        assert lite_score(s) <= _RATIO_CEILING + 1e-9, f"lite cap breached by {s!r}"


def test_perplexity_burstiness_is_deliberately_not_windowed():
    """Pins a negative result, because this looks like a missing feature and was once "fixed".

    Every supervised adapter wraps its scorer in `windowed_max`, because `truncation=True,
    max_length=512` meant they could not see past ~380 words. This detector has no such limit and
    both its terms are aggregate: burstiness is the variation of sentence lengths ACROSS a
    document, and the common-word ratio is a document-wide proportion. Windowing destroys the
    quantity being measured, and max-of-many-noisy-windows inflates long input.

    MEASURED on real HC3 documents, windowed vs whole-document:
        3 paragraphs   AUROC 0.887 / FPR 90%   vs   0.975 / FPR 30%
        6 paragraphs   AUROC 0.980 / FPR 90%   vs   1.000 / FPR  0%
    TPR was 100% either way — windowing bought nothing and flagged 9 of 10 human documents.
    """
    import inspect

    import untell.detectors.perplexity_burstiness as pb

    assert "windowed_max(" not in inspect.getsource(pb.PerplexityBurstinessDetector.score), (
        "perplexity_burstiness must stay whole-document: windowing it measured AUROC 0.887 vs "
        "0.975 and FPR 90% vs 30% on 3-paragraph HC3 documents"
    )


def test_long_document_scoring_is_stable_not_inflated():
    """A long stretch of ordinary human prose must not become AI-flagged just for being long.

    This is the failure mode that windowing this detector produced: the max over many windows of a
    weak signal climbs with document length regardless of content.

    The paragraphs must be DISTINCT. A first version of this test repeated one paragraph twelve
    times, which passed on the stdlib path and failed under the GPT-2 backend — correctly. Verbatim
    repetition is extremely predictable, so it reads as machine-written on its own merits
    (0.140 -> 0.625 across 12 copies), and the test was measuring repetition rather than length.
    """
    paragraphs = [
        "I went to the store and forgot the milk again. Third time this month, embarrassing.",
        "The build broke because someone bumped the pinned version. Took me an hour to spot it.",
        "She said it was fine, but her face said otherwise, so I dropped it and left.",
        "We tried it twice and it still did not work. Nobody wanted to admit we were stuck.",
        "Turns out the cable was loose the whole time. I laughed, then I did not laugh.",
        "He emailed back three days later with one line: no. That was the whole message.",
        "The dog got out through the gate again. I have started counting how often it happens.",
        "My neighbour repainted his fence bright orange. Nobody has said a word to him about it.",
    ]
    from untell.scripts.score import DEFAULT_THRESHOLD

    det = PerplexityBurstinessDetector()
    scores = {n: det.score(" ".join(paragraphs[:n])) for n in (2, 4, 8)}
    assert all(s is not None for s in scores.values())

    # The property this test exists for, and it must hold on either backend.
    assert scores[8] <= scores[2] + 0.10, (
        f"score climbs with length on human prose: {scores[2]:.3f} (2 paras) -> {scores[8]:.3f} (8)"
    )

    # Whether this prose is flagged at all is only assertable on the GPT-2 backend. The pure-stdlib
    # heuristic scores it 0.48-0.53 — above threshold — which is the known weakness the code already
    # documents (measured per-sentence AUROC 0.493, a coin flip). Asserting it there would be
    # asserting the heuristic is good, which it is not and does not claim to be.
    if det._torch_ready():
        for n, s in scores.items():
            assert s < DEFAULT_THRESHOLD, f"{n} paragraphs of ordinary human prose flagged at {s:.3f}"


class TestShortInputAbstentionIsPathIndependent:
    """`_MIN_WORDS_FOR_SIGNAL` must hold on BOTH scoring paths, not just the stdlib one.

    The floor lived only inside `lite_score`. `score()` routes to the GPT-2 path whenever torch is
    importable — the default once .[full] is installed — and that path has only a token-count guard,
    which trips at one token rather than five words. Measured before:

        "Hi."                   -> 0.811   a two-token fragment reported as AI
        "word word"             -> 0.000   "definitely human", from two words
        "word word word word"   -> 0.000   same

    Both are confident verdicts drawn from no stylometric evidence, and both reach the ensemble max
    as if they were measurements.
    """

    @pytest.mark.parametrize("n", [0, 1, 2, 3, 4])
    def test_detector_abstains_below_the_floor(self, n):
        from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector

        assert PerplexityBurstinessDetector().score(" ".join(["word"] * n)) is None

    @pytest.mark.parametrize(
        "text", ["Hi.", "The cat sat.", "Yes!", "No, never.", "Stop -- now."]
    )
    def test_short_real_fragments_abstain(self, text):
        """Punctuation makes these several TOKENS but still fewer than five words, which is the
        gap the token-count guard left open."""
        from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector

        assert PerplexityBurstinessDetector().score(text) is None

    def test_five_words_is_scored(self):
        """The floor must not swallow real input: at the boundary the detector still answers."""
        from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector

        v = PerplexityBurstinessDetector().score("The cat sat on the mat.")
        assert v is not None and 0.0 <= v <= 1.0

    def test_score_text_reports_an_abstention_rather_than_a_verdict(self):
        from untell.scripts.score import score_text

        r = score_text("Hi.", tier="lite")
        assert r.get("scored") is False
        assert r.get("warning")
        assert r.get("flagged") is False


class TestWindowingCoversTextWithoutSentenceTerminators:
    """A "sentence" wider than a window could never be packed, so it passed through whole.

    The size test is skipped for the first piece of a window (`if current and ...`), exactly as in
    BackTranslator._chunk. Any text with no sentence terminators is ONE sentence to the splitter,
    which covers transcripts, bullet lists, headings-only outlines, semicolon run-ons and single
    very long sentences. Each was handed to the adapter whole and then truncated at ~380 words by
    its own `truncation=True`, and scored confidently on that fraction — the precise failure
    windowing exists to prevent.

    Measured before, at a 320-word window: a 1600-word bullet list produced one window of 1600
    words, a 1200-word transcript one of 1200, a 900-word run-on one of 900.
    """

    SHAPES = {
        "no terminators": " ".join(f"word{i}" for i in range(900)),
        "newline-separated": "\n".join(f"line {i} of the transcript here" for i in range(200)),
        "bullet list": "\n".join(f"- item number {i} in the list here" for i in range(200)),
        "semicolon run-on": "; ".join(f"clause number {i} of the run-on" for i in range(200)),
        "one enormous sentence": " ".join(f"word{i}" for i in range(900)) + ".",
        "headings only": "\n".join(f"## Section {i} heading text" for i in range(200)),
        "normal prose": " ".join(f"This is sentence number {i} with a few words." for i in range(120)),
    }

    @pytest.mark.parametrize("label", sorted(SHAPES))
    def test_no_window_exceeds_the_cap(self, label):
        from untell.detectors.base import WINDOW_WORDS, windowed_max

        seen: list[str] = []
        windowed_max(self.SHAPES[label], lambda w: seen.append(w) or 0.5)
        assert seen
        for w in seen:
            assert len(w.split()) <= WINDOW_WORDS, (
                f"{label}: window of {len(w.split())} words exceeds the {WINDOW_WORDS} cap, so the "
                "adapter will truncate it"
            )

    @pytest.mark.parametrize("label", sorted(SHAPES))
    def test_no_word_is_dropped(self, label):
        from untell.detectors.base import windowed_max

        text = self.SHAPES[label]
        seen: list[str] = []
        windowed_max(text, lambda w: seen.append(w) or 0.5)
        assert " ".join(seen).split() == text.split(), f"{label}: windowing lost or reordered words"

    def test_short_text_is_still_one_call(self):
        """Nothing may change for ordinary input."""
        from untell.detectors.base import WINDOW_WORDS, windowed_max

        text = " ".join(f"word{i}" for i in range(WINDOW_WORDS))
        seen: list[str] = []
        windowed_max(text, lambda w: seen.append(w) or 0.5)
        assert seen == [text]

    def test_aggregation_is_still_the_max_and_none_survives(self):
        from untell.detectors.base import windowed_max

        doc = self.SHAPES["normal prose"]
        vals = iter([0.1, 0.9, 0.3, 0.2, 0.4, 0.5])
        assert windowed_max(doc, lambda w: next(vals, 0.0)) == 0.9
        mixed = iter([None, 0.7, None, None, None, None])
        assert windowed_max(doc, lambda w: next(mixed, None)) == 0.7
        assert windowed_max(doc, lambda w: None) is None


class TestDetectorsDoNotFlagHumanWriting:
    """A detector that flags human prose is worse than useless to the person running it.

    MEASURED on 40 HC3 pairs at the default threshold, before the calibration fixes:
    fast_detectgpt scored human text at a mean of 0.510 and flagged 92% of it, perplexity_burstiness
    flagged 32%, and because the ensemble aggregates with `max` the full tier flagged 95% of human
    documents. The loop then rewrites that text, spending meaning-similarity to fix nothing.

    Nothing in the suite failed. `untell-detector-audit` reported both detectors healthy at AUROC
    0.999+ the entire time, because AUROC is threshold-free: it asks whether a detector RANKS the
    classes correctly, which both did perfectly, and cannot see one reporting on a scale that puts
    ordinary human prose over the line. Fixing them moved AUROC by at most 0.001.

    This guards the property AUROC cannot: at the threshold the product actually ships, human text
    must come back clean.
    """

    @staticmethod
    def _human_probes():
        from eval.detector_audit import HUMAN_PROBES

        return HUMAN_PROBES

    @pytest.mark.parametrize("tier", ["lite", "full"])
    def test_human_probes_are_not_flagged(self, tier):
        from untell.scripts.score import DEFAULT_THRESHOLD, score_text

        probes = self._human_probes()
        scores = [float(score_text(t, tier=tier)["max"]) for t in probes]
        flagged = [s for s in scores if s >= DEFAULT_THRESHOLD]
        # One borderline probe out of five is tolerable; a calibration regression flags four or five.
        assert len(flagged) <= 1, (
            f"tier={tier}: {len(flagged)}/{len(probes)} human probes flagged at "
            f"{DEFAULT_THRESHOLD} (scores {[round(s, 3) for s in scores]}). A detector is reporting "
            "human writing as machine-generated — check its calibration constants, not its AUROC."
        )

    @pytest.mark.parametrize("tier", ["lite", "full"])
    def test_human_probes_score_well_below_ai_probes(self, tier):
        """Separation must survive the calibration, not just the false-positive rate.

        Asserted on the MEANS with a margin, not as strict separation: five hand-written probes per
        class are too few for the extremes to be stable, and the audit's own verdicts distinguish
        OK from OK_SEPARATED for the same reason. Measured here, human max 0.272 sits above AI min
        0.219 on lite, which is noise at this sample size rather than a broken detector — the 40-pair
        HC3 run gives AUROC 1.000.
        """
        import statistics

        from eval.detector_audit import AI_PROBES
        from untell.scripts.score import score_text

        human = [float(score_text(t, tier=tier)["max"]) for t in self._human_probes()]
        ai = [float(score_text(t, tier=tier)["max"]) for t in AI_PROBES]
        gap = statistics.mean(ai) - statistics.mean(human)
        assert gap > 0.15, (
            f"tier={tier}: mean gap {gap:.3f} — human {[round(x, 3) for x in human]} "
            f"vs ai {[round(x, 3) for x in ai]}"
        )


class TestEverySupervisedAdapterWindows:
    """An adapter that truncates but never windows reads only the first ~380 words.

    `truncation=True, max_length=N` discards everything past the cap silently, so a document with a
    long human preamble scores as human no matter what follows. That was fixed for hc3_roberta,
    roberta_openai, mage and fast_detectgpt — and missed for radar and binoculars, both of which
    sit outside the default tiers and so were absent from the runs the fix was verified against.

    MEASURED on radar: a 2887-word document whose final 207 words were AI scored 0.113, while
    windowed hc3_roberta scored 0.999 on the same input. RADAR scores the AI block alone at 0.995,
    so the detector was never the problem — it simply never saw the text.

    A grep guard rather than a behavioural one because these two adapters need models this suite
    does not download, so nothing else can catch a regression here.
    """

    EXEMPT = {
        # Documented, and measured: this one is a document-level aggregate (burstiness is the
        # variance of sentence lengths ACROSS a document) and windowing destroys the quantity it
        # measures. It reads the whole text natively instead of truncating.
        "perplexity_burstiness.py": "not truncated at all; windowing would break the aggregate",
        # A generative judge, not a classifier — there is no per-window score to take a max over,
        # and it is opt-in and off by default.
        "local_judge.py": "generative judge, opt-in, no per-window score",
    }

    def test_no_adapter_truncates_without_windowing(self):
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent / "untell" / "detectors"
        offenders = []
        for path in sorted(root.glob("*.py")):
            if path.name in ("base.py", "__init__.py") or path.name in self.EXEMPT:
                continue
            body = path.read_text(encoding="utf-8", errors="replace")
            if "truncation=True" in body and "windowed_max" not in body:
                offenders.append(path.name)

        assert not offenders, (
            f"{offenders} truncate their input without windowing it, so they read only the first "
            "~380 words of any document and score the rest as if it were not there. Wrap the "
            "per-window call in windowed_max, or add an entry to EXEMPT explaining why not."
        )


class TestLiteTierFalsePositiveRateIsDocumented:
    """AUROC hides calibration, and this repo has been bitten by it before.

    MEASURED on 100 real HC3 pairs, stdlib path, at the shipped 0.30 threshold:
        HUMAN text flagged 65%      AI text flagged 99%      AUROC 0.810
    The separation is real; the threshold is mis-placed for this tier (0.55 -> 15%/53%,
    0.60 -> 9%/41%). This pins the number to the README so it cannot quietly drift, and pins
    the property that makes it matter: at 0.30 the stdlib tier flags most human writing.
    """

    HUMAN = [
        "I walked to the shop this morning and it was shut. Typical. The sign said back at two "
        "but nobody turned up until nearly three, and by then I had given up and gone home.",
        "My dad taught me to change a tyre when I was fifteen. I have needed it twice since. Both "
        "times in the rain, both times on a road with no lay-by, which feels like a rule.",
    ]

    def test_the_readme_states_the_measured_false_positive_rate(self):
        """A caveat of 'weak' does not tell a user that most human text gets flagged."""
        from pathlib import Path

        readme = Path(__file__).resolve().parents[1] / "README.md"
        row = [ln for ln in readme.read_text(encoding="utf-8").splitlines()
               if ln.startswith("| **lite**")]
        assert row, "the lite tier row is missing from the README tier table"
        assert "65%" in row[0], "the measured human false-positive rate is not stated"

    def test_lite_scores_are_high_enough_on_human_text_to_justify_the_warning(self, monkeypatch):
        """Guards the direction, not the exact rate: if human text stopped scoring near the
        threshold the README paragraph would be stale and should be re-measured."""
        monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
        from untell.scripts.score import score_text

        scores = [score_text(t, tier="lite")["max"] for t in self.HUMAN]
        assert all(0.0 <= s <= 1.0 for s in scores)
        assert max(scores) > 0.15, (
            "human text now scores far below the 0.30 threshold on the stdlib path — the "
            "documented 65% false-positive rate may no longer hold; re-measure it"
        )


class TestDegenerateRepetitionIsNotHuman:
    """`"test " * 100` scored 0.000 on the stdlib path — the single most human number available.

    Nothing in the heuristic noticed repetition: burstiness needs two sentences and the
    common-word ratio of a repeated rare word is near zero, so the most machine-like text there is
    came out cleaner than any real writing. It matters twice: a user pasting repetitive text is
    told it is perfectly human, and the LOOP maximises against this score, so a rewriter that
    degenerates into repetition would win outright.

    The floor is type-token ratio 0.25, chosen from a gap with nothing in it — MEASURED over 800
    HC3 texts, the lowest real ratio is 0.440; the degenerate cases sit at 0.010-0.050.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "test " * 100,
            "yes no " * 50,
            "This is a test. " * 20,
            " ".join(["alpha beta gamma delta epsilon"] * 20),
        ],
    )
    def test_repetition_reads_as_machine(self, text):
        from untell.detectors.perplexity_burstiness import lite_score

        assert lite_score(text) == 1.0

    def test_the_term_is_silent_on_every_real_hc3_text(self):
        """A new term in a detector with published FPR/TPR has to be provably inert on real text."""
        from eval.datasets import _BUILTIN
        from untell.detectors.perplexity_burstiness import _repetition_signal

        for text in _BUILTIN:
            assert _repetition_signal(text) == 0.0

    def test_short_text_gets_no_repetition_verdict(self):
        """Under 40 words the ratio is unstable, so the term says nothing rather than guessing."""
        from untell.detectors.perplexity_burstiness import _repetition_signal

        assert _repetition_signal("test test test test test test test test") == 0.0
