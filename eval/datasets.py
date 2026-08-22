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
    # Repeat to satisfy larger n requests without external data — but SAY SO. The padding is
    # deliberate (the harness must run offline), and it was silent, which made every caller that
    # reports a count report a fabricated one: `--n 2000` against the builtin set returns 2000
    # items that are 5 texts repeated 400 times. training/rl_humanizer builds one GRPO prompt per
    # item, so a run "on 2000 samples" sees five, with no diversity and nothing to show it;
    # training/distill and eval_policy print the padded number as their denominator.
    logger.warning(
        "dataset padded: %d requested but only %d unique built-in samples exist, so each is "
        "repeated ~%.0fx. Counts derived from this are NOT %d distinct texts — install .[eval] "
        "and pass --dataset hc3/raid/mage for real data.",
        n, len(_BUILTIN), n / len(_BUILTIN), n,
    )
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


def _raid_pairs(n: int, min_words: int, scan_cap: int = 60000) -> list[tuple[str, str]]:
    """True (human, machine) pairs from RAID, matched on ``source_id``.

    RAID is the corpus this repo most needed and did not have. HC3 is 2022-era ChatGPT answering
    forum questions; RAID spans several domains (abstracts, books, news, reviews, recipes, poetry,
    wiki) and several generators (llama-chat, mpt, mpt-chat, gpt2, and more), which is what makes
    it possible to tell "this pattern marks AI text" apart from "this pattern marks 2022 ChatGPT
    answering an ELI5 question".

    Pairing is exact rather than topical: every machine row carries the ``source_id`` of the human
    document it was generated from, so the two really are about the same thing. MEASURED on the
    first 4000 rows — 493 source_ids, and all 493 had both sides.

    ``attack='none'`` rows only. RAID also ships adversarially perturbed copies (homoglyphs,
    whitespace, synonym swaps); those are a different measurement — how a detector survives an
    attack — and mixing them in would quietly answer that question instead of this one.
    """
    try:
        from datasets import load_dataset
    except Exception:
        logger.warning("RAID pairs need the '.[eval]' extra (`datasets`)")
        return []
    try:
        ds = load_dataset("liamdugan/raid", split="train", streaming=True)
    except Exception as exc:
        logger.warning("could not stream RAID: %s: %s", type(exc).__name__, exc)
        return []

    humans: dict[str, str] = {}
    machines: dict[str, str] = {}
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for i, row in enumerate(ds):
        if i >= scan_cap or len(pairs) >= n:
            break
        if (row.get("attack") or "none") != "none":
            continue
        text = (row.get("generation") or "").strip()
        key = row.get("source_id")
        if not text or not key or len(text.split()) < min_words:
            continue
        bucket = humans if row.get("model") == "human" else machines
        bucket.setdefault(key, text)
        # Emit as soon as both halves of a pair exist, so a short scan still yields data.
        if key not in seen and key in humans and key in machines:
            seen.add(key)
            pairs.append((humans[key], machines[key]))
    if len(pairs) < n:
        logger.warning(
            "RAID yielded %d of %d requested pairs within a %d-row scan (min_words=%d)",
            len(pairs), n, scan_cap, min_words,
        )
    return pairs[:n]


