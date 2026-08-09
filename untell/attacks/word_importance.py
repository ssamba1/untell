"""Word-importance-ranked synonym substitution (HMGC / TextFooler style).

Surgical alternative to whole-text rewriting: rank each word by how much it drives the detector
score (the drop when the word is removed), then swap the highest-importance words for synonyms,
keeping only swaps that *lower* the score. Minimal surface change, maximum signal reduction — useful
when the similarity budget is tight or as a cheap CPU-only pre/post pass around the LLM loop.

Scores via the lite detector by default (fast, stdlib). Synonyms come from a built-in AI-vocabulary
map, extended with WordNet when ``nltk`` is installed. No GPU, no API key.
"""

from __future__ import annotations

import re

# Run-as-file support (zero-dep lite tier): when this file is executed directly
# rather than imported as part of the `untell` package, put the directory that
# *contains* the package on sys.path so `import untell` resolves from any cwd.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

from untell.scripts.score import DEFAULT_THRESHOLD, batch_score_texts, score_text

# Hyphenated compounds are ONE token. With a bare [A-Za-z]+ the table's hyphenated keys
# ("cutting-edge", "state-of-the-art", "world-class", "best-in-class", "top-tier", "next-level")
# could never be looked up — every one of them was unreachable, while the comment on _SYN claimed
# phrases were matched. They are among the most recognisable AI tells in the catalogue.
_WORD = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)*")

