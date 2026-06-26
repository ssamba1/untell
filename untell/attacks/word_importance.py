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

from untell.scripts.score import DEFAULT_THRESHOLD, score_text

_WORD = re.compile(r"[A-Za-z]+")

# Formulaic AI vocabulary -> plainer human alternatives (the words detectors + competitors target).
_SYN: dict[str, list[str]] = {
    "numerous": ["many", "plenty of", "lots of"],
    "significant": ["real", "major", "big"],
    "significantly": ["sharply", "a lot", "hugely"],
    "fundamentally": ["deeply", "at root", "basically"],
    "various": ["different", "all sorts of", "assorted"],
    "crucial": ["key", "vital", "central"],
    "essential": ["needed", "key", "necessary"],
    "utilize": ["use"],
    "utilizing": ["using"],
    "leverage": ["use", "lean on"],
    "facilitate": ["help", "ease"],
    "demonstrate": ["show"],
    "enhance": ["improve", "boost"],
    "optimize": ["tune", "sharpen"],
    "robust": ["solid", "sturdy"],
    "comprehensive": ["full", "thorough"],
    "innovative": ["new", "fresh"],
    "paradigm": ["model", "pattern"],
    "myriad": ["countless", "tons of"],
    "pivotal": ["key", "central"],
    "seamless": ["smooth"],
    "delve": ["dig", "look"],
    "realm": ["area", "space"],
    "furthermore": ["also", "and"],
    "moreover": ["also", "on top of that"],
    "additionally": ["also", "plus"],
    "consequently": ["so", "as a result"],
    "therefore": ["so"],
    "however": ["but", "though"],
    "overall": ["in the end", "all told"],
}


def synonyms(word: str) -> list[str]:
    """Synonym candidates for ``word`` — built-in map plus WordNet (if nltk is available)."""
    w = word.lower()
    out = list(_SYN.get(w, []))
    try:
        from nltk.corpus import wordnet

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


def _max(text: str, tier: str) -> float:
    return float(score_text(text, tier=tier)["max"]) if text.strip() else 0.0


def importance(text: str, tier: str = "lite") -> list[tuple[str, float]]:
    """Rank unique words by how much removing them drops the detector score (descending)."""
    base = _max(text, tier)
    scored: list[tuple[str, float]] = []
    for w in dict.fromkeys(m.group(0) for m in _WORD.finditer(text)):  # unique, order-preserving
        stripped = re.sub(rf"\b{re.escape(w)}\b", "", text)
        scored.append((w, base - _max(stripped, tier)))
    return sorted(scored, key=lambda kv: -kv[1])


def surgical_substitute(
    text: str, tier: str = "lite", threshold: float = DEFAULT_THRESHOLD, max_subs: int = 8
) -> dict:
    """Swap the highest-importance words for score-lowering synonyms. Returns text + stats."""
    cur = text
    pre = _max(cur, tier)
    subs = 0
    for word, drop in importance(text, tier=tier):
        if subs >= max_subs or _max(cur, tier) < threshold:
            break
        if drop <= 0:
            continue
        cur_score = _max(cur, tier)
        for syn in synonyms(word):
            cand = re.sub(rf"\b{re.escape(word)}\b", syn, cur, count=1)
            if _max(cand, tier) < cur_score:
                cur, subs = cand, subs + 1
                break
    return {"text": cur, "substitutions": subs, "pre": round(pre, 4), "post": round(_max(cur, tier), 4)}
