"""Reproduce the systematic literature pass this repo's research documents rest on.

`docs/research-verification.md` reports a count over the primary literature: of the
machine-generated-text detection papers published in the ACL Anthology, roughly a third address
robustness and evasion while **under 2% address false positives or fairness**. That number is the
argument for this project's existence, so it must not be something a reader has to take on trust
from a document. This module re-derives it.

It downloads Anthology volume metadata (the Anthology's own XML, published in its GitHub
repository), extracts every abstract, selects the detection-related subset by keyword, and counts
how many address each topic. Run it and you get the table; change ``VOLUMES`` and you extend the
survey.

**Why this exists rather than a saved spreadsheet.** The compiling environment could not reach
arxiv.org, aclanthology.org or most publishers — an organization egress policy — so the published
survey covers the Anthology and PubMed and says so. Shipping the *method* means the next person to
run it, on a machine without those restrictions, extends the coverage instead of repeating the
work. A bounded survey that can be re-run and widened is worth more than an unbounded claim.

    python -m eval.litreview                    # counts, from cached XML if present
    python -m eval.litreview --download         # fetch the volumes first (~67 MB)
    python -m eval.litreview --topic fairness   # list the papers behind one row
    python -m eval.litreview --json             # machine-readable

Counts are reported with the corpus size beside them, because "6 papers" means nothing without
"out of 397 detection papers out of 28,120 abstracts".
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)

ANTHOLOGY_XML = "https://raw.githubusercontent.com/acl-org/acl-anthology/master/data/xml"

# The volumes the published survey covers. Extend this list to widen the survey; a volume that does
# not exist yet is skipped with a warning rather than failing the run, because the Anthology
# publishes them as conferences complete.
VOLUMES: tuple[str, ...] = (
    # PRE-LLM VOLUMES. Not for the survey — every one of these predates ChatGPT, so they contribute
    # almost nothing to a count of detection papers. They are here because `eval/pre_llm_fpr.py`
    # builds its ground truth from Anthology text published no later than 2021, and without them it
    # returns ZERO abstracts: the repository's most-quoted false-positive number, "15.8% of 120
    # pre-LLM abstracts", could not be reproduced by the shipped tool at all. Verified to resolve;
    # note the Anthology uses year-only ids here (2021.acl, not 2021.acl-long), and that this
    # scheme only goes back to 2020 — 2018.acl and 2019.acl return 200 with an empty stub.
    "2020.acl", "2020.emnlp", "2020.coling", "2020.lrec", "2020.findings",
    "2021.acl", "2021.emnlp", "2021.naacl", "2021.eacl", "2021.findings", "2021.tacl", "2021.cl",
    # 2022 was missing entirely and nothing said so — the list jumped from 2021 to 2023, leaving a
    # hole in the middle of the survey's denominator that no comment acknowledged. It is the year
    # ChatGPT shipped (November), so most of it predates the thing the survey counts, but
    # machine-generated-text detection did not begin with ChatGPT: GPT-2 output detection, GROVER
    # and their successors are 2019-2022 work, and a survey that skips the year cannot say what it
    # excluded. 4,997 papers across seven volumes.
    "2022.acl", "2022.emnlp", "2022.findings", "2022.naacl", "2022.coling", "2022.lrec",
    "2022.aacl",
    # ROUND 69. Round sixty-eight found 2022 missing by hand; this is the systematic sweep that
    # should have followed immediately. Forty-three volumes across five years existed, resolved, and
    # were not indexed — 2,892 papers.
    #
    # ⚠️ The venues matter more than the count. `2023.eacl` (335 papers) and `2024.eacl` (281) are
    # main conferences. **`trustnlp` and `bea` are worse**: Trustworthy NLP and Building Educational
    # Applications are precisely where work on false accusation, fairness and classroom use would
    # appear, and this survey's headline finding is that such work is scarce. A venue list that omits
    # them under-samples the exact topics whose scarcity it reports — which is selection bias
    # pointing toward this project's own conclusion, the worst direction for it to point.
    "2022.tacl", "2022.cl", "2022.conll", "2022.wmt", "2022.semeval",
    "2022.sigdial", "2022.inlg", "2022.iwslt", "2022.starsem", "2022.bea",
    "2022.wnut", "2022.blackboxnlp", "2022.trustnlp", "2022.clinicalnlp", "2022.louhi",
    "2022.nlp4call", "2022.gem", "2023.eacl", "2023.cl", "2023.conll",
    "2023.wmt", "2023.semeval", "2023.sigdial", "2023.inlg", "2023.iwslt",
    "2023.starsem", "2023.bea", "2023.blackboxnlp", "2023.trustnlp", "2023.clinicalnlp",
    "2023.nlp4call", "2023.gem", "2024.eacl", "2024.cl", "2024.wmt",
    "2024.iwslt", "2024.clinicalnlp", "2024.nlp4call", "2025.iwslt", "2025.clinicalnlp",
    "2025.nlp4call", "2026.iwslt", "2026.clinicalnlp",
    # The last twenty, reported by `--gaps` after the forty-three above went in. Specialised
    # workshops mostly, and several with nothing to do with detection — `crac` is coreference,
    # `codi` discourse, `law` linguistic annotation. They are here anyway, because the rule that
    # makes a hole detectable is venue consistency across years, not a judgement about which venues
    # are on topic. Cherry-picking the on-topic ones is how a denominator acquires a thumb on it.
    # The eight `--gaps` reported after the twenty above went in: adding a venue for one year makes
    # its absence in every other year a gap, so the sweep converges by iteration rather than at once.
    "2022.alta", "2022.argmining", "2022.clpsych", "2022.codi", "2022.crac",
    "2022.insights", "2022.law", "2022.mrl",
    "2022.nlp4dh", "2022.nlp4pi", "2022.nlpcss", "2022.paclic", "2022.privatenlp",
    "2022.sdp", "2022.wassa", "2023.alta", "2023.argmining", "2023.codi",
    "2023.crac", "2023.insights", "2023.law", "2023.mrl", "2023.nlp4dh",
    "2023.paclic", "2023.ranlp", "2023.sicon", "2023.wassa", "2025.ijcnlp",
    "2023.acl", "2023.emnlp", "2023.findings", "2023.tacl", "2023.ijcnlp",
    "2024.acl", "2024.emnlp", "2024.findings", "2024.naacl", "2024.lrec", "2024.tacl", "2024.inlg",
    "2025.acl", "2025.emnlp", "2025.findings", "2025.naacl", "2025.coling", "2025.tacl", "2025.cl",
    "2025.aacl", "2025.inlg", "2025.wmt",
    "2026.acl", "2026.findings", "2026.eacl", "2026.lrec", "2026.tacl", "2026.cl",
    # Workshops. Easy to forget and the reason an earlier version of this survey undercounted by
    # 3.5x: the Anthology holds ~1,700 volume files and the first pass sampled 28 of them. The
    # omission that mattered most was **2025.genaidetect** — an entire COLING workshop on detecting
    # AI-generated content, i.e. the single most on-topic venue that exists.
    "2024.trustnlp", "2024.wnut", "2024.bea", "2024.blackboxnlp", "2024.insights", "2024.nlpcss",
    "2024.argmining", "2024.wassa", "2024.sdp", "2024.semeval", "2024.conll", "2024.starsem",
    "2024.sigdial", "2024.paclic", "2024.alta", "2024.privatenlp", "2024.nlp4dh", "2024.clpsych",
    "2024.law", "2024.crac", "2024.codi", "2024.mrl", "2024.sicon", "2024.customnlp4u",
    "2024.nlp4pi", "2024.luhme",
    "2025.genaidetect", "2025.trustnlp", "2025.wnut", "2025.bea", "2025.blackboxnlp", "2025.gem",
    "2025.insights", "2025.argmining", "2025.sdp", "2025.semeval", "2025.conll", "2025.starsem",
    "2025.sigdial", "2025.ranlp", "2025.paclic", "2025.alta", "2025.privatenlp", "2025.nlp4dh",
    "2025.clpsych", "2025.law", "2025.crac", "2025.codi", "2025.mrl", "2025.sicon", "2025.nlp4pi",
    "2025.luhme",
    "2026.trustnlp", "2026.bea", "2026.gem", "2026.nlpcss", "2026.argmining", "2026.wassa",
    "2026.semeval", "2026.conll", "2026.starsem", "2026.sigdial", "2026.privatenlp", "2026.nlp4dh",
    "2026.clpsych", "2026.law", "2026.codi", "2026.customnlp4u",
)

# A paper counts as detection-related if it talks about detecting generated text at all. Kept broad
# on purpose: the point of the exercise is the *ratio between topics inside* this set, and a narrow
# filter would let the selection do the arguing.
# A bare `detector` used to be an alternative here, and it matched ANY detector: Chinese spelling
# correction, hallucination detection in machine translation, sarcasm, out-of-distribution detection.
# MEASURED: 213 of 526 matches — 40% — came in that way, and they fed every topic count and the
# ratio this project's strategy rests on. `detector` is kept, because papers say "we evaluate five
# detectors on student essays" without ever writing "AI-generated text", but only when an AI/LLM term
# sits within 40 characters of it.
#
# The tighter phrase-only filter was tested and rejected: it scores better on precision and drops
# 2026.eacl-srw.20 — the Czech result that disconfirms part of our own thesis, and one of the most
# load-bearing citations we have. For a RATIO, losing on-topic papers is worse than keeping some
# off-topic ones, because recall loss biases the topics unevenly while noise is roughly flat.
# The proximity window, in characters. Nobody chose 40 deliberately — round fifty-seven needed *a*
# number and this one worked. Round eighty-six swept it from 0 to 400 rather than leave a hidden
# parameter under a published ratio; `detection_pattern` and `--window-sweep` exist so the sweep is
# rerunnable rather than a one-off script. What it found is in `window_sensitivity`.
DETECTION_WINDOW = 40


def detection_pattern(window: int = DETECTION_WINDOW) -> re.Pattern[str]:
    """The detection filter at a given proximity window, so the window can be varied.

    `DETECTION` is this at the default. Building it in a function is what makes the parameter
    checkable: a constant regex hides `{0,40}` inside a string where no reader can vary it, and a
    number nobody can vary is a number nobody has tested.
    """
    return re.compile(
        r"machine[- ]generated text|AI-generated text|LLM-generated text|MGT detection"
        r"|AI text detect"
        # \b around AI/LLM/GPT is not cosmetic: with re.I a bare `AI` matches inside "training",
        # "domain" and "certain", which let a Chinese-spelling-correction paper in through the phrase
        # "detector or corrector and training".
        r"|(?:\bAI\b|\bLLM\b|\bGPT|machine-generated|machine generated|synthetic text|watermark)"
        rf"[\w\s\-,]{{0,{window}}}?detect(?:or|ion)"
        rf"|detect(?:or|ion)[\w\s\-,]{{0,{window}}}?"
        r"(?:\bAI\b|\bLLM\b|\bGPT|machine-generated|synthetic text)",
        re.I,
    )


DETECTION = detection_pattern()

TOPICS: dict[str, re.Pattern[str]] = {
    "robustness/paraphrase": re.compile(r"paraphras|adversarial|robustness|evad", re.I),
    "human-AI mixed/edited": re.compile(
        r"co-?written|human-edited|polish|hybrid|boundary|AI-assisted|mixed", re.I),
    "watermark": re.compile(r"watermark", re.I),
    "education/integrity": re.compile(r"academic integrity|student|classroom|education|essay", re.I),
    "calibration/thresholds": re.compile(r"calibrat|conformal|TPR@|operating point", re.I),
    "false positives/accusation": re.compile(
        r"false positive|false accusation|falsely (flag|accus)|FPR", re.I),
    # Added in round 56. The taxonomy had no row for it and it is 13.3% of the corpus — six times
    # the fairness row. The distinction matters more than the count: this work asks whether a
    # detector CAN read Urdu, Korean or Bangla, while the fairness row asks whether reading it harms
    # the people who wrote it. Same population, opposite question, and the field studies the
    # capability far more than the cost.
    "multilingual/cross-lingual": re.compile(
        r"multilingual|cross-?lingual|non-English|languages other than English"
        r"|low-resource language", re.I),
    "fairness/non-native bias": re.compile(
        r"non-native|second language|L2 writer|bias(ed)? against|fairness|demographic", re.I),
    # Deliberately narrow: `accessible` and `assistive` are excluded because they occur throughout
    # detection abstracts in the ordinary sense ("publicly accessible"), and counting them would
    # turn an honest zero into a soft dozen. The zero this reports is the point — see round sixteen
    # of the verification ledger.
    "disability/neurodivergence": re.compile(
        r"autis|neurodiver|ADHD|dyslex|disabilit|disabled", re.I),
}


def _flatten(element: ET.Element | None) -> str:
    """All text under an element, whitespace-normalised.

    Anthology titles and abstracts carry inline markup (``<fixed-case>``, ``<i>``, TeX math), so
    ``element.text`` alone silently truncates at the first tag.
    """
    if element is None:
        return ""
    return re.sub(r"\s+", " ", "".join(element.itertext())).strip()


def searchable(paper: dict) -> str:
    """The text every pattern in this module is matched against: **title first, then abstract.**

    ⚠️ **The order is part of the measurement, and that is not obvious.** `DETECTION` is
    proximity-based — round fifty-seven rewrote it that way to cut a 40% noise rate — so which words
    sit near which decides a match, and the words either side of the join change when the order does.

    MEASURED on the 186-volume corpus: title-first gives **612** detection papers and abstract-first
    gives **604**. Eight papers, 1.3%, flip on nothing but concatenation order — and they are the
    noise-floor cases (`InfoSurgeon`, factual-inconsistency detection, `Centering the Margins`),
    which is where a proximity rule is doing the most work.

    Round eighty-five found this by running an ad-hoc analysis that joined the other way and getting
    604 where the published figure said 612. Four call sites did the concatenation inline, two in
    each order by luck rather than choice; they all call this now, so an analysis cannot silently
    disagree with the survey it is analysing.
    """
    return f"{paper['title']} {paper['abstract']}"

def _fetch(url: str, name: str, attempts: int = 3) -> bytes | None:
    """Fetch one volume, retrying truncated transfers.

    A cut-off read (``IncompleteRead``) returns a partial body that is far larger than the 200-byte
    floor checked here, so without a retry it would be cached as if it were the whole volume and every
    count derived from it would be quietly short. That is not hypothetical: one run of this survey
    lost 3,394 abstracts to a single truncated volume and still printed a plausible total. A 404 is
    different — the volume does not exist — so it is reported once and not retried.
    """
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=240) as response:  # noqa: S310
                body = response.read()
        except urllib.error.HTTPError as exc:
            logger.warning("skipping %s: HTTPError: %s", name, exc)
            return None
        except Exception as exc:  # noqa: BLE001 - transient; worth another try
            if attempt == attempts - 1:
                logger.warning("skipping %s: %s: %s", name, type(exc).__name__, exc)
                return None
            logger.warning("retrying %s after %s: %s", name, type(exc).__name__, exc)
            continue
        if len(body) < 200:
            logger.warning("skipping %s: response too small to be a volume", name)
            return None
        # A byte floor is not enough. `2018.acl` and `2019.acl` return HTTP 200 with a 743-byte
        # stub containing zero papers — the Anthology used the old `P18-1001` id scheme then, in
        # differently-named files. Cached, those look like successful downloads forever and
        # contribute nothing, which is how four dead volumes sat in the list for a whole round.
        try:
            papers = len(ET.fromstring(body).findall(".//paper"))
        except ET.ParseError as exc:
            logger.warning("skipping %s: not parseable XML: %s", name, exc)
            return None
        if papers == 0:
            logger.warning("skipping %s: parses to zero papers", name)
            return None
        return body
    return None



# Venues the Anthology publishes under a `YEAR.venue` id. Not the whole Anthology — it is every
# venue any year of `VOLUMES` names, which is what makes a hole detectable: if a venue is worth
# indexing in one year it is worth indexing in the next, and the gap is the finding.
# The survey counts detection papers; the 2020-2021 volumes are in VOLUMES for a different corpus
# entirely (`eval/pre_llm_fpr.py` builds human ground truth from text published no later than 2021)
# and predate the field. `volume_gaps` starts here so it does not report a workshop's absence from a
# year the survey does not claim to cover.
SURVEY_FROM_YEAR = "2022"


def known_venues() -> tuple[str, ...]:
    """Every venue slug appearing anywhere in :data:`VOLUMES`."""
    return tuple(sorted({v.split(".", 1)[1] for v in VOLUMES if "." in v}))


def volume_gaps(years: tuple[str, ...] | None = None) -> list[str]:
    """Volume ids that exist in the Anthology, are not in :data:`VOLUMES`, and should be.

    Round sixty-eight found 2022 missing by hand. Round sixty-nine swept for the rest and found
    **forty-three** volumes across five years — 2,892 papers — including `2023.eacl` and
    `2024.eacl`, two main conferences.

    ⚠️ **The venues mattered more than the count.** `trustnlp` and `bea` — Trustworthy NLP, and
    Building Educational Applications — are exactly where work on false accusation, fairness and
    classroom use appears, and this survey's headline finding is that such work is scarce. Omitting
    them under-samples the topics whose scarcity is being reported, which is selection bias pointing
    toward the conclusion. Adding them moved `education/integrity` from 7.5% to 7.9% and
    `false positives/accusation` from 2.0% to 2.2%: the right direction, and small.

    ⚠️ **The rule does not converge on its own, and the first version of this said it had.** Adding
    a venue for one year makes its absence in every OTHER year a gap, so closing forty-three holes
    opened sixty-two more. Fifty-four of those were 2020 and 2021 — years that are in `VOLUMES`
    only to give `eval/pre_llm_fpr.py` its ground truth, as the comment on them says, and that
    predate the field the survey counts. Probing them for survey venues is a category error, so the
    sweep starts at :data:`SURVEY_FROM_YEAR`.

    Network-dependent, so this is a tool rather than a unit test — `--gaps` runs it. It reports
    rather than mutates: which volumes to add is an editorial call about scope, not something a
    survey should widen behind its author's back.
    """
    years = years or tuple(sorted(
        y for y in {v.split(".", 1)[0] for v in VOLUMES} if y >= SURVEY_FROM_YEAR))
    have = set(VOLUMES)
    gaps = []
    for year in years:
        for venue in known_venues():
            vid = f"{year}.{venue}"
            if vid in have:
                continue
            raw = _fetch(f"{ANTHOLOGY_XML}/{vid}.xml", vid, attempts=1)
            if raw:
                gaps.append(vid)
    return gaps


def download(cache: Path, volumes: tuple[str, ...] = VOLUMES) -> int:
    """Fetch volume XML into ``cache``. Returns how many are available locally afterwards."""
    cache.mkdir(parents=True, exist_ok=True)
    for name in volumes:
        target = cache / f"{name}.xml"
        if target.exists() and target.stat().st_size > 200:
            continue
        url = f"{ANTHOLOGY_XML}/{name}.xml"
        body = _fetch(url, name)
        if body is None:
            continue
        target.write_bytes(body)
    return len(list(cache.glob("*.xml")))


def load_abstracts(cache: Path) -> list[dict[str, str]]:
    """Every paper in the cached volumes that has an abstract."""
    papers: list[dict[str, str]] = []
    for path in sorted(cache.glob("*.xml")):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            logger.warning("could not parse %s: %s", path.name, exc)
            continue
        collection = root.get("id")
        for volume in root.findall("volume"):
            for paper in volume.findall("paper"):
                abstract = _flatten(paper.find("abstract"))
                if not abstract:
                    continue
                papers.append({
                    "id": f"{collection}-{volume.get('id')}.{paper.get('id')}",
                    "title": _flatten(paper.find("title")),
                    "abstract": abstract,
                })
    return papers


# Detection problems that are not machine-generated-text detection. A paper whose TITLE names one
# of these and does not name MGT is about hallucination, or fake news, or toxicity — a different
# question that shares the word "detection".
#
# This is measured rather than excluded, and that is a deliberate choice. Round thirty established
# that a stricter filter scores better on precision and drops `2026.eacl-srw.20`, the Czech result
# that disconfirms part of this project's own thesis. For a RATIO, losing on-topic papers biases the
# topics unevenly while noise is roughly flat — MEASURED in round fifty-seven, removing all 80 of
# them moves no topic share by more than 1.7 points. So the survey reports its error term instead of
# claiming a precision it does not have.
OTHER_DETECTION = re.compile(
    r"hallucinat|factual (in)?consisten|fake news|misinformation|disinformation|hate speech"
    r"|abus(e|ive)|toxic|spam|bot detection|stance detection|out-of-distribution|out-of-domain"
    r"|spelling", re.I)

NAMES_MGT = re.compile(
    r"machine[- ]generated text|AI-generated text|LLM-generated text|MGT detection|AI text detect"
    r"|machine-generated content|authorship", re.I)


def noise_floor(papers: list[dict]) -> dict:
    """How much of the detection corpus is a different detection problem, and what it costs.

    Returns the off-topic count and every topic's share with and without them, so a reader can see
    the error term on the ratio this project argues from rather than take the count on trust.
    """
    detection = [p for p in papers if DETECTION.search(searchable(p))]
    off = [p for p in detection
           if OTHER_DETECTION.search(p["title"]) and not NAMES_MGT.search(p["title"])]
    kept = [p for p in detection if p not in off]

    def share(subset: list[dict], pattern: re.Pattern[str]) -> float:
        if not subset:
            return 0.0
        n = sum(1 for p in subset if pattern.search(searchable(p)))
        return round(100.0 * n / len(subset), 1)

    topics = {
        name: {"with": share(detection, rx), "without": share(kept, rx)}
        for name, rx in TOPICS.items()
    }
    moves = [abs(v["with"] - v["without"]) for v in topics.values()]
    return {
        "detection_papers": len(detection),
        "other_detection_problem": len(off),
        "off_topic_share": round(100.0 * len(off) / len(detection), 1) if detection else 0.0,
        "topics": topics,
        "largest_share_move": round(max(moves), 1) if moves else 0.0,
        "examples": [p["id"] for p in off[:5]],
        "note": (
            "These are measured, not excluded. A stricter filter scores better on precision and "
            "drops on-topic papers unevenly across topics — including one that disconfirms this "
            "project's own thesis. See rounds 30 and 57 of docs/research-verification.md."
        ),
    }


SWEEP_WINDOWS = (0, 10, 20, 30, 40, 60, 80, 120, 200, 400)


def window_sensitivity(
    papers: list[dict[str, str]], windows: tuple[int, ...] = SWEEP_WINDOWS,
) -> dict[str, object]:
    """Every published survey figure, recomputed at each proximity window.

    The survey's counts rest on a filter whose recall is set by one number, `DETECTION_WINDOW`, that
    nobody chose deliberately. This varies it and reports what moves. Three things it establishes,
    MEASURED on the 186-volume corpus:

    **The windows nest.** Every wider window is a strict superset of every narrower one — 0 papers
    lost at any step from 0 to 400. So the parameter trades recall against precision along a single
    axis; it does not shuffle the corpus, and no result here is a reshuffling artefact.

    **The corpus size is very sensitive and the topic shares are not.** Detection papers run 343 at
    w=0 to 768 at w=400, a 2.2x range, while the off-topic noise floor climbs 3.2% to 15.5%. Across
    that whole range the largest move in any topic share is **4.3 points** (robustness, 28.0% down
    to 23.7%). The shares drift because the denominator takes on noise, so a share is quoted with
    its window; the ordering of the topics never changes.

    **The false-positives row saturates, and that is the finding.** It reaches 13 papers at w=30 and
    stays at 13 through w=400 — 192 further detection papers enter behind it and **not one of them
    is about false positives.** Robustness nearly doubles over the same sweep (93 to 182) and
    multilingual work is still growing at w=400. So the imbalance this project argues from is not
    the filter being too strict to find the false-positive literature: buying recall at any price in
    precision recruits none of it. `disability/neurodivergence` is the same story harder — 1 paper
    at w=20, and 243 further papers enter without a second.

    The ratio therefore moves *against* the objection: robustness-to-false-positives is 9.3x at the
    tightest window and 14.0x at the widest, with the published 12.1x sitting between them. There is
    no window at which the survey's claim gets weaker than the one it publishes by more than a
    third, and none at which it inverts.
    """
    texts = [searchable(p) for p in papers]
    rows: list[dict[str, object]] = []
    seen: dict[int, set[int]] = {}
    for window in windows:
        pattern = detection_pattern(window)
        hits = {i for i, text in enumerate(texts) if pattern.search(text)}
        seen[window] = hits
        detection = [texts[i] for i in sorted(hits)]
        off = sum(
            1 for i in sorted(hits)
            if OTHER_DETECTION.search(papers[i]["title"])
            and not NAMES_MGT.search(papers[i]["title"])
        )
        counts = {name: sum(1 for t in detection if rx.search(t)) for name, rx in TOPICS.items()}
        rows.append({
            "window": window,
            "detection_papers": len(hits),
            "off_topic_share": round(100.0 * off / len(hits), 1) if hits else 0.0,
            "topics": counts,
            "shares": {
                name: round(100.0 * n / len(hits), 1) if hits else 0.0
                for name, n in counts.items()
            },
        })

    lost = {
        f"{a}->{b}": len(seen[a] - seen[b]) for a, b in zip(windows, windows[1:])
    }
    widest = max(windows)
    saturates: dict[str, dict[str, int]] = {}
    for name in TOPICS:
        final = next(r for r in rows if r["window"] == widest)["topics"][name]
        at = next(r["window"] for r in rows if r["topics"][name] == final)
        after = next(r for r in rows if r["window"] == widest)["detection_papers"] - next(
            r for r in rows if r["window"] == at)["detection_papers"]
        saturates[name] = {"papers": final, "window": at, "papers_entering_after": after}

    moves = [
        max(r["shares"][name] for r in rows) - min(r["shares"][name] for r in rows)
        for name in TOPICS
    ]
    return {
        "rows": rows,
        "papers_lost_when_widening": lost,
        "nested": all(v == 0 for v in lost.values()),
        "saturates": saturates,
        "largest_share_move": round(max(moves), 1) if moves else 0.0,
    }


# Round eighty-six swept the detection filter. This is the second filter in the same series, and it
# was just as unchosen: a topic's count is whatever its regex happens to match. Broadening a topic
# is not a neutral act — widen it far enough and it matches English rather than a subject — so the
# ladders below go from the shipped pattern outward in steps that each still *mean* the topic, plus
# one final rung that deliberately does not, to show what the failure looks like from inside.
TOPIC_LADDERS: dict[str, tuple[tuple[str, str], ...]] = {
    "false positives/accusation": (
        ("shipped", r"false positive|false accusation|falsely (flag|accus)|FPR"),
        ("+ type I error, specificity",
         r"false positive|false accusation|falsely (flag|accus)|FPR|type[- ]I error|specificity"),
        ("+ wrongly, mistakenly",
         r"false positive|false accusation|falsely (flag|accus)|FPR|type[- ]I error|specificity"
         r"|wrongl(y|ful)|mistakenly (flag|accus|classif)"),
        ("+ human text misclassified",
         r"false positive|false accusation|falsely (flag|accus)|FPR|type[- ]I error|specificity"
         r"|wrongl(y|ful)|mistakenly (flag|accus|classif)"
         r"|human[- ]written text as (machine|AI|LLM)"
         r"|misclassif\w* (as )?(machine|AI|LLM)[- ]generated|human text (is |being )?(mis)?classif"),
        ("+ over-flagging, accusation, unfairness",
         r"false positive|false accusation|falsely (flag|accus)|FPR|type[- ]I error|specificity"
         r"|wrongl(y|ful)|mistakenly (flag|accus|classif)"
         r"|human[- ]written text as (machine|AI|LLM)"
         r"|misclassif\w* (as )?(machine|AI|LLM)[- ]generated|human text (is |being )?(mis)?classif"
         r"|over[- ]?flag|innocent|accus\w+|unfair\w*"),
        # The rung that fails, kept on purpose. See `topic_sensitivity`.
        ("+ reliability, trust, consequence (NOT a topic pattern)",
         r"false positive|false accusation|falsely (flag|accus)|FPR|type[- ]I error|specificity"
         r"|wrongl(y|ful)|mistakenly (flag|accus|classif)"
         r"|human[- ]written text as (machine|AI|LLM)"
         r"|misclassif\w* (as )?(machine|AI|LLM)[- ]generated|human text (is |being )?(mis)?classif"
         r"|over[- ]?flag|innocent|accus\w+|unfair\w*"
         r"|reliab\w+|trustworth\w+|consequence"),
    ),
    "robustness/paraphrase": (
        ("shipped", r"paraphras|adversarial|robustness|evad"),
        ("+ attack, perturbation, obfuscation",
         r"paraphras|adversarial|robustness|evad|attack|perturb|obfuscat"),
        ("+ rewriting, humanizing, spoofing",
         r"paraphras|adversarial|robustness|evad|attack|perturb|obfuscat"
         r"|rewrit|humaniz|spoof|circumvent|bypass"),
    ),
}


def term_lift(papers: list[dict[str, str]], pattern: str) -> dict[str, float]:
    """How much more often a term appears in detection papers than in the corpus at large.

    This is the instrument that tells a topic term from a word. A pattern matching 7% of the *whole*
    Anthology is not measuring a topic within the detection subset — it is measuring English, and a
    count built on it will look like a large finding while carrying almost no information.

    Lift near 1 means the term is background. MEASURED on the 186-volume corpus: `false positive`
    has lift 6.1 and `falsely flag/accus` 51.1, while a `reliab` stem appears in **7.1% of every
    abstract in the Anthology** at lift 2.1 and `specificity` at lift 1.1. That is the whole
    difference between the ladder rungs that mean something and the one that does not.
    """
    rx = re.compile(pattern, re.I)
    corpus = sum(1 for p in papers if rx.search(searchable(p)))
    detection = [p for p in papers if DETECTION.search(searchable(p))]
    hits = sum(1 for p in detection if rx.search(searchable(p)))
    corpus_rate = 100.0 * corpus / len(papers) if papers else 0.0
    detection_rate = 100.0 * hits / len(detection) if detection else 0.0
    return {
        "corpus_rate": round(corpus_rate, 2),
        "detection_rate": round(detection_rate, 2),
        "lift": round(detection_rate / corpus_rate, 1) if corpus_rate else float("inf"),
    }


def topic_sensitivity(papers: list[dict[str, str]]) -> dict[str, object]:
    """The survey's second filter, varied the way round eighty-six varied the first.

    A topic count is whatever its regex matches, and the false-positives regex is four alternatives
    long. If widening it to every reasonable synonym found sixty papers instead of thirteen, this
    project's central claim would be an artefact of a narrow pattern rather than a fact about the
    literature. So it is widened, in rungs that each still mean the topic.

    MEASURED on the 612 detection papers: false positives goes **13 → 16 → 16 → 17 → 21** across
    four meaning-preserving broadenings, and robustness **157 → 176 → 184**. Over all twelve
    combinations the ratio runs **7.5x to 14.2x** and never approaches parity. The shipped 13 is on
    the conservative side — the broadest honest rung adds eight papers, some of which plainly belong
    (*Almost AI, Almost Human: The Challenge of Detecting AI-Polished Writing*) — so the row is
    reported with its range rather than quietly rewritten, on the round-thirty principle that a
    survey states its error term instead of picking the filter it prefers.

    A second fact falls out of the same table: **the shipped pattern has the highest lift of any
    rung** (7.1, against 3.6, 3.4, 3.6 and 3.3 for the broadenings). Every widening buys papers by
    spending discrimination. So the shipped row is not merely conservative on count — it is the most
    informative pattern in the ladder, which is the opposite of what a filter tuned to flatter a
    conclusion would look like.

    ⚠️ **One rung takes the ratio to 1.3x, and it is in the table on purpose.** Adding
    `reliab|trustworth|consequence` lifts false positives from 21 papers to 123. It looks like a
    refutation and is not one: `term_lift` shows those terms in 7.1%, 1.0% and 0.5% of *every*
    abstract in the Anthology, at lifts of 2.1, 2.3 and 2.8 — near-background words that match any
    abstract claiming its method is reliable. The rung is kept because a reader who broadens the
    pattern themselves will land on exactly it, and should find it already measured and already
    explained rather than think they have overturned something.
    """
    detection = [p for p in papers if DETECTION.search(searchable(p))]
    texts = [searchable(p) for p in detection]

    rungs: dict[str, list[dict[str, object]]] = {}
    for topic, ladder in TOPIC_LADDERS.items():
        rungs[topic] = []
        for name, pattern in ladder:
            rx = re.compile(pattern, re.I)
            n = sum(1 for t in texts if rx.search(t))
            rungs[topic].append({
                "rung": name,
                "papers": n,
                "share": round(100.0 * n / len(detection), 1) if detection else 0.0,
                "lift": term_lift(papers, pattern)["lift"],
                "honest": "NOT a topic pattern" not in name,
            })

    honest_fp = [r for r in rungs["false positives/accusation"] if r["honest"]]
    honest_rob = [r for r in rungs["robustness/paraphrase"] if r["honest"]]
    ratios = [
        rob["papers"] / fp["papers"] for fp in honest_fp for rob in honest_rob if fp["papers"]
    ]
    return {
        "detection_papers": len(detection),
        "rungs": rungs,
        "ratio_min": round(min(ratios), 1) if ratios else 0.0,
        "ratio_max": round(max(ratios), 1) if ratios else 0.0,
        "note": (
            "Ratios are over the rungs that still mean the topic. The excluded rung is reported "
            "above with its lift, because it is what a reader broadening the pattern will hit."
        ),
    }


def survey(papers: list[dict[str, str]]) -> dict[str, object]:
    """Counts per topic over the detection subset, plus the corpus sizes that give them meaning."""
    detection = [p for p in papers if DETECTION.search(searchable(p))]
    counts = {
        topic: sum(1 for p in detection if pattern.search(searchable(p)))
        for topic, pattern in TOPICS.items()
    }
    return {"abstracts": len(papers), "detection_papers": len(detection), "topics": counts}


def papers_for_topic(papers: list[dict[str, str]], topic: str) -> list[dict[str, str]]:
    """The detection papers behind one row, so a count can be audited rather than believed."""
    pattern = TOPICS[topic]
    return [
        p for p in papers
        if DETECTION.search(searchable(p))
        and pattern.search(searchable(p))
    ]


def cited_acl_ids(root: Path) -> dict[str, list[str]]:
    """Every ACL Anthology identifier this repository cites, and the files citing it.

    A citation that does not resolve is the worst kind of documentation defect: it looks like
    evidence, survives review, and cannot be checked without the corpus. This repo already refuses
    to publish an unattributed number — a fabricated or mistyped attribution is the same failure one
    level down, and until now nothing checked for it.
    """
    pattern = re.compile(r"aclanthology\.org/([0-9A-Za-z._-]+?)/")
    found: dict[str, list[str]] = {}
    for path in sorted([*root.glob("*.md"), *(root / "docs").glob("*.md"),
                        *(root / "untell").rglob("*.py"), *(root / "eval").glob("*.py"),
                        *(root / "untell" / "references").glob("*.md")]):
        try:
            body = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in pattern.finditer(body):
            found.setdefault(match.group(1), []).append(path.name)
    return found


def paper_index(cache: Path) -> dict[str, str]:
    """Anthology id -> title, for every paper in the cached volumes."""
    index: dict[str, str] = {}
    for path in sorted(cache.glob("*.xml")):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        collection = root.get("id")
        for volume in root.findall("volume"):
            for paper in volume.findall("paper"):
                index[f"{collection}-{volume.get('id')}.{paper.get('id')}"] = _flatten(
                    paper.find("title"))
    return index


def abstract_index(cache: Path) -> dict[str, str]:
    """Anthology id -> title and abstract, for every paper in the cached volumes.

    `paper_index` deliberately returns titles only. Cross-checking a figure needs the abstract, and
    reaching for the wrong one silently compares every number against a title — which reports the
    whole corpus as unsupported and looks exactly like a catastrophic finding.
    """
    index: dict[str, str] = {}
    for path in sorted(cache.glob("*.xml")):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        collection = root.get("id")
        for volume in root.findall("volume"):
            for paper in volume.findall("paper"):
                pid = f"{collection}-{volume.get('id')}.{paper.get('id')}"
                index[pid] = (_flatten(paper.find("title")) + " "
                              + _flatten(paper.find("abstract")))
    return index


_FIGURE = re.compile(r"\d+(?:\.\d+)?[kKmM]?%?")
_BOLD_RUN = re.compile(r"\*\*([^*\n]{0,160}?)\*\*")
_CITATION = re.compile(r"aclanthology\.org/([0-9A-Za-z._-]+?)/")


def _figure_forms(token: str) -> set[str]:
    """The spellings one figure can take between a paper's abstract and a document quoting it."""
    core = token.rstrip("%").lower()
    forms = {token.lower(), core}
    if core.endswith("k"):
        forms |= {core[:-1] + "000", core[:-1] + ",000"}
    if core.endswith("m"):
        forms |= {core[:-1] + "000000", core[:-1] + ",000,000"}
    if "." in core:
        forms.add(core.rstrip("0").rstrip("."))
    return {f for f in forms if f}


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace(",", "").replace("\u00d7", " times "))


