"""Structural rewriter — sentence-level transformations without an LLM.

The surgical rewriter (``SurgicalRewriter``) does word-level synonym substitution. This rewriter
does **structural** transformations: it strips formulaic transitions, merges/splits sentences,
flattens participial trailers, breaks negated contrasts, and varies sentence openings — all
without an API key, GPU, or model download.

These are the exact transformations that move the needle on the local detector ensemble
(perplexity/burstiness respond to sentence-length variance; supervised detectors respond to
formulaic structure). Combining structural + surgical transforms gives the free $0 path
**far more leverage** than either alone.

Always ``available()``. Deterministic (identical input → identical output for a given seed).
"""

from __future__ import annotations

import random
import re

from untell.layout import apply_per_block
from untell.rewriter.base import Rewriter
from untell.text_split import split_sentences

# ---------------------------------------------------------------------------
# Sentence-level patterns
# ---------------------------------------------------------------------------

# (sentence splitting lives in untell.text_split — imported above)

# Words it is safe to lowercase when a sentence becomes a subordinate clause. Anything outside this
# set is left capitalised and the merge is SKIPPED, because the alternative — lowercasing whatever
# happens to start the sentence — turns "Smith published" into "smith published" and "NASA
# confirmed" into "nASA confirmed". Fewer merges is a cheap price for never mangling a name.
_SAFE_TO_LOWERCASE = {
    # function words and determiners
    "the", "this", "that", "these", "those", "a", "an", "it", "its", "they", "their", "them",
    "he", "his", "him", "she", "her", "we", "our", "us", "you", "your", "i", "my", "there",
    "here", "some", "many", "most", "much", "all", "each", "every", "both", "few", "several",
    "one", "two", "three", "no", "not", "if", "when", "while", "after", "before", "since",
    "because", "although", "though", "unless", "until", "as", "but", "and", "or", "so", "yet",
    "in", "on", "at", "for", "from", "with", "without", "by", "to", "into", "over", "under",
    "such", "other", "another", "any", "who", "which", "what", "how", "why", "where",
    # ordinary nouns that routinely open a sentence in expository prose
    "people", "operators", "users", "results", "data", "studies", "research", "researchers",
    "companies", "organizations", "organisations", "businesses", "students", "customers",
    "patients", "developers", "engineers", "teams", "systems", "models", "tools", "machine",
    "software", "hardware", "technology", "technologies", "industries", "governments",
    "scientists", "doctors", "workers", "employees", "managers", "leaders", "experts",
    "evidence", "analysis", "performance", "efficiency", "productivity", "growth", "costs",
    "benefits", "risks", "challenges", "problems", "solutions", "changes", "effects",
    "impact", "adoption", "training", "testing", "development", "production", "demand",
    "supply", "prices", "revenue", "profits", "sales", "markets", "clients",
    "documents", "files", "records", "reports", "papers", "articles", "books", "sources",
    "methods", "approaches", "techniques", "strategies", "policies", "practices", "processes",
    "exercise", "nutrition", "health", "treatment", "symptoms", "trials",
    "climate", "energy", "emissions", "pollution", "temperatures", "weather", "sea",
    "education", "schools", "teachers", "learning", "knowledge", "skills", "experience",
    # common adjectives and adverbs in the same position
    "artificial", "regular", "effective", "modern", "current", "recent", "further", "additional",
    "similar", "different", "specific", "general", "overall", "typical", "common", "important",
    "significant", "large", "small", "high", "low", "new", "old", "good", "better", "best",
    "worse", "worst", "early", "late", "fast", "slow", "long", "short", "clear", "likely",
    "unlike", "despite", "given", "based", "using", "according",
}

# Capitalisation that is never sentence-position capitalisation: an internal capital (NASA, iPhone,
# McDonald) always signals a name or acronym, whatever the word list says.
_INTERNAL_CAPS_RE = re.compile(r"^[A-Za-z][a-z]*[A-Z]")

def _safe_to_lowercase(word: str, context: str = "") -> bool:
    """Can this sentence-initial word be lowercased without mangling a name or acronym?

    Three sources of evidence, cheapest first — no model, so the free path stays dependency-free:
      * an internal or full capital ("NASA", "iPhone") is never sentence-position capitalisation;
      * a curated list of words that routinely open an expository sentence;
      * the word appearing in lower case elsewhere in the same text, which is strong evidence it is
        an ordinary word that merely happens to sit at a sentence start here.
    """
    bare = word.strip(",;:.!?\"'()").lower()
    if not bare:
        return False
    if word.isupper() and len(word) > 1:
        return False
    if _INTERNAL_CAPS_RE.match(word.strip(",;:.!?\"'()")):
        return False
    if bare in _SAFE_TO_LOWERCASE:
        return True
    return bool(context) and re.search(rf"(?<![.!?]\s)\b{re.escape(bare)}\b", context) is not None


def _proper_noun_evidence(word: str, context: str) -> bool:
    """Does this word look like a NAME rather than an ordinary word that starts a sentence?

    The mirror of ``_safe_to_lowercase``, and needed because "not provably safe to lowercase" is
    not the same as "must stay capital". Evidence: the word appears capitalised somewhere that is
    NOT a sentence start — "the Smith study" — or it is an acronym or has internal capitals.

    Used where the alternative is emitting text: a wrong answer here costs one skipped rhythm
    variation, where the old unconditional fallback cost a visibly broken sentence.
    """
    bare = word.strip(",;:.!?\"'()")
    if not bare:
        return False
    if bare.isupper() and len(bare) > 1:
        return True
    if _INTERNAL_CAPS_RE.match(bare):
        return True
    # Capitalised and NOT preceded by sentence-ending punctuation or the start of the string.
    return re.search(rf"(?<![.!?]\s)(?<!^)\b{re.escape(bare)}\b", context) is not None


# Discourse markers that may survive at the start of the second clause. Joining with ", and " when
# the clause already opens with one produced "and plus,", "while and," and "and and," — visible
# garbage in the primary free rewriter's output.
_LEADING_MARKER_RE = re.compile(
    r"^(?:and|but|or|so|yet|plus|also|then|however|moreover|furthermore|additionally|"
    r"overall|therefore|thus|hence|indeed|besides|meanwhile|still)\b,?\s+",
    re.IGNORECASE,
)

# Clause connectors for the sentence merge, weighted to the frequencies HUMANS actually use.
#
# No "; " in this list. The merge runs after the semicolon strip, so a semicolon inserted as a
# connector survives into the output, and semicolon_crutch is a tell this repo catalogues at 2+ per
# passage. MEASURED once repetition-aware merging made merges more frequent: 40 AI texts through
# the loop went from 0 semicolons in to 4 out — the rewriter manufacturing a tell it also counts.
#
# The weights are the second half of the same problem. Choosing uniformly emits each connector 20%
# of the time, and natural English is nothing like uniform. MEASURED over 400 paired texts from HC3
# and RAID (596 human occurrences of a comma-joined clause connective, the construction this merge
# produces):
#
#     connector    human     ai    uniform (what we emitted)
#     and          65.9%   79.5%     20.0%
#     but          21.6%    6.7%     20.0%
#     so            7.9%    3.1%     20.0%
#     while         3.9%   10.6%     20.0%
#     though        0.7%    0.0%     20.0%
#
# "though" was emitted 29x more often than a human writes it and "while" 5x. An unnatural
# connective distribution is exactly what a perplexity detector reads, so the transform meant to
# humanise rhythm was leaving its own signature. Weighted to the human column instead.
#
# Note the AI column: humans use "but" 3.2x as often as AI does. Under-using contrast is itself an
# AI trait, so the weights lean the right way on that axis too rather than merely away from ours.
_MERGE_CONNECTORS = (", and ", ", but ", ", so ", ", while ", ", though ")
_MERGE_WEIGHTS = (0.659, 0.216, 0.079, 0.039, 0.007)

# Formulaic transitions that OPEN a sentence (§3, §8 from ai-tells.md).
_TRANSITIONS_RE = re.compile(
    r"^(Moreover|Furthermore|Additionally|Overall|In conclusion|In summary|"
    r"Notably|Importantly|Consequently|Therefore|Thus|Hence|"
    r"Ultimately|Nevertheless|Nonetheless|Accordingly|Subsequently|"
    r"Arguably|Indeed|Essentially|In essence),?\s+",
    re.IGNORECASE,
)

