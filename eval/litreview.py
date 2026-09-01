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
DETECTION = re.compile(
    r"machine[- ]generated text|AI-generated text|LLM-generated text|MGT detection"
    r"|AI text detect|detector",
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
