"""Dataset loading for the benchmark.

Pulls AI-generated samples to untell — and, via :func:`load_pairs`, the matching *human* answers,
which is what any statement about a detector actually discriminating requires. Uses HuggingFace
``datasets`` when the ``[eval]`` extra is installed; otherwise falls back to a small built-in
bootstrap sample so the harness still runs (and tests pass) with zero downloads.

Supported names:
  - ``hc3``   -> Hello-SimpleAI/HC3 (human answers AND ChatGPT answers to the same question)
  - ``raid``  -> liamdugan/raid machine-generated split
  - ``mage``  -> yaful/MAGE machine-generated (label 0) samples
  - ``builtin`` (default fallback) -> packaged sample paragraphs
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

# A few machine-flavored paragraphs (formulaic transitions, uniform cadence) for zero-download
# runs. Intentionally "AI-sounding" so the lite detector flags them.
_BUILTIN: list[str] = [
    (
        "Artificial intelligence has fundamentally transformed numerous industries in recent "
        "years. Moreover, it has enabled organizations to streamline their operations and "
        "improve efficiency. Furthermore, machine learning algorithms can analyze vast amounts "
        "of data quickly. Overall, the impact of artificial intelligence continues to grow "
        "significantly across various sectors."
    ),
    (
        "Climate change represents one of the most pressing challenges of our time. Additionally, "
        "it poses significant risks to ecosystems and human societies alike. Furthermore, rising "
        "global temperatures contribute to more frequent extreme weather events. In conclusion, "
        "addressing climate change requires coordinated global action and sustained commitment."
    ),
    (
        "Effective communication plays a crucial role in the success of any organization. "
        "Moreover, it fosters collaboration and strengthens relationships among team members. "
        "Additionally, clear communication helps prevent misunderstandings and conflicts. "
        "Overall, organizations that prioritize communication tend to achieve better outcomes."
    ),
    (
        "Regular physical exercise offers numerous benefits for both physical and mental health. "
        "Furthermore, it helps reduce the risk of chronic diseases such as diabetes and heart "
        "disease. Additionally, exercise releases endorphins that improve mood and reduce stress. "
        "In summary, incorporating regular exercise into daily routines is highly beneficial."
    ),
    (
        "The development of renewable energy sources is essential for a sustainable future. "
        "Moreover, solar and wind power have become increasingly cost-effective in recent years. "
        "Furthermore, transitioning to renewable energy reduces dependence on fossil fuels. "
        "Overall, investing in renewable energy infrastructure yields long-term environmental "
        "and economic benefits."
    ),
]


def _builtin(n: int) -> list[str]:
    if n <= len(_BUILTIN):
        return _BUILTIN[:n]
    # Repeat to satisfy larger n requests without external data.
    out = list(_BUILTIN)
    while len(out) < n:
        out.append(_BUILTIN[len(out) % len(_BUILTIN)])
    return out[:n]


def _hc3_rows() -> list[dict]:
    """Read HC3 straight from its data file.

    ``load_dataset("Hello-SimpleAI/HC3", "all")`` cannot work on any current install: the repo
    ships a loading *script* (``HC3.py``) and ``datasets`` >= 3 refuses it outright with
    "Dataset scripts are no longer supported". That exception was caught and logged at warning
    level, so every caller asking for HC3 silently received the five packaged bootstrap
    paragraphs instead — a benchmark quietly measuring nothing. The data file itself is plain
    JSONL and needs no script.
    """
    from huggingface_hub import hf_hub_download

    path = hf_hub_download("Hello-SimpleAI/HC3", "all.jsonl", repo_type="dataset")
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_pairs(dataset: str = "hc3", n: int = 50, min_words: int = 60) -> list[tuple[str, str]]:
    """Return ``(human_text, ai_text)`` pairs answering the same prompt.

    Paired data is the only way to say whether a detector *discriminates* rather than merely
    *responds*. Without it every check reduces to "the score changed", which a detector emitting
    noise also passes. Returns ``[]`` when the data is unavailable — callers should say so rather
    than substitute unlabelled text.
    """
    if dataset.lower() != "hc3":
        logger.warning("paired human/AI data is only wired up for 'hc3'; got %r", dataset)
        return []
    try:
        rows = _hc3_rows()
    except Exception as exc:
        logger.warning("could not load HC3 pairs: %s: %s", type(exc).__name__, exc)
        return []
    pairs: list[tuple[str, str]] = []
    for row in rows:
        humans = [a for a in (row.get("human_answers") or []) if a and len(a.split()) >= min_words]
        bots = [a for a in (row.get("chatgpt_answers") or []) if a and len(a.split()) >= min_words]
        if humans and bots:
            pairs.append((humans[0].strip(), bots[0].strip()))
        if len(pairs) >= n:
            break
    return pairs


def load_samples(dataset: str = "builtin", n: int = 5) -> list[str]:
    """Return up to ``n`` AI-generated text samples for the named dataset.

    Falls back to the built-in sample if ``datasets`` isn't installed or the load fails, so the
    harness never hard-requires a network download.
    """
    name = dataset.lower()
    if name in ("builtin", "sample"):
        return _builtin(n)

    try:
        from datasets import load_dataset
    except Exception:
        logger.warning("could not import `datasets` package")
        return _builtin(n)

    try:
        if name == "hc3":
            # Read the JSONL directly — the hub repo's loading script is rejected by datasets >= 3.
            texts: list[str] = []
            for row in _hc3_rows():
                answers = row.get("chatgpt_answers") or []
                for a in answers:
                    if a and len(a.split()) > 30:
                        texts.append(a.strip())
                        break
                if len(texts) >= n:
                    break
            return texts[:n] or _builtin(n)

        if name == "raid":
            ds = load_dataset("liamdugan/raid", split="train", streaming=True)
            texts = []
            for row in ds:
                gen = row.get("generation") or row.get("text")
                if gen and row.get("model", "human") != "human" and len(gen.split()) > 30:
                    texts.append(gen.strip())
                if len(texts) >= n:
                    break
            return texts[:n] or _builtin(n)

        if name == "mage":
            ds = load_dataset("yaful/MAGE", split="test", streaming=True)
            texts = []
            for row in ds:
                txt = row.get("text")
                # MAGE label convention: 0 == machine-generated (the samples we want to untell).
                if txt and row.get("label", 1) == 0 and len(txt.split()) > 30:
                    texts.append(txt.strip())
                if len(texts) >= n:
                    break
            return texts[:n] or _builtin(n)
    except Exception as exc:
        logger.warning("failed to load dataset '%s': %s", name, exc)
        return _builtin(n)

    logger.warning("unknown dataset '%s'; using builtin samples.", dataset)
    return _builtin(n)
