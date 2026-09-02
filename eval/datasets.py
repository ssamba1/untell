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


# ---------------------------------------------------------------------------------------------
# Labelled human corpora, for the subgroup false-positive audit (eval/subgroup_audit.py).
#
# These carry writer metadata, which the pair loaders above do not, and they are HUMAN-ONLY on
# purpose: a false-positive audit needs text that is known-human by construction, so that every
# flag is unambiguously an error.
#
# NOTHING HERE IS VENDORED. ELLIPSE is CC BY-NC-SA 4.0 and this package is MIT; committing the
# corpus would relicense the repository. It is fetched on demand, cached outside the tree, and its
# licence and citation are printed the first time it loads.
# ---------------------------------------------------------------------------------------------

ELLIPSE_URL = (
    "https://raw.githubusercontent.com/scrosseye/ELLIPSE-Corpus/main/"
    "ELLIPSE_Final_github_train.csv"
)
ELLIPSE_CITATION = (
    "ELLIPSE corpus -- Crossley, S., Tian, Y., et al. (2023), 'The English Language Learner "
    "Insight, Proficiency and Skills Evaluation (ELLIPSE) Corpus', International Journal of "
    "Learner Corpus Research 9(2), 248-269. Licence: CC BY-NC-SA 4.0 (NON-COMMERCIAL, "
    "share-alike). Source: https://github.com/scrosseye/ELLIPSE-Corpus"
)
# Columns kept from the corpus: the essay, plus the writer metadata the audit groups by.
_ELLIPSE_LABELS = ("gender", "grade", "race_ethnicity", "SES", "Overall")


def _ellipse_cache():
    import os
    from pathlib import Path as _P

    base = os.environ.get("UNTELL_CORPUS_DIR") or os.path.join(
        os.path.expanduser("~"), ".cache", "untell-corpora"
    )
    return _P(base) / "ellipse_train.csv"


# ASAP 2.0 (Crossley et al. 2025). The independent second corpus, and the one that carries the
# contrast ELLIPSE structurally cannot: ELLIPSE writers are ALL English language learners, so it
# can compare learners to each other but never to native speakers. ASAP has `ell_status`, which is
# the Liang et al. question directly. Different task type (source-based rather than independent
# writing), different sampling, 4x the size, and CC BY 4.0 rather than NC-SA -- so unlike ELLIPSE
# it is only the file size, not the licence, that keeps it out of the tree.
ASAP_URL = ("https://raw.githubusercontent.com/scrosseye/ASAP_2.0/main/"
            "ASAP_2_Final_github_train.zip")
ASAP_CITATION = (
    "ASAP 2.0 corpus -- Crossley, S., et al., 'A large-scale corpus for assessing source-based "
    "writing quality: ASAP 2.0', Assessing Writing. Licence: CC BY 4.0. "
    "Source: https://github.com/scrosseye/ASAP_2.0"
)
_ASAP_LABELS = ("ell_status", "race_ethnicity", "gender", "economically_disadvantaged",
                "student_disability_status", "grade_level", "score")

_CORPORA = {
    "ellipse": {"url": None, "text_col": "full_text"},
    "asap": {"url": ASAP_URL, "text_col": "full_text"},
}


def _asap_cache():
    import os
    from pathlib import Path as _P

    base = os.environ.get("UNTELL_CORPUS_DIR") or os.path.join(
        os.path.expanduser("~"), ".cache", "untell-corpora"
    )
    return _P(base) / "asap_train.csv"