def _mage_pairs(n: int, min_words: int, scan_cap: int = 260000) -> list[tuple[str, str]]:
    """DOMAIN-MATCHED (human, machine) pairs from MAGE — **not** prompt-paired.

    Read that distinction before using these numbers. MAGE carries no key linking a machine
    sample to the human document it came from; the only shared field is ``src``, e.g.
    ``cmv_human`` against ``cmv_machine_continuation_gpt-3.5-turbo``. Pairing on the domain prefix
    controls for genre and topic area, which is most of what matters for a detector comparison, but
    the two texts are not about the same specific thing the way HC3's and RAID's are. Anything
    sensitive to per-item matching should use RAID.

    What MAGE brings instead is generator breadth: gpt-3.5-turbo, text-davinci-002, flan-t5 (large
    and xxl), opt (2.7b through 30b) and others, which is far wider than HC3's single model.

    The scan cap is large because the corpus is ORDERED — MEASURED, the first 150k rows are all
    label=1 (human) and machine rows only start after that — so a small scan finds one class only
    and silently returns nothing.
    """
    try:
        from datasets import load_dataset
    except Exception:
        logger.warning("MAGE pairs need the '.[eval]' extra (`datasets`)")
        return []
    try:
        ds = load_dataset("yaful/MAGE", split="train", streaming=True)
    except Exception as exc:
        logger.warning("could not stream MAGE: %s: %s", type(exc).__name__, exc)
        return []

    def _domain(src: str) -> str:
        # "cmv_human" -> "cmv";  "hswag_machine_continuation_flan_t5_xxl" -> "hswag"
        for marker in ("_human", "_machine"):
            if marker in src:
                return src.split(marker, 1)[0]
        return src

    humans: dict[str, list[str]] = {}
    machines: dict[str, list[str]] = {}
    for i, row in enumerate(ds):
        if i >= scan_cap:
            break
        text = (row.get("text") or "").strip()
        if not text or len(text.split()) < min_words:
            continue
        dom = _domain(str(row.get("src") or ""))
        # label 1 = human, 0 = machine (verified against the published srcs: label 1 rows are
        # *_human, label 0 rows are *_machine_*).
        bucket = humans if row.get("label") == 1 else machines
        bucket.setdefault(dom, []).append(text)

    pairs: list[tuple[str, str]] = []
    for dom, hs in humans.items():
        for h, m in zip(hs, machines.get(dom, [])):
            pairs.append((h, m))
            if len(pairs) >= n:
                return pairs
    if len(pairs) < n:
        logger.warning(
            "MAGE yielded %d of %d requested domain-matched pairs within a %d-row scan",
            len(pairs), n, scan_cap,
        )
    return pairs[:n]


def load_pairs(dataset: str = "hc3", n: int = 50, min_words: int = 60) -> list[tuple[str, str]]:
    """Return ``(human_text, ai_text)`` pairs answering the same prompt.

    Paired data is the only way to say whether a detector *discriminates* rather than merely
    *responds*. Without it every check reduces to "the score changed", which a detector emitting
    noise also passes. Returns ``[]`` when the data is unavailable — callers should say so rather
    than substitute unlabelled text.
    """
    name = dataset.lower()
    if name == "raid":
        return _raid_pairs(n, min_words)
    if name == "mage":
        return _mage_pairs(n, min_words)
    if name != "hc3":
        logger.warning(
            "paired human/AI data is wired up for 'hc3', 'raid' and 'mage'; got %r", dataset
        )
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


class DatasetUnavailable(RuntimeError):
    """A named dataset could not be loaded and ``strict=True`` refused to substitute another."""


# Every name with a loader below, "builtin"/"sample" aside (they return before any of this).
_KNOWN_DATASETS = frozenset({"hc3", "raid", "mage"})


