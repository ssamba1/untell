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
from collections import Counter

# RUN DIRECTLY (`python .../untell/scripts/tells.py`), put the directory that *contains* the package
# on sys.path so `import untell` resolves from any cwd. Must come BEFORE any `from untell...`
# import: below them it is unreachable, because the import raises ModuleNotFoundError first. An
# editable install hides that on every developer machine — it only shows on a bare interpreter,
# which is the zero-dependency skill path the README leads with.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

# The sentinel shape `preserve.lock()` emits. Imported rather than re-declared, which is what
# `SENTINEL_RE` is exported for — one constant, two names, no second copy to drift.
#
# The local copy carried its own justification: "`preserve` imports from this module, and the
# pattern is four characters of regex." The first half is not true — `preserve` imports from
# `untell.scripts.latex` and from nothing else in this package — and the second is the argument
# against every duplicated constant ever written. The repo has a test enforcing the rule, and it
# was failing on main.
from untell.scripts.preserve import SENTINEL_RE as _SENTINEL_RE  # noqa: E402
from untell.text_split import fold_unicode_spaces  # noqa: E402

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
#     human RAID texts — those are academic abstracts, where "Furthermore" is native. A catalogue
#     tuned on forum answers partly learns "formal" rather than "machine".
#
#     This finding used to carry the claim that overall separation was WORSE on RAID than HC3
#     (AUROC 0.638 vs 0.705, tells/100w gap +0.227 vs +0.307). That ordering has inverted, and the
#     figures were stale rather than wrong — re-derive them with `python -m eval.tells_auroc`:
#
#                       AUROC            tells/100w human    ai      gap
#         RAID (200)    0.9555                    1.139   12.823   +11.683
#         HC3  (200)    0.8696                    0.635    6.834    +6.199
#
#     The cause is the two repetition tells, which landed after 0.638 was written and are listed
#     below as the strongest categories in the catalogue. Excluding them reproduces the old numbers
#     exactly — RAID 0.6379 — which is how the drift was identified rather than guessed at. Their
#     effect is +0.3175 on RAID and +0.1373 on HC3, so RAID now separates BETTER than HC3 and the
#     register argument no longer rests on the overall gap. It still rests on
#     `formulaic_transition`'s own 43-of-150 human hits, which is the evidence that was always
#     doing the work.
#
#     WHICH CATEGORIES EARN THOSE NUMBERS — measured over 60 pairs per corpus, counting how many
#     of the 20 categories fire at all on the AI half:
#
#         RAID   9/20    ai_vocab cliche false_range formulaic_transition hedge_stacking
#                        challenges_section inflated_copula negated_contrast participial_trailer
#         HC3    7/20    ai_vocab cliche false_range formulaic_transition hedge_stacking
#                        meta_closer vague_attribution
#         MAGE   3/20    ai_vocab cliche false_range
#
#     Union 11 of 20, and only `ai_vocab`, `cliche` and `false_range` fire on all three. The other
#     NINE — sycophancy, chatbot_artifact, markdown_artifact, cutoff_disclaimer, rhetorical_opener,
#     steering_opener, aphorism, notability_padding, filler_phrase — score zero on 360 AI documents
#     across all three corpora, and are exercised only by the constructed positives in
#     `test_every_tell_category_can_fire.py`.
#
#     They are not broken: every one of the 20 matches a known positive, and that suite passes. They
#     are artifacts of a register these corpora do not contain — chat-interface scaffolding,
#     markdown headers, refusal boilerplate — where HC3 is 2022 forum answers, RAID is news and
#     reviews, MAGE is domain-matched prose. So the honest reading of "AUROC 0.9555 on RAID" is that
#     nine categories produced it and nine others were never tested against real text at all. A
#     corpus of modern chat output would be the thing that validates them; none is in this repo.
#
#     Layout was checked at the same time, since RAID separates its own halves at AUROC 1.0000 on
#     newline density alone and `eval/detector_audit.py` collapses layout for exactly that reason.
#     It does not affect this metric: collapsing whitespace moves the AUROC by +0.0000 on RAID, HC3
#     and MAGE, because the three line-anchored categories fire on 0, 1 and 1 of 400 documents. So
#     layout is deliberately NOT collapsed here — those categories are line-anchored by design and
#     silencing them would delete signal, not bias. `eval.tells_auroc` reports the delta every run.
#
# They are NOT dropped or reweighted. Ten categories never fire on HC3 at all —
# chatbot_artifact, cutoff_disclaimer, aphorism, notability_padding and the formatting ones — and
# those are precisely the MODERN tells: HC3 is 2022-era ChatGPT and predates them. Refitting to it
# would delete the patterns aimed at current models to score better on a dated benchmark, which is
# the same trap `humanness.py` documents declining. What ships instead is the split below, so a
# caller can see whether a score rests on strong evidence or on style preferences.
#
# CONFIRMED at a larger n, 2026-08-09 — the same measurement re-run at 200 pairs on BOTH corpora,
# which reproduces the PER-CATEGORY precisions above and adds the ones the 150-pair run left
# unlisted. It did not re-derive the overall AUROC, and that is what let the 0.638/0.705 pair in
# finding 3 go stale while the table below was being updated around it:
#
#                             HC3 (200)      RAID (200)
#     participial_trailer     never fires    0.971  (150-pair run: 0.96)
#     repeated_phrasing       0.925          0.942
#     cliche                  0.902          0.941  (0.93)
#     repeated_sentence_openers 0.667        0.890
#     hedge_stacking          0.526          0.875   <- 0.53 to 0.88 across corpora
#     challenges_section      never fires    0.833
#     formulaic_transition    0.884          0.603  (0.60)
#     ai_vocab                0.615          0.585  (0.59)
#     em_dash                 0.000          0.000  (0.00)
#     semicolon_crutch        0.000          0.333
#
# Nothing here changes the decision, which is the point of running it. Two additions:
#
#  4. **`em_dash` has now fired on 0 AI documents out of 400, across two corpora and two eras.**
#     The single most-cited "AI tell" in public discourse. It is not weak evidence pointing the
#     right way; it has no observations pointing the right way at all. It stays in the catalogue
#     as `weak` because a caller scanning for the famous tells should see it reported and see the
#     number next to it — deleting it silently would leave them assuming it was never checked.
#
#     Read the DENOMINATOR before acting on any precision in these tables — it is per FIRING, not
#     per document scanned, and "0 out of 400 documents" is 7 firings. Re-derived with
#     `python -m eval.tells_auroc --precision`, which now reports n and a 95% Wilson interval:
#
#         em_dash            human 7  ai 0   n=7    0.000  [0.00, 0.35]   p=0.016
#         semicolon_crutch   human 6  ai 1   n=7    0.143  [0.03, 0.51]   p=0.125
#         inflated_copula    human 2  ai 2   n=4    0.500  [0.15, 0.85]   p=1.000
#         rule_of_three      human 1  ai 0   n=1    0.000  [0.00, 0.79]   p=1.000
#
#     em_dash survives this: 7 firings, all 7 on human text, p=0.016 pooled. The direction is
#     established even though the interval on the rate spans [0.00, 0.35]. `semicolon_crutch` and
#     `inflated_copula` do NOT survive it — the published 0.000 for inflated_copula came from ONE
#     firing, and its interval [0.00, 0.79] is equally consistent with it being among the better
#     categories. Nine of the fifteen categories that fire at all on RAID do so fewer than ten
#     times, so their point estimates are decoration.
#
#     Nothing was decided on those entries, which is the saving grace: the "five categories fire
#     more on human writing" note below leads to no action, because they are explicitly NOT dropped
#     or reweighted. Had they been dropped, three of the five would have been dropped on a single
#     observation each.
#  5. **`hedge_stacking` is register, not authorship.** 0.53 on forum answers and 0.88 on
#     abstracts. Same pattern, same code, opposite usefulness — which is the third category after
#     `formulaic_transition` and `moreover` to behave this way, and the reason no single number
#     for "how good is this catalogue" is meaningful without naming the corpus.
#
# "unmeasured" means exactly that: no evidence either way from this corpus, not "weak".
_EVIDENCE: dict[str, str] = {
    "sycophancy": "strong", "meta_closer": "strong", "filler_phrase": "strong",
    "cliche": "strong", "chatbot_artifact": "strong", "cutoff_disclaimer": "strong",
    "formulaic_transition": "moderate", "vague_attribution": "moderate",
    "hedge_stacking": "weak", "negated_contrast": "weak", "ai_vocab": "weak",
    "false_range": "weak", "em_dash": "weak", "inflated_copula": "weak",
    "markdown_artifact": "weak", "rule_of_three": "weak", "semicolon_crutch": "weak",
    # Added 2026-08-07 and immediately the strongest entries here — repeated_phrasing at AUROC
    # 0.817 once controlled for length (0.965 raw, and the raw figure over-claims: RAID's AI texts
    # are 45% longer, which inflates any repetition measure), repeated_sentence_openers at
    # 0.901/0.606. Against 0.638-0.705 for the whole tells/100w metric, and ~0.57 for ai_vocab
    # measured twice. Both replicate across corpora, which is what earns "strong" here.
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
#
# This is the strongest category in the catalogue — 0.971 precision on RAID — and for a long time
# its coverage was thirteen hand-picked verbs that happened to omit the commonest ones. ",
# including ..." alone appears 205 times in the AI half of 200 RAID pairs against 12 in the human
# half, and was invisible.
#
# Every addition below was measured on BOTH halves of both corpora (200 pairs each, 2026-08-09) and
# is listed with its own numbers, because a trailer that human academics write as often as models
# is register rather than authorship:
#
#     including      HC3 38/2  (0.950)   RAID 205/12  (0.945)   <- both corpora
#     making                             RAID  32/1   (0.970)
#     allowing                           RAID  31/1   (0.969)
#     providing                          RAID  23/0   (1.000)
#     achieving                          RAID  19/0   (1.000)
#     enabling                           RAID  17/1   (0.944)
#     leading                            RAID  26/6   (0.812)
#     outperforming                      RAID  13/2   (0.867)
#     reducing                           RAID   7/0   (1.000)
#     improving                          RAID   4/0   (1.000)
#
# Declined, and why — a list like this grows by accretion unless the rejections are written down:
#
#     tracking      5/0 but RAID is paper abstracts and half of them are about object tracking.
#                   Subject matter, not register. Same call as "united" in Result 32.
#     resulting     9/4  (0.692) — under the bar.
#     showing       8/4  (0.667), obtaining 4/2 — under the bar.
#     using         6/10 on RAID and 2/3 on HC3: points HUMAN in both.
#     causing       5/1 on HC3 only, total n=6. Too rare to say anything.
#
# NOT ADDED — the widened list was built, measured, and reverted. Keeping the numbers because the
# reason is more useful than the list.
#
# With all ten in, the category's recall rose fivefold (33 -> 176 of 200 AI RAID documents) and it
# started firing on HC3 at all (0 -> 37, precision 0.822). Precision on RAID fell 0.971 -> 0.876,
# which would have been an acceptable trade. What killed it was the output:
#
#     old (13 verbs)  post=0.4560 flagged=0.600  trailers left in output 52
#     new (23 verbs)  post=0.4807 flagged=0.650  trailers left in output 53
#     replicate:      old 0.4413/0.625 (47)      new 0.4689/0.675 (51)
#
# Two readings, and the second is the one that matters:
#
#  1. The output trailer count does not move. 92 in the AI input, ~50 left either way. The rewriter
#     has NO transform for a participial trailer — it removes some incidentally when it merges or
#     splits around one, and that is all. Seeing more of them cannot help it fix more of them.
#  2. The score is consistently WORSE, +0.025 and +0.028 across two runs against a +/-0.013
#     single-run noise floor. `prefer_tells` ranks candidate rewrites by total tell count, so
#     widening a category the rewriter cannot act on re-weights the objective toward something
#     unfixable and it picks worse candidates.
#
# So the real gap looked like the missing rewrite rather than the word list. That was then built —
# ", showcasing Y." -> ". This showcases Y.", no parser needed since the participle carries its own
# object and thirteen verbs conjugate from a fixed map — budgeted to the human rate for "This ..."
# openers (4.59 per 100 sentences; AI already sits at 4.19, so the headroom allows about a third of
# them). It fires, it is grammatical, it guards against promoting a fragment. It was also reverted:
#
#     narrow pattern, transform off   post=0.4700 flagged=0.625
#     narrow pattern, transform on    post=0.4769 flagged=0.625
#     wide pattern,   transform off   post=0.4904 flagged=0.700
#     wide pattern,   transform on    post=0.4913 flagged=0.675
#
# No effect in either configuration, and the two OFF baselines differ by 0.020 — larger than any
# treatment effect in the table, so the noise floor swallows all of it.
#
# The reason is in a column that had been there the whole time: **trailers left in the output = 0**,
# with the transform off. Every one of the thirteen catalogued verbs is already gone by the end of
# the pipeline, removed incidentally by merges and splits landing on them. The ~50 residual trailers
# counted earlier were entirely the UNLISTED verbs, and promoting those did not help either.
#
# What this actually establishes: **diagnostic strength is not rewrite leverage.** participial
# trailer is the best discriminator in the catalogue and there is nothing to gain by acting on it,
# because the pipeline already clears it as a side effect. A category being predictive of AI
# authorship says the detector can see it; it does not say a rewriter that removes it will score
# better. Nothing shipped — no word-list change, no transform, no constant.
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
    # "Symmetry is the language of trust" — the pull-quote closer. The branch above only reaches
    # this shape when it ends in web/internet/world/age/era, which is the narrower half of it. A
    # closed list of metaphor nouns is what keeps the branch honest: "Paris is the capital of
    # France" has the same grammar and must not match, so the noun, not the shape, does the work.
    # "price" was on this list and was the only human false positive in 1,200 documents — "the cost
    # of gasoline at the pump is the price of oil" is a literal price. Unlike language and currency
    # it cannot be rescued by naming its literal subjects, because the literal sense takes an open
    # set of commodities, so it is dropped rather than guarded.
    r"|\b(?:is|are)\s+the\s+(?:foundation|bedrock|engine|backbone|lifeblood"
    r"|cornerstone|heartbeat|enemy|architecture|grammar|soul)\s+of\s+\w+"
    # "language" and "currency" are the two nouns on that list with an everyday literal sense —
    # "French is the language of diplomacy", "the euro is the currency of Ireland" are true
    # statements, not aphorisms. What separates them is the subject, so name the literal subjects
    # and exclude them. Sentence-initial capitalisation rules out the tidier test of "is the
    # subject a proper noun", since the aphorism's subject is capitalised just as often.
    r"|\b(?!(?:french|english|spanish|german|latin|arabic|mandarin|chinese|russian|portuguese"
    r"|italian|japanese|korean|hindi|greek|hebrew|euro|dollar|yen|pound|peso|rupee|franc|bitcoin"
    r")\b)\w+\s+(?:is|are)\s+the\s+(?:language|currency)\s+of\s+\w+"
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
    r"maintains a low profile|i do not have access to real-?time|"
    # The first-person forms above are the easy half. The assistant hedge that actually survives
    # into pasted output is impersonal — it reads as caution about the subject rather than about
    # the model, which is why a reader leaves it in. Same artefact, no "my".
    r"while (?:specific |precise |further )?details (?:are|remain) (?:limited|scarce|sparse)|"
    r"(?:limited|little|scant) (?:public |reliable |verifiable )?information is available|"
    r"(?:specific|precise) details (?:are|remain) (?:unclear|unavailable|undisclosed))\b",
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
    r"has been (?:widely )?(?:covered|featured) (?:in|by)|written by a leading expert)\b"
    # The padding above is the generic kind. The other kind names the outlets — "cited in the New
    # York Times, the BBC, the FT, and The Hindu" — where the roster IS the claim and no single
    # citation is given. Three or more is the bar: one or two publications is ordinary sourcing,
    # and a list is what turns it into notability padding. Case matters here (outlet names are
    # proper nouns) so this branch opts out of IGNORECASE.
    r"|\b(?:cited|featured|profiled|mentioned|covered)\s+(?:in|by)\s+"
    r"(?-i:(?:[Tt]he\s+)?[A-Z][\w.&]*(?:\s+[A-Z][\w.&]*)*"
    r"(?:,\s+(?:and\s+)?(?:[Tt]he\s+)?[A-Z][\w.&]*(?:\s+[A-Z][\w.&]*)*){2,})",
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
    # The subject between "challenges," and "continues" is a noun PHRASE, not a bare noun. The
    # original `\w+` matched "Despite challenges, Lisbon continues to thrive" and missed "…, the
    # sector continues to thrive" — the more common shape of the two. Bounded and non-greedy so it
    # cannot reach across a sentence, and the verb set covers the same boosterism.
    r"despite (?:(?:the|these|those|its|their|ongoing|numerous|several|many|significant)\s+){0,2}"
    r"(?:challenges|obstacles|setbacks|difficulties)"
    r"[^.]{0,40}?continues to (?:thrive|grow|flourish|expand)",
    r"vibrant hub", r"thriving ecosystem",
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
    # `to the` was required here, so this alternative missed the catalogue's OWN headline example:
    # `ai-tells.md` item 17 quotes "from ancient civilizations to modern startups", and the second
    # half has no article. The scope word at the front is what keeps this from matching an ordinary
    # range, so the article was carrying no weight. MEASURED over 120 HC3 and RAID pairs, dropping
    # it changes the counts on real text by ZERO in both corpora — the shape simply does not occur
    # there — so this closes a documented-example gap at no measured cost.
    r"|\bfrom\s+(?:ancient|the everyday|the mundane|individual|small|humble)\b[^.!?]{0,50}\bto\s+\w+"
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
    ('fast, simple, and effective') is skipped because it collides with ordinary noun lists.

    MEASURED, so this is not re-attempted. A bare `A, B, and C` count looks promising — 2.7x
    AI-ward on RAID — but inverts on MAGE (0.98), and the obvious repair makes it worse rather
    than better. Tagging the coordinated items with spaCy and keeping only all-ADJ or all-ADV runs
    (the literal 'fast, simple, and effective' shape) gives, at 400 pairs per corpus:

        ADJ-only    RAID 1.04   HC3 2.10   MAGE 0.36     <- no signal, and inverted on MAGE
        NOUN-only   RAID 2.51   HC3 1.38   MAGE 1.95
        MIXED       RAID 0.77   HC3 0.83   MAGE 0.79     <- reliably HUMAN-ward

    So the AI lean in the naive count is carried by *noun* lists, not by the adjective tricolon the
    catalogue describes: the POS guard keeps the one slice with no signal and discards the one that
    has it. (RAID ADJ was 1.84 at 200 pairs and 1.04 at 400 — that slice is too sparse to quote
    from a single sample.) Flagging noun lists instead is not the fix either. At ~2x, one human
    document is flagged for every two AI documents, against a catalogue where the neighbouring
    patterns manage zero human hits in 1,200 — and there is no rewrite for 'apples, oranges, and
    bananas' anyway, so the tell would add noise to the loop without giving it an action."""
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
    """Word 3-grams the text uses more than once, counted, once the count clears 5% of its tokens.

    The share is the FIRING RULE; the number returned is the raw repeat count, not the percentage.
    This line used to say "as a share of its tokens (percent, floored)", which contradicted the
    "counted once per repeat" line below it and the code between them: 150 words with 143 repeats
    returns 143, not 95. The count is the right choice and the reason is three paragraphs down —
    the share is confounded by length and this text's length is something the rewriter changes.

    The strongest single signal measured in this repo, and it replicates across corpora — but the
    headline number is inflated by LENGTH and the honest figure is the controlled one:

        AUROC 0.965 raw · **0.817 length-matched** · 0.815 on a fixed 150-word window
                                                      (120 RAID pairs; 0.921 raw on HC3)

    RAID's AI texts run 293 words against 203 for the human halves, and a longer text has more
    chances for any trigram to recur, so roughly 40% of the raw separation was length rather than
    style. What survives the control is still the best signal here — AI repeats 3.3x more per
    token at matched length (4.24% against 1.29%) — and still beats the whole tells/100w metric,
    which runs 0.638-0.705. But 0.965 was over-claiming and is corrected here rather than quoted on.

    The THRESHOLD is unaffected, which is the practical question. Measured on human text alone
    across 384 documents, the share crossing 5% is flat with length — 6% at 60-150 words, 5% at
    150-250, 5% at 250-400, 7% above 400 — because human prose stays far below the bar at every
    length. Mean human repetition does climb (1.19% -> 2.56%), so the margin narrows; a much longer
    corpus than anything measured here should re-check it.

    Threshold 5.0 chosen from the false-positive curve rather than by eye:

        threshold   RAID FP / TP    HC3 FP / TP
            4         9% / 88%        9% / 72%
            5         3% / 80%        6% / 62%      <- shipped
            6         2% / 71%        5% / 49%

    Counted once per repeat, not once per gram, so a phrase used three times contributes two.

    **MOSTLY NOT FIXABLE BY A MEANING-PRESERVING REWRITER, and that is not a defect.** Breaking
    down the repeated-trigram mass across 60 RAID AI abstracts:

        82%  DOMAIN TERMS    "medical image segmentation" x42, "local contrastive learning"
        18%  boilerplate     "we propose a", "a novel approach", "state of the art"

    Repeating the subject *is* the meaning. A rewriter that varied "medical image segmentation"
    would be changing what the text is about, and the meaning gates would veto it — correctly. So
    this is an excellent DETECTOR (AI hammers its subject where a person switches to "it" or "the
    technique") and a poor rewrite TARGET. MEASURED end to end on 12 RAID texts through the loop:

        no transform              24.83 -> 24.58
        + repetition-aware merge  24.83 -> 23.92
        + boilerplate synonyms    24.83 -> 23.50

    Read a high score here as "this text hammers one phrase", which is diagnostic, rather than as
    a defect the loop can be expected to clear.
    """
    words = [w.lower() for w in _WORD.findall(text)]
    if len(words) < _MIN_WORDS_FOR_REPETITION:
        return 0
    grams = Counter(tuple(words[i : i + 3]) for i in range(len(words) - 2))
    repeats = sum(c - 1 for c in grams.values() if c > 1)
    return repeats if (repeats / len(words) * 100) >= 5.0 else 0


# How much text may sit around a matched sign-off and still count as pure scaffolding. MEASURED over
# seven sign-offs and three content sentences opening with the same phrases:
#
#     scaffolding remainders   0, 0, 3, 4, 5, 5, 5
#     content remainders       10, 11, 17
#
# Six sits between the groups. The evidence is thin — one content sentence is real, the rest
# constructed — so re-measure this if a document ever loses a sentence it should have kept.
CLOSER_REMAINDER_WORDS = 6


# Contentless stance frames: "It is important to note that X" says nothing about X that X does not
# already say. The rewriter deletes these outright (`structural._CLICHE_FLATTEN`, the entries whose
# replacement is empty), and the meaning gate has to know the same set, because each one contains a
# PREDICATE — "note", "should be noted" — whose disappearance the role checker reads as a role change.
#
# MEASURED before this existed, over 120 corpus texts: `_flatten_cliches` fired 22 times and was
# vetoed 4, every rejection from `role_swap` and every one a false veto — an 18% loss on the
# transform, and 1 in 20 documents losing its ENTIRE structural rewrite to it.
#
# Exactly the deleted set and nothing wider. Exempting every catalogued cliché would let a genuine
# role swap hide inside a cliché match, which is the leak direction; these nine frames carry no
# argument structure about the subject at all.
STANCE_FRAME_RE = re.compile(
    # The boundary is a lookbehind, not an escape. The first version of this constant was
    # generated through a shell heredoc and landed as a literal 0x08 BACKSPACE byte where the
    # escape was meant, so it matched nothing and the exemption below silently did nothing —
    # the same defect already recorded for three other patterns in this file. Only re-measuring
    # the fix and finding it changed NOTHING surfaced it.
    r"(?<![A-Za-z0-9_])(?:"
    r"[Ii]t(?:'s| is| was)\s+(?:also\s+)?(?:important|worth|essential|necessary|crucial)\s+"
    r"(?:to note|noting|to mention|mentioning|to remember|remembering)(?:\s+that)?\s*,?\s*"
    r"|it\s+should\s+be\s+noted\s+that\s+"
    r"|it'?s\s+no\s+secret\s+that\s+"
    r"|the\s+bottom\s+line\s+is\s+that\s+"
    r"|in\s+conclusion,?\s*"
    r"|(?:in\s+summary|to\s+summari[sz]e),?\s*"
    r"|at\s+its\s+core,?\s*"
    r"|as\s+technology\s+continues\s+to\s+evolve,?\s*"
    r")",
    re.IGNORECASE,
)


def is_pure_scaffolding(sentence: str) -> bool:
    """True when ``sentence`` is a chatbot sign-off and nothing else.

    Lives here because TWO callers need the same answer and they were built with two: the rewriter
    deletes whole sentences that satisfy this, while the meaning gate exempted only the matched
    SPAN. The remainder — "if you need more detail" — then read as deleted content and the gate
    vetoed the very transform this predicate defines. One definition, one unit, both sides.
    """
    match = _META_CLOSER_RE.search(sentence)
    if not match:
        return False
    # Anything the preserve layer locks is content, whatever the word count says. A remainder rule
    # counts WORDS, and a citation is worth more than its length: MEASURED, "I hope this helps [3]!",
    # "Let me know if you need the data (Smith 2020)." and "I hope this helps
    # https://example.org/paper." were all deleted as pure scaffolding, taking the reference with
    # them — against a README that promises citations are kept intact.
    #
    # `preserve._collect_spans` rather than a second citation pattern here: it already covers both
    # citation forms, URLs, DOIs, emails, identifiers, dates and quantities, and a private copy of
    # any of that is the two-vocabularies defect this file has been on both sides of.
    from untell.scripts.preserve import _collect_spans

    if _collect_spans(sentence):
        return False
    remainder = (sentence[: match.start()] + sentence[match.end() :]).strip(" .!?,;:")
    return len(remainder.split()) <= CLOSER_REMAINDER_WORDS


def _duplicate_sentence_starts(text: str) -> int:
    """Sentences opening with a word already used to open another sentence, as a percent.

    MEASURED — AUROC 0.901 on RAID, 0.606 on HC3. Weaker on HC3 because its answers are short and
    a handful of sentences cannot repeat much; the direction is the same on both. Threshold 40%
    keeps the false-positive rate at 8% (RAID) and 7% (HC3).

    "The direction is the same on both" is true of the RANKING and not of the raw counts, which is
    worth spelling out because the counts look damning. Over 60 paired texts per corpus:

        corpus    human   ai    ratio
        HC3          40    28    0.70   <- fires MORE on human prose
        MAGE         57    89    1.56
        RAID         22   248   11.27

    On HC3 this category supplies 37% of all human tells while firing less on the machine side, and
    HC3 is the corpus most of this repository's numbers are taken on. That reads as a category to
    drop. It is not — CHECKED before assuming, as AUROC of tells-per-100-words with the category
    and without it:

        corpus    with    without   delta
        HC3       0.898    0.904    +0.007   removing it helps, barely
        MAGE      0.800    0.764    -0.036
        RAID      0.934    0.881    -0.053

    So the inversion is real and dropping the category would still be wrong: it buys 0.007 on one
    corpus and costs five to seven times that on the other two. HC3's human side is forum answers,
    where people genuinely do open sentence after sentence with "I" and "It" — the tell is
    measuring something true about machine prose that this particular human corpus also does.

    Recorded because the fix that suggests itself here is a regression, and the evidence for it
    (40 against 28) is visible in one command while the evidence against it is not.

    This is the mechanical form of a documented tell: machine prose cycles through a small set of
    openers ("Additionally", "The", "This"), where a person varies them without trying.

    It FIRES on a share and REPORTS a count. They disagree whenever a rewrite changes the sentence
    count, and **the count is the one to trust**: it measures repetition INCIDENTS, which is what a
    reader notices, while the share measures DENSITY against a denominator the rewriter itself
    moves. MEASURED over the 47 corpus texts that fire, on the 18 where the share fell without the
    count falling: the duplicate openers were IDENTICAL before and after on 14 of them — not one
    repetition removed, the share fell only because sentences were added — and on the other 4 the
    repetition genuinely got WORSE while the share said better (e.g. 14 sentences with 8 duplicate
    openers becoming 18 with 10, share 57.1% -> 55.6%).

    So the count is length-invariant by design, the same reason `_repeated_trigrams` reports a count:
    its raw AUROC is ~40% length rather than style. Reporting the excess above the threshold instead
    was measured and is worse anyway — RAID AUROC 0.9555 -> 0.9381 floored at 1 / 0.9336 unfloored.
    See `tests/test_opener_repetition_fires_on_a_share_and_scores_a_count.py`.
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


# Below this many words, one tell alone reports a rate above the AI corpus mean (100/14 = 7.1 vs
# 7.335), so `tells_per_100w` stops being an estimate and becomes an artefact of the word count.
_MIN_WORDS_FOR_A_RATE = 14


# Closed-class English words. Short, and deliberately not a full stopword list — the ratio only has
# to be stable, not complete.
_ENGLISH_FUNCTION_WORDS = frozenset("""
a an the and or but if then than that this these those of in on at to for with from by about
is are was were be been being am do does did have has had will would can could should may might
not no nor as it its he she they them we you i his her their our your my me him us
""".split())

# The same class for the other major Latin-script languages, MINUS anything that is also an English
# function word: "a" is a Portuguese and Italian article, "in" is German and Dutch, and a shared
# token is evidence of nothing.
_OTHER_FUNCTION_WORDS = frozenset("""
el la los las un una del al es son fue eran ser estar y o pero si por para con sin sobre entre
le les des du au aux une est sont était être et ou mais si pour avec sans sur dans chez ce cette
der die das dem den ein eine einer und oder aber wenn ist sind war waren sein werden nach bei
mit von zu auf aus durch über unter zwischen sich nicht auch noch schon
il lo gli della dei delle sono era essere senza sopra tra questo questa
os um uma dos das na pelo pela sao foi mas se sem
het een van voor met zonder over tussen deze dit zijn worden niet ook al
""".split()) - _ENGLISH_FUNCTION_WORDS

_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ']+")


# Minimum words before the ratios mean anything, and the share of other-language function words
# that counts as positive evidence. See `looks_non_english` for the measurement behind both.
# 20 was a guess, and it left a real hole: a 13-word Spanish sentence went ungated and the
# rewriter prepended "In practice," to it — MEASURED at 1 of 16 seeds calling the structural
# rewriter directly. Re-measured against 20 SHORT English samples of 8-13 words chosen to be as
# hostile as possible (Der Spiegel, Le Monde and El Pais, El Paso, La Nina, Von Neumann, A la
# carte, Rio de Janeiro, "the del operator ... the in operator") and 10 short non-English:
#
#     min_words   English false positives   non-English caught
#         8               0/20                     9/10
#        10               0/20                     7/10
#        12               0/20                     0/10
#        20               0/20                     0/10
#
# 8 costs nothing on the side that matters and closes most of the hole. The floor cannot go much
# lower: below ~8 words a single article decides the ratio.
_LANG_MIN_WORDS = 8
_OTHER_FUNCTION_WORD_FLOOR = 0.12


def looks_non_english(text: str) -> bool:
    """True when the text is confidently a Latin-script language that is not English.

    `_language_supported` below is SCRIPT-based, so Chinese is caught and German is not. That
    mattered: the rewriter injected English words into Latin-script text it could not read —
    MEASURED end to end on a German paragraph and a French one, every word the loop changed:

        Die Studie ...        ->  Of course, die Studie ...
        ... erheblich. Die    ->  ... erheblich, and die
        ... sur le site. Les  ->  ... sur le site, and les

    An English opener from the pool, and `and` as a clause joiner, welded onto German and French.

    Absence of English is NOT enough to decide this, and trying it first is what showed why. The
    share of English function words alone does not separate the classes — a run of English headings
    scores 0.000 and Italian scores 0.125 — so any single bar either lets German through or
    disables the rewriter on English headings, and the second is far worse than the first.

    So this requires POSITIVE evidence of another language: enough other-language function words,
    and more of them than English ones. MEASURED over 10 deliberately awkward English samples
    (headings, terse lists, code-heavy prose, a passage quoting German, one full of French and
    German proper nouns) and 6 non-English:

        floor   English false positives   non-English caught
        0.10            0/10                     6/6
        0.12            0/10                     6/6
        0.15            0/10                     5/6   (Portuguese, 0.136)
        0.20            0/10                     5/6

    0.12 sits inside the margin on both sides. The `more than English` half is what does the real
    work: the proper-noun sample scores 0.130 on other-language words and is not flagged, because
    its English share is 0.261.

    Conservative by construction. A false positive silences the rewriter on English, which is worse
    than the damage it prevents, so anything short of confident is treated as English.
    """
    if not isinstance(text, str):
        # Same contract as score_tells/score_text: a clean TypeError naming the
        # input type, not an internal regex error from _SENTINEL_RE.sub.
        raise TypeError(f"text must be str, got {type(text).__name__}")
    # Strip sentinels before counting. The loop hands the rewriter MASKED text, and a sentinel is
    # not a word in any language — but `⟦HZ0000⟧` contributes "HZ" to `_WORD_RE`, so each locked
    # span both removes real words from the count and adds a token that dilutes the ratio. MEASURED
    # on the same Spanish paragraph before and after locking 5 spans: other-language share 0.231 ->
    # 0.100, straight through the 0.12 floor. Removing them restores the raw ratio.
    text = _SENTINEL_RE.sub(" ", text)
    words = [w.lower().strip("'") for w in _WORD_RE.findall(text)]
    words = [w for w in words if w]
    if len(words) < _LANG_MIN_WORDS:
        return False
    english = sum(1 for w in words if w in _ENGLISH_FUNCTION_WORDS) / len(words)
    other = sum(1 for w in words if w in _OTHER_FUNCTION_WORDS) / len(words)
    return other >= _OTHER_FUNCTION_WORD_FLOOR and other > english


def _language_supported(text: str) -> bool:
    """False when this English catalogue cannot read the text — wrong script OR wrong language.

    Compared against Latin letters rather than against total length, so punctuation, digits and
    whitespace do not sway it. A passage that is majority non-Latin gets a warning; a mostly-English
    passage quoting a Chinese phrase does not.

    The Latin-script clause was added after finding that this module held two answers to the same
    question. `looks_non_english` — written for the rewriter, after English openers and an English
    "and" were found welded into German and French sentences — says German is not English. This
    function said German was supported, and `score_tells` reported this one:

        german    language_supported=True    tells_per_100w=0.00
        french    language_supported=True    tells_per_100w=0.00
        japanese  language_supported=False   tells_per_100w=0.00

    The field exists precisely to stop that zero being read as a clean bill of health — the
    `languages` module says so in as many words, about Korean. German produces the identical
    misleading zero, and Latin-script non-English is far the commoner case of the two.

    This widens what `False` means: not "wrong script" but "cannot be read". The REST schema's
    description is updated with it, since that description is the contract a caller reads.
    """
    if text.strip() and looks_non_english(text):
        return False
    non_latin = len(_NON_LATIN_RE.findall(text))
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    # No letters at all is the same situation as the wrong script, and it reached the opposite
    # answer: digits, punctuation and emoji are neither Latin nor non-Latin, so `non_latin == 0`
    # returned True for text the catalogue cannot read a word of. MEASURED on a punctuation-only
    # string:
    #
    #     tells 7   by_category {'rule_of_three': 1, 'semicolon_crutch': 6}   words 0
    #
    # Six "semicolon crutches" counted in `;;; ;;;`. A semicolon crutch is a prose habit, and there
    # is no prose here — the finding is the catalogue matching its own punctuation patterns against
    # punctuation. `humanness` already abstains on these inputs and returns 50.0; this is the same
    # judgement, on the same text, from the surface that was disagreeing with it.
    if latin == 0:
        return False
    if non_latin == 0:
        return True
    return latin > non_latin


def _claimed_spans(text: str) -> list[tuple[int, int, str, str]]:
    """Pattern tell spans ``text`` actually counts: (start, end, category, matched).

    Count by SPAN, not by pattern, so one stretch of text can only ever be one tell. Several words
    legitimately appear in two categories — "boasts" is AI vocabulary AND an inflated copula;
    "showcasing" is AI vocabulary AND the head of a participial trailer — and counting both fired
    the same token twice, breaking the module's stated invariant that "a single phrase must count
    in exactly one category, never two". Deleting the duplicate words is the wrong fix: they are
    real tells in constructions the more specific pattern does not match ("platform showcasing
    wins" has no comma, so the trailer pattern never fires).

    The LONGEST match claims the span, not the first category in the list — _CATEGORIES is ordered
    for readability, not specificity, and ai_vocab sits first, so list order would let a single
    word beat the multi-word construction that contains it.

    Extracted from ``score_tells`` so the probe-set restriction in
    ``untell.attacks.word_importance`` can ask "which words sit inside a counted tell span?"
    without reimplementing (and silently drifting from) the claiming rule.

    COMPLEXITY FIX (2026-08-21): the original overlap check was an O(S²) linear scan —
    ``any(start < c_end and end > c_start for c_start, c_end, … in claimed)`` — where S is the
    total number of matched spans.  PROFILED on a 108KB AI-tell-dense input: 4 000 spans produced
    8 002 000 Python genexpr iterations (2 000 per span) and took 8.4 s, representing 72% of the
    total ``score_tells`` runtime.  Scaling to 1 MB would have required ~800 M iterations (~800 s).

    Replaced with a ``bytearray`` over the text's character positions.  The overlap check becomes
    ``bytearray.find(b"\\x01", start, end) >= 0`` — a C-speed memchr scan, O(span_length) not
    O(claimed_so_far) — and the claim writes ``blocked[start:end] = b"\\x01" * (end - start)``,
    also C-speed.  For typical tell spans (5–20 chars) the check is O(1) amortised; in the worst
    case it is O(text_length) total (each character checked at most once if non-overlapping spans
    tile the text).  Space cost: one byte per character of text, bounded by ``_MAX_INPUT_CHARS``
    in the REST path and by document size elsewhere.

    BEFORE/AFTER on identical 108KB input (median of 5 runs, 19 sibling agents loaded):
        _claimed_spans only:  3.155 s  →  0.011 s   (286× faster)
        score_tells total:    7.4 s    →  1.9 s      (3.9× faster; regex/scrub now dominate)
    Output is byte-for-byte identical to the old implementation — same spans, same order — so
    all callers (score_tells and word_importance._word_importance_set) are unaffected.
    """
    spans: list[tuple[int, int, str, str]] = []
    for name, pat in _CATEGORIES:
        for m in pat.finditer(text):
            spans.append((m.start(), m.end(), name, m.group(0)))
    spans.sort(key=lambda s_: (-(s_[1] - s_[0]), s_[0]))  # longest first, then leftmost

    # One byte per character; 0 = unclaimed, 1 = already claimed by a longer (or equal) span.
    # bytearray.find(b"\x01", start, end) is a C-speed memchr — never touches Python between
    # start and end — so the overlap check is O(span_length) rather than O(claimed_so_far).
    blocked = bytearray(len(text)) if text else bytearray()
    claimed: list[tuple[int, int, str, str]] = []
    for start, end, name, matched in spans:
        if blocked.find(b"\x01", start, end) >= 0:
            continue  # this text is already counted as a richer tell
        blocked[start:end] = b"\x01" * (end - start)
        claimed.append((start, end, name, matched))
    return claimed


def score_tells(text: str, *, include_matches: bool = False) -> dict:
    """Count AI tells in ``text`` per the catalogue. Lower is more human-reading."""
    if not isinstance(text, str):
        # Fuzz-found: bytes input raised 'cannot use a string pattern on a bytes-like
        # object' from deep inside scrub_hidden — the same style of internal leak
        # score_text's guard exists for. Name the contract instead.
        raise TypeError(f"text must be str, got {type(text).__name__}")
    # Every multi-word pattern in the catalogue is written with a literal space, so a non-breaking
    # space silently defeats it: "in conclusion" does not match "in conclusion". MEASURED on a
    # 37-word AI paragraph, replacing every space with U+00A0, 5 tells became 3 and humanness moved
    # 37.4 -> 43.9. That is an under-report for anyone pasting out of Word, and a one-keystroke
    # evasion of our own catalogue for anyone who notices.
    #
    # Folded here rather than per-pattern for the reason the scoring path learned the hard way: a
    # rule applied in some places is a rule that will be missed in the rest.
    #
    # Invisible characters are stripped for a harder reason than tidiness: they shatter the word
    # count, and every number here is derived from it. MEASURED on a 209-word HC3 answer with a
    # zero-width space inserted between every character — which is what a soft hyphen from a PDF
    # extraction or a steganographic watermark looks like to the tokeniser:
    #
    #     plain            209 words,  23 tells, 11.0 per 100w
    #     zero-width       889 words, 436 tells, 49.0 per 100w   <- 433 of them repeated_phrasing
    #     scrubbed first   209 words,  23 tells, 11.0 per 100w   <- identical to plain
    #
    # Single-character fragments repeat constantly, so trigram repetition explodes. "889 words" is
    # not a surprising description of a 209-word text, it is a false one, and everything computed
    # from it inherits that. Soft hyphens in particular are not an attack — justified PDF text is
    # full of them.
    #
    # `scrub_hidden` rather than a narrower local stripper, deliberately: it already distinguishes
    # an orphan zero-width joiner from one holding an emoji sequence together, and writing a second
    # nearly-identical stripper here is the exact mistake Result 51 recorded — a rule applied in
    # some places is a rule that will be missed in the rest.
    from untell.attacks import scrub_hidden

    text = fold_unicode_spaces(scrub_hidden(text))
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

    # Count by SPAN, not by pattern — see _claimed_spans for why a single phrase must count in
    # exactly one category, and how the longest match wins the overlap.
    for _, _, name, matched in _claimed_spans(text):
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
        # Two different reasons, and saying the wrong one sends the reader at the wrong fix. "mostly
        # non-Latin script" is true of a Chinese paragraph and false of `;;; ...`, which has no
        # script at all — the same distinction `humanness` already draws between "too short" and
        # "not English", and for the same reason: the message is what a reader acts on.
        # THREE reasons, not two. A Latin-script language that is not English is the common case in
        # this repo's own examples, and the two-way split described it as "mostly non-Latin script",
        # which is false of German and is exactly the wrong-reason failure this branch exists to
        # prevent: a reader told their Latin-script paragraph is non-Latin has been sent at a fix
        # that does not exist. MEASURED on a four-sentence German paragraph — tells 0, and the
        # caveat said "mostly non-Latin script". `score`, `run` and the REST schema all already say
        # "a Latin-script language other than English" for the same input; this is the surface that
        # disagreed with them.
        from untell.languages import dominant_script

        has_letters = any(ch.isalpha() for ch in text)
        if not has_letters:
            why = "the text contains no letters at all, so there is no prose to read"
        elif dominant_script(text) == "Latin":
            why = "the text reads as a Latin-script language other than English"
        else:
            why = "the text is mostly non-Latin script"
        result["warning"] = (
            f"this catalogue is English-only, and {why} — a score of "
            f"{total} tells means the patterns did not apply, NOT that the text reads as human"
        )
        logger.warning(result["warning"])
    # A rate per 100 words computed from a handful of words is not an estimate of anything: the
    # smallest non-zero value a text of N words can report is 100/N, so the number is quantised far
    # above the scale it is meant to be read on. `Moreover.` is one word and one tell, and reports
    # 100.0 per 100 words — against the measured corpus means of 0.551 for human text and 7.335 for
    # AI text (Result 45). A reader comparing those would conclude something catastrophic about a
    # single word.
    #
    # 14 is not a round number, it is the point where the arithmetic stops misleading: 100/14 = 7.1,
    # just under the AI mean. Below it, ANY single tell reports a rate above the AI corpus average
    # no matter what the text says.
    #
    # Only warned when the rate is actually non-zero. Short text usually produces no tells at all —
    # measured over 60 HC3 pairs truncated to 5 words, the mean rate is 0.00 for human and 0.67 for
    # AI — and a caveat on a harmless 0.0 would be noise that teaches readers to skip warnings.
    if result["words"] < _MIN_WORDS_FOR_A_RATE and total > 0:
        rate_warning = (
            f"{result['words']} words: `tells_per_100w` is {result['tells_per_100w']}, but a rate "
            f"per 100 words from {result['words']} words is quantised — one tell alone reports "
            f"{100 / max(result['words'], 1):.0f}. Compare the COUNT ({total}), not the rate; the "
            "corpus means it would be read against are 0.642 human and 7.320 AI (100 HC3 pairs, >=60 words)."
        )
        result["warning"] = (
            f"{result['warning']} Also: {rate_warning}" if result.get("warning") else rate_warning
        )
        # Reported in the dict, deliberately NOT logged. The language warning logs because
        # non-English input is rare and a user hitting it needs telling once. Short text is not
        # rare — `score_sentences` calls this per sentence, and sentences are almost always under
        # 14 words, so a log line here would fire on nearly every sentence of every document. The
        # CLI renders `warning` for the one-shot case, which is where a human is reading.
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
    elif not r.get("warning"):
        # NOT "no catalogued tells found" when a warning applies — that sentence reads as a clean
        # bill of health, and on non-Latin input it would be reporting the catalogue's blindness as
        # the text's virtue.
        lines.append("no catalogued tells found.")

    # Its own branch, not an `elif` on the category list. The warning used to print ONLY when no
    # tell fired, so any text that both matched a pattern and warranted a caveat showed the
    # categories and swallowed the caveat. MEASURED on a 9-word input: `tells: 2`,
    # `tells_per_100w: 22.22`, and the warning that says a rate from 9 words is quantised — "one
    # tell alone reports 11" — never reached the reader, who saw a rate 3x the AI corpus mean of
    # 7.320 presented without qualification.
    if r.get("warning"):
        lines.append(f"WARNING: {r['warning']}")
    # `--matches` promises the substrings in its help text, and the result dict always carried
    # them (as did --json), but the plain renderer dropped them — `untell tells --matches <text>`
    # printed byte-identical output to the no-flag call, a silent no-op in the default mode.
    # The matches are the detail under the category counts, so they print right after them.
    if r.get("matches"):
        lines.append("matched spans:")
        for k, v in sorted(r["matches"].items(), key=lambda kv: -len(kv[1])):
            lines.append(f"  {k:22} " + ", ".join(f'"{s}"' for s in v))
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
        from untell.scripts.io_utils import read_file_or_exit

        text = read_file_or_exit(args.file)
    elif args.text:
        text = args.text
    else:
        # None means stdin is a terminal. Reading it would block until the user sent EOF, with no
        # prompt and no output — the command looks hung when what they wanted was the usage line.
        from untell.scripts.io_utils import read_stdin_or_none

        piped = read_stdin_or_none()
        if piped is None:
            print(json.dumps({"error": "no input: pass text, --file PATH, or pipe to stdin"}))
            return 2
        text = piped
    if not text.strip():
        print(json.dumps({"error": "empty input"}))
        return 2

    result = score_tells(text, include_matches=args.matches)
    print(json.dumps(result, ensure_ascii=True, indent=2) if args.json else _render(result))
    # 2 when the catalogue could not read the text at all, the same code and reasoning
    # `untell-verify` and `untell-score` use: nothing ran is a configuration problem with the input,
    # not a verdict about it.
    #
    # The result already says so — `language_supported: false`, and the warning spells out that "a
    # score of 0 tells means the patterns did not apply, NOT that the text reads as human". The exit
    # code said the opposite. MEASURED on a Chinese paragraph: `tells: 0`, `words: 0`, exit **0**, so
    # a CI job reading the status of `untell-tells` was told the cleanest possible result on text
    # this catalogue cannot match a single pattern against.
    #
    # The tell COUNT never changes the exit code — a document with forty tells is a report, not a
    # failure. `untell-verify` is the only command here that returns a verdict.
    return 2 if result.get("language_supported") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