def _attribution_units(body: str) -> list[str]:
    """Split a document into the spans over which one citation can be said to attribute a figure.

    Paragraphs, except that a markdown TABLE is not one span. A table has no blank lines in it, so
    treating it as a paragraph credits every row's figures to whichever single paper happens to be
    linked anywhere in the table — which is how MASH's abstract came to be checked against another
    paper's evasion numbers from a different row. Each row carries its own citation, so each row is
    its own unit.
    """
    units: list[str] = []
    for para in re.split(r"\n\s*\n", body):
        if any(line.lstrip().startswith("|") for line in para.splitlines()):
            units.extend(para.splitlines())
        else:
            units.append(para)
    return units


def unsupported_figures(repo_root: Path, cache: Path) -> list[dict[str, str]]:
    """Bolded figures stated in a paragraph that cites exactly one Anthology paper, and that do not
    appear in that paper's abstract.

    This is a REVIEW TOOL, not a pass/fail check, and the distinction matters. A paragraph routinely
    and legitimately mixes a cited paper's numbers with our own measurements and with figures
    credited to another author by name — none of which are in the cited abstract. So a hit means
    "read this and confirm the reader cannot misattribute it", not "this is wrong".

    It exists because the failure it looks for is real: Beemo was published here as "11 detectors
    across 33 configurations" when its abstract says only 33 configurations, the 11 coming from the
    authors' repository. Nothing caught that except reading the abstract by hand.
    """
    index = abstract_index(cache)
    out: list[dict[str, str]] = []
    docs = sorted([*repo_root.glob("*.md"), *(repo_root / "docs").glob("*.md")])
    for path in docs:
        try:
            body = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for para in _attribution_units(body):
            cited = set(_CITATION.findall(para))
            if len(cited) != 1:
                continue  # zero or several papers: attribution is not unambiguous, so say nothing
            paper = cited.pop()
            abstract = index.get(paper)
            if not abstract:
                continue  # not in the cached volumes; `verify_citations` covers resolution
            haystack = _normalise(abstract)
            for run in _BOLD_RUN.finditer(para):
                claim = run.group(1)
                # A leading list ordinal is not a figure, and neither is a bare identifier.
                if "arXiv:" in claim or "arxiv.org" in claim:
                    continue  # an identifier mapping, not a measurement
                stripped = re.sub(r"^\d+\.\s+", "", claim)
                # A cross-reference to one of this repository's own rows is not a figure about the
                # cited paper. "row 28 was blocked" produced a finding against a paper that has no
                # 28 in it, which is true and meaningless.
                stripped = re.sub(r"\b(?:row|round|result|section|table|figure)\s+\d+", "",
                                  stripped, flags=re.I)
                # Digits inside a word are part of an identifier, not a measurement: H2L, GPT4,
                # M4GT. `_FIGURE` matched the 2 in H2L and reported it as an unsupported figure.
                stripped = re.sub(r"[A-Za-z]\d+[A-Za-z]*|\d+[A-Za-z]{2,}", "", stripped)
                for token in _FIGURE.findall(stripped):
                    if re.fullmatch(r"(19|20|21|25|26)\d\d", token.rstrip("%")):
                        continue  # a year
                    if any(form in haystack for form in _figure_forms(token)):
                        continue
                    out.append({"document": path.name, "paper": paper,
                                "figure": token, "context": claim.strip()[:120]})
    return out


