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
from untell.scripts.tells import (
    CLOSER_REMAINDER_WORDS as _TELLS_CLOSER_REMAINDER_WORDS,
)
from untell.scripts.tells import is_pure_scaffolding
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
    # "i" was here, in among the other pronouns, and it is the one word in English that is never
    # lowercase. It produced "The system was slow, and i believe the cache was cold." Sitting
    # between "you" and "my" it reads as an oversight rather than a decision — every other pronoun
    # in this row genuinely is safe. `_safe_to_lowercase` now refuses it outright as well, so
    # re-adding it here cannot resurrect the bug.
    "he", "his", "him", "she", "her", "we", "our", "us", "you", "your", "my", "there",
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
    # The pronoun "I" is capitalised everywhere in English, so no evidence below can license
    # lowercasing it. Checked before the curated list rather than only removing it from that list,
    # because the last two guards would each let it back in: `word.isupper()` exempts single
    # characters, and "i" appears lower case inside plenty of ordinary text, which the
    # context-evidence rule at the bottom reads as proof it is an ordinary word.
    if bare == "i":
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

# The SUBORDINATORS in `_CONJ` — because, while, although, though, since — are the other half of the
# same problem and cannot go in the list above. Found by scanning 60 rewrites for grammar shapes the
# tell catalogue cannot see: "…equal rights for the LGBT community, but though, there are some
# conservatives…". `_CONJ` can emit all five, so a second clause opening with one takes a connector
# on top of the one it already has.
#
# They are NOT stripped, because stripping them is unsafe in a way the discourse markers are not.
# `_LEADING_MARKER_RE` removes only the marker and its comma, which is right for "Moreover, X" —
# the word carries nothing but the join. A subordinator governs what follows it: "Because of this,
# Y" would become "and of this, Y", turning a broken join into a broken clause.
#
# So the merge is SKIPPED instead. Two sentences that both want to be subordinate clauses are not a
# merge this rewriter can do correctly, and leaving them apart costs only a merge opportunity.
_LEADING_SUBORDINATOR_RE = re.compile(
    r"^(?:because|while|although|though|since|whereas|unless|whether)\b", re.IGNORECASE
)

