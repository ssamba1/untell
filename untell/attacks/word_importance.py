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
    "crucial": ["key", "vital", "central", "critical"],
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
    "groundbreaking": ["pioneering", "pivotal", "landmark"],
    "transformative": ["game-changing", "powerful", "far-reaching"],
    "innovative": ["new", "fresh", "original"],
    "boasts": ["has", "offers", "can claim"],
    "nestled": ["set", "situated", "tucked"],
    "profound": ["deep", "far-reaching", "major"],
    "holistic": ["whole-picture", "full-spectrum", "broad"],
    "actionable": ["usable", "practical", "concrete"],
    "impactful": ["powerful", "striking", "meaningful"],
    "streamline": ["simplify", "smooth", "speed up"],
    "empower": ["enable", "help", "equip"],
    "empowering": ["enabling", "helpful", "freeing"],
    "revolutionize": ["transform", "overhaul", "shake up"],
    "resonate": ["connect", "ring true", "strike a chord"],
    "encompass": ["cover", "span", "include"],
    "paradigm": ["model", "pattern", "framework"],
    "cornerstone": ["foundation", "bedrock", "base"],
    "burgeoning": ["growing", "expanding", "rising"],
    "quintessential": ["typical", "classic", "perfect example of"],
    "overarching": ["overall", "central", "blanket"],
    "synergy": ["collaboration", "combined effect", "teamwork"],
    "endeavor": ["effort", "undertaking", "pursuit"],
    "commence": ["start", "begin", "kick off"],
    "illuminate": ["clarify", "shed light on", "explain"],
    "cultivate": ["develop", "build", "grow"],
    "catalyze": ["spark", "trigger", "set off"],
    "galvanize": ["rally", "rouse", "jolt"],
    "augment": ["boost", "add to", "supplement"],
    "elucidate": ["clarify", "explain", "spell out"],
    "interplay": ["interaction", "exchange", "give-and-take"],
    "underpin": ["support", "undergird", "back"],
    "compelling": ["powerful", "convincing", "strong"],
    "unprecedented": ["unmatched", "unheard-of", "record"],
    "exceptional": ["outstanding", "remarkable", "top-notch"],
    "remarkable": ["striking", "impressive", "notable"],
    "sophisticated": ["advanced", "refined", "polished"],
    "invaluable": ["priceless", "indispensable", "vital"],
    "unwavering": ["steady", "firm", "constant"],
    "scalable": ["expandable", "growable", "adaptable"],
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
    # --- Transition words (§3, §8) ---
    "furthermore": ["also", "and", "plus"],
    "moreover": ["also", "what is more", "and"],
    "additionally": ["also", "plus", "on top of that"],
    "consequently": ["so", "as a result", "because of that"],
    "therefore": ["so", "thus", "that is why"],
    "accordingly": ["so", "thus", "in line with that"],
    "hence": ["so", "thus", "for that reason"],
    "subsequently": ["later", "next", "afterward"],
    "nevertheless": ["still", "even so", "yet"],
    "nonetheless": ["still", "even so", "yet"],
    "notably": ["especially", "in particular", "most notably"],
    "importantly": ["mostly", "above all", "significantly"],
    "ultimately": ["in the end", "finally", "eventually"],
    "overall": ["in the end", "all told", "on the whole"],
    "essentially": ["basically", "at bottom", "in essence"],
    "arguably": ["possibly", "debatably", "one could say"],
    # --- High-signal verbs to flatten ---
    "numerous": ["many", "plenty of", "lots of"],
    "significant": ["real", "major", "big"],
    "significantly": ["sharply", "a lot", "greatly"],
    "fundamentally": ["deeply", "at root", "basically"],
    "various": ["different", "all sorts of", "assorted"],
    "essential": ["needed", "key", "necessary"],
    "facilitate": ["help", "ease", "aid"],
    "facilitates": ["helps", "eases", "aids"],
    "demonstrate": ["show", "prove", "display"],
    "demonstrates": ["shows", "proves", "displays"],
    "enhance": ["improve", "boost", "strengthen"],
    "enhances": ["improves", "boosts", "strengthens"],
    "optimize": ["tune", "sharpen", "improve"],
    "optimizes": ["tunes", "sharpens", "improves"],
    "represents": ["is", "stands for", "means"],
    "enables": ["lets", "allows", "makes possible"],
    "enabled": ["let", "allowed", "made possible"],
    "increasingly": ["more and more", "ever more"],
    # --- Clichés that collapse to a single word ---
    "however": ["but", "though", "on the other hand"],
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


def substitute_once(text: str, word: str, replacement: str) -> str:
    """Replace the first whole-word ``word`` with ``replacement``, collapsing a doubled particle.

    When the replacement already ends in the particle the sentence supplies next, that particle is
    consumed rather than repeated. Only the seam is touched — a duplicated word anywhere else in the
    text is the author's and is left exactly as written.
    """
    rep = _match_case(word, replacement)
    tail = replacement.rsplit(" ", 1)[-1].lower() if " " in replacement else ""
    pattern = rf"\b{re.escape(word)}\b"
    if tail in _PARTICLES:
        pattern += rf"(?:\s+{re.escape(tail)}(?![\w-]))?"
    return re.sub(pattern, lambda _m: rep, text, count=1)


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


def surgical_substitute(
    text: str, tier: str = "lite", threshold: float = DEFAULT_THRESHOLD, max_subs: int = 8
) -> dict:
    """Swap the highest-importance words for score-lowering synonyms. Returns text + stats.

    Optimised via batched scoring: importance ranks are computed with one detector load,
    and each round of synonym candidates is scored together in a single batch.
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
        for cand, s in zip(candidates, cand_scores):
            if float(s["max"]) < cur_score:
                cur, subs, cur_score = cand, subs + 1, float(s["max"])
                break
    return {"text": cur, "substitutions": subs, "pre": round(pre, 4), "post": round(cur_score, 4)}