# Formulaic AI vocabulary -> plainer human alternatives (the words detectors + competitors target).
# Each entry must be a single word or short phrase that is a natural, less-AI-sounding replacement.
# Keep entries lowercased, and every key must be a single token as _WORD defines one: letters,
# optionally hyphen-joined. A key containing a SPACE can never be looked up, because both consumers
# (synonyms() here and _plain_register in rewriter/structural.py) key on individual tokens —
# test_word_importance.py enforces this, since a dead entry looks exactly like a live one.
_SYN: dict[str, list[str]] = {
    # --- Tells-catalog AI vocab (ai-tells.md §1-2) ---
    "delve": ["dig", "look", "go deep"],
    "leverage": ["use", "lean on", "tap into"],
    # INFLECTIONS. The map is keyed on exact tokens — both consumers look up `_WORD` matches
    # verbatim — so "leverage" being present does nothing for "leverages", which appears 107 times
    # across 300 real AI texts at 15x the human rate. MEASURED, ten inflected forms of existing
    # keys were missing while their stems were covered, in the transform the ablation shows is
    # worth 3-5x every other one. A stem without its inflections is a half-connected entry that
    # looks complete in the table.
    #
    # Every substitute carries the SAME inflection as its key, or the swap produces "the system use
    # robust methods". test_inflected_forms_agree_with_their_key enforces that.
    "leverages": ["uses", "leans on", "taps into"],
    "leveraging": ["using", "leaning on", "tapping into"],
    "utilizes": ["uses"],
    # "proving" dropped: it upgrades the claim. See the note above "demonstrate" below.
    "demonstrating": ["showing", "indicating"],
    "achieving": ["reaching", "hitting"],
    "required": ["needed"],
    "requiring": ["needing"],
    "evaluated": ["tested", "checked"],
    "introducing": ["adding", "bringing in"],
    "outperforming": ["beating", "besting"],
    "utilize": ["use"],
    "utilizing": ["using"],
    "robust": ["solid", "sturdy", "strong"],
    "seamless": ["smooth", "easy"],
    "seamlessly": ["smoothly", "easily"],
    "tapestry": ["mix", "array", "range"],
    "testament": ["proof", "sign", "mark"],
    "realm": ["area", "space", "field"],
    "landscape": ["scene", "setting", "field"],
    "underscore": ["show", "highlight", "stress"],
    "underscores": ["shows", "highlights"],
    "underscoring": ["showing", "highlighting"],
    "pivotal": ["key", "central", "critical"],
    # No "vital" here, no "remarkable" under exceptional, no "pivotal" under groundbreaking:
    # each of those is ITSELF in the ai_vocab catalogue (scripts/tells.py `_AI_VOCAB`), so the
    # swap was a lateral move that left the tell in place and the detector still firing on the
    # same span. Four entries carried such a substitute; test_every_substitute_is_not_itself_a_tell
    # now rejects them at import time, because a dead-end substitute looks exactly like a live one.
    "crucial": ["key", "central", "critical"],
    "vital": ["key", "essential", "needed"],
    "foster": ["build", "grow", "encourage"],
    "fostering": ["building", "growing", "encouraging"],
    "garner": ["get", "win", "earn"],
    "garnered": ["got", "won", "earned"],
    "bolster": ["boost", "strengthen", "prop up"],
    "elevate": ["raise", "lift", "boost"],
    "embark": ["start", "begin", "set out"],
    "harness": ["use", "tap", "put to work"],
    "harnessing": ["using", "tapping", "putting to work"],
    "unlock": ["open", "release", "free up"],
    "unleash": ["release", "let loose", "set off"],
    "spearhead": ["lead", "head", "drive"],
    "paramount": ["key", "top", "critical"],
    "plethora": ["wealth", "lots", "many"],
    "myriad": ["countless", "many", "scores of"],
    "multifaceted": ["many-sided", "complex", "varied"],
    "nuanced": ["subtle", "fine-grained", "careful"],
    "intricate": ["complex", "detailed", "elaborate"],
    "intricacies": ["details", "complexities", "workings"],
    "meticulous": ["careful", "thorough", "painstaking"],
    "meticulously": ["carefully", "thoroughly", "closely"],
    "comprehensive": ["full", "broad", "wide-ranging"],
    "vibrant": ["lively", "bright", "active"],
    "bustling": ["busy", "lively", "humming"],
    "noteworthy": ["notable", "striking", "worth noting"],
    "groundbreaking": ["pioneering", "landmark", "first-of-its-kind"],
    "transformative": ["powerful", "far-reaching", "sweeping"],
    "innovative": ["new", "fresh", "original"],
    "boasts": ["has", "offers", "can claim"],
    "nestled": ["set", "situated", "tucked"],
    "profound": ["deep", "far-reaching", "major"],
    "holistic": ["whole-picture", "full-spectrum", "broad"],
    "actionable": ["usable", "practical", "concrete"],
    "impactful": ["powerful", "striking", "meaningful"],
    "streamline": ["simplify", "smooth", "speed up"],
    "empower": ["enable", "help", "equip"],
    # "helpful" was here and is not a participle: "the tool is empowering users" became "the
    # tool is helpful users". Caught by the inflection-agreement invariant, which is the
    # value of scoping that check to verb forms rather than to every word ending in -ing.
    "empowering": ["enabling", "freeing", "helping"],
    "revolutionize": ["transform", "overhaul", "shake up"],
    "resonate": ["connect", "ring true", "strike a chord"],
    "encompass": ["cover", "span", "include"],
    "paradigm": ["model", "pattern", "framework"],
    "cornerstone": ["foundation", "bedrock", "base"],
    "burgeoning": ["growing", "expanding", "rising"],
    "quintessential": ["typical", "classic", "perfect example of"],
    "overarching": ["central", "blanket", "broad"],
    "synergy": ["collaboration", "combined effect", "teamwork"],
    "endeavor": ["effort", "undertaking", "pursuit"],
    "commence": ["start", "begin", "kick off"],
    "illuminate": ["clarify", "explain", "spell out"],
    "cultivate": ["develop", "build", "grow"],
    "catalyze": ["spark", "trigger", "set off"],
    "galvanize": ["rally", "rouse", "jolt"],
    "augment": ["boost", "add to", "supplement"],
    "elucidate": ["clarify", "explain", "spell out"],
    "interplay": ["interaction", "exchange", "give-and-take"],
    "underpin": ["support", "undergird", "back"],
    "compelling": ["powerful", "convincing", "strong"],
    # "record" dropped: "record accuracy" and "unprecedented accuracy" are different claims —
    # the first is a ranking against past results, the second says there is no precedent.
    "unprecedented": ["unmatched", "unheard-of"],
    "exceptional": ["outstanding", "top-notch", "first-rate"],
    "remarkable": ["striking", "impressive", "notable"],
    "sophisticated": ["advanced", "refined", "polished"],
    "invaluable": ["priceless", "indispensable", "worth a lot"],
    "unwavering": ["steady", "firm", "constant"],
    # "growable" dropped: found by reading output ("to aid growable outcomes"). A word you can
    # parse and would never choose is a fingerprint, not a neutral swap.
    "scalable": ["expandable", "adaptable"],
    "bespoke": ["custom", "tailored", "made-to-order"],
    "showcasing": ["showing", "highlighting", "presenting"],
    "showcase": ["show", "highlight", "present"],
    "reimagine": ["rethink", "recast", "re-envision"],
    "reimagining": ["rethinking", "recasting"],
    "world-class": ["top-class", "elite", "first-rate"],
    "cutting-edge": ["leading", "advanced", "frontier"],
    "state-of-the-art": ["advanced", "modern", "top of the line"],
    "best-in-class": ["top", "leading", "finest"],
    "top-tier": ["top-level", "elite", "premier"],
    "next-level": ["higher", "better", "step up"],
    "turnkey": ["ready-made", "pre-built", "ready to use"],
    "supercharge": ["boost", "turbocharge", "ramp up"],
    "unparalleled": ["unmatched", "peerless", "second-to-none"],
    "trailblazing": ["pioneering", "path-breaking", "trendsetting"],
    # --- Academic / paper boilerplate -----------------------------------------------------------
    # Added 2026-08-07 to give the repetition tell something it can act on. MEASURED across 60 RAID
    # AI abstracts, the repeated-trigram mass breaks down as:
    #
    #     82%  DOMAIN TERMS      "medical image segmentation" x42, "local contrastive learning"
    #     18%  boilerplate       "we propose a", "a novel approach", "state of the art",
    #                            "the proposed method", "the effectiveness of"
    #      2%  reachable by the synonym map as it stood
    #
    # The 82% is untouchable on purpose: repeating the subject IS the meaning, and a rewriter that
    # varied it would be changing what the text is about — the meaning gates would veto it, rightly.
    # The 18% is pure template, carries no domain content, and was simply missing from the map. It
    # is the only part of the strongest tell in the catalogue a meaning-preserving rewriter can
    # legitimately reach.
    # NOT propose/proposes/proposed. They are INTENTION hedges (scripts/hedges.py), and swapping
    # one for a word outside that class reads as intent becoming achievement. MEASURED: adding
    # them drove the hedge gate's veto rate to 20% of all candidates — every hedge veto in a
    # 150-candidate sample — while similarity, numerals and roles vetoed 0%, 0% and 2%. Widening
    # the hedge class instead is worse: "suggest" is an EVIDENTIAL hedge in "the results suggest
    # a link" and an intention verb in "we suggest a method", so forcing it into one class breaks
    # the other. The gate is right; the substitution was the mistake.
    "novel": ["new", "fresh", "original"],
    # "way" and "route" dropped: they cannot head a noun compound. "An unsupervised
    # segmentation approach" became "An unsupervised segmentation way", which the repaired
    # contradiction gate flagged before any human read it.
    "approach": ["method", "technique"],
    "approaches": ["methods", "techniques"],
    "method": ["approach", "technique", "way"],
    "methods": ["approaches", "techniques", "ways"],
    "framework": ["setup", "structure", "system"],
    # NOT "usefulness": it is itself a nominalisation, so the swap leaves the signal it was meant
    # to move exactly where it was. Same shape as the four synonyms that were themselves ai_vocab,
    # in a dimension the tell catalogue does not cover — MEASURED, AI text carries 36% more
    # nominalisations per 100 words than human text answering the same prompt (2.575 vs 1.896).
    "effectiveness": ["success", "value", "how well it works"],
    # Register nominalisations, substituted for plain non-nominal words. Deliberately NOT
    # "robustness", "contribution", "development", "importance" or "complexity": in a paper each of
    # those carries meaning — a contribution IS the novel claim, robustness IS a measured property —
    # and swapping them changes what the text says rather than how it reads.
    #
    # Only 18.5% of the nominalisation excess is register at all; the other 81.5% is domain content
    # (segmentation, attention, detection, ablation), which is the same 82/18 split the repeated-
    # phrasing ceiling has. The reachable share is small by nature, not by neglect.
    # Words the corpus shows AI over-using with no entry at all, found by the same sweep that
    # produced the inflection fix. Each is REGISTER, not content: "united" (99x) is excluded because
    # it is "United States", "treatment" and "efficiency" because they are subject matter, and
    # "contributions" because in a paper it names the novel claim.
    "analyze": ["study", "examine", "look at"],
    "analyzed": ["studied", "examined", "looked at"],
    "analyzing": ["studying", "examining", "looking at"],
    "summarized": ["summed up", "boiled down"],
    "combines": ["mixes", "brings together", "joins"],
    "incorporates": ["includes", "builds in", "takes in"],
    "applying": ["using", "putting to work"],
    "involves": ["means", "needs", "takes"],
    "components": ["parts", "pieces"],
    "accurately": ["correctly", "closely"],
    "traditional": ["older", "standard", "long-standing"],
    "variety": ["range", "mix", "spread"],
    "utilization": ["use"],
    "utilisation": ["use"],
    "implementation": ["rollout", "build"],
    "improvement": ["gain", "boost", "step up"],
    "combination": ["mix", "blend", "pairing"],
    "extensive": ["wide", "broad", "thorough"],
    "outperforms": ["beats", "does better than", "tops"],
    "outperform": ["beat", "do better than", "top"],
    "present": ["show", "give", "set out"],
    "presents": ["shows", "gives", "sets out"],
    "introduce": ["add", "bring in", "set out"],
    "introduces": ["adds", "brings in", "sets out"],
    "achieve": ["reach", "hit", "get"],
    "achieves": ["reaches", "hits", "gets"],
    "strengths": ["advantages", "merits", "plus points"],
    "benchmark": ["test", "reference", "yardstick"],
    "benchmarks": ["tests", "references", "yardsticks"],
    "evaluate": ["test", "assess", "check"],
    "evaluates": ["tests", "assesses", "checks"],
    "validate": ["confirm", "check", "bear out"],
    "substantial": ["large", "sizable", "big"],
    # --- Transition words (§3, §8) ---
    "furthermore": ["also", "and", "plus"],
    "moreover": ["also", "what is more", "and"],
    "additionally": ["also", "plus", "on top of that"],
    "consequently": ["so", "as a result", "because of that"],
    "therefore": ["so", "that is why", "which is why"],
    "accordingly": ["so", "in line with that", "to match"],
    "hence": ["so", "for that reason", "that is why"],
    "subsequently": ["later", "next", "afterward"],
    "nevertheless": ["still", "even so", "yet"],
    "nonetheless": ["still", "even so", "yet"],
    "notably": ["especially", "in particular", "most notably"],
    "importantly": ["mostly", "above all", "significantly"],
    "ultimately": ["in the end", "finally", "eventually"],
    "overall": ["in the end", "all told", "on the whole"],
    "essentially": ["basically", "at bottom", "put simply"],
    # "possibly" dropped: it downgrades. "arguably the best" ASSERTS and invites dispute;
    # "possibly the best" concedes uncertainty. "one could say" dropped for grammar — this is
    # an in-place adverb substitution, so it produced "This is one could say the strongest
    # result." One survivor is correct here: "arguably" has no close single-word synonym, and
    # inventing one to pad the list is how the other three got in.
    "arguably": ["debatably"],
    # --- High-signal verbs to flatten ---
    "numerous": ["many", "plenty of", "lots of"],
    "significant": ["real", "major", "big"],
    "significantly": ["sharply", "a lot", "greatly"],
    "fundamentally": ["deeply", "at root", "basically"],
    # "all sorts of" dropped: it overclaims. "applied to various tasks" says a range,
    # "applied to all sorts of tasks" says every kind. Found by the chunked contradiction
    # gate scoring a real rewrite at 0.606 — I had seen this entry in the epistemic scan
    # and waved it through as a register shift, and the gate was right where I was not.
    "various": ["different", "assorted"],
    "essential": ["needed", "key", "necessary"],
    "facilitate": ["help", "ease", "aid"],
    "facilitates": ["helps", "eases", "aids"],
    # The whole "demonstrate" family had two defects at once, and the meaning gates catch
    # neither. "prove" upgrades the epistemic strength of a claim — in a paper, "our
    # experiments demonstrate X" and "our experiments prove X" are different assertions, and
    # entailment scores that swap at 0.993 with 0.0009 contradiction, so it passes every gate
    # this project has. "display" is simply ungrammatical in the construction the key appears
    # in: "the experiments display that the method works" — display takes an object, not a
    # that-clause. "indicate" preserves both the strength and the syntax.
    "demonstrate": ["show", "indicate"],
    "demonstrates": ["shows", "indicates"],
    "enhance": ["improve", "boost", "strengthen"],
    "enhances": ["improves", "boosts", "strengthens"],
    "optimize": ["tune", "sharpen", "improve"],
    "optimizes": ["tunes", "sharpens", "improves"],
    "represents": ["is", "stands for", "means"],
    "enables": ["lets", "allows", "makes possible"],
    "enabled": ["let", "allowed", "made possible"],
    "increasingly": ["more and more", "ever more"],
    # --- Clichés that collapse to a single word ---
    "however": ["but", "though", "by contrast"],
    "thus": ["so", "this way", "in this way"],
    # --- Additional high-frequency 2024-2026 AI tells ---
    "navigate": ["handle", "work through", "deal with"],
    "navigating": ["handling", "working through", "dealing with"],
    "grapple": ["wrestle", "struggle", "contend"],
    "beacon": ["signal", "guide", "light"],
    "trajectory": ["path", "course", "direction"],
    "salient": ["key", "main", "standout"],
    "granular": ["detailed", "fine-grained", "specific"],
    "orchestrate": ["arrange", "coordinate", "run"],
    "orchestrating": ["arranging", "coordinating", "running"],
    "curate": ["select", "pick", "assemble"],
    "curated": ["selected", "hand-picked", "chosen"],
    "amplify": ["boost", "raise", "magnify"],
    "ecosystem": ["network", "system", "environment"],
    "dichotomy": ["split", "divide", "contrast"],
    "juxtapose": ["contrast", "compare", "set against"],
    "trove": ["hoard", "stash", "collection"],
    "veritable": ["real", "true", "genuine"],
    "aforementioned": ["earlier", "above", "that"],
    "delves": ["digs", "looks", "explores"],
    "delving": ["digging", "looking", "exploring"],
    "penchant": ["taste", "liking", "fondness"],
    "adept": ["skilled", "capable", "able"],
    "prowess": ["skill", "ability", "talent"],
    "hallmark": ["sign", "mark", "feature"],
    "poised": ["ready", "set", "positioned"],
    "align": ["match", "fit", "line up"],
    "aligns": ["matches", "fits", "lines up"],
    "aligned": ["matched", "in step", "lined up"],
    # --- Formal -> plain simplifications (raise perplexity toward the human range; research Pri-6).
    # Single words only: the surgical path ranks/replaces one token at a time, so multi-word keys
    # would never match — they belong in a phrase-level transform, not here. ---
    "obtain": ["get", "gain"],
    "obtained": ["got", "gained"],
    "purchase": ["buy"],
    "purchased": ["bought"],
    "assist": ["help", "aid"],
    "require": ["need"],
    "requires": ["needs"],
    "attempt": ["try"],
    "terminate": ["end", "stop"],
    "sufficient": ["enough"],
    "additional": ["more", "extra"],
    "approximately": ["about", "around", "roughly"],
    "regarding": ["about", "on"],
    "prioritize": ["favor", "put first", "focus on"],
    "endeavour": ["effort", "try"],
    "ascertain": ["find out", "learn", "check"],
    "utilise": ["use"],
    "commencing": ["starting", "beginning"],
    "aforesaid": ["earlier", "that"],
}


