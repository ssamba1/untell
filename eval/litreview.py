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
DETECTION = re.compile(
    r"machine[- ]generated text|AI-generated text|LLM-generated text|MGT detection"
    r"|AI text detect"
    # \b around AI/LLM/GPT is not cosmetic: with re.I a bare `AI` matches inside "training",
    # "domain" and "certain", which let a Chinese-spelling-correction paper in through the phrase
    # "detector or corrector and training".
    r"|(?:\bAI\b|\bLLM\b|\bGPT|machine-generated|machine generated|synthetic text|watermark)"
    r"[\w\s\-,]{0,40}?detect(?:or|ion)"
    r"|detect(?:or|ion)[\w\s\-,]{0,40}?(?:\bAI\b|\bLLM\b|\bGPT|machine-generated|synthetic text)",
    re.I,
)

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


def survey(papers: list[dict[str, str]]) -> dict[str, object]:
    """Counts per topic over the detection subset, plus the corpus sizes that give them meaning."""
    detection = [p for p in papers if DETECTION.search(f"{p['title']} {p['abstract']}")]
    counts = {
        topic: sum(1 for p in detection if pattern.search(f"{p['title']} {p['abstract']}"))
        for topic, pattern in TOPICS.items()
    }
    return {"abstracts": len(papers), "detection_papers": len(detection), "topics": counts}


def papers_for_topic(papers: list[dict[str, str]], topic: str) -> list[dict[str, str]]:
    """The detection papers behind one row, so a count can be audited rather than believed."""
    pattern = TOPICS[topic]
    return [
        p for p in papers
        if DETECTION.search(f"{p['title']} {p['abstract']}")
        and pattern.search(f"{p['title']} {p['abstract']}")
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
    parser.add_argument("--cross-check", action="store_true",
                        help="list bolded figures that do not appear in the cited paper's abstract "
                             "(a review list, not a pass/fail check)")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true", dest="as_json", help="machine-readable output")
    args = parser.parse_args(argv)

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

    if args.cross_check:
        findings = unsupported_figures(args.repo_root, args.cache)
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
