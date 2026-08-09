"""The rewriter must not damage the text mechanically, and nothing was checking.

Every other suite in this repo asks whether the output evades a detector or preserves meaning.
None of them asks whether it is *well-formed English*, and `score_tells` cannot: a sentence
fragment, an unbalanced quotation and a dangling coordinator are all perfectly clean to a tell
catalogue. Six real defects were found in one session by reading rewritten corpus text by hand:

    "There are other options for melting ice on roads. Such as using chemicals ..."
    "In this paper, we show EdgeFlow. A new way to interactive segmentation ..."
    "... in combination with other techniques, but. Salt is often the most effective ..."
    'He said "the result is robust.' / 'It replicates", which the reviewers accepted.'
    "The authors, Smith, Jones, and Patel." / "Reported that the effect held ..."
    "Because the encoder is small it runs fast, the model works well and."

This file turns that reading into a battery. Every check is scored on the OUTPUT and on the
SOURCE, and only a positive delta is a failure — the corpora contain their own artefacts and the
rewriter must not be blamed for those.

Deliberately corpus-free: the fixtures are constructed to carry the shapes that broke, so the
battery runs in CI with no download. The corpus version lives in the session scratchpad and is
what produced the numbers quoted above.
"""

from __future__ import annotations

import random
import re

import pytest

from untell.rewriter.structural import structural_rewrite
from untell.text_split import split_sentences

# Each check is (name, pattern). A match is damage.
_CHECKS: dict[str, re.Pattern[str]] = {
    "double_space": re.compile(r"[^\s]  +[^\s]"),
    "space_before_punctuation": re.compile(r"\s+[,.;:!?]"),
    "doubled_punctuation": re.compile(r"[,.;:]{2,}|\.\s*\."),
    "comma_then_period": re.compile(r",\s*\."),
    "empty_parentheses": re.compile(r"\(\s*\)"),
    "lowercase_after_full_stop": re.compile(r"[.!?]\s+[a-z]"),
    "doubled_word": re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE),
    "a_before_vowel": re.compile(r"\ba\s+[aeiouAEIOU]\w"),
    "an_before_consonant": re.compile(r"\ban\s+[bcdfgjklmnpqrstvwxyz]\w", re.IGNORECASE),
    "dangling_coordinator": re.compile(r"\b(and|but|or|so|because|while|which)\s*[.!?]"),
    "doubled_particle": re.compile(r"\b(to|of|in|on|for|with|through)\s+\1\b", re.IGNORECASE),
}

# Leads that cannot open an independent clause, so a sentence starting with one is a fragment.
# Openers the rewriter legitimately prepends are stripped before judging — "Of course, in this
# paper." must be blamed on the fragment, not on the opener, and an early version of this battery
# counted every "Of course," as damage for exactly that reason.
_OUR_OPENERS = (
    "actually", "in practice", "in short", "put simply",
    "also", "now", "basically", "well", "of course",
)
_FRAGMENT_LEADS = {"such", "which", "who", "whom", "including", "of", "as", "than", "can"}

# Paragraphs carrying every shape that has broken: exemplifier and appositive commas, a serial
# list, a quotation containing a coordinator, a trailing subordinate clause, a proper noun that
# must not be lowercased, an abbreviation, and a number with a comma in it.
_FIXTURES = [
    "There are other options for melting ice and snow on roads, such as using chemicals like"
    " calcium chloride or magnesium chloride, or using mechanical methods like plows and sand."
    " However, salt is often the most effective and affordable option for most municipalities."
    " The ice melts on the road surface because salt lowers the freezing point of the water.",

    "In this paper, we present EdgeFlow, a novel approach to interactive image segmentation that"
    " leverages edge-guided flow to reach practical accuracy on a tight annotation budget."
    " Existing methods are often limited by their heavy reliance on repeated iterative user"
    " input, which can be extremely time-consuming for a working analyst in the field."
    " Moreover, the authors, Smith, Jones, and Patel, reported that the effect held at every site.",

    'He said "the result is robust, and it replicates", which the reviewers accepted without'
    " further argument. The study enrolled 3,000 participants across twelve separate sites, and"
    " the follow-up ran for two full years afterwards. Revenue rose in Q1, Q2, and Q3, but the"
    " fourth quarter fell short of the target by a considerable margin overall.",

    "NASA confirmed the result because the second probe returned matching data from orbit."
    " Dr. Smith published the findings in a journal that is read widely across the discipline."
    " The system leverages robust methodologies to optimize operational efficiency, and it is"
    " crucial to underscore the pivotal role of comprehensive frameworks in this domain.",
]