_WORDNET_UNSET = object()
_wordnet_cache = _WORDNET_UNSET  # _WORDNET_UNSET = not probed; None = unavailable; else the module


def _wordnet():
    """Return nltk's wordnet corpus, or None. Probed once.

    `synonyms()` used to `from nltk.corpus import wordnet` on every call, inside a try/except. That
    reads as free when nltk is missing — but Python does NOT cache failed imports, so every call
    re-scanned the whole of sys.path. MEASURED in a warm 3-iteration best-of-3 loop profile:

        7389 find_spec calls, all for 'nltk', ~0.6s of pure import machinery
        (36720 _path_join, 7344 nt.stat)

    One probe per process instead. Same lazy-sentinel pattern as `quality._st_model` and
    `preserve`'s NER guard: _UNSET means not yet probed, None means probed and absent.
    """
    global _wordnet_cache
    if _wordnet_cache is not _WORDNET_UNSET:
        return _wordnet_cache
    try:
        from nltk.corpus import wordnet as _wn

        _wn.synsets("test")  # the corpus is a lazy loader; touch it so a missing download fails here
        _wordnet_cache = _wn
    except Exception:
        _wordnet_cache = None
    return _wordnet_cache


def synonyms(word: str) -> list[str]:
    """Synonym candidates for ``word`` — built-in map plus WordNet (if nltk is available)."""
    w = word.lower()
    out = list(_SYN.get(w, []))
    wordnet = _wordnet()
    if wordnet is not None:
        try:
            for syn in wordnet.synsets(w):
                for lemma in syn.lemmas():
                    name = lemma.name().replace("_", " ")
                    if name.lower() != w and name.replace(" ", "").isalpha():
                        out.append(name)
        except Exception:
            pass
    seen: set[str] = set()
    deduped: list[str] = []
    for s in out:
        if s.lower() not in seen:
            seen.add(s.lower())
            deduped.append(s)
    return deduped[:6]