def _fetch_asap(path) -> None:
    """Download the zip and extract the single CSV, skipping the __MACOSX sidecar."""
    import io
    import urllib.request
    import zipfile

    logger.warning("fetching ASAP 2.0 (~11MB) to %s\n%s", path, ASAP_CITATION)
    with urllib.request.urlopen(ASAP_URL, timeout=180) as fh:  # noqa: S310 - fixed https URL
        blob = fh.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        name = next(n for n in zf.namelist()
                    if n.endswith(".csv") and not n.startswith("__MACOSX"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(zf.read(name))


def load_labelled(corpus: str = "ellipse", csv_path=None, min_words: int = 60) -> list[dict]:
    """Known-human texts with writer labels, as ``{"text": ..., <label>: ...}`` dicts.

    ``min_words`` drops essays too short to score meaningfully -- the detectors are calibrated on
    paragraphs, and a 14-word answer measures the window logic rather than the writer.
    """
    import csv as _csv

    text_col = "full_text"

    if corpus not in _CORPORA and csv_path is None:
        raise ValueError(f"unknown labelled corpus {corpus!r}; known: {sorted(_CORPORA)}")

    # A user-supplied CSV keeps ALL of its columns. MEASURED 2026-09-01: with an explicit --csv
    # the corpus argument still defaulted to "ellipse", so an ASAP file was filtered through the
    # ELLIPSE allowlist and `ell_status` -- the whole reason to load ASAP -- silently vanished.
    # The audit then rendered an empty axis rather than an error, which is the worst shape for a
    # bug to take: a heading with nothing under it reads as "no disparity here".
    labels = None if csv_path is not None else (_ASAP_LABELS if corpus == "asap"
                                                else _ELLIPSE_LABELS)
    if csv_path is not None:
        path = csv_path
    elif corpus == "asap":
        path = _asap_cache()
        if not path.exists():
            _fetch_asap(path)
        else:
            logger.info("%s", ASAP_CITATION)
    else:
        path = _ellipse_cache()
        if not path.exists():
            import urllib.request

            path.parent.mkdir(parents=True, exist_ok=True)
            logger.warning("fetching ELLIPSE (~10MB) to %s\n%s", path, ELLIPSE_CITATION)
            urllib.request.urlretrieve(ELLIPSE_URL, path)  # noqa: S310 - fixed https URL above
        else:
            logger.info("%s", ELLIPSE_CITATION)

    rows: list[dict] = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in _csv.DictReader(fh):
            text = (raw.get("full_text") or "").strip()
            if len(text.split()) < min_words:
                continue
            keep = raw.keys() if labels is None else [k for k in labels if k in raw]
            rows.append({"text": text,
                         **{k: raw.get(k) for k in keep if k != text_col}})
    if not rows:
        raise DatasetUnavailable(f"{corpus}: no rows survived the {min_words}-word floor")
    return rows

# --------------------------------------------------------------------------------------------
# Liang et al. (2023), the corpus this field's bias literature is founded on. ADDED 2026-09-01
# after reading `satyamshivam13/AI_Text_Detector`, which had been measuring per-population
# false-positive rates on it since July 2026 -- see docs/strategy-the-audit-position.md for the
# claim of ours that falsified. Its populations are corpora rather than demographic attributes,
# so it complements ELLIPSE and ASAP rather than replacing them: those answer "which writers does
# this detector fail, holding genre constant", this one answers "which kinds of writing", on the
# essays the published bias results were measured on.
# --------------------------------------------------------------------------------------------
LIANG_BASE = ("https://raw.githubusercontent.com/Weixin-Liang/ChatGPT-Detector-Bias/main/"
              "Data_and_Results/Human_Data")
LIANG_CITATION = (
    "Liang, W., Yuksekgonul, M., Mao, Y., Wu, E., Zou, J., 'GPT detectors are biased against "
    "non-native English writers', Patterns 4(7), 2023. "
    "Source: https://github.com/Weixin-Liang/ChatGPT-Detector-Bias"
)
# population -> upstream folder. Every one is human-authored, so every flag is a false positive
# -- except the last, which is human-authored and machine-EDITED. That is a different question
# and is labelled so it can be held out rather than counted as a plain error.
LIANG_POPULATIONS = {
    "toefl_nonnative": "TOEFL_real_91",
    "student_us_8th": "HewlettStudentEssay_real_88",
    "college_admission": "CollegeEssay_real_70",
    "cs224n_student": "CS224N_real_145",
    "toefl_gpt4_polished": "TOEFL_gpt4polished_91",
}
LIANG_MACHINE_EDITED = frozenset({"toefl_gpt4_polished"})

# The other half of the audit. `docs/detector-fairness-measured.md` said for weeks that
# equalised odds could not be computed because no paired human/machine corpus was reachable --
# RAID, MAGE and HC3 are all HuggingFace-hosted and blocked here. That was true of those three
# and false in general: Liang ships GPT-3 essays on the SAME prompts as its human ones, in the
# same upstream repository, one directory across from the human data that was already being
# loaded. `machine` rows carry is_ai=True; the `population` axis stays domain-matched, so
# CS224N human essays are compared against CS224N machine essays rather than against a different
# domain's.
LIANG_MACHINE = {
    "cs224n_student": "GPT_Data/CS224N_gpt3_145",
    "college_admission": "GPT_Data/CollegeEssay_gpt3_31",
}
# Prompt-engineered variants: the same generators told to write less like themselves. Kept
# separate because "can the detector find GPT-3" and "can it find GPT-3 that is trying" are
# different questions, and pooling them answers neither.
LIANG_MACHINE_PROMPT_ENGINEERED = {
    "cs224n_student": "GPT_Data/CS224N_gpt3PromptEng_145",
    "college_admission": "GPT_Data/CollegeEssay_gpt3PromptEng_31",
}


def _liang_cache():
    import os
    from pathlib import Path as _P

    base = os.environ.get("UNTELL_CORPUS_DIR") or os.path.join(
        os.path.expanduser("~"), ".cache", "untell-corpora"
    )
    return _P(base) / "liang_human.json"


def load_liang_paired(prompt_engineered: bool = False, min_words: int = 0) -> list[dict]:
    """Human AND machine essays from Liang, domain-matched, for an equalised-odds audit.

    Returns rows carrying ``is_ai``, so both error rates are measurable: a false positive is a
    human essay flagged, a false negative is a machine essay missed. Only the two populations
    that have a machine counterpart are included -- TOEFL has none, and inventing one by pairing
    against another domain's machine text would measure the distance between two datasets and
    report it as a property of a detector, which is the error this corpus exists to avoid.
    """
    import json as _json

    cache = _liang_cache().with_name(
        f"liang_paired{'_prompteng' if prompt_engineered else ''}.json")
    if cache.exists():
        logger.info("%s", LIANG_CITATION)
        payload = _json.loads(cache.read_text(encoding="utf-8"))
    else:
        logger.warning("fetching Liang et al. 2023 paired human/machine essays to %s\n%s",
                       cache, LIANG_CITATION)
        payload = []
        for population, folder in LIANG_POPULATIONS.items():
            if population in LIANG_MACHINE_EDITED or population not in LIANG_MACHINE:
                continue
            payload += _liang_fetch(folder, population, is_ai=False)
        machine = LIANG_MACHINE_PROMPT_ENGINEERED if prompt_engineered else LIANG_MACHINE
        for population, folder in machine.items():
            payload += _liang_fetch(folder, population, is_ai=True)
        if not payload:
            raise DatasetUnavailable("liang-paired: every arm fetched empty")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(_json.dumps(payload), encoding="utf-8")

    rows = [dict(r) for r in payload if len(r["text"].split()) >= min_words]
    if not rows:
        raise DatasetUnavailable(f"liang-paired: no rows survived the {min_words}-word floor")
    return rows


def _liang_fetch(folder: str, population: str, is_ai: bool) -> list[dict]:
    """One upstream folder as audit rows. `folder` may carry a leading `GPT_Data/`."""
    import json as _json
    import urllib.request

    # LIANG_BASE points at Human_Data; a machine folder carries its own `GPT_Data/` prefix and is
    # resolved against the parent instead.
    root = LIANG_BASE.rsplit("/", 1)[0] if "/" in folder else LIANG_BASE
    url = f"{root}/{folder}/data.json"
    with urllib.request.urlopen(url, timeout=180) as fh:  # noqa: S310 - fixed https base
        raw = _json.loads(fh.read())
    out = []
    for record in raw:
        text = " ".join((record.get("document") or "").split()).strip()
        if text:
            out.append({"text": text, "population": population, "is_ai": is_ai})
    return out


def load_liang(min_words: int = 0) -> list[dict]:
    """The five Liang populations as audit rows, cached after the first fetch.

    ``min_words`` defaults to 0 rather than the 60 the other loaders use: these are the essays
    the published figures were computed on, and silently dropping some of them would make any
    comparison against those figures meaningless. Filter afterwards if you want to, and say so.
    """
    import json as _json
    import urllib.request

    cache = _liang_cache()
    if cache.exists():
        logger.info("%s", LIANG_CITATION)
        payload = _json.loads(cache.read_text(encoding="utf-8"))
    else:
        logger.warning("fetching Liang et al. 2023 human essays to %s\n%s", cache, LIANG_CITATION)
        payload = []
        for population, folder in LIANG_POPULATIONS.items():
            url = f"{LIANG_BASE}/{folder}/data.json"
            with urllib.request.urlopen(url, timeout=180) as fh:  # noqa: S310 - fixed https base
                raw = _json.loads(fh.read())
            for record in raw:
                text = " ".join((record.get("document") or "").split()).strip()
                if text:
                    payload.append({"text": text, "population": population})
        if not payload:
            raise DatasetUnavailable("liang: every population fetched empty")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(_json.dumps(payload), encoding="utf-8")

    rows = [dict(r, machine_edited=str(r["population"] in LIANG_MACHINE_EDITED))
            for r in payload if len(r["text"].split()) >= min_words]
    if not rows:
        raise DatasetUnavailable(f"liang: no rows survived the {min_words}-word floor")
    return rows


# --------------------------------------------------------------------------------------------
# M4 (SemEval-2024 Task 8) -- the paired corpus this repository said it did not have.
#
# `docs/detector-fairness-measured.md` listed "a corpus that pairs human and machine text on the
# same prompts" under what its results could not establish, and named RAID, MAGE and HC3 as the
# nearest candidates, all HuggingFace-hosted and blocked here. M4 ships its data IN ITS GITHUB
# REPOSITORY -- 959 MB across 39 files, every record carrying a prompt, the human answer to it and
# a machine answer to it, labelled by generator and domain. FOUND 2026-09-01 by re-testing three
# repos an earlier timing-out loop had recorded as "clone failed".
#
# It is also the first non-English text this instrument has ever scored: German, Indonesian, Urdu,
# Arabic, Russian, Bulgarian and Chinese subsets exist alongside the English ones.
# --------------------------------------------------------------------------------------------
M4_REPO = "https://github.com/mbzuai-nlp/M4"
M4_CITATION = (
    "Wang, Y., et al., 'M4: Multi-generator, Multi-domain, and Multi-lingual Black-Box "
    "Machine-Generated Text Detection', EACL 2024. Data: https://github.com/mbzuai-nlp/M4"
)
# filename stem -> (domain, language). The language is the corpus's own split, not a guess.
M4_FILES = {
    "arxiv_chatGPT": ("arxiv", "en"), "arxiv_davinci": ("arxiv", "en"),
    "arxiv_bloomz": ("arxiv", "en"), "arxiv_cohere": ("arxiv", "en"),
    "wikipedia_chatgpt": ("wikipedia", "en"), "wikihow_chatGPT": ("wikihow", "en"),
    "reddit_chatGPT": ("reddit", "en"), "peerread_cohere": ("peerread", "en"),
    "peerread_llama": ("peerread", "en"), "peerread_chatgpt": ("peerread", "en"),
    "germanwikipedia_chatgpt": ("wikipedia", "de"),
    "id-newspaper_chatGPT": ("newspaper", "id"),
    "urdu_chatGPT": ("news", "ur"),
    "arabic_chatGPT": ("news", "ar"),
    "russian_chatGPT": ("news", "ru"),
    "bulgarian_true_and_fake_news_chatGPT": ("news", "bg"),
    "qazh_chatgpt": ("qa", "zh"), "qazh_davinci": ("qa", "zh"),
}
# Human text first, machine text second. `arxiv_bloomz` uses a different pair of names AND ships a
# `machine_text` field containing the PROMPT rather than the generation -- scoring that as machine
# text would put instructions into the false-negative denominator, so `machine_abstract` wins and
# `_m4_rows` drops any row whose machine text is its own prompt.
_M4_HUMAN_KEYS = ("human_text", "abstract")
_M4_MACHINE_KEYS = ("machine_abstract", "machine_text")


def _m4_cache():
    import os
    from pathlib import Path

    base = os.environ.get("UNTELL_CORPUS_DIR") or os.path.join(
        os.path.expanduser("~"), ".cache", "untell-corpora"
    )
    return Path(base) / "m4"


def fetch_m4(stems: tuple[str, ...], dest=None, timeout: int = 1800):
    """Blobless sparse checkout of only the requested data files."""
    import subprocess

    dest = dest or _m4_cache()
    data = dest / "data"
    if all((data / f"{s}.jsonl").exists() for s in stems):
        return data
    dest.mkdir(parents=True, exist_ok=True)
    logger.warning("fetching M4 subset (%s) to %s\n%s", ", ".join(stems), dest, M4_CITATION)
    if not (dest / ".git").exists() and any(dest.iterdir()):
        # Data restored from a cache or copied in by hand. `git clone` into a non-empty directory
        # fails with a message about the path, which reads as a network problem and is not one.
        missing = [s for s in stems if not (data / f"{s}.jsonl").exists()]
        raise DatasetUnavailable(
            f"{dest} holds files but no git checkout, so {len(missing)} missing file(s) "
            f"({', '.join(missing[:3])}) cannot be fetched. Delete it to re-fetch cleanly."
        )
    steps = []
    if not (dest / ".git").exists():
        steps.append(["git", "clone", "--depth", "1", "--filter=blob:none", "--no-checkout",
                      "-q", M4_REPO, "."])
        steps.append(["git", "sparse-checkout", "init", "--no-cone"])
    steps.append(["git", "sparse-checkout", "set", *[f"/data/{s}.jsonl" for s in stems]])
    steps.append(["git", "checkout", "-q"])
    for step in steps:
        proc = subprocess.run(step, cwd=dest, capture_output=True, text=True,  # noqa: S603
                              timeout=timeout)
        if proc.returncode != 0:
            raise DatasetUnavailable(
                f"M4 fetch failed at `{' '.join(step[:3])}`: {(proc.stderr or '').strip()[:300]}"
            )
    return data


def _m4_text(value) -> str:
    """M4 stores some fields as a list of strings and others as one string.

    `peerread_*` ships `prompt` as a list of alternative instructions; `arxiv_*` ships it as a
    string. Assuming either shape crashes on the other, and coercing with `str()` would put a
    Python list repr into the corpus.
    """
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return " ".join(str(v).strip() for v in value if isinstance(v, str)).strip()
    return ""


def _m4_pick(row: dict, keys: tuple[str, ...]) -> str:
    for k in keys:
        text = _m4_text(row.get(k))
        if text:
            return text
    return ""


def load_m4(stems: tuple[str, ...] = ("arxiv_chatGPT",), min_words: int = 60,
            per_file: int | None = None) -> list[dict]:
    """Paired human/machine rows: ``{"text", "is_ai", "generator", "domain", "language"}``.

    Each source record gives TWO rows — the human answer and the machine answer to one prompt — so
    a subgroup is balanced by construction and false positives and false negatives are measured on
    the same material.
    """
    import json as _json

    data = fetch_m4(stems)
    rows: list[dict] = []
    for stem in stems:
        path = data / f"{stem}.jsonl"
        if not path.exists():
            raise DatasetUnavailable(f"M4: {path} was not fetched")
        domain, language = M4_FILES.get(stem, (stem, "en"))
        kept = 0
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = _json.loads(line)
                except _json.JSONDecodeError:
                    continue
                if per_file is not None and kept >= per_file:
                    break
                human = _m4_pick(r, _M4_HUMAN_KEYS)
                machine = _m4_pick(r, _M4_MACHINE_KEYS)
                prompt = _m4_text(r.get("prompt"))
                # The arxiv_bloomz release puts the prompt in `machine_text`. Scoring instructions
                # as a generation would corrupt the false-negative rate silently.
                if machine and prompt and machine[:200] == prompt[:200]:
                    continue
                gen = str(r.get("model") or stem.split("_")[-1])
                base = {"generator": gen, "domain": domain, "language": language, "source": stem}
                for text, is_ai in ((human, False), (machine, True)):
                    if text and len(text.split()) >= min_words:
                        rows.append({"text": text, "is_ai": is_ai, **base})
                kept += 1
    if not rows:
        raise DatasetUnavailable(f"M4: no rows survived the {min_words}-word floor")
    return rows