def verify_citations(repo_root: Path, cache: Path) -> dict:
    """Check that every Anthology id this repo cites resolves to a real paper."""
    cited = cited_acl_ids(repo_root)
    index = paper_index(cache)
    unresolved = {cid: where for cid, where in cited.items() if cid not in index}
    return {"cited": len(cited), "indexed": len(index),
            "unresolved": unresolved, "resolved": len(cited) - len(unresolved)}


TRIAGE_PATH = Path(__file__).resolve().parent / "data" / "citation_triage.json"


def _triage_key(finding: dict) -> str:
    """A finding's identity, stable across edits that move it.

    Deliberately not the line number. The whole point of this baseline is to survive documents
    growing, and a line-keyed baseline goes stale the first time somebody inserts a paragraph.
    """
    return f"{finding['document']}|{finding['paper']}|{finding['figure']}"


def untriaged(findings: list[dict], triage_path: Path = TRIAGE_PATH) -> list[dict]:
    """Cross-check findings that nobody has read and cleared.

    ⚠️ **This exists because a manual triage with no machine-readable record silently goes stale.**
    An earlier round read all 25 findings this tool reported, established that none was a
    misattribution, and wrote that conclusion in prose. The count then drifted to 35 as the
    documents grew, and nothing could tell a new finding from one already cleared — so the honest
    options were to re-read all 35 or to trust a sentence about a different 25.

    With a baseline, reading a finding once is permanent and only new ones need attention. The
    ratchet is what turns a review tool into a check that can gate a commit, which is what the
    docstring above says this one deliberately is not.
    """
    if not triage_path.exists():
        return list(findings)
    cleared = {entry["key"] for entry in json.loads(triage_path.read_text())["cleared"]}
    return [f for f in findings if _triage_key(f) not in cleared]