def _score_max(text: str, tier: str) -> float:
    return float(score_text(text, tier=tier)["max"]) if text.strip() else 0.0


def importance(
    text: str, tier: str = "lite", only: set[str] | None = None, base: float | None = None
) -> list[tuple[str, float]]:
    """Rank unique words by how much removing them drops the detector score (descending).

    Batches all word-removed variants through the detector ensemble in one call — O(1) detector
    *loads* instead of O(unique_words). It is still O(unique_words) forward PASSES, which is the
    real cost on the full tier, so ``only`` restricts the ranking to a caller-supplied word set.

    ``base`` is the score of ``text`` itself. Callers that already have it — surgical_substitute
    computes exactly this for its ``pre`` — should pass it: recomputing it here ran a second,
    byte-identical baseline pass over the same text at the same tier on every call.
    """
    if not text.strip():
        return []
    if base is None:
        base = _score_max(text, tier)
    # Batch score all word-removed texts with one detector-load.
    unique_words = list(dict.fromkeys(m.group(0) for m in _WORD.finditer(text)))
    if only is not None:
        unique_words = [w for w in unique_words if w.lower() in only]
    if not unique_words:
        return []
    stripped_variants = [re.sub(rf"\b{re.escape(w)}\b", "", text) for w in unique_words]
    stripped_scores = batch_score_texts(stripped_variants, tier=tier)
    scored = [(w, base - float(s["max"])) for w, s in zip(unique_words, stripped_scores)]
    return sorted(scored, key=lambda kv: -kv[1])