def _warn_if_mostly_too_short(dataset: str, texts: list[str]) -> list[str]:
    """Say so when a corpus comes back below the thresholds the tool itself enforces.

    Every loader here filters at `> 30` words. Two of untell's own guards sit above that:
    `score._MIN_WORDS_FOR_A_VERDICT` is 40, and `tells._MIN_WORDS_FOR_REPETITION` is 60, which
    gates the two strongest tell categories. A corpus of 35-word texts therefore produces numbers
    the tool would refuse to stand behind if asked about any single document.

    MEASURED over 40 samples per corpus, word counts:

        corpus   median   under 60 words
        HC3         207      0%
        RAID        281      0%
        MAGE         37     90%

    So this is not hypothetical, and it explains a result that looked like a coverage hole: the
    loop moves tells 169 -> 149 on HC3 and 377 -> 298 on RAID, but 36 -> 35 on MAGE. The repetition
    categories are silent on 90% of MAGE by construction, because those documents are shorter than
    the guard. Nothing was wrong with the loop.

    A warning rather than a filter: raising the floor would silently change every MAGE figure ever
    recorded, and `load_pairs` already takes `min_words` for callers who want one. What was missing
    was any signal at all.
    """
    if not texts:
        return texts
    try:
        from untell.scripts.score import _MIN_WORDS_FOR_A_VERDICT as floor
    except Exception:
        floor = 40
    counts = sorted(len(t.split()) for t in texts)
    short = sum(1 for c in counts if c < floor)
    if short * 4 >= len(counts):  # a quarter or more
        logger.warning(
            "%d of %d %r samples are under %d words (median %d) — below untell's own minimum for "
            "a reliable verdict, and the repetition tells need 60. Numbers from this corpus are "
            "dominated by length, not by the property being measured.",
            short, len(counts), dataset, floor, counts[len(counts) // 2],
        )
    return texts


def load_samples(dataset: str = "builtin", n: int = 5, strict: bool = False) -> list[str]:
    """Return up to ``n`` AI-generated text samples for the named dataset.

    Falls back to the built-in sample if ``datasets`` isn't installed or the load fails, so the
    harness never hard-requires a network download.

    ``strict=True`` raises ``DatasetUnavailable`` instead of falling back. The fallback is right for
    a smoke run and wrong for a measurement: the built-in sample is three hand-written paragraphs
    that are measurably EASIER than real AI output (see docs/free-ceiling-measured.md, Result 10),
    so silently substituting it attaches a real corpus's name to a demo corpus's numbers. Callers
    that report a dataset name in their output should pass strict=True.
    """
    name = dataset.lower()
    if name in ("builtin", "sample"):
        return _builtin(n)

    def _fallback(reason: str) -> list[str]:
        if strict:
            raise DatasetUnavailable(
                f"dataset {dataset!r} is unavailable ({reason}). Refusing to substitute the "
                "built-in sample, which is easier than real AI text and would be reported under "
                f"{dataset!r}'s name. Install the '.[eval]' extra, or pass --dataset builtin."
            )
        logger.warning("dataset %r unavailable (%s); using builtin samples.", dataset, reason)
        return _builtin(n)

    # Check the NAME before the dependency. A typo reported as "the `datasets` package is not
    # installed" sends the user to `pip install .[eval]`, after which the same command fails again
    # for the reason nobody named. The known set is a constant here, so it costs nothing to say so
    # first, and the diagnosis stays the same whether or not the extra is installed.
    if name not in _KNOWN_DATASETS:
        return _fallback(f"no such dataset — known: {', '.join(sorted(_KNOWN_DATASETS))}, builtin")

    try:
        from datasets import load_dataset
    except Exception:
        return _fallback("the `datasets` package is not installed")

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
            return _warn_if_mostly_too_short(name, texts[:n]) or _fallback(
                "the load returned no usable samples"
            )

        if name == "raid":
            ds = load_dataset("liamdugan/raid", split="train", streaming=True)
            texts = []
            for row in ds:
                # Skip adversarially perturbed copies (homoglyphs, whitespace, synonym swaps).
                # _raid_pairs already enforces this filter with the same reason: those rows
                # answer "how does a detector survive an attack", not "how does untell perform
                # against normal AI text". Without it, --dataset raid silently mixed the two
                # populations and answered neither question cleanly.
                if (row.get("attack") or "none") != "none":
                    continue
                gen = row.get("generation") or row.get("text")
                if gen and row.get("model", "human") != "human" and len(gen.split()) > 30:
                    texts.append(gen.strip())
                if len(texts) >= n:
                    break
            return _warn_if_mostly_too_short(name, texts[:n]) or _fallback(
                "the load returned no usable samples"
            )

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
            return _warn_if_mostly_too_short(name, texts[:n]) or _fallback(
                "the load returned no usable samples"
            )
    except Exception as exc:
        return _fallback(f"{type(exc).__name__}: {exc}")

    return _fallback("no such dataset — known: hc3, raid, mage, builtin")