# Participial-phrase trailers: sentence ending with ", [verb]ing ...".
# Map of participial verb → simple present tense for the flatten transform.
_PARTICIPIAL_VERBS: dict[str, str] = {
    # "underscoring" -> "shows", not "underscores": the -s form is itself catalogued ai_vocab, so
    # flattening the participial trailer traded a `participial_trailer` hit for an `ai_vocab` hit.
    # _plain_register would often clean it up afterwards, but only with probability
    # `intensity * profile["register"]` — emitting a known tell and relying on a later stochastic
    # pass to remove it is not the same as not emitting it. Same class of bug as the four
    # self-referential synonyms in attacks/word_importance.py.
    "underscoring": "shows", "underlining": "underlines",
    "marking": "marks", "reflecting": "reflects",
    "highlighting": "highlights", "showcasing": "showcases",
    "emphasizing": "emphasizes", "signaling": "signals",
    "cementing": "cements", "solidifying": "solidifies",
    "paving": "paves", "ensuring": "ensures",
    "demonstrating": "demonstrates", "reinforcing": "reinforces",
    "suggesting": "suggests", "indicating": "indicates",
    "revealing": "reveals", "confirming": "confirms",
}
_PARTICIPIAL_RE = re.compile(
    r",\s+(" + r"|".join(re.escape(v) for v in _PARTICIPIAL_VERBS) + r")\b[^.!?]*[.!?]",
    re.IGNORECASE,
)

# Negated contrast: "It's not X, it's Y" / "Not only X but also Y".
# These are complex patterns; the flatten function below handles each case.
_NEGATED_CONTRAST_RE = re.compile(
    r"\bit'?s not\s+.+?,?\s+it'?s\s+\w+[^.]*\.?"
    r"|not only\b[^.]{0,60}\bbut also\b"
    r"|isn'?t about\b[^.;]{0,50};?\s+it'?s about\b"
    r"|not\s+just\b[^.]{0,40}\bbut\b",
    re.IGNORECASE | re.DOTALL,
)

# Inflated copula: verbs an AI reaches for where plain "is" would do. "marks" is dropped — it is
# usually a genuine transitive verb ("marks the score"/"marks the spot"), not a copula, so flattening
# it to "is" corrupts meaning. "boasts" flattens to "has", not "is" ("the city boasts a museum" ->
# "the city has a museum", never "is a museum") and is handled separately below.
_INFLATED_COPULA_RE = re.compile(
    r"\b(serves as|represents|epitomizes|exemplifies)\b",
    re.IGNORECASE,
)
_BOASTS_RE = re.compile(r"\bboasts\b", re.IGNORECASE)

# Vague attribution: "studies show", "research suggests".
_VAGUE_ATTR_RE = re.compile(
    r"\b(studies show|research suggests?|experts? (?:believe|say|agree)|scientists? believe|"
    r"it is (?:widely )?believed|many believe|some argue)\b",
    re.IGNORECASE,
)

# Semicolons used as rhythm crutch.
_SEMICOLON_RE = re.compile(r";\s+")