# Particles a multi-word replacement can end with, and which the surrounding sentence may already
# supply. A substitution is a plain one-token swap, so when both sides carry the same particle it is
# emitted twice. MEASURED on natural sentences:
#
#     "navigate through the complexities"  -> "work through THROUGH the complexities"
#     "navigating through a transition"    -> "working through THROUGH a transition"
#     "a myriad of options"                -> "a scores of OF options"
#
# 30 of the table's multi-word values end in one of these, so this is a property of the substitution
# mechanism rather than of any particular entry — the table cannot know what follows the word.
_PARTICLES = frozenset(
    {"on", "into", "in", "up", "out", "of", "to", "for", "with", "at", "from", "off", "over",
     "through", "about", "by", "down", "across"}
)

# `(?![\w-])` so "the reason for for-profit companies" is left alone: the second "for" starts a
# hyphenated compound and is not a duplicate particle at all.
_PARTICLE_ALT = "|".join(sorted(_PARTICLES, key=len, reverse=True))
# CAPTURING and optional, so a caller can read the tail back and decide whether it duplicates the
# replacement's own ending.
DUP_PARTICLE_TAIL = rf"(\s+(?:{_PARTICLE_ALT})(?![\w-]))?"


# "a myriad of X" / "a plethora of X" is a quantifier FRAME: the article and the "of" belong to the
# construction, not to the noun, so swapping the middle token alone cannot be grammatical. MEASURED
# coming out of the composite rewriter on three natural sentences:
#
#     "a myriad of options"   -> "a many of options" / "a countless of options"
#     "a plethora of evidence" -> "a lots of evidence" / "a many of evidence"
#
# The table is single-token by design (a test enforces it) and no single token fits this frame, so
# the frame has to be rewritten as a unit. _FRAME_FORM says how each replacement reads once the
# article and "of" are the substitution's responsibility; a replacement that is not listed is left
# alone entirely, because emitting nothing is better than emitting broken English.
_QUANT_FRAME_KEYS = ("myriad", "plethora")
_FRAME_FORM = {
    "many": "many",
    "countless": "countless",
    "numerous": "numerous",
    "several": "several",
    "lots": "lots of",
    "scores": "scores of",
    "plenty": "plenty of",
    "wealth": "a wealth of",
    "range": "a range of",
    "array": "an array of",
    "mix": "a mix of",
}


# Quantifier forms that work with a MASS noun. "a plethora of evidence" -> "many evidence" is
# ungrammatical for the same reason "many water" is: `many` counts, and `evidence` does not. The
# frame hides this, because "a plethora of X" reads naturally whether X is count or mass.
_MASS_SAFE_FORMS = frozenset({"lots of", "plenty of", "a wealth of"})


def _looks_plural(noun: str) -> bool:
    """Rough count-noun test: a plural head takes a counting quantifier, a mass head does not.

    Deliberately conservative — "not obviously plural" only ever RESTRICTS the options, so a wrong
    answer costs a substitution rather than producing "many evidence".
    """
    w = noun.strip().strip(".,;:!?\"')").lower()
    return w.endswith("s") and not w.endswith(("ss", "us", "is", "'s"))


def _frame_form(replacement: str, plural_head: bool = True) -> str | None:
    """How ``replacement`` reads in "a <key> of X", or None if it has no grammatical form there."""
    form = replacement if replacement.lower().endswith(" of") else _FRAME_FORM.get(replacement.lower())
    if form is None:
        return None
    if not plural_head and form.lower() not in _MASS_SAFE_FORMS:
        return None
    return form