def _strip_our_opener(sentence: str) -> str:
    low = sentence.strip()
    for opener in _OUR_OPENERS:
        if low.lower().startswith(opener + ","):
            return low[len(opener) + 1:].strip()
    return low


def _damage(text: str) -> dict[str, int]:
    found = {name: len(pat.findall(text)) for name, pat in _CHECKS.items()}
    fragments = 0
    for sentence in split_sentences(text):
        body = _strip_our_opener(sentence)
        words = body.split()
        if not words:
            continue
        if words[0].rstrip(",.;:").lower() in _FRAGMENT_LEADS:
            fragments += 1
    found["fragment_lead"] = fragments
    found["unbalanced_quotes"] = 1 if text.count('"') % 2 else 0
    # Brackets, checked because `_parenthesise_asides` creates them. A transform that can OPEN a
    # bracket can leave one open, and an unbalanced bracket is the loudest possible artefact.
    found["unbalanced_parens"] = abs(text.count("(") - text.count(")"))
    # A sentence under four words is a stranded opener or a list item, not a sentence. Counted
    # here rather than only in the corpus sweep, where it is the one check still showing a
    # positive delta (+1 across 60 texts, down from +4). The fixtures below must not add any.
    found["stub_sentence"] = sum(
        1 for s in split_sentences(text) if 0 < len(_strip_our_opener(s).split()) < 4
    )
    return found


@pytest.mark.parametrize("source", _FIXTURES)
@pytest.mark.parametrize("intensity", [0.5, 1.0])
def test_the_rewriter_introduces_no_mechanical_damage(source, intensity):
    """Scored against the SOURCE, so an artefact already in the input is not a failure."""
    baseline = _damage(source)
    for seed in range(25):
        random.seed(seed)
        out = structural_rewrite(source, intensity=intensity)
        after = _damage(out)
        worse = {k: (baseline[k], after[k]) for k in after if after[k] > baseline[k]}
        assert not worse, (
            f"seed {seed}, intensity {intensity}: {worse}\n--- source ---\n{source}\n"
            f"--- output ---\n{out}"
        )


@pytest.mark.parametrize("source", _FIXTURES)
def test_the_rewriter_actually_changes_these_fixtures(source):
    """Anti-vacuity. A rewriter that returned its input unchanged would pass every check above,
    and "too conservative to do anything" is a failure mode this pipeline has hit five times."""
    changed = False
    for seed in range(25):
        random.seed(seed)
        if structural_rewrite(source, intensity=1.0).strip() != source.strip():
            changed = True
            break
    assert changed, "the rewriter left the fixture untouched, so the battery proves nothing"


def test_every_check_can_actually_fire():
    """A pattern that matches nothing is dead coverage that looks alive — this repo has shipped
    six of those before (`\\b` written into a non-raw string became U+0008)."""
    probes = {
        "double_space": "the  cat sat",
        "space_before_punctuation": "the cat , sat",
        "doubled_punctuation": "the cat sat,, and",
        "comma_then_period": "the cat sat, .",
        "empty_parentheses": "the cat () sat",
        "lowercase_after_full_stop": "The cat sat. the dog",
        "doubled_word": "the the cat",
        "a_before_vowel": "a apple",
        "an_before_consonant": "an cat",
        "dangling_coordinator": "the cat sat and.",
        "doubled_particle": "walk to to the shop",
    }
    assert set(probes) == set(_CHECKS), "a check has no probe, or a probe has no check"
    for name, probe in probes.items():
        assert _CHECKS[name].search(probe), f"{name} cannot match its own example"