# HOW WELL THIS TRANSFORM ACTUALLY WORKS, measured as duplicate sentence openers per sentence so
# the number is not a function of document length (raw counts mislead here: HC3's AI half has FEWER
# duplicate openers than its human half in absolute terms, 28 against 40, purely because the human
# documents are longer):
#
#                 human    ai    after rewrite   result
#     HC3         0.028  0.060       0.029       105% of the human rate — lands on it
#     RAID        0.040  0.339       0.127       318% — still three times human
#
# HC3 is as close to right as this can get. RAID is not, and raising `intensity` from 0.7 to 1.0
# only moves it to 263%, so the limit is not the rate.
#
# It is the mechanism. This transform PREPENDS a marker; it does not change how the sentence itself
# begins. RAID's AI half opens a third of its sentences the same way ("We propose…", "We evaluate…",
# "The proposed method…"), and prepending reaches only the sentences it fires on — marking every one
# of them would be a tell in itself. Closing the rest needs a transform that changes the subject
# position, which is what `_front_subordinate_clauses` does, not another opener.
#
# Except that it cannot either, and this is the part worth knowing before reaching for it.
# Instrumented over 50 RAID documents at rate=1.0: 211 calls, 536 sentences seen, and 7 sentences
# actually fronted — 1.3%. It needs a subordinate clause to move, and the text that has this problem
# is simple declaratives ("We propose X. We evaluate Y."), which have none. The transform is not
# throttled, it is inapplicable.
#
# So on this kind of input neither available mechanism can change how a sentence begins: prepending
# reaches a fraction and marking everything is a tell, fronting has nothing to move. What is left is
# real syntactic restructuring — voice change, nominalisation — which is a paraphrase-level
# operation. That is the same conclusion the repetition analysis reached from the other direction,
# and it is why both halves of the post-rewrite residual point at the neural path.
#
# The openers this rewriter INSERTS, hoisted so the "already has a marker" guard can be derived from
# them rather than maintained beside them. `_LEADING_MARKER_RE` above lists coordinating markers and
# none of these, so a sentence that had already been given "Basically," was not recognised as
# carrying a marker and got a second one. MEASURED over 120 rewrites: 7 stacked pairs — "So, in
# short, the reason that airplane technology…", "Basically, in short, the color of your eyes…".
#
# The guard for this was already written and already correct in intent; it just consulted a list
# that did not include the transform's own vocabulary.
_OPENERS = (
    "Actually,", "In practice,", "In short,", "Put simply,",
    "Also,", "Now,", "Basically,", "Well,", "Of course,",
)
# The three whose meaning depends on something having been said already — see `_opener` for the
# measurement. Not removed from the pool: they are fine anywhere but the top of a block.
_NEEDS_PRIOR_DISCOURSE = frozenset({"In short,", "Put simply,", "Also,"})
# Openers that carry a spoken register. Fine in casual prose, wrong in a paper or a spec — and the
# formal profiles already decline contractions and the plain-word swap for exactly that reason.
# The rest of the pool ("In practice,", "In short,", "Put simply,", "Also,", "Now,", "Of course,")
# is attested in formal writing and stays available, so a formal style is steered, not silenced.
_CONVERSATIONAL_OPENERS = frozenset({"Basically,", "Well,", "Actually,"})
_ANY_LEADING_MARKER_RE = re.compile(
    r"^(?:"
    + "|".join(re.escape(o.rstrip(",")) for o in _OPENERS)
    + r"|and|but|or|so|yet|plus|also|then|however|moreover|furthermore|additionally"
    r"|overall|therefore|thus|hence|indeed|besides|meanwhile|still"
    # Subordinators and concessives. The guard only has to cover the OPENER POOL to stop this
    # transform stacking on itself, and it did — but other transforms put markers at the front of a
    # sentence too, and this one then treated the result as unmarked. `however` was covered while
    # `though`, the word the substitution table rewrites it TO, was not. MEASURED over 6 real HC3
    # answers, 51 sentences:
    #
    #     "Well, though, despite these potential downsides, many communities continue ..."
    #     "Basically, though, many people believe that the color of your eyes ..."
    #
    # Adding these can only make the guard decline more sentences: `_ANY_LEADING_MARKER_RE` has
    # exactly one caller, the stacking check below.
    r"|though|although|while|whereas|despite|nonetheless|nevertheless|regardless"
    r"|conversely|anyway|instead|otherwise|because|since|unless)\b,?\s+",
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
#
# This is NARROWER than `tells._VAGUE_ATTR_RE`, which flags it, and the gap is deliberate — but it
# was too narrow by exactly the impersonal forms. FOUND by counting detections against fixes over
# 120 corpus texts: `vague_attribution` fired on one text and the flattener acted on none of them.
# The phrase was "it is generally accepted", which the detector covers via
# `it is (widely|often|generally) (believed|said|understood|accepted)` and this had only
# `it is (widely )?believed`. So the loop counted a tell, tried to remove it, failed, and scored the
# result as unimproved.
#
# The rest of the detector's vocabulary stays out, and the reason is measured rather than assumed.
# It also flags attributed subjects — reports, surveys, analysts, observers, critics, sources — and
# rewriting "Critics argue that X" to "Evidence suggests that X" changes WHO SAID IT. The meaning
# gates do not catch that: on five such pairs, similarity 0.905-0.947, `contradicts` False and
# `role_swap` False on every one. So a wider flattener would ship attribution changes past every
# guard this repo has. The impersonal forms below have no attributor to lose, which is the whole
# reason they are safe to add.
_VAGUE_ATTR_RE = re.compile(
    r"\b(studies show|research suggests?|experts? (?:believe|say|agree)|scientists? believe|"
    r"it is (?:widely |often |generally )?(?:believed|said|understood|accepted)|"
    r"many believe|some argue)\b",
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
    """Is ``pos`` the first word of a sentence? Start of text, after a terminator, or after a lock.

    A preserve sentinel ends a sentence for this purpose. It stands for a heading, an environment,
    a display equation — spans that terminate whatever preceded them — and the character before the
    word is then `⟧`, not a full stop. FOUND on a real `.tex` file: `\\section{Introduction}` masks
    to a sentinel, so the `Moreover,` after it did not look sentence-initial, `_plain_register`
    substituted it instead of leaving it for `_strip_transitions` to delete, and the output carried
    the fragment "What is more." where the transition should simply have been removed.

    This is not LaTeX-specific — it applies wherever a locked span precedes a sentence, which is
    every document with citations or numbers at a paragraph boundary.
    """
    before = text[:pos].rstrip()
    if not before:
        return True
    if before[-1] in ".!?":
        return True
    # Two marker forms reach this function. `_plain_register` re-stashes preserve sentinels as
    # `\x00N\x00` before substituting, so checking only for `⟦HZ…⟧` matched nothing on the path that
    # actually needed it — the first version of this fix looked right and changed nothing.
    tail = before[-12:]
    return bool(_SENTINEL_PATTERN.search(tail)) or tail.endswith("\x00")


# One or more preserve sentinels (plus surrounding whitespace) at the very start of a sentence.
# Both marker forms: `⟦HZ0003⟧` as `lock` writes it, and the `\x00N\x00` re-stash `_plain_register`
# uses internally.
_LEADING_SENTINEL_RE = re.compile(r"^(?:\s*(?:⟦HZ[0-9a-fA-F]+⟧|\x00\d+\x00))+\s*")


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
            # A sentence may OPEN with a locked span — a `\section{...}`, a display equation, a
            # leading citation — and `_TRANSITIONS_RE` is `^`-anchored, so on a real `.tex` file
            # "⟦HZ0003⟧\nMoreover, it is crucial ..." matched nothing and the transition survived
            # every pass. The prefix is set aside for the match and put back verbatim, so the lock
            # is untouched and only the marker after it is considered.
            prefix = ""
            body = s
            lead = _LEADING_SENTINEL_RE.match(s)
            if lead:
                prefix, body = lead.group(0), s[lead.end():]
            m = _TRANSITIONS_RE.match(body)
            # Capitalise ONLY when a transition was actually removed. `not (m and ...)` is True when
            # `m` is None, so this branch used to run on sentences with no transition at all: the
            # `sub` was a harmless no-op, but the capitalisation still fired. Harmless too while
            # `body` was the whole sentence (already uppercase) — and wrong the moment a sentence
            # OPENS with a locked span, because then `body` is the mid-sentence remainder.
            #
            # MEASURED on a real HC3 answer. `lock()` masks the entity, so the rewriter sees
            #
            #     "⟦HZ0001⟧ best seller list is a weekly list that ranks ..."
            #
            # the sentinel is set aside as `prefix`, `body` becomes "best seller list is ...", no
            # transition matches, and the first letter is upcased regardless. After `restore`:
            #
            #     "The New York Times Best seller list is a weekly list ..."
            #
            # Twice in one document, on 3 of 3 runs. Invisible until `composite` started adopting
            # candidates at all — its selector was discarding every draft (see composite.py).
            if m and m.group(1).lower() not in keep:
                body = _TRANSITIONS_RE.sub("", body)
                # Capitalise the clause the strip exposes, not the sentinel prefix.
                if body and body[0].islower():
                    body = body[0].upper() + body[1:]
            s = prefix + body
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


# How far the output's MEAN sentence length may drift above the input's. Merging raises burstiness,
# which is the point, but it also lengthens sentences, and nothing was watching the second effect.
#
# MEASURED over 40 HC3 pairs, words per sentence:
#
#     human 21.62    ai 23.08    ours 27.95
#
# So the rewriter was making its output 21% longer-sentenced than the AI it started from and 29%
# longer than a human writing the same answer — moving Flesch-Kincaid grade level from the AI's
# 11.84 to 13.56 against a human 10.53, i.e. AWAY from human on a measure detectors and readers
# both use. The syllable half was fine (1.562 -> 1.546, toward the human 1.499): the plain-register
# pass does its job. Length was the whole regression, and it got worse when the fragment guards
# started refusing splits while merges carried on.
_MEAN_LENGTH_BUDGET = 1.10

# A merged sentence is never "too long" in absolute terms below this, whatever the input mean.
# Merging two AVERAGE sentences always yields 2x the mean, so a relative cap alone refuses it by
# construction — correct for long prose, and wrong for short. Uniform four-word sentences have a
# mean of 4, so every possible merge exceeded the cap and the transform stopped entirely on exactly
# the text burstiness targeting most wants to merge. 25 words is just above the measured human mean
# (21.62 on HC3), so this floor never licenses a sentence a human would not write.
_ALWAYS_MERGEABLE_WORDS = 25


def _merge_sentences(sentences: list[str], rate: float = 0.33) -> list[str]:
    """Merge adjacent sentence pairs into compound sentences (raises burstiness)."""
    if len(sentences) < 2:
        return sentences
    # Length budget, relative to the input rather than to a constant: a paper's sentences are
    # legitimately longer than a forum answer's, so a fixed cap would flatten register instead of
    # preserving it.
    _lengths = [len(s.split()) for s in sentences if s.strip()]
    _budget = (sum(_lengths) / len(_lengths)) * _MEAN_LENGTH_BUDGET if _lengths else 0.0
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
        # A merge that would leave a sentence well past the input's average is declined even when
        # the pair repeats an opening. Removing a duplicated span is worth a lot, but not at the
        # cost of a 40-word sentence in prose that averages 21 — that trades a catalogued tell for
        # an uncatalogued one a reader feels immediately.
        _fits = (
            i + 1 >= len(sentences)
            or not _budget
            or len(sentences[i].split()) + len(sentences[i + 1].split())
            <= max(_budget * 1.5, _ALWAYS_MERGEABLE_WORDS)
        )
        if i + 1 < len(sentences) and _fits and random.random() < take and _mergeable(
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
            # A clause that opens with a subordinator keeps it (see `_LEADING_SUBORDINATOR_RE`):
            # stripping would break the clause, and adding a connector in front of it produces
            # "but though, there are…". Neither is acceptable, so this pair is not merged — the
            # first sentence is emitted on its own, exactly as the "not safe to demote" branch
            # below does. Advancing without appending it would delete it from the output.
            if _LEADING_SUBORDINATOR_RE.match(b):
                out.append(sentences[i])
                i += 1
                continue
            merged_ok = bool(b) and (
                b[0].islower() or _safe_to_lowercase(b.split()[0], " ".join(sentences))
            )
            # A sentence that is itself a quotation cannot be joined onto the one before it.
            # Measured on dialogue:
            #     '"I told you it would not scale," she said. "Moreover, the cost is prohibitive."'
            #   -> '"... ," she said, and "And, the cost is prohibitive.".'
            # Two separate breakages in one join. The connector lands in front of an opening quote,
            # so the marker substitution inside the quotation ("Moreover," -> "And,") ends up
            # reading "and \"And,"; and the quoted sentence's own full stop sits inside the quote,
            # so rstrip(".!?") cannot reach it and the merge appends a second one after the closing
            # quote. Neither is worth special-casing: a quotation is somebody else's sentence and
            # joining it to the narration changes who is speaking.
            if b.lstrip().startswith(('"', "“", "'", "‘")):
                merged_ok = False
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


# Words that cannot begin an independent clause, so a split leaving one at the front produced a
# fragment. Three groups: relative pronouns ("which can be time-consuming"), exemplifiers and
# appositive leads ("such as using chemicals"), and bare prepositions ("with the results in hand").
# Articles are deliberately ABSENT — "A new method solves this." is a perfectly good sentence — so
# the appositive case is handled positionally below instead.
_CANNOT_OPEN_A_CLAUSE = frozenset(
    {
        "which", "who", "whom", "whose", "that", "where", "when",
        "such", "including", "like", "especially", "particularly", "namely", "e.g.", "i.e.",
        "with", "without", "from", "by", "of", "as", "than", "via", "per", "among", "between",
        "rather", "instead", "along", "across", "toward", "towards", "upon", "regarding",
    }
)

# Fronted adverbials, which are a DIFFERENT case from the set above and cannot join it.
#
# "Regardless of their actions or beliefs." is a fragment; "Regardless of the cost, we proceed." is
# a sentence. Same lead word, and the set above is unconditional — so adding `regardless` to it
# would block a legitimate split, while leaving it out let this through. FOUND at best_of=3 over
# five iterations, which is where enough transforms fire for it to appear:
#
#     ...condone the assassination of any individual, regardless of their actions or beliefs.
#       ->  ...condone the assassination of any individual.
#           Regardless of their actions or beliefs.
#
# `regarding` is already in the set above; `regardless` was simply missed, and the family with it.
# What separates the two readings is whether a MAIN CLAUSE follows, and a fronted adverbial that has
# one is separated from it by a comma. Checked on ten pairs — one fragment and one sentence for each
# of five leads — the comma rule splits all ten correctly.
_NEEDS_A_MAIN_CLAUSE = frozenset(
    {"regardless", "despite", "notwithstanding", "unlike", "throughout", "during",
     "within", "beyond", "concerning", "versus", "besides", "amid", "amidst"}
)
_ARTICLES = frozenset({"a", "an", "the"})

# Words that open a DEPENDENT clause, so a sentence starting with one is not complete until
# its main clause arrives. Defined here rather than reusing _FRONTABLE (declared much later,
# next to the fronting transform) because the split guards run before it in the file; the
# test below asserts the two stay in sync.
_FRONTABLE_LEADS = frozenset(
    {"because", "when", "while", "since", "if", "although", "though", "unless",
     "after", "before", "whereas", "whenever", "wherever", "as", "until"}
)

# Fewest words either half of a split may have. A discourse marker is one or two words, so
# anything below this is a stranded opener rather than a sentence.
_MIN_SPLIT_SIDE = 4


def _content_word_count(words: list[str]) -> int:
    """Words in a would-be sentence, not counting a discourse marker this rewriter prepended.

    `_MIN_SPLIT_SIDE` exists to stop a fronted adverbial becoming a sentence, and a marker added by
    `_vary_openers` is not content — it inflates the count by exactly the amount needed to defeat
    the rule. FOUND in a corpus sweep, as the one `stub_sentence` on RAID that was not the known
    truncated-source artefact:

        In this paper, we present a new method...           -> refused, "In this paper" is 3 words
        Put simply, in this paper, we present a new method  -> "Put simply, in this paper."

    Three content words either way. The battery already strips these before judging a fragment
    (`_strip_our_opener`); the splitter that produces them was counting them.
    """
    text = " ".join(words)
    marker = _ANY_LEADING_MARKER_RE.match(text)
    if marker:
        text = text[marker.end():]
    return len(text.split())

# Words that open a subordinate clause, so a half ENDING inside one is a fragment. Wider than
# `_LEADING_SUBORDINATOR_RE`, which governs a different decision (whether two sentences can be
# merged) and was measured for that; "if" is absent there and is the one that produced this bug.
_SUBORDINATORS = frozenset({
    "if", "when", "whenever", "unless", "although", "though", "because", "since", "while",
    "whereas", "whether", "after", "before", "until", "once", "as",
})
# The subset that opens a clause wherever it appears, not only at the head of a segment. Needed
# because the subordinator is often buried: "this means THAT IF we only had HD channels," splits
# into a fragment while its segment begins with an innocent "this".
#
# The others are deliberately absent. "as", "since", "while", "after", "before", "until" and "once"
# are prepositions at least as often as they are subordinators — "as many HD channels as we have",
# "before deployment" — so testing for them anywhere would reject correct splits. They stay in the
# head-of-segment check above, where they are unambiguous.
_CLAUSE_OPENERS_ANYWHERE = frozenset({
    "if", "when", "whenever", "unless", "although", "though", "because", "whereas", "whether",
})
# A split half may end on a coordinator plus a subordinate clause — "..., so if we only had X" —
# and the coordinator must be stepped over to see the subordinator behind it.
_LEADING_COORDINATORS = frozenset({"so", "and", "but", "or", "yet", "for"})


def _orphans_a_subordinate_clause(first: str) -> bool:
    """Would ending the sentence here strand a subordinate clause without its main clause?

    `_cannot_start_a_sentence` asks the same question of the RIGHT half and has always been
    checked. The left half was not, so a split at the comma that CLOSES an if-clause passed every
    guard. FOUND by reading loop output on HC3:

        These TVs can only display SD channels, so if we only had HD channels, those people
        wouldn't be able to watch TV.
          -> These TVs can only display SD channels, so if we only had HD channels.
             Those people wouldn't be able to watch TV.

    The right half is a perfectly good sentence, which is why the existing guard waved it through.
    The left half is a conditional with nothing conditional on it.

    Only the final segment matters: an earlier subordinate clause in the same half has already been
    resolved by the text that follows it inside that half.
    """
    segment = first.rstrip().rstrip(",").rsplit(",", 1)[-1].split()
    if segment and segment[0].lower() in _LEADING_COORDINATORS:
        segment = segment[1:]
    if not segment:
        return False
    if segment[0].lower().strip(",;:") in _SUBORDINATORS:
        return True
    # The segment has no commas in it — that is what `rsplit` guarantees — so a clause opened
    # anywhere inside it is still open at the split point.
    return any(w.lower().strip(",;:()") in _CLAUSE_OPENERS_ANYWHERE for w in segment)


def _cannot_start_a_sentence(second: str, first: str) -> bool:
    """Would promoting ``second`` to its own sentence leave a fragment?

    Two signals, both cheap — this path is on the zero-dependency tier, so no parser is available.

    1. The opening word is one that cannot begin an independent clause (see the set above).
    2. An APPOSITIVE: the first half ends on a proper noun and the second opens with an article,
       as in "we present EdgeFlow, a novel approach to ...". The article groups cannot go in the
       set — most sentences beginning "The" are fine — so this needs the left context to decide.

    Returns True when the two halves should be rejoined with a comma rather than split.
    """
    # The LEFT half must also stand alone. A sentence opening with a subordinator is a dependent
    # clause until its main clause arrives, so splitting after it strands the subordinator:
    # "Because salt lowers the freezing point of water. The ice melts." This became reachable the
    # moment _front_subordinate_clauses started putting those clauses at the front — a transform
    # feeding a fragment to the pass after it, which is the third time that shape has appeared.
    left = first.split()
    if left and left[0].rstrip(",.;:").lower() in _FRONTABLE_LEADS:
        return True

    # Leading punctuation is stripped before the word is read. `_parenthesise_asides` runs before
    # this pass, so by the time the split is judged the aside may already carry a bracket, and
    # "(which" matched nothing in the set. FOUND by reading loop output on HC3:
    #
    #     ...pigments in your iris. (which is the colored part of your eye) and by the way...
    #
    # The guard was working and the token had changed under it — the fragment is identical, one
    # character wider. Quotes are stripped for the same reason: `_swap` and the dialogue passes can
    # both put one in front of a clause this pass then has to judge.
    head = second.lstrip("([{\"'“‘").split()
    if not head:
        return True
    lead = head[0].rstrip(",.;:").lower()
    if lead in _SPLIT_CONJUNCTIONS or lead in _CANNOT_OPEN_A_CLAUSE:
        return True
    # A fronted adverbial with no main clause after it — see `_NEEDS_A_MAIN_CLAUSE`. Conditional on
    # the comma, because these leads are the one family where the same word opens a fragment and a
    # sentence: "Regardless of their beliefs." against "Regardless of the cost, we proceed."
    if lead in _NEEDS_A_MAIN_CLAUSE and "," not in second:
        return True
    if lead in _ARTICLES:
        tail = first.split()
        # A capitalised final word that is not the sentence's own first word is a name, and
        # "<Name>, a <noun phrase>" is an appositive rather than two clauses.
        if len(tail) > 1 and tail[-1][:1].isupper():
            return True
    return False


def _semicolons_to_periods(text: str) -> str:
    """Promote each "; " to a sentence break, but only where the right side can stand alone.

    The previous form was ``_SEMICOLON_RE.sub(". ", text)``, which had two defects that only show
    up by reading output. It produced fragments whenever the semicolon introduced a list or a
    gloss — "many tasks; including autonomous driving" became "many tasks. including autonomous
    driving" — and it never capitalised what followed, so "shipped it; the customers were happy"
    became "shipped it. the customers were happy", which is both broken English and a formatting
    tell in its own right.

    MEASURED over 60 RAID+HC3 texts through the full pipeline: "Including ..." was the single most
    common fragment in rewritten output, and every instance traced here. The sentence-level stages
    were innocent — attributing the fragments stage by stage found none until the text-level passes
    were included.
    """
    out: list[str] = []
    pos = 0
    for m in _SEMICOLON_RE.finditer(text):
        left = text[pos:m.start()]
        right = text[m.end():]
        if _cannot_start_a_sentence(right, left):
            out.append(text[pos:m.end()])   # leave the semicolon exactly as it was
        else:
            out.append(left + ". ")
            # Capitalise the clause the break exposes; nothing else in the pipeline does it here.
            if right[:1].islower():
                text = text[:m.end()] + right[0].upper() + right[1:]
        pos = m.end()
    out.append(text[pos:])
    return "".join(out)


def _gerund_takes_an_object(following: list[str]) -> bool:
    """``following`` starts at the gerund. Does a noun phrase come after it?

    This is what separates "needs calibrating before every session" — correct, the passive reading
    holds — from "needs balancing accuracy, speed and efficiency", which is not English. No parser
    is available on this tier, so the test is the word after the gerund: a preposition or a
    conjunction ends the phrase, anything else opens the object.

    A gerund at the end of a sentence has no object either, which is the "needs calibrating." case.
    """
    if len(following) < 2:
        return False
    gerund = following[0]
    if gerund.rstrip(",.;:!?") != gerund:  # punctuation right after it closes the phrase
        return False
    return following[1].strip(",.;:!?()").lower() not in _NOT_AN_OBJECT


def _looks_like_a_serial_list(words: list[str]) -> bool:
    """Do the commas in this sentence separate list items rather than clauses?

    Three or more comma-terminated tokens is the signal:

        "The authors, Smith, Jones, and Patel, reported that ..."
          -> "The authors, Smith, Jones, and Patel." + the subjectless "Reported that ..."
        "...to address the ethical, social, and technical challenges..."
          -> "...to address the ethical." + "Social, and technical challenges..."

    Shared by both splitters on purpose. `_split_one` has had this guard for a long time and
    `_split_long_sentences` did not, which is the THIRD time these two functions have been found
    with the same hole in one of them — the fragment guard and the midpoint default were the other
    two, and both times fixing one left the damage rate unmoved because the other kept producing it.
    A predicate one of them can have and the other can lack is the shape of that bug, so there is
    now one definition and two callers.
    """
    return sum(1 for w in words if w.endswith(",")) >= 3


def _split_long_sentences(sentences: list[str], max_words: int = 28, rate: float = 0.25) -> list[str]:
    """Split sentences longer than ``max_words`` words at a suitable break point."""
    out: list[str] = []
    for s in sentences:
        words = s.split()
        if len(words) > max_words and random.random() < rate and not _looks_like_a_serial_list(words):
            # Find a good split: after a comma. There is no "natural midpoint" — a word boundary
            # chosen by counting is a clause boundary only by luck.
            mid = len(words) // 2
            # Look for a comma around the midpoint. `split_at` starts at None, not at `mid`: it used
            # to default to the midpoint, so a sentence with NO comma was split at whatever word
            # sat halfway. FOUND by reading RAID output:
            #
            #   ...a team of experts in the field of artificial.
            #   Intelligence (AI) and medical imaging set out a set of guiding principles...
            #
            # cut through the middle of "artificial intelligence". Nothing downstream could catch
            # it — "Intelligence (AI) and medical imaging set out..." opens with a capitalised noun
            # and reads as a sentence to every guard here. MEASURED over 269 long sentences across
            # HC3 and RAID, 26 of them (9.7%) contain no comma at all and were being cut this way.
            # Not splitting them costs a transform on a tenth of long sentences; splitting them
            # costs grammar on all of it.
            split_at = None
            for offset in range(mid):
                for pos in (mid + offset, mid - offset):
                    # `.rstrip` before the test: a comma that closes a quotation or a bracket lives
                    # in a token like `Imaging,"`, which does not end with a comma and made the one
                    # real boundary in that RAID sentence invisible — which is how it reached the
                    # midpoint fallback in the first place. 1 sentence in 269, and it was this one.
                    if 0 < pos < len(words) and words[pos].rstrip("\"')]”’").endswith(","):
                        split_at = pos + 1
                        break
                if split_at is not None:
                    break
            if split_at is None:
                out.append(s)
                continue
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
            # Same minimum-side rule as _split_one: a one- or two-word left half is a stranded
            # discourse marker, not a sentence. Counted in CONTENT words — see `_content_words` —
            # because a marker `_vary_openers` prepended inflates the count by exactly enough to
            # get past this rule.
            if (
                _content_word_count(words[:split_at]) < _MIN_SPLIT_SIDE
                or len(words) - split_at < _MIN_SPLIT_SIDE
            ):
                out.append(s)
                continue
            first = " ".join(words[:split_at]).rstrip(",")
            second = " ".join(words[split_at:])
            if not first.strip():
                out.append(s)
                continue
            if second:
                second = second[0].lower() + second[1:] if second[0].isupper() else second
                # Check if we broke mid-clause (second starts with a conjunction), or mid-PHRASE.
                # The conjunction test alone was not nearly enough: the split point is "any comma
                # near the midpoint", and most commas in real prose do not mark a clause boundary.
                # FOUND by reading actual rewriter output on RAID and HC3 rather than by any metric,
                # because a fragment is perfect English to a tell catalogue:
                #   "There are other options for melting ice and snow on roads. Such as using
                #    chemicals like calcium chloride ..."          (exemplifier comma)
                #   "In this paper, we show EdgeFlow. A new way to interactive segmentation that
                #    leverages the concept of edge-guided flow."   (appositive comma)
                # Broken English is worse for a reader than any detector score, and nothing in the
                # suite was looking: score_tells has no grammaticality check.
                # The left half is asked the same question — see `_orphans_a_subordinate_clause`.
                # This function and `_split_one` had the identical hole once before, and fixing one
                # of them left the fragment count unmoved because the other kept producing them.
                if _cannot_start_a_sentence(second, first) or _orphans_a_subordinate_clause(first):
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


# Contractions per 100 words in the HUMAN half of the paired corpora, which is the level this pass
# aims at rather than exceeds. MEASURED over 200 pairs each:
#
#                  human mean   human median   AI mean   after unbounded injection
#     HC3            0.666         0.357        0.757            2.263
#     RAID           0.045         0.000        0.079            0.215
#
# Two things follow, and both contradict the rationale this function was written on. AI text
# already contracts *at or above* the human rate in both corpora — the premise that "AI contracts
# far less than human writing" is simply false here — and unbounded injection took HC3 text to 3.4x
# the human rate, which is its own signature. 46% of human HC3 texts and 94% of human RAID texts
# contain no contraction at all.
#
# The detectors do not arbitrate this: injection measured at delta +0.0000 (HC3) and -0.0003 (RAID)
# on the full tier over 14 texts each, helping 1 of 14 both times. So this is not a scoring fix. It
# is a frequency fix, made because overshooting a human distribution by 3.4x costs nothing to avoid
# and nothing downstream would have caught it — score_tells has no contraction check.
_HUMAN_CONTRACTIONS_PER_100W = 0.67
_WORD_RE = re.compile(r"[A-Za-z']+")
# Both the ASCII apostrophe and U+2019, which is what most real prose actually carries.
_CONTRACTED_RE = re.compile(r"\b\w+['’](?:s|t|re|ve|ll|d|m)\b", re.IGNORECASE)


def _contraction_rate(text: str) -> float:
    words = len(_WORD_RE.findall(text))
    return len(_CONTRACTED_RE.findall(text)) / words * 100 if words else 0.0


def _inject_contractions(text: str, rate: float = 1.0) -> str:
    """Contract formal verb phrases ("do not" -> "don't", "it is" -> "it's"). Case-preserving.

    Injects only up to the measured human rate — text already at or above it is left alone. ``rate``
    in [0, 1] additionally thins each candidate match.
    """
    words = len(_WORD_RE.findall(text))
    if not words:
        return text
    # Budget in contractions, not in matches: the text may already carry some, and those count.
    have = len(_CONTRACTED_RE.findall(text))
    budget = _HUMAN_CONTRACTIONS_PER_100W * words / 100 - have
    remaining = int(budget)
    # A rate is a document-level statistic, and the pipeline hands this function one block at a
    # time. On a short block the budget rounds to zero and the transform would silently never fire —
    # "It is not clear." is four words, for a budget of 0.027. So a text carrying NO contraction at
    # all is always allowed one; that is the difference between formal and conversational register,
    # which is what this pass is for. Text that already contracts is never pushed higher.
    if remaining < 1:
        if have or budget <= 0:
            return text
        remaining = 1

    for pat, repl in _CONTRACTIONS:
        def _sub(m: re.Match, _repl: str = repl) -> str:
            nonlocal remaining
            if remaining <= 0:
                return m.group(0)
            if rate < 1.0 and random.random() > rate:
                return m.group(0)
            remaining -= 1
            out = m.expand(_repl)
            if m.group(0)[:1].isupper():
                out = out[0].upper() + out[1:]
            return out

        text = pat.sub(_sub, text)
    return text


# Words that may remain in a trailing sentence after its sign-off phrase is removed and still count
# as pure scaffolding. `_META_CLOSER_RE` matches a PREFIX for half its alternatives — "Let me know
# if X" leaves X behind — so the remainder length is what separates a sign-off from a sentence
# wearing one. MEASURED on seven sign-offs and three content sentences that begin with the same
# phrases:
#
#     scaffolding remainders   0, 0, 3, 4, 5, 5, 5
#     content remainders       10, 11, 17
#
# Six sits between them with margin on both sides. The evidence is thin — ONE of those content
# sentences is a real corpus instance and the rest are constructed — so this is a threshold to
# re-measure if a document ever loses a sentence it should have kept, not a fitted constant.
# The remainder bound and the predicate that uses it moved to `untell.scripts.tells` when the
# meaning gate needed the same answer — see `tells.is_pure_scaffolding`. Aliased here so existing
# readers and tests still find the name where the transform lives.
_CLOSER_REMAINDER_WORDS = _TELLS_CLOSER_REMAINDER_WORDS


def _strip_meta_closers(text: str) -> str:
    """Drop a chatbot sign-off from the END of the text.

    `meta_closer` was FLAGGED AND UNREMOVABLE: sweeping every tell category over 120 corpus texts for
    "detected, and does the rewriter reduce it" gave `false_range` 2/0, `meta_closer` 1/0 and
    `challenges_section` 1/0 — three categories the catalogue counts and no transform could act on.
    Of the three this is the one with an obvious safe action: "I hope this helps!" carries no content
    at all, so removing it is not a rewrite, it is a deletion of scaffolding.

    MEASURED on four sign-offs appended to a real paragraph — the tell goes 1 -> 0 (2 -> 0 for a
    doubled one) and every gate passes: similarity 0.981-0.997, `passes` True, `contradicts` False,
    numerals kept.

    Built on `tells._META_CLOSER_RE` rather than a second pattern of its own. The `vague_attribution`
    defect one commit earlier was exactly two vocabularies drifting apart — the detector flagging a
    phrase the flattener had never heard of — and the cheapest way not to repeat it is to have one
    pattern with two readers.

    Only at the END, and only a whole trailing sentence. "Let me know if the build fails" mid-document
    is a real instruction to a reader, and "In this article we'll explore ..." is an opener the same
    pattern matches; deleting either would remove content rather than scaffolding.

    And only when the sentence is NOTHING BUT the closer. The first version of this deleted any
    trailing sentence the pattern matched, and the one real corpus instance is

        "I hope this helps to explain why we might not have high resolution color cameras on some
         space probes and satellites."

    — the paragraph's conclusion, wearing a sign-off as a prefix. Removing the matched phrase leaves
    **17 words** there against **0** for "I hope this helps!", so the remainder is the test. A tell
    fix that deletes the user's last sentence is a far worse defect than the tell.
    """
    sentences = _split_sentences(text)
    kept_sentences = list(sentences)
    while len(kept_sentences) > 1 and is_pure_scaffolding(kept_sentences[-1]):
        kept_sentences.pop()
    if len(kept_sentences) == len(sentences):
        return text
    kept = " ".join(s.strip() for s in kept_sentences).strip()
    return kept or text


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
        # A word with both an adverb and an adjective sense, whose substitutes only have the adverb
        # one. "overall" is the only such headword in the table — MEASURED by scanning every _SYN
        # entry with a phrasal substitute for `<determiner> <head> <noun>` in 240 HC3 texts, which
        # returns "overall" and nothing else with a live adjective sense. All three of its
        # substitutes are sentence adverbs, so in the adjective slot all three break:
        #
        #     the overall cost           -> the all told cost / the in the end cost
        #     improves overall efficiency -> improves in the end efficiency
        #
        # The adverbial slots are fine and stay fine — "improved overall." and "the result,
        # overall, was" all three substitute cleanly, and sentence-initial "Overall," is already
        # declined above and left to the transition stripper. So the test is not the determiner
        # before it (the third example has none) but the word after it: a letter means the next
        # token is what "overall" is modifying, and an adverb phrase cannot modify a noun.
        if word.lower() in _ADVERB_SLOT_ONLY:
            after = (tail or masked[m.end():]).lstrip(" \t")
            if after[:1].isalpha():
                return m.group(0)
        # Prefer an option this text has not used yet; fall back to the full list when every option
        # is spent, because leaving the AI word in place is worse than repeating a plain one.
        fresh = [o for o in options if o not in spent]
        choice = random.choice(fresh or options)
        # A separable phrasal-verb substitute takes its object INSIDE: "putting it to work", never
        # "putting to work it". "spell out the details" is fine, so the fault is not the particle —
        # it is a particle followed by a PRONOUN. FOUND when `applying -> putting to work` turned
        # "applying it accurately" into "putting to work it accurately"; `harnessing` carried the
        # same latent bug already. Rather than reorder the object, which needs to know where the
        # object ends, decline and let another option or another pass handle the word.
        if " " in choice and choice.rsplit(" ", 1)[-1].lower() in _SEPARABLE_PARTICLES:
            after = masked[m.end():].lstrip()
            if after.split()[:1] and after.split()[0].strip(",.;:").lower() in _PRONOUN_OBJECTS:
                plain = [o for o in (fresh or options) if " " not in o]
                if not plain:
                    return m.group(0)
                choice = random.choice(plain)
        # Some words carry their preposition. "an approach TO segmentation" is idiomatic and
        # "a method to segmentation" is not, so swapping the noun silently breaks the phrase.
        # FOUND when the repaired contradiction gate started vetoing real candidates: three of the
        # four it caught were not meaning changes at all, they were this —
        #     "a novel approach to medical image segmentation"
        #       -> "an original way to medical image segmentation"
        # — and the NLI model reads badly-formed English as not-entailing, which is fair.
        # Checked against the following word rather than a curated collocation list, because the
        # rule is about the preposition and nothing else.
        if word.lower() in _PREPOSITION_BOUND:
            # The preposition is usually already inside `tail` — the match pattern captures a
            # following particle as group(3) precisely so this pass can see it — but it is only
            # captured for the particles in that list, so fall back to the next word otherwise.
            after = (tail or masked[m.end():]).lstrip()
            next_word = after.split()[0].strip(",.;:").lower() if after.split() else ""
            if next_word in _PREPOSITION_BOUND[word.lower()]:
                return m.group(0)
        # A noun-phrase adverbial cannot premodify anything but a comparative — see
        # `_POSTMODIFIER_ONLY`. Filtered, not declined: "sharply" and "greatly" are correct in the
        # same slot and are what the swap should use there.
        postmod = _POSTMODIFIER_ONLY.get(word.lower())
        if postmod:
            following = (tail or masked[m.end():]).lstrip().split()
            if following and following[0][:1].isalpha() and not _premodifies_a_comparative(following):
                usable = [o for o in (fresh or options) if o.lower() not in postmod]
                if not usable:
                    return m.group(0)
                choice = random.choice(usable)
        # The headword is followed by a comma and some substitutes cannot precede one — see
        # `_COMMA_UNSAFE`.
        comma_unsafe = _COMMA_UNSAFE.get(word.lower())
        if comma_unsafe and (tail or masked[m.end():]).lstrip(" \t").startswith(","):
            usable = [o for o in (fresh or options) if o.lower() not in comma_unsafe]
            if not usable:
                return m.group(0)
            choice = random.choice(usable)
        # A gerund follows, and some substitutes cannot govern one — see `_GERUND_UNSAFE`. Filtered
        # rather than declined: `involves -> means` reads correctly in the same slot, so the swap is
        # still worth making.
        always = _GERUND_UNSAFE.get(word.lower(), frozenset())
        with_object = _GERUND_OBJECT_UNSAFE.get(word.lower(), frozenset())
        if always or with_object:
            following = (tail or masked[m.end():]).lstrip().split()
            next_word = following[0].strip(",.;:") if following else ""
            if next_word.lower().endswith("ing") and len(next_word) > 4:
                unsafe = always | (
                    with_object if _gerund_takes_an_object(following) else frozenset()
                )
                usable = [o for o in (fresh or options) if o.lower() not in unsafe]
                if not usable:
                    return m.group(0)
                choice = random.choice(usable)
        # An article already sits in front of this word, so a substitute that begins with its own
        # determiner stacks two. FOUND on the one corpus case of the shape: "a significantly longer
        # wait" -> "an a lot longer wait", where `agree_article` had also faithfully re-agreed "a"
        # to "an" for the following vowel, making the output worse rather than catching it. Filter
        # rather than decline, matching the separable-particle rule above — "sharply" and "greatly"
        # are fine in this slot and the swap is still worth making.
        if article and choice.split(" ", 1)[0].lower() in _BARE_ARTICLES:
            usable = [
                o for o in (fresh or options) if o.split(" ", 1)[0].lower() not in _BARE_ARTICLES
            ]
            if not usable:
                return m.group(0)
            choice = random.choice(usable)
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
    # "testament" governs "to"; every word-level substitute for it governs "of". The entry in
    # `word_importance._SYN` swapped the noun and left the preposition, so real output read
    # "It's a sign to the work." and "A mark to the effort." — ungrammatical, and invisible to the
    # tell catalogue, which counts vocabulary and never parses. The line above only covered the
    # "stands as a testament to" form; these two carry the rest, rewriting noun and preposition
    # together so no later pass has to guess which one is wrong.
    (re.compile(r"\bis\s+a\s+testament\s+to\b", re.IGNORECASE), "shows"),
    (re.compile(r"\ba\s+testament\s+to\b", re.IGNORECASE), "proof of"),
    # --- coverage pass -------------------------------------------------------------------------
    # AUDITED by probing every pattern in `tells._CLICHES` through this rewriter: 41 of 57 fired as
    # a `cliche` tell and survived every draw. `cliche` is the strongest category in the catalogue
    # (precision 0.902 on HC3, 0.941 on RAID) and this table was treating 16 of them.
    #
    # The entries below are the subset where a plain rewrite is unambiguous. Pure scaffolding is
    # deleted; a phrase carrying meaning is replaced by the plainest wording of the same meaning.
    # Nothing here is a judgement call about what the author meant.
    #
    # WHAT THIS BUYS ON TODAY'S CORPORA: nothing measurable, and that is stated rather than left to
    # be assumed. Measured with the table before and after this block:
    #
    #     HC3  (60)  mean tells/100w 6.045 -> 6.040   cliche hits after rewrite 1 -> 0
    #     RAID (80)  15 cliche hits in source, 0 after rewrite with EITHER table
    #     MAGE (80)   2 cliche hits in source, 0 after rewrite with EITHER table
    #
    # The 41-of-57 coverage gap was a real property of the table and the phrases it missed barely
    # occur in these corpora, so closing it moves no number. Kept anyway, for the reason
    # `scripts/tells.py` gives for keeping the tells these corpora never fire: HC3 is 2022-era
    # ChatGPT and RAID's generators are not much newer, while "game-changer", "deep dive" and "the
    # tip of the iceberg" are current corporate-AI vocabulary. Declining to treat a modern phrase
    # because a dated benchmark does not contain it is the same mistake as deleting the pattern
    # that detects it. What is NOT claimed is an improvement: on anything measurable here, this is
    # a no-op.
    (re.compile(r"\bin\s+conclusion,?\s*", re.IGNORECASE), ""),
    (re.compile(r"\b(?:in\s+summary|to\s+summari[sz]e),?\s*", re.IGNORECASE), ""),
    (re.compile(r"\bit\s+should\s+be\s+noted\s+that\s+", re.IGNORECASE), ""),
    (re.compile(r"\bit'?s\s+no\s+secret\s+that\s+", re.IGNORECASE), ""),
    (re.compile(r"\bat\s+its\s+core,?\s*", re.IGNORECASE), ""),
    (re.compile(r"\bthe\s+bottom\s+line\s+is\s+that\s+", re.IGNORECASE), ""),
    (re.compile(r"\bthe\s+bottom\s+line\s+is\b", re.IGNORECASE), "in short"),
    (re.compile(r"\blet'?s\s+dive\s+in(?:to)?\b", re.IGNORECASE), "let's start"),
    (re.compile(r"\b(?:deep\s+dive|deep-dive)\b", re.IGNORECASE), "close look"),
    (re.compile(r"\bdive\s+into\b", re.IGNORECASE), "look at"),
    (re.compile(r"\bshed\s+light\s+on\b", re.IGNORECASE), "explain"),
    (re.compile(r"\bgame[-\s]?chang(?:er|ing)\b", re.IGNORECASE), "major change"),
    (re.compile(r"\bat\s+the\s+forefront\s+of\b", re.IGNORECASE), "leading"),
    (re.compile(r"\bpush\s+the\s+boundaries\s+of\b", re.IGNORECASE), "extend"),
    (re.compile(r"\ba\s+double[-\s]edged\s+sword\b", re.IGNORECASE), "a trade-off"),
    (re.compile(r"\bthe\s+tip\s+of\s+the\s+iceberg\b", re.IGNORECASE), "a small part of it"),
    (re.compile(r"\bin\s+the\s+(?:age|world)\s+of\b", re.IGNORECASE), "in"),
    (re.compile(r"\bin\s+an\s+era\s+where\b", re.IGNORECASE), "when"),
    (re.compile(r"\bas\s+technology\s+continues\s+to\s+evolve,?\s*", re.IGNORECASE), ""),
    #
    # "one of the most important" is deliberately absent. "a key" is the natural flattening and it
    # disagrees in number with the plural noun that always follows: "one of the most important
    # rules" -> "a key rules". Same shape as the testament/preposition break above — a substitution
    # table matches a string and cannot inflect what comes after it, so a phrase whose replacement
    # must agree with its object does not belong in one. Caught by reading the output of this very
    # pass, which is the third time that has been the only thing that would have.
    #
    # NOT added, and the reason is the same for all of them: they assert something. "The future
    # looks bright", "only time will tell", "one thing is certain", "the possibilities are
    # endless", "as we move forward" and "a sea change" are claims about the world, not
    # scaffolding around a claim. Deleting one removes a proposition the author made; replacing it
    # requires deciding what they meant by it. Both are meaning edits, which is not this
    # transform's job — it flattens phrasing. They stay catalogued as tells so a caller sees them,
    # and the rewrite is left to the neural path or to the author.
]

# `(?<!\.)` so the LAST dot of an ellipsis is not read as a sentence end. An ellipsis is a pause,
# and the clause after it continues in lowercase — capitalising there manufactures a subjectless
# fragment out of correct input. MEASURED at intensity 1.0, on 4 of 12 seeds:
#
#     "He paused... then continued with the analysis."
#       -> "He paused... Then continued with the analysis."
#
# Invisible to every gate: no word changed, so similarity, NLI and the role check all pass, and a
# fragment is clean to a tell catalogue. `[!?]` is deliberately still allowed after a dot-free
# terminator, so "What?! yes ..." keeps its capital.
_AFTER_SENTENCE_START = re.compile(r"(^|(?<!\.)[.!?]\s+)([a-z])(\S*)")

# A token that is not a WORD does not get a sentence capital. The restore pass upcases the first
# letter after any terminator, which is right for prose and wrong for the things technical text puts
# at the start of a sentence. MEASURED:
#
#     "Call untell.score. untell.tells also works."   -> "... Untell.tells also works."
#     "Install untell==0.2.0. pip handles the rest."  -> "... Pip handles the rest."
#
# An identifier, a module path, a package name or a shell command is lowercase because that is its
# spelling, not because a capital went missing. Broken capitalisation is itself a catalogued tell,
# so the transform that exists to remove tells was adding one — the same sentence the opener
# transform already carries about "Actually, Issue #4821 tracks ...".
#
# Scoped by SHAPE, not by a word list: a dotted path, an assignment or comparison, a call, a flag,
# a path separator, or a digit. Ordinary prose words contain none of these, so the correction that
# makes this function useful — "The result was clear. it was also cheap." -> "It" — is untouched.
_NOT_A_PROSE_WORD = re.compile(r"[.=/\\(){}\[\]<>@:_\d-]|^-{1,2}[a-z]")


def _capitalise_sentence_start(match: re.Match) -> str:
    """Upcase the first letter of a sentence, unless the token is not prose."""
    lead, first, rest = match.group(1), match.group(2), match.group(3)
    if _NOT_A_PROSE_WORD.search(rest):
        return match.group(0)
    return lead + first.upper() + rest


# The capital restore above finds a sentence start at the beginning of the STRING or after a
# terminator. Neither describes a line that opens with a marker, so a deletion there left the tell it
# exists to prevent. MEASURED, one cliché stripped from the head of each line:
#
#     Alice: In conclusion, organizations ...  ->  "Alice: organizations must adopt ..."
#     1.3 In conclusion, any defect ...        ->  "1.3 any defect shall be notified ..."
#     - In conclusion, the team ...            ->  "- the team must use a sturdy approach"
#     ## In conclusion, the team ...           ->  "## the team must tap into a solid approach"
#
# **6 of 7 marker kinds reached shipped `structural_rewrite` output.** Only "1. " survived, and by
# accident: its dot reads as a terminator to the pattern above, so the existing repair fired.
#
# Widening that pattern to every line start is the wrong fix twice over. A soft-wrapped paragraph
# continues mid-sentence in lower case, and — the case that decided this — plenty of marked lines are
# DELIBERATELY lower case:
#
#     (a) the Seller shall deliver ...     legal drafting, lower case by convention
#     - apples / - bananas                 list fragments
#
# So the rule is to RESTORE a capital that was there, never to invent one: a line is corrected only
# when the transform changed it AND the word it now begins with was capitalised before. That is what
# the docstring always claimed, applied at the boundary it missed.
_LINE_MARKER_PREFIX = re.compile(
    r"^[ \t]*(?:"
    r"[-*+>]+[ \t]+"  # bullet, blockquote
    r"|\#{1,6}[ \t]+"  # heading
    r"|\d+(?:\.\d+)+[ \t]+"  # dotted clause: 1.3, 2.4.1
    r"|\(?[A-Za-z0-9]{1,4}[.)][ \t]+"  # 1. / 1) / (a) / (iv)
    r"|[A-Z][A-Za-z.'’-]{0,20}:[ \t]+"  # speaker label
    r")"
)


def _first_word_after_marker(line: str) -> tuple[int, str]:
    """Offset and token of the first word on a line, skipping any list or speaker marker."""
    marker = _LINE_MARKER_PREFIX.match(line)
    start = marker.end() if marker else len(line) - len(line.lstrip())
    return start, line[start:].split(" ", 1)[0]


def _restore_marker_capitals(before: str, after: str) -> str:
    """Re-capitalise lines a deletion left lower-case, where the capital existed beforehand."""
    old_lines, new_lines = before.split("\n"), after.split("\n")
    if len(old_lines) != len(new_lines):  # a transform moved a line boundary; alignment is a guess
        return after
    out = []
    for old, new in zip(old_lines, new_lines):
        start, word = _first_word_after_marker(new)
        _, was = _first_word_after_marker(old)
        if (
            old != new
            and word[:1].islower()
            and was[:1].isupper()
            and not _NOT_A_PROSE_WORD.search(word[1:])
        ):
            new = new[:start] + word[0].upper() + new[start + 1 :]
        out.append(new)
    return "\n".join(out)


def _flatten_cliches(text: str) -> str:
    """Delete or plainly replace the catalogued clichés.

    Deletions leave a lower-case word where a sentence now begins, so capitalisation is restored
    afterwards — otherwise removing "It is important to note that " turns the sentence into one
    starting mid-word, which is a more obvious tell than the cliché was.
    """
    if not text.strip():
        return text
    source = text
    for pattern, replacement in _CLICHE_FLATTEN:
        text = pattern.sub(replacement, text)
    text = _AFTER_SENTENCE_START.sub(_capitalise_sentence_start, text)
    return _restore_marker_capitals(source, text)


def _flatten_copula(text: str) -> str:
    """Flatten inflated copulas: 'serves as'/'represents'/... → 'is', and 'boasts' → 'has'."""
    text = _BOASTS_RE.sub("has", text)
    text = _INFLATED_COPULA_RE.sub("is", text)
    return text


def _flatten_vague_attribution(text: str) -> str:
    """Replace 'studies show' with concrete alternatives.

    Case is carried across from whatever was matched. The substitution was a flat string, so a
    sentence-initial "Studies show that ..." became ". evidence suggests that ..." — caught by the
    battery's own `lowercase_after_full_stop` check, which fires on the output and not on the source.

    It went unnoticed because this transform never fired on real corpus text: over 50 HC3 and RAID
    documents it changed 0. Widening the pattern to cover the impersonal forms the detector already
    flags is what made the defect reachable, so it is fixed in the same commit rather than shipped
    by it.
    """

    def _replace(match: re.Match) -> str:
        return "Evidence suggests" if match.group(0)[:1].isupper() else "evidence suggests"

    return _VAGUE_ATTR_RE.sub(_replace, text)


# Subordinators whose clause can move to the FRONT of its sentence without changing what the
# sentence says. "The ice melts because salt lowers the freezing point." and "Because salt lowers
# the freezing point, the ice melts." are the same claim in either order — English marks the
# relation on the subordinator, not on the position.
#
# "as" and "so" are deliberately absent: "as" is three different words (causal, temporal,
# comparative) and fronting the comparative one changes the reading, while "so" trailing is usually
# a result coordinator ("... , so we adopted it"), which cannot front at all.
_FRONTABLE = (
    "because", "when", "while", "since", "if", "although", "though", "unless",
    "after", "before", "whereas", "whenever", "wherever", "even though", "even if",
)
_FRONTABLE_RE = re.compile(
    r"^(?P<main>.{20,}?)[,]?\s+(?P<sub>" + "|".join(_FRONTABLE) + r")\s+(?P<dep>.{12,})$",
    re.IGNORECASE,
)


# Share of sentences containing a frontable subordinator that HUMANS actually front. MEASURED over
# 200 pairs per corpus:
#
#                   human    ai
#     HC3 (forum)   22.0%   25.2%     AI already fronts slightly MORE than humans
#     RAID (paper)  17.6%    2.8%     humans front 6.3x as often as the generators
#
# So this is a target, not a maximum — the same lesson as contraction injection. Fronting every
# eligible sentence would take HC3-like text to 100% against a human 22%, trading one distribution
# error for a larger one. Academic prose is where the gap is real and where this pays.
_HUMAN_FRONTING_RATE = 0.20
_FRONTED_RE = re.compile(r"^(?:" + "|".join(_FRONTABLE) + r")\b[^,]{5,},", re.IGNORECASE)


def _front_subordinate_clauses(sentences: list[str], rate: float = 0.0) -> list[str]:
    """Move a trailing subordinate clause to the front: "X because Y." -> "Because Y, X."

    Every other transform in this file is LOCAL — a word swap, a split, a merge, a deletion. None
    of them changes the order in which information arrives, which is what a curvature detector
    reads over a long span. This is the one reordering move that is safe without a parser: the
    subordinator travels with its clause, so the relation it marks is preserved exactly.

    Deliberately conservative. It fires only on a sentence with exactly one frontable subordinator,
    never when the dependent clause already carries a comma (which usually means it is not a simple
    two-clause sentence), and never on a question.
    """
    # Budget: how many more sentences must be fronted to reach the human share of the ELIGIBLE
    # ones. Text already at or above that share gets nothing, exactly like _inject_contractions.
    eligible = [s for s in sentences if _FRONTABLE_RE.match(s.strip().rstrip())]
    if not eligible:
        return list(sentences)
    already = sum(1 for s in sentences if _FRONTED_RE.match(s.strip()))
    want = _HUMAN_FRONTING_RATE * len(eligible) - already
    if want <= 0:
        return list(sentences)
    # Fractional budgeting rather than rounding. A block with ONE eligible sentence wants 0.2 of a
    # fronting, and rounding that to zero means short blocks — which is most paragraphs — never
    # front at all, so the aggregate rate lands well under the human 20% however the constant is
    # set. Taking the integer part and adding one more with probability equal to the remainder
    # gives the right rate in expectation at every block length.
    budget = int(want)
    if random.random() < want - budget:
        budget += 1
    if budget < 1:
        return list(sentences)

    out: list[str] = []
    for s in sentences:
        stripped = s.strip()
        m = _FRONTABLE_RE.match(stripped.rstrip()) if budget > 0 else None
        if (
            not m
            or random.random() >= rate
            or stripped.endswith(("?", "!"))
            or "," in m.group("dep")            # multi-clause tail: not a clean two-part sentence
            or sum(stripped.lower().count(f" {w} ") for w in _FRONTABLE) != 1
        ):
            out.append(s)
            continue
        main = m.group("main").rstrip(" ,")
        dep = m.group("dep").rstrip(" .")
        if not main or not dep:
            out.append(s)
            continue
        # The main clause becomes the TAIL of the sentence, so a coordinator at its right edge is
        # left dangling against the full stop: "The model works well and because the encoder is
        # small it runs fast." fronted to "Because the encoder is small it runs fast, the model
        # works well and." The subordinator matched inside a coordinate structure, which this
        # transform is not equipped to reorder — decline rather than repair.
        if main.split()[-1].rstrip(",").lower() in _SPLIT_CONJUNCTIONS:
            out.append(s)
            continue
        # The main clause loses its sentence-initial position, so its capital goes only if the word
        # is safe to lowercase — the same rule the merge and opener paths use, for the same reason:
        # lowercasing whatever happens to be there turns "NASA confirmed" into "nASA confirmed".
        head = main.split()[0]
        if head[:1].isupper():
            if not _safe_to_lowercase(head, " ".join(sentences)):
                out.append(s)
                continue
            main = main[0].lower() + main[1:]
        sub = m.group("sub")
        budget -= 1
        out.append(f"{sub[0].upper()}{sub[1:].lower()} {dep}, {main}.")
    return out


# Share of words that are an opening parenthesis, MEASURED over 120 pairs per corpus:
#
#                    human    ai      ai/human
#     HC3            0.679   0.177     0.26x
#     RAID           0.924   0.421     0.46x
#
# Humans use parentheses two to four times as often, consistently in both corpora. Unlike the other
# punctuation gaps in the same sweep this one is safe to close: question marks (human 15x) would
# invent rhetoric, exclamation marks a tone, and quotation marks would fabricate a quotation.
# Parenthesising an aside that is ALREADY set off by commas changes punctuation and nothing else —
# no word is added, removed or reordered, so the meaning gates see an identical claim.
#
# Only non-restrictive asides qualify. "the method, which is fast, works" carries the same meaning
# with brackets; "the method that is fast works" does not, because a restrictive clause is part of
# what is being identified. The pattern therefore requires an explicit non-restrictive marker and a
# closing comma followed by lower-case continuation — a trailing clause at the end of a sentence is
# not an aside and bracketing it would strand the sentence.
_ASIDE_RE = re.compile(
    r",\s+(which\s+[^,.;:()]{8,60}"
    r"|such as\s+[^,.;:()]{5,50}"
    r"|for example[^,.;:()]{0,50}"
    r"|including\s+[^,.;:()]{5,50}),(?=\s+[a-z])"
)
_HUMAN_PARENTHESES_PER_100W = 0.80

# More list items and then a coordinator: "hair, and eyes their color". Anchored at the character
# after the aside's closing comma. A real aside end is followed by the sentence resuming — "and by
# the way that the iris scatters light" — where the first word IS the coordinator and no item list
# precedes it, so that shape does not match and stays convertible.
_LIST_CONTINUES_RE = re.compile(r"\s+[a-z][\w-]*(?:,\s*[a-z][\w-]*)*,?\s+(?:and|or)\s")

# Words whose meaning is carried partly by the preposition that follows them. Substituting the
# word alone leaves the preposition stranded on a synonym that does not take it: "an approach to
# segmentation" is idiomatic English and "a method to segmentation" is not.
_PREPOSITION_BOUND: dict[str, frozenset[str]] = {
    "approach": frozenset({"to"}),
    "approaches": frozenset({"to"}),
    "solution": frozenset({"to"}),
    "solutions": frozenset({"to"}),
    "response": frozenset({"to"}),
    "alternative": frozenset({"to"}),
    "resistance": frozenset({"to"}),
    "access": frozenset({"to"}),
    "insight": frozenset({"into"}),
    "insights": frozenset({"into"}),
    "reliance": frozenset({"on"}),
    "emphasis": frozenset({"on"}),
    "impact": frozenset({"on"}),
    "effect": frozenset({"on"}),
    "focus": frozenset({"on"}),
    "demand": frozenset({"for"}),
    "need": frozenset({"for"}),
    "capacity": frozenset({"for"}),
    # "in combination WITH" is a fixed frame and its substitutes do not fit it: FOUND by reading
    # loop output, "used in combination with other methods" became "used in pairing with other
    # methods", and `mix` and `blend` break it the same way. Bound to `with` only — "a combination
    # of X" takes every substitute cleanly ("a mix of", "a blend of"), and that is 46 of the 47
    # occurrences across 240 HC3 and RAID texts, so binding the word outright would cost the common
    # case to fix the rare one.
    "combination": frozenset({"with"}),
}

# Substitutes that cannot take a gerund complement, keyed by the headword they replace.
#
# "involves X-ing" means *includes the activity of* X-ing; "needs X-ing" means *requires being*
# X-ed. With an object following, the second reading collapses. FOUND by reading RAID output:
#
#     a fundamental task in computer vision that involves allowing a user to interact
#       -> ...that NEEDS ALLOWING a user to interact
#
# "means allowing a user to interact" is fine, so this filters rather than declines.
#
# MEASURED across 240 HC3 and RAID texts, `involves` is followed by a gerund in 33% of its HC3
# occurrences and 72% of its RAID ones — the majority case in academic prose, not an edge.
#
# `requires`/`require` -> `needs`/`need` look like the same shape and are not: "requires
# calibrating" and "needs calibrating" both carry the passive reading, so they are correct and
# stay. The scan that produced this entry found 29 headwords that ever precede an -ing word, and
# all the others are adjective-plus-noun ("robust testing", "novel tracking") or noun-plus-
# participle ("approach using"), where no verb complement is involved at all.
#
# An entry for `involved` was written here and removed the same hour: the table has no `involved`
# headword, so it guarded a substitution that cannot happen and would have read as protection
# forever. `test_the_unsafe_map_names_real_substitutes` is what caught it.
#
# `requires` is here for a reason worth stating, because the first version of this rule left it out
# on the grounds that "requires calibrating" -> "needs calibrating" is correct. It is — and a
# corpus sweep of 80 rewritten texts found the counter-example anyway:
#
#     ...as it requires balancing accuracy, speed, and computational efficiency
#       -> ...as it NEEDS BALANCING accuracy, speed, and computational efficiency
#
# So the boundary is not the headword, it is whether the gerund takes an OBJECT. "needs balancing"
# alone carries the passive reading and is fine; "needs balancing accuracy" is not. See
# `_gerund_takes_an_object`.
# Two maps, because the two headwords fail for different reasons and a single rule got both wrong.
#
# `involves X-ing` never maps to `needs X-ing` — "includes the activity of" and "requires being" are
# different claims whether or not an object follows. "The procedure involves staring at a fixed
# point" -> "...needs staring at a fixed point" has no object and is still wrong.
_GERUND_UNSAFE: dict[str, frozenset[str]] = {
    "involves": frozenset({"needs", "takes"}),
}

# `requires X-ing` DOES map to `needs X-ing` — both carry the passive reading — until the gerund
# takes an object, at which point the passive reading is unavailable. FOUND by sweeping 80
# rewritten texts after the first version of this rule declared `requires` safe on the strength of
# "requires calibrating" -> "needs calibrating":
#
#     ...as it requires balancing accuracy, speed, and computational efficiency
#       -> ...as it NEEDS BALANCING accuracy, speed, and computational efficiency
#
# `needs` is its only substitute, so in that slot the swap is declined outright. That is correct
# here rather than a sign the entry should go: the other slot still converts.
_GERUND_OBJECT_UNSAFE: dict[str, frozenset[str]] = {
    "requires": frozenset({"needs"}),
}

# Words that can follow a gerund WITHOUT being its object: prepositions, conjunctions, and the
# clause-level words that end the phrase. Anything else after the gerund is a noun phrase, which is
# what makes the passive "needs X-ing" reading impossible.
_NOT_AN_OBJECT = frozenset({
    "before", "after", "under", "over", "with", "without", "for", "from", "into", "onto", "than",
    "at", "by", "in", "on", "to", "of", "as", "and", "or", "but", "so", "because", "when", "while",
    "if", "unless", "though", "although", "during", "across", "through", "within", "between",
})

# Substitutes that cannot stand in front of the comma the headword is already carrying.
#
# "However," is a sentence adverb and takes a comma. "But" and "though" are conjunctions and do not:
# "But, existing methods are limited" and "Though, existing methods are limited" are not English.
# FOUND by reading RAID output, where both forms appeared.
#
# MEASURED across 240 HC3 and RAID texts: "However," occurs 95 times, and "But," and "Though," occur
# ZERO times in either the human or the AI half. So the substitution was not merely ungrammatical,
# it emitted a form nobody in the reference corpus writes — the tell this rewriter exists to remove,
# manufactured by the pass meant to remove it.
#
# 86% of the 117 `however` occurrences are followed by a comma, so this is the usual slot, not the
# rare one. Without the comma the same substitutes are correct — "the method is fast, however it
# fails" -> "...but it fails" — which is why this filters on the comma rather than dropping them.
# "by contrast" is a sentence adverb and stays available in both slots.
_COMMA_UNSAFE: dict[str, frozenset[str]] = {
    "however": frozenset({"but", "though"}),
}

# Substitutes that are noun-phrase adverbials, so they can only sit AFTER what they modify.
#
# "a lot" is the one in the table. "improved significantly" -> "improved a lot" is right; the same
# swap one word earlier is not. FOUND in the `--json` output of the humanize CLI:
#
#     It significantly improves overall efficiency   ->   It A LOT IMPROVES overall efficiency
#
# MEASURED across 240 HC3 and RAID texts, 67 of the 68 `significantly` occurrences are followed by
# a word, so the bad slot is the usual one and the clause-final case is the exception.
#
# The exception that keeps this from being a blanket rule is the COMPARATIVE: "significantly longer"
# -> "a lot longer" is correct, and so is "a lot better" and "a lot more". A noun-phrase adverbial
# can premodify a comparative and nothing else, which is a rule about the following word rather than
# about the part of speech, so it is checkable here without a parser.
_POSTMODIFIER_ONLY: dict[str, frozenset[str]] = {
    "significantly": frozenset({"a lot"}),
}
# Comparatives a noun-phrase adverbial may premodify. `-er` covers the morphological ones; the rest
# are the suppletive and periphrastic forms, which have no ending to match on.
_COMPARATIVES = frozenset({"more", "less", "better", "worse", "further", "fewer", "greater"})


def _premodifies_a_comparative(following: list[str]) -> bool:
    """Is the word after the headword a comparative, the one thing "a lot" may premodify?"""
    if not following:
        return False
    word = following[0].strip(",.;:!?()").lower()
    return word in _COMPARATIVES or (len(word) > 4 and word.endswith("er"))

# Particles that end a separable phrasal verb. A substitute ending in one cannot be followed
# directly by a pronoun object: "put it to work", not "put to work it".
_SEPARABLE_PARTICLES = frozenset(
    {"work", "to", "in", "on", "up", "out", "over", "through", "into", "down", "off", "apart"}
)
_PRONOUN_OBJECTS = frozenset(
    {"it", "them", "this", "that", "these", "those", "him", "her", "us", "me", "you", "one"}
)

# Headwords whose substitutes are all sentence adverbs, but which also have a live adjective sense.
# Substituting in the adjective slot produces "the in the end cost". Derived, not guessed: every
# _SYN entry with a phrasal substitute was scanned for `<determiner> <head> <noun>` across 240 HC3
# texts, and "overall" is the only one with a real adjective sense among the hits.
_ADVERB_SLOT_ONLY = frozenset({"overall"})

# A substitute that opens with one of these cannot follow an article — the output stacks two
# determiners ("an a lot longer wait").
_BARE_ARTICLES = frozenset({"a", "an", "the"})


def _parenthesise_asides(text: str) -> str:
    """Turn a comma-bounded non-restrictive aside into a parenthetical, up to the human rate."""
    words = len(_WORD_RE.findall(text))
    if not words:
        return text
    have = text.count("(")
    budget = _HUMAN_PARENTHESES_PER_100W * words / 100 - have
    if budget <= 0:
        return text
    # Fractional, like the fronting budget: a short block wants a fraction of one conversion, and
    # rounding that to zero means most paragraphs never convert and the aggregate lands at zero
    # however the constant is set.
    remaining = int(budget)
    if random.random() < budget - remaining:
        remaining += 1
    if remaining < 1:
        return text

    def _swap(m: re.Match) -> str:
        nonlocal remaining
        if remaining <= 0:
            return m.group(0)
        # The aside body excludes commas, so when the real aside CONTAINS one the pattern matches a
        # prefix of it and closes the bracket on an internal comma. FOUND by reading loop output on
        # HC3:
        #
        #   one called melanin, which gives your skin, hair, and eyes their color, and another...
        #     -> one called melanin (which gives your skin) hair, and eyes their color, and...
        #
        # "gives your skin" then a dangling "hair, and eyes their color". That is not the
        # punctuation-only change this transform is documented to make and the meaning gates cannot
        # see it — no word was added, removed or reordered, so cosine, NLI and roles all pass a
        # sentence that has been cut in half.
        #
        # The tell is what FOLLOWS the closing comma: a serial list continues with more items and a
        # coordinator ("hair, and eyes"), where a genuine aside end is followed by the sentence
        # resuming ("...of your eye, and by the way that..."). Checked on the text after the match
        # rather than by widening the body, because a body that allowed commas would swallow the
        # coordinate clause after a real aside instead.
        if _LIST_CONTINUES_RE.match(m.string, m.end()):
            return m.group(0)
        remaining -= 1
        return f" ({m.group(1)})"

    return _ASIDE_RE.sub(_swap, text)


def _vary_openers(
    sentences: list[str], rate: float = 0.3, *, conversational: bool = True
) -> list[str]:
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
    openers = list(_OPENERS) if conversational else [
        o for o in _OPENERS if o not in _CONVERSATIONAL_OPENERS
    ]
    context = " ".join(sentences)
    # Openers already spent in this text. Picking independently from an 8-item pool at ~0.3 rate
    # means a long passage reuses one: MEASURED over 60 RAID+HC3 texts, "Looking at this," was the
    # single largest source of rewriter-CREATED repeated phrasing, 7 excess occurrences — more than
    # any other, and this transform exists to VARY openers. Same collision as the synonym map's
    # many-to-one entries (see `spent` in _plain_register). Cleared when the pool is exhausted, so
    # a text with more than 8 varied openers cycles rather than stops varying.
    spent: set[str] = set()

    def _opener(*, opening_the_block: bool = False) -> str:
        fresh = [o for o in openers if o not in spent]
        if not fresh:
            spent.clear()
            fresh = list(openers)
        # Some of these assert a relation to text that has not been written yet. "In short," and
        # "Put simply," announce a compression of what came before, and "Also," adds to it; at the
        # top of a block there is nothing to compress or add to, and the result reads as though a
        # paragraph went missing above it. FOUND on human input at default settings:
        #
        #     In short, my grandmother kept every birthday card anyone ever sent her, in a shoebox
        #
        # — the first sentence of the document. MEASURED over 100 rewrites of 4 documents, 4 open
        # a document this way, and the tell catalogue scores every one of them 0, so nothing
        # downstream sees it. This is the same class as the openers declined above for asserting
        # recency or sequence ("recently", "then", "so"); those were screened out of the pool
        # entirely, and these three only misfire in one position, so they are screened by position.
        #
        # The guard is over-broad by exactly one case: a LATER paragraph opening with "In short,"
        # is legitimate — there is prior discourse — and `apply_per_block` hands the transform a
        # bare string with no block index, so first-of-block is the finest distinction available
        # without threading position through every rewriter. The remaining six openers still cover
        # a block's first sentence, so the transform is never blocked, only steered.
        if opening_the_block:
            fresh = [o for o in fresh if o not in _NEEDS_PRIOR_DISCOURSE] or [
                o for o in openers if o not in _NEEDS_PRIOR_DISCOURSE
            ]
        pick = random.choice(fresh)
        spent.add(pick)
        return pick

    # `rate` is a BUDGET SHARE, not a per-sentence coin flip. Flipping a coin per sentence makes the
    # output share equal to `rate`, and `rate` was derived from intensity with nothing to anchor it
    # to how often humans actually do this. The frequencies above are the anchor and they were
    # already in this function: humans open with these specific markers ~1.4% of the time.
    #
    # MEASURED, share of sentences opening with a marker from this pool (HC3, >=90 words):
    #
    #     human                 13 / 415   3.13%
    #     AI, unrewritten        1 / 368   0.27%
    #     untell output         19 /  52  36.54%      <- 12x human, 135x the input
    #
    # A third of all sentences opening with "Basically," / "Well," / "Now," is a fingerprint in its
    # own right, and this transform is supposed to REMOVE fingerprints. The failure is not the pool
    # — every member was frequency-screened — it is the dose.
    #
    # So spend a budget instead: cap total pool-openers near the human share, and spend what is
    # available on the sentences that actually need it. The job this transform exists for is
    # `repeated_sentence_openers`, so a sentence whose first word repeats another sentence's first
    # word is served before an already-distinct one.
    #
    # WHAT THE CUT COSTS, measured afterwards rather than assumed. The line above used to end "same
    # work, a twelfth of the noise", and that was too clean. Stripping a transition leaves
    # "Overall, The paper ..." as "The paper ...", which CREATES a duplicate opener — the note
    # further down records duplicates rising 18 -> 58 over 60 texts when this transform declined to
    # act. Offsetting that is half its job, and a smaller budget offsets less of it. Over 12 HC3
    # documents through the structural rewriter:
    #
    #     dose            duplicate openers/sentence      tells
    #     0.42 (old)          0.231 -> 0.214  (falls)      98 -> 84
    #     ~0.10 (now)         0.231 -> 0.238  (rises)      98 -> 84
    #
    # So duplicates now rise slightly where they used to fall. The tell catalogue does not move
    # either way — 98 -> 84 on both, 1 of 12 documents worse on both — so nothing downstream sees
    # it, which is exactly why it needed measuring rather than noticing.
    #
    # The trade is still right: 0.024 duplicates per sentence against a pool-opener rate 12x human,
    # which is a fingerprint built entirely out of human-attested words. Recorded because the
    # earlier version of this comment claimed only the benefit.
    #
    # Fractional, like the fronting and parentheses budgets above, and for a reason this transform
    # specifically needs. `round()` collapses the rate into an integer, and the style knobs are
    # MULTIPLIERS on it — `blunt` and `minimalist` are 1.2x the neutral opener rate. On a paragraph
    # of this length 0.30 and 0.36 both round to the same budget, so those two styles produced
    # byte-identical output to no-style at every seed and
    # `test_the_previously_inert_styles_now_bite` failed on both: the flag could no longer change
    # the output at all, which is the exact regression that test was written for.
    #
    # Carrying the remainder as a probability keeps the dose right on average — the whole point of
    # the budget — while letting a 1.2x rate still show up somewhere in a 60-seed sweep.
    marked = sum(1 for s in sentences if _ANY_LEADING_MARKER_RE.match(s))
    raw = rate * len(sentences) - marked
    budget = max(0, int(raw))
    if random.random() < raw - budget:
        budget += 1

    first_words = [(s.split()[0].lower().strip(".,;:!?") if s.split() else "") for s in sentences]
    counts: dict[str, int] = {}
    for w in first_words:
        counts[w] = counts.get(w, 0) + 1
    # Duplicate-opening sentences first, then the rest; `random.random()` keeps the choice within
    # each group non-deterministic so the best-of-N sweep still explores different drafts.
    order = sorted(
        range(len(sentences)),
        key=lambda i: (0 if counts.get(first_words[i], 0) > 1 else 1, random.random()),
    )
    chosen = set(order[:budget])

    out: list[str] = []
    for _i, s in enumerate(sentences):
        # A sentence that ALREADY opens with a discourse marker gets no second one. Stacking them
        # produced "Put simply, also, wine is often shipped at specific temperatures" — found by
        # scanning 30 real HC3 rewrites for mechanical breakage. `_LEADING_MARKER_RE` exists for
        # exactly this and was consulted only by the clause-merge path.
        if _i in chosen and not _ANY_LEADING_MARKER_RE.match(s):
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
                    s = f"{_opener(opening_the_block=_i == 0)} {s[0].lower() + s[1:]}"
                elif _proper_noun_evidence(first_word, context):
                    s = f"{_opener(opening_the_block=_i == 0)} {s}"
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


# NOT "which". _split_one drops the conjunction it splits on, which is right for a coordinator
# ("... and traced the fault" -> "Traced the fault") and fatal for a relative pronoun: removing it
# leaves the clause without its subject, so "..., which can capture local information" became the
# fragment "Can capture local information ...". Measured over 60 RAID+HC3 texts, that was the
# second-most-common fragment shape in rewritten output after the comma-split one.
_CONJ = ("and", "but", "because", "so", "while", "although", "though", "since")


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


def _words_until_next_comma(words: list[str], index: int) -> int:
    """How many words follow ``index`` before the next comma (or the end)?

    Distinguishes a list coordinator from a clause coordinator without a parser: "and Q3, but ..."
    gives 1, "but the fourth quarter fell short of the target" gives 8.
    """
    n = 0
    for w in words[index:]:
        n += 1
        if w.endswith(","):
            break
    return n


def _inside_quotes(words: list[str], index: int) -> bool:
    """Is a break before ``words[index]`` inside a quotation?

    An odd number of double quotes to the left puts the split point between an opening quote and
    its close, so promoting the right half to a sentence leaves BOTH halves unbalanced:
        He said "the result is robust.   /   It replicates", which the reviewers accepted.
    """
    return " ".join(words[:index]).count('"') % 2 == 1


def _split_one(s: str) -> list[str] | None:
    """Split one long sentence into two at a comma or coordinating conjunction near the midpoint.
    Redistributes words only — no content added. Returns [first, second] or None if no clean split."""
    words = s.split()
    if len(words) < 12:
        return None
    # A SERIAL LIST is not a clause boundary, and its commas outnumber any real one:
    #   "The authors, Smith, Jones, and Patel, reported that ..."
    #     -> "The authors, Smith, Jones, and Patel." + the subjectless "Reported that ..."
    #   "Revenue rose in Q1, Q2, and Q3, but ..."
    #     -> "Revenue rose in Q1." + "Q2, and Q3, but ..."
    # The conjunction branch below is unaffected and can still find a real boundary in such a
    # sentence.
    list_like = _looks_like_a_serial_list(words)
    mid = len(words) // 2
    best: int | None = None
    for off in range(mid):  # nearest comma to the midpoint
        for pos in (mid + off, mid - off):
            # The conjunction branch below has always checked that the right side can open a
            # clause; this one never did, and "any comma near the midpoint" is mostly not a clause
            # boundary. It is the source of every "Including autonomous driving, medical imaging,
            # and robotics." in rewritten output — the most common fragment measured over 60
            # RAID+HC3 texts. `_split_long_sentences` had the identical hole and was fixed first;
            # this copy kept producing them, which is why the fragment count did not move.
            if (
                0 < pos < len(words) - 1
                and words[pos].endswith(",")
                and not list_like
                and not _inside_quotes(words, pos + 1)
                and not _cannot_start_a_sentence(
                    " ".join(words[pos + 1:]), " ".join(words[:pos + 1])
                )
                # The same question asked of the other half. The guard above rejects a right side
                # that cannot open a clause; this rejects a left side that cannot close one.
                and not _orphans_a_subordinate_clause(" ".join(words[:pos + 1]))
            ):
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
                    # A LIST's own coordinator is not a clause boundary: "The authors, Smith,
                    # Jones, and Patel, reported ..." split on that "and". But `list_like` alone
                    # is too blunt here — "Revenue rose in Q1, Q2, and Q3, but the fourth quarter
                    # fell short." contains a list AND a real boundary at "but", and blanket-
                    # rejecting cost that split. What separates them is what FOLLOWS: a list
                    # coordinator is followed by one short item before the next comma, a clause
                    # coordinator by a clause.
                    and _words_until_next_comma(words, pos + 1) >= _MIN_SPLIT_SIDE
                    and not _inside_quotes(words, pos + 1)
                    and _starts_a_clause(words[pos + 1])
                ):
                    best = pos
                    break
            if best is not None:
                break
    if best is None:
        return None
    # Both sides must be substantial enough to be a sentence. The comma scan walks outward from
    # the midpoint, so with a single early comma it happily picks position 1 — and _vary_openers
    # puts one there. "Of course, the model works well ..." split into "Of course." plus the rest,
    # i.e. this pass fragmenting the output of the pass before it.
    # In CONTENT words: "Put simply, in this paper" is five tokens and three of them are a sentence,
    # so the raw count cleared this rule and produced "Put simply, in this paper." — the same shape
    # as the "Of course." case above, one marker further along.
    if _content_word_count(words[:best]) < _MIN_SPLIT_SIDE or len(words) - best < _MIN_SPLIT_SIDE:
        return None
    first_words = words[:best]
    # A coordinator at the RIGHT edge of the first half is left dangling against the full stop:
    # "... in combination with other techniques, but. Salt is often the most effective option."
    # _split_long_sentences has carried a guard for this shape since it was found in real HC3
    # output; this copy of the split never got one, which is the third time the two have diverged
    # (the comma clause-check and the minimum side length were the other two). The coordinator
    # joined two clauses that are now separate sentences, so it has nothing left to coordinate.
    while first_words and first_words[-1].rstrip(",").lower() in _SPLIT_CONJUNCTIONS:
        first_words = first_words[:-1]
    if len(first_words) < _MIN_SPLIT_SIDE:
        return None
    first = " ".join(first_words).rstrip(",")
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
    # Same length budget as _merge_sentences. This copy runs AFTER it, inside the burstiness climb,
    # and was unconstrained — so a pair the main merge had just declined as too long could be
    # merged here anyway, one pass later, for a CV gain.
    lengths = [len(s.split()) for s in sents if s.strip()]
    if lengths:
        mean = sum(lengths) / len(lengths)
        cap = max(mean * _MEAN_LENGTH_BUDGET * 1.5, _ALWAYS_MERGEABLE_WORDS)
        if len(sents[j].split()) + len(sents[j + 1].split()) > cap:
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

    ``target_cv`` is register-dependent and comes from the style profile. MEASURED coefficient of
    variation of sentence length over 200 pairs per corpus:

        HC3  (forum Q&A)        human 0.480 (median 0.465)   ai 0.301
        RAID (paper abstracts)  human 0.352 (median 0.330)   ai 0.263

    The default 0.45 tracks conversational human prose closely and overshoots academic human prose
    by 0.10 — real abstracts are more uniform in sentence length than forum answers, and driving
    them past that is a deviation in its own right. The formal profiles therefore aim lower. Note
    the AI column is below human in BOTH registers, so the direction of the transform is right
    everywhere; only the destination was register-blind.

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
    # Sentence-length CV to aim at. 0.45 is the previous fixed value and tracks the measured
    # conversational human 0.480. Only "academic" lowers it, to the measured academic 0.352 —
    # the evidence is RAID paper abstracts, so it is not extended to professional/technical
    # (formal but unmeasured) and certainly not to journalistic, whose whole register is short
    # punchy sentences against long ones, i.e. the opposite direction.
    "burstiness": 0.45,
    # Markers _strip_transitions must leave alone. Empty for every style but "academic" —
    # see _ACADEMIC_HUMAN_TRANSITIONS for the per-corpus measurement that separates them.
    "keep_transitions": frozenset(),
    # May `_vary_openers` reach for the conversational end of its pool? The formal styles already
    # turn contractions off and hold back the plain-word swap, on the stated ground that
    # "utilize" -> "use" is right for casual prose and wrong for a paper. The opener pool is the
    # same argument and was not covered by it: `--style academic` still produced
    # "Basically, the study examined soil carbon at eleven sites". MEASURED over 60 rewrites of one
    # paper abstract, openers emitted per style BEFORE this knob existed:
    #
    #     none          Actually 2  Also 1  In short 2  In practice 3  Basically 1  Of course 2
    #     academic      Actually 2          In practice 2  Basically 1  Of course 2
    #     technical     Actually 1          In practice 1               Of course 2
    #     professional  Actually 2  In short 1  In practice 2  Basically 1  Of course 2
    #
    # The rate falls with the profile — that dial worked — but the VOCABULARY never changed.
    "conversational_openers": True,
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
                      "keep_transitions": _ACADEMIC_HUMAN_TRANSITIONS, "burstiness": 0.35,
                      "conversational_openers": False},
    "professional":  {"contractions": False, "register": 0.4,  "sentences": 1.0, "openers": 0.6,
                      "conversational_openers": False},
    "technical":     {"contractions": False, "register": 0.3,  "sentences": 1.2, "openers": 0.3,
                      "conversational_openers": False},
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

    # 0b. And the matching sign-off at the other end. Beside the opener strip because it is the same
    # move — deleting scaffolding rather than rewriting content — and because `meta_closer` was one
    # of three tell categories the catalogue counted and nothing could act on.
    text = _strip_meta_closers(text)

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

    # 5d. Parenthesise an aside that is already comma-bounded. Punctuation only — no word is added,
    # removed or reordered — and humans use parentheses 2-4x as often as AI in both corpora.
    text = _parenthesise_asides(text)

    # 6. Semicolon → period (semiconductors are a tell)
    text = _semicolons_to_periods(text)

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

        # Reorder BEFORE merging and splitting, so a fronted clause is then eligible for both.
        # This is the only transform in the file that changes the ORDER information arrives in;
        # every other one is a local edit, and order is what a curvature detector reads over a
        # long span. MEASURED in isolation over 14 RAID texts, fronting every eligible sentence:
        # fast_detectgpt -0.0298, perplexity_burstiness -0.0263, roberta_openai -0.0221, no
        # detector worse, at 0.9993 similarity — it adds no words, it moves them.
        sents = _front_subordinate_clauses(sents, rate=1.0)

        # Drop restatements BEFORE merging: a merge would fuse a restatement onto its own source
        # and preserve the duplication inside one longer sentence instead of removing it.
        #
        # SCOPE PROBLEM, measured and left in place deliberately. `_rewrite_prose` handles one
        # BLOCK of prose, so this sees a paragraph, while the restatement it targets is
        # document-scale — an opening states X, the body restates X, the close restates it again.
        # Instrumented over 40 RAID documents: 171 calls, mean 2.5 sentences per call, and 156 of
        # them return immediately on this function's own `len(sentences) < 4` guard. It fires on 0
        # of 80 documents. The transform aimed at the strongest tell in the catalogue is inert in
        # the shipped path.
        #
        # That matters because `repeated_phrasing` is where all the residual lives. Every other
        # category is essentially solved — cliche and ai_vocab 100% removed, formulaic_transition
        # 93-97%.
        #
        # MEASURE THE RATE, NOT THE CATEGORY COUNT. `_repeated_trigrams` ends in
        # `return repeats if (repeats / len(words) * 100) >= 5.0 else 0`, so the category is a
        # high-precision FLAG for heavy repetition, not a rate: 77 of 80 human RAID documents
        # report exactly 0, which is what earns it precision 0.925/0.942 and also makes a ratio of
        # its means meaningless. Comparing those means gives "53x", and an earlier version of this
        # note quoted 15-33x from the same mistake.
        #
        # On the continuous share of tokens in a repeated 3-gram:
        #
        #                 human     ai    ai after rewrite   gap closed
        #     HC3          1.31    7.32        6.92              7%
        #     RAID         1.77   10.54        9.03             17%
        #
        # So the real figure is about 6x, not 33x — still the largest untreated gap in the
        # catalogue, and the "barely closed" part is unchanged.
        #
        # What the repetition IS, which decides what could fix it. Only 1% of repeated trigrams are
        # all function words, so this is real content. Splitting the types by syntax:
        #
        #     RAID   54% noun phrases ("medical image segmentation" x57, "the proposed method")
        #            20% contain a verb (clause restatement)
        #     HC3    45% contain a verb, 32% noun phrases
        #
        # and both halves of the gap are real: noun-phrase repeats run 4.7x human on RAID, clause
        # repeats 8.1x. The noun-phrase half is not paraphraseable — a paper cannot stop saying
        # "medical image segmentation" — but humans writing the same document reach for a shorter
        # reference ("the method", "it") where the model restates the full phrase. That is an
        # anaphora transform, and it is a different and much cheaper thing than paraphrasing a
        # sentence.
        #
        # PROTOTYPED AND NOT SHIPPED, with the numbers so the next attempt starts from them.
        # Replacing later mentions of a repeated 3+ word noun chunk with "the <head noun>" — which
        # keeps the referent explicit, unlike a pronoun, so the reference cannot go ambiguous:
        #
        #     RAID   18 of 40 docs touched, 95 mentions shortened, 9.14 -> 8.24 (10% less
        #            repetition), meaning gate passed 17/18
        #     HC3     4 of 40 docs touched, 12 mentions shortened, 6.42 -> 6.20 (3%), gate 4/4
        #
        # Safe and real, but modest, and corpus-dependent for a reason: HC3's repetition is 45%
        # clause restatement against 32% noun phrases, so there is little for it to shorten. The
        # crude upper bound — pronominalising the top three repeated trigrams outright — is 25% on
        # RAID and 42% on HC3, so most of the available reduction is NOT in the safe transform.
        #
        # The blocking objection is not the size, it is the dependency. Identifying a noun chunk
        # needs a parser, and this module is stdlib + `re` on purpose: it is the free path that runs
        # with no model download. Adding spaCy to it to buy 3-10% less repetition on one of two
        # corpora is the wrong trade. If this is built, it belongs behind the same optional-extra
        # guard as the neural rewriters, and the one gate failure to look at first is a definition
        # site — shortening a term in the sentence that introduces it ("called deep active contours
        # using locally controlled distance vector flow") is wrong even when the rule is right.
        #
        # Widening the scope is NOT the fix, which is why it is not done here. Running
        # `_drop_restatements` over the whole document instead of the block:
        #
        #     RAID   9.684 -> 8.163   drops 3.5% of AI sentences, 0.0% of human   <- clean
        #     HC3    6.138 -> 5.779   drops 0.9% of AI sentences, 0.9% of human   <- no better
        #                                                                            than chance
        #
        # On RAID that is a real gain with no false drops; on HC3 it deletes human sentences at
        # exactly the rate it deletes AI ones. And even the good case closes about a sixth of a
        # 33x gap. Deletion is the wrong instrument: the duplication is spread across sentences
        # that each carry some content, so removing whole sentences cannot reach most of it. What
        # would is rewriting a restating sentence rather than dropping it, which needs a
        # paraphraser and its own meaning check — a different piece of work, sized here rather
        # than guessed at.
        sents = _drop_restatements(sents)

        merge_rate = min(0.7, intensity * 0.6)
        sents = _merge_sentences(sents, rate=merge_rate)

        split_rate = min(0.9, intensity * 0.5 * profile["sentences"])
        sents = _split_long_sentences(sents, rate=split_rate)

        # Target SHARE of sentences carrying a leading marker, not a per-sentence probability.
        # `intensity * 0.6` gave 0.42 at the default intensity, against a measured human share of
        # 3.13% — see `_vary_openers`. The ceiling is 0.9 in name only when the floor of the
        # comparison is 0.03. Scaled so the default lands a little above human rather than 12x it,
        # leaving headroom at intensity 1.0 for the duplicate-opener work the transform exists for.
        open_rate = min(0.20, intensity * 0.10 * profile["openers"])
        sents = _vary_openers(
        sents, rate=open_rate, conversational=profile["conversational_openers"]
    )

        # 8. Burstiness targeting — drive sentence-length variance toward the human range. The single
        # most reliable stylometric differentiator; only redistributes existing words (meaning-safe).
        sents = _target_burstiness(sents, target_cv=profile["burstiness"])

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