def _render(result: dict[str, object]) -> str:
    topics: dict[str, int] = result["topics"]  # type: ignore[assignment]
    total = result["detection_papers"]
    lines = [
        f"{result['abstracts']} abstracts indexed; {total} detection-related.",
        "",
        f"{'topic':<30} {'papers':>7}  {'share':>7}",
    ]
    for topic, count in sorted(topics.items(), key=lambda kv: -kv[1]):
        share = f"{100 * count / total:.1f}%" if total else "n/a"
        lines.append(f"{topic:<30} {count:>7}  {share:>7}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path(".anthology-cache"),
                        help="where volume XML is stored (default: .anthology-cache)")
    parser.add_argument("--download", action="store_true", help="fetch missing volumes first")
    parser.add_argument("--topic", choices=sorted(TOPICS), help="list the papers behind one row")
    parser.add_argument("--verify-citations", action="store_true",
                        help="check every ACL id this repo cites against the cached corpus")
    parser.add_argument("--untriaged", action="store_true",
                        help="only cross-check findings nobody has read and cleared; this is the "
                             "pass/fail form, and it exits non-zero when one appears")
    parser.add_argument("--cross-check", action="store_true",
                        help="list bolded figures that do not appear in the cited paper's abstract "
                             "(a review list, not a pass/fail check)")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--noise-floor", action="store_true", dest="noise",
                        help="how much of the corpus is a different detection problem, and what "
                             "excluding it would do to every topic share")
    parser.add_argument("--topic-sweep", action="store_true", dest="topics",
                        help="broaden each load-bearing topic regex and report what the ratio does; "
                             "the survey's second filter, varied like the first")
    parser.add_argument("--window-sweep", action="store_true", dest="sweep",
                        help="recompute every figure at each proximity window, since the survey's "
                             "recall rests on one number nobody chose deliberately")
    parser.add_argument("--gaps", action="store_true",
                        help="volumes the Anthology has that VOLUMES does not; a review list, since "
                             "widening a survey's scope is an editorial call")
    parser.add_argument("--json", action="store_true", dest="as_json", help="machine-readable output")
    args = parser.parse_args(argv)

    if args.gaps:
        gaps = volume_gaps()
        if gaps:
            print(f"{len(gaps)} volume(s) exist and are not indexed:", file=sys.stderr)
            for vid in gaps:
                print(f"  {vid}")
        else:
            print("no gaps: every venue named in VOLUMES is indexed for every year it names",
                  file=sys.stderr)
        return 0

    if args.download:
        available = download(args.cache)
        print(f"{available} volume(s) cached in {args.cache}", file=sys.stderr)

    if not args.cache.exists() or not any(args.cache.glob("*.xml")):
        print(f"no volume XML in {args.cache} — run with --download first "
              f"(~67 MB; needs access to raw.githubusercontent.com)", file=sys.stderr)
        return 1

    if args.verify_citations:
        report = verify_citations(args.repo_root, args.cache)
        if args.as_json:
            print(json.dumps(report, indent=2))
        else:
            print(f"{report['resolved']}/{report['cited']} cited Anthology ids resolve "
                  f"against {report['indexed']} indexed papers")
            for cid, where in sorted(report["unresolved"].items()):
                print(f"  UNRESOLVED {cid} — cited in {', '.join(sorted(set(where)))}")
        return 1 if report["unresolved"] else 0

    if args.cross_check or args.untriaged:
        findings = unsupported_figures(args.repo_root, args.cache)
        if args.untriaged:
            new = untriaged(findings)
            if args.as_json:
                print(json.dumps(new, indent=2))
            else:
                print(f"{len(findings)} cross-check finding(s), {len(new)} not yet triaged.")
                for f in new:
                    print(f"  {f['document']} [{f['paper']}] {f['figure']!r} in: "
                          f"{f['context'][:110]}")
                if not new:
                    print("Every finding has been read and recorded in "
                          "eval/data/citation_triage.json.")
            return 1 if new else 0
        if args.as_json:
            print(json.dumps(findings, indent=2))
        else:
            print(f"{len(findings)} bolded figure(s) not found in the cited abstract.")
            print("Each needs a human read: a paragraph may legitimately mix the cited paper's "
                  "numbers\nwith our own measurements and with figures credited to another author "
                  "by name.\n")
            for f in findings:
                print(f"  {f['document']} [{f['paper']}] {f['figure']!r} in: {f['context']}")
        return 0

    papers = load_abstracts(args.cache)

    if args.noise:
        report = noise_floor(papers)
        if args.as_json:
            print(json.dumps(report, indent=2))
        else:
            print(f"{report['other_detection_problem']} of {report['detection_papers']} detection "
                  f"papers ({report['off_topic_share']}%) name a different detection problem.")
            print(f"e.g. {', '.join(report['examples'])}\n")
            print(f"{'topic':<32} {'with':>7} {'without':>9}")
            for name, row in report["topics"].items():
                print(f"{name:<32} {row['with']:>6.1f}% {row['without']:>8.1f}%")
            print(f"\nLargest share move: {report['largest_share_move']} points.")
            print(f"\n{report['note']}")
        return 0

    if args.topics:
        report = topic_sensitivity(papers)
        if args.as_json:
            print(json.dumps(report, indent=2))
        else:
            print(f"{report['detection_papers']} detection papers\n")
            for topic, rows in report["rungs"].items():
                print(f"{topic}")
                print(f"  {'rung':<46} {'papers':>7} {'share':>7} {'lift':>6}")
                for row in rows:
                    mark = " " if row["honest"] else "!"
                    print(f" {mark}{row['rung']:<46} {row['papers']:>7} "
                          f"{row['share']:>6.1f}% {row['lift']:>6.1f}")
                print()
            print(f"ratio across every honest combination: "
                  f"{report['ratio_min']}x to {report['ratio_max']}x")
            print(f"\n{report['note']}")
        return 0

    if args.sweep:
        report = window_sensitivity(papers)
        if args.as_json:
            print(json.dumps(report, indent=2))
        else:
            names = list(TOPICS)
            head = "  ".join(f"{n[:13]:>13}" for n in names)
            print(f"{'window':>6} {'papers':>7} {'noise':>7}  {head}")
            for row in report["rows"]:
                shares = "  ".join(f"{row['shares'][n]:>12.1f}%" for n in names)
                print(f"{row['window']:>6} {row['detection_papers']:>7} "
                      f"{row['off_topic_share']:>6.1f}%  {shares}")
            print(f"\nnested (no paper lost by widening): {report['nested']}")
            print(f"largest share move across the sweep: {report['largest_share_move']} points\n")
            print(f"{'topic':<32} {'papers':>7} {'saturates':>10} {'entering after':>15}")
            for name, sat in report["saturates"].items():
                print(f"{name:<32} {sat['papers']:>7} {'w=' + str(sat['window']):>10} "
                      f"{sat['papers_entering_after']:>15}")
        return 0

    if args.topic:
        hits = papers_for_topic(papers, args.topic)
        if args.as_json:
            print(json.dumps(hits, indent=2))
        else:
            print(f"{len(hits)} paper(s) under {args.topic!r}:")
            for paper in hits:
                print(f"  [{paper['id']}] {paper['title']}")
        return 0

    result = survey(papers)
    print(json.dumps(result, indent=2) if args.as_json else _render(result))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
