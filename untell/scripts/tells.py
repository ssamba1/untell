"""Mechanical AI-tells scorer — count the machine-writing markers in a passage.

The detector ensemble answers "does a *classifier* think this is AI"; this answers a different,
complementary question: **does it read like AI to a human** — how many of the catalogued AI tells
(``untell/references/ai-tells.md``) actually appear in the text. It is a transparent, deterministic,
stdlib-only count (em-dashes, the "delve" vocabulary cluster, formulaic transitions, reader-steering
openers, negated contrast, participial trailers, vague attribution, clichés, sycophancy, chatbot
artifacts, inflated copula, hedge-stacking, false-range breadth, rule-of-three staccato, markdown
artifacts, semicolon crutch) plus a burstiness read.

Why it matters: the local detectors *anti-correlate* with human-ness on some text (a plainer, more
human rewrite can score *higher* on the proxy — measured, see ``docs/free-ceiling-measured.md``). A
tell count does not have that failure mode: fewer catalogued tells is unambiguously closer to how a
careful human writes. That makes it the right yardstick for "is this output more natural" when
comparing humanizers — independent of any detector.

    untell-tells "Furthermore, we leverage robust, seamless solutions."
    untell-tells --file draft.txt --json
    echo "text" | untell-tells

API: ``score_tells(text) -> dict`` with ``tells``, ``tells_per_100w``, ``by_category`` and
``burstiness_cv`` (coefficient of variation of sentence lengths; low = uniform = a tell).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

logger = logging.getLogger(__name__)

# --- how much each category is worth as EVIDENCE -----------------------------------------------
# Not every tell is equally incriminating. "As an AI language model" is near-proof; an em-dash is
# a punctuation preference. The catalogue counted them the same, so a text with three weak style
# markers scored like one with three chatbot artifacts.
#
# MEASURED on 400 real HC3 pairs — precision = P(the text is AI | this category fires at all):
#
#     sycophancy            human   0  ai   2   1.00
#     meta_closer           human   0  ai  26   1.00
#     filler_phrase         human   0  ai   1   1.00
#     cliche                human   7  ai  64   0.90
#     formulaic_transition  human  20  ai 132   0.87
#     vague_attribution     human   1  ai   6   0.86
#     hedge_stacking        human  12  ai  18   0.60
#     negated_contrast      human   5  ai   7   0.58
#     ai_vocab              human  17  ai  21   0.55   <- the flagship cluster, near chance
#     false_range           human   3  ai   2   0.40
#     em_dash               human   6  ai   3   0.33
#     inflated_copula       human   1  ai   0   0.00
#     markdown_artifact     human   2  ai   0   0.00
#     rule_of_three         human   3  ai   0   0.00
#     semicolon_crutch      human   7  ai   0   0.00
#
# Two findings worth stating rather than burying. The "delve / leverage / tapestry" vocabulary
# cluster this catalogue is best known for is a **coin flip** on real text. And five categories
# fire MORE on human writing than on AI: dropping them raises separation from +0.307 to +0.332 and
# AUROC from 0.7047 to 0.7177.
#
# REPLICATED on a SECOND corpus, 2026-08-07 — 150 RAID pairs (liamdugan/raid: multi-domain,
# multi-generator, exact human-vs-machine pairing on source_id, and far more recent than HC3):
#
#     participial_trailer   human   1  ai  24   0.96   <- never fired on HC3 AT ALL
#     cliche                human   2  ai  27   0.93   (HC3 0.90 — holds)
#     formulaic_transition  human  43  ai  65   0.60   (HC3 0.87 — much weaker here)
#     ai_vocab              human  92  ai 131   0.59   (HC3 0.55 — weak on BOTH)
#     em_dash               human   2  ai   0   0.00   (HC3 0.33 — wrong way on both)
#
# Three things this settles that one corpus could not:
#
#  1. **ai_vocab really is a coin flip.** 0.55 on HC3 and 0.59 on RAID. Two corpora, two eras, two
#     generator families, same answer. It is not an artefact of 2022 ChatGPT.
#  2. **Never-firing is not useless.** `participial_trailer` scored nothing on HC3 and is the
#     STRONGEST category on RAID at 0.96. Dropping the silent categories, which the HC3 numbers
#     alone would have justified, would have deleted the best pattern in the catalogue.
#  3. **Some of this measures REGISTER, not authorship.** `formulaic_transition` fires on 43 of 150
#     human RAID texts — those are academic abstracts, where "Furthermore" is native. Overall
#     separation is worse on RAID than HC3 (AUROC 0.638 vs 0.705, tells/100w gap +0.227 vs +0.307)
#     precisely because RAID's human half is formal writing. A catalogue tuned on forum answers
#     partly learns "formal" rather than "machine".
#
# They are NOT dropped or reweighted. Ten categories never fire on HC3 at all —
# chatbot_artifact, cutoff_disclaimer, aphorism, notability_padding and the formatting ones — and
# those are precisely the MODERN tells: HC3 is 2022-era ChatGPT and predates them. Refitting to it
# would delete the patterns aimed at current models to score better on a dated benchmark, which is
# the same trap `humanness.py` documents declining. What ships instead is the split below, so a
# caller can see whether a score rests on strong evidence or on style preferences.
#
# "unmeasured" means exactly that: no evidence either way from this corpus, not "weak".
_EVIDENCE: dict[str, str] = {
    "sycophancy": "strong", "meta_closer": "strong", "filler_phrase": "strong",
    "cliche": "strong", "chatbot_artifact": "strong", "cutoff_disclaimer": "strong",
    "formulaic_transition": "moderate", "vague_attribution": "moderate",
    "hedge_stacking": "weak", "negated_contrast": "weak", "ai_vocab": "weak",
    "false_range": "weak", "em_dash": "weak", "inflated_copula": "weak",
    "markdown_artifact": "weak", "rule_of_three": "weak", "semicolon_crutch": "weak",
    # Added 2026-08-07 and immediately the strongest entries here — AUROC 0.965/0.921 (RAID/HC3)
    # for repeated_phrasing and 0.901/0.606 for repeated_sentence_openers, against 0.638-0.705 for
    # the whole tells/100w metric. Both replicate across corpora, which is why they are "strong"
    # where ai_vocab, measured twice at ~0.57, is "weak".
    "repeated_phrasing": "strong", "repeated_sentence_openers": "moderate",
}

_WORD = re.compile(r"[A-Za-z0-9']+")
# Sentence splitting lives in untell.text_split — see the note there. A naive split made "Dr." a
# one-word sentence, which feeds straight into the burstiness coefficient of variation below and so
# into the loop's tie-break between candidate rewrites.

# High-frequency AI vocabulary (from ai-tells.md §1). Whole-word, case-insensitive.
_AI_VOCAB = [
    "ascertain", "relentless",  # documented in ai-tells.md, absent here
    "delve", "leverage", "utilize", "utilizing", "robust", "seamless", "seamlessly", "tapestry",
    "testament", "realm", "landscape", "underscore", "underscores", "underscoring", "pivotal",
    "crucial", "vital", "foster", "fostering", "garner", "garnered", "bolster", "elevate", "embark",
    "harness", "harnessing", "unlock", "unleash", "spearhead", "paramount", "plethora", "myriad",
    "multifaceted", "nuanced", "intricate", "intricacies", "meticulous", "meticulously",
    "comprehensive", "vibrant", "bustling", "noteworthy", "groundbreaking", "transformative",
    "innovative", "boasts", "nestled", "profound", "holistic", "actionable", "impactful",
    "streamline", "empower", "empowering", "revolutionize", "resonate", "encompass", "paradigm",
    "cornerstone", "burgeoning", "quintessential", "overarching", "synergy", "endeavor", "commence",
    "illuminate", "cultivate", "catalyze", "galvanize", "augment", "elucidate", "interplay",
    "underpin", "compelling", "unprecedented", "exceptional", "remarkable", "sophisticated",
    "invaluable", "unwavering", "scalable", "bespoke",
    # second cluster (ai-tells.md §1/§2 promo set)
    "showcasing", "showcase", "reimagine", "reimagining", "world-class", "cutting-edge",
    "state-of-the-art", "best-in-class", "top-tier", "next-level", "turnkey", "supercharge",
    "unparalleled", "trailblazing",
    # third cluster (2024-2026 high-frequency tells)
    "navigate", "navigating", "grapple", "beacon", "trajectory", "salient", "granular",
    "orchestrate", "orchestrating", "curate", "curated", "amplify", "ecosystem", "dichotomy",
    "juxtapose", "trove", "veritable", "aforementioned", "delves", "delving", "penchant",
    "adept", "prowess", "hallmark", "poised",
]
_AI_VOCAB_RE = re.compile(r"\b(" + "|".join(_AI_VOCAB) + r")\b", re.IGNORECASE)

# Formulaic transitions (ai-tells.md §3) — counted heavily when they OPEN a sentence. "Notably" and
# "Importantly" live in _STEER_RE instead, and "In conclusion"/"In summary" in _CLICHES, so they are
# NOT repeated here (a single phrase must count in exactly one category, never two).
_TRANSITIONS = [
    "Moreover", "Furthermore", "Additionally", "Overall", "Ultimately",
    "Thus", "Therefore", "Accordingly", "Hence", "Subsequently", "Consequently", "Nevertheless",
    "Nonetheless", "Similarly", "Alternatively", "Indeed", "Essentially", "Arguably",
    "In essence", "That said", "On the other hand",
]
_TRANSITION_OPENER_RE = re.compile(
    r"(?:^|(?<=[.!?]\s))\s*(" + "|".join(_TRANSITIONS) + r")\b", re.IGNORECASE | re.MULTILINE
)

# Reader-steering adverb openers (§20).
_STEER_RE = re.compile(
    r"(?:^|(?<=[.!?]\s))\s*(Interestingly|Notably|Importantly|Surprisingly|Crucially|Remarkably),",
    re.IGNORECASE | re.MULTILINE,
)

# Negated contrast (§4).
#
# Two gaps measured on the tell probe set, both letting the *same* construction through:
#   - the first alternative required a CONTRACTION ("it's not X, it's Y"), so the uncontracted
#     "It is not just a tool, it is a philosophy" — which models write at least as often — matched
#     nothing at all;
#   - the "not just" alternative required a literal "but", so the far more common punctuated form
#     ("not just a tool, it is a philosophy" / "not merely X — it is Y") was missed.
# The subject is also not always "it": "That's not a bug, that's a feature" is the identical move.
_SUBJ = r"(?:it|that|this)(?:'?s|\s+is|\s+was)"
_NEGATED_CONTRAST_RE = re.compile(
    rf"\b(?:{_SUBJ}\s+not\s+(?:just|merely|simply|only|about)?\s*\w+[^.;!?]{{0,60}}"
    rf"[,;—–-]\s*(?:but\s+)?{_SUBJ}\s+"
    r"|not only\b[^.]{0,60}\bbut(?:\s+also)?\b"
    rf"|(?:isn'?t|aren'?t|is not|are not)\s+about\b[^.;]{{0,50}}[;,]?\s*{_SUBJ}\s+about\b"
    r"|not\s+(?:just|merely|simply)\b[^.;!?]{0,50}[,;—–]\s*(?:but\b|it|that|this)"
    r"|not\s+(?:just|merely|simply)\b[^.]{0,40}\bbut\b)",
    re.IGNORECASE,
)

# Participial-phrase trailers (§6): a clause ending ", ...ing ..." near sentence end.
_PARTICIPIAL_TRAILER_RE = re.compile(
    r",\s+(?:under(?:scoring|lining)|marking|reflecting|highlighting|showcasing|emphasizing|"
    r"signaling|cementing|solidifying|paving|ensuring|demonstrating)\b[^.!?]*[.!?]",
    re.IGNORECASE,
)

# Vague attribution (§7).
#
# The old list was nine literal bigrams, so the category shipped while missing most of its own
# construction: "reports suggest", "analysts note", "critics argue", "industry reports indicate"
# all scored clean. The shape is what makes it a tell — an unnamed plural authority plus a
# reporting verb — so it is matched as a shape. The subject list stays closed (no bare "people
# say") to keep it off ordinary prose that names its source: "Chen's studies show" is preceded by
# a possessive, and "the 2019 survey shows" is singular with a determiner.
_VAGUE_ATTR_RE = re.compile(
    r"\b(?<!'s )(?:studies|research|reports|surveys|analysts|observers|critics|experts|"
    r"scientists|researchers|sources)\s+"
    r"(?:show|shows|suggest|suggests|indicate|indicates|say|says|note|notes|argue|argues|"
    r"believe|believes|agree|agrees|point to|have shown|have found)\b"
    r"|\b(?:it is (?:widely |often |generally )?(?:believed|said|understood|accepted)|"
    r"many (?:believe|argue|say)|some (?:argue|say|believe)|"
    r"(?:studies|research) (?:has|have) shown)\b",
    re.IGNORECASE,
)

# --- patterns measured as MISSING against the public catalogue -------------------------------
# Coverage was 17 of the 33 patterns in blader/humanizer's list (itself derived from Wikipedia's
# "Signs of AI writing"). These close the prose half of that gap. Each is deliberately narrow: a
# tell catalogue that fires on ordinary human writing is worse than one with holes, because the
# loop's tie-break prefers fewer tells and would start rewriting away normal prose.

# Filler that adds words without meaning. NOT "in order to" alone — that is ordinary English and
# appears constantly in careful human writing; only the padded variants are listed.
_FILLER_RE = re.compile(
    r"\b(?:due to the fact that|at this point in time|in the event that|for the purpose of|"
    r"in spite of the fact that|it is worth mentioning that|needless to say|"
    r"as a matter of fact|when all is said and done)\b",
    re.IGNORECASE,
)

# Aphorism formulas — "X is the new Y", "the X of Y" equivalences that sound profound and say little.
_APHORISM_RE = re.compile(
    r"\b(?:is|are|becomes?|remains?)\s+the\s+new\s+\w+"
    r"|\bis\s+the\s+\w+\s+of\s+(?:the\s+)?\w+(?:\s+(?:web|internet|world|age|era))\b"
    r"|\bbecomes?\s+a\s+trap\b",
    re.IGNORECASE,
)

# Theatrical rhetorical openers used as standalone hooks.
_RHETORICAL_OPENER_RE = re.compile(
    r"(?:^|(?<=[.!?]\s))\s*(?:Honestly\?|Look,|Here'?s the thing|The thing is,|Truth is,)",
    re.IGNORECASE | re.MULTILINE,
)

# Knowledge-cutoff disclaimers and speculative gap-filling — unmistakably assistant output.
_CUTOFF_RE = re.compile(
    r"\b(?:as of my (?:last|latest)\s+(?:training|update|knowledge)|"
    r"up to my last training|my training data|as of my knowledge cutoff|"
    r"maintains a low profile|i do not have access to real-?time)\b",
    re.IGNORECASE,
)

# "Challenges and future prospects" outline sections — the shape of a generated article.
_CHALLENGES_RE = re.compile(
    r"\b(?:faces? (?:several|numerous|a number of|many) challenges|"
    r"challenges and (?:legacy|opportunities|future)|future (?:outlook|prospects|directions))\b",
    re.IGNORECASE,
)

# Notability / media-coverage padding, straight out of generated encyclopedia entries.
_NOTABILITY_RE = re.compile(
    r"\b(?:independent coverage|(?:local|regional|national|international) media outlets|"
    r"has been (?:widely )?(?:covered|featured) (?:in|by)|written by a leading expert)\b",
    re.IGNORECASE,
)

# Banned clichés / phrases (§2) — openers, signposting, action, closings, promo.
_CLICHES = [
    r"in today'?s (?:fast-paced|digital|modern|ever-changing) world", r"in the ever-evolving \w+ of",
    r"in an era where", r"as technology continues to evolve", r"when it comes to", r"at its core",
    r"at the end of the day", r"in the realm of", r"this is where \w+ comes in",
    # "it'?s" matches "it's" and "its" but NOT "it is" — so the single most common signpost in AI
    # prose, "It is important to note that ...", scored as perfectly clean. Curly apostrophes are
    # matched too: AI output is full of them, and "it’s" missed the straight-quote-only class.
    r"it(?:['’]?s| is) (?:important|worth|essential|necessary) (?:to note|noting)",
    r"it should be noted", r"it cannot be overstated",
    r"one of the most important", r"plays? a (?:crucial|pivotal|vital) role",
    r"stands? as a testament to", r"underscores? the importance of",
    r"reflects? a broader (?:trend|shift)", r"marks? a significant shift", r"let'?s dive in",
    r"dive into", r"deep dive", r"shed light on", r"pave[sd]? the way",
    r"navigate the complexities of", r"embark on a journey", r"explore the intricacies of",
    r"in conclusion", r"in summary", r"to summarize", r"the future looks bright",
    r"only time will tell", r"one thing is certain", r"as we move forward",
    r"despite (?:the )?challenges,? \w+ continues to thrive", r"vibrant hub", r"thriving ecosystem",
    r"rich tapestry of", r"game-?changer", r"game-?changing",
    # 2024-2026 additions — corporate/AI cliché set
    r"in the age of", r"in the world of", r"it'?s no secret that", r"the bottom line is",
    r"the possibilities are endless", r"unlock the (?:potential|power) of", r"harness the power of",
    r"take (?:it|things|your \w+) to the next level", r"a double-edged sword", r"the tip of the iceberg",
    r"paradigm shift", r"sea change", r"at the forefront of", r"push the boundaries",
    r"break new ground", r"move the needle", r"low-hanging fruit", r"circle back",
    r"when we consider", r"look no further", r"the key takeaway",
    # Documented in ai-tells.md but never implemented — found by diffing the reference's own
    # quoted examples against what score_tells actually detects. Each was verified uncaught first.
    r"rich cultural heritage",                      # promo register (§ "Promo")
    r"the journey doesn'?t end here",               # meta-closer
    r"here'?s the kicker",                          # fake-suspense opener
    r"picture this",                                # fake-personal anecdote (§13 list)
    r"let'?s unpack", r"unpack (?:what|this|how|why)",  # action cliché; bare "unpack" is literal
    r"unravel the (?:complexit|myster|intricac)\w*",   # same — "unravel the boxes" is not a tell
    r"represents a broader (?:trend|shift)",        # sibling of the implemented "reflects a broader"
    r"watershed moment",                            # significance inflation (§19)
    r"landmark (?:achievement|moment|decision|ruling)",  # not "landmark building", which is literal
]
_CLICHE_RE = re.compile(r"\b(" + "|".join(_CLICHES) + r")\b", re.IGNORECASE)

# Sycophancy / preamble + closing meta + chatbot artifacts (§9, §10, §14).
_SYCOPHANCY_RE = re.compile(
    r"(?:^|(?<=[.!?]\s)|(?<=\n))\s*(Certainly!|Absolutely!|Great question!|"
    r"Sure,? here'?s|Let me (?:break this down|walk you through)|You'?re absolutely right)",
    re.IGNORECASE | re.MULTILINE,
)
_META_CLOSER_RE = re.compile(
    r"\b(I hope this helps|Let me know if|Feel free to reach out|Is there anything else|"
    r"In this article,? we(?:'ll| will) explore|Here'?s a breakdown)\b",
    re.IGNORECASE,
)
_ARTIFACT_RE = re.compile(
    r"(citeturn|oai_citation|utm_source=chatgpt\.com|\[INSERT[^\]]*\]|As an AI language model)",
    re.IGNORECASE,
)

# Inflated copula (§15) — "serves as", "boasts" etc. used for plain is/has.
_INFLATED_COPULA_RE = re.compile(r"\b(serves as|boasts|epitomizes|exemplifies)\b", re.IGNORECASE)

# Hedge stacking (§4) — modal + vague adverb piled together ("could potentially", "may eventually").
_HEDGE_STACK_RE = re.compile(
    r"\b(?:could|can|may|might|would|will)\s+(?:potentially|eventually|ultimately|possibly|"
    r"conceivably|arguably|likely|perhaps)\b",
    re.IGNORECASE,
)

# False-range / unearned breadth (§17) — "whether you're a X or a Y", "from X to Y" sweeping scope.
_FALSE_RANGE_RE = re.compile(
    r"\bwhether you'?re\s+(?:an?\s+)?\w+[^.!?]{0,40}\bor\s+(?:an?\s+)?\w+"
    r"|\bfrom\s+(?:ancient|the everyday|the mundane|individual|small|humble)\b[^.!?]{0,50}\bto\s+the\b"
    # The generic sweep, which is the form that actually appears: "everything from X to Y",
    # "from startups to enterprises". The list above only caught six hand-picked openers, so the
    # category shipped while missing its own headline construction. Requires a scope word
    # (everything/anything/from) so ordinary ranges ("from Monday to Friday") do not match.
    r"|\b(?:everything|anything|all)\s+from\s+\w+[^.!?]{0,45}?\s+to\s+\w+"
    r"|\bfrom\s+\w+s\s+to\s+\w+s\b",
    re.IGNORECASE,
)

# Distinctly-AI markdown artifacts (§7/§12) — NOT plain headings/bullets (those have honest uses), only
# the structure prose almost never adds itself: TL;DR / Key Takeaways blocks and emoji section headers.
_MARKDOWN_ARTIFACT_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:key takeaways?|key points?|tl;?dr|in a nutshell)\b"
    r"|^#{1,6}\s.*[\U0001F300-\U0001FAFF✅✨]",  # TL;DR/Key-Takeaways blocks, or emoji headers
    re.MULTILINE | re.IGNORECASE,
)


# A corpus that writes " , " or " . " has spaces around ALL punctuation, so its hyphens carry no
# information about dash usage. Two occurrences are required so a single stray " . " in ordinary
# prose (an ellipsis, a spaced initial) does not disable the check for the whole text.
_SPACE_TOKENIZED_RE = re.compile(r"(?:\s[,.]\s.*){2}", re.DOTALL)
# The spaced hyphen as a dash: not between digits ("2020 - 2025"), and not a list bullet — at the
# start of a line, or introducing items after a colon.
_SPACED_DASH_RE = re.compile(r"(?<!\d)(?<!^)(?<!:) - (?!\d)", re.MULTILINE)

_CATEGORIES: list[tuple[str, re.Pattern]] = [
    ("ai_vocab", _AI_VOCAB_RE),
    ("formulaic_transition", _TRANSITION_OPENER_RE),
    ("steering_opener", _STEER_RE),
    ("negated_contrast", _NEGATED_CONTRAST_RE),
    ("participial_trailer", _PARTICIPIAL_TRAILER_RE),
    ("vague_attribution", _VAGUE_ATTR_RE),
    ("cliche", _CLICHE_RE),
    ("sycophancy", _SYCOPHANCY_RE),
    ("meta_closer", _META_CLOSER_RE),
    ("chatbot_artifact", _ARTIFACT_RE),
    ("inflated_copula", _INFLATED_COPULA_RE),
    ("hedge_stacking", _HEDGE_STACK_RE),
    ("false_range", _FALSE_RANGE_RE),
    ("markdown_artifact", _MARKDOWN_ARTIFACT_RE),
    ("filler_phrase", _FILLER_RE),
    ("aphorism", _APHORISM_RE),
    ("rhetorical_opener", _RHETORICAL_OPENER_RE),
    ("cutoff_disclaimer", _CUTOFF_RE),
    ("challenges_section", _CHALLENGES_RE),
    ("notability_padding", _NOTABILITY_RE),
]


def _rule_of_three_runs(text: str) -> int:
    """Count runs of 3+ consecutive very-short sentences — the staccato 'Fast. Simple. Effective.'
    tricolon cadence that is a distinctive AI/marketing tell (and rare in ordinary prose). Each run of
    >=3 short (<=3-word) sentences counts once. Conservative on purpose: the comma tricolon
    ('fast, simple, and effective') is skipped because it collides with ordinary noun lists."""
    sents = _sentences(text)
    runs, streak = 0, 0
    for s in sents:
        if len(_WORD.findall(s)) <= 3:
            streak += 1
            if streak == 3:  # count the run once, when it first reaches three
                runs += 1
        else:
            streak = 0
    return runs


# Minimum length for the two repetition tells below. A 40-word paragraph has ~38 trigrams, so a
# single incidental repeat is 2.6% and would clear a 5% bar on noise alone.
_MIN_WORDS_FOR_REPETITION = 60


def _repeated_trigrams(text: str) -> int:
    """Word 3-grams the text uses more than once, as a share of its tokens (percent, floored).

    **The strongest single signal measured in this repo**, and it replicates across corpora:

        AUROC 0.965 on 120 RAID pairs · 0.921 on 120 HC3 pairs

    For scale, the whole tells/100w metric runs 0.638-0.705. AI prose reuses its own phrasing far
    more than human prose does — mean 11.3% against 1.8% on RAID, 7.5% against 1.3% on HC3 — which
    is a different failure from vocabulary: the model settles into a phrase and returns to it.

    Threshold 5.0 chosen from the false-positive curve rather than by eye:

        threshold   RAID FP / TP    HC3 FP / TP
            4         9% / 88%        9% / 72%
            5         3% / 80%        6% / 62%      <- shipped
            6         2% / 71%        5% / 49%

    Counted once per repeat, not once per gram, so a phrase used three times contributes two.
    """
    words = [w.lower() for w in _WORD.findall(text)]
    if len(words) < _MIN_WORDS_FOR_REPETITION:
        return 0
    grams = Counter(tuple(words[i : i + 3]) for i in range(len(words) - 2))
    repeats = sum(c - 1 for c in grams.values() if c > 1)
    return repeats if (repeats / len(words) * 100) >= 5.0 else 0


def _duplicate_sentence_starts(text: str) -> int:
    """Sentences opening with a word already used to open another sentence, as a percent.

    MEASURED — AUROC 0.901 on RAID, 0.606 on HC3. Weaker on HC3 because its answers are short and
    a handful of sentences cannot repeat much; the direction is the same on both. Threshold 40%
    keeps the false-positive rate at 8% (RAID) and 7% (HC3).

    This is the mechanical form of a documented tell: machine prose cycles through a small set of
    openers ("Additionally", "The", "This"), where a person varies them without trying.
    """
    words = _WORD.findall(text)
    if len(words) < _MIN_WORDS_FOR_REPETITION:
        return 0
    starts = [_WORD.findall(s)[0].lower() for s in _sentences(text) if _WORD.findall(s)]
    if len(starts) < 4:  # too few openers for a share to mean anything
        return 0
    dupes = len(starts) - len(set(starts))
    return dupes if (dupes / len(starts) * 100) >= 40.0 else 0


def _semicolon_crutch(text: str) -> int:
    """Semicolons used as a rhythm crutch (§6). One is ordinary; 2+ in a passage is the tell. Returns
    the count only when it crosses that bar, else 0 (so a single legitimate semicolon never flags)."""
    n = text.count(";")
    return n if n >= 2 else 0


# --- formatting tells -------------------------------------------------------------------------
# The catalogue's other half is about how a document is LAID OUT, not what it says. These are
# thresholded, unlike the prose patterns, because every one of them has an honest use: humans write
# title-case headings, bulleted definition lists and curly quotes all the time. The threshold is the
# whole design, so it was measured rather than guessed — 135 human-written markdown documents
# (site-packages READMEs and dist METADATA, overwhelmingly pre-LLM), share of docs that fire:
#
#     candidate            share of human docs firing        shipped
#     diff_anchored          0.0%                             yes (>=2)
#     title_case_heading     27.4% -> 8.1% at >=3             yes (>=3)
#     inline_header_list     13.3% at >=3, 8.1% at >=8        NO
#     curly_quotes           0.7% at >=4                      NO
#     fragmented_header      55.6% -> 43.7% at >=3            NO
#
# Four of the seven candidates in the public catalogue are rejected here, each on a measurement:
#
#   fragmented_header  — human READMEs are naturally header-dense with short sections, so "many
#       headings with little text between them" describes ordinary documentation, not machine
#       writing. Nothing survives thresholding.
#   hyphenated pairs   — human markdown already runs a median 1.71 and a p90 of 4.83 hyphenated
#       pairs per 100 words. Any threshold clearing that is too high to catch anything.
#   inline_header_list — "- **Speed**: fast" is standard documentation style. The giveaway is that
#       the false-positive rate barely responds to the threshold (13.3% at 3, still 8.1% at 8): a
#       pattern that separated would fall off a cliff, this one just loses recall.
#   curly_quotes       — on the one corpus where direction is testable it points the WRONG WAY:
#       200 HC3 prose pairs give human 5, ai 0. That is the em-dash failure mode exactly (see
#       score_tells), and a punctuation tell that fires on human text degrades the metric it is
#       supposed to improve. Worth revisiting against a modern-model corpus, since HC3's AI side is
#       2022-era and later models do emit typographic quotes — but not on today's evidence.
_FENCE_RE = re.compile(r"(?ms)^```.*?^```")
_HEADING_RE = re.compile(r"(?m)^#{1,6}\s+(.+)$")
_DIFF_ANCHOR_RE = re.compile(r"(?m)^\s*\+\s+\w")
# Skipped when deciding whether a heading is title-cased: capitalising these is what distinguishes
# real Title Case from a merely capitalised sentence, so counting them would flag both.
_TITLE_STOPWORDS = frozenset(
    "a an the and or of to in for with on at by is as from but nor so if then than".split()
)


def _title_case_headings(text: str) -> int:
    """Headings written in Title Case — "How To Build A Better Thing" (§ formatting).

    The first word is ignored: every heading capitalises it, so it carries no signal. A heading
    qualifies when at least 80% of the remaining non-stopword tokens are capitalised, and only
    headings of four or more words are considered — "## Quick Start" is a normal heading.
    """
    n = 0
    for heading in _HEADING_RE.findall(text):
        words = _WORD.findall(heading)
        if len(words) < 4:
            continue
        rest = [w for w in words[1:] if w.lower() not in _TITLE_STOPWORDS]
        if rest and sum(w[0].isupper() for w in rest) / len(rest) >= 0.8:
            n += 1
    return n


def _formatting_tells(text: str) -> dict[str, int]:
    """Layout-level tells, each counted only once it crosses its measured threshold.

    Fenced code is stripped first. A code block is quoted material, not the author's prose, and a
    README's shell snippet is full of ``+`` lines and hyphens that mean nothing about the writing.
    """
    body = _FENCE_RE.sub("\n", text)
    out: dict[str, int] = {}
    for name, count, floor in (
        ("title_case_heading", _title_case_headings(body), 3),
        ("diff_anchored", len(_DIFF_ANCHOR_RE.findall(body)), 2),
    ):
        if count >= floor:
            out[name] = count
    return out


def _sentences(text: str) -> list[str]:
    from untell.text_split import split_sentences

    return split_sentences(text)


def _burstiness_cv(text: str) -> float | None:
    """Coefficient of variation of sentence lengths (stdev/mean). Low (<~0.35) = uniform = a tell.
    None when there are fewer than 2 sentences (undefined)."""
    sents = _sentences(text)
    if len(sents) < 2:
        return None
    lengths = [len(_WORD.findall(s)) for s in sents]
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return None
    var = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    return round((var**0.5) / mean, 4)


# Scripts this catalogue cannot read at all: CJK ideographs, Hangul, Hiragana/Katakana, Cyrillic,
# Arabic, Hebrew, Devanagari, Thai. Deliberately a rough test — the question is only "is this
# mostly not-Latin", not "which language is it".
_NON_LATIN_RE = re.compile(
    "[぀-ヿ㐀-䶿一-鿿가-힯"
    "Ѐ-ӿ֐-׿؀-ۿऀ-ॿ฀-๿]"
)


def _by_evidence(by_category: dict[str, int]) -> dict[str, int]:
    """Roll the per-category counts up into strong / moderate / weak / unmeasured buckets."""
    out = {"strong": 0, "moderate": 0, "weak": 0, "unmeasured": 0}
    for name, n in by_category.items():
        out[_EVIDENCE.get(name, "unmeasured")] += n
    return {k: v for k, v in out.items() if v}


def _language_supported(text: str) -> bool:
    """False when the text is mostly a script none of these English patterns can match.

    Compared against Latin letters rather than against total length, so punctuation, digits and
    whitespace do not sway it. A passage that is majority non-Latin gets a warning; a mostly-English
    passage quoting a Chinese phrase does not.
    """
    non_latin = len(_NON_LATIN_RE.findall(text))
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    if non_latin == 0:
        return True
    return latin > non_latin


def score_tells(text: str, *, include_matches: bool = False) -> dict:
    """Count AI tells in ``text`` per the catalogue. Lower is more human-reading."""
    words = len(_WORD.findall(text))
    by_category: dict[str, int] = {}
    matches: dict[str, list[str]] = {}

    # True em-dash plus the spaced-hyphen " - " used as a dash — but NOT digit ranges ("2020 - 2025"),
    # which a spaced hyphen between numbers represents.
    #
    # The surrogate needs two more exclusions, both measured on 200 HC3 pairs where this category
    # alone counted 190 on HUMAN text and 0 on AI, single-handedly inverting tells/100w (human 0.602
    # vs ai 0.468 — the metric pointed the wrong way). Only 5 of the 190 were real em-dashes. The
    # other 185 were:
    #   - space-tokenized compounds: "oscar - winning", "Kim Jong - Un", "mass - production". Not
    #     dashes at all, just a corpus that puts spaces around every punctuation mark. Detected by
    #     the same corpus writing " , " and " . ", which no ordinary prose does;
    #   - list bullets: ": - Summon a creature", "- Create a lasting effect". A bullet is document
    #     structure and is already the markdown_artifact category's business.
    # Both exclusions are properties of the text, not of HC3, so they generalise.
    spaced = 0
    if not _SPACE_TOKENIZED_RE.search(text):
        spaced = len(_SPACED_DASH_RE.findall(text))
    em_dashes = text.count("—") + spaced
    if em_dashes:
        by_category["em_dash"] = em_dashes
        if include_matches:
            matches["em_dash"] = ["—"] * text.count("—")

    # Count by SPAN, not by pattern, so one stretch of text can only ever be one tell. Several words
    # legitimately appear in two categories — "boasts" is AI vocabulary AND an inflated copula;
    # "showcasing" is AI vocabulary AND the head of a participial trailer — and counting both fired
    # the same token twice, breaking the module's stated invariant that "a single phrase must count
    # in exactly one category, never two". Deleting the duplicate words is the wrong fix: they are
    # real tells in constructions the more specific pattern does not match ("platform showcasing
    # wins" has no comma, so the trailer pattern never fires).
    #
    # The LONGEST match claims the span, not the first category in the list — _CATEGORIES is ordered
    # for readability, not specificity, and ai_vocab sits first, so list order would let a single
    # word beat the multi-word construction that contains it.
    spans: list[tuple[int, int, str, str]] = []
    for name, pat in _CATEGORIES:
        for m in pat.finditer(text):
            spans.append((m.start(), m.end(), name, m.group(0)))
    spans.sort(key=lambda s_: (-(s_[1] - s_[0]), s_[0]))  # longest first, then leftmost

    claimed: list[tuple[int, int]] = []
    for start, end, name, matched in spans:
        if any(start < c_end and end > c_start for c_start, c_end in claimed):
            continue  # this text is already counted as a richer tell
        claimed.append((start, end))
        by_category[name] = by_category.get(name, 0) + 1
        if include_matches:
            matches.setdefault(name, []).append(matched)

    # Two tells that aren't a simple findall:
    rot = _rule_of_three_runs(text)
    if rot:
        by_category["rule_of_three"] = rot
    semi = _semicolon_crutch(text)
    if semi:
        by_category["semicolon_crutch"] = semi
    # The two repetition tells — the strongest signals in the catalogue, added 2026-08-07 after
    # measuring candidate techniques used across the 435-repo census. See their docstrings.
    rep = _repeated_trigrams(text)
    if rep:
        by_category["repeated_phrasing"] = rep
    dup = _duplicate_sentence_starts(text)
    if dup:
        by_category["repeated_sentence_openers"] = dup
    by_category.update(_formatting_tells(text))

    total = sum(by_category.values())
    cv = _burstiness_cv(text)
    result = {
        "words": words,
        "tells": total,
        "tells_per_100w": round(total / words * 100, 2) if words else 0.0,
        "by_category": by_category,
        "burstiness_cv": cv,
        "low_burstiness": (cv is not None and cv < 0.35),  # uniform sentence length is itself a tell
        # Every pattern in this module is an English regex, and ``_WORD`` is ``[A-Za-z0-9']+``, so
        # text in a non-Latin script matches nothing and divides by nothing. MEASURED, before this
        # field existed:
        #     Chinese AI text   tells 0   words 0   -> reported as perfectly clean
        #     Korean AI text    tells 0   words 0   -> reported as perfectly clean
        #     Japanese AI text  tells 0   words 0   -> reported as perfectly clean
        # A zero from an inapplicable catalogue is not a clean bill of health, and returning one is
        # the same defect as a detector that saturates: silence read as a verdict. Callers get an
        # explicit signal instead. This does NOT add non-English coverage — it refuses to pretend.
        "language_supported": _language_supported(text),
        # Counts split by how incriminating each category measured on real text (see _EVIDENCE).
        # A caller can now tell "3 tells, all strong" from "3 tells, all punctuation habits" —
        # the same total, very different verdicts.
        "by_evidence": _by_evidence(by_category),
    }
    if not result["language_supported"]:
        result["warning"] = (
            "this catalogue is English-only, and the text is mostly non-Latin script — a score of "
            f"{total} tells means the patterns did not apply, NOT that the text reads as human"
        )
        logger.warning(result["warning"])
    if include_matches:
        result["matches"] = matches
    return result


def _render(r: dict) -> str:
    lines = [
        f"AI-tells: {r['tells']}  ({r['tells_per_100w']} per 100 words, {r['words']} words)",
        f"burstiness CV: {r['burstiness_cv']}"
        + ("  [LOW — uniform sentence length is itself a tell]" if r["low_burstiness"] else ""),
    ]
    if r.get("by_evidence"):
        lines.append(
            "by evidence: "
            + ", ".join(f"{k} {v}" for k, v in r["by_evidence"].items())
            + "   (strong = measured near-certain on real text; weak = style preference)"
        )
    if r["by_category"]:
        lines.append("by category:")
        for k, v in sorted(r["by_category"].items(), key=lambda kv: -kv[1]):
            lines.append(f"  {k:22} {v}")
    elif r.get("warning"):
        # NOT "no catalogued tells found" — that sentence reads as a clean bill of health, and on
        # non-Latin input it would be reporting the catalogue's blindness as the text's virtue.
        lines.append(f"WARNING: {r['warning']}")
    else:
        lines.append("no catalogued tells found.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()
    parser = argparse.ArgumentParser(
        prog="untell-tells",
        description="Count the AI writing tells in a passage (lower = more human-reading).",
    )
    parser.add_argument("text", nargs="?", help="text to scan (or --file / stdin)")
    parser.add_argument("--file", "-f", help="read text from this file (.txt/.docx/.pdf)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--matches", action="store_true", help="include the matched substrings")
    args = parser.parse_args(argv)

    if args.file:
        from untell.scripts.io_utils import read_file

        text = read_file(args.file)
    elif args.text:
        text = args.text
    else:
        text = sys.stdin.read()
    if not text.strip():
        print(json.dumps({"error": "empty input"}))
        return 2

    result = score_tells(text, include_matches=args.matches)
    print(json.dumps(result, ensure_ascii=True, indent=2) if args.json else _render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