# Low-content AI scaffolding openers — pure filler that precedes the real sentence. Strip the phrase
# and keep the clause. "It is worth noting that X" -> "X"; "It should be noted that X" -> "X".
_FILLER_OPENER_RE = re.compile(
    r"(?P<lead>^|(?<=[.!?]\s))\s*"
    r"(?:it (?:is|'s) (?:worth (?:noting|mentioning)|important to (?:note|mention|highlight|remember)) that"
    r"|it should be noted that"
    r"|one (?:thing|point) (?:to note|worth noting) is that"
    r"|(?:it is|there is) no (?:doubt|denying) that"
    r"|needless to say,?"
    r"|as (?:we|previously) (?:noted|mentioned|discussed),?)\s+(?P<rest>\S.*?)?(?=$|[.!?])",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Word-level patterns (additional to SurgicalRewriter's synonym map)
# ---------------------------------------------------------------------------

# High-frequency AI hedging — strip the second word, keep the modal.
_HEDGE_RE = re.compile(
    r"\b(could|may|might|would|can)\s+(potentially|eventually|possibly|likely|arguably)\b",
    re.IGNORECASE,
)

# Contraction injection. AI text contracts far less than human writing (a strong, cheap function-word
# / formality signal). Each (pattern -> contraction) is applied case-preserving for a sentence-initial
# capital. Ordered longest-first so "it is not" contracts the negation before "it is". Verb+not forms
# are safe; ambiguous ones ("she's" = she is / she has) are left out to avoid changing meaning.
_CONTRACTIONS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(can)not\b", re.I), r"\1't"),      # cannot -> can't (special: one word)
    (re.compile(r"\bdo not\b", re.I), "don't"),
    (re.compile(r"\bdoes not\b", re.I), "doesn't"),
    (re.compile(r"\bdid not\b", re.I), "didn't"),
    (re.compile(r"\bis not\b", re.I), "isn't"),
    (re.compile(r"\bare not\b", re.I), "aren't"),
    (re.compile(r"\bwas not\b", re.I), "wasn't"),
    (re.compile(r"\bwere not\b", re.I), "weren't"),
    (re.compile(r"\bwill not\b", re.I), "won't"),
    (re.compile(r"\bwould not\b", re.I), "wouldn't"),
    (re.compile(r"\bshould not\b", re.I), "shouldn't"),
    (re.compile(r"\bcould not\b", re.I), "couldn't"),
    (re.compile(r"\bcan not\b", re.I), "can't"),
    (re.compile(r"\bhave not\b", re.I), "haven't"),
    (re.compile(r"\bhas not\b", re.I), "hasn't"),
    (re.compile(r"\bhad not\b", re.I), "hadn't"),
    (re.compile(r"\bit is\b", re.I), "it's"),
    (re.compile(r"\bthat is\b", re.I), "that's"),
    (re.compile(r"\bthere is\b", re.I), "there's"),
    (re.compile(r"\bhere is\b", re.I), "here's"),
    (re.compile(r"\bwhat is\b", re.I), "what's"),
    (re.compile(r"\bwho is\b", re.I), "who's"),
    (re.compile(r"\bthey are\b", re.I), "they're"),
    (re.compile(r"\bwe are\b", re.I), "we're"),
    (re.compile(r"\byou are\b", re.I), "you're"),
    (re.compile(r"\bthey will\b", re.I), "they'll"),
    (re.compile(r"\bwe will\b", re.I), "we'll"),
    (re.compile(r"\byou will\b", re.I), "you'll"),
    (re.compile(r"\bit will\b", re.I), "it'll"),
    (re.compile(r"\blet us\b", re.I), "let's"),
    (re.compile(r"\bI am\b"), "I'm"),
    (re.compile(r"\bI will\b"), "I'll"),
    (re.compile(r"\bI have\b"), "I've"),
]

# ---------------------------------------------------------------------------
# Structural transforms
# ---------------------------------------------------------------------------


def _split_sentences(text: str) -> list[str]:
    """Split on sentence-final punctuation, keeping abbreviations intact (see untell.text_split)."""
    return split_sentences(text)


# Transitions that point the HUMAN way in academic prose, so stripping them there makes the text
# read LESS human, not more. MEASURED per corpus over 200 pairs each, sentence-opening frequency:
#
#                     HC3 (forum Q&A)          RAID (paper abstracts)
#                     human      ai            human      ai
#     moreover        (<5 occurrences)         0.888%   0.041%   <- human, 22x
#     furthermore     (<5 occurrences)         0.947%   0.332%   <- human, 2.9x
#     therefore       (<5 occurrences)         0.592%   0.000%   <- human, all human
#     additionally    0.000%   1.544%          0.178%   0.913%      AI in both
#     overall         0.000%   2.613%          0.000%   2.407%      AI in both
#     in conclusion   (<5)                     0.000%   0.539%      AI
#     in summary      (<5)                     0.000%   0.539%      AI
#
# Real abstracts use "Moreover" and "Furthermore"; the generators largely do not. The counts behind
# the RAID column are modest (15, 16 and 10 human occurrences against 1, 8 and 0) — but all three
# agree in direction, and the AI-pointing markers are unambiguous in BOTH corpora, so the split is
# between the two groups rather than a per-marker judgement call.
#
# This is corpus scope, not a universal fact: the same marker points opposite ways in conversational
# and academic text, which is why the exemption is tied to the style profile rather than applied
# globally. Stripping stays the default for everything else.
_ACADEMIC_HUMAN_TRANSITIONS = frozenset({"moreover", "furthermore", "therefore"})


def _at_sentence_start(text: str, pos: int) -> bool:
    """Is ``pos`` the first word of a sentence? Start of text, or after a terminator."""
    before = text[:pos].rstrip()
    return not before or before[-1] in ".!?"


def _strip_transitions(
    sentences: list[str], rate: float = 1.0, keep: frozenset[str] = frozenset()
) -> list[str]:
    """Strip formulaic openers from a fraction of sentences (``rate`` in [0, 1]).

    ``keep`` names markers to leave alone, lowercased. Used by the formal style profiles, where the
    measured direction of some of these is the opposite of the conversational case.
    """
    out: list[str] = []
    for _i, s in enumerate(sentences):
        if random.random() < rate:
            m = _TRANSITIONS_RE.match(s)
            if not (m and m.group(1).lower() in keep):
                s = _TRANSITIONS_RE.sub("", s)
                if s and s[0].islower():
                    s = s[0].upper() + s[1:]
        out.append(s)
    return out


# Function words carry no content, so they are excluded when asking whether one sentence restates
# another — otherwise every pair of English sentences looks similar.
_CONTENT_STOP = frozenset(
    "the a an of to in and is are for that this it as on with be by was were which can has have "
    "we our from at or not but their its these those such also more most than then when where "
    "how why what who will would could should may might must do does did been being into over "
    "under about between across during while if so because".split()
)
_RESTATEMENT_COVERAGE = 0.70
# preserve.py OWNS this pattern. A second copy here drifts the moment the sentinel format changes,
# and tests/test_preserve.py::test_sentinel_pattern_is_defined_once exists to catch exactly that —
# it caught this. rewriter/targeted.py imports it the same way, so there is no cycle.
from untell.scripts.preserve import SENTINEL_RE as _SENTINEL_PATTERN  # noqa: E402


def _content_words(sentence: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z0-9']+", sentence)} - _CONTENT_STOP


def _drop_restatements(sentences: list[str], coverage: float = _RESTATEMENT_COVERAGE) -> list[str]:
    """Remove sentences whose content is already carried by an earlier one.

    This is the only transform found that attacks repeated phrasing at its source rather than at
    its symptoms. MEASURED across 80 RAID pairs, the share of sentences whose content words are
    at least 60% covered by an earlier sentence:

        human 0.1%    ai 7.7%    AUROC 0.740

    Seventy-seven times more restatement, and AI writes 11.8 sentences to the human 8.3 for the
    same source document. That surplus is where the duplicated phrasing lives, which is why the
    earlier transforms — merging, synonym substitution — could only reach its edges: they rewrote
    the repetition instead of removing the sentence that carried it.

    Deliberately conservative, because deleting a sentence is the most destructive edit here:

    * coverage bar of 0.70, chosen from the firing curve rather than guessed. MEASURED over 80
      RAID pairs, the share of texts where a sentence is dropped:

          coverage   AI texts   HUMAN texts (a false drop)
            0.60       45%          1%
            0.70       26%          0%      <- shipped
            0.75       25%          0%
            0.80       19%          0%

      0.70 fires on 37% more AI text than the 0.80 first tried, with no human sentence dropped
      anywhere in the sample;
    * never the first or last sentence — the opener frames and the closer concludes, and both
      restate on purpose;
    * never a sentence carrying a NUMERAL the earlier sentence lacks, since a restatement that
      adds a figure is not a restatement;
    * never a sentence carrying a preserve-lock sentinel, which by definition holds a citation,
      quote or quantity that exists nowhere else;
    * a cap of one removal per five sentences, so an unlucky pass cannot strip a paragraph. One
      flat removal per call was leaving work behind: MEASURED over 80 RAID pairs, 40 sentences
      are droppable in total but a single pass reached only 21, because 11 texts carry two to
      four restatements each. Applying it to exhaustion drops nothing at all from the human
      halves — 0 of 80 at any depth — so the cap is about bounding damage from a bad call, not
      about false positives.

    The loop's meaning gates (bidirectional NLI, numeral retention, semantic roles) sit downstream
    and veto anything this gets wrong, so the failure mode is a rejected candidate rather than a
    damaged output.
    """
    if len(sentences) < 4:  # nothing safe to drop once the first and last are excluded
        return sentences
    budget = max(1, len(sentences) // 5)
    kept = list(sentences)
    for _ in range(budget):
        shorter = _drop_one_restatement(kept, coverage)
        if len(shorter) == len(kept):
            break
        kept = shorter
    return kept


def _drop_one_restatement(sentences: list[str], coverage: float) -> list[str]:
    """Remove the first restatement found, or return the input unchanged."""
    if len(sentences) < 4:
        return sentences
    seen: list[set[str]] = [_content_words(sentences[0])]
    for i in range(1, len(sentences) - 1):
        s = sentences[i]
        words = _content_words(s)
        if not words or _SENTINEL_PATTERN.search(s):
            seen.append(words)
            continue
        best = max((len(words & prev) / len(words) for prev in seen if prev), default=0.0)
        if best >= coverage:
            new_numerals = set(re.findall(r"\d+(?:\.\d+)?", s)) - {
                n for p in sentences[:i] for n in re.findall(r"\d+(?:\.\d+)?", p)
            }
            if not new_numerals:
                return sentences[:i] + sentences[i + 1 :]
        seen.append(words)
    return sentences


_OPENING_WORDS = 3


def _shares_opening(a: str, b: str) -> bool:
    """True when two sentences begin with the same first three words, case-insensitively.

    Three words rather than one: a shared "The" is ordinary English, while a shared "The system
    is" is the repeated-phrasing pattern that reads as machine-written.
    """
    wa = re.findall(r"[A-Za-z0-9']+", a.lower())[:_OPENING_WORDS]
    wb = re.findall(r"[A-Za-z0-9']+", b.lower())[:_OPENING_WORDS]
    return len(wa) == _OPENING_WORDS and wa == wb


def _merge_sentences(sentences: list[str], rate: float = 0.33) -> list[str]:
    """Merge adjacent sentence pairs into compound sentences (raises burstiness)."""
    if len(sentences) < 2:
        return sentences
    out: list[str] = []
    i = 0
    while i < len(sentences):
        # Merging is chosen at random EXCEPT when the two sentences open the same way, where it is
        # taken every time. Repeated phrasing is the strongest tell in the catalogue — AUROC 0.965
        # on RAID, 0.921 on HC3, against ~0.57 for the ai_vocab cluster — and MEASURED, no rewriter
        # moved it at all: 24.83 -> 24.58 through the full loop on 12 RAID texts, while repeated
        # sentence openers fell 3.92 -> 0.67 over the same run.
        #
        # The reason surgical substitution cannot help is that the repeated words are ordinary
        # ("the system is designed to"), so they are absent from an AI-vocabulary synonym map.
        # Merging is the transform that does work on them: collapsing "The system does X. The
        # system does Y." into one sentence removes the duplicated span outright, and it is the
        # same operation already trusted here for burstiness, so it inherits the existing
        # mergeability and meaning checks rather than adding a new risk.
        pair_repeats_opening = (
            i + 1 < len(sentences) and _shares_opening(sentences[i], sentences[i + 1])
        )
        take = 1.0 if pair_repeats_opening else rate
        if i + 1 < len(sentences) and random.random() < take and _mergeable(
            sentences[i], sentences[i + 1]
        ):
            # rstrip(".!?"), not rstrip("."). Stripping only the period left the other terminators
            # in place and the connector was appended straight after them:
            #     "The results were remarkable!" + "The team published them."
            #       -> "The results were remarkable!; the team published them."
            # _merge_pair below — the other copy of this same merge — has always used ".!?"; this
            # copy was the one that diverged.
            a = sentences[i].rstrip(".!?")
            b = sentences[i + 1].strip()
            # A clause that already opens with a discourse marker cannot take another connector:
            # ", and " + "plus, it improves..." reads "and plus, it improves". Strip the marker
            # first — the connector about to be added does the same job.
            b = _LEADING_MARKER_RE.sub("", b, count=1)
            merged_ok = bool(b) and (
                b[0].islower() or _safe_to_lowercase(b.split()[0], " ".join(sentences))
            )
            if b and merged_ok:
                b = b.rstrip(".!?")
                b = b[0].lower() + b[1:] if b and b[0].isupper() else b
                            # No "; " here. This runs AFTER the semicolon strip above, so a semicolon
                # inserted as a connector survives into the output — and semicolon_crutch is a
                # tell this repo catalogues at 2+ per passage. MEASURED once repetition-aware
                # merging made merges more frequent: 40 AI texts through the loop went from 0
                # semicolons in to 4 out, i.e. the rewriter was manufacturing a tell it also
                # counts. The remaining connectors carry the same clause relation without it.
                conn = random.choices(_MERGE_CONNECTORS, weights=_MERGE_WEIGHTS, k=1)[0]
                out.append(f"{a}{conn}{b}.")
                i += 2
                continue
            # Not safe to demote to a subordinate clause (a name, an acronym, an unknown noun):
            # leave both sentences alone rather than lowercasing something that must stay capital.
            out.append(sentences[i])
            i += 1
        else:
            out.append(sentences[i])
            i += 1
    return out


# A terminator, allowing for closing quotes/brackets after it: `he said "stop."` is terminated.
_TERMINATED_RE = re.compile(r"[.!?][\"'”’)\]]*$")


def _terminated(s: str) -> str:
    """``s`` with a full stop appended only if it does not already end in one.

    Appending unconditionally is how "…different retailers.." reached the output: the second half
    of a split sentence is the tail of a sentence that already ended in a full stop, and it got
    another. Nothing downstream objects — detectors score statistics, the meaning gate checks
    meaning, and the tells catalogue matches phrases — so a doubled stop ships in text whose entire
    purpose is to read as human writing.
    """
    s = s.rstrip()
    return s if not s or _TERMINATED_RE.search(s) else s + "."


# Words that cannot end a sentence and cannot be severed from the clause they introduce. Used on
# BOTH sides of a split point: the second half starting with one means the split broke a clause,
# and the first half ending with one means the same break, detected one word too late.
# Deliberately NOT "that", "which", "who", "if", "for" or "so". Those open clauses too, but they
# also sit mid-phrase constantly, and treating them as split-blockers made things worse rather than
# better: shifting the split point off "that" in "On top of that, the clause ..." produced
# "On top of, that." — a comma inserted where the phrase had none. Widened once, measured, reverted.
_SPLIT_CONJUNCTIONS = frozenset(
    {"and", "or", "but", "nor", "yet", "while", "because", "since", "although", "though",
     "whereas", "unless", "until"}
)


def _split_long_sentences(sentences: list[str], max_words: int = 28, rate: float = 0.25) -> list[str]:
    """Split sentences longer than ``max_words`` words at a suitable break point."""
    out: list[str] = []
    for s in sentences:
        words = s.split()
        if len(words) > max_words and random.random() < rate:
            # Find a good split: after a comma, semicolon, or at a natural midpoint.
            mid = len(words) // 2
            # Look for a comma around the midpoint.
            split_at = mid
            for offset in range(mid):
                for pos in (mid + offset, mid - offset):
                    if 0 < pos < len(words) and words[pos].endswith(","):
                        split_at = pos + 1
                        break
                if split_at != mid:
                    break
            # A midpoint split can land immediately AFTER a conjunction, stranding it at the end of
            # the first half. MEASURED on real HC3 text (composite rewriter):
            #   "... they had no representation in the British government and. Were being dictated
            #    to by officials ..."
            # The guard below only looked at what the SECOND half starts with, so this shape — the
            # same broken clause, one word to the left — walked straight past it. Hand the
            # conjunction to the second half, where that guard then joins the two with a comma
            # instead of ending a sentence on "and".
            while split_at > 1 and words[split_at - 1].rstrip(",").lower() in _SPLIT_CONJUNCTIONS:
                split_at -= 1
            first = " ".join(words[:split_at]).rstrip(",")
            second = " ".join(words[split_at:])
            if not first.strip():
                out.append(s)
                continue
            if second:
                second = second[0].lower() + second[1:] if second[0].isupper() else second
                # Check if we broke mid-clause (second starts with a conjunction)
                if second.split()[0].rstrip(",").lower() in _SPLIT_CONJUNCTIONS:
                    out.append(_terminated(f"{first}, {second}"))
                else:
                    out.append(f"{_terminated(first)} {_terminated(second[0].upper() + second[1:])}")
            else:
                out.append(s)
        else:
            out.append(s)
    return out


# Subjects for the flattened clause, cycled rather than fixed. A single fixed "This" turned every
# participial trailer in a document into an identically-opening sentence: five trailers became
# "This shows ... This reflects ... This confirms ... This indicates ... This suggests ...".
# `score_tells` did not flag it — `_duplicate_sentence_starts` needs 40% of sentences and enough
# words to qualify — but the catalogue is not the detector, and repeating one opener five times is
# the exact shape `repeated_sentence_openers` exists to name. Fixing one tell must not manufacture
# another; same failure as the replacements swept by TestTheRewriterNeverEmitsACataloguedTell.
_PARTICIPIAL_SUBJECTS = ("This", "That", "It")


def _flatten_participial_trailers(text: str) -> str:
    """Convert ', underscoring its importance' → '. This underscores its importance'."""
    used: list[str] = []

    def _replace(m: re.Match) -> str:
        verb_ing = m.group(1).lower()  # e.g. "underscoring"
        present = _PARTICIPIAL_VERBS.get(verb_ing, verb_ing.rstrip("ing") + "s")
        # Everything after the participial verb, sliced by the match's own group offsets so any amount
        # of whitespace (", underscoring", ",  underscoring", ",\nunderscoring") is handled correctly.
        after = m.group(0)[m.end(1) - m.start(0):]  # " its importance." — keeps the leading space
        after = after.rstrip(".!?")                 # drop the trailing terminator, keep leading space
        # Avoid the subject used last time, so consecutive flattenings never share an opener. Chosen
        # at random among the rest rather than round-robin: a fixed rotation is its own pattern, and
        # best-of-N draws would otherwise all agree.
        options = [s for s in _PARTICIPIAL_SUBJECTS if not used or s != used[-1]]
        subject = random.choice(options)
        used.append(subject)
        return f". {subject} {present}{after}."

    return _PARTICIPIAL_RE.sub(_replace, text)


def _flatten_negated_contrast(text: str) -> str:
    """Convert 'It's not X, it's Y' → 'It's Y' preserving the positive statement."""
    def _replace(m: re.Match) -> str:
        full = m.group(0)
        # Pattern: "It's not X, it's Y" — extract the Y part after the second "it's"
        if "it's not" in full.lower() and "it's" in full.lower():
            # Find the last "it's" and take everything after it
            idx = full.lower().rindex("it's")
            after = full[idx + len("it's"):].strip().strip(".,;!?")
            return f"It's {after}."

        if "not only" in full.lower() and "but also" in full.lower():
            # "not only X but also Y" is NOT a negated contrast — X and Y are BOTH asserted, so
            # there is no false half to discard. The match spans only "not only X but also" (Y and
            # the head sit outside it), and the old code returned everything after "but also",
            # which inside that span is the empty string. So X was deleted and a doubled space left
            # behind:
            #     "It's not only faster, but also cheaper to run."  ->  "It's  cheaper to run."
            # "faster" is simply gone — content loss, from a transform whose contract is to keep
            # the positive statement. Replacing the span with "X and" yields the meaning-preserving
            # flattening: "It's faster and cheaper to run."
            lower = full.lower()
            start = lower.index("not only") + len("not only")
            x = full[start:lower.rindex("but also")].strip().rstrip(",").strip()
            return f"{x} and" if x else full

        if "isn't about" in full.lower():
            parts = full.split(";", 1)
            if len(parts) >= 2:
                return parts[-1].strip()

        if "not just" in full.lower():
            parts = full.split("but", 1)
            if len(parts) == 2:
                return parts[1].strip()

        return full

    return _NEGATED_CONTRAST_RE.sub(_replace, text)


def _inject_contractions(text: str, rate: float = 1.0) -> str:
    """Contract formal verb phrases ("do not" -> "don't", "it is" -> "it's"). Case-preserving.

    AI text contracts far less than human writing; injecting contractions shifts the function-word /
    formality distribution toward human. ``rate`` in [0, 1] applies to each candidate match.
    """
    for pat, repl in _CONTRACTIONS:
        def _sub(m: re.Match, _repl: str = repl) -> str:
            if rate < 1.0 and random.random() > rate:
                return m.group(0)
            out = m.expand(_repl)
            if m.group(0)[:1].isupper():
                out = out[0].upper() + out[1:]
            return out

        text = pat.sub(_sub, text)
    return text


def _strip_filler_openers(text: str) -> str:
    """Remove low-content AI scaffolding openers ("It is worth noting that ...") and keep the clause,
    re-capitalizing the sentence start that the strip exposes."""
    # Capitalise ONLY the clause each strip exposes — never the whole text. The previous
    # implementation ran `re.sub(r"(^|[.!?]\s+)([a-z])", ...)` over the entire string after the
    # strip, which capitalises any lowercase word following ANY sentence-ending punctuation. That
    # includes the period inside an abbreviation, so text this function never touched came back
    # corrupted:
    #     "The study used e.g. three methods."  -> "... e.g. Three methods."
    #     "We met at 3 p.m. tomorrow"           -> "... 3 p.m. Tomorrow"
    # The abbreviation guard in _split_sentences does not help here, because this runs on raw text
    # before any sentence splitting. Folding the capitalisation into the substitution itself means
    # nothing outside a matched filler can be altered.
    def _strip_and_capitalise(m: re.Match) -> str:
        lead = m.group("lead") or ""
        rest = m.group("rest") or ""
        return lead + (rest[:1].upper() + rest[1:] if rest else "")

    return _FILLER_OPENER_RE.sub(_strip_and_capitalise, text)


# Sentinel spans (⟦HZxxxx⟧) must never be touched by a word-level substitution.
# Imported, not re-declared — see the note on SENTINEL_RE in preserve.py.
from untell.scripts.preserve import SENTINEL_RE as _SENTINEL_SPAN_RE  # noqa: E402


def _plain_register(text: str, intensity: float = 1.0) -> str:
    """Swap formal / AI-inflected vocabulary for the words people actually use.

    A 180-entry formal->plain map already existed, but only the *surgical* rewriter used it, ranked
    by detector-importance and capped by ``max_subs`` — so most swaps never fired, and the ones that
    did were chosen to move a score rather than to change register.

    Register change is the single most natural humanizing move ("utilize" -> "use", "demonstrates"
    -> "shows"), and until now the loop could not use it at all: the meaning gate scored cosine
    similarity, which PENALISES register change, and rejected 6/6 faithful formal->casual rewrites.
    With the NLI gate carrying fidelity instead, those rewrites are finally adoptable — so it is
    worth making them wholesale rather than incidentally.

    ``intensity`` scales how many eligible words are swapped, which also gives best-of-N draws real
    diversity instead of near-identical variants.
    """
    if not text.strip():
        return text
    from untell.attacks.word_importance import (
        _ARTICLE,
        _QUANT_FRAME_KEYS,
        _SYN,
        agree_article,
        substitute_once,
    )
    from untell.attacks.word_importance import DUP_PARTICLE_TAIL as _DUP_PARTICLE_TAIL

    # Protect locked spans: mask them out, substitute, then restore.
    spans: list[str] = []

    def _stash(m: re.Match) -> str:
        spans.append(m.group(0))
        return f"\x00{len(spans) - 1}\x00"

    masked = _SENTINEL_SPAN_RE.sub(_stash, text)

    # Quantifier frames first, as a unit. "a myriad of X" carries its article and its "of" as part
    # of the construction, so the token pass below cannot make it grammatical — it produced "a many
    # of X" and "a lots of X". Handled here, the frame is gone before the token pass sees the key.
    for _key in _QUANT_FRAME_KEYS:
        while re.search(rf"\b(?:a|an)\s+{_key}\s+of\b", masked, flags=re.IGNORECASE):
            if random.random() > intensity:
                break
            # substitute_once owns the grammar rule (which forms fit the frame, and which of those
            # survive a mass-noun head), so try the options until one of them applies. It returns
            # the text unchanged when a replacement has no grammatical form here.
            options = list(_SYN.get(_key, []))
            random.shuffle(options)
            for option in options:
                replaced = substitute_once(masked, _key, option)
                if replaced != masked:
                    masked = replaced
                    break
            else:
                break

    # Replacements already spent in this text. The map is many-to-one in places — six different
    # source words offer "key" ('pivotal', 'crucial', 'vital', 'paramount', 'essential', 'salient'),
    # six offer "boost", five offer "so" — and AI prose reaches for several of a cluster in the same
    # passage. Choosing independently each time, three of those words land on "key" about 4% of the
    # time and at least two of them about 26%, manufacturing `repeated_phrasing` out of text that
    # had none. MEASURED after the register pass stopped being intensity-gated: ai_vocab fell 21->0
    # but repeated_phrasing rose 960->985 and repeated openers 44->52 on the same 60 texts.
    spent: set[str] = set()

    def _swap(m: re.Match) -> str:
        article, word, tail = m.group(1) or "", m.group(2), m.group(3) or ""
        options = _SYN.get(word.lower())
        if not options or random.random() > intensity:
            return m.group(0)  # group(0), not `word` — the article and tail are not ours to drop
        # A formulaic transition at a sentence start belongs to _strip_transitions, which DELETES
        # it. This pass runs first, and substituting pre-empts that: "Therefore, we adopt it."
        # became "That is why, we adopt it." — no longer matched by _TRANSITIONS_RE, so it survived
        # the stripper and then collided with a merge connector to produce "results are strong, so
        # that is why, we adopt it." Deletion is the right treatment for these and a wordier
        # connective is a worse outcome than the word we started with; mid-sentence occurrences are
        # unaffected, where substitution IS the right move.
        # Probe with ", " appended: _TRANSITIONS_RE requires whitespace after the optional comma,
        # so matching the bare word alone silently never fires.
        if _at_sentence_start(masked, m.start()) and _TRANSITIONS_RE.match(word + ", x"):
            return m.group(0)
        # Prefer an option this text has not used yet; fall back to the full list when every option
        # is spent, because leaving the AI word in place is worse than repeating a plain one.
        fresh = [o for o in options if o not in spent]
        choice = random.choice(fresh or options)
        spent.add(choice)
        # Preserve the original capitalisation so sentence starts survive the swap.
        if word[:1].isupper():
            choice = choice[:1].upper() + choice[1:]
        # The article agreed with the word being replaced, not with the replacement: "an intricate
        # design" became "an complex design".
        head = agree_article(article, choice) if article else ""
        # Consume a following particle the replacement already ends with, rather than repeating it:
        # "navigate through X" -> "work through X", not "work through through X". 30 of the table's
        # multi-word values end in such a particle, so this belongs at the seam, not in the table —
        # the table cannot know what follows the word.
        if tail and choice.rsplit(" ", 1)[-1].lower() == tail.strip().lower():
            return head + choice
        return head + choice + tail

    # Same token shape as word_importance._WORD: hyphenated compounds are one token, so the
    # table's "cutting-edge" / "state-of-the-art" entries are reachable here too. The optional
    # groups around it are the preceding article and the following particle, matched here so _swap
    # can re-agree the one and drop the other when the replacement already supplies it.
    masked = re.sub(
        _ARTICLE + r"([A-Za-z]+(?:-[A-Za-z]+)*)" + _DUP_PARTICLE_TAIL, _swap, masked
    )
    return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], masked)


# Clichés the catalogue counts and nothing removed. MEASURED through the composite loop on 40 AI
# texts, `cliche` went 6 -> 6: detected, never touched — and it is one of only two categories rated
# STRONG evidence on both corpora (precision 0.90 on HC3, 0.93 on RAID). The 58 hits across 300 AI
# texts concentrate almost entirely in a few forms:
#
#     16  it's important to note        8  it is important to note
#     14  in summary                   12  in conclusion
#      5  paves the way                 1  play a crucial role / it's worth noting / when it comes to
#
# The first group is pure scaffolding: deleting "It is important to note that" leaves the sentence
# saying exactly what it said. The rest are substitutions rather than deletions.
_CLICHE_FLATTEN: list[tuple[re.Pattern, str]] = [
    # "It is important to note that X" -> "X". The capital is restored below.
    (
        re.compile(
            r"\b[Ii]t(?:'s| is| was)\s+(?:also\s+)?(?:important|worth|essential|necessary|crucial)"
            r"\s+(?:to note|noting|to mention|mentioning|to remember|remembering)\s+that\s+",
            re.IGNORECASE,
        ),
        "",
    ),
    # Same without "that": "It is worth noting, X"
    (
        re.compile(
            r"\b[Ii]t(?:'s| is| was)\s+(?:also\s+)?(?:important|worth|essential|necessary|crucial)"
            r"\s+(?:to note|noting|to mention|mentioning)\s*,\s*",
            re.IGNORECASE,
        ),
        "",
    ),
    (re.compile(r"\bpaves?\s+the\s+way\s+for\b", re.IGNORECASE), "leads to"),
    (re.compile(r"\bpaves?\s+the\s+way\b", re.IGNORECASE), "opens the door"),
    (
        re.compile(r"\bplays?\s+an?\s+(?:crucial|pivotal|vital|key|central)\s+role\s+in\b", re.I),
        "is central to",
    ),
    (re.compile(r"\bplays?\s+an?\s+(?:crucial|pivotal|vital|key|central)\s+role\b", re.I), "matters"),
    (re.compile(r"\bwhen\s+it\s+comes\s+to\b", re.IGNORECASE), "for"),
    # "in the end", not "ultimately": "ultimately" is a catalogued formulaic_transition, so the
    # flatten swapped a `cliche` hit for a transition hit and the tell count did not move. Unlike
    # the participial case there is no later pass that would clean it — _strip_transitions runs on
    # sentence openers, and this substitution lands mid-sentence as often as not.
    (re.compile(r"\bat\s+the\s+end\s+of\s+the\s+day\b", re.IGNORECASE), "in the end"),
    (re.compile(r"\bin\s+the\s+realm\s+of\b", re.IGNORECASE), "in"),
    (re.compile(r"\bstands?\s+as\s+a\s+testament\s+to\b", re.IGNORECASE), "shows"),
]

_AFTER_SENTENCE_START = re.compile(r"(^|[.!?]\s+)([a-z])")


def _flatten_cliches(text: str) -> str:
    """Delete or plainly replace the catalogued clichés.

    Deletions leave a lower-case word where a sentence now begins, so capitalisation is restored
    afterwards — otherwise removing "It is important to note that " turns the sentence into one
    starting mid-word, which is a more obvious tell than the cliché was.
    """
    if not text.strip():
        return text
    for pattern, replacement in _CLICHE_FLATTEN:
        text = pattern.sub(replacement, text)
    return _AFTER_SENTENCE_START.sub(lambda m: m.group(1) + m.group(2).upper(), text)


def _flatten_copula(text: str) -> str:
    """Flatten inflated copulas: 'serves as'/'represents'/... → 'is', and 'boasts' → 'has'."""
    text = _BOASTS_RE.sub("has", text)
    text = _INFLATED_COPULA_RE.sub("is", text)
    return text


def _flatten_vague_attribution(text: str) -> str:
    """Replace 'studies show' with concrete alternatives."""
    text = _VAGUE_ATTR_RE.sub("evidence suggests", text)
    return text


def _vary_openers(sentences: list[str], rate: float = 0.3) -> list[str]:
    """Vary sentence openings by prepending transitional phrases or restructuring."""
    # Openers humans are MEASURED to use, not ones that merely sound casual. Sentence-opening
    # frequency over 400 HC3+RAID pairs (3347 human sentences, 4094 AI):
    #
    #     dropped — 0.000% in BOTH halves: nobody writes these, so inserting one is a fingerprint
    #         broadly            0.000%  /  0.000%
    #         looking at this    0.000%  /  0.000%      (also the top source of repeated phrasing)
    #         as it turns out    0.000%  /  0.000%
    #         realistically      0.000%  /  0.000%
    #     kept — attested, human-leaning
    #         in short           0.090%  /  0.073%
    #         in practice        0.060%  /  0.000%
    #         actually           0.030%  /  0.000%
    #         put simply         0.030%  /  0.000%
    #     added — human-leaning by a wide margin, and content-neutral
    #         also               0.568%  /  0.000%
    #         now                0.329%  /  0.073%
    #         basically          0.209%  /  0.000%
    #         well               0.179%  /  0.000%
    #         of course          0.090%  /  0.000%
    #
    # NOT added despite being human-leaning, because each asserts something about the sentence it
    # is prepended to and the meaning gates do not check discourse relations:
    #     "recently" (0.269%) claims recency, "meanwhile" (0.179%) claims simultaneity, "then"
    #     (0.717%) claims sequence, "so" (1.285%) claims consequence, "here" (0.359%) is deictic.
    # "so" is the single most common human opener in the corpus and is still declined on that
    # ground — frequency is not the only criterion.
    #
    # NOT added because they point the AI way: "for example" (0.329% human / 1.392% AI), "in fact"
    # (0.090% / 0.147%), "instead" (0.030% / 0.269%).
    #
    # Every entry is screened against score_tells and _TRANSITIONS_RE, so none is a catalogued tell
    # and none would be deleted by the stripper that runs later.
    openers = [
        "Actually,", "In practice,", "In short,", "Put simply,",
        "Also,", "Now,", "Basically,", "Well,", "Of course,",
    ]
    context = " ".join(sentences)
    # Openers already spent in this text. Picking independently from an 8-item pool at ~0.3 rate
    # means a long passage reuses one: MEASURED over 60 RAID+HC3 texts, "Looking at this," was the
    # single largest source of rewriter-CREATED repeated phrasing, 7 excess occurrences — more than
    # any other, and this transform exists to VARY openers. Same collision as the synonym map's
    # many-to-one entries (see `spent` in _plain_register). Cleared when the pool is exhausted, so
    # a text with more than 8 varied openers cycles rather than stops varying.
    spent: set[str] = set()

    def _opener() -> str:
        fresh = [o for o in openers if o not in spent]
        if not fresh:
            spent.clear()
            fresh = list(openers)
        pick = random.choice(fresh)
        spent.add(pick)
        return pick

    out: list[str] = []
    for s in sentences:
        # A sentence that ALREADY opens with a discourse marker gets no second one. Stacking them
        # produced "Put simply, also, wine is often shipped at specific temperatures" — found by
        # scanning 30 real HC3 rewrites for mechanical breakage. `_LEADING_MARKER_RE` exists for
        # exactly this and was consulted only by the clause-merge path.
        if random.random() < rate and not _LEADING_MARKER_RE.match(s):
            first_word = s.split()[0] if s.split() else ""
            # No `first_word not in subjects` test here. It skipped every sentence opening with
            # The/This/It/That/There — which are precisely the sentences that duplicate an opener
            # and the reason `repeated_sentence_openers` fires at all. MEASURED: a four-sentence
            # passage where every sentence began "The ..." came back completely unvaried at
            # rate=1.0, and after transition-stripping started leaving "Overall, The paper ..." as
            # "The paper ...", duplicate openers rose from 18 to 58 over 60 texts with this skip in
            # place. The transform declined the one job it exists to do.
            #
            # The two guards that remain are the ones with a reason: _LEADING_MARKER_RE above stops
            # marker stacking ("Put simply, also, wine is ..."), and the capitalisation checks below
            # stop names being mangled.
            if first_word and first_word[0].isupper():
                # Prepend the opener, and lowercase what follows ONLY when that word is safe to
                # lowercase. Doing it unconditionally produced "In short, dr. Smith published the
                # results" — the abbreviation destroyed by the very transform meant to vary rhythm.
                # "In short, Dr. Smith published ..." is correct English; nothing needs demoting.
                if _safe_to_lowercase(first_word, context):
                    s = f"{_opener()} {s[0].lower() + s[1:]}"
                elif _proper_noun_evidence(first_word, context):
                    s = f"{_opener()} {s}"
                # Otherwise: leave the sentence alone. The old fallback prepended anyway and kept
                # the capital, which is correct English only for a real name — "Actually, Smith
                # published ..." — and visibly broken for an ordinary word the evidence check
                # merely failed to confirm: "Actually, Issue #4821 tracks ...", "As it turns out,
                # Run untell==0.2.0 ...". MEASURED over 3112 sentence-initial capitals in 400 HC3
                # texts: 21.2% reach this branch at all, and 475 of those 661 have no proper-noun
                # evidence — "Replace", "Same", "Also", "Hence", "Eventually". Broken capitalisation
                # is itself an AI tell, so the transform that exists to remove tells was adding one.
        out.append(s)
    return out


_CONJ = ("and", "but", "which", "because", "so", "while", "although", "though", "since")


def _mergeable(a: str, b: str) -> bool:
    """Can these two sentences be coordinated into one without mangling either?

    A question cannot be demoted to a coordinate clause: its word order is interrogative, so
    "Was the effect real, and the replication says yes" is not English, and neither is the
    trailing "?." you get from appending a period after one. Exclamations coordinate fine —
    the force is carried by the punctuation, which the merge is dropping anyway.
    """
    return not a.rstrip().endswith("?") and not b.rstrip().endswith("?")


# Words that can begin an independent clause: a subject of some kind. Used to tell a conjunction
# that joins two CLAUSES ("...at midnight, and it traced...") from one that joins two VERB PHRASES
# sharing a subject ("...opened the log and traced the fault"). Splitting at the latter and dropping
# the conjunction leaves a subject-less fragment:
#     "The engineer opened the log at midnight and traced the fault to a stale cache entry."
#       -> "The engineer opened the log at midnight." / "Traced the fault to a stale cache entry."
# There is no parser in this module, so the test is deliberately conservative: an unrecognised word
# means "don't split", which costs some burstiness gain and never emits a fragment.
_CLAUSE_STARTERS = frozenset(
    """i we you he she it they there this that these those his her its their our your my
    a an the some many most few several each every both all one another no other such
    what which who whose when where why how if""".split()
)


def _starts_a_clause(word: str) -> bool:
    """Could this word begin an independent clause — i.e. is it plausibly a subject?"""
    w = word.strip("\"'“”‘’(),;:").strip()
    if not w:
        return False
    # A capitalised word mid-sentence is a proper noun, which is a subject.
    if w[0].isupper():
        return True
    return w.lower() in _CLAUSE_STARTERS


def _cv(lengths: list[int]) -> float:
    if len(lengths) < 2:
        return 0.0
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return 0.0
    var = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    return (var**0.5) / mean


def _split_one(s: str) -> list[str] | None:
    """Split one long sentence into two at a comma or coordinating conjunction near the midpoint.
    Redistributes words only — no content added. Returns [first, second] or None if no clean split."""
    words = s.split()
    if len(words) < 12:
        return None
    mid = len(words) // 2
    best: int | None = None
    for off in range(mid):  # nearest comma to the midpoint
        for pos in (mid + off, mid - off):
            if 0 < pos < len(words) - 1 and words[pos].endswith(","):
                best = pos + 1
                break
        if best is not None:
            break
    if best is None:  # else a coordinating conjunction
        for off in range(mid):
            for pos in (mid + off, mid - off):
                if (
                    0 < pos < len(words) - 1
                    and words[pos].lower() in _CONJ
                    and _starts_a_clause(words[pos + 1])
                ):
                    best = pos
                    break
            if best is not None:
                break
    if best is None:
        return None
    first = " ".join(words[:best]).rstrip(",")
    tail = words[best:]
    if tail and tail[0].lower() in _CONJ:  # drop a leading conjunction for a clean second sentence
        tail = tail[1:]
    if not first or not tail:
        return None
    second = " ".join(tail)
    second = second[0].upper() + second[1:]
    if not first.endswith((".", "!", "?")):
        first += "."
    if not second.endswith((".", "!", "?")):
        second += "."
    return [first, second]


def _merge_pair(sents: list[str], j: int) -> list[str]:
    """Merge sentences j and j+1 into one compound sentence, or leave them if that is unsafe."""
    if not _mergeable(sents[j], sents[j + 1]):
        return sents
    a = sents[j].rstrip(".!?")
    b = _LEADING_MARKER_RE.sub("", sents[j + 1].strip(), count=1)
    # Same rule as _merge_sentences: only demote a sentence to a clause when its opening word can
    # be lowercased without mangling a name or an acronym.
    if not b or not (b[0].islower() or _safe_to_lowercase(b.split()[0], " ".join(sents))):
        return sents
    b = b[0].lower() + b[1:] if b[0].isupper() else b
    return sents[:j] + [f"{a}, and {b}"] + sents[j + 2 :]


def _target_burstiness(sentences: list[str], target_cv: float = 0.45, max_moves: int = 12) -> list[str]:
    """Raise sentence-length variance toward the human range (CV ~0.45-0.55; AI sits ~0.3).

    The single most reliable human/AI stylometric differentiator (research: human academic std ~8
    words vs AI ~4-5). Greedy hill-climb: each round it tries splitting the longest sentence and
    merging the lowest-combined-length adjacent pair, and keeps whichever move raises CV the most.
    Only redistributes existing words — no content added/removed — so meaning is preserved.
    """
    sents = list(sentences)
    for _ in range(max_moves):
        lengths = [len(s.split()) for s in sents]
        cur_cv = _cv(lengths)
        if len(sents) < 2 or cur_cv >= target_cv:
            break

        candidates: list[tuple[float, list[str]]] = []

        # Candidate A: split the longest sentence.
        li = max(range(len(sents)), key=lambda i: lengths[i])
        if lengths[li] >= 14:
            parts = _split_one(sents[li])
            if parts:
                cand = sents[:li] + parts + sents[li + 1 :]
                candidates.append((_cv([len(s.split()) for s in cand]), cand))

        # Candidate B: merge the adjacent pair with the smallest combined length (<=45 words).
        if len(sents) >= 2:
            j = min(range(len(sents) - 1), key=lambda i: lengths[i] + lengths[i + 1])
            if lengths[j] + lengths[j + 1] <= 45:
                cand = _merge_pair(sents, j)
                candidates.append((_cv([len(s.split()) for s in cand]), cand))

        # Keep the move that raises CV the most; stop if none improves.
        candidates = [c for c in candidates if c[0] > cur_cv + 1e-6]
        if not candidates:
            break
        sents = max(candidates, key=lambda c: c[0])[1]
    return sents


# ---------------------------------------------------------------------------
# Main rewrite pipeline
# ---------------------------------------------------------------------------


# Style profiles. `--style` was accepted by the CLI, advertised with 14 modes, threaded into
# score_result — and read by nothing except the hosted-LLM rewriter's prompt. The free rewriters
# already had the two knobs that actually carry register (contraction injection and plain-word
# substitution); they were simply always on at a fixed setting. A profile just sets them.
#
# `contractions`: inject "it is" -> "it's" etc. The single strongest formality signal in English,
#   and wrong for academic prose, which contracts far less than speech.
# `register`: how much of the formal->plain vocabulary map to apply (0 = keep the formal word).
# `sentences`: multiplier on how often a long sentence is SPLIT.
# `openers`: multiplier on how often a transitional opener is added.
#
# Those two exist because four styles were inert. With only `contractions` and `register` to set,
# casual, conversational, blunt and minimalist all resolved to the neutral default's exact values —
# so `--style minimalist` produced byte-identical output to no style at all. MEASURED over 20 HC3
# texts before this: those four differed from no-style on 0 of 20, while academic, professional and
# technical differed on 19 of 20. A flag the CLI advertises in its own help text, that cannot
# change anything, is worse than one that is missing.
#
# The knobs are the ones the pipeline already had at fixed rates, so this sets existing dials
# rather than adding transforms: shorter sentences for minimalist and blunt, more connective
# variation for conversational, longer flowing sentences for storytelling.
_NEUTRAL = {
    "contractions": True, "register": 1.0, "sentences": 1.0, "openers": 1.0,
    # Markers _strip_transitions must leave alone. Empty for every style but "academic" —
    # see _ACADEMIC_HUMAN_TRANSITIONS for the per-corpus measurement that separates them.
    "keep_transitions": frozenset(),
}

_STYLE_PROFILES: dict[str, dict] = {
    "casual":        {"contractions": True,  "register": 1.0,  "sentences": 1.0, "openers": 1.2},
    "conversational": {"contractions": True, "register": 1.0,  "sentences": 1.1, "openers": 1.5},
    "blunt":         {"contractions": True,  "register": 1.0,  "sentences": 1.6, "openers": 0.0},
    "storytelling":  {"contractions": True,  "register": 0.8,  "sentences": 0.5, "openers": 1.0},
    "humorous":      {"contractions": True,  "register": 0.9,  "sentences": 1.0, "openers": 1.3},
    "journalistic":  {"contractions": False, "register": 0.8,  "sentences": 1.3, "openers": 0.5},
    "persuasive":    {"contractions": True,  "register": 0.7,  "sentences": 1.0, "openers": 1.0},
    "empathetic":    {"contractions": True,  "register": 0.8,  "sentences": 0.8, "openers": 1.0},
    "instructional": {"contractions": True,  "register": 0.8,  "sentences": 1.3, "openers": 0.6},
    "minimalist":    {"contractions": True,  "register": 1.0,  "sentences": 1.8, "openers": 0.0},
    # Formal registers: contractions OFF and the plain-word swap held back, because "utilize" ->
    # "use" is the right move for casual prose and the wrong one for a paper.
    # "academic" alone carries the transition exemption. The evidence is RAID paper abstracts,
    # so it is claimed for academic prose and NOT extended to professional/technical, where the
    # same direction is plausible but unmeasured.
    "academic":      {"contractions": False, "register": 0.15, "sentences": 0.7, "openers": 0.4,
                      "keep_transitions": _ACADEMIC_HUMAN_TRANSITIONS},
    "professional":  {"contractions": False, "register": 0.4,  "sentences": 1.0, "openers": 0.6},
    "technical":     {"contractions": False, "register": 0.3,  "sentences": 1.2, "openers": 0.3},
    "poetic":        {"contractions": True,  "register": 0.5,  "sentences": 0.6, "openers": 0.8},
}


def style_profile(style: str | None) -> dict:
    """Knob settings for a style name. Unknown/None -> the neutral default (previous behaviour)."""
    if not style:
        return dict(_NEUTRAL)
    return {**_NEUTRAL, **_STYLE_PROFILES.get(style.strip().lower(), {})}


def structural_rewrite(
    text: str, intensity: float = 0.5, seed: int | None = None, style: str | None = None
) -> str:
    """Run the full structural rewrite pipeline. ``intensity`` in [0, 1].

    Higher intensity = more aggressive restructuring. Pass ``seed`` for reproducible
    output; leave as ``None`` (default) for varied results on each call.

    ``style`` selects a register profile (see ``_STYLE_PROFILES``): it decides whether contractions
    are injected and how much of the formal->plain vocabulary map is applied. Unknown or None keeps
    the previous neutral behaviour, so this is additive.

    Document structure is preserved. The pipeline ends in ``" ".join(sentences)``, so run over a
    whole document it returned one wall of text: paragraph breaks gone, three bullets merged onto
    one line, a fenced code block reflowed into prose. Nothing downstream objects — the meaning gate
    compares meaning and the detectors score statistics, neither of which looks at layout — so a
    user who pasted a formatted document got an unformatted one back with every check passing.
    Prose is therefore rewritten a line-block at a time and the original separators are restored
    verbatim.
    """
    run = lambda: apply_per_block(  # noqa: E731 - one expression, used twice below
        text, lambda block: _rewrite_prose(block, intensity=intensity, style=style)
    )
    if seed is None:
        return run()
    # `random.seed(seed)` reseeds the PROCESS-GLOBAL generator, so asking this function for a
    # reproducible rewrite silently reset the caller's own random stream — measured: a caller
    # mid-sequence got 0.701325 where it expected 0.080066. A library has no business doing that.
    # Save and restore around the seeded run: seeding still works exactly as documented, and
    # unseeded calls still follow whatever the caller has seeded globally.
    state = random.getstate()
    random.seed(seed)
    try:
        return run()
    finally:
        random.setstate(state)


def _rewrite_prose(text: str, *, intensity: float, style: str | None) -> str:
    """The transform pipeline itself, for one block of prose containing no layout to protect."""
    profile = style_profile(style)

    # 0. Strip low-content scaffolding openers (pure filler)
    text = _strip_filler_openers(text)

    # 1. Flatten participial trailers (always, these are pure tell)
    text = _flatten_participial_trailers(text)

    # 2. Flatten negated contrast
    text = _flatten_negated_contrast(text)

    # 3. Flatten inflated copula
    text = _flatten_copula(text)

    # 4. Flatten vague attribution
    text = _flatten_vague_attribution(text)

    # 4b. Flatten clichés — always, these are pure tell
    text = _flatten_cliches(text)

    # 5. Hedge removal — always, these are pure tell
    text = _HEDGE_RE.sub(r"\1", text)

    # 5b. Contraction injection — the strongest formality signal in English, so it is the first
    # thing a style profile turns off: academic/technical prose contracts far less than speech.
    if profile["contractions"]:
        text = _inject_contractions(text)

    # 5c. Plain-register vocabulary — formal/AI-inflected words to the words people actually use.
    # Scaled by the PROFILE only, not by `intensity`: "utilize" -> "use" is right for casual prose
    # and wrong for a paper, so the formal registers hold most of the map back — but there is no
    # useful "gentle" version of leaving a catalogued tell in place.
    #
    # The `intensity *` factor was there for best-of-N diversity, and MEASURED it provided none.
    # 12 RAID AI texts, 4 draws each, full tier, register pass isolated:
    #
    #                        best-of-4 score   ai_vocab left   sim-to-source   draw-to-draw sim
    #     gated (x0.5)           0.8130              6            0.9941           0.9949
    #     ungated (x1.0)         0.7613              0            0.9903           0.9948
    #
    # Draw-to-draw similarity is identical to four decimal places: the gate contributed nothing to
    # diversity, because `random.choice` already picks among 2-4 synonyms per word, so two draws
    # differ even when both swap everything. What the gate did contribute was 6 surviving ai_vocab
    # hits and +0.05 of detector score, for 0.004 of similarity.
    #
    # Draw-level diversity is unaffected: CompositeRewriter sweeps `intensity` ACROSS draws
    # (rewriter/composite.py `_intensity_sweep`), which still varies every structural transform.
    text = _plain_register(text, intensity=profile["register"])

    # 6. Semicolon → period (semiconductors are a tell)
    text = _SEMICOLON_RE.sub(". ", text)

    # 7. Sentence-level transforms — scaled by intensity.
    sents = _split_sentences(text)

    # Per-SENTENCE transforms run whatever the block length. They used to sit behind the
    # `len(sents) >= 2` guard below, which is only correct for the transforms that need a PAIR
    # (merge, restatement-drop, burstiness). A one-sentence block therefore kept its formulaic
    # opener outright, and blocks are per-paragraph — MEASURED over 60 RAID+HC3 texts, 9 of the 10
    # surviving `formulaic_transition` hits were a lone "Overall, ..." paragraph that no pass ever
    # looked at, while the rewriter's own strip rate was 100%.
    sents = _strip_transitions(sents, rate=1.0, keep=profile["keep_transitions"])

    if len(sents) >= 2:
        # At intensity 1.0: merge ~60% of pairs, split ~50% of long sentences,
        # vary ~60% of openers.

        # Drop restatements BEFORE merging: a merge would fuse a restatement onto its own source
        # and preserve the duplication inside one longer sentence instead of removing it.
        sents = _drop_restatements(sents)

        merge_rate = min(0.7, intensity * 0.6)
        sents = _merge_sentences(sents, rate=merge_rate)

        split_rate = min(0.9, intensity * 0.5 * profile["sentences"])
        sents = _split_long_sentences(sents, rate=split_rate)

        open_rate = min(0.9, intensity * 0.6 * profile["openers"])
        sents = _vary_openers(sents, rate=open_rate)

        # 8. Burstiness targeting — drive sentence-length variance toward the human range. The single
        # most reliable stylometric differentiator; only redistributes existing words (meaning-safe).
        sents = _target_burstiness(sents)

    result = " ".join(sents)

    return result


class StructuralRewriter(Rewriter):
    """No-LLM, no-key sentence-level rewriter. Always ``available()``.

    Transforms AI-sounding sentence structures: formulaic transitions, uniform
    sentence length, participial trailers, negated contrast, inflated copula.

    Combine with ``SurgicalRewriter`` (word-level synonym substitution) for the
    most effective free $0 path: structural first, then surgical polish.
    """

    name = "structural"

    def __init__(self, intensity: float = 0.7):
        self.intensity = intensity

    def available(self) -> bool:
        return True

    def rewrite(
        self, text: str, score_result: dict, threshold: float = 0.30,
        intensity: float | None = None,
    ) -> str:
        """``intensity`` overrides the configured value for this call only.

        CompositeRewriter sweeps intensity across its best-of draws. It used to do that by
        assigning ``self._structural.intensity`` and restoring it afterwards, which corrupts the
        object if anything between the two raises — the restore is not in a ``finally`` — and
        corrupts it permanently under concurrent use, because a second caller reads the swept value
        as its "original" and restores that. Measured with 8 threads on one shared instance: the
        configured 0.7 came back as 0.4, so every later call used the wrong intensity with no error
        anywhere. An argument cannot leak.
        """
        # The loop puts the user's --style into score_result; read it instead of ignoring it.
        return structural_rewrite(
            text,
            intensity=self.intensity if intensity is None else intensity,
            style=(score_result or {}).get("style"),
        )