# ---------------------------------------------------------------------------
# The same battery, over every CPU-only rewriter rather than the structural one alone.
# ---------------------------------------------------------------------------

# structural was the only offender when this was written — surgical came back clean on all four
# fixtures and lock/restore round-tripped exactly — but "clean today" is not a guarantee, and the
# six defects above all lived in code that had been passing its own tests for months.
_CPU_REWRITERS = ["structural", "surgical", "composite", "targeted"]


@pytest.mark.parametrize("name", _CPU_REWRITERS)
def test_no_cpu_rewriter_damages_the_text(name):
    """Registry-driven, so a rewriter added later is covered without anyone remembering to add it.

    Only the CPU-only backends: `neural`, `t5_paraphrase` and `mt_pivot` need model downloads and
    `ensemble`/`max` fan out to all of them, which does not belong in a unit run.
    """
    from untell.rewriter import get_rewriter

    rw = get_rewriter(name)
    if rw is None or not rw.available():
        pytest.skip(f"{name} unavailable in this environment")

    for source in _FIXTURES:
        baseline = _damage(source)
        for seed in range(8):
            random.seed(seed)
            out = rw.rewrite(source, {"max": 0.9})
            worse = {k: (baseline[k], v) for k, v in _damage(out).items() if v > baseline[k]}
            assert not worse, (
                f"{name}, seed {seed}: {worse}\n"
                f"--- source ---\n{source}\n--- output ---\n{out}"
            )


def test_the_cpu_rewriter_list_is_not_stale():
    """A name that no longer resolves would skip forever and look like coverage."""
    from untell.rewriter import get_rewriter

    for name in _CPU_REWRITERS:
        assert get_rewriter(name) is not None, f"{name} is no longer a registered rewriter"


@pytest.mark.parametrize("source", _FIXTURES)
def test_locking_round_trips_exactly(source):
    """The preserve layer is what protects citations and numbers, and a lossy restore would be
    invisible to every check above — the text would be well-formed and simply wrong."""
    from untell.scripts.preserve import lock, restore

    masked, spans = lock(source)
    assert restore(masked, spans) == source


# ---------------------------------------------------------------------------
# Content preservation — the check that tells a defect from a corpus artefact
# ---------------------------------------------------------------------------

# Words the rewriter is SUPPOSED to remove: formulaic transitions it strips, filler openers, and
# the AI vocabulary it substitutes. Everything else is the user's content.
_MAY_REMOVE = {
    "moreover", "furthermore", "additionally", "overall", "notably", "importantly",
    "consequently", "therefore", "thus", "hence", "ultimately", "nevertheless", "nonetheless",
    "accordingly", "subsequently", "arguably", "indeed", "essentially", "conclusion", "summary",
    "in", "it", "is", "worth", "noting", "that", "should", "be", "noted", "the", "a", "an",
}


@pytest.mark.parametrize("source", _FIXTURES)
def test_no_content_word_is_silently_dropped(source):
    """A rewrite redistributes and substitutes; it must not DELETE the user's content.

    This is the check that separates a real defect from a corpus artefact. Chasing the last
    `stub_sentence` residual led to output ending "TAN is" — which looked like truncation until the
    source turned out to end mid-sentence at "In conclusion, TAN represents". The RAID sample is
    cut off; the rewriter stripped the transition from an already-broken tail. Word count went
    329 -> 343, so nothing had been lost, and a stub count could not tell the two cases apart.
    """
    import re as _re2

    for seed in range(15):
        random.seed(seed)
        out = structural_rewrite(source, intensity=1.0)
        before = {w.lower() for w in _re2.findall(r"[A-Za-z]{4,}", source)}
        after = {w.lower() for w in _re2.findall(r"[A-Za-z]{4,}", out)}
        lost = before - after - _MAY_REMOVE
        # Substitution legitimately replaces a word with a synonym, so a handful of losses is
        # expected. Wholesale deletion is not: losing a third of the distinct content vocabulary
        # means a sentence went missing.
        assert len(lost) <= max(3, len(before) // 5), (
            f"seed {seed}: {len(lost)} of {len(before)} content words vanished: {sorted(lost)[:12]}"
        )


