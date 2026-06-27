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
import re
import sys

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

_WORD = re.compile(r"[A-Za-z0-9']+")
_SENT_SPLIT = re.compile(r"[.!?]+(?:\s+|$)")

# High-frequency AI vocabulary (from ai-tells.md §1). Whole-word, case-insensitive.
_AI_VOCAB = [
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
_NEGATED_CONTRAST_RE = re.compile(
    r"\b(?:it'?s not\s+\w+[^.,;]{0,40},?\s+it'?s\s+\w+"
    r"|not only\b[^.]{0,60}\bbut also\b"
    r"|isn'?t about\b[^.;]{0,50};?\s+it'?s about\b"
    r"|not\s+just\b[^.]{0,40}\bbut\b)",
    re.IGNORECASE,
)

# Participial-phrase trailers (§6): a clause ending ", ...ing ..." near sentence end.
_PARTICIPIAL_TRAILER_RE = re.compile(
    r",\s+(?:under(?:scoring|lining)|marking|reflecting|highlighting|showcasing|emphasizing|"
    r"signaling|cementing|solidifying|paving|ensuring|demonstrating)\b[^.!?]*[.!?]",
    re.IGNORECASE,
)

# Vague attribution (§7).
_VAGUE_ATTR_RE = re.compile(
    r"\b(studies show|research suggests?|experts? (?:believe|say|agree)|scientists? believe|"
    r"it is (?:widely )?believed|many believe|some argue)\b",
    re.IGNORECASE,
)

# Banned clichés / phrases (§2) — openers, signposting, action, closings, promo.
_CLICHES = [
    r"in today'?s (?:fast-paced|digital|modern|ever-changing) world", r"in the ever-evolving \w+ of",
    r"in an era where", r"as technology continues to evolve", r"when it comes to", r"at its core",
    r"at the end of the day", r"in the realm of", r"this is where \w+ comes in",
    r"it'?s (?:important|worth) (?:to note|noting)", r"it cannot be overstated",
    r"one of the most important", r"plays? a (?:crucial|pivotal|vital) role",
    r"stands? as a testament to", r"underscores? the importance of",
    r"reflects? a broader (?:trend|shift)", r"marks? a significant shift", r"let'?s dive in",
    r"dive into", r"deep dive", r"shed light on", r"pave[sd]? the way",
    r"navigate the complexities of", r"embark on a journey", r"explore the intricacies of",
    r"in conclusion", r"in summary", r"to summarize", r"the future looks bright",
    r"only time will tell", r"one thing is certain", r"as we move forward",
    r"despite (?:the )?challenges,? \w+ continues to thrive", r"vibrant hub", r"thriving ecosystem",
    r"rich tapestry of", r"game-?changer", r"game-?changing",
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
    r"|\bfrom\s+(?:ancient|the everyday|the mundane|individual|small|humble)\b[^.!?]{0,50}\bto\s+the\b",
    re.IGNORECASE,
)

# Distinctly-AI markdown artifacts (§7/§12) — NOT plain headings/bullets (those have honest uses), only
# the structure prose almost never adds itself: TL;DR / Key Takeaways blocks and emoji section headers.
_MARKDOWN_ARTIFACT_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:key takeaways?|key points?|tl;?dr|in a nutshell)\b"
    r"|^#{1,6}\s.*[\U0001F300-\U0001FAFF✅✨]",  # TL;DR/Key-Takeaways blocks, or emoji headers
    re.MULTILINE | re.IGNORECASE,
)


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


def _semicolon_crutch(text: str) -> int:
    """Semicolons used as a rhythm crutch (§6). One is ordinary; 2+ in a passage is the tell. Returns
    the count only when it crosses that bar, else 0 (so a single legitimate semicolon never flags)."""
    n = text.count(";")
    return n if n >= 2 else 0


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]


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


def score_tells(text: str, *, include_matches: bool = False) -> dict:
    """Count AI tells in ``text`` per the catalogue. Lower is more human-reading."""
    words = len(_WORD.findall(text))
    by_category: dict[str, int] = {}
    matches: dict[str, list[str]] = {}

    # True em-dash plus the spaced-hyphen " - " used as a dash — but NOT digit ranges ("2020 - 2025"),
    # which a spaced hyphen between numbers represents.
    em_dashes = text.count("—") + len(re.findall(r"(?<!\d) - (?!\d)", text))
    if em_dashes:
        by_category["em_dash"] = em_dashes
        if include_matches:
            matches["em_dash"] = ["—"] * text.count("—")

    for name, pat in _CATEGORIES:
        found = pat.findall(text)
        if found:
            by_category[name] = len(found)
            if include_matches:
                matches[name] = [m if isinstance(m, str) else next((g for g in m if g), "") for m in found]

    # Two tells that aren't a simple findall:
    rot = _rule_of_three_runs(text)
    if rot:
        by_category["rule_of_three"] = rot
    semi = _semicolon_crutch(text)
    if semi:
        by_category["semicolon_crutch"] = semi

    total = sum(by_category.values())
    cv = _burstiness_cv(text)
    result = {
        "words": words,
        "tells": total,
        "tells_per_100w": round(total / words * 100, 2) if words else 0.0,
        "by_category": by_category,
        "burstiness_cv": cv,
        "low_burstiness": (cv is not None and cv < 0.35),  # uniform sentence length is itself a tell
    }
    if include_matches:
        result["matches"] = matches
    return result


def _render(r: dict) -> str:
    lines = [
        f"AI-tells: {r['tells']}  ({r['tells_per_100w']} per 100 words, {r['words']} words)",
        f"burstiness CV: {r['burstiness_cv']}"
        + ("  [LOW — uniform sentence length is itself a tell]" if r["low_burstiness"] else ""),
    ]
    if r["by_category"]:
        lines.append("by category:")
        for k, v in sorted(r["by_category"].items(), key=lambda kv: -kv[1]):
            lines.append(f"  {k:22} {v}")
    else:
        lines.append("no catalogued tells found.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
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