# "a" vs "an" follows the SOUND of the next word, and a substitution changes that word. MEASURED
# coming out of the composite rewriter: "an intricate scheduling system" -> "an complex scheduling
# system", "an innovative approach" -> "an new approach".
#
# A first-letter rule is wrong in two directions ("a university", "an hour"), so both exceptions are
# listed. The vocabulary is closed — replacements come from _SYN — and a scan of all 389 distinct
# first-words found no silent-h word at all and eight /j/-onset ones, so these lists are complete
# for what can actually be emitted, plus the common cases in case the table grows.
_A_DESPITE_VOWEL = frozenset(
    """one once use used useful user using usable usage usual usually unique unit united universal
    university uniform union unified utility utilise utilize utilizing utilization euro european
    eulogy ubiquitous""".split()
)
_AN_DESPITE_CONSONANT = frozenset(
    "hour hourly honest honestly honor honour honorary honoured heir heiress".split()
)
_ARTICLE = r"(\b[Aa]n?\b[ \t]+)?"


def takes_an(word: str) -> bool:
    """Does ``word`` take "an" rather than "a"?"""
    w = word.strip().lower().lstrip("\"'([").rstrip("\"')],.;:!?")
    if not w:
        return False
    if w in _AN_DESPITE_CONSONANT:
        return True
    if w in _A_DESPITE_VOWEL:
        return False
    return w[0] in "aeiou"


def agree_article(article: str, following: str) -> str:
    """Return ``article`` corrected to agree with ``following``, keeping case and spacing."""
    head = article.rstrip()
    spacing = article[len(head):]
    want = "an" if takes_an(following) else "a"
    if head[:1].isupper():
        want = want.capitalize()
    return want + spacing


# Replacements that cannot open a sentence, however well they read mid-clause. Subordinators, not
# conjunctive adverbs: "..., though" is idiomatic; "Though, ..." is not.
_NOT_SENTENCE_INITIAL = frozenset({"though", "although", "whereas", "while"})

# Bare coordinators. These CAN open a sentence — but without the comma the conjunctive adverb they
# replaced required. MEASURED: "moreover" -> "and" turned "Moreover, stakeholders must navigate the
# landscape" into "And, stakeholders must navigate the landscape". Unlike the set above these are
# worth keeping, because deleting one character makes them correct — so the comma is consumed
# rather than the swap refused. "So," and "Yet," are idiomatic openers and are deliberately absent.
_COMMA_LESS_OPENERS = frozenset({"and", "but", "or", "nor"})


def substitute_once(text: str, word: str, replacement: str) -> str:
    """Replace the first whole-word ``word`` with ``replacement``, keeping the seam grammatical.

    Two things happen at the seam. A particle the replacement already ends in is consumed rather
    than repeated, and a quantifier frame ("a myriad of") is rewritten whole rather than having its
    middle token swapped. Only the seam is touched — a duplicated word anywhere else in the text is
    the author's and is left exactly as written.
    """
    if word.lower() in _QUANT_FRAME_KEYS:
        # group(1) is the frame to replace; group(2) is the head noun, read only to decide whether
        # a counting quantifier is allowed. Slice on group(1) so the noun is never consumed.
        frame = re.compile(rf"\b((?:a|an)\s+{re.escape(word)}\s+of)\b\s*(\S*)", re.IGNORECASE)
        match = frame.search(text)
        if match:
            form = _frame_form(replacement, plural_head=_looks_plural(match.group(2)))
            if form is None:
                return text  # no grammatical form in this frame — leave it rather than mangle it
            if match.group(1)[:1].isupper():
                form = form[:1].upper() + form[1:]
            return text[: match.start(1)] + form + text[match.end(1):]

    # A connective that is fine mid-sentence can be ungrammatical opening one. MEASURED across 240
    # real HC3 texts, "however -> though" is the single most common substitution this makes (31 of
    # 47), and every sentence-initial instance reads as broken:
    #     "However, salt is often the most effective option."
    #  -> "Though, salt is often the most effective option."
    # Subordinating "though" cannot introduce an independent clause the way "however" does. Refuse
    # the swap in that position and let the caller try its next candidate — the same "leave it
    # rather than mangle it" rule the quantifier frame above follows. Mid-sentence "though" is
    # untouched, and so is every other candidate ("but", "on the other hand", "plus", "still").
    if replacement.lower() in _NOT_SENTENCE_INITIAL:
        # Case-insensitive on purpose, though the in-tree caller passes the word's surface form
        # ("However"), which the replacement below matches case-sensitively. This is the POSITION
        # test, not the replacement: a library caller handing over the synonym map's lower-case key
        # should still be refused rather than silently allowed through a check that quietly matched
        # nothing. It costs one flag.
        opener = re.compile(
            rf"(?:^|(?<=[.!?])\s+|(?<=\n))\b{re.escape(word)}\b\s*,", re.MULTILINE | re.IGNORECASE
        )
        first = re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE)
        opening = opener.search(text)
        if first is not None and opening is not None and opening.end() > first.start() >= opening.start():
            return text

    if replacement.lower() in _COMMA_LESS_OPENERS:
        opener = re.compile(
            # After a semicolon too: "it is cheap; moreover, it is fast" -> "; and, it is fast"
            # carries the same stray comma, for the same reason — a coordinator does not take one.
            # ...and after a comma: "the costs rose, moreover, the delays grew" would otherwise
            # become "rose, and, the delays grew". Every one of these positions is the same shape —
            # a clause boundary the conjunctive adverb punctuated on BOTH sides, where the
            # coordinator replacing it takes punctuation on neither.
            rf"((?:^|(?<=[.!?;:,])\s+|(?<=\n)|(?<=^> )|(?<=\n> ))\b){re.escape(word)}\b\s*,\s*",
            re.MULTILINE | re.IGNORECASE,
        )
        match = opener.search(text)
        if match:
            rep_here = _match_case(word, replacement)
            return text[: match.start()] + match.group(1) + rep_here + " " + text[match.end():]

    rep = _match_case(word, replacement)
    tail = replacement.rsplit(" ", 1)[-1].lower() if " " in replacement else ""
    pattern = _ARTICLE + rf"\b{re.escape(word)}\b"
    if tail in _PARTICLES:
        pattern += rf"(?:\s+{re.escape(tail)}(?![\w-]))?"

    def _replace(m: re.Match) -> str:
        article = m.group(1)
        if not article:
            return rep
        # The article agreed with the word being replaced, not with the replacement.
        return agree_article(article, replacement) + rep

    return re.sub(pattern, _replace, text, count=1)