@pytest.mark.parametrize("source", _FIXTURES)
def test_the_output_is_not_shorter_than_the_input_by_much(source):
    """Length collapse is the loudest form of content loss and the cheapest to check."""
    for seed in range(15):
        random.seed(seed)
        out = structural_rewrite(source, intensity=1.0)
        assert len(out.split()) >= 0.75 * len(source.split()), (
            f"seed {seed}: {len(source.split())} words in, {len(out.split())} out"
        )


class TestInputShapesTheCorporaDoNotContain:
    """Every measurement in this repo runs on HC3 forum answers or RAID paper abstracts:
    continuous prose, third person, declarative. Users paste other things. Reading the output on
    other shapes found two defects that no metric here could see — a tell catalogue scores
    "and i believe" as perfectly clean, and a mangled quotation as clean too.
    """

    @staticmethod
    def _many(text: str, n: int = 60):
        import random

        from untell.rewriter.composite import CompositeRewriter

        rewriter = CompositeRewriter()
        out = []
        for seed in range(n):
            random.seed(seed)
            out.append(rewriter.rewrite(text, {"tier": "lite", "max": 0.9}))
        return out

    def test_the_pronoun_i_is_never_lowercased(self):
        """`"i"` sat in the 220-word `_SAFE_TO_LOWERCASE` list among the other pronouns, and it is
        the one word in English that is never lower case. Output: "The system was slow, and i
        believe the cache was cold."
        """
        for text in (
            "The system was slow. I believe the cache was cold at that moment in time.",
            "I have been working on this for months. Moreover, I believe the approach is sound.",
            "It failed again, and I could not tell why the retry logic never fired at all.",
        ):
            for got in self._many(text):
                assert " i " not in got and not got.startswith("i "), got
                assert " i'" not in got and " i," not in got, got

    def test_a_quoted_sentence_is_not_merged_into_the_one_before_it(self):
        """Dialogue produced: '"...," she said, and "And, the cost is prohibitive.".' — the
        connector landed before an opening quote, and the quoted sentence's own full stop is inside
        the quotation where rstrip cannot reach it, so the merge appended a second one.
        """
        text = (
            '"I told you it would not scale," she said. "Moreover, the cost is prohibitive." '
            "He shrugged."
        )
        for got in self._many(text, n=40):
            assert ', and "' not in got, f"merged into a quotation: {got}"
            assert '".' not in got.replace('."', ""), f"stranded stop after a quote: {got}"

    def test_a_citation_sentence_survives_a_following_transition(self):
        text = (
            'As Smith (2019) argues, "the effect is robust across settings." '
            "Moreover, Jones et al. (2021) replicate it in three further domains."
        )
        for got in self._many(text, n=40):
            assert "(2019)" in got and "(2021)" in got, f"citation lost: {got}"
            assert got.count('"') % 2 == 0, f"unbalanced quotes: {got}"

    def test_urls_and_emails_survive_intact(self):
        text = (
            "See https://example.com/docs?a=1&b=2 for details, or write to a.b@example.com. "
            "Moreover, the mirror at http://alt.example.org leverages the same index."
        )
        for got in self._many(text, n=30):
            assert "https://example.com/docs?a=1&b=2" in got, got
            assert "a.b@example.com" in got, got
            assert "http://alt.example.org" in got, got

    def test_a_numeric_paragraph_keeps_every_figure(self):
        text = (
            "Revenue grew 23% to $4.2M in Q3 2024, up from $3.4M. Moreover, margins improved "
            "180 basis points to 34.5% across all twelve regions."
        )
        for got in self._many(text, n=30):
            for token in ("23%", "$4.2M", "Q3 2024", "$3.4M", "180", "34.5%"):
                assert token in got, f"lost {token!r}: {got}"

    def test_a_numbered_list_keeps_its_structure(self):
        text = (
            "The system has three components:\n\n1. A parser that reads the input.\n"
            "2. A scorer that leverages a robust model.\n3. A writer that emits the result.\n\n"
            "Furthermore, each component is independently testable."
        )
        for got in self._many(text, n=30):
            for marker in ("1.", "2.", "3."):
                assert marker in got, f"list marker {marker} lost: {got!r}"
            assert got.count("\n") >= 4, f"line structure collapsed: {got!r}"

    def test_inline_code_spans_stay_balanced(self):
        text = (
            "Call `score_text(text, tier='full')` to get a result. Moreover, the `threshold` "
            "argument leverages a calibrated cutoff for the verdict."
        )
        for got in self._many(text, n=30):
            assert got.count("`") == 4, f"backticks unbalanced: {got}"
            assert "score_text(text, tier='full')" in got, got


class TestWordsThatCarryTheirPreposition:
    """"An approach TO segmentation" is idiomatic; "a method to segmentation" is not.

    Substituting the noun alone strands the preposition on a synonym that does not take it. Found
    indirectly: the repaired contradiction gate began vetoing real candidates, and three of the four
    it caught were not meaning changes at all — they were this, plus "An unsupervised segmentation
    approach" turning into "An unsupervised segmentation way". The NLI model reads badly-formed
    English as not-entailing, which is fair, and it noticed before any human did.
    """

    @staticmethod
    def _many(text: str, n: int = 60):
        import random

        from untell.rewriter.composite import CompositeRewriter

        rewriter = CompositeRewriter()
        out = []
        for seed in range(n):
            random.seed(seed)
            out.append(rewriter.rewrite(text, {"tier": "lite", "max": 0.9}))
        return out

    def test_approach_to_keeps_its_preposition(self):
        text = (
            "We propose a novel approach to medical image segmentation. An unsupervised "
            "segmentation approach was used throughout the study."
        )
        for got in self._many(text):
            low = got.lower()
            for broken in ("method to medical", "technique to medical", "way to medical",
                           "route to medical", "segmentation way", "segmentation route"):
                assert broken not in low, f"{broken!r} in: {got}"

    def test_other_preposition_bound_nouns_survive(self):
        text = (
            "This offers a practical solution to the scaling problem. The team had access to the "
            "full dataset. The paper provides insight into the failure mode."
        )
        for got in self._many(text, n=40):
            low = got.lower()
            for broken in ("answer to the scaling", "entry to the full", "look into the failure"):
                assert broken not in low, f"{broken!r} in: {got}"

    def test_the_noun_still_varies_where_no_preposition_follows(self):
        """The guard must decline one substitution, not disable the word. A rule that froze
        "approach" everywhere would cost a common substitution to fix a narrow case.

        Asserted against `_plain_register`, which owns the substitution, rather than through the
        composite rewriter. Composite is deterministic on a sentence this short — 40 seeds give one
        output — so a test at that level would pass or fail for reasons unrelated to the guard.
        """
        import random

        from untell.rewriter.structural import _plain_register

        text = "An unsupervised segmentation approach was used throughout the study."
        outputs = set()
        for seed in range(30):
            random.seed(seed)
            outputs.add(_plain_register(text, intensity=1.0))
        changed = [o for o in outputs if "segmentation approach" not in o.lower()]
        assert changed, f"the noun never varied — the guard is too broad: {outputs}"

    def test_the_collocation_table_is_populated(self):
        """Guards the guard: an empty table makes every assertion above vacuous."""
        from untell.rewriter.structural import _PREPOSITION_BOUND

        assert len(_PREPOSITION_BOUND) >= 10
        assert _PREPOSITION_BOUND["approach"] == frozenset({"to"})