def _match_case(original: str, replacement: str) -> str:
    """Carry ``original``'s capitalisation onto ``replacement``.

    The synonym table is written in lower case, so substituting verbatim silently demoted a
    sentence-initial word: "Furthermore, it improves mood" became "also, it improves mood" — a
    sentence starting in lower case, in output whose whole purpose is to read as human writing.
    """
    if not original or not replacement:
        return replacement
    if original.isupper() and len(original) > 1:
        return replacement.upper()
    if original[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


# The loop's own detector-noise band (``run.py::_TELLS_EPS``). A candidate whose score sits inside
# it is not measurably worse on evasion, so trading it for strictly fewer catalogued tells is the
# same bargain the loop already makes when breaking ties between best-of-N drafts.
_TELLS_EPS = 0.02


def _tell_count(text: str) -> int:
    from untell.scripts.tells import score_tells

    return score_tells(text).get("tells", 0)


def _tell_ranks(text: str) -> list[tuple[str, int]]:
    """Words worth swapping because swapping one removes a catalogued tell, most-gain first.

    Detector-independent by construction, which is the point: on the stdlib path the detector has
    no usable per-word gradient, and at full tier it has one that buys nothing for this operation.
    The gain is measured with the word's FIRST synonym as a probe — enough to tell whether the word
    is carrying a tell at all, without scoring every synonym of every word up front.
    """
    base = _tell_count(text)
    ranks: list[tuple[str, int]] = []
    for word in dict.fromkeys(m.group(0) for m in _WORD.finditer(text)):
        syns = synonyms(word)
        if not syns:
            continue
        gain = base - _tell_count(substitute_once(text, word, syns[0]))
        if gain > 0:
            ranks.append((word, gain))
    ranks.sort(key=lambda wg: (-wg[1], wg[0]))  # deterministic: most gain, then alphabetical
    return ranks


def surgical_substitute(
    text: str,
    tier: str = "lite",
    threshold: float = DEFAULT_THRESHOLD,
    max_subs: int = 8,
    prefer_tells: bool = False,
) -> dict:
    """Swap the highest-importance words for score-lowering synonyms. Returns text + stats.

    Optimised via batched scoring: importance ranks are computed with one detector load,
    and each round of synonym candidates is scored together in a single batch.

    HOW OFTEN THIS DOES NOTHING, and why. MEASURED on 30 real HC3 AI texts on the pure-stdlib
    path (``UNTELL_LITE_NO_TORCH=1``): **16 of 30 get zero substitutions**, mean 0.53 swaps, and
    the mean score moves 0.5693 -> 0.5663 — three thousandths.

    The cause is not the one the rewriter's own docstring used to give ("a small synonym map").
    The map is not the problem: on a paragraph carrying 13 catalogued tells it covers every one of
    leverage, robust, seamless, delve, multifaceted, tapestry, groundbreaking, paradigm,
    underscores, pivotal and landscape. Nor is it the ``drop <= 0`` filter — 7 of 13 words there
    ranked positive. The acceptance test is what never fires:

        leverage -> use / lean on / tap into    0.8016  0.8190  0.8190   (baseline 0.7522)
        tapestry -> mix / array / range         0.7522  0.7522  0.7522
        pivotal  -> key / central / critical    0.7522  0.7522  0.7522

    The stdlib heuristic is **insensitive to synonym substitution**: replacing the word leaves its
    score bit-identical, or raises it. `< cur_score` is therefore unreachable, so nothing is
    adopted. Note this is a different failure from ranking — deleting "leverage" *does* move the
    score by 0.0207, which is why importance ranks it highly and then nothing comes of it.

    Two consequences worth knowing before trusting a number from this function:

    * it is close to inert on the zero-dependency path, which is exactly the path the free-ceiling
      measurements advertise as "$0, no key, no model download";
    * the same substitutions that the detector cannot see DO remove catalogued tells.

    ``prefer_tells=True`` switches to that second objective: rank words by whether swapping one
    removes a catalogued tell, and accept a swap that removes a tell while leaving the score inside
    the loop's own 0.02 noise band. A strict score improvement is still taken whenever it is
    available, so this only ever ADDS adoptions the score-only rule refused.

    MEASURED both ways, on real HC3 AI text, tells/100w and mean detector max:

        30 texts, stdlib   shipped  0.571 -> 0.458   score 0.5693 -> 0.5663   16/30 zero-sub
                           tells    0.571 -> 0.233   score 0.5693 -> 0.5653   14/30 zero-sub
         5 texts, full     shipped  0.566 -> 0.428   score 0.9993 -> 0.9991    4/5  zero-sub  21s
                           tells    0.566 -> 0.196   score 0.9993 -> 0.9991    2/5  zero-sub   9s

    The full-tier row is the one that decided it. The reason to keep the deletion-importance
    ranking was that it should earn its keep where the detector has a usable gradient — measured,
    it does not: surgical substitution moves the full-tier score by 0.0002 either way. So the
    ranking is buying nothing there, while costing 2.3x the wall-clock (the leave-one-out pass it
    needs is exactly what the tells ranking skips).

    It is NOT the default, deliberately. ``eval/compare_humanizers.py`` uses this function as the
    ``synonym_swap`` baseline standing in for the QuillBot / TextFooler class of tool, and that row
    has to keep modelling *their* technique — score-driven word-importance substitution — rather
    than quietly inheriting an improvement of ours. Our own ``SurgicalRewriter`` passes True.
    """
    if not text.strip():
        return {"text": text, "substitutions": 0, "pre": 0.0, "post": 0.0}
    pre = _score_max(text, tier)
    cur = text
    subs = 0
    # Rank ONLY the words a substitution could ever touch. Ranking is a leave-one-out detector pass
    # per unique word, and a word with no synonym can never be substituted no matter how important
    # it turns out to be — so every pass spent on one is pure waste. On a 207-word paragraph at full
    # tier this was the difference between 57s and a few seconds, with identical output.
    substitutable = {w.lower() for w in dict.fromkeys(m.group(0) for m in _WORD.finditer(text))
                     if synonyms(w)}
    if prefer_tells:
        # Rank by "does swapping this word remove a catalogued tell" — detector-independent, and
        # therefore still informative on the stdlib path where deletion-importance leads nowhere.
        # This also SKIPS the leave-one-out detector pass entirely, which is where the 2.3x
        # speed-up at full tier comes from.
        word_ranks = _tell_ranks(text)
    else:
        word_ranks = importance(text, tier=tier, only=substitutable, base=pre)  # `pre` IS its baseline
    # NOTE: ``word_ranks`` is computed ONCE from the original text. After a substitution changes
    # the text, subsequent drop values are stale — a word's true importance may differ in the
    # modified text. This is a performance caveat (we may try an already-deflated word), not a
    # correctness bug: every synonym candidate is verified against the CURRENT ``cur_score`` via
    # batch scoring below, so no bad substitution goes through.
    # `cur` only changes when a substitution is ACCEPTED, so re-scoring it at the top of every
    # iteration repeated an identical full-tier detector pass once per ranked word. Carry the score
    # forward instead and refresh it only when the text actually changes — same values, same
    # decisions, one pass instead of one per word.
    cur_score = pre
    # Best score reached so far. Only used by the prefer_tells path, as the fixed point the noise
    # budget is measured from, so a run of tell-removing swaps cannot ratchet the score upward.
    floor = pre
    for word, drop in word_ranks:
        if subs >= max_subs or cur_score < threshold:
            break
        if drop <= 0:
            continue
        # Generate all synonym candidates for this word and batch-score them.
        candidates = []
        for syn in synonyms(word):
            cand = substitute_once(cur, word, syn)
            candidates.append(cand)
        if not candidates:
            continue
        cand_scores = batch_score_texts(candidates, tier=tier)
        if not prefer_tells:
            for cand, s in zip(candidates, cand_scores):
                if float(s["max"]) < cur_score:
                    cur, subs, cur_score = cand, subs + 1, float(s["max"])
                    break
            continue
        # Tells objective: a strict score win is still taken first, so this only ever ADDS
        # adoptions the score-only rule refused. Failing that, take the candidate that removes a
        # tell without moving the score outside the loop's noise band, preferring the one that
        # removes the most tells and then the lowest score, so the choice is deterministic.
        cur_tells = _tell_count(cur)
        ranked = sorted(
            zip(candidates, cand_scores), key=lambda cs: (_tell_count(cs[0]), float(cs[1]["max"]))
        )
        for cand, s in ranked:
            score = float(s["max"])
            # The noise band is a TOTAL budget measured from the best score reached, not a per-swap
            # allowance. Spending 0.02 per substitution let the score creep by up to max_subs*0.02
            # (0.24 at the default 12), and MEASURED that broke the caller that matters: composite
            # chains structural -> surgical and then picks among its own draws on SCORE alone, so
            # the creep changed which draw won and its tells/100w went the WRONG way, 0.167 -> 0.294,
            # even though surgical alone improved (0.307 -> 0.179). Budgeting against `floor` keeps
            # the whole run inside one noise band, which is what the loop's own tie-break means.
            if score < cur_score or (_tell_count(cand) < cur_tells and score <= floor + _TELLS_EPS):
                cur, subs, cur_score = cand, subs + 1, score
                floor = min(floor, score)
                break
    return {"text": cur, "substitutions": subs, "pre": round(pre, 4), "post": round(cur_score, 4)}
